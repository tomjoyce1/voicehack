"""Gradium real-time STT bridge.

Streams student PCM16 audio to Gradium ASR WebSocket and yields final
utterances based on VAD (voice activity detection) turn-end signals.

All WebSocket sends go through a single send queue to avoid concurrent
writes which corrupt websockets framing.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from typing import AsyncIterator, Optional

import numpy as np
import websockets

log = logging.getLogger("osceai.stt")

GRADIUM_STT_WS = "wss://api.gradium.ai/api/speech/asr"
GRADIUM_SAMPLE_RATE = 24000
INPUT_SAMPLE_RATE = 16000
GRADIUM_FRAME_SIZE = 1920  # samples per frame (80ms at 24kHz)
GRADIUM_FRAME_BYTES = GRADIUM_FRAME_SIZE * 2


def _resample_16k_to_24k(pcm16_16k: bytes) -> bytes:
    samples = np.frombuffer(pcm16_16k, dtype=np.int16).astype(np.float32)
    if len(samples) == 0:
        return b""
    ratio = GRADIUM_SAMPLE_RATE / INPUT_SAMPLE_RATE
    new_len = int(len(samples) * ratio)
    indices = np.linspace(0, len(samples) - 1, new_len)
    resampled = np.interp(indices, np.arange(len(samples)), samples)
    return resampled.astype(np.int16).tobytes()


# Sentinel value to signal a flush through the send queue
_FLUSH = object()
_END = object()


class StudentSTT:
    def __init__(self):
        self._api_key = os.getenv("GRADIUM_API_KEY")
        if not self._api_key:
            raise RuntimeError("GRADIUM_API_KEY is required")
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._ws = None
        self._ws_task: Optional[asyncio.Task] = None
        # Single send queue: bytes for audio frames, _FLUSH for flush, _END for end
        self._send_queue: asyncio.Queue = asyncio.Queue()
        self._connected = asyncio.Event()
        self._stopped = False
        self._pcm_buffer = bytearray()
        self._push_count = 0
        self._send_count = 0
        self._flush_count = 0

    async def start(self):
        log.info("Connecting to Gradium STT...")
        self._ws_task = asyncio.create_task(self._run_gradium())
        await asyncio.wait_for(self._connected.wait(), timeout=10.0)

    async def _run_gradium(self):
        try:
            async with websockets.connect(
                GRADIUM_STT_WS,
                extra_headers={"x-api-key": self._api_key},
                max_size=None,
            ) as ws:
                self._ws = ws
                await ws.send(json.dumps({
                    "type": "setup",
                    "model_name": "default",
                    "input_format": "pcm",
                }))

                ready = json.loads(await ws.recv())
                log.info("Gradium STT ready: request_id=%s frame_size=%s",
                         ready.get("request_id"), ready.get("frame_size"))
                if ready.get("type") != "ready":
                    raise RuntimeError(f"Gradium STT setup failed: {ready}")

                self._connected.set()

                # Single sender, single receiver — no concurrent ws.send()
                sender = asyncio.create_task(self._send_loop(ws))
                receiver = asyncio.create_task(self._recv_loop(ws))

                done, pending = await asyncio.wait(
                    [sender, receiver],
                    return_when=asyncio.FIRST_EXCEPTION,
                )
                for task in pending:
                    task.cancel()
                for task in done:
                    exc = task.exception()
                    if exc and not isinstance(exc, asyncio.CancelledError):
                        log.error("STT subtask failed: %s", exc)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error("Gradium STT connection error: %s", e)
            self._connected.set()
            raise

    async def _send_loop(self, ws):
        """Single sender — handles audio frames, flush, and end-of-stream."""
        log.info("STT send loop started")
        try:
            while not self._stopped:
                item = await self._send_queue.get()

                if item is _FLUSH:
                    self._flush_count += 1
                    flush_id = str(self._flush_count)
                    msg = json.dumps({"type": "flush", "flush_id": flush_id})
                    log.info("STT SEND flush (id=%s)", flush_id)
                    await ws.send(msg)

                elif item is _END:
                    log.info("STT SEND end_of_stream")
                    await ws.send(json.dumps({"type": "end_of_stream"}))
                    break

                elif isinstance(item, bytes):
                    self._send_count += 1
                    b64 = base64.b64encode(item).decode()
                    msg = json.dumps({"type": "audio", "audio": b64})
                    if self._send_count <= 3:
                        log.info("STT SEND frame #%d: %d pcm bytes", self._send_count, len(item))
                    elif self._send_count % 50 == 0:
                        log.debug("STT SEND frame #%d (queue: %d)", self._send_count, self._send_queue.qsize())
                    await ws.send(msg)

        except asyncio.CancelledError:
            log.debug("STT send loop cancelled (sent %d frames, %d flushes)", self._send_count, self._flush_count)

    async def _recv_loop(self, ws):
        """Receives text + VAD from Gradium. Signals flush via send queue."""
        log.info("STT recv loop started")
        transcript_parts = []
        has_speech = False
        silence_count = 0
        SILENCE_THRESHOLD = 0.5
        SILENCE_FRAMES_NEEDED = 3
        pending_flush = False
        msg_count = 0

        try:
            async for raw_msg in ws:
                if self._stopped:
                    break
                msg_count += 1
                data = json.loads(raw_msg)
                msg_type = data.get("type")

                if msg_type == "text":
                    text = data.get("text", "").strip()
                    if text:
                        transcript_parts.append(text)
                        has_speech = True
                        silence_count = 0
                        log.info("STT text: '%s' (parts: %d)", text, len(transcript_parts))

                elif msg_type == "step":
                    vad = data.get("vad", [])
                    if has_speech and len(vad) >= 3:
                        inactivity = vad[2].get("inactivity_prob", 0)
                        if inactivity > SILENCE_THRESHOLD:
                            silence_count += 1
                        else:
                            silence_count = 0
                        if silence_count >= SILENCE_FRAMES_NEEDED and not pending_flush:
                            log.info("STT VAD turn-end (inactivity=%.3f) — requesting flush", inactivity)
                            pending_flush = True
                            # Route flush through the single send queue
                            self._send_queue.put_nowait(_FLUSH)

                elif msg_type == "flushed":
                    full_text = " ".join(transcript_parts).strip()
                    log.info("STT flushed — utterance: '%s'", full_text)
                    if full_text:
                        await self._queue.put(full_text)
                    transcript_parts.clear()
                    has_speech = False
                    silence_count = 0
                    pending_flush = False

                elif msg_type == "end_of_stream":
                    full_text = " ".join(transcript_parts).strip()
                    if full_text:
                        await self._queue.put(full_text)
                    break

                elif msg_type == "error":
                    log.error("GRADIUM STT ERROR: %s", json.dumps(data))
                    break

        except asyncio.CancelledError:
            log.debug("STT recv loop cancelled (%d messages)", msg_count)

    async def push(self, pcm16_16k: bytes):
        if not pcm16_16k:
            return
        self._push_count += 1
        if self._push_count <= 3:
            log.info("STT push #%d: %d bytes (%d samples@16kHz)",
                     self._push_count, len(pcm16_16k), len(pcm16_16k) // 2)

        pcm_24k = _resample_16k_to_24k(pcm16_16k)
        if not pcm_24k:
            return

        self._pcm_buffer.extend(pcm_24k)
        frames_queued = 0
        while len(self._pcm_buffer) >= GRADIUM_FRAME_BYTES:
            frame = bytes(self._pcm_buffer[:GRADIUM_FRAME_BYTES])
            del self._pcm_buffer[:GRADIUM_FRAME_BYTES]
            self._send_queue.put_nowait(frame)
            frames_queued += 1

        if self._push_count <= 3:
            log.info("STT push #%d: resampled=%d bytes, queued=%d frames, buf=%d bytes",
                     self._push_count, len(pcm_24k), frames_queued, len(self._pcm_buffer))

    async def utterances(self) -> AsyncIterator[str]:
        while True:
            u = await self._queue.get()
            yield u

    async def stop(self):
        log.info("STT stopping (pushed=%d, sent=%d, flushes=%d)",
                 self._push_count, self._send_count, self._flush_count)
        self._stopped = True
        self._send_queue.put_nowait(_END)
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except (asyncio.CancelledError, Exception):
                pass
