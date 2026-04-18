import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: {
          DEFAULT: "#ffffff",
          2: "#fafaf7",
        },
        ink: {
          DEFAULT: "#0e1726",
          soft: "#4a5568",
        },
        line: "#e7e4dc",
        accent: {
          DEFAULT: "#2f7a4f",
          soft: "#e6f1eb",
        },
        coral: "#e26d5c",
        navy: "#1b2a4e",
        gold: "#d4a24c",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui"],
        hand: ["var(--font-caveat)", "cursive"],
      },
      boxShadow: {
        soft: "0 1px 0 rgba(14,23,38,0.04), 0 8px 24px -12px rgba(14,23,38,0.12)",
      },
    },
  },
  plugins: [],
};
export default config;
