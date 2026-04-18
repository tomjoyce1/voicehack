"""OSCEai backend — FastAPI WebSocket session server.

Single websocket per session. Client sends student audio chunks + diagnosis.
Server streams: transcripts (student + patient), patient TTS PCM, and final score.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import time
from typing import Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .patient_actor import PatientActor
from .scenarios import get_scenario
from .scoring import score_session
from .stt import StudentSTT
from .tts import synthesize

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("osceai")

# Quiet down noisy libs
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

app = FastAPI(title="OSCEai backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

RESULTS: Dict[str, dict] = {}


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/results/{session_id}")
async def results(session_id: str):
    return RESULTS.get(session_id, {"error": "not_found"})


@app.websocket("/ws/session/{session_id}")
async def session_ws(ws: WebSocket, session_id: str):
    await ws.accept()
    log.info("[%s] WS connected", session_id)

    scenario_id: Optional[str] = None
    actor: Optional[PatientActor] = None
    audio_count = 0

    # --- STT setup ---
    log.info("[%s] Starting Gradium STT...", session_id)
    stt = StudentSTT()
    try:
        await stt.start()
        log.info("[%s] STT ready", session_id)
    except Exception as e:
        log.error("[%s] STT failed to start: %s", session_id, e)
        await ws.close()
        return

    transcript_log: List[dict] = []
    bio_timeline: Dict[str, List[float]] = {
        "confidence": [], "anxiety": [], "pacing": [], "empathy": [],
    }
    stop_flag = asyncio.Event()

    async def send(msg: dict):
        try:
            await ws.send_json(msg)
        except Exception:
            pass

    async def tts_and_stream(text: str):
        log.info("[%s] TTS synthesizing: %s", session_id, text[:80])
        chunk_count = 0
        try:
            async for chunk in synthesize(text):
                if not chunk:
                    continue
                chunk_count += 1
                await send({
                    "type": "patient_audio",
                    "data": base64.b64encode(chunk).decode("ascii"),
                    "ts": int(time.time() * 1000),
                })
            log.info("[%s] TTS done: %d chunks sent", session_id, chunk_count)
        except Exception as e:
            log.error("[%s] TTS error: %s", session_id, e)

    async def patient_turn(student_text: str):
        if actor is None:
            log.warning("[%s] No actor yet, ignoring utterance", session_id)
            return
        log.info("[%s] LLM generating reply to: %s", session_id, student_text[:80])
        try:
            reply = await actor.reply(student_text)
            log.info("[%s] LLM reply: %s", session_id, reply[:80])
        except Exception as e:
            log.error("[%s] LLM error: %s", session_id, e)
            return
        transcript_log.append({"role": "patient", "text": reply})
        await send({
            "type": "transcript",
            "role": "patient",
            "text": reply,
            "final": True,
            "ts": int(time.time() * 1000),
        })
        await tts_and_stream(reply)

    async def stt_loop():
        log.info("[%s] STT loop started", session_id)
        async for utt in stt.utterances():
            log.info("[%s] STT utterance: '%s'", session_id, utt)
            transcript_log.append({"role": "student", "text": utt})
            await send({
                "type": "transcript",
                "role": "student",
                "text": utt,
                "final": True,
                "ts": int(time.time() * 1000),
            })
            asyncio.create_task(patient_turn(utt))

    stt_task = asyncio.create_task(stt_loop())

    try:
        while True:
            msg = await ws.receive_json()
            t = msg.get("type")

            if t == "start":
                scenario_id = msg.get("scenarioId") or session_id
                blind = bool(msg.get("blind"))
                log.info("[%s] START scenario=%s blind=%s", session_id, scenario_id, blind)
                sc = get_scenario(scenario_id)
                if sc is None:
                    sc = get_scenario("chest-pain-stemi")
                assert sc is not None
                actor = PatientActor(sc, blind=blind)
                opening = actor.opening_line()
                log.info("[%s] Opening line: %s", session_id, opening)
                transcript_log.append({"role": "patient", "text": opening})
                await send({
                    "type": "transcript",
                    "role": "patient",
                    "text": opening,
                    "final": True,
                    "ts": int(time.time() * 1000),
                })
                await tts_and_stream(opening)

            elif t == "audio":
                audio_count += 1
                data = msg.get("data", "")
                try:
                    pcm = base64.b64decode(data)
                except Exception:
                    log.warning("[%s] Bad base64 in audio msg #%d", session_id, audio_count)
                    continue
                if audio_count <= 5 or audio_count % 100 == 0:
                    log.debug("[%s] Audio #%d: %d bytes (%d samples@16kHz)",
                              session_id, audio_count, len(pcm), len(pcm) // 2)
                await stt.push(pcm)

            elif t == "diagnosis":
                diagnosis = (msg.get("text") or "").strip()
                log.info("[%s] DIAGNOSIS submitted: %s", session_id, diagnosis)
                sc = get_scenario(scenario_id or "") or get_scenario("chest-pain-stemi")
                assert sc is not None
                result = await score_session(sc, transcript_log, diagnosis, bio_timeline)
                RESULTS[session_id] = result
                RESULTS[scenario_id or session_id] = result
                await send({"type": "scored", "sessionId": session_id})
                break

            elif t == "stop":
                log.info("[%s] STOP received", session_id)
                break

            else:
                log.warning("[%s] Unknown msg type: %s", session_id, t)

    except WebSocketDisconnect:
        log.info("[%s] WS disconnect (audio chunks received: %d)", session_id, audio_count)
    except Exception as e:
        log.exception("[%s] WS error: %s", session_id, e)
    finally:
        log.info("[%s] Cleaning up...", session_id)
        stop_flag.set()
        stt_task.cancel()
        await stt.stop()
        try:
            await ws.close()
        except Exception:
            pass
        log.info("[%s] Session ended", session_id)
