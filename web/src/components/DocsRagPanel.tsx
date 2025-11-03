// web/components/DocsRagPanel.tsx
import React, { useState } from "react";
import { uploadRagFile, uploadRagFiles, RagUploadResponse } from "../lib/toolserver";

export default function DocsRagPanel() {
  const [collection, setCollection] = useState("default");
  const [files, setFiles] = useState<FileList | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");

  async function onUpload() {
    if (!files || files.length === 0) {
      setStatus("Pick at least one file.");
      return;
    }
    setBusy(true);
    setStatus("Uploading…");

    try {
      let result: RagUploadResponse;
      if (files.length === 1) {
        result = await uploadRagFile({ file: files[0], collection });
      } else {
        result = await uploadRagFiles({ files, collection });
      }

      const total = result.total_chunks ?? 0;
      const lines = [
        `Uploaded ${result.indexed?.length ?? 0} file(s) into "${result.collection}".`,
        `Total indexed chunks: ${total}.`,
      ];

      if (result.indexed?.length) {
        lines.push(
          "",
          "Details:",
          ...result.indexed.map((it) => `• ${it.filename}: ${it.chunks} chunk(s)`)
        );
      }

      setStatus(lines.join("\n"));
    } catch (e: any) {
      setStatus(`Upload failed: ${e?.message || String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel space-y-3">
      <div className="h3 gradient-text">Docs & RAG</div>

      <div className="text-sm opacity-80">
        Upload files here. Then ask questions in the main chat with <b>“Use docs (RAG)”</b> enabled.
      </div>

      <label className="block text-sm opacity-80">Collection</label>
      <input
        className="w-[200px] rounded-md bg-black/20 px-3 py-2"
        value={collection}
        onChange={(e) => setCollection(e.target.value)}
        placeholder="default"
      />

      <label className="block text-sm opacity-80 mt-2">Files</label>
      <input
        type="file"
        multiple
        onChange={(e) => setFiles(e.target.files)}
      />

      <button
        className="mt-3 rounded-md px-4 py-2 bg-fuchsia-600 hover:bg-fuchsia-500 disabled:opacity-60"
        onClick={onUpload}
        disabled={busy || !files || files.length === 0}
      >
        {busy ? "Processing…" : "Upload & Index"}
      </button>

      {status && (
        <pre className="mt-3 text-sm whitespace-pre-wrap opacity-90">{status}</pre>
      )}
    </div>
  );
}
