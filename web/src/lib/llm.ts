type Msg = { role: "system"|"user"|"assistant"|"tool"; content: string; name?: string };

const OLLAMA_URL      = process.env.OLLAMA_URL      || "http://localhost:11434";
const OPENAI_BASE_URL = process.env.OPENAI_BASE_URL || "http://localhost:8001/v1";  // host fallback
const OPENAI_API_KEY  = process.env.OPENAI_API_KEY  || "none";

export type Provider = "ollama" | "openai";

export type LLMResult = {
  message: { content: string };
  usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
  latencyMs: number;
  raw?: any;
};

async function parseJsonOrThrow(res: Response) {
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    // Make errors readable in the chat instead of crashing with "<!DOCTYPE...>"
    throw new Error(`Backend returned non-JSON (status ${res.status}): ${text.slice(0,200)}`);
  }
}

export async function callLLM(messages: Msg[], provider: Provider, model: string): Promise<LLMResult> {
  const t0 = performance.now();

  if (provider === "ollama") {
    const res = await fetch(`${OLLAMA_URL}/api/chat`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ model, messages, stream: false, options: { temperature: 0.7 } })
    });
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`Ollama error ${res.status}: ${body.slice(0,200)}`);
    }
    const data = await parseJsonOrThrow(res);
    const t1 = performance.now();

    const usage = (data?.eval_count || data?.prompt_eval_count) ? {
      prompt_tokens: data?.prompt_eval_count,
      completion_tokens: data?.eval_count,
      total_tokens: (data?.prompt_eval_count || 0) + (data?.eval_count || 0),
    } : undefined;

    return {
      message: { content: data?.message?.content ?? "" },
      usage,
      latencyMs: Math.round(t1 - t0),
      raw: data
    };
  } else {
    // OpenAI-compatible
    const res = await fetch(`${OPENAI_BASE_URL}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${OPENAI_API_KEY}`
      },
      body: JSON.stringify({ model, messages, temperature: 0.7, stream: false })
    });
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`OpenAI-compatible error ${res.status}: ${body.slice(0,200)}`);
    }
    const data = await parseJsonOrThrow(res);
    const t1 = performance.now();
    const content = data?.choices?.[0]?.message?.content ?? "";
    const usage = data?.usage; // {prompt_tokens, completion_tokens, total_tokens}
    return { message: { content }, usage, latencyMs: Math.round(t1 - t0), raw: data };
  }
}
