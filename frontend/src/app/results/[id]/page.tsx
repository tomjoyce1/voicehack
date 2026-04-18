"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Logo } from "@/components/Logo";
import { ScoreDial } from "@/components/ScoreDial";
import {
  PrescriptionNote,
  type PrescriptionData,
  type PrescriptionMedication,
} from "@/components/PrescriptionNote";
import { getScenario, type Scenario } from "@/lib/scenarios";
import {
  ArrowLeft,
  RefreshCw,
  Check,
  X,
  Quote,
  Share2,
  Activity,
  TrendingDown,
  TrendingUp,
  Loader2,
} from "lucide-react";

type ResultPayload = {
  sessionId: string;
  scenarioId?: string;
  diagnosis: { given: string; correct: string; match: boolean };
  clinical: { score: number; max: number; questions: QuestionFeedback[] };
  delivery: {
    score: number;
    max: number;
    timeline: { confidence: number[]; anxiety: number[]; pacing: number[]; empathy: number[] };
    concordance: string[];
  };
  transcript: { role: "student" | "patient"; text: string; annotation?: string }[];
  transcripts?: {
    live?: { role: "student" | "patient"; text: string }[];
    medical?: { role: "student" | "patient"; text: string }[];
  };
  medical_vocab?: {
    recall: number;
    hits: string[];
    missing: string[];
    source: "speechmatics" | "gradium";
  };
  speechmatics?: {
    status: "ok" | "pending" | "error" | "skipped";
    reason?: string;
    transcript?: string;
    wpm?: number;
    filler_count?: number;
    filler_examples?: string[];
    low_confidence?: { word: string; confidence: number }[];
  };
  written_feedback: string;
  /** Optional medication rows from backend; omit on older stored results (client fallback). */
  prescriptionMedications?: PrescriptionMedication[];
};

type VoiceSection = {
  turn: number;
  nervousness: number;
  voice_strain: number;
  hesitancy: number;
  emotions: Record<string, number>;
  alert_level: string;
  confidence: string;
  rationale: string;
  concerns: string[];
};

type VoiceAnalysis = {
  status?: string;
  error?: string;
  overall?: {
    nervousness: number;
    voice_strain: number;
    hesitancy: number;
  };
  peak_stress_moment?: string;
  calmest_moment?: string;
  llm_interpretation?: string;
  sections?: VoiceSection[];
};

function isValidResultPayload(v: unknown): v is ResultPayload {
  if (!v || typeof v !== "object") return false;
  const o = v as Record<string, unknown>;
  const dx = o.diagnosis;
  if (!dx || typeof dx !== "object") return false;
  const d = dx as Record<string, unknown>;
  if (
    typeof d.given !== "string" ||
    typeof d.correct !== "string" ||
    typeof d.match !== "boolean"
  ) {
    return false;
  }
  const clin = o.clinical;
  if (!clin || typeof clin !== "object") return false;
  const c = clin as Record<string, unknown>;
  if (
    typeof c.score !== "number" ||
    typeof c.max !== "number" ||
    !Array.isArray(c.questions)
  ) {
    return false;
  }
  const del = o.delivery;
  if (!del || typeof del !== "object") return false;
  const dv = del as Record<string, unknown>;
  if (
    typeof dv.score !== "number" ||
    typeof dv.max !== "number" ||
    !Array.isArray(dv.concordance)
  ) {
    return false;
  }
  const tl = dv.timeline;
  if (!tl || typeof tl !== "object") return false;
  const t = tl as Record<string, unknown>;
  if (
    !Array.isArray(t.confidence) ||
    !Array.isArray(t.anxiety) ||
    !Array.isArray(t.pacing) ||
    !Array.isArray(t.empathy)
  ) {
    return false;
  }
  if (!Array.isArray(o.transcript) || typeof o.written_feedback !== "string")
    return false;
  return true;
}

