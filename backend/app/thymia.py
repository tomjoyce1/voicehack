"""Thymia Sentinel — real-time voice biomarker analysis via WebSocket.

Streams student PCM16@16kHz audio + transcripts to wss://ws.thymia.ai.
Receives policy results with biomarker scores (distress, stress, etc.).

Reframes Thymia's patient-wellness labels for a doctor-performance context:
  - stress → vocal nervousness (pitch variation, tremor)
  - distress → voice strain (tension in vocal delivery)
  - depression_probability → hesitancy (uncertain intonation)

Runs as a background sidecar — zero impact on STT/TTS latency.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import websockets

log = logging.getLogger("osceai.thymia")

THYMIA_WS = "wss://ws.thymia.ai"
SAMPLE_RATE = 16000


@dataclass
class PolicySnapshot:
    """A single policy result at a point in time."""
    turn: int
    timestamp: float
    nervousness: float = 0.0
    voice_strain: float = 0.0
    hesitancy: float = 0.0
    emotions: Dict[str, float] = field(default_factory=dict)  # Psyche emotion scores
    concerns: List[str] = field(default_factory=list)
    alert_level: str = "none"
    confidence: str = "low"
    rationale: str = ""
    concordance: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class ThymiaResult:
    snapshots: List[PolicySnapshot] = field(default_factory=list)
    overall_nervousness: float = 0.0
    overall_voice_strain: float = 0.0
    overall_hesitancy: float = 0.0
    peak_stress_moment: str = ""
    calmest_moment: str = ""
    llm_interpretation: str = ""
    error: Optional[str] = None


class ThymiaSidecar:
    """Streams audio + transcripts to Thymia Sentinel WebSocket in background."""

    def __init__(self, api_key: str, session_id: str):
        self._api_key = api_key
        self._session_id = session_id
        self._ws = None
        self._ws_task: Optional[asyncio.Task] = None
        self._send_queue: asyncio.Queue = asyncio.Queue()
        self._snapshots: List[PolicySnapshot] = []
        self._progress: dict = {}
        self._connected = asyncio.Event()
        self._stopped = False
        self._audio_chunks_sent = 0
        self._transcripts_sent = 0

    async def start(self):
        """Connect to Thymia WebSocket in background."""
        self._ws_task = asyncio.create_task(self._run())
        try:
            await asyncio.wait_for(self._connected.wait(), timeout=10.0)
            log.info("[%s] Thymia Sentinel connected", self._session_id)
        except asyncio.TimeoutError:
            log.warning("[%s] Thymia Sentinel connection timeout", self._session_id)

    async def _run(self):
        try:
            async with websockets.connect(THYMIA_WS, max_size=None) as ws:
                self._ws = ws

                # Send config
                config = {
                    "api_key": self._api_key,
                    "user_label": f"osce-{self._session_id}",
                    "language": "en-GB",
                    "biomarkers": ["helios"],
                    "policies": [os.getenv("THYMIA_POLICY", "wellbeing-awareness")],
                    "audio_config": {
                        "sample_rate": SAMPLE_RATE,
                        "format": "pcm16",
                        "channels": 1,
                    },
                    "progress_updates": {
                        "enabled": True,
                        "interval_seconds": 2.0,
                    },
                }
                await ws.send(json.dumps(config))
                log.info("[%s] Thymia config sent, waiting for ack...", self._session_id)

                self._connected.set()

                sender = asyncio.create_task(self._send_loop(ws))
                receiver = asyncio.create_task(self._recv_loop(ws))

                done, pending = await asyncio.wait(
                    [sender, receiver],
                    return_when=asyncio.FIRST_EXCEPTION,
                )
                for t in pending:
                    t.cancel()
                for t in done:
                    exc = t.exception()
                    if exc and not isinstance(exc, asyncio.CancelledError):
                        log.error("[%s] Thymia subtask failed: %s", self._session_id, exc)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error("[%s] Thymia connection error: %s", self._session_id, e)
            self._connected.set()

    async def _send_loop(self, ws):
        """Send audio headers + PCM bytes and transcripts."""
        try:
            while not self._stopped:
                item = await self._send_queue.get()
                if item is None:
                    break

                if isinstance(item, bytes):
                    # Audio: send JSON header then raw bytes
                    header = json.dumps({
                        "type": "AUDIO_HEADER",
                        "track": "user",
                        "format": "pcm16",
                        "sample_rate": SAMPLE_RATE,
                        "channels": 1,
                        "bytes": len(item),
                    })
                    await ws.send(header)
                    await ws.send(item)
                    self._audio_chunks_sent += 1
                    if self._audio_chunks_sent <= 3 or self._audio_chunks_sent % 100 == 0:
                        log.debug("[%s] Thymia audio chunk #%d (%d bytes)",
                                  self._session_id, self._audio_chunks_sent, len(item))

                elif isinstance(item, dict):
                    # Transcript message
                    await ws.send(json.dumps(item))
                    self._transcripts_sent += 1
                    log.debug("[%s] Thymia transcript #%d: %s",
                              self._session_id, self._transcripts_sent, item.get("text", "")[:60])

        except asyncio.CancelledError:
            log.debug("[%s] Thymia send loop cancelled (sent %d audio, %d transcripts)",
                      self._session_id, self._audio_chunks_sent, self._transcripts_sent)

    async def _recv_loop(self, ws):
        """Receive policy results and progress updates."""
        msg_count = 0
        try:
            async for raw_msg in ws:
                if self._stopped:
                    break
                if isinstance(raw_msg, bytes):
                    continue

                msg_count += 1
                data = json.loads(raw_msg)
                msg_type = data.get("type", "")

                if msg_type == "POLICY_RESULT":
                    log.info("[%s] Thymia POLICY_RESULT raw: %s",
                             self._session_id, json.dumps(data, indent=2)[:2000])
                    snapshot = self._parse_policy_result(data)
                    self._snapshots.append(snapshot)
                    log.info("[%s] Thymia policy result: turn=%d alert=%s nervousness=%.2f concerns=%s",
                             self._session_id, snapshot.turn, snapshot.alert_level,
                             snapshot.nervousness, snapshot.concerns)

                elif msg_type == "PROGRESS":
                    self._progress = data.get("biomarkers", {})
                    helios = self._progress.get("helios", {})
                    log.debug("[%s] Thymia progress: speech=%.1fs/%.1fs processing=%s",
                              self._session_id,
                              helios.get("speech_seconds", 0),
                              helios.get("trigger_seconds", 0),
                              helios.get("processing", False))

                elif msg_type == "ERROR":
                    log.error("[%s] Thymia error: code=%s msg=%s",
                              self._session_id, data.get("error_code"), data.get("message"))

                else:
                    log.info("[%s] Thymia msg #%d type=%s: %s",
                             self._session_id, msg_count, msg_type, json.dumps(data)[:500])

        except asyncio.CancelledError:
            log.debug("[%s] Thymia recv loop cancelled (%d messages)", self._session_id, msg_count)

    def _parse_policy_result(self, data: dict) -> PolicySnapshot:
        """Extract doctor-framed biomarkers from a POLICY_RESULT message.

        Two data sources within each result:
        1. result.biomarker_summary — Psyche emotion scores (neutral, sad, etc.)
        2. result.raw_response.biomarker_summary — Helios clinical scores
           (anxiety_probability, distress, depression_probability) — needs 10s+ speech.
        """
        result = data.get("result", {})
        psyche = result.get("biomarker_summary", {})
        raw_resp = result.get("raw_response", {})
        helios = raw_resp.get("biomarker_summary", {})
        concordance = result.get("concordance_analysis", {})

        # Helios clinical scores (0 until 10s+ speech processed)
        anxiety = float(helios.get("anxiety_probability", 0))
        distress = float(helios.get("distress", 0))
        depression = float(helios.get("depression_probability", 0))

        # Psyche emotion scores — extract all non-meta keys
        emotions = {}
        for k, v in psyche.items():
            if k != "interpretation" and isinstance(v, (int, float)):
                emotions[k] = float(v)

        # Use Helios if available, otherwise derive from Psyche
        has_helios = anxiety > 0 or distress > 0 or depression > 0
        neutral = emotions.get("neutral", 0)

        if has_helios:
            nervousness = anxiety
            voice_strain = distress
            hesitancy = depression
        elif emotions:
            # Nervousness = all non-neutral emotion (sad, angry, fearful, etc.)
            nervousness = round(1.0 - neutral, 3) if neutral > 0 else 0.0
            voice_strain = emotions.get("sad", 0.0)
            hesitancy = emotions.get("<unk>", 0.0)
        else:
            nervousness = 0.0
            voice_strain = 0.0
            hesitancy = 0.0

        return PolicySnapshot(
            turn=data.get("triggered_at_turn", 0),
            timestamp=data.get("timestamp", time.time()),
            nervousness=nervousness,
            voice_strain=voice_strain,
            hesitancy=hesitancy,
            emotions=emotions,
            concerns=result.get("concerns", []),
            alert_level=result.get("alert", "none"),
            confidence=result.get("confidence", "low"),
            rationale=result.get("rationale", ""),
            concordance=concordance.get("scenario", ""),
            raw=data,
        )

    def push_audio(self, pcm16_16k: bytes):
        """Queue audio for Thymia. Non-blocking."""
        if not self._stopped:
            self._send_queue.put_nowait(pcm16_16k)

    def push_transcript(self, text: str, role: str = "user", is_final: bool = True):
        """Queue a transcript for Thymia. Non-blocking."""
        if not self._stopped:
            self._send_queue.put_nowait({
                "type": "TRANSCRIPT",
                "speaker": role,
                "text": text,
                "is_final": is_final,
                "language": "en-GB",
                "timestamp": time.time(),
            })

    def get_latest_snapshot(self) -> Optional[PolicySnapshot]:
        """Return most recent policy result, or None."""
        return self._snapshots[-1] if self._snapshots else None

    def build_result(self, transcript_log: List[dict]) -> ThymiaResult:
        """Build final result from accumulated snapshots."""
        for i, s in enumerate(self._snapshots):
            log.info("[%s] Snapshot #%d raw POLICY_RESULT:\n%s",
                     self._session_id, i, json.dumps(s.raw, indent=2)[:3000])
        if not self._snapshots:
            return ThymiaResult(error="No voice analysis data received (need ~10s of speech)")

        n = len(self._snapshots)
        result = ThymiaResult(
            snapshots=self._snapshots,
            overall_nervousness=sum(s.nervousness for s in self._snapshots) / n,
            overall_voice_strain=sum(s.voice_strain for s in self._snapshots) / n,
            overall_hesitancy=sum(s.hesitancy for s in self._snapshots) / n,
        )

        peak = max(self._snapshots, key=lambda s: s.nervousness)
        calmest = min(self._snapshots, key=lambda s: s.nervousness)

        # Find what was being discussed at peak/calm turns
        peak_topic = _topic_at_turn(peak.turn, transcript_log)
        calm_topic = _topic_at_turn(calmest.turn, transcript_log)

        result.peak_stress_moment = f"{peak_topic or f'turn {peak.turn}'} ({_pct(peak.nervousness)})"
        result.calmest_moment = f"{calm_topic or f'turn {calmest.turn}'} ({_pct(calmest.nervousness)})"

        return result

    async def stop(self):
        """Shut down the Thymia connection."""
        log.info("[%s] Thymia stopping (audio=%d, transcripts=%d, snapshots=%d)",
                 self._session_id, self._audio_chunks_sent, self._transcripts_sent,
                 len(self._snapshots))
        self._stopped = True
        self._send_queue.put_nowait(None)  # signal send loop to exit
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except (asyncio.CancelledError, Exception):
                pass


def _topic_at_turn(turn: int, transcript_log: List[dict]) -> str:
    """Find the student utterance closest to a given turn number."""
    student_utterances = [t for t in transcript_log if t.get("role") == "student"]
    if not student_utterances:
        return ""
    idx = min(turn - 1, len(student_utterances) - 1)
    if idx < 0:
        return ""
    text = student_utterances[idx].get("text", "")
    return text[:100] if text else ""


def _pct(v: float) -> str:
    return f"{round(v * 100)}%"


async def generate_voice_interpretation(
    result: ThymiaResult,
    transcript_log: List[dict],
) -> str:
    """Use Groq LLM to interpret voice biomarkers from a doctor's perspective."""
    import httpx

    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        return ""

    snapshot_summaries = []
    for s in result.snapshots:
        emotions_str = ", ".join(f"{k}={_pct(v)}" for k, v in s.emotions.items())
        snapshot_summaries.append(
            f"  Turn {s.turn}: nervousness={_pct(s.nervousness)}, "
            f"strain={_pct(s.voice_strain)}, hesitancy={_pct(s.hesitancy)}, "
            f"emotions=[{emotions_str}], alert={s.alert_level}, "
            f"rationale={s.rationale[:120]}"
        )

    transcript_text = "\n".join(
        f"  {t['role'].upper()}: {t['text']}" for t in transcript_log
    )

    prompt = f"""You are a communication coach for medical students. Analyse this student doctor's vocal performance during an OSCE exam.

VOICE BIOMARKERS (from vocal analysis of the DOCTOR's voice only):
Overall: nervousness={_pct(result.overall_nervousness)}, voice strain={_pct(result.overall_voice_strain)}, hesitancy={_pct(result.overall_hesitancy)}
Most nervous moment: {result.peak_stress_moment}
Calmest moment: {result.calmest_moment}

Per-turn analysis:
{chr(10).join(snapshot_summaries)}

TRANSCRIPT:
{transcript_text}

Write 3-4 sentences of actionable feedback about the student's vocal delivery. Focus on:
- Which topics made them sound nervous and why that matters clinically
- Whether their voice projected confidence to the patient
- Specific moments where vocal strain or hesitancy was notable
- What they did well vocally

Frame everything from "how a patient would perceive this doctor." No bullet points — flowing prose."""

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {groq_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                    "temperature": 0.4,
                    "max_tokens": 250,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return (data["choices"][0]["message"]["content"] or "").strip()
    except Exception as e:
        log.error("Thymia LLM interpretation failed: %s", e)
        return ""


def thymia_result_to_dict(result: ThymiaResult) -> dict:
    """Serialize ThymiaResult for JSON response."""
    if result.error:
        return {"error": result.error}

    return {
        "overall": {
            "nervousness": round(result.overall_nervousness, 3),
            "voice_strain": round(result.overall_voice_strain, 3),
            "hesitancy": round(result.overall_hesitancy, 3),
        },
        "peak_stress_moment": result.peak_stress_moment,
        "calmest_moment": result.calmest_moment,
        "llm_interpretation": result.llm_interpretation,
        "sections": [
            {
                "turn": s.turn,
                "nervousness": round(s.nervousness, 3),
                "voice_strain": round(s.voice_strain, 3),
                "hesitancy": round(s.hesitancy, 3),
                "emotions": {k: round(v, 3) for k, v in s.emotions.items()},
                "alert_level": s.alert_level,
                "confidence": s.confidence,
                "rationale": s.rationale,
                "concerns": s.concerns,
            }
            for s in result.snapshots
        ],
    }
