import Link from "next/link";
import { Nav } from "@/components/Nav";
import { EcgHero } from "@/components/EcgHero";
import {
  ArrowRight,
  Mic,
  Activity,
  Waves,
  BrainCircuit,
  Stethoscope,
  Clock,
  BadgePoundSterling,
  ShieldCheck,
} from "lucide-react";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-white">
      <Nav variant="landing" />

      {/* HERO */}
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 grid-dots opacity-60" />
        <div className="relative mx-auto max-w-6xl px-6 pt-24 pb-16 text-center">
          <span className="pill mb-6">
            <span className="h-1.5 w-1.5 rounded-full bg-coral" /> Track 1 · Voice &amp; Medical
          </span>
          <h1 className="text-balance text-5xl font-semibold tracking-tight text-ink sm:text-6xl md:text-7xl">
            Your OSCE exam partner —
            <br />
            <span className="font-hand text-accent text-6xl sm:text-7xl md:text-8xl">
              an AI patient you can actually talk to.
            </span>
          </h1>
          <p className="mt-8 mx-auto max-w-2xl text-lg text-ink-soft leading-relaxed">
            Practice history-taking and diagnosis against a voice-first AI
            patient. Get scored on clinical reasoning — and on how you
            <em className="font-hand text-accent not-italic"> sound </em>
            while you do it.
          </p>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
            <Link href="/dashboard" className="btn-primary">
              Start a practice session <ArrowRight className="h-4 w-4" />
            </Link>
            <a href="#how" className="btn-ghost">
              How it works
            </a>
          </div>

          <div className="mt-16">
            <EcgHero />
          </div>
        </div>
      </section>

      {/* PROBLEM */}
      <section id="problem" className="border-y border-line bg-paper-2">
        <div className="mx-auto grid max-w-6xl gap-10 px-6 py-20 md:grid-cols-3">
          <div>
            <p className="font-hand text-2xl text-coral">the problem</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight text-ink">
              Standardised patients are the bottleneck in clinical training.
            </h2>
          </div>
          <div className="space-y-6 md:col-span-2">
            <ProblemRow
              icon={<BadgePoundSterling className="h-5 w-5" />}
              title="£50–200 per hour, per student"
              body="Medical schools pay trained actors to play patients. It doesn't scale, so most students get only a handful of reps before finals."
            />
            <ProblemRow
              icon={<Clock className="h-5 w-5" />}
              title="Available once a term, not at 2am the night before"
              body="Students can't book an actor when they actually need to rehearse — evenings, weekends, the day before the OSCE."
            />
            <ProblemRow
              icon={<Activity className="h-5 w-5" />}
              title="No objective feedback on delivery"
              body="Human actors can't tell you your voice sounds anxious, your pacing dropped, or that your bedside confidence faded in the last two minutes. We can."
            />
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section id="how" className="mx-auto max-w-6xl px-6 py-24">
        <div className="mb-14 text-center">
          <p className="font-hand text-2xl text-accent">the solution</p>
          <h2 className="mt-2 text-4xl font-semibold tracking-tight text-ink">
            Voice in. Voice out. Scored both ways.
          </h2>
          <p className="mt-4 mx-auto max-w-2xl text-ink-soft">
            One WebSocket runs your whole OSCE. Talk to the patient, call your
            diagnosis, walk away with a full score card.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-4">
          <HowStep
            n={1}
            icon={<Stethoscope className="h-5 w-5" />}
            title="Pick a scenario"
            body="Choose from 8 OSCE cases or design your own patient profile."
          />
          <HowStep
            n={2}
            icon={<Mic className="h-5 w-5" />}
            title="Take a history"
            body="Speak naturally. Speechmatics transcribes with 96% medical recall."
          />
          <HowStep
            n={3}
            icon={<Waves className="h-5 w-5" />}
            title="Patient replies"
            body="Gradium's low-latency TTS gives your patient a real human voice."
          />
          <HowStep
            n={4}
            icon={<BrainCircuit className="h-5 w-5" />}
            title="Get scored"
            body="Clinical reasoning (LLM evaluator) + delivery biomarkers (Thymia)."
          />
        </div>
      </section>

      {/* STACK */}
      <section id="stack" className="border-t border-line bg-paper-2">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <div className="mb-12 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="font-hand text-2xl text-accent">built on</p>
              <h2 className="text-3xl font-semibold tracking-tight text-ink">
                The entire voice AI stack, end-to-end.
              </h2>
            </div>
            <span className="pill">
              <ShieldCheck className="h-3.5 w-3.5" /> Clinical-grade pipeline
            </span>
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            <StackCard
              tag="Speechmatics"
              tone="navy"
              title="Student speech → text"
              body="Medical domain model. 93% accuracy, 96% medical keyword recall, real-time diarisation."
              bullets={["Medical domain", "ENHANCED operating point", "<1s latency"]}
            />
            <StackCard
              tag="Gradium"
              tone="accent"
              title="Patient actor → voice"
              body="Low-latency TTS streaming over WebSocket. Warm, human-sounding patient replies."
              bullets={["WebSocket streaming", "Custom voice IDs", "PCM @ 48kHz"]}
            />
            <StackCard
              tag="Thymia Sentinel"
              tone="coral"
              title="How the student sounds"
              body="Voice biomarkers in parallel — confidence, anxiety, pacing. Clinical insight hidden in how you speak."
              bullets={["Sidecar audio fork", "Concordance analysis", "Apollo + Helios"]}
            />
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-5xl px-6 py-24 text-center">
        <p className="font-hand text-3xl text-coral">ready?</p>
        <h2 className="mt-2 text-4xl font-semibold tracking-tight text-ink">
          Your next OSCE rehearsal starts in 30 seconds.
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-ink-soft">
          No booking, no actor, no room. Just a microphone and a scenario.
        </p>
        <div className="mt-8 flex justify-center">
          <Link href="/dashboard" className="btn-primary">
            Open the dashboard <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-8 text-sm text-ink-soft">
          <span>
            OSCEai · Voice AI Hack London · Track 1 — Voice &amp; Medical
          </span>
          <span className="font-hand text-lg text-accent">
            built for medical students, by people who&apos;ve sat the exam
          </span>
        </div>
      </footer>
    </main>
  );
}

