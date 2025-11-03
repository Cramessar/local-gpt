// web/lib/toolserver.ts
const BASE =
  process.env.NEXT_PUBLIC_TOOLSERVER_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export type RagUploadResponse = {
  ok: boolean;
  collection: string;
  total_chunks: number;
  indexed: Array<{
    filename: string;
    chunks: number;
    info?: Record<string, any>;
    preview?: string;
  }>;
};

export async function uploadRagFile(opts: {
  file: File;
  collection?: string;
  signal?: AbortSignal;
}): Promise<RagUploadResponse> {
  const fd = new FormData();
  fd.append("file", opts.file); // <-- singular field the backend expects
  fd.append("collection", opts.collection ?? "default");

  const res = await fetch(`${BASE}/rag/upload`, { method: "POST", body: fd, signal: opts.signal });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
  return data as RagUploadResponse;
}

export async function uploadRagFiles(opts: {
  files: FileList | File[];
  collection?: string;
  signal?: AbortSignal;
}): Promise<RagUploadResponse> {
  const fd = new FormData();
  const arr = Array.from(opts.files as any);
  // use array field for multi
  arr.forEach((f) => fd.append("files", f));
  fd.append("collection", opts.collection ?? "default");

  const res = await fetch(`${BASE}/rag/upload`, { method: "POST", body: fd, signal: opts.signal });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
  return data as RagUploadResponse;
}

export async function ragList() {
  const r = await fetch(`${BASE}/rag/list`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function ragDiag() {
  const r = await fetch(`${BASE}/rag/diag`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
