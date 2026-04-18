import Link from "next/link";

export function Logo({ className = "" }: { className?: string }) {
  return (
    <Link
      href="/"
      className={`inline-flex items-baseline gap-1 leading-none ${className}`}
    >
      <span className="text-xl font-semibold tracking-tight text-ink">OSCE</span>
      <span className="font-hand text-2xl text-accent -ml-0.5">ai</span>
    </Link>
  );
}
