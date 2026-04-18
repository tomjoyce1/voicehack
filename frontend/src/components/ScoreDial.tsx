export function ScoreDial({
  value,
  max = 100,
  label,
  tone = "accent",
  sub,
}: {
  value: number;
  max?: number;
  label: string;
  tone?: "accent" | "coral" | "navy";
  sub?: string;
}) {
  const pct = Math.max(0, Math.min(1, value / max));
  const R = 56;
  const C = 2 * Math.PI * R;
  const dash = C * pct;
  const color = {
    accent: "#2f7a4f",
    coral: "#e26d5c",
    navy: "#1b2a4e",
  }[tone];
  return (
    <div className="flex items-center gap-5 rounded-2xl border border-line bg-white p-6">
      <svg width={140} height={140} viewBox="0 0 140 140">
        <circle
          cx="70"
          cy="70"
          r={R}
          stroke="#e7e4dc"
          strokeWidth="10"
          fill="none"
        />
        <circle
          cx="70"
          cy="70"
          r={R}
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          fill="none"
          strokeDasharray={`${dash} ${C}`}
          transform="rotate(-90 70 70)"
        />
        <text
          x="70"
          y="70"
          textAnchor="middle"
          dominantBaseline="central"
          fontSize="30"
          fontWeight="600"
          fill="#0e1726"
        >
          {Math.round(value)}
        </text>
        <text
          x="70"
          y="96"
          textAnchor="middle"
          fontSize="11"
          fill="#4a5568"
        >
          / {max}
        </text>
      </svg>
      <div>
        <p className="font-hand text-2xl" style={{ color }}>
          {label}
        </p>
        {sub && <p className="text-sm text-ink-soft">{sub}</p>}
      </div>
    </div>
  );
}