const DEMO_RESULT: ResultPayload = {
  sessionId: "demo",
  scenarioId: "chest-pain-stemi",
  diagnosis: {
    given: "Acute myocardial infarction",
    correct: "ST-elevation myocardial infarction (STEMI)",
    match: true,
  },
  clinical: {
    score: 48,
    max: 60,
    questions: [
      { text: "SOCRATES for pain", hit: true },
      { text: "Past cardiac history", hit: true },
      { text: "Smoking history", hit: true },
      { text: "Drug history", hit: true },
      { text: "Family history", hit: false },
    ],
  },
  delivery: {
    score: 29,
    max: 40,
    timeline: {
      confidence: [52, 58, 64, 66, 70, 72, 74, 78, 82, 80, 76, 78],
      anxiety: [40, 42, 38, 35, 32, 30, 28, 24, 22, 26, 30, 28],
      pacing: [55, 58, 62, 66, 70, 72, 72, 70, 68, 65, 64, 62],
      empathy: [58, 60, 63, 66, 68, 70, 72, 72, 70, 68, 66, 66],
    },
    concordance: [
      "Between 1:20 and 1:40 you asked three closed questions in a row while your voice anxiety spiked to 42 — consider an open question to reset.",
      "You told the patient \"try not to worry\" while your own voice confidence dipped to 58 — patients pick this up unconsciously.",
    ],
  },
  transcript: [
    { role: "student", text: "Hi, I'm the medical student on the ward today. Can I ask you some questions?" },
    { role: "patient", text: "Yeah, please — this pain is awful." },
    { role: "student", text: "Where exactly is the pain?", annotation: "Good open start, SOCRATES-site" },
    { role: "patient", text: "Right in the middle of my chest, it's like a weight crushing me." },
    { role: "student", text: "Does it go anywhere else?", annotation: "Radiation — correct to ask" },
    { role: "patient", text: "Down my left arm, and into my jaw." },
    { role: "student", text: "And have you had anything like this before?" },
    { role: "patient", text: "No, never like this. I'm scared." },
    { role: "student", text: "I think you may be having a heart attack — we need to act quickly.", annotation: "Clear communication of working diagnosis" },
  ],
  written_feedback:
    "Confident, structured history-taking with strong SOCRATES coverage and an appropriate working diagnosis stated to the patient. Family history was missed — a meaningful omission for cardiovascular risk. Delivery biomarkers show steady confidence with a brief anxiety spike during the drug history; your pacing was slightly too fast in the first minute. Overall, the patient would have felt heard and reassured. With one more pass on family history you'd be in the top quartile for this scenario.",
  prescriptionMedications: [
    {
      name: "Aspirin",
      dose: "300mg",
      form: "dispersible tablets",
      quantity: "",
      instructions:
        "Loading dose immediately — chew or swallow as per ACS pathway",
    },
    {
      name: "Glyceryl trinitrate",
      dose: "400micrograms",
      form: "sublingual spray",
      quantity: "",
      instructions:
        "1–2 sprays PRN for ongoing chest pain while awaiting definitive care",
    },
  ],
};

function patientAddressLines(scenario: Scenario | undefined): string {
  if (!scenario) {
    return "Simulated patient\nTraining session\nAddress withheld";
  }
  return [
    "Simulated patient (training)",
    `${scenario.system} · ${scenario.chief_complaint}`,
    "Address withheld — training record",
  ].join("\n");
}

