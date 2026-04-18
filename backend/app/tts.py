"""Gradium TTS bridge. Streams PCM @ 48kHz mono back to the client.

In demo mode (no API key) we synthesize a soft placeholder tone so the frontend
waveform reacts and the session flow is still demonstrable.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import struct
from typing import AsyncIterator, Optional

try:
    import websockets
except Exception:  # pragma: no cover
    websockets = None  # type: ignore

log = logging.getLogger(__name__)

GRADIUM_WS = "wss://api.gradium.ai/v1/tts/stream"
SAMPLE_RATE = 48000
CHUNK_SAMPLES = 3840  # 80ms at 48kHz (matches Gradium chunking)


async def synthesize(text: str) -> AsyncIterator[bytes]:
    """Yield raw PCM16 mono 48kHz chunks for the given text."""
    api_key = os.getenv("GRADIUM_API_KEY")
    demo = os.getenv("DEMO_MODE", "0") == "1" or not api_key or websockets is None
    if demo:
        async for chunk in _demo_synthesize(text):
            yield chunk
        return

    voice_id = os.getenv("GRADIUM_VOICE_ID", "YTpq7expH9539ERJ")
    try:
        async with websockets.connect(
            GRADIUM_WS,
            extra_headers={"Authorization": f"Bearer {api_key}"},
            max_size=None,
        ) as ws:
            await ws.send(
                json.dumps(
                    {
                        "type": "setup",
                        "model_name": "default",
                        "voice_id": voice_id,
                        "output_format": "pcm",
                    }
                )
            )
            await ws.send(json.dumps({"type": "text", "text": text}))
            await ws.send(json.dumps({"type": "flush"}))
            await ws.send(json.dumps({"type": "end"}))
            while True:
                msg = await ws.recv()
                if isinstance(msg, (bytes, bytearray)):
                    yield bytes(msg)
                else:
                    data = json.loads(msg)
                    if data.get("type") in ("end", "done", "finished"):
                        break
    except Exception as e:
        log.warning("Gradium TTS failed, falling back to demo tone: %s", e)
        async for chunk in _demo_synthesize(text):
            yield chunk


async def _demo_synthesize(text: str) -> AsyncIterator[bytes]:
    """Synthesize a soft speech-like modulated tone proportional to text length.

    Not real speech — just enough for the waveform visual + latency demo.
    """
    duration = max(1.2, min(6.0, len(text) * 0.05))
    total_samples = int(duration * SAMPLE_RATE)
    phase = 0.0
    for start in range(0, total_samples, CHUNK_SAMPLES):
        end = min(start + CHUNK_SAMPLES, total_samples)
        samples = bytearray()
        for i in range(start, end):
            t = i / SAMPLE_RATE
            # formant-like sum of sinusoids, amplitude modulated by an envelope
            env = 0.5 * (1 - math.cos(math.pi * min(1.0, t / 0.2)))  # attack
            env *= 0.5 + 0.5 * math.sin(2 * math.pi * 3.5 * t)  # syllable rate
            v = (
                math.sin(2 * math.pi * 180 * t) * 0.35
                + math.sin(2 * math.pi * 330 * t) * 0.25
                + math.sin(2 * math.pi * 760 * t) * 0.15
            )
            s = int(max(-1, min(1, v * env * 0.7)) * 30000)
            samples += struct.pack("<h", s)
            phase += 1
        yield bytes(samples)
        await asyncio.sleep(CHUNK_SAMPLES / SAMPLE_RATE * 0.92)  # near-realtime pacing
