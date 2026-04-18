import Link from "next/link";

export function Logo({ className = "" }: { className?: string }) {
  return (
    <Link
      href="/"
      className={`inline-flex items-baseline gap-0.5 leading-none transition-opacity hover:opacity-90 ${className}`}
    >
      <span className="text-xl font-semibold tracking-tight text-ink">Patient</span>
      <span className="font-hand text-2xl text-accent -ml-0.5">Sim</span>
    </Link>
  );
}