function ProblemRow({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="flex gap-4 border-b border-line pb-5 last:border-b-0">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white text-ink">
        {icon}
      </div>
      <div>
        <h3 className="font-medium text-ink">{title}</h3>
        <p className="mt-1 text-ink-soft">{body}</p>
      </div>
    </div>
  );
}

function HowStep({
  n,
  icon,
  title,
  body,
}: {
  n: number;
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="relative rounded-2xl border border-line bg-white p-6">
      <div className="absolute -top-3 left-6 font-hand text-2xl text-accent">
        {n}
      </div>
      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-accent-soft text-accent">
        {icon}
      </div>
      <h3 className="mt-4 font-medium text-ink">{title}</h3>
      <p className="mt-2 text-sm text-ink-soft">{body}</p>
    </div>
  );
}

function StackCard({
  tag,
  tone,
  title,
  body,
  bullets,
}: {
  tag: string;
  tone: "accent" | "navy" | "coral";
  title: string;
  body: string;
  bullets: string[];
}) {
  const toneClasses = {
    accent: "text-accent bg-accent-soft",
    navy: "text-navy bg-navy/10",
    coral: "text-coral bg-coral/10",
  }[tone];
  return (
    <div className="rounded-2xl border border-line bg-white p-6">
      <span
        className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${toneClasses}`}
      >
        {tag}
      </span>
      <h3 className="mt-4 text-lg font-semibold tracking-tight text-ink">
        {title}
      </h3>
      <p className="mt-2 text-sm text-ink-soft">{body}</p>
      <ul className="mt-4 space-y-1.5 text-sm text-ink-soft">
        {bullets.map((b) => (
          <li key={b} className="flex items-center gap-2">
            <span className="h-1 w-1 rounded-full bg-ink" /> {b}
          </li>
        ))}
      </ul>
    </div>
  );
}
