"""Patient actor LLM — given a scenario profile, generates in-character replies."""
from __future__ import annotations

import asyncio
import logging
import os
import random
from typing import List, Optional

from .scenarios import Scenario

log = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """You are {name}, a {age}-year-old {sex} patient in a UK hospital. A medical student is taking your history as part of an OSCE exam.

PRESENTING COMPLAINT (volunteer only this at the start, if asked a very open question):
{chief_complaint}

YOUR OPENING LINE WHEN THEY SAY HELLO:
"{presenting_line}"

HIDDEN CLINICAL FACTS — reveal ONLY if the student asks an appropriate question. Do not volunteer unprompted:
- Symptoms: {symptoms}
- Past medical / social / family history: {history}
- Red flag findings that are present: {red_flags}

CORRECT DIAGNOSIS (never state this yourself, no matter what): {hidden_diagnosis}

STYLE RULES:
1. Reply in natural, lay patient language — NEVER use medical jargon the patient wouldn't know.
2. 1–3 sentences per reply. If asked a focused yes/no question, answer briefly.
3. Stay emotionally in character — mildly worried, in pain, or confused as the scenario dictates.
4. If asked something outside the hidden facts, make a plausible neutral answer ("No, nothing like that.").
5. If the student calls a diagnosis, react naturally as a patient would — do NOT confirm or deny the diagnosis.
6. Do not break character, no matter what the student says. If asked if you are an AI, deflect in character ("I'm just trying to get some help here, doctor.").
"""

BLIND_SYSTEM_SUFFIX = "\n\nEXTRA: Do NOT reveal your presenting complaint until the student asks an open question about why you're here today."


def build_system_prompt(scenario: Scenario, blind: bool = False) -> str:
    prompt = SYSTEM_PROMPT_TEMPLATE.format(
        name=scenario.name,
        age=scenario.age,
        sex="male" if scenario.sex == "M" else "female",
        chief_complaint=scenario.chief_complaint,
        presenting_line=scenario.presenting_line,
        symptoms="; ".join(scenario.symptoms),
        history="; ".join(scenario.history),
        red_flags="; ".join(scenario.red_flags),
        hidden_diagnosis=scenario.hidden_diagnosis,
    )
    if blind:
        prompt += BLIND_SYSTEM_SUFFIX
    return prompt


class PatientActor:
    """Wraps OpenAI chat for the patient. Falls back to scripted replies in demo mode."""

    def __init__(self, scenario: Scenario, blind: bool = False):
        self.scenario = scenario
        self.blind = blind
        self.history: List[dict] = []
        self.system_prompt = build_system_prompt(scenario, blind)
        self.demo_mode = os.getenv("DEMO_MODE", "0") == "1"
        self._client = None
        if not self.demo_mode and os.getenv("OPENAI_API_KEY"):
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            except Exception as e:
                log.warning("OpenAI client unavailable, falling back to demo: %s", e)
                self.demo_mode = True
        else:
            self.demo_mode = True

    def opening_line(self) -> str:
        return self.scenario.presenting_line if not self.blind else "Hi doctor."

    async def reply(self, student_utterance: str) -> str:
        self.history.append({"role": "user", "content": student_utterance})
        if self.demo_mode or not self._client:
            text = self._demo_reply(student_utterance)
        else:
            try:
                resp = await self._client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    temperature=0.7,
                    max_tokens=160,
                    messages=[{"role": "system", "content": self.system_prompt}]
                    + self.history,
                )
                text = (resp.choices[0].message.content or "").strip()
            except Exception as e:
                log.warning("OpenAI reply failed, using demo fallback: %s", e)
                text = self._demo_reply(student_utterance)
        self.history.append({"role": "assistant", "content": text})
        return text

    def _demo_reply(self, q: str) -> str:
        ql = q.lower()
        s = self.scenario
        if any(k in ql for k in ("hi", "hello", "good morning", "how are you", "introduce")):
            return s.presenting_line
        if any(k in ql for k in ("where", "site", "location", "whereabouts")):
            return self._first_symptom_match(["pain", "site", "where", "left", "right", "central"])
        if any(k in ql for k in ("radiat", "move", "spread", "anywhere else")):
            return self._first_symptom_match(["radiat", "jaw", "arm", "move", "migrat"])
        if any(k in ql for k in ("when", "start", "onset", "begin", "how long")):
            return self._first_symptom_match(["start", "hour", "day", "ago", "onset", "thunderclap"])
        if any(k in ql for k in ("severity", "scale", "out of 10", "how bad", "describe")):
            return self._first_symptom_match(["9/10", "severity", "crush", "worst"])
        if any(k in ql for k in ("medication", "drug", "tablet", "inhaler")):
            return self._first_history_match(["ramipril", "metformin", "inhaler", "pill", "tiotropium"])
        if any(k in ql for k in ("smoke", "alcohol", "drink")):
            return self._first_history_match(["smoker", "pack-years", "ex-smoker"])
        if any(k in ql for k in ("family history", "father", "mother", "parent", "relative")):
            return self._first_history_match(["father", "mother", "aneurysm", "mi"])
        if any(k in ql for k in ("travel", "flight", "plane", "immobil")):
            return self._first_history_match(["flight", "plane", "long-haul"])
        if any(k in ql for k in ("diagnos", "think", "suspect", "heart attack", "asthma", "appendicitis")):
            return "That sounds scary — is that what's happening to me, doctor?"
        # generic fallback — pick a random uncovered hidden symptom
        pool = s.symptoms + s.history
        return f"Well... {random.choice(pool).lower()}." if pool else "I'm not sure, doctor."

    def _first_symptom_match(self, keys: List[str]) -> str:
        for sym in self.scenario.symptoms:
            if any(k in sym.lower() for k in keys):
                return f"Yes — {sym.lower()}."
        return self.scenario.symptoms[0].capitalize() if self.scenario.symptoms else "I don't know."

    def _first_history_match(self, keys: List[str]) -> str:
        for h in self.scenario.history:
            if any(k in h.lower() for k in keys):
                return f"{h}."
        return "No, nothing like that."
