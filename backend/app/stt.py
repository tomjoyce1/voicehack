"""Speechmatics real-time STT bridge (medical domain).

In demo mode we rely on a naive VAD + timer-based utterance grouping and emit
placeholder transcripts. In live mode, we forward audio to speechmatics-rt and
yield final transcripts.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import AsyncIterator, Optional

log = logging.getLogger(__name__)


class StudentSTT:
    """Collects student PCM16 @ 16kHz chunks and yields final utterances."""

    def __init__(self):
        self.demo = os.getenv("DEMO_MODE", "0") == "1" or not os.getenv("SPEECHMATICS_API_KEY")
        self._silence_ms = 0
        self._voiced_ms = 0
        self._utterance_started = False
        self._buffer: list[bytes] = []
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._sm_task: Optional[asyncio.Task] = None
        self._sm_client = None

    async def start(self):
        if self.demo:
            return
        try:
            from speechmatics_rt import (  # type: ignore
                AsyncClient,
                ConnectionSettings,
                TranscriptionConfig,
                OperatingPoint,
                ServerMessageType,
                AudioSettings,
            )

            settings = ConnectionSettings(
                url="wss://eu2.rt.speechmatics.com/v2",
                auth_token=os.getenv("SPEECHMATICS_API_KEY"),
            )
            cfg = TranscriptionConfig(
                language="en",
                domain=os.getenv("SPEECHMATICS_DOMAIN", "medical"),
                operating_point=OperatingPoint.ENHANCED,
                enable_partials=True,
            )
            audio_settings = AudioSettings(
                encoding="pcm_s16le", sample_rate=16000
            )
            client = AsyncClient(settings)

            @client.on(ServerMessageType.AddTranscript)  # type: ignore
            async def _on_final(msg):
                text = (msg.get("metadata", {}) or {}).get("transcript") or ""
                if text.strip():
                    await self._queue.put(text.strip())

            self._sm_client = client
            # We drive the connection manually via start_recognition/send_audio in push()
            await client.start_recognition(cfg, audio_settings)
        except Exception as e:
            log.warning("Speechmatics RT unavailable, falling back to demo STT: %s", e)
            self.demo = True

    async def push(self, pcm16_16k: bytes):
        if self.demo:
            await self._push_demo(pcm16_16k)
            return
        try:
            assert self._sm_client is not None
            await self._sm_client.send_audio(pcm16_16k)
        except Exception as e:
            log.warning("Speechmatics push failed, switching to demo: %s", e)
            self.demo = True
            await self._push_demo(pcm16_16k)

    async def _push_demo(self, pcm16_16k: bytes):
        # Energy-based VAD + end-of-utterance silence timer
        if not pcm16_16k:
            return
        import numpy as np

        arr = np.frombuffer(pcm16_16k, dtype=np.int16).astype(np.float32) / 32768.0
        rms = float(np.sqrt((arr * arr).mean() + 1e-9))
        ms = int(1000 * len(arr) / 16000)
        if rms > 0.015:
            self._voiced_ms += ms
            self._silence_ms = 0
            self._buffer.append(pcm16_16k)
            self._utterance_started = True
        else:
            self._silence_ms += ms
            if self._utterance_started and self._silence_ms > 800 and self._voiced_ms > 400:
                # emit a placeholder transcript based on buffer duration
                duration_s = sum(len(b) for b in self._buffer) / (16000 * 2)
                transcript = self._placeholder_transcript(duration_s)
                self._buffer.clear()
                self._voiced_ms = 0
                self._silence_ms = 0
                self._utterance_started = False
                await self._queue.put(transcript)

    def _placeholder_transcript(self, duration_s: float) -> str:
        samples = [
            "Hi, I'm the medical student — can I ask you some questions?",
            "Where exactly is the pain?",
            "And does it go anywhere else?",
            "How long has it been going on for?",
            "On a scale of one to ten, how bad is it?",
            "Any past medical problems I should know about?",
            "Do you smoke or drink alcohol?",
            "Any family history of anything similar?",
            "Are you taking any medications at the moment?",
            "I think this might be serious — I'm going to ask a doctor to see you urgently.",
        ]
        idx = min(len(samples) - 1, int(duration_s // 1.2) % len(samples))
        return samples[idx]

    async def utterances(self) -> AsyncIterator[str]:
        while True:
            u = await self._queue.get()
            yield u

    async def stop(self):
        try:
            if self._sm_client is not None:
                await self._sm_client.end_of_stream()
        except Exception:
            pass
