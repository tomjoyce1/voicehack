"""OSCEai backend — FastAPI WebSocket session server.

Single websocket per session. Client sends student audio chunks + diagnosis.
Server streams: transcripts (student + patient), patient TTS PCM, biomarker events, and final score.
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
from .sentinel import SentinelSidecar
from .stt import StudentSTT
from .tts import synthesize

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("osceai")

app = FastAPI(title="OSCEai backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# session_id -> stored results (for GET /results/{id})
RESULTS: Dict[str, dict] = {}


@app.get("/health")
async def health():
    return {
        "ok": True,
        "demo_mode": os.getenv("DEMO_MODE", "0") == "1",
        "scenarios": len(os.listdir(os.path.dirname(__file__))),
    }


@app.get("/results/{session_id}")
async def results(session_id: str):
    return RESULTS.get(session_id, {"error": "not_found"})


@app.websocket("/ws/session/{session_id}")
async def session_ws(ws: WebSocket, session_id: str):
    await ws.accept()
    log.info("WS connected: %s", session_id)

    scenario_id: Optional[str] = None
    blind = False
    actor: Optional[PatientActor] = None
    stt = StudentSTT()
    await stt.start()
    sentinel = SentinelSidecar(user_label=session_id)
    await sentinel.start()

    transcript_log: List[dict] = []
    bio_timeline: Dict[str, List[float]] = {
        "confidence": [],
        "anxiety": [],
        "pacing": [],
        "empathy": [],
    }
    stop_flag = asyncio.Event()

    async def send(msg: dict):
        try:
            await ws.send_json(msg)
        except Exception:
            pass

    async def tts_and_stream(text: str):
        async for chunk in synthesize(text):
            if not chunk:
                continue
            await send(
                {
                    "type": "patient_audio",
                    "data": base64.b64encode(chunk).decode("ascii"),
                    "ts": int(time.time() * 1000),
                }
            )

    async def patient_turn(student_text: str):
        if actor is None:
            return
        reply = await actor.reply(student_text)
        transcript_log.append({"role": "patient", "text": reply})
        await send(
            {
                "type": "transcript",
                "role": "patient",
                "text": reply,
                "final": True,
                "ts": int(time.time() * 1000),
            }
        )
        await tts_and_stream(reply)

    async def stt_loop():
        async for utt in stt.utterances():
            transcript_log.append({"role": "student", "text": utt})
            await send(
                {
                    "type": "transcript",
                    "role": "student",
                    "text": utt,
                    "final": True,
                    "ts": int(time.time() * 1000),
                }
            )
            await sentinel.send_transcript(utt)
            asyncio.create_task(patient_turn(utt))

    async def biomarker_loop():
        while not stop_flag.is_set():
            bm = sentinel.tick()
            bio_timeline["confidence"].append(bm.confidence)
            bio_timeline["anxiety"].append(bm.anxiety)
            bio_timeline["pacing"].append(bm.pacing)
            bio_timeline["empathy"].append(bm.empathy)
            await send(
                {
                    "type": "biomarker",
                    "confidence": bm.confidence,
                    "anxiety": bm.anxiety,
                    "pacing": bm.pacing,
                    "empathy": bm.empathy,
                    "ts": int(time.time() * 1000),
                }
            )
            await asyncio.sleep(1.2)

    stt_task = asyncio.create_task(stt_loop())
    bio_task = asyncio.create_task(biomarker_loop())

    try:
        while True:
            msg = await ws.receive_json()
            t = msg.get("type")
            if t == "start":
                scenario_id = msg.get("scenarioId") or session_id
                blind = bool(msg.get("blind"))
                sc = get_scenario(scenario_id)
                if sc is None:
                    # default to chest pain for free-practice / unknown ids
                    sc = get_scenario("chest-pain-stemi")
                assert sc is not None
                actor = PatientActor(sc, blind=blind)
                opening = actor.opening_line()
                transcript_log.append({"role": "patient", "text": opening})
                await send(
                    {
                        "type": "transcript",
                        "role": "patient",
                        "text": opening,
                        "final": True,
                        "ts": int(time.time() * 1000),
                    }
                )
                await tts_and_stream(opening)
            elif t == "audio":
                data = msg.get("data", "")
                try:
                    pcm = base64.b64decode(data)
                except Exception:
                    continue
                await stt.push(pcm)
                await sentinel.push_audio(pcm)
            elif t == "diagnosis":
                diagnosis = (msg.get("text") or "").strip()
                sc = get_scenario(scenario_id or "") or get_scenario("chest-pain-stemi")
                assert sc is not None
                result = await score_session(sc, transcript_log, diagnosis, bio_timeline)
                RESULTS[session_id] = result
                RESULTS[scenario_id or session_id] = result
                await send({"type": "scored", "sessionId": session_id})
                break
            elif t == "stop":
                break
    except WebSocketDisconnect:
        log.info("WS disconnect: %s", session_id)
    except Exception as e:
        log.exception("WS error: %s", e)
    finally:
        stop_flag.set()
        stt_task.cancel()
        bio_task.cancel()
        await stt.stop()
        await sentinel.stop()
        try:
            await ws.close()
        except Exception:
            pass
