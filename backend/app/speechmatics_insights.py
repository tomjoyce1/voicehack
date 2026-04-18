"""Post-session Speechmatics batch transcription → medical-domain insights.

Takes the accumulated student PCM16 audio, uploads it to Speechmatics'
batch transcription API with `operating_point=enhanced` and `domain=medical`,
then derives a handful of insights for the results page:

  - medical-domain transcript (plain text)
  - speaking rate in words-per-minute
  - filler word count (um / uh / erm / like / you know / sort of / kind of)
  - medical vocabulary coverage (against scenario.required_questions)
  - top low-confidence words (Speechmatics' own per-word confidence)

Speechmatics failures are swallowed — the rest of the results page still works
without this section.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import struct
from typing import Any, Dict, List, Optional

import httpx

from .scenarios import Scenario

log = logging.getLogger(__name__)

SPEECHMATICS_HOST = "https://asr.api.speechmatics.com/v2"
SAMPLE_RATE = 16000
POLL_INTERVAL_S = 3.0
POLL_TIMEOUT_S = 180.0
FILLER_WORDS = {"um", "uh", "erm", "ah", "hmm", "like", "basically", "literally"}
FILLER_BIGRAMS = {("you", "know"), ("sort", "of"), ("kind", "of"), ("i", "mean")}


def pcm16_to_wav(pcm: bytes, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Wrap raw little-endian PCM16 mono bytes in a minimal WAV container."""
    byte_rate = sample_rate * 2  # 16-bit mono
    block_align = 2
    bits_per_sample = 16
    data_size = len(pcm)
    header = b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVE"
    fmt = (
        b"fmt "
        + struct.pack("<I", 16)
        + struct.pack("<H", 1)
        + struct.pack("<H", 1)
        + struct.pack("<I", sample_rate)
        + struct.pack("<I", byte_rate)
        + struct.pack("<H", block_align)
        + struct.pack("<H", bits_per_sample)
    )
    data = b"data" + struct.pack("<I", data_size) + pcm
    return header + fmt + data


def _keywords_for_question(q: str) -> List[str]:
    """Crude keyword bag per required question — mirrors scoring._keywords_for."""
    ql = q.lower()
    bags: Dict[str, List[str]] = {
        "socrates": ["pain", "where", "radiat", "onset", "charac", "severity", "scale"],
        "past cardiac": ["cardiac", "heart", "mi", "angina", "attack"],
        "smoking": ["smoke", "smoker", "cigarette", "pack"],
        "drug": ["medicat", "tablet", "drug", "taking", "inhaler", "pill"],
        "family": ["family", "father", "mother", "parent", "sibling", "relative"],
        "onset": ["when", "onset", "start", "how long", "first"],
        "inhaler": ["inhaler", "salbutamol"],
        "admission": ["admit", "admission", "hospital"],
        "pefr": ["peak flow", "pefr"],
        "allergen": ["allergy", "allergens", "pets", "cat", "dog"],
        "gi": ["nausea", "vomit", "bowel", "appetite", "stool"],
        "urinary": ["urine", "pee", "dysuria", "urinary"],
        "sexual": ["sexual", "period", "menstr", "pregnan"],
        "surgical": ["operation", "surgery", "surgical"],
        "peak": ["worst", "thunderclap", "peak"],
        "neuro": ["weakness", "numb", "vision", "speech", "seizure"],
        "meningism": ["neck", "photophobia", "light"],
        "vertigo": ["spin", "vertigo", "dizzy"],
        "hearing": ["hearing", "tinnitus", "ear"],
        "sputum": ["sputum", "cough", "phlegm"],
        "fever": ["fever", "temperature", "rigor", "chills"],
        "pleuritic": ["pleuritic", "sharp"],
        "travel": ["travel", "abroad", "flight"],
        "collateral": ["daughter", "son", "family", "carer"],
        "baseline": ["baseline", "usual", "normal"],
        "immobil": ["flight", "plane", "immobil"],
        "contracept": ["pill", "contracept", "hormon", "oestrogen"],
        "vte": ["dvt", "clot", "pe", "embol", "vte"],
    }
    for key, kws in bags.items():
        if key in ql:
            return kws
    return [w for w in re.findall(r"[a-z]+", ql) if len(w) > 3]


