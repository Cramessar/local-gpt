import { useEffect, useRef, useState } from "react";
import ResourcePanel from "../components/ResourcePanel";
import DocTools from "../components/DocTools";

type ChatMsg = { role: "system" | "user" | "assistant" | "tool"; content: string; name?: string };

const DEFAULT_PROVIDER: "ollama" | "openai" = "openai";
const DEFAULT_MODEL = "openai/gpt-oss-20b";

export default function Home() {
  const [messages, setMessages] = useState<ChatMsg[]>([
    { role: "system", content: "You are LocalGPT." }
  ]);
  const [input, setInput] = useState("");
  const [provider, setProvider] = useState<"ollama" | "openai">(DEFAULT_PROVIDER);
  const [model, setModel] = useState(DEFAULT_MODEL);
  const [isSending, setIsSending] = useState(false);
  const [stats, setStats] = useState<{ latencyMs?: number; tokens?: number }>({});
  const scrollRef = useRef<HTMLDivElement>(null);

  // RAG controls
  const [useDocs, setUseDocs] = useState(true);
  const [ragCollection, setRagCollection] = useState("default");
  const [ragK, setRagK] = useState(5);

  async function send() {
    const text = input.trim();
    if (!text || isSending) return;
    setIsSending(true);

    const nextMsgs: ChatMsg[] = [...messages, { role: "user", content: text }];
    setMessages(nextMsgs);
    setInput("");

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: nextMsgs,
          provider,
          model,
          rag: useDocs,
          ragCollection,
          ragK
        })
      });
      const data = await res.json();
      const content = data?.message?.content ?? "(no reply)";
      const totalTokens = data?.usage?.total_tokens
        ?? (data?.usage?.prompt_tokens || 0) + (data?.usage?.completion_tokens || 0);
      setStats({ latencyMs: data?.latencyMs, tokens: totalTokens });
      setMessages(m => [...m, { role: "assistant", content }]);
    } catch (e: any) {
      setMessages(m => [...m, { role: "assistant", content: `⚠️ Error: ${e?.message || e}` }]);
    } finally {
      setIsSending(false);
      setTimeout(() => scrollRef.current?.scrollTo({ top: 1e9, behavior: "smooth" }), 0);
    }
  }

  function onKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  const visibleMsgs = messages.filter(m => m.role !== "system");

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: 16 }}>
      <h1 className="gradient-text" style={{ fontSize: 32, fontWeight: 800, marginBottom: 12 }}>Local GPT</h1>

      <div className="panel" style={{ padding: 10, marginBottom: 12 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <label className="meta">Provider:</label>
          <select
            value={provider}
            onChange={e => setProvider(e.target.value as any)}
            className="input"
            style={{ width: 240 }}
          >
            <option value="openai">OpenAI-compatible (vLLM)</option>
            <option value="ollama">Ollama</option>
          </select>

          <label className="meta" style={{ marginLeft: 8 }}>Model:</label>
          <input
            value={model}
            onChange={e => setModel(e.target.value)}
            placeholder={provider === "openai" ? "openai/gpt-oss-20b" : "llama3.1"}
            className="input"
            style={{ flex: 1, minWidth: 280 }}
          />

          <div className="meta" style={{ marginLeft: "auto" }}>
            {stats.latencyMs != null && <>Latency: {stats.latencyMs}ms&nbsp;•&nbsp;</>}
            {stats.tokens != null && <>Tokens: {stats.tokens}</>}
          </div>
        </div>

        {/* RAG controls */}
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8, flexWrap: "wrap" }}>
          <label className="meta" style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input
              type="checkbox"
              checked={useDocs}
              onChange={e => setUseDocs(e.target.checked)}
            />
            Use docs (RAG)
          </label>
          {useDocs && (
            <>
              <input
                className="input"
                style={{ width: 160 }}
                value={ragCollection}
                onChange={(e) => setRagCollection(e.target.value)}
                placeholder="collection"
              />
              <input
                className="input"
                style={{ width: 80 }}
                type="number"
                min={1}
                max={10}
                value={ragK}
                onChange={(e) => setRagK(parseInt(e.target.value || "5"))}
                placeholder="k"
              />
              <span className="meta" style={{ opacity: .8 }}>
                (Upload docs in the sidebar; context is auto-injected)
              </span>
            </>
          )}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 16 }}>
        {/* Chat column */}
        <div className="panel" style={{ padding: 0 }}>
          <div
            ref={scrollRef}
            style={{
              height: "65vh",
              padding: 12,
              overflowY: "auto",
            }}
          >
            {visibleMsgs.length === 0 ? (
              <div className="meta">No messages yet. Type below and press Enter.</div>
            ) : (
              visibleMsgs.map((m, i) => (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    justifyContent: m.role === "user" ? "flex-end" : "flex-start",
                    margin: "10px 0"
                  }}
                >
                  <div
                    className={m.role === "user" ? "chat-bubble user" : "chat-bubble assistant"}
                    style={{ maxWidth: "80%" }}
                  >
                    <div className="meta" style={{ fontWeight: 600, marginBottom: 4 }}>
                      {m.role === "user" ? "You" : m.role === "assistant" ? "Assistant" : m.role}
                    </div>
                    <div style={{ whiteSpace: "pre-wrap" }}>{m.content}</div>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Input row */}
          <div style={{ display: "flex", gap: 8, padding: 12, borderTop: "1px solid rgba(255,255,255,0.06)" }}>
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={onKey}
              placeholder="Type a message… (Enter to send)"
              className="input"
              style={{ flex: 1 }}
            />
            <button
              onClick={send}
              disabled={isSending || !input.trim()}
              className="btn btn-primary"
              style={{ opacity: isSending || !input.trim() ? .6 : 1 }}
            >
              {isSending ? "Sending…" : "Send"}
            </button>
          </div>
        </div>

        {/* Right column: Monitor + Docs */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <ResourcePanel />
          <DocTools /> {/* Upload panel (no ask button now) */}
        </div>
      </div>
    </div>
  );
}
