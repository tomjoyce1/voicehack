"use client";

import { useEffect, useRef } from "react";

type Props = {
  amplitude: number;
  speaking: boolean;
  tone?: "accent" | "coral";
};

export function Waveform({ amplitude, speaking, tone = "accent" }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number | null>(null);
  const tRef = useRef(0);
  const ampRef = useRef(amplitude);

  useEffect(() => {
    ampRef.current = amplitude;
  }, [amplitude]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    const DPR = Math.min(window.devicePixelRatio || 1, 2);

    const resize = () => {
      const { clientWidth: w, clientHeight: h } = canvas;
      canvas.width = w * DPR;
      canvas.height = h * DPR;
      ctx.scale(DPR, DPR);
    };
    resize();

    const color = tone === "accent" ? "#2f7a4f" : "#e26d5c";
    const bars = 72;

    const draw = () => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);

      const cx = w / 2;
      const cy = h / 2;
      const baseR = Math.max(12, Math.min(w, h) * 0.32);
      tRef.current += 0.04;
      const amp = ampRef.current;

      // Outer ring (static)
      ctx.beginPath();
      ctx.arc(cx, cy, baseR + 8, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(14,23,38,0.08)";
      ctx.lineWidth = 1;
      ctx.stroke();

      // Radial bars
      for (let i = 0; i < bars; i++) {
        const angle = (i / bars) * Math.PI * 2;
        const wave =
          Math.sin(tRef.current * 1.4 + i * 0.35) * 0.5 +
          Math.sin(tRef.current * 0.7 + i * 0.12) * 0.5;
        const idleLen = 6 + Math.abs(wave) * 3;
        const liveLen =
          14 + amp * 60 + Math.abs(Math.sin(tRef.current * 3 + i)) * amp * 40;
        const len = speaking ? liveLen : idleLen;

        const x1 = cx + Math.cos(angle) * baseR;
        const y1 = cy + Math.sin(angle) * baseR;
        const x2 = cx + Math.cos(angle) * (baseR + len);
        const y2 = cy + Math.sin(angle) * (baseR + len);

        ctx.beginPath();
        ctx.strokeStyle = speaking ? color : "rgba(14,23,38,0.35)";
        ctx.lineWidth = 2;
        ctx.lineCap = "round";
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      }

      // Inner disc
      ctx.beginPath();
      ctx.arc(cx, cy, baseR - 6, 0, Math.PI * 2);
      ctx.fillStyle = speaking ? "rgba(47,122,79,0.08)" : "rgba(14,23,38,0.03)";
      ctx.fill();

      rafRef.current = requestAnimationFrame(draw);
    };

    draw();

    const onResize = () => resize();
    window.addEventListener("resize", onResize);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      window.removeEventListener("resize", onResize);
    };
  }, [tone, speaking]);

  return (
    <canvas
      ref={canvasRef}
      className="h-full w-full"
      aria-label="patient voice waveform"
    />
  );
}
