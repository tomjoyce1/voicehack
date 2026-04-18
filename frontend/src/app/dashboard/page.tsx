"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Nav } from "@/components/Nav";
import { SCENARIOS } from "@/lib/scenarios";
import {
  ClipboardList,
  PencilRuler,
  MessagesSquare,
  EyeOff,
  ArrowRight,
  Search,
  Sparkles,
} from "lucide-react";

type Mode = "osce" | "custom" | "free" | "blind";

export default function DashboardPage() {
  const [mode, setMode] = useState<Mode>("osce");
  const [query, setQuery] = useState("");
  const [system, setSystem] = useState<string>("All");

  const systems = useMemo(
    () => ["All", ...Array.from(new Set(SCENARIOS.map((s) => s.system)))],
    []
  );

  const filtered = SCENARIOS.filter((s) => {
    const q = query.trim().toLowerCase();
    const matchesQ =
      !q ||
      s.name.toLowerCase().includes(q) ||
      s.chief_complaint.toLowerCase().includes(q) ||
      s.system.toLowerCase().includes(q);
    const matchesS = system === "All" || s.system === system;
    return matchesQ && matchesS;
  });

  return (
    <main className="min-h-screen bg-white">
      <Nav variant="app" />

      <section className="mx-auto max-w-6xl px-6 pt-10 pb-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="font-hand text-2xl text-accent">welcome back</p>
            <h1 className="text-3xl font-semibold tracking-tight text-ink">
              What do you want to practise today?
            </h1>
            <p className="mt-2 text-sm text-ink-soft">
              PatientSim · OSCE voice practice
            </p>
          </div>
          <div className="flex items-center gap-2">
            <SkillsChip label="Cardio" value={72} />
            <SkillsChip label="Resp" value={84} />
            <SkillsChip label="Neuro" value={61} />
            <SkillsChip label="GI" value={70} />
          </div>
        </div>
      </section>

      {/* MODE CARDS */}
      <section className="mx-auto max-w-6xl px-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <ModeCard
            active={mode === "osce"}
            onClick={() => setMode("osce")}
            icon={<ClipboardList className="h-5 w-5" />}
            title="OSCE Scenarios"
            sub="8 exam-style cases, timed"
            accent="accent"
          />
          <ModeCard
            active={mode === "custom"}
            onClick={() => setMode("custom")}
            icon={<PencilRuler className="h-5 w-5" />}
            title="Design Your Own"
            sub="Define patient, symptoms, dx"
            accent="navy"
          />
          <ModeCard
            active={mode === "free"}
            onClick={() => setMode("free")}
            icon={<MessagesSquare className="h-5 w-5" />}
            title="Free Practice"
            sub="No timer, no scoring pressure"
            accent="gold"
          />
          <ModeCard
            active={mode === "blind"}
            onClick={() => setMode("blind")}
            icon={<EyeOff className="h-5 w-5" />}
            title="Blind Patient"
            sub="Elicit everything yourself"
            accent="coral"
          />
        </div>
      </section>

      {/* MODE BODY */}
      <section className="mx-auto max-w-6xl px-6 py-10">
        {mode === "osce" && (
          <ScenarioBrowser
            query={query}
            setQuery={setQuery}
            systems={systems}
            system={system}
            setSystem={setSystem}
            items={filtered}
            blind={false}
          />
        )}
        {mode === "blind" && (
          <ScenarioBrowser
            query={query}
            setQuery={setQuery}
            systems={systems}
            system={system}
            setSystem={setSystem}
            items={filtered}
            blind
          />
        )}
        {mode === "custom" && <CustomScenarioForm />}
        {mode === "free" && <FreePractice />}
      </section>

      {/* RECENT */}
      <section className="border-t border-line bg-paper-2">
        <div className="mx-auto max-w-6xl px-6 py-10">
          <h2 className="font-hand text-2xl text-accent">recent sessions</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <RecentRow
              title="Chest pain — Michael Davies"
              score={82}
              delivery={71}
              when="Yesterday, 9:14pm"
            />
            <RecentRow
              title="SOB — Priya Shah"
              score={76}
              delivery={80}
              when="2 days ago"
            />
            <RecentRow
              title="Headache — Eleanor Price"
              score={64}
              delivery={58}
              when="Last week"
            />
          </div>
        </div>
      </section>
    </main>
  );
}

