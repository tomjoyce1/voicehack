"""Thymia Sentinel sidecar.

- Live mode: forwards PCM audio to thymia-sentinel and emits biomarker events.
- Demo mode: returns a lightly-randomised trajectory driven by student audio energy
  so the UI updates realistically during the demo.
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
from dataclasses import dataclass
from typing import Optional

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
        self.demo = os.getenv("DEMO_MODE", "0") == "1" or not os.getenv("THYMIA_API_KEY")
        self.current = Biomarkers()
        self._client = None
        self._lock = asyncio.Lock()
        self._last_rms = 0.0
        self._voiced_windows = 0
        self._silent_windows = 0

    async def start(self):
        if self.demo:
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
                    # Map a few biomarkers onto our scalar delivery dimensions
                    distress = float(bio.get("distress", 0.0))
                    stress = float(bio.get("stress", 0.0))
                    fatigue = float(bio.get("fatigue", 0.0))
                    self.current.anxiety = max(
                        0.0, min(100.0, 100.0 * (distress * 0.6 + stress * 0.4))
                    )
                    self.current.confidence = max(
                        0.0, min(100.0, 100.0 * (1.0 - (stress * 0.5 + distress * 0.3)))
                    )
                    self.current.empathy = max(
                        0.0, min(100.0, 100.0 - 70.0 * fatigue)
                    )
                except Exception as e:
                    log.warning("Biomarker mapping error: %s", e)

            await client.connect()
            self._client = client
        except Exception as e:
            log.warning("Thymia Sentinel unavailable, falling back to demo: %s", e)
            self.demo = True

    async def push_audio(self, pcm16_16k: bytes):
        # Always update our energy-based demo signal (used when demo=True or as supplement)
        try:
            import numpy as np

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
        if not self.demo and self._client is not None:
            try:
                await self._client.send_user_audio(pcm16_16k)
            except Exception as e:
                log.warning("Sentinel push failed: %s", e)

    async def send_transcript(self, text: str):
        if not self.demo and self._client is not None:
            try:
                await self._client.send_user_transcript(text)
            except Exception:
                pass

    def tick(self) -> Biomarkers:
        """Call periodically. In demo mode returns a drift-smoothed, energy-modulated trajectory."""
        if self.demo:
            # Confidence rises as the student speaks more; anxiety rises with high RMS bursts
            voice_ratio = self._voiced_windows / max(1, self._voiced_windows + self._silent_windows)
            target_conf = 45 + 40 * voice_ratio + random.uniform(-4, 4)
            target_anx = 55 - 30 * voice_ratio + (20 * min(1.0, self._last_rms * 10)) + random.uniform(-3, 3)
            target_pace = 55 + 25 * voice_ratio + random.uniform(-5, 5)
            target_emp = 55 + 15 * (1.0 - abs(voice_ratio - 0.55)) + random.uniform(-3, 3)
            self.current.confidence = _ease(self.current.confidence, target_conf)
            self.current.anxiety = _ease(self.current.anxiety, target_anx)
            self.current.pacing = _ease(self.current.pacing, target_pace)
            self.current.empathy = _ease(self.current.empathy, target_emp)
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
