// /web/src/pages/api/ollama-models.ts
import type { NextApiRequest, NextApiResponse } from "next";

type OllamaTag = { name: string; digest?: string; size?: number; modified_at?: string };
type OllamaTagsResponse = { models?: OllamaTag[] } | { message?: string };

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const base = process.env.OLLAMA_URL || "http://localhost:11434";

  try {
    const r = await fetch(`${base}/api/tags`, { method: "GET" });
    if (!r.ok) {
      const text = await r.text();
      return res.status(r.status).json({ message: `Ollama /api/tags failed: ${text}` });
    }
    const data = (await r.json()) as OllamaTagsResponse;
    const models = Array.isArray((data as any)?.models)
      ? ((data as any).models as OllamaTag[]).map(m => m.name).sort()
      : [];

    return res.status(200).json({ models });
  } catch (e: any) {
    return res.status(500).json({ message: `Failed to reach Ollama at ${base}: ${e?.message || e}` });
  }
}
