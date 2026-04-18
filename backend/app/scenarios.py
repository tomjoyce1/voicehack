"""Pre-built OSCE patient scenarios. Mirrors frontend/src/lib/scenarios.ts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Scenario:
    id: str
    name: str
    age: int
    sex: str
    chief_complaint: str
    presenting_line: str
    hidden_diagnosis: str
    difficulty: str
    system: str
    symptoms: List[str] = field(default_factory=list)
    history: List[str] = field(default_factory=list)
    red_flags: List[str] = field(default_factory=list)
    required_questions: List[str] = field(default_factory=list)


SCENARIOS: Dict[str, Scenario] = {
    s.id: s
    for s in [
        Scenario(
            id="chest-pain-stemi",
            name="Michael Davies",
            age=58,
            sex="M",
            chief_complaint="Crushing central chest pain",
            presenting_line="Doctor, I've got this awful crushing pain in my chest, it started about an hour ago.",
            hidden_diagnosis="ST-elevation myocardial infarction (STEMI)",
            difficulty="Year 4",
            system="Cardiovascular",
            symptoms=[
                "Central crushing chest pain radiating to left arm and jaw",
                "Started 1 hour ago at rest",
                "Associated sweating and nausea",
                "Pain severity 9/10",
            ],
            history=[
                "Hypertension on ramipril",
                "Type 2 diabetes on metformin",
                "Father died of MI aged 62",
                "Smoker, 30 pack-years",
            ],
            red_flags=["Radiation to jaw", "Diaphoresis", "Family history"],
            required_questions=[
                "SOCRATES for pain",
                "Past cardiac history",
                "Smoking history",
                "Drug history",
                "Family history of cardiac disease",
            ],
        ),
        Scenario(
            id="sob-asthma",
            name="Priya Shah",
            age=22,
            sex="F",
            chief_complaint="Shortness of breath and wheeze",
            presenting_line="I can't catch my breath and my chest feels really tight, it's getting worse.",
            hidden_diagnosis="Acute asthma exacerbation (moderate)",
            difficulty="Year 3",
            system="Respiratory",
            symptoms=[
                "Progressive SOB over 6 hours",
                "Audible wheeze",
                "Chest tightness",
                "Dry cough, worse at night",
            ],
            history=[
                "Known asthmatic since age 8",
                "Uses blue inhaler 4x per day lately",
                "Recent viral URTI",
                "Cat in the house",
            ],
            red_flags=["Using accessory muscles", "Cannot complete sentences"],
            required_questions=[
                "Onset and triggers",
                "Inhaler use",
                "Previous admissions",
                "PEFR baseline",
                "Smoking and allergens",
            ],
        ),
        Scenario(
            id="abdo-appendicitis",
            name="Tom Harrow",
            age=19,
            sex="M",
            chief_complaint="Abdominal pain moving to right lower quadrant",
            presenting_line="I've had this belly ache since yesterday, but now it's really sore on the bottom right.",
            hidden_diagnosis="Acute appendicitis",
            difficulty="Year 3",
            system="Gastrointestinal",
            symptoms=[
                "Central abdominal pain that migrated to RIF",
                "Anorexia",
                "Nausea with one episode of vomiting",
                "Low-grade fever 37.9",
            ],
            history=["No previous surgery", "No allergies", "Last ate last night"],
            red_flags=["Migrating pain", "Rebound tenderness", "Fever"],
            required_questions=[
                "SOCRATES",
                "Associated GI symptoms",
                "Urinary symptoms",
                "Sexual/menstrual history if relevant",
                "Surgical history",
            ],
        ),
        Scenario(
            id="headache-sah",
            name="Eleanor Price",
            age=44,
            sex="F",
            chief_complaint="Sudden severe headache",
            presenting_line="Doctor, I had the worst headache of my life come on out of nowhere — it felt like I was hit on the back of the head.",
            hidden_diagnosis="Subarachnoid haemorrhage",
            difficulty="Year 5",
            system="Neurology",
            symptoms=[
                "Thunderclap onset headache at peak in seconds",
                "Neck stiffness",
                "Photophobia",
                "One episode of vomiting",
            ],
            history=["Smoker", "Mother had a brain aneurysm", "On the combined pill"],
            red_flags=["Thunderclap onset", "Neck stiffness", "Family history aneurysm"],
            required_questions=[
                "Onset speed",
                "Peak intensity",
                "Neurological symptoms",
                "Meningism",
                "Family history",
            ],
        ),
        Scenario(
            id="dizziness-bppv",
            name="Margaret Ellis",
            age=67,
            sex="F",
            chief_complaint="Episodes of dizziness when turning over in bed",
            presenting_line="Every time I roll over in bed the room spins for about 20 seconds — it's terrifying.",
            hidden_diagnosis="Benign paroxysmal positional vertigo (BPPV)",
            difficulty="Year 4",
            system="ENT / Neurology",
            symptoms=[
                "True vertigo (room spinning)",
                "Triggered by head position change",
                "Lasts <30 seconds",
                "No hearing loss or tinnitus",
            ],
            history=["Hypertension", "Recent viral illness 2 weeks ago"],
            red_flags=["No focal neurology", "No persistent symptoms"],
            required_questions=[
                "Vertigo vs lightheadedness",
                "Duration per episode",
                "Triggers",
                "Hearing/tinnitus",
                "Neurological symptoms",
            ],
        ),
        Scenario(
            id="cough-pneumonia",
            name="David Okafor",
            age=72,
            sex="M",
            chief_complaint="Productive cough and fever",
            presenting_line="I've been coughing up green stuff for three days and I just feel awful, shaking with fever.",
            hidden_diagnosis="Community-acquired pneumonia",
            difficulty="Year 3",
            system="Respiratory",
            symptoms=[
                "Productive cough, green sputum",
                "Fever with rigors",
                "Pleuritic right-sided chest pain",
                "Breathless on exertion",
            ],
            history=["COPD on tiotropium", "Ex-smoker 20 years", "Flu jab this year"],
            red_flags=["Confusion", "RR > 30", "SBP < 90"],
            required_questions=[
                "Sputum colour",
                "Fever and rigors",
                "Pleuritic pain",
                "Travel history",
                "Vaccination status",
            ],
        ),
        Scenario(
            id="confusion-uti",
            name="Doris Hamilton",
            age=84,
            sex="F",
            chief_complaint="Acute confusion (brought in by daughter)",
            presenting_line="Where am I, dear? My daughter brought me but I don't really know why...",
            hidden_diagnosis="Delirium secondary to urinary tract infection",
            difficulty="Year 5",
            system="Geriatrics",
            symptoms=[
                "Sudden confusion over 24 hours",
                "Fluctuating attention",
                "New urinary frequency and dysuria",
                "Low-grade fever",
            ],
            history=[
                "Well at baseline, lives alone",
                "No known dementia",
                "Mild CKD",
                "On bendroflumethiazide",
            ],
            red_flags=["New confusion in elderly patient", "Signs of sepsis"],
            required_questions=[
                "Collateral history from daughter",
                "Baseline cognition",
                "Urinary symptoms",
                "Drug history",
                "Signs of infection elsewhere",
            ],
        ),
        Scenario(
            id="leg-swelling-dvt",
            name="Sarah Colbert",
            age=36,
            sex="F",
            chief_complaint="Swollen painful calf",
            presenting_line="My left calf has been swollen and really tender since I got off the plane three days ago.",
            hidden_diagnosis="Deep vein thrombosis (left calf)",
            difficulty="Year 4",
            system="Cardiovascular",
            symptoms=[
                "Unilateral left calf swelling",
                "Pain on walking",
                "Warmth and erythema",
                "No chest pain or SOB currently",
            ],
            history=[
                "Long-haul flight 3 days ago (12 hours)",
                "On combined oral contraceptive",
                "Mother had a DVT postpartum",
            ],
            red_flags=["Chest pain or SOB (PE)", "Recent immobility", "Hormonal risk"],
            required_questions=[
                "Onset and timeline",
                "Immobility / flights",
                "Contraceptive and hormonal history",
                "Family history of VTE",
                "PE screening (SOB, chest pain, haemoptysis)",
            ],
        ),
    ]
}


def get_scenario(scenario_id: str) -> Optional[Scenario]:
    return SCENARIOS.get(scenario_id)