def _build_additional_vocab(scenario: Scenario) -> List[Dict[str, Any]]:
    """Seed Speechmatics' custom lexicon with scenario-specific medical terms.

    This improves recognition of condition-specific vocabulary (e.g. "radiation",
    "diaphoresis", "STEMI") so the medical transcript is noticeably better than
    the generic Gradium live stream.
    """
    terms: set[str] = set()
    for source in (scenario.red_flags, scenario.symptoms, scenario.history):
        for entry in source:
            for w in re.findall(r"[A-Za-z]{4,}", entry):
                terms.add(w)
    terms.add(scenario.hidden_diagnosis.split()[0])
    # Speechmatics additional_vocab format: [{"content": "...", "sounds_like": [...]}]
    return [{"content": t} for t in sorted(terms) if t.isalpha()]


async def _submit_job(
    client: httpx.AsyncClient, api_key: str, wav: bytes, vocab: List[Dict[str, Any]]
) -> str:
    config = {
        "type": "transcription",
        "transcription_config": {
            "language": "en",
            "operating_point": "enhanced",
            "domain": "medical",
            "enable_entities": True,
            "additional_vocab": vocab[:100],  # API caps list size
        },
    }
    files = {
        "data_file": ("session.wav", wav, "audio/wav"),
        "config": (None, json.dumps(config), "application/json"),
    }
    r = await client.post(
        f"{SPEECHMATICS_HOST}/jobs/",
        headers={"Authorization": f"Bearer {api_key}"},
        files=files,
        timeout=60.0,
    )
    r.raise_for_status()
    return r.json()["id"]