function ModeCard({
  active,
  onClick,
  icon,
  title,
  sub,
  accent,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  title: string;
  sub: string;
  accent: "accent" | "navy" | "gold" | "coral";
}) {
  const badge = {
    accent: "bg-accent-soft text-accent",
    navy: "bg-navy/10 text-navy",
    gold: "bg-gold/20 text-gold",
    coral: "bg-coral/10 text-coral",
  }[accent];
  return (
    <button
      onClick={onClick}
      className={`group text-left rounded-2xl border p-5 transition ${
        active
          ? "border-ink bg-white shadow-soft"
          : "border-line bg-white hover:border-ink/40"
      }`}
    >
      <div
        className={`flex h-9 w-9 items-center justify-center rounded-full ${badge}`}
      >
        {icon}
      </div>
      <h3 className="mt-4 font-medium text-ink">{title}</h3>
      <p className="mt-1 text-sm text-ink-soft">{sub}</p>
    </button>
  );
}

function SkillsChip({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-2 rounded-full border border-line bg-white px-3 py-1.5 text-xs text-ink-soft">
      <span className="font-medium text-ink">{label}</span>
      <span className="h-1.5 w-20 overflow-hidden rounded-full bg-paper-2">
        <span
          className="block h-full bg-accent"
          style={{ width: `${value}%` }}
        />
      </span>
      <span>{value}</span>
    </div>
  );
}

