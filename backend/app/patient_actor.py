"""Patient actor LLM — given a scenario profile, generates in-character replies via Groq."""
from __future__ import annotations

import logging
import os
from typing import List

import httpx

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

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


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
    """Wraps Groq LLM for the patient."""

    def __init__(self, scenario: Scenario, blind: bool = False):
        self.scenario = scenario
        self.blind = blind
        self.history: List[dict] = []
        self.system_prompt = build_system_prompt(scenario, blind)
        self._groq_key = os.getenv("GROQ_API_KEY")
        if not self._groq_key:
            raise RuntimeError("GROQ_API_KEY is required")

    def opening_line(self) -> str:
        return self.scenario.presenting_line if not self.blind else "Hi doctor."

    async def reply(self, student_utterance: str) -> str:
        self.history.append({"role": "user", "content": student_utterance})
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                GROQ_URL,
                headers={
                    "Authorization": f"Bearer {self._groq_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                    "temperature": 0.7,
                    "max_tokens": 160,
                    "messages": [{"role": "system", "content": self.system_prompt}]
                    + self.history,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = (data["choices"][0]["message"]["content"] or "").strip()
        self.history.append({"role": "assistant", "content": text})
        return text
