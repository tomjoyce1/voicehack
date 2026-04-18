"""Thymia Sentinel sidecar.

Forwards PCM audio to thymia-sentinel and emits biomarker events.
Falls back to energy-based estimation if Thymia SDK unavailable.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)


@dataclass
class Biomarkers:
    confidence: float = 60.0
    anxiety: float = 35.0
    pacing: float = 60.0
    empathy: float = 60.0


class SentinelSidecar:
    def __init__(self, user_label: str):
        self.user_label = user_label
        self.current = Biomarkers()
        self._client = None
        self._last_rms = 0.0
        self._voiced_windows = 0
        self._silent_windows = 0
        self._use_thymia = bool(os.getenv("THYMIA_API_KEY"))

    async def start(self):
        if not self._use_thymia:
            log.info("No THYMIA_API_KEY — using energy-based biomarker estimation")
            return
        try:
            from thymia_sentinel import SentinelClient  # type: ignore

            client = SentinelClient(
                user_label=self.user_label,
                policies=[os.getenv("THYMIA_POLICY", "wellbeing-awareness")],
            )

            @client.on_policy_result  # type: ignore
            async def _handle_result(result):
                try:
                    r = result.get("result", {})
                    bio = r.get("biomarkers", {}) or {}
                    distress = float(bio.get("distress", 0.0))
                    stress = float(bio.get("stress", 0.0))
                    fatigue = float(bio.get("fatigue", 0.0))
                    self.current.anxiety = _clamp(100.0 * (distress * 0.6 + stress * 0.4))
                    self.current.confidence = _clamp(100.0 * (1.0 - (stress * 0.5 + distress * 0.3)))
                    self.current.empathy = _clamp(100.0 - 70.0 * fatigue)
                except Exception as e:
                    log.warning("Biomarker mapping error: %s", e)

            await client.connect()
            self._client = client
        except Exception as e:
            log.warning("Thymia Sentinel unavailable: %s — using energy-based estimation", e)
            self._use_thymia = False

    async def push_audio(self, pcm16_16k: bytes):
        try:
            arr = np.frombuffer(pcm16_16k, dtype=np.int16).astype(np.float32) / 32768.0
            rms = float((arr * arr).mean() ** 0.5)
            self._last_rms = rms
            if rms > 0.012:
                self._voiced_windows += 1
                self._silent_windows = 0
            else:
                self._silent_windows += 1
        except Exception:
            pass
        if self._client is not None:
            try:
                await self._client.send_user_audio(pcm16_16k)
            except Exception as e:
                log.warning("Sentinel push failed: %s", e)

    async def send_transcript(self, text: str):
        if self._client is not None:
            try:
                await self._client.send_user_transcript(text)
            except Exception:
                pass

    def tick(self) -> Biomarkers:
        """Return current biomarkers. Uses energy-based estimation when Thymia unavailable."""
        if self._client is None:
            voice_ratio = self._voiced_windows / max(1, self._voiced_windows + self._silent_windows)
            import random
            self.current.confidence = _ease(self.current.confidence, 45 + 40 * voice_ratio + random.uniform(-4, 4))
            self.current.anxiety = _ease(self.current.anxiety, 55 - 30 * voice_ratio + (20 * min(1.0, self._last_rms * 10)) + random.uniform(-3, 3))
            self.current.pacing = _ease(self.current.pacing, 55 + 25 * voice_ratio + random.uniform(-5, 5))
            self.current.empathy = _ease(self.current.empathy, 55 + 15 * (1.0 - abs(voice_ratio - 0.55)) + random.uniform(-3, 3))
        return Biomarkers(
            confidence=_clamp(self.current.confidence),
            anxiety=_clamp(self.current.anxiety),
            pacing=_clamp(self.current.pacing),
            empathy=_clamp(self.current.empathy),
        )

    async def stop(self):
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                pass


def _ease(current: float, target: float, k: float = 0.25) -> float:
    return current + (target - current) * k


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))
