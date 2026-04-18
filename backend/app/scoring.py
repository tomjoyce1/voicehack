"""Clinical + delivery scoring.

- Clinical: LLM evaluator on the transcript, plus checklist on required questions.
- Delivery: aggregated from Thymia biomarker timeline.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Dict, List

from .scenarios import Scenario

log = logging.getLogger(__name__)


def _keyword_hits(transcript: List[dict], required: List[str]) -> List[dict]:
    student_text = " ".join(
        t["text"].lower() for t in transcript if t["role"] == "student"
    )
    checklist = []
    for q in required:
        hit = any(k in student_text for k in _keywords_for(q))
        checklist.append({"text": q, "hit": hit})
    return checklist


def _keywords_for(q: str) -> List[str]:
    ql = q.lower()
    # crude but effective keyword bag per required question
    bags: Dict[str, List[str]] = {
        "socrates": ["where", "site", "radiat", "onset", "start", "charac", "associated", "time", "exacerbat", "severity", "scale"],
        "past cardiac": ["cardiac", "heart", "mi", "angina", "attack"],
        "smoking": ["smoke", "smoker", "cigarette", "pack"],
        "drug": ["medicat", "tablet", "drug", "taking", "inhaler", "pill"],
        "family": ["family", "father", "mother", "parent", "sibling", "relative"],
        "onset": ["when", "onset", "start", "how long", "first"],
        "inhaler": ["inhaler", "blue inhaler", "salbutamol"],
        "admission": ["admit", "admission", "hospital before"],
        "pefr": ["peak flow", "pefr"],
        "allergen": ["allergy", "allergens", "pets", "cat", "dog"],
        "gi": ["nause", "vomit", "bowel", "appetite", "stool"],
        "urinary": ["urine", "pee", "dysuria", "urinary", "water"],
        "sexual": ["sexual", "period", "menstr", "pregnan"],
        "surgical": ["operation", "surgery", "surgical"],
        "peak intensity": ["worst", "thunderclap", "peak"],
        "neuro": ["weakness", "numb", "vision", "speech", "seizure"],
        "meningism": ["neck stiff", "photophobia", "light", "meningism"],
        "vertigo": ["spin", "vertigo", "dizzy"],
        "hearing": ["hearing", "tinnitus", "ear"],
        "sputum": ["sputum", "cough", "green", "phlegm", "blood"],
        "fever": ["fever", "temperature", "rigor", "chills"],
        "pleuritic": ["pleuritic", "sharp", "breath"],
        "travel": ["travel", "abroad", "flight"],
        "vaccin": ["vaccin", "jab", "flu"],
        "collateral": ["daughter", "son", "family", "carer", "collateral"],
        "baseline": ["baseline", "usual", "normal", "before"],
        "immobil": ["flight", "plane", "immobil", "long haul"],
        "contracept": ["pill", "contracept", "hormon", "oestrogen"],
        "vte": ["dvt", "clot", "pe", "embol", "vte"],
        "pe": ["chest pain", "short of breath", "cough up blood", "haemoptys"],
    }
    hits: List[str] = []
    for key, kws in bags.items():
        if key in ql:
            hits.extend(kws)
    if not hits:
        # fallback — key-ish words from the question itself
        hits = [w for w in re.findall(r"[a-z]+", ql) if len(w) > 3]
    return hits


async def score_session(
    scenario: Scenario,
    transcript: List[dict],
    diagnosis: str,
    bio_timeline: Dict[str, List[float]],
) -> dict:
    # --- Clinical checklist ---
    checklist = _keyword_hits(transcript, scenario.required_questions)
    hits = sum(1 for c in checklist if c["hit"])
    total_qs = max(1, len(checklist))

    # --- Diagnosis match ---
    dx_match = _diagnosis_matches(diagnosis, scenario.hidden_diagnosis)

    # --- Clinical score /60 ---
    question_score = 30 * (hits / total_qs)
    diagnosis_score = 30 if dx_match else (10 if diagnosis.strip() else 0)
    clinical = round(question_score + diagnosis_score)

    # --- Delivery score /40 from biomarker timeline ---
    def _mean(xs: List[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    conf = _mean(bio_timeline.get("confidence", [60]))
    anx = _mean(bio_timeline.get("anxiety", [40]))
    pace = _mean(bio_timeline.get("pacing", [60]))
    emp = _mean(bio_timeline.get("empathy", [60]))
    # confident + empathic + well paced + low anxiety → high delivery
    delivery = round(
        0.35 * conf + 0.25 * (100 - anx) + 0.20 * pace + 0.20 * emp
    ) * 40 // 100
    delivery = int(max(0, min(40, delivery)))

    # --- LLM-written feedback (best-effort) ---
    feedback = await _llm_feedback(scenario, transcript, diagnosis, checklist, bio_timeline)

    # Concordance heuristics
    concordance = _concordance(transcript, bio_timeline)

    # Annotate transcript with hits
    annotated = _annotate_transcript(transcript, checklist)

    return {
        "sessionId": scenario.id,
        "scenarioId": scenario.id,
        "diagnosis": {
            "given": diagnosis,
            "correct": scenario.hidden_diagnosis,
            "match": dx_match,
        },
        "clinical": {"score": clinical, "max": 60, "questions": checklist},
        "delivery": {
            "score": delivery,
            "max": 40,
            "timeline": bio_timeline,
            "concordance": concordance,
        },
        "transcript": annotated,
        "written_feedback": feedback,
    }


def _diagnosis_matches(given: str, correct: str) -> bool:
    g = given.lower()
    c = correct.lower()
    if not g.strip():
        return False
    # Accept substring, abbreviation, or overlap on 2+ content words
    if g in c or c in g:
        return True
    abbr_map = {
        "stemi": ["st-elevation", "myocardial infarction", "heart attack", "mi"],
        "mi": ["myocardial infarction", "heart attack"],
        "sah": ["subarachnoid"],
        "bppv": ["benign", "positional"],
        "dvt": ["deep vein", "thrombos"],
        "uti": ["urinary", "delirium"],
    }
    for abbr, forms in abbr_map.items():
        if abbr in g and any(f in c for f in forms):
            return True
        if abbr in c and any(f in g for f in forms):
            return True
    g_words = set(re.findall(r"[a-z]{4,}", g))
    c_words = set(re.findall(r"[a-z]{4,}", c))
    overlap = g_words & c_words
    return len(overlap) >= 2


def _concordance(transcript: List[dict], bio: Dict[str, List[float]]) -> List[str]:
    notes: List[str] = []
    anx = bio.get("anxiety", [])
    if anx and max(anx) > 55:
        notes.append(
            f"Your voice anxiety peaked at {int(max(anx))} during the session — most visible when you were asking closed, rapid-fire questions."
        )
    conf = bio.get("confidence", [])
    if conf and min(conf) < 45:
        notes.append(
            f"There was a dip in confidence to {int(min(conf))} mid-history; patients pick this up even if your words sound fine."
        )
    if any("don't worry" in t["text"].lower() or "try not to worry" in t["text"].lower() for t in transcript if t["role"] == "student"):
        notes.append(
            "You told the patient not to worry — empathic intent, but make sure your tone matches the reassurance."
        )
    return notes


def _annotate_transcript(transcript: List[dict], checklist: List[dict]) -> List[dict]:
    # Add a light annotation on the first student utterance that hit each required question
    remaining = {c["text"]: True for c in checklist if c["hit"]}
    out: List[dict] = []
    for line in transcript:
        entry = {"role": line["role"], "text": line["text"]}
        if line["role"] == "student":
            text = line["text"].lower()
            for q in list(remaining.keys()):
                if any(k in text for k in _keywords_for(q)):
                    entry["annotation"] = f"Covered: {q}"
                    del remaining[q]
                    break
        out.append(entry)
    return out


async def _llm_feedback(
    scenario: Scenario,
    transcript: List[dict],
    diagnosis: str,
    checklist: List[dict],
    bio: Dict[str, List[float]],
) -> str:
    import httpx

    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        raise RuntimeError("GROQ_API_KEY is required")

    transcript_text = "\n".join(f"{t['role'].upper()}: {t['text']}" for t in transcript)
    prompt = f"""You are an OSCE examiner writing a short (4-6 sentence) feedback note for a medical student.
SCENARIO: {scenario.name}, {scenario.age}{scenario.sex} — {scenario.chief_complaint}.
CORRECT DIAGNOSIS: {scenario.hidden_diagnosis}.
STUDENT'S DIAGNOSIS: {diagnosis}.

TRANSCRIPT:
{transcript_text}

REQUIRED QUESTIONS HIT: {[c['text'] for c in checklist if c['hit']]}
REQUIRED QUESTIONS MISSED: {[c['text'] for c in checklist if not c['hit']]}

DELIVERY BIOMARKERS (means): confidence {sum(bio.get('confidence',[60]))/max(1,len(bio.get('confidence',[60]))):.0f}, anxiety {sum(bio.get('anxiety',[40]))/max(1,len(bio.get('anxiety',[40]))):.0f}, pacing {sum(bio.get('pacing',[60]))/max(1,len(bio.get('pacing',[60]))):.0f}, empathy {sum(bio.get('empathy',[60]))/max(1,len(bio.get('empathy',[60]))):.0f}.

Give warm but directive feedback. Reference specific questions they covered or missed, and weave in the biomarker delivery insight. No bullet points — flowing prose."""

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
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return (data["choices"][0]["message"]["content"] or "").strip()
