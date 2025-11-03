// pages/api/chat.ts
import type { NextApiRequest, NextApiResponse } from "next";

type ChatMsg = {
  role: "system" | "user" | "assistant" | "tool";
  content: string;
  name?: string;
};

const OPENAI_BASE_URL = process.env.OPENAI_BASE_URL || "http://vllm:8000/v1";
const OPENAI_API_KEY  = process.env.OPENAI_API_KEY  || "placeholder";
const OLLAMA_URL      = process.env.OLLAMA_URL      || "http://ollama:11434";
const TOOLS_URL       = process.env.TOOLS_URL       || "http://toolserver:8000";

/**
 * Ask the toolserver for RAG hits.
 * Preferred: POST /tool { name: "rag_query", args: { question, k, collection } }
 * Fallback:  POST /rag/ask (x-www-form-urlencoded) — only if you later expose it.
 */
async function getRagHits(params: { question: string; k: number; collection: string }) {
  // Preferred path: /tool
  try {
    const r = await fetch(`${TOOLS_URL}/tool`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: "rag_query",
        args: {
          question: params.question,
          k: params.k,
          collection: params.collection,
        },
      }),
    });
    if (r.ok) {
      const data = await r.json();
      if (Array.isArray(data?.hits)) return data.hits;      // normalized by tool_router
      if (Array.isArray(data?.results)) return data.results; // some versions return results
    }
  } catch {
    // ignore and try fallback
  }

  // Legacy fallback: /rag/ask (optional)
  try {
    const usp = new URLSearchParams();
    usp.set("question", params.question);
    usp.set("k", String(params.k));
    usp.set("collection", params.collection);

    const r = await fetch(`${TOOLS_URL}/rag/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: usp.toString(),
    });
    if (r.ok) {
      const data = await r.json();
      if (Array.isArray(data?.hits)) return data.hits;
    }
  } catch {
    // ignore
  }

  return [];
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const t0 = Date.now();

  try {
    const { messages, provider, model, rag, ragCollection, ragK } = req.body as {
      messages: ChatMsg[];
      provider: "ollama" | "openai";
      model: string;
      rag?: boolean;
      ragCollection?: string;
      ragK?: number;
    };

    if (!Array.isArray(messages) || !messages.length) {
      return res.status(400).json({ error: "Missing messages" });
    }

    // ----- RAG: fetch context and inject as system messages -----
    let finalMessages: ChatMsg[] = messages;
    const userText = messages[messages.length - 1]?.content || "";

    if (rag && userText.trim()) {
      try {
        const hits = await getRagHits({
          question: userText,
          k: Math.max(1, Math.min(50, ragK ?? 5)),
          collection: ragCollection || "default",
        });

        if (hits.length) {
          const contextText = hits
            .map((h: any, i: number) => {
              const src =
                h?.meta?.filename ??
                h?.metadata?.filename ?? // some backends call it metadata
                h?.meta?.source ??
                `chunk #${i + 1}`;
              const txt = (h?.text ?? h?.document ?? h)?.toString?.() ?? "";
              return `#${i + 1} — ${src}\n${txt}`;
            })
            .join("\n\n");

          finalMessages = [
            {
              role: "system",
              content:
                "Use the provided CONTEXT when relevant. If an answer is not in the context, say so. " +
                "Cite filenames if you reference context.",
            },
            { role: "system", content: `CONTEXT START\n${contextText}\nCONTEXT END` },
            ...messages,
          ];
        }
      } catch {
        // Best-effort; continue without RAG if toolserver query fails
      }
    }

    // ----- Call provider -----
    let outMessage: ChatMsg = { role: "assistant", content: "(no reply)" };
    let usage: any = {};

    if (provider === "ollama") {
      const r = await fetch(`${OLLAMA_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model,
          messages: finalMessages,
          stream: false,
          options: { temperature: 0.2 },
        }),
      });
      const data = await r.json();
      outMessage = data?.message ?? outMessage;
      usage = data?.eval_count ? { total_tokens: data.eval_count } : {};
    } else {
      const r = await fetch(`${OPENAI_BASE_URL}/chat/completions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${OPENAI_API_KEY}`,
        },
        body: JSON.stringify({
          model,
          messages: finalMessages,
          temperature: 0.2,
          stream: false,
        }),
      });
      const data = await r.json();
      outMessage = data?.choices?.[0]?.message ?? outMessage;
      usage = data?.usage ?? {};
    }

    const latencyMs = Date.now() - t0;
    return res.status(200).json({ message: outMessage, usage, latencyMs });
  } catch (e: any) {
    const latencyMs = Date.now() - t0;
    return res.status(500).json({ error: e?.message || String(e), latencyMs });
  }
}