async def _poll_job(client: httpx.AsyncClient, api_key: str, job_id: str) -> None:
    deadline = asyncio.get_event_loop().time() + POLL_TIMEOUT_S
    while asyncio.get_event_loop().time() < deadline:
        r = await client.get(
            f"{SPEECHMATICS_HOST}/jobs/{job_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )
        r.raise_for_status()
        status = r.json().get("job", {}).get("status", "")
        if status == "done":
            return
        if status == "rejected":
            raise RuntimeError(f"Speechmatics job rejected: {r.json()}")
        await asyncio.sleep(POLL_INTERVAL_S)
    raise TimeoutError(f"Speechmatics job {job_id} did not finish in {POLL_TIMEOUT_S}s")


async def _fetch_transcript(
    client: httpx.AsyncClient, api_key: str, job_id: str
) -> Dict[str, Any]:
    r = await client.get(
        f"{SPEECHMATICS_HOST}/jobs/{job_id}/transcript",
        headers={"Authorization": f"Bearer {api_key}"},
        params={"format": "json-v2"},
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()


def _extract_words(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten json-v2 payload into [{word, start, end, confidence}, ...]."""
    out: List[Dict[str, Any]] = []
    for result in payload.get("results", []):
        if result.get("type") != "word":
            continue
        alt = (result.get("alternatives") or [{}])[0]
        content = (alt.get("content") or "").strip()
        if not content:
            continue
        out.append(
            {
                "word": content,
                "start": float(result.get("start_time", 0.0)),
                "end": float(result.get("end_time", 0.0)),
                "confidence": float(alt.get("confidence", 1.0)),
            }
        )
    return out


def _compute_insights(words: List[Dict[str, Any]], scenario: Scenario) -> Dict[str, Any]:
    if not words:
        return {
            "transcript": "",
            "wpm": 0,
            "filler_count": 0,
            "filler_examples": [],
            "low_confidence": [],
            "medical_vocab": {
                "recall": 0.0,
                "hits": [],
                "missing": list(scenario.required_questions),
                "source": "speechmatics",
            },
        }

    transcript = " ".join(w["word"] for w in words)
    lowered = [re.sub(r"[^a-z']", "", w["word"].lower()) for w in words]
    duration_s = max(0.1, words[-1]["end"] - words[0]["start"])
    wpm = int(round(len(words) * 60.0 / duration_s))

    # Filler counting
    filler_count = 0
    filler_examples: List[str] = []
    for i, tok in enumerate(lowered):
        if tok in FILLER_WORDS:
            filler_count += 1
            if len(filler_examples) < 5:
                filler_examples.append(tok)
        if i + 1 < len(lowered) and (tok, lowered[i + 1]) in FILLER_BIGRAMS:
            filler_count += 1
            if len(filler_examples) < 5:
                filler_examples.append(f"{tok} {lowered[i + 1]}")

    # Low-confidence words (skip tiny filler tokens)
    ranked = sorted(
        (w for w in words if len(w["word"]) >= 3 and w["confidence"] < 0.85),
        key=lambda w: w["confidence"],
    )
    low_conf = [
        {"word": w["word"], "confidence": round(w["confidence"], 2)}
        for w in ranked[:3]
    ]

    # Medical vocab coverage — reuse scenario.required_questions
    full_text = transcript.lower()
    hits: List[str] = []
    missing: List[str] = []
    for q in scenario.required_questions:
        kws = _keywords_for_question(q)
        if any(k in full_text for k in kws):
            hits.append(q)
        else:
            missing.append(q)
    total = max(1, len(scenario.required_questions))
    recall = len(hits) / total

    return {
        "transcript": transcript,
        "wpm": wpm,
        "filler_count": filler_count,
        "filler_examples": filler_examples,
        "low_confidence": low_conf,
        "medical_vocab": {
            "recall": round(recall, 2),
            "hits": hits,
            "missing": missing,
            "source": "speechmatics",
        },
    }


async def run_speechmatics_insights(
    pcm16_mono_16k: bytes,
    scenario: Scenario,
) -> Dict[str, Any]:
    """Entry point: upload audio → poll → compute insights.

    Returns ``{"status": "ok", ...insights}`` on success, or
    ``{"status": "error", "reason": "..."}`` on any failure.
    """
    api_key = (os.getenv("SPEECHMATICS_API_KEY") or "").strip()
    if not api_key:
        return {"status": "skipped", "reason": "no_api_key"}
    if not pcm16_mono_16k or len(pcm16_mono_16k) < SAMPLE_RATE * 2:  # <1s
        return {"status": "skipped", "reason": "not_enough_audio"}

    wav = pcm16_to_wav(pcm16_mono_16k)
    vocab = _build_additional_vocab(scenario)
    log.info(
        "Speechmatics: submitting %.1fs of audio, %d custom terms",
        len(pcm16_mono_16k) / (SAMPLE_RATE * 2),
        len(vocab),
    )

    try:
        async with httpx.AsyncClient() as client:
            job_id = await _submit_job(client, api_key, wav, vocab)
            log.info("Speechmatics: job %s submitted, polling…", job_id)
            await _poll_job(client, api_key, job_id)
            payload = await _fetch_transcript(client, api_key, job_id)
    except httpx.HTTPStatusError as e:
        body = e.response.text[:300] if e.response is not None else ""
        log.error("Speechmatics HTTP error: %s — %s", e, body)
        return {"status": "error", "reason": f"http_{e.response.status_code if e.response else '?'}"}
    except Exception as e:
        log.exception("Speechmatics insights failed: %s", e)
        return {"status": "error", "reason": type(e).__name__}

    words = _extract_words(payload)
    insights = _compute_insights(words, scenario)
    log.info(
        "Speechmatics: done — %d words, %d wpm, %d fillers, recall=%.0f%%",
        len(words),
        insights["wpm"],
        insights["filler_count"],
        insights["medical_vocab"]["recall"] * 100,
    )
    return {"status": "ok", **insights}
