"""Gradium TTS bridge. Streams PCM16 @ 48kHz mono back to the client."""
from __future__ import annotations

import base64
import json
import logging
import os
from typing import AsyncIterator

import websockets

log = logging.getLogger(__name__)

GRADIUM_TTS_WS = "wss://api.gradium.ai/api/speech/tts"
SAMPLE_RATE = 48000


async def synthesize(text: str) -> AsyncIterator[bytes]:
    """Yield raw PCM16 mono 48kHz chunks for the given text."""
    api_key = os.getenv("GRADIUM_API_KEY")
    if not api_key:
        raise RuntimeError("GRADIUM_API_KEY is required")

    voice_id = os.getenv("GRADIUM_VOICE_ID", "YTpq7expH9539ERJ")

    async with websockets.connect(
        GRADIUM_TTS_WS,
        extra_headers={"x-api-key": api_key},
        max_size=None,
    ) as ws:
        await ws.send(json.dumps({
            "type": "setup",
            "model_name": "default",
            "voice_id": voice_id,
            "output_format": "pcm",
        }))

        ready = json.loads(await ws.recv())
        if ready.get("type") != "ready":
            raise RuntimeError(f"Gradium TTS setup failed: {ready}")

        await ws.send(json.dumps({"type": "text", "text": text}))
        await ws.send(json.dumps({"type": "end_of_stream"}))

        async for raw_msg in ws:
            if isinstance(raw_msg, (bytes, bytearray)):
                yield bytes(raw_msg)
            else:
                data = json.loads(raw_msg)
                if data.get("type") == "audio":
                    yield base64.b64decode(data["audio"])
                elif data.get("type") == "end_of_stream":
                    break
