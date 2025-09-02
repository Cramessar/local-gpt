import { useState } from "react";

const BASE = process.env.NEXT_PUBLIC_TOOLSERVER_URL || "http://localhost:8000";

type UploadSummary = {
  indexed?: Array<{ filename: string; chunks: number }>;
  total_chunks?: number;
  [k: string]: any;
};

export default function DocTools() {
  const [files, setFiles] = useState<FileList | null>(null);
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<string | null>(null);
  const [collection, setCollection] = useState("default");

  async function upload() {
    if (!files || files.length === 0) return;

    setBusy(true);
    setAnswer(null);

    let totalChunks = 0;
    const details: string[] = [];

    try {
      // Upload each file as `file` (singular). Most FastAPI examples expect this.
      for (const f of Array.from(files)) {
        const form = new FormData();
        form.append("file", f);                 // <-- key renamed to `file`
        form.append("collection", collection);  // optional; backend can default to "default"

        const res = await fetch(`${BASE}/rag/upload`, { method: "POST", body: form });
        const text = await res.text();
        if (!res.ok) throw new Error(text || `HTTP ${res.status}`);

        let data: UploadSummary = {};
        try { data = JSON.parse(text); } catch { /* some servers return text */ }

        // Try to read a few common shapes
        const fileChunks =
          (Array.isArray(data.indexed) && data.indexed.reduce((s: number, it: any) => s + (it?.chunks || 0), 0)) ||
          (typeof data.total_chunks === "number" ? data.total_chunks : 0);

        totalChunks += fileChunks;

        // Friendly line item
        const name = (data?.indexed?.[0]?.filename) || f.name;
        details.push(`${name}: ${fileChunks} chunk(s)`);
      }

      const lines = [
        `Uploaded ${Array.from(files).length} file(s) into "${collection}".`,
        `Total indexed chunks: ${totalChunks}.`,
        details.length ? `\nDetails:\n• ${details.join("\n• ")}` : ""
      ].join("\n");

      setAnswer(lines + `\n\nNow ask questions in the main chat with “Use docs (RAG)” enabled.`);
    } catch (e: any) {
      setAnswer(`Upload failed: ${e?.message || e}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="h3 gradient-text">Docs & RAG</div>

      <div className="meta" style={{ opacity: .85 }}>
        Upload files here. Then ask questions in the main chat with
        <b> “Use docs (RAG)”</b> enabled.
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <span className="meta">Collection</span>
        <input
          className="input"
          style={{ width: 160 }}
          value={collection}
          onChange={(e)=>setCollection(e.target.value)}
          placeholder="default"
        />
      </div>

      <div>
        <input type="file" multiple onChange={(e)=>setFiles(e.target.files)} className="input" />
        <div className="mt-8" />
        <button
          onClick={upload}
          className="btn btn-primary"
          disabled={busy || !files || files.length===0}
          style={{ opacity: busy || !files ? .6 : 1 }}
        >
          {busy ? "Processing…" : "Upload & Index"}
        </button>
      </div>

      {answer && (
        <div className="chat-bubble assistant" style={{ marginTop: 8 }}>
          <div className="meta" style={{ fontWeight: 700, marginBottom: 4 }}>Status</div>
          <div style={{ whiteSpace: "pre-wrap" }}>{answer}</div>
        </div>
      )}
    </div>
  );
}