function ScenarioBrowser({
  query,
  setQuery,
  systems,
  system,
  setSystem,
  items,
  blind,
}: {
  query: string;
  setQuery: (q: string) => void;
  systems: string[];
  system: string;
  setSystem: (s: string) => void;
  items: typeof SCENARIOS;
  blind: boolean;
}) {
  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div className="flex flex-1 items-center gap-2 rounded-full border border-line bg-white px-4 py-2.5">
          <Search className="h-4 w-4 text-ink-soft" />
          <input
            placeholder="Search by complaint, system, or patient..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-ink-soft/60"
          />
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {systems.map((s) => (
            <button
              key={s}
              onClick={() => setSystem(s)}
              className={`rounded-full border px-3 py-1.5 text-xs transition ${
                system === s
                  ? "border-ink bg-ink text-white"
                  : "border-line bg-white text-ink-soft hover:border-ink/40"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {items.map((s) => (
          <Link
            key={s.id}
            href={`/session/${s.id}${blind ? "?blind=1" : ""}`}
            className="group flex flex-col rounded-2xl border border-line bg-white p-5 transition hover:border-ink/40 hover:shadow-soft"
          >
            <div className="flex items-center justify-between">
              <span className="pill">{s.system}</span>
              <span className="font-hand text-lg text-accent">
                {s.difficulty}
              </span>
            </div>
            <h3 className="mt-3 text-lg font-semibold tracking-tight text-ink">
              {blind ? "Blind patient" : s.name}
              {!blind && (
                <span className="ml-1 font-normal text-ink-soft">
                  · {s.age}
                  {s.sex.toLowerCase()}
                </span>
              )}
            </h3>
            <p className="mt-1 text-sm text-ink-soft">
              {blind ? "No presenting complaint shown" : s.chief_complaint}
            </p>
            <div className="mt-4 flex items-center justify-between text-sm">
              <span className="text-ink-soft">
                {blind ? "Elicit everything" : `${s.required_questions.length} key Qs`}
              </span>
              <span className="inline-flex items-center gap-1 font-medium text-ink group-hover:text-accent">
                Start <ArrowRight className="h-4 w-4" />
              </span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

function CustomScenarioForm() {
  return (
    <div className="grid gap-6 md:grid-cols-[1fr_320px]">
      <form className="rounded-2xl border border-line bg-white p-6">
        <h3 className="text-lg font-semibold text-ink">Design your patient</h3>
        <p className="text-sm text-ink-soft">
          The profile becomes the patient actor&apos;s system prompt inside the
          LLM. Hidden fields stay hidden from you during the OSCE.
        </p>
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <Field label="Patient name" placeholder="e.g. Helen Carter" />
          <Field label="Age" placeholder="e.g. 62" />
          <Field label="Sex" placeholder="F / M" />
          <Field label="System" placeholder="e.g. Cardiovascular" />
          <Field
            label="Chief complaint"
            placeholder="e.g. Crushing chest pain"
            full
          />
          <Field
            label="Opening line (what the patient says first)"
            placeholder="e.g. Doctor, my chest feels awful..."
            full
          />
          <Textarea
            label="Symptoms (hidden — revealed only if asked)"
            placeholder="Radiates to jaw, sweating, nausea, started 1h ago..."
          />
          <Textarea
            label="Past medical / social history"
            placeholder="HTN, T2DM, 30 pack-years..."
          />
          <Field label="Correct diagnosis (hidden)" placeholder="e.g. STEMI" full />
        </div>
        <div className="mt-6 flex items-center justify-between">
          <p className="font-hand text-accent text-lg">
            this becomes your patient&apos;s script
          </p>
          <button type="button" className="btn-primary">
            <Sparkles className="h-4 w-4" /> Generate &amp; start
          </button>
        </div>
      </form>
      <aside className="rounded-2xl border border-line bg-paper-2 p-6">
        <h4 className="font-hand text-2xl text-accent">tip</h4>
        <p className="mt-2 text-sm text-ink-soft">
          Want a harder case? Give the patient vague opening words (&quot;I
          just feel off&quot;) and move the key findings into the hidden
          symptoms list — you&apos;ll have to work for them.
        </p>
        <div className="mt-5 border-t border-line pt-5">
          <h4 className="font-medium text-ink">Preset templates</h4>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="pill">Vague presenter</span>
            <span className="pill">Anxious patient</span>
            <span className="pill">Non-English first language</span>
            <span className="pill">Non-compliant</span>
          </div>
        </div>
      </aside>
    </div>
  );
}

function FreePractice() {
  return (
    <div className="rounded-2xl border border-dashed border-line bg-paper-2 p-10 text-center">
      <p className="font-hand text-3xl text-accent">freestyle</p>
      <h3 className="mt-2 text-2xl font-semibold text-ink">
        An AI patient with no script, no timer, no score.
      </h3>
      <p className="mx-auto mt-3 max-w-xl text-ink-soft">
        We&apos;ll pick a random presentation and the patient will roll with
        whatever line of questioning you go down. Good for warming up before a
        real OSCE.
      </p>
      <Link href="/session/free-practice" className="btn-primary mt-6">
        Start free session <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  );
}

function Field({
  label,
  placeholder,
  full,
}: {
  label: string;
  placeholder: string;
  full?: boolean;
}) {
  return (
    <label className={`block ${full ? "md:col-span-2" : ""}`}>
      <span className="text-xs font-medium text-ink-soft">{label}</span>
      <input
        placeholder={placeholder}
        className="mt-1.5 w-full rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none focus:border-ink"
      />
    </label>
  );
}

function Textarea({
  label,
  placeholder,
}: {
  label: string;
  placeholder: string;
}) {
  return (
    <label className="block md:col-span-2">
      <span className="text-xs font-medium text-ink-soft">{label}</span>
      <textarea
        placeholder={placeholder}
        rows={3}
        className="mt-1.5 w-full rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none focus:border-ink"
      />
    </label>
  );
}

function RecentRow({
  title,
  score,
  delivery,
  when,
}: {
  title: string;
  score: number;
  delivery: number;
  when: string;
}) {
  return (
    <div className="rounded-2xl border border-line bg-white p-5">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-ink">{title}</h3>
        <span className="text-xs text-ink-soft">{when}</span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs text-ink-soft">Clinical</p>
          <p className="text-2xl font-semibold text-ink">{score}</p>
        </div>
        <div>
          <p className="text-xs text-ink-soft">Delivery</p>
          <p className="text-2xl font-semibold text-coral">{delivery}</p>
        </div>
      </div>
    </div>
  );
}
