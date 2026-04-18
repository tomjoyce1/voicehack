type Tone = "accent" | "coral" | "gold" | "navy";

export function BiomarkerPill({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: Tone;
}) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  const toneClasses = {
    accent: "text-accent",
    coral: "text-coral",
    gold: "text-gold",
    navy: "text-navy",
  }[tone];
  const bgClasses = {
    accent: "bg-accent",
    coral: "bg-coral",
    gold: "bg-gold",
    navy: "bg-navy",
  }[tone];
  return (
    <div className="flex min-w-[170px] items-center gap-3 rounded-full border border-line bg-white px-4 py-2">
      <span className={`text-xs font-medium ${toneClasses}`}>{label}</span>
      <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-paper-2">
        <span
          className={`block h-full ${bgClasses} transition-[width] duration-500`}
          style={{ width: `${clamped}%` }}
        />
      </span>
      <span className="text-xs font-semibold text-ink">{clamped}</span>
    </div>
  );
}