export default function ResultsPage({ params }: { params: { id: string } }) {
  const [data, setData] = useState<ResultPayload>({
    ...DEMO_RESULT,
    sessionId: params.id,
    scenarioId: params.id,
  });
  const [clientMeds, setClientMeds] = useState<PrescriptionMedication[] | null>(
    null,
  );
  const [voiceAnalysis, setVoiceAnalysis] = useState<VoiceAnalysis | null>(
    null,
  );

  useEffect(() => {
    const base =
      process.env.NEXT_PUBLIC_BACKEND_HTTP || "http://localhost:8000";
    let cancelled = false;

    const load = () =>
      fetch(`${base}/results/${encodeURIComponent(params.id)}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((json) => {
          if (!cancelled && json && isValidResultPayload(json)) setData(json);
          return json as ResultPayload | null;
        })
        .catch(() => null);

    load();

    // Poll the dedicated Speechmatics endpoint so the insights card lights up
    // as soon as the background batch job finishes (~5-30s post-diagnosis).
    let attempts = 0;
    const poll = setInterval(async () => {
      attempts += 1;
      const r = await fetch(
        `${base}/speechmatics/${encodeURIComponent(params.id)}`
      ).catch(() => null);
      if (!r || !r.ok) return;
      const sx = (await r.json().catch(() => null)) as
        | ResultPayload["speechmatics"]
        | null;
      if (!sx) return;
      if (sx.status === "ok" || sx.status === "error" || sx.status === "skipped") {
        clearInterval(poll);
        // Re-fetch the merged RESULTS so medical_vocab also updates.
        await load();
      }
      if (attempts > 40) clearInterval(poll); // ~2 min hard stop
    }, 3000);

    return () => {
      cancelled = true;
      clearInterval(poll);
    };
  }, [params.id]);

  useEffect(() => {
    if (data.prescriptionMedications !== undefined) {
      setClientMeds(null);
      return;
    }
    const dx = data.diagnosis?.given?.trim() ?? "";
    if (!dx) {
      setClientMeds([]);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch("/api/prescription-meds", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ diagnosis: dx }),
        });
        const j = (await r.json()) as { medications?: PrescriptionMedication[] };
        if (!cancelled) setClientMeds(j.medications ?? []);
      } catch {
        if (!cancelled) setClientMeds([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [data.diagnosis?.given, data.prescriptionMedications]);

  // Poll for Thymia voice analysis (runs in background on backend)
  useEffect(() => {
    const backendHttp =
      process.env.NEXT_PUBLIC_BACKEND_HTTP || "http://localhost:8000";
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const poll = () => {
      fetch(`${backendHttp}/voice-analysis/${encodeURIComponent(params.id)}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((json: VoiceAnalysis | null) => {
          if (cancelled || !json) return;
          if (json.status === "pending") {
            timer = setTimeout(poll, 3000);
          } else {
            setVoiceAnalysis(json);
          }
        })
        .catch(() => {
          if (!cancelled) timer = setTimeout(poll, 5000);
        });
    };

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [params.id]);

  const scenario = data.scenarioId ? getScenario(data.scenarioId) : undefined;
  const total =
    Math.round(
      ((data.clinical.score + data.delivery.score) /
        (data.clinical.max + data.delivery.max)) *
        100
    );

  const prescription: PrescriptionData = useMemo(() => {
    const medications: PrescriptionMedication[] =
      data.prescriptionMedications !== undefined
        ? data.prescriptionMedications
        : (clientMeds ?? []);
    return {
      patientName: scenario?.name ?? "Simulated patient",
      patientAge: scenario ? `${scenario.age} years (${scenario.sex})` : "—",
      patientAddress: patientAddressLines(scenario),
      medications,
      date: new Date().toLocaleDateString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      }),
    };
  }, [scenario, data.prescriptionMedications, clientMeds]);

  return (
    <main className="min-h-screen bg-white">
      {/* TOP BAR */}
      <div className="flex h-16 items-center justify-between border-b border-line px-6">
        <div className="flex min-w-0 items-center gap-4">
          <div className="flex shrink-0 flex-col gap-0.5">
            <Logo />
            <span className="text-xs text-ink-soft">PatientSim · results</span>
          </div>
          <span className="h-5 w-px shrink-0 bg-line" />
          <span className="min-w-0 truncate text-sm text-ink-soft">
            Session results{scenario ? ` · ${scenario.name}` : ""}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/dashboard" className="btn-ghost">
            <ArrowLeft className="h-4 w-4" /> Dashboard
          </Link>
          <Link
            href={`/session/${data.scenarioId || params.id}`}
            className="btn-primary"
          >
            <RefreshCw className="h-4 w-4" /> Practise again
          </Link>
        </div>
      </div>

      <section className="mx-auto max-w-6xl px-6 py-10">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="font-hand text-3xl text-accent">Your score</p>
            <h1 className="text-4xl font-semibold tracking-tight text-ink">
              {total} / 100
            </h1>
            <p className="mt-1 text-sm font-medium text-ink-soft">
              {scenario?.chief_complaint || "Session summary"}
            </p>
          </div>
          <DiagnosisBadge
            given={data.diagnosis.given}
            correct={data.diagnosis.correct}
            match={data.diagnosis.match}
          />
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-10">
        <div className="grid gap-4 md:grid-cols-2">
          <ScoreDial
            value={data.clinical.score}
            max={data.clinical.max}
            label="Clinical"
            tone="accent"
            sub="Questions asked + diagnosis accuracy"
          />
          <ScoreDial
            value={data.delivery.score}
            max={data.delivery.max}
            label="Delivery"
            tone="coral"
            sub="Thymia biomarkers through the session"
          />
        </div>
      </section>

      {data.medical_vocab && data.medical_vocab.source === "speechmatics" && (
        <section className="voicehack-print-hide-screen mx-auto max-w-6xl px-6 pb-10">
          <div className="rounded-2xl border border-line bg-white p-6">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="font-hand text-2xl text-accent">
                  Medical vocabulary recall
                </p>
                <h3 className="mt-1 text-3xl font-semibold tracking-tight text-ink">
                  {data.medical_vocab.hits.length} /{" "}
                  {data.medical_vocab.hits.length +
                    data.medical_vocab.missing.length}
                </h3>
                <p className="mt-1 text-sm text-ink-soft">
                  Speechmatics medical-domain transcription ·{" "}
                  {Math.round(data.medical_vocab.recall * 100)}% of required
                  clinical areas covered
                </p>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {data.medical_vocab.hits.map((t) => (
                <span
                  key={`hit-${t}`}
                  className="inline-flex items-center gap-1 rounded-full border border-accent/40 bg-accent-soft px-2.5 py-0.5 text-xs text-accent"
                >
                  ✓ {t}
                </span>
              ))}
              {data.medical_vocab.missing.map((t) => (
                <span
                  key={`miss-${t}`}
                  className="inline-flex items-center gap-1 rounded-full border border-line bg-white px-2.5 py-0.5 text-xs text-ink-soft"
                >
                  · {t}
                </span>
              ))}
            </div>
          </div>
        </section>
      )}

      <div className="voicehack-print-hide-screen">
        <SpeechmaticsCard sx={data.speechmatics} />
      </div>

      <div className="voicehack-print-hide-screen">
        {data.delivery.concordance.length > 0 && (
          <section className="mx-auto max-w-6xl px-6 pb-10">
            <div className="rounded-2xl border border-coral/30 bg-coral/5 p-6">
              <p className="font-hand text-2xl text-coral">
                Concordance watch-outs
              </p>
              <p className="text-sm text-ink-soft">
                Moments where what you said and how you sounded didn&apos;t line up.
              </p>
              <ul className="mt-4 space-y-3">
                {data.delivery.concordance.map((c, i) => (
                  <li key={i} className="flex items-start gap-3 text-sm text-ink">
                    <Quote className="mt-0.5 h-4 w-4 shrink-0 text-coral" />
                    <span>{c}</span>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        )}
      </div>

      <section className="mx-auto grid max-w-6xl gap-6 px-6 pb-10 md:grid-cols-[1fr_340px]">
        <div className="voicehack-print-hide-screen rounded-2xl border border-line bg-white p-6">
          <div className="flex items-center justify-between">
            <h3 className="font-hand text-2xl text-accent">transcript</h3>
            <span className="text-xs text-ink-soft">with annotations</span>
          </div>
          <div className="mt-4 space-y-4">
            {data.transcript.map((l, i) => (
              <div
                key={i}
                className={`flex ${
                  l.role === "student" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
                    l.role === "student"
                      ? "bg-ink text-white rounded-br-sm"
                      : "bg-paper-2 text-ink rounded-bl-sm border border-line"
                  }`}
                >
                  <div
                    className={`mb-0.5 text-[10px] uppercase tracking-wider ${
                      l.role === "student" ? "text-white/60" : "text-ink-soft"
                    }`}
                  >
                    {l.role === "student" ? "you" : "patient"}
                  </div>
                  {l.text}
                  {l.annotation && (
                    <div
                      className={`mt-1.5 font-hand text-base ${
                        l.role === "student" ? "text-accent-soft" : "text-accent"
                      }`}
                    >
                      ✓ {l.annotation}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        <aside className="space-y-4">
          <div className="voicehack-print-hide-screen rounded-2xl border border-line bg-white p-5">
            <h4 className="font-medium text-ink">Key questions</h4>
            <ul className="mt-3 space-y-2">
              {data.clinical.questions.map((q) => (
                <li
                  key={q.text}
                  className="flex items-start gap-2 text-sm text-ink"
                >
                  {q.hit ? (
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
                  ) : (
                    <X className="mt-0.5 h-4 w-4 shrink-0 text-coral" />
                  )}
                  <span
                    className={
                      q.hit ? "text-ink" : "text-ink-soft line-through"
                    }
                  >
                    {q.text}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="voicehack-print-hide-screen rounded-2xl border border-line bg-paper-2 p-5">
            <p className="font-hand text-2xl text-accent">examiner&apos;s note</p>
            <p className="mt-2 text-sm text-ink leading-relaxed">
              {data.written_feedback}
            </p>
          </div>

          <div
            id="prescription-print-root"
            className="rounded-2xl border border-line bg-paper-2 p-5 print:shadow-none"
          >
            <p className="font-hand text-2xl text-accent lowercase print:hidden">
              training prescription (SimPatient)
            </p>
            <p className="mt-1 text-sm text-ink-soft print:hidden">
              From your stated diagnosis — medications shown here are parsed for
              this training worksheet only.
            </p>
            <div className="mt-2">
              <PrescriptionNote prescription={prescription} layout="sidebar" />
            </div>
          </div>

          <div className="voicehack-print-hide-screen rounded-2xl border border-dashed border-line bg-white p-5 text-sm text-ink-soft">
            <div className="flex items-center gap-2">
              <Share2 className="h-4 w-4" /> Share this with a tutor
            </div>
            <p className="mt-1 text-xs">
              Export the transcript, scores and biomarker timeline as a PDF.
            </p>
          </div>
        </aside>
      </section>

      {/* VOICE CONFIDENCE REPORT (Thymia) — at the bottom */}
      <section className="voicehack-print-hide-screen mx-auto max-w-6xl px-6 pb-10">
        <VoiceConfidenceReport analysis={voiceAnalysis} />
      </section>
    </main>
  );
}

type QuestionFeedback = { text: string; hit: boolean };

function SpeechmaticsCard({
  sx,
}: {
  sx?: ResultPayload["speechmatics"];
}) {
  // Don't render at all for demo (no backend-provided data)
  if (!sx) {
    return (
      <section className="mx-auto max-w-6xl px-6 pb-10">
        <div className="rounded-2xl border border-dashed border-line bg-paper-2/40 p-6">
          <div className="flex items-center gap-3">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-accent" />
            <p className="text-sm text-ink-soft">
              <span className="font-medium text-ink">Speechmatics</span> ·
              re-transcribing with medical-domain ASR to score pacing, fillers
              and clinical vocabulary. This usually takes 20–40 seconds.
            </p>
          </div>
        </div>
      </section>
    );
  }
  if (sx.status === "skipped") return null;
  if (sx.status === "error") {
    return (
      <section className="mx-auto max-w-6xl px-6 pb-10">
        <div className="rounded-2xl border border-coral/30 bg-coral/5 p-6 text-sm text-ink-soft">
          <span className="font-medium text-coral">Speechmatics</span>{" "}
          post-session analysis unavailable
          {sx.reason ? ` — ${sx.reason}` : ""}.
        </div>
      </section>
    );
  }

  const wpm = sx.wpm ?? 0;
  // Target 140–160 WPM for conversational clinical communication.
  const paceLabel =
    wpm < 110 ? "slow" : wpm > 170 ? "rushed" : "well paced";
  const paceTone =
    wpm < 110 || wpm > 170 ? "text-coral" : "text-accent";

  return (
    <section className="mx-auto max-w-6xl px-6 pb-10">
      <div className="rounded-2xl border border-line bg-white p-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="font-hand text-2xl text-accent">
              Speechmatics insights
            </p>
            <p className="mt-1 text-sm text-ink-soft">
              Enhanced medical-domain re-transcription of your half of the
              conversation, for a cleaner signal on pacing and clarity.
            </p>
          </div>
        </div>

        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          <div className="rounded-xl border border-line bg-paper-2/60 p-4">
            <p className="text-xs uppercase tracking-wider text-ink-soft">
              Speaking rate
            </p>
            <p className="mt-1 text-3xl font-semibold tracking-tight text-ink">
              {wpm}
              <span className="ml-1 text-sm font-normal text-ink-soft">wpm</span>
            </p>
            <p className={`mt-1 text-sm ${paceTone}`}>{paceLabel}</p>
          </div>

          <div className="rounded-xl border border-line bg-paper-2/60 p-4">
            <p className="text-xs uppercase tracking-wider text-ink-soft">
              Filler words
            </p>
            <p className="mt-1 text-3xl font-semibold tracking-tight text-ink">
              {sx.filler_count ?? 0}
            </p>
            <p className="mt-1 text-sm text-ink-soft">
              {sx.filler_examples && sx.filler_examples.length > 0
                ? `e.g. ${sx.filler_examples.slice(0, 3).join(", ")}`
                : "clean delivery"}
            </p>
          </div>

          <div className="rounded-xl border border-line bg-paper-2/60 p-4">
            <p className="text-xs uppercase tracking-wider text-ink-soft">
              Unclear words
            </p>
            {sx.low_confidence && sx.low_confidence.length > 0 ? (
              <ul className="mt-1 space-y-1 text-sm text-ink">
                {sx.low_confidence.map((w) => (
                  <li
                    key={w.word}
                    className="flex items-center justify-between"
                  >
                    <span>{w.word}</span>
                    <span className="text-xs text-ink-soft">
                      {Math.round(w.confidence * 100)}%
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-sm text-ink-soft">
                all words recognised confidently
              </p>
            )}
          </div>
        </div>

        {sx.transcript && (
          <details className="group mt-4 rounded-xl border border-line bg-paper-2/40 p-4 text-sm text-ink">
            <summary className="cursor-pointer select-none font-medium text-ink">
              Medical-domain transcript ({sx.transcript.split(/\s+/).filter(Boolean).length}{" "}
              words)
            </summary>
            <p className="mt-3 leading-relaxed text-ink-soft">
              {sx.transcript}
            </p>
          </details>
        )}
      </div>
    </section>
  );
}

function DiagnosisBadge({
  given,
  correct,
  match,
}: {
  given: string;
  correct: string;
  match: boolean;
}) {
  return (
    <div
      className={`rounded-2xl border p-4 ${
        match ? "border-accent/40 bg-accent-soft" : "border-coral/40 bg-coral/10"
      }`}
    >
      <p className={`font-hand text-xl ${match ? "text-accent" : "text-coral"}`}>
        {match ? "diagnosis correct" : "diagnosis missed"}
      </p>
      <p className="mt-1 text-sm text-ink">
        <span className="text-ink-soft">You said:</span> {given}
      </p>
      <p className="text-sm text-ink">
        <span className="text-ink-soft">Actual:</span> {correct}
      </p>
    </div>
  );
}

function VoiceConfidenceReport({
  analysis,
}: {
  analysis: VoiceAnalysis | null;
}) {
  if (!analysis) {
    return (
      <div className="rounded-2xl border border-dashed border-line bg-paper-2 p-6">
        <div className="flex items-center gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-ink-soft" />
          <div>
            <p className="font-hand text-2xl text-accent">
              voice confidence report
            </p>
            <p className="text-sm text-ink-soft">
              Analysing your voice patterns with Thymia...
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (analysis.error) {
    return (
      <div className="rounded-2xl border border-line bg-paper-2 p-6">
        <p className="font-hand text-2xl text-accent">
          voice confidence report
        </p>
        <p className="mt-2 text-sm text-ink-soft">{analysis.error}</p>
      </div>
    );
  }

  if (!analysis.overall) return null;

  const o = analysis.overall;
  const fmt = (v: number) => `${Math.round(v * 100)}%`;
  const level = (v: number) =>
    v < 0.33 ? "Low" : v < 0.66 ? "Moderate" : "High";

  return (
    <div className="rounded-2xl border border-line bg-white p-6">
      <div className="flex items-center gap-2">
        <Activity className="h-5 w-5 text-accent" />
        <p className="font-hand text-2xl text-accent">
          voice confidence report
        </p>
        <span className="ml-auto text-xs text-ink-soft">Powered by Thymia</span>
      </div>
      <p className="mt-1 text-sm text-ink-soft">
        Vocal biomarker analysis of your voice during the consultation.
      </p>

      <div className="mt-5 overflow-hidden rounded-xl border border-line">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line bg-paper-2">
              <th className="px-4 py-2 text-left font-medium text-ink-soft">
                Metric
              </th>
              <th className="px-4 py-2 text-right font-medium text-ink-soft">
                Score
              </th>
              <th className="px-4 py-2 text-left font-medium text-ink-soft">
                Level
              </th>
              <th className="hidden px-4 py-2 text-left font-medium text-ink-soft sm:table-cell">
                What it measures
              </th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-line">
              <td className="px-4 py-2 font-medium text-ink">Nervousness</td>
              <td className="px-4 py-2 text-right tabular-nums text-ink">
                {fmt(o.nervousness)}
              </td>
              <td className="px-4 py-2">
                <span
                  className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${o.nervousness < 0.33 ? "bg-accent-soft text-accent" : o.nervousness < 0.66 ? "bg-gold/20 text-gold" : "bg-coral/10 text-coral"}`}
                >
                  {level(o.nervousness)}
                </span>
              </td>
              <td className="hidden px-4 py-2 text-ink-soft sm:table-cell">
                Emotional activation in voice
              </td>
            </tr>
            <tr className="border-b border-line">
              <td className="px-4 py-2 font-medium text-ink">Emotional tone</td>
              <td className="px-4 py-2 text-right tabular-nums text-ink">
                {fmt(o.voice_strain)}
              </td>
              <td className="px-4 py-2">
                <span
                  className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${o.voice_strain < 0.33 ? "bg-accent-soft text-accent" : o.voice_strain < 0.66 ? "bg-gold/20 text-gold" : "bg-coral/10 text-coral"}`}
                >
                  {level(o.voice_strain)}
                </span>
              </td>
              <td className="hidden px-4 py-2 text-ink-soft sm:table-cell">
                Sadness / concern detected in voice
              </td>
            </tr>
            <tr>
              <td className="px-4 py-2 font-medium text-ink">Hesitancy</td>
              <td className="px-4 py-2 text-right tabular-nums text-ink">
                {fmt(o.hesitancy)}
              </td>
              <td className="px-4 py-2">
                <span
                  className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${o.hesitancy < 0.33 ? "bg-accent-soft text-accent" : o.hesitancy < 0.66 ? "bg-gold/20 text-gold" : "bg-coral/10 text-coral"}`}
                >
                  {level(o.hesitancy)}
                </span>
              </td>
              <td className="hidden px-4 py-2 text-ink-soft sm:table-cell">
                Uncertainty in vocal delivery
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {analysis.peak_stress_moment && (
          <div className="flex items-start gap-2 rounded-xl border border-coral/30 bg-coral/5 p-3">
            <TrendingUp className="mt-0.5 h-4 w-4 shrink-0 text-coral" />
            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-coral">
                Most nervous
              </p>
              <p className="mt-0.5 text-sm text-ink">
                {analysis.peak_stress_moment}
              </p>
            </div>
          </div>
        )}
        {analysis.calmest_moment && (
          <div className="flex items-start gap-2 rounded-xl border border-accent/30 bg-accent-soft p-3">
            <TrendingDown className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-accent">
                Most calm
              </p>
              <p className="mt-0.5 text-sm text-ink">
                {analysis.calmest_moment}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
