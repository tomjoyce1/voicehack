import { NextResponse } from "next/server";

type MedRow = {
  name: string;
  dose: string;
  form: string;
  quantity: string;
  instructions: string;
};

function normalizeMeds(raw: unknown): MedRow[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((r): r is Record<string, unknown> => r !== null && typeof r === "object")
    .map((row) => ({
      name: String(row.name ?? "").trim() || "—",
      dose: String(row.dose ?? "").trim() || "—",
      form: String(row.form ?? "").trim() || "—",
      quantity: String(row.quantity ?? "").trim() || "—",
      instructions: String(row.instructions ?? "").trim() || "—",
    }));
}

export async function POST(req: Request) {
  let diagnosis = "";
  try {
    const body = await req.json();
    diagnosis = typeof body?.diagnosis === "string" ? body.diagnosis.trim() : "";
  } catch {
    return NextResponse.json({ medications: [] }, { status: 400 });
  }

  if (!diagnosis) {
    return NextResponse.json({ medications: [] });
  }

  const groqKey = process.env.GROQ_API_KEY;
  if (!groqKey) {
    return NextResponse.json({ medications: [] });
  }

  const model = process.env.GROQ_MODEL || "llama-3.3-70b-versatile";

  const prompt = `You extract medication prescribing details from a medical student's free-text diagnosis or management statement.

STUDENT TEXT:
${diagnosis}

Return ONLY valid JSON on a single line (no markdown fences) with this exact shape:
{"medications":[{"name":"","dose":"","form":"","quantity":"","instructions":""}]}

Rules:
- One object per distinct drug or product explicitly mentioned (brand or generic).
- Put stated doses/units in "dose"; otherwise empty string.
- "form": tablets, capsules, inhaler, liquid, injection, cream — infer if obvious.
- "quantity" only if a count or pack size is stated; else empty string.
- "instructions": frequency, route, PRN, or protocol phrases for that drug.
- If NO medications are mentioned, return {"medications":[]}.`;

  try {
    const resp = await fetch("https://api.groq.com/openai/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${groqKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        temperature: 0.1,
        max_tokens: 500,
        messages: [{ role: "user", content: prompt }],
      }),
    });

    if (!resp.ok) {
      return NextResponse.json({ medications: [] });
    }

    const data = (await resp.json()) as {
      choices?: { message?: { content?: string } }[];
    };
    const content = data.choices?.[0]?.message?.content?.trim();
    if (!content) {
      return NextResponse.json({ medications: [] });
    }
    const parsed = JSON.parse(content) as { medications?: unknown };
    return NextResponse.json({
      medications: normalizeMeds(parsed.medications),
    });
  } catch {
    return NextResponse.json({ medications: [] });
  }
}
