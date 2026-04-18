# PatientSim

Voice-first **OSCE** practice for medical students: an AI patient you can speak with, an examiner that scores your clinical reasoning, and **Thymia** biomarkers that score how you sound while you do it.

Built for the Voice AI Hack London, Track 1 — Voice & Medical.

## Stack

- **Frontend** — Next.js 14 (App Router) + Tailwind + Framer Motion. Handwritten accents (`Caveat`), white paper theme.
- **Backend** — FastAPI, single WebSocket per session.
- **STT** — [Speechmatics](https://docs.speechmatics.com/) `speechmatics-rt` with `domain="medical"` and `operating_point=ENHANCED`.
- **LLM** — OpenAI (`gpt-4o-mini` by default) as the patient actor + examiner feedback writer.
- **TTS** — [Gradium](https://docs.gradium.ai/) streaming PCM over WebSocket.
- **Biomarkers** — [Thymia Sentinel](https://thymia-ai.github.io/thymia-sentinel-integrations/1.1.0/) sidecar listening to the student's audio.

Every module has a demo fallback so the full flow works without any API keys — useful for local dev and for the judges to try the UI.

## Architecture

```
Student mic ─┬─► Speechmatics (student transcript)
             └─► Thymia Sentinel (confidence / anxiety / pacing / empathy)
                     │
                     ▼
             FastAPI session server ─► GPT-4o patient actor ─► Gradium TTS ─► Student speakers
                     │
                     └─► Scoring engine (clinical + delivery) ─► /results/[id]
```

## Run it

### Backend

```bash
cd backend
./run.sh
```

That script creates a venv, installs deps, copies `.env.example` to `.env`, and starts `uvicorn app.main:app` on port 8000. Keep `DEMO_MODE=1` to run fully offline.

### Frontend

```bash
cd frontend
cp .env.local.example .env.local
npm install        # already done by create-next-app
npm run dev
```

Open http://localhost:3000.

## Pages

- `/` — landing page with problem + solution + stack.
- `/dashboard` — pick a mode (OSCE scenarios, design your own, free practice, blind patient) and a scenario.
- `/session/[id]` — live OSCE: waveform avatar, live transcript, live biomarker pills, mic + call-diagnosis buttons.
- `/results/[id]` — clinical + delivery scores, biomarker timeline, annotated transcript, examiner-style written feedback.

## Demo mode

If you don't have API keys the system still fully runs:

- STT → VAD-triggered placeholder utterances.
- LLM → scripted keyword-matched patient replies.
- TTS → formant-like soft tone, paced so the waveform reacts.
- Thymia → RMS-driven drift trajectory for all four delivery scores.
