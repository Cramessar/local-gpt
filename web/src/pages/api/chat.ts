import type { NextApiRequest, NextApiResponse } from "next";

type ChatMsg = { role: "system" | "user" | "assistant" | "tool"; content: string; name?: string };

const OPENAI_BASE_URL =
  process.env.OPENAI_BASE_URL || "http://vllm:8000/v1";
const OPENAI_API_KEY = process.env.OPENAI_API_KEY || "placeholder";
const OLLAMA_URL =
  process.env.OLLAMA_URL || "http://ollama:11434";
const TOOLS_URL =
  process.env.TOOLS_URL || "http://toolserver:8000";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "POST") return res.status(405).json({ error: "Method not allowed" });

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

    // Option B: pull top-k context from the toolserver and inject into messages
    let finalMessages: ChatMsg[] = messages;
    const userText = messages[messages.length - 1]?.content || "";

    if (rag && userText.trim()) {
      try {
        const params = new URLSearchParams();
        params.set("question", userText);
        params.set("k", String(ragK ?? 5));
        params.set("collection", ragCollection || "default");

        const r = await fetch(`${TOOLS_URL}/rag/ask`, {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: params.toString(),
        });

        if (r.ok) {
          const data = await r.json();
          if (Array.isArray(data?.hits) && data.hits.length) {
            const contextText = data.hits
              .map((h: any, i: number) => {
                const src = h.meta?.filename ?? h.meta?.source ?? `chunk #${i + 1}`;
                return `#${i + 1} — ${src}\n${h.text}`;
              })
              .join("\n\n");

            finalMessages = [
              { role: "system", content: "Use the provided CONTEXT when relevant. If an answer is not in the context, say so. Cite filenames if you reference context." },
              { role: "system", content: `CONTEXT START\n${contextText}\nCONTEXT END` },
              ...messages,
            ];
          }
        }
      } catch {
        // Best-effort: if RAG fails, proceed without it
      }
    }

    // Call provider
    let outMessage = { role: "assistant", content: "(no reply)" };
    let usage: any = {};
    if (provider === "ollama") {
      const r = await fetch(`${OLLAMA_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model,
          messages: finalMessages,
          stream: false,
          options: { temperature: 0.2 }
        }),
      });
      const data = await r.json();
      outMessage = data?.message ?? outMessage;
      usage = data?.eval_count
        ? { total_tokens: data.eval_count }
        : {};
    } else {
      // vLLM / OpenAI-compatible
      const r = await fetch(`${OPENAI_BASE_URL}/chat/completions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${OPENAI_API_KEY}`
        },
        body: JSON.stringify({
          model,
          messages: finalMessages,
          temperature: 0.2,
          stream: false
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
