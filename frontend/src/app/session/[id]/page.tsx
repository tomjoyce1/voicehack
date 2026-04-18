"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Logo } from "@/components/Logo";
import { Waveform } from "@/components/Waveform";
import { BiomarkerPill } from "@/components/BiomarkerPill";
import { getScenario } from "@/lib/scenarios";
import { SessionClient, ServerEvent } from "@/lib/session-client";
import { MicStreamer } from "@/lib/mic";
import {
  Mic,
  MicOff,
  PhoneOff,
  ClipboardCheck,
  Clock,
  User,
  Pause,
  Play,
} from "lucide-react";

type Line = {
  role: "student" | "patient";
  text: string;
  final: boolean;
  ts: number;
};

export default function SessionPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const search = useSearchParams();
  const blind = search.get("blind") === "1";
  const scenario = useMemo(() => getScenario(params.id), [params.id]);

  const [connected, setConnected] = useState(false);
  const [micOn, setMicOn] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [amp, setAmp] = useState(0);
  const [transcript, setTranscript] = useState<Line[]>([]);
  const [biomarkers, setBiomarkers] = useState({
    confidence: 70,
    anxiety: 30,
    pacing: 60,
    empathy: 65,
  });
  const [seconds, setSeconds] = useState(0);
  const [paused, setPaused] = useState(false);
  const [diagnosis, setDiagnosis] = useState("");
  const [showDiagnose, setShowDiagnose] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const sessionRef = useRef<SessionClient | null>(null);
  const micRef = useRef<MicStreamer | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const lastPatientAudioAt = useRef(0);

  // Timer
  useEffect(() => {
    if (paused) return;
    const id = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [paused]);

  // WebSocket + lifecycle
  useEffect(() => {
    const s = new SessionClient(params.id);
    sessionRef.current = s;
    s.onOpen = () => {
      setConnected(true);
      s.send({ type: "start", scenarioId: params.id, blind });
    };
    s.onClose = () => setConnected(false);
    s.onEvent = (e: ServerEvent) => {
      if (e.type === "transcript") {
        setTranscript((lines) => {
          const last = lines[lines.length - 1];
          if (last && last.role === e.role && !last.final) {
            const next = [...lines];
            next[next.length - 1] = {
              role: e.role,
              text: e.text,
              final: e.final,
              ts: e.ts,
            };
            return next;
          }
          return [
            ...lines,
            { role: e.role, text: e.text, final: e.final, ts: e.ts },
          ];
        });
      } else if (e.type === "biomarker") {
        setBiomarkers({
          confidence: e.confidence,
          anxiety: e.anxiety,
          pacing: e.pacing,
          empathy: e.empathy,
        });
      } else if (e.type === "patient_audio") {
        lastPatientAudioAt.current = Date.now();
        setSpeaking(true);
      } else if (e.type === "stop_audio") {
        setSpeaking(false);
      } else if (e.type === "scored") {
        router.push(`/results/${e.sessionId}`);
      }
    };
    s.connect();
    return () => {
      s.close();
      sessionRef.current = null;
    };
  }, [params.id, blind, router]);

  // Decay speaking flag when no audio
  useEffect(() => {
    const id = setInterval(() => {
      if (Date.now() - lastPatientAudioAt.current > 500) setSpeaking(false);
    }, 200);
    return () => clearInterval(id);
  }, []);

  // Autoscroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  const toggleMic = async () => {
    if (micOn) {
      micRef.current?.stop();
      micRef.current = null;
      setMicOn(false);
      setAmp(0);
      return;
    }
    const m = new MicStreamer();
    m.onChunk = (b64) => sessionRef.current?.send({ type: "audio", data: b64 });
    m.onLevel = (level) => setAmp(level);
    try {
      await m.start();
      micRef.current = m;
      setMicOn(true);
    } catch {
      setMicOn(false);
    }
  };

  const callDiagnosis = () => setShowDiagnose(true);
  const submitDiagnosis = () => {
    if (!diagnosis.trim() || submitting) return;
    setSubmitting(true);
    sessionRef.current?.send({ type: "diagnosis", text: diagnosis });
    // If backend never replies (demo mode), fall back to results page after a beat
    setTimeout(() => {
      if (submitting) router.push(`/results/${params.id}`);
    }, 4000);
  };

  const timeStr = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(
    seconds % 60
  ).padStart(2, "0")}`;

  return (
    <main className="flex h-screen flex-col bg-white">
      {/* TOP BAR */}
      <div className="flex h-16 shrink-0 items-center justify-between border-b border-line px-6">
        <div className="flex min-w-0 items-center gap-4">
          <div className="flex min-w-0 shrink-0 flex-col gap-0.5">
            <Logo />
            <span className="text-xs text-ink-soft">PatientSim · live session</span>
          </div>
          <span className="h-5 w-px shrink-0 bg-line" />
          <span className="min-w-0 truncate text-sm text-ink-soft">
            {blind
              ? "Blind patient"
              : scenario
              ? `${scenario.name} · ${scenario.age}${scenario.sex.toLowerCase()} · ${scenario.system}`
              : "Free practice"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="pill">
            <Clock className="h-3.5 w-3.5" />
            {timeStr}
          </span>
          <span
            className={`pill ${
              connected ? "text-accent" : "text-coral"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                connected ? "bg-accent" : "bg-coral"
              }`}
            />
            {connected ? "Live" : "Connecting…"}
          </span>
          <button
            onClick={() => setPaused((p) => !p)}
            className="btn-ghost"
            aria-label="pause"
          >
            {paused ? (
              <Play className="h-4 w-4" />
            ) : (
              <Pause className="h-4 w-4" />
            )}
            {paused ? "Resume" : "Pause"}
          </button>
          <Link href="/dashboard" className="btn-ghost">
            <PhoneOff className="h-4 w-4" /> End
          </Link>
        </div>
      </div>

      {/* BIOMARKER STRIP */}
      <div className="flex shrink-0 items-center gap-2 overflow-x-auto border-b border-line bg-paper-2 px-6 py-3">
        <span className="mr-2 shrink-0 text-xs font-semibold uppercase tracking-wide text-ink-soft">
          Delivery signals
        </span>
        <BiomarkerPill
          label="Confidence"
          value={biomarkers.confidence}
          tone="accent"
        />
        <BiomarkerPill
          label="Anxiety"
          value={biomarkers.anxiety}
          tone="coral"
        />
        <BiomarkerPill label="Pacing" value={biomarkers.pacing} tone="navy" />
        <BiomarkerPill label="Empathy" value={biomarkers.empathy} tone="gold" />
        <span className="ml-auto text-xs text-ink-soft">
          Thymia Sentinel · live
        </span>
      </div>

      {/* MAIN */}
      <div className="grid flex-1 grid-cols-1 overflow-hidden lg:grid-cols-[minmax(0,1fr)_520px]">
        {/* LEFT: patient waveform */}
        <div className="relative flex flex-col items-center justify-center border-r border-line bg-paper-2 p-6">
          <div className="pointer-events-none absolute inset-0 grid-dots opacity-60" />
          <div className="relative flex flex-col items-center">
            <p className="font-hand text-2xl text-accent">
              {blind ? "the patient" : scenario?.name}
            </p>
            <p className="text-sm text-ink-soft">
              {speaking ? "speaking…" : "listening"}
            </p>
            <div className="mt-4 aspect-square w-[360px] max-w-[52vw]">
              <Waveform amplitude={amp * 3} speaking={speaking} />
            </div>
            {!blind && scenario && (
              <div className="mt-6 max-w-md rounded-2xl border border-line bg-white p-5">
                <div className="flex items-center gap-2 text-sm text-ink-soft">
                  <User className="h-4 w-4" /> Presenting complaint
                </div>
                <p className="mt-1 text-ink">{scenario.chief_complaint}</p>
                <p className="mt-3 font-hand text-lg text-coral">
                  &quot;{scenario.presenting_line}&quot;
                </p>
              </div>
            )}
          </div>

          {/* MIC CONTROLS */}
          <div className="mt-auto flex items-center gap-3 pt-8">
            <button
              onClick={toggleMic}
              className={`flex h-16 w-16 items-center justify-center rounded-full border transition ${
                micOn
                  ? "border-coral bg-coral text-white"
                  : "border-ink bg-ink text-white hover:bg-ink/90"
              }`}
              aria-label={micOn ? "mute" : "unmute"}
            >
              {micOn ? (
                <Mic className="h-6 w-6" />
              ) : (
                <MicOff className="h-6 w-6" />
              )}
            </button>
            <button
              onClick={callDiagnosis}
              className="btn-primary"
            >
              <ClipboardCheck className="h-4 w-4" /> Call diagnosis
            </button>
          </div>
        </div>

        {/* RIGHT: transcript */}
        <div className="flex min-h-0 flex-col">
          <div className="flex shrink-0 items-center justify-between border-b border-line px-6 py-3">
            <h2 className="font-hand text-2xl text-accent">Transcript</h2>
            <span className="text-xs text-ink-soft">
              Speechmatics · medical domain
            </span>
          </div>
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {transcript.length === 0 && (
              <div className="mx-auto max-w-sm rounded-xl border border-dashed border-line bg-paper-2 p-6 text-center text-sm text-ink-soft">
                Turn on your mic and introduce yourself. PatientSim streams the
                patient&apos;s replies in character as soon as audio is detected.
              </div>
            )}
            <div className="space-y-4">
              {transcript.map((l, i) => (
                <TranscriptLine key={i} line={l} />
              ))}
              <div ref={transcriptEndRef} />
            </div>
          </div>
        </div>
      </div>

      {/* DIAGNOSIS MODAL */}
      {showDiagnose && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-6">
          <div className="w-full max-w-lg rounded-2xl border border-line bg-white p-6">
            <p className="font-hand text-2xl text-accent">your diagnosis</p>
            <h3 className="mt-1 text-xl font-semibold text-ink">
              What&apos;s going on with this patient?
            </h3>
            <p className="mt-2 text-sm text-ink-soft">
              State your working diagnosis in plain words — exactly as you would
              to the examiner.
            </p>
            <textarea
              value={diagnosis}
              onChange={(e) => setDiagnosis(e.target.value)}
              rows={3}
              autoFocus
              placeholder="e.g. Acute ST-elevation myocardial infarction"
              className="mt-4 w-full rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none focus:border-ink"
            />
            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={() => setShowDiagnose(false)}
                className="btn-ghost"
              >
                Keep going
              </button>
              <button
                onClick={submitDiagnosis}
                disabled={!diagnosis.trim() || submitting}
                className="btn-primary disabled:opacity-60"
              >
                {submitting ? "Scoring…" : "Submit & score"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

function TranscriptLine({ line }: { line: Line }) {
  const isStudent = line.role === "student";
  return (
    <div
      className={`flex ${isStudent ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
          isStudent
            ? "bg-ink text-white rounded-br-sm"
            : "bg-paper-2 text-ink rounded-bl-sm border border-line"
        } ${!line.final ? "opacity-70 italic" : ""}`}
      >
        <div
          className={`mb-0.5 text-[10px] uppercase tracking-wider ${
            isStudent ? "text-white/60" : "text-ink-soft"
          }`}
        >
          {isStudent ? "you" : "patient"}
        </div>
        {line.text || "…"}
      </div>
    </div>
  );
}
