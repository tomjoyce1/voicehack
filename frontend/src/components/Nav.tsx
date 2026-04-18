import Link from "next/link";
import { Logo } from "./Logo";

export function Nav({ variant = "landing" }: { variant?: "landing" | "app" }) {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-line bg-white/80 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <Logo />
        {variant === "landing" ? (
          <nav className="flex items-center gap-6 text-sm text-ink-soft">
            <a href="#how" className="ink-underline hidden sm:inline">
              How it works
            </a>
            <a href="#stack" className="ink-underline hidden sm:inline">
              Stack
            </a>
            <a href="#problem" className="ink-underline hidden sm:inline">
              Problem
            </a>
            <Link href="/dashboard" className="btn-primary">
              Start practising
            </Link>
          </nav>
        ) : (
          <nav className="flex items-center gap-4 text-sm text-ink-soft">
            <Link href="/dashboard" className="ink-underline">
              Dashboard
            </Link>
            <span className="pill">Hackathon demo</span>
          </nav>
        )}
      </div>
    </header>
  );
}
