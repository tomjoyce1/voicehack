"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { ScoreDial } from "@/components/ScoreDial";
import { BiomarkerTimeline } from "@/components/BiomarkerTimeline";
import { getScenario } from "@/lib/scenarios";
import {
  ArrowLeft,
  RefreshCw,
  Check,
  X,
  Quote,
  Share2,
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
  written_feedback: string;
};

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
};

export default function ResultsPage({ params }: { params: { id: string } }) {
  const [data, setData] = useState<ResultPayload>({
    ...DEMO_RESULT,
    sessionId: params.id,
    scenarioId: params.id,
  });

  useEffect(() => {
    const url =
      (process.env.NEXT_PUBLIC_BACKEND_HTTP || "http://localhost:8000") +
      `/results/${encodeURIComponent(params.id)}`;
    fetch(url)
      .then((r) => (r.ok ? r.json() : null))
      .then((json) => {
        if (json) setData(json as ResultPayload);
      })
      .catch(() => {
        // fall back to DEMO_RESULT
      });
  }, [params.id]);

  const scenario = data.scenarioId ? getScenario(data.scenarioId) : undefined;
  const total =
    Math.round(
      ((data.clinical.score + data.delivery.score) /
        (data.clinical.max + data.delivery.max)) *
        100
    );

  return (
    <main className="min-h-screen bg-white">
      {/* TOP BAR */}
      <div className="flex h-16 items-center justify-between border-b border-line px-6">
        <div className="flex items-center gap-4">
          <Logo />
          <span className="h-5 w-px bg-line" />
          <span className="text-sm text-ink-soft">
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
            <p className="font-hand text-3xl text-accent">your score</p>
            <h1 className="text-4xl font-semibold tracking-tight text-ink">
              {total} / 100
            </h1>
            <p className="mt-1 text-ink-soft">
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

      <section className="mx-auto max-w-6xl px-6 pb-10">
        <BiomarkerTimeline
          series={[
            { name: "Confidence", color: "#2f7a4f", values: data.delivery.timeline.confidence },
            { name: "Anxiety", color: "#e26d5c", values: data.delivery.timeline.anxiety },
            { name: "Pacing", color: "#1b2a4e", values: data.delivery.timeline.pacing },
            { name: "Empathy", color: "#d4a24c", values: data.delivery.timeline.empathy },
          ]}
        />
      </section>

      {data.delivery.concordance.length > 0 && (
        <section className="mx-auto max-w-6xl px-6 pb-10">
          <div className="rounded-2xl border border-coral/30 bg-coral/5 p-6">
            <p className="font-hand text-2xl text-coral">
              concordance watch-outs
            </p>
            <p className="text-sm text-ink-soft">
              Moments where what you said and how you sounded didn&apos;t match.
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

      <section className="mx-auto grid max-w-6xl gap-6 px-6 pb-10 md:grid-cols-[1fr_340px]">
        <div className="rounded-2xl border border-line bg-white p-6">
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
          <div className="rounded-2xl border border-line bg-white p-5">
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

          <div className="rounded-2xl border border-line bg-paper-2 p-5">
            <p className="font-hand text-2xl text-accent">examiner&apos;s note</p>
            <p className="mt-2 text-sm text-ink leading-relaxed">
              {data.written_feedback}
            </p>
          </div>

          <div className="rounded-2xl border border-dashed border-line bg-white p-5 text-sm text-ink-soft">
            <div className="flex items-center gap-2">
              <Share2 className="h-4 w-4" /> Share this with a tutor
            </div>
            <p className="mt-1 text-xs">
              Export the transcript, scores and biomarker timeline as a PDF.
            </p>
          </div>
        </aside>
      </section>
    </main>
  );
}

type QuestionFeedback = { text: string; hit: boolean };

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
