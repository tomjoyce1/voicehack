"""PatientSim backend — FastAPI WebSocket session server.

Single websocket per session. Client sends student audio chunks + diagnosis.
Server streams: transcripts (student + patient), patient TTS PCM, and final score.

Latency design:
- Message receive loop NEVER blocks on TTS/LLM — all long ops are fire-and-forget tasks.
- Active TTS/LLM tasks are tracked so they can be cancelled on interruption.
- When student speaks mid-reply, we cancel TTS and tell the frontend to stop playback.
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
from .speechmatics_insights import run_speechmatics_insights
from .stt import StudentSTT
from .thymia import ThymiaSidecar, generate_voice_interpretation, thymia_result_to_dict
from .tts import synthesize

load_dotenv()  # backend/.env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"), override=False)  # root .env fallback

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("patientsim")

# Quiet down noisy libs
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

app = FastAPI(title="PatientSim backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

RESULTS: Dict[str, dict] = {}
VOICE_ANALYSIS: Dict[str, dict] = {}
SPEECHMATICS: Dict[str, dict] = {}


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/results/{session_id}")
async def results(session_id: str):
    return RESULTS.get(session_id, {"error": "not_found"})


@app.get("/voice-analysis/{session_id}")
async def voice_analysis(session_id: str):
    result = VOICE_ANALYSIS.get(session_id)
    if result is None:
        return {"status": "pending"}
    return result


@app.get("/speechmatics/{session_id}")
async def speechmatics(session_id: str):
    result = SPEECHMATICS.get(session_id)
    if result is None:
        return {"status": "pending"}
    return result


@app.websocket("/ws/session/{session_id}")
async def session_ws(ws: WebSocket, session_id: str):
    await ws.accept()
    log.info("[%s] WS connected", session_id)

    scenario_id: Optional[str] = None
    actor: Optional[PatientActor] = None
    audio_count = 0
    student_audio_buffer = bytearray()

    # --- STT setup with interim transcript forwarding ---
    async def on_interim(text: str):
        log.debug("[%s] STT interim → frontend: '%s'", session_id, text)
        await send({
            "type": "transcript",
            "role": "student",
            "text": text,
            "final": False,
            "ts": int(time.time() * 1000),
        })

    log.info("[%s] Starting Gradium STT...", session_id)
    stt = StudentSTT(on_interim=on_interim)
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

    # --- Thymia voice biomarker sidecar (background, zero-cost) ---
    thymia_sidecar: Optional[ThymiaSidecar] = None
    thymia_key = os.getenv("THYMIA_API_KEY")
    if thymia_key:
        thymia_sidecar = ThymiaSidecar(api_key=thymia_key, session_id=session_id)
        await thymia_sidecar.start()

    # --- Interruption tracking ---
    active_tts_task: Optional[asyncio.Task] = None
    active_turn_task: Optional[asyncio.Task] = None

    async def send(msg: dict):
        try:
            await ws.send_json(msg)
        except Exception:
            pass

    async def cancel_patient_speech():
        """Cancel any in-progress LLM + TTS and tell frontend to stop playback."""
        nonlocal active_tts_task, active_turn_task
        if active_tts_task and not active_tts_task.done():
            active_tts_task.cancel()
        if active_turn_task and not active_turn_task.done():
            active_turn_task.cancel()
        # Always tell frontend to stop — backend may have finished sending
        # chunks but frontend is still playing buffered audio.
        log.info("[%s] Interrupting patient (stop_audio)", session_id)
        await send({"type": "stop_audio", "ts": int(time.time() * 1000)})

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
        except asyncio.CancelledError:
            log.info("[%s] TTS cancelled after %d chunks", session_id, chunk_count)
        except Exception as e:
            log.error("[%s] TTS error: %s", session_id, e)

    async def patient_turn(student_text: str):
        nonlocal active_tts_task
        if actor is None:
            log.warning("[%s] No actor yet, ignoring utterance", session_id)
            return
        log.info("[%s] LLM generating reply to: %s", session_id, student_text[:80])
        try:
            reply = await actor.reply(student_text)
            log.info("[%s] LLM reply: %s", session_id, reply[:80])
        except asyncio.CancelledError:
            log.info("[%s] LLM call cancelled", session_id)
            return
        except Exception as e:
            log.error("[%s] LLM error: %s", session_id, e)
            return
        transcript_log.append({"role": "patient", "text": reply})
        if thymia_sidecar:
            thymia_sidecar.push_transcript(reply, role="agent")
        await send({
            "type": "transcript",
            "role": "patient",
            "text": reply,
            "final": True,
            "ts": int(time.time() * 1000),
        })
        active_tts_task = asyncio.create_task(tts_and_stream(reply))
        await active_tts_task

    async def start_patient_turn(student_text: str):
        nonlocal active_turn_task
        await cancel_patient_speech()
        active_turn_task = asyncio.create_task(patient_turn(student_text))

    async def stt_loop():
        log.info("[%s] STT loop started", session_id)
        async for utt in stt.utterances():
            log.info("[%s] STT utterance: '%s'", session_id, utt)
            transcript_log.append({"role": "student", "text": utt})
            if thymia_sidecar:
                thymia_sidecar.push_transcript(utt, role="user")
            await send({
                "type": "transcript",
                "role": "student",
                "text": utt,
                "final": True,
                "ts": int(time.time() * 1000),
            })
            await start_patient_turn(utt)

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
                # Fire-and-forget — don't block the message loop
                active_tts_task = asyncio.create_task(tts_and_stream(opening))

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
                student_audio_buffer.extend(pcm)
                if thymia_sidecar:
                    thymia_sidecar.push_audio(pcm)

            elif t == "diagnosis":
                diagnosis = (msg.get("text") or "").strip()
                log.info("[%s] DIAGNOSIS submitted: %s", session_id, diagnosis)
                await cancel_patient_speech()
                sc = get_scenario(scenario_id or "") or get_scenario("chest-pain-stemi")
                assert sc is not None
                result = await score_session(sc, transcript_log, diagnosis, bio_timeline)
                RESULTS[session_id] = result
                RESULTS[scenario_id or session_id] = result
                await send({"type": "scored", "sessionId": session_id})

                # --- Speechmatics post-session insights (fire-and-forget) ---
                SPEECHMATICS[session_id] = {"status": "pending"}
                SPEECHMATICS[scenario_id or session_id] = SPEECHMATICS[session_id]
                audio_snapshot = bytes(student_audio_buffer)
                scenario_snapshot = sc
                sid_snapshot = session_id
                scid_snapshot = scenario_id or session_id

                async def _run_speechmatics():
                    try:
                        log.info("[%s] Speechmatics insights starting (%d bytes)...",
                                 sid_snapshot, len(audio_snapshot))
                        sx = await run_speechmatics_insights(audio_snapshot, scenario_snapshot)
                        SPEECHMATICS[sid_snapshot] = sx
                        SPEECHMATICS[scid_snapshot] = sx
                        # Merge medical_vocab into main RESULTS so the existing
                        # results-page card lights up without any extra polling.
                        if sx.get("status") == "ok" and sx.get("medical_vocab"):
                            for key in (sid_snapshot, scid_snapshot):
                                if key in RESULTS:
                                    RESULTS[key]["medical_vocab"] = sx["medical_vocab"]
                                    RESULTS[key]["speechmatics"] = sx
                        log.info("[%s] Speechmatics insights done: %s",
                                 sid_snapshot, sx.get("status"))
                    except Exception as e:
                        log.error("[%s] Speechmatics insights failed: %s", sid_snapshot, e)
                        SPEECHMATICS[sid_snapshot] = {"status": "error", "reason": str(e)}
                        SPEECHMATICS[scid_snapshot] = SPEECHMATICS[sid_snapshot]

                asyncio.create_task(_run_speechmatics())

                # Build Thymia voice analysis from accumulated snapshots
                if thymia_sidecar:
                    log.info("[%s] Building Thymia voice analysis (%d snapshots)...",
                             session_id, len(thymia_sidecar._snapshots))

                    async def _run_thymia():
                        try:
                            tr = thymia_sidecar.build_result(transcript_log)
                            if not tr.error:
                                tr.llm_interpretation = await generate_voice_interpretation(
                                    tr, transcript_log,
                                )
                            result_dict = thymia_result_to_dict(tr)
                            VOICE_ANALYSIS[session_id] = result_dict
                            VOICE_ANALYSIS[scenario_id or session_id] = result_dict
                            log.info("[%s] Thymia analysis complete: %s",
                                     session_id, "error" if tr.error else "success")
                        except Exception as e:
                            log.error("[%s] Thymia analysis failed: %s", session_id, e)
                            VOICE_ANALYSIS[session_id] = {"error": str(e)}

                    asyncio.create_task(_run_thymia())
                else:
                    log.info("[%s] No THYMIA_API_KEY — skipping voice analysis", session_id)
                    VOICE_ANALYSIS[session_id] = {"error": "No THYMIA_API_KEY configured"}
                    VOICE_ANALYSIS[scenario_id or session_id] = VOICE_ANALYSIS[session_id]

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
        if active_tts_task and not active_tts_task.done():
            active_tts_task.cancel()
        if active_turn_task and not active_turn_task.done():
            active_turn_task.cancel()
        stt_task.cancel()
        await stt.stop()
        if thymia_sidecar:
            await thymia_sidecar.stop()
        if actor:
            await actor.close()
        try:
            await ws.close()
        except Exception:
            pass
        log.info("[%s] Session ended", session_id)
