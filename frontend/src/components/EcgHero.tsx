"use client";

export function EcgHero() {
  const path =
    "M 0 60 L 80 60 L 100 60 L 120 40 L 140 80 L 160 10 L 180 100 L 200 60 L 300 60 L 320 40 L 340 80 L 360 10 L 380 100 L 400 60 L 500 60 L 520 40 L 540 80 L 560 10 L 580 100 L 600 60 L 700 60 L 720 40 L 740 80 L 760 10 L 780 100 L 800 60 L 900 60 L 920 40 L 940 80 L 960 10 L 980 100 L 1000 60 L 1100 60 L 1120 40 L 1140 80 L 1160 10 L 1180 100 L 1200 60";

  return (
    <div className="relative h-28 w-full overflow-hidden">
      <svg
        viewBox="0 0 1200 120"
        preserveAspectRatio="none"
        className="h-full w-full"
      >
        <defs>
          <linearGradient id="fade" x1="0" x2="1">
            <stop offset="0%" stopColor="#2f7a4f" stopOpacity="0" />
            <stop offset="20%" stopColor="#2f7a4f" stopOpacity="0.9" />
            <stop offset="80%" stopColor="#2f7a4f" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#2f7a4f" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path
          d={path}
          fill="none"
          stroke="url(#fade)"
          strokeWidth="1.6"
          className="ecg-line"
        />
      </svg>
    </div>
  );
}
