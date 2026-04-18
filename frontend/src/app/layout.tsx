import type { Metadata } from "next";
import { Inter, Caveat } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const caveat = Caveat({
  subsets: ["latin"],
  variable: "--font-caveat",
  display: "swap",
});

export const metadata: Metadata = {
  title: "OSCEai — Practice OSCEs with an AI patient",
  description:
    "AI standardised patients for medical students. Practice OSCE exams with voice-first AI, clinical scoring, and objective biometric feedback on your delivery.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${inter.variable} ${caveat.variable} font-sans bg-white text-ink antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
