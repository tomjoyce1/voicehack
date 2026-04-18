"use client";

export type TranscriptEvent = {
  type: "transcript";
  role: "student" | "patient";
  text: string;
  final: boolean;
  ts: number;
};

export type BiomarkerEvent = {
  type: "biomarker";
  confidence: number;
  anxiety: number;
  pacing: number;
  empathy: number;
  ts: number;
};

export type PatientAudioEvent = {
  type: "patient_audio";
  data: string; // base64 pcm16 @ 48k mono
  ts: number;
};

export type StopAudioEvent = {
  type: "stop_audio";
  ts: number;
};

export type ScoredEvent = {
  type: "scored";
  sessionId: string;
};

export type ServerEvent =
  | TranscriptEvent
  | BiomarkerEvent
  | PatientAudioEvent
  | StopAudioEvent
  | ScoredEvent;

export type ClientEvent =
  | { type: "audio"; data: string }
  | { type: "start"; scenarioId: string; blind?: boolean }
  | { type: "diagnosis"; text: string }
  | { type: "stop" };

const BACKEND_WS =
  process.env.NEXT_PUBLIC_BACKEND_WS || "ws://localhost:8000/ws/session";

export class SessionClient {
  ws: WebSocket | null = null;
  onEvent?: (e: ServerEvent) => void;
  onOpen?: () => void;
  onClose?: () => void;
  private audioCtx: AudioContext | null = null;
  private scheduledAt = 0;
  private activeSources: AudioBufferSourceNode[] = [];

  constructor(private sessionId: string) {}

  connect() {
    const url = `${BACKEND_WS}/${encodeURIComponent(this.sessionId)}`;
    const ws = new WebSocket(url);
    this.ws = ws;
    ws.onopen = () => this.onOpen?.();
    ws.onclose = () => this.onClose?.();
    ws.onerror = () => this.onClose?.();
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as ServerEvent;
        if (msg.type === "patient_audio") {
          this.schedulePatientAudio(msg.data);
        } else if (msg.type === "stop_audio") {
          this.stopPatientAudio();
        }
        this.onEvent?.(msg);
      } catch {
        // ignore
      }
    };
  }

  send(msg: ClientEvent) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  close() {
    this.ws?.close();
    this.ws = null;
    if (this.audioCtx) {
      this.audioCtx.close();
      this.audioCtx = null;
    }
  }

  private ensureAudioCtx() {
    if (!this.audioCtx) {
      const AC =
        (window as unknown as { AudioContext: typeof AudioContext }).AudioContext ||
        (
          window as unknown as {
            webkitAudioContext: typeof AudioContext;
          }
        ).webkitAudioContext;
      this.audioCtx = new AC({ sampleRate: 48000 });
      this.scheduledAt = this.audioCtx.currentTime;
    }
    return this.audioCtx;
  }

  stopPatientAudio() {
    for (const src of this.activeSources) {
      try {
        src.stop();
      } catch {
        // already stopped
      }
    }
    this.activeSources = [];
    if (this.audioCtx) {
      this.scheduledAt = this.audioCtx.currentTime;
    }
  }

  private schedulePatientAudio(base64: string) {
    const ctx = this.ensureAudioCtx();
    const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
    const dv = new DataView(bytes.buffer);
    const frames = bytes.length / 2;
    const buf = ctx.createBuffer(1, frames, 48000);
    const ch = buf.getChannelData(0);
    for (let i = 0; i < frames; i++) {
      ch[i] = dv.getInt16(i * 2, true) / 32768;
    }
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.connect(ctx.destination);
    const now = ctx.currentTime;
    const start = Math.max(now, this.scheduledAt);
    src.start(start);
    this.scheduledAt = start + buf.duration;
    this.activeSources.push(src);
    src.onended = () => {
      const idx = this.activeSources.indexOf(src);
      if (idx >= 0) this.activeSources.splice(idx, 1);
    };
  }
}
