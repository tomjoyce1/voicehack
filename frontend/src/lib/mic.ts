"use client";

export class MicStreamer {
  private ctx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private node: ScriptProcessorNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  running = false;
  targetSampleRate = 16000;
  onChunk?: (b64: string) => void;
  onLevel?: (level: number) => void;

  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        sampleRate: 48000,
        channelCount: 1,
      },
    });
    const AC =
      (window as unknown as { AudioContext: typeof AudioContext }).AudioContext ||
      (
        window as unknown as {
          webkitAudioContext: typeof AudioContext;
        }
      ).webkitAudioContext;
    this.ctx = new AC();
    this.source = this.ctx.createMediaStreamSource(this.stream);
    this.node = this.ctx.createScriptProcessor(4096, 1, 1);
    this.source.connect(this.node);
    this.node.connect(this.ctx.destination);
    const nativeRate = this.ctx.sampleRate;
    const targetRate = this.targetSampleRate;
    this.running = true;

    this.node.onaudioprocess = (e) => {
      if (!this.running) return;
      const input = e.inputBuffer.getChannelData(0);
      // compute level (RMS)
      let sum = 0;
      for (let i = 0; i < input.length; i++) sum += input[i] * input[i];
      const rms = Math.sqrt(sum / input.length);
      this.onLevel?.(rms);
      // Downsample linearly to target rate
      const ratio = nativeRate / targetRate;
      const outLen = Math.floor(input.length / ratio);
      const out = new Int16Array(outLen);
      for (let i = 0; i < outLen; i++) {
        const s = input[Math.floor(i * ratio)];
        const v = Math.max(-1, Math.min(1, s));
        out[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
      }
      // base64 encode
      const u8 = new Uint8Array(out.buffer);
      let bin = "";
      for (let i = 0; i < u8.length; i++) bin += String.fromCharCode(u8[i]);
      const b64 = btoa(bin);
      this.onChunk?.(b64);
    };
  }

  stop() {
    this.running = false;
    if (this.node) this.node.disconnect();
    if (this.source) this.source.disconnect();
    if (this.stream) this.stream.getTracks().forEach((t) => t.stop());
    if (this.ctx) this.ctx.close();
    this.ctx = null;
    this.node = null;
    this.source = null;
    this.stream = null;
  }
}
