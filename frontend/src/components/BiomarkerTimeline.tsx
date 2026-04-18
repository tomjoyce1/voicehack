"use client";

import { useEffect, useRef } from "react";

type Series = { name: string; color: string; values: number[] };

export function BiomarkerTimeline({ series }: { series: Series[] }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    const DPR = Math.min(window.devicePixelRatio || 1, 2);

    const render = () => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      canvas.width = w * DPR;
      canvas.height = h * DPR;
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
      ctx.clearRect(0, 0, w, h);

      const pad = { l: 28, r: 16, t: 16, b: 28 };
      const plotW = w - pad.l - pad.r;
      const plotH = h - pad.t - pad.b;

      ctx.strokeStyle = "#e7e4dc";
      ctx.lineWidth = 1;
      for (let i = 0; i <= 4; i++) {
        const y = pad.t + (plotH / 4) * i;
        ctx.beginPath();
        ctx.moveTo(pad.l, y);
        ctx.lineTo(pad.l + plotW, y);
        ctx.stroke();
        ctx.fillStyle = "#4a5568";
        ctx.font = "10px Inter, sans-serif";
        ctx.textAlign = "right";
        ctx.fillText(String(100 - i * 25), pad.l - 6, y + 3);
      }

      const n = Math.max(...series.map((s) => s.values.length), 2);
      for (const s of series) {
        ctx.beginPath();
        ctx.strokeStyle = s.color;
        ctx.lineWidth = 2;
        s.values.forEach((v, i) => {
          const x = pad.l + (plotW * i) / (n - 1);
          const y = pad.t + plotH * (1 - Math.max(0, Math.min(100, v)) / 100);
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.stroke();

        // Dot at end
        const lastI = s.values.length - 1;
        const lastV = s.values[lastI];
        const x = pad.l + (plotW * lastI) / (n - 1);
        const y = pad.t + plotH * (1 - Math.max(0, Math.min(100, lastV)) / 100);
        ctx.beginPath();
        ctx.fillStyle = s.color;
        ctx.arc(x, y, 3, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.fillStyle = "#4a5568";
      ctx.textAlign = "left";
      ctx.font = "10px Inter, sans-serif";
      ctx.fillText("start", pad.l, h - 8);
      ctx.textAlign = "right";
      ctx.fillText("diagnosis", pad.l + plotW, h - 8);
    };

    render();
    const obs = new ResizeObserver(render);
    obs.observe(canvas);
    return () => obs.disconnect();
  }, [series]);

  return (
    <div className="rounded-2xl border border-line bg-white p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-medium text-ink">Delivery timeline</h3>
        <div className="flex flex-wrap gap-3 text-xs">
          {series.map((s) => (
            <span key={s.name} className="inline-flex items-center gap-1.5">
              <span
                className="h-2 w-2 rounded-full"
                style={{ background: s.color }}
              />
              <span className="text-ink-soft">{s.name}</span>
            </span>
          ))}
        </div>
      </div>
      <canvas ref={ref} className="h-48 w-full" />
    </div>
  );
}
