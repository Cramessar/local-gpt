import { useEffect, useRef, useState } from "react";

type Sample = {
  time: string;
  cpu_percent: number;
  mem_percent: number;
  mem_total: number;
  mem_available: number;
  gpus?: Array<{
    index: number;
    name: string;
    util_percent: number;
    mem_used: number;
    mem_total: number;
  }> | null;
  vllm_ready?: boolean;
  gpu_driver?: string;
};

const BASE = process.env.NEXT_PUBLIC_TOOLSERVER_URL || "http://localhost:8000";
const SSE_URL = `${BASE}/metrics/sse`;

function prettyBytes(n: number) {
  if (!n) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(n) / Math.log(k));
  return `${(n / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

export default function ResourcePanel() {
  const [latest, setLatest] = useState<Sample | null>(null);
  const [history, setHistory] = useState<Sample[]>([]);
  const [status, setStatus] = useState<"connecting" | "live" | "error">(
    "connecting"
  );
  const [errorMsg, setErrorMsg] = useState<string>("");
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    try {
      const es = new EventSource(SSE_URL, { withCredentials: false });
      esRef.current = es;

      es.onopen = () => setStatus("live");

      es.onmessage = (e) => {
        try {
          const data: Sample = JSON.parse(e.data);
          setLatest(data);
          setHistory((h) => {
            const next = [...h, data];
            return next.length > 60 ? next.slice(next.length - 60) : next;
          });
        } catch {
          /* ignore bad frames */
        }
      };

      es.onerror = () => {
        setStatus("error");
        setErrorMsg("SSE connection failed. Is the toolserver up?");
        es.close();
      };

      return () => es.close();
    } catch (err: any) {
      setStatus("error");
      setErrorMsg(err?.message || "Unknown error creating EventSource");
    }
  }, []);

  const Bar = ({ label, value }: { label: string; value: number }) => {
    const pct = Math.min(100, Math.max(0, value || 0));
    return (
      <div className="mt-8">
        <div className="meta" style={{ marginBottom: 6 }}>
          {label}: {pct.toFixed(0)}%
        </div>
        <div className="bar">
          <div className="fill" style={{ width: `${pct}%` }} />
        </div>
      </div>
    );
  };

  const pillClass =
    status === "error"
      ? "pill pill-warn"
      : latest?.vllm_ready
      ? "pill pill-ok"
      : "pill pill-muted";

  return (
    <div className="panel monitor">
      <div className="title">
        <span style={{ fontWeight: 700 }}>Resource Monitor</span>
        <span className={pillClass}>
          {latest?.vllm_ready ? "Model: ready" : "Model: warming up"}
        </span>
      </div>

      {status === "connecting" && (
        <div className="meta">Connecting…</div>
      )}
      {status === "error" && (
        <div className="meta" style={{ color: "#f59e0b" }}>
          Error: {errorMsg}
        </div>
      )}

      {status === "live" && latest && (
        <>
          <Bar label="CPU" value={latest.cpu_percent} />
          <Bar label="Memory" value={latest.mem_percent} />

          {/* GPU section */}
          {Array.isArray(latest.gpus) ? (
            <div className="mt-12">
              <div
                className="meta"
                style={{ fontWeight: 600, marginBottom: 6 }}
              >
                GPU {latest.gpu_driver ? `(Driver ${latest.gpu_driver})` : ""}
              </div>
              {latest.gpus.map((g) => (
                <div key={g.index} className="mt-8">
                  <div className="meta" style={{ marginBottom: 6 }}>
                    #{g.index} {g.name}
                  </div>
                  <Bar label="GPU Util" value={g.util_percent} />
                  <div className="meta" style={{ marginTop: 4 }}>
                    VRAM: {prettyBytes(g.mem_used)} /{" "}
                    {prettyBytes(g.mem_total)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="meta" style={{ marginTop: 8 }}>
              No GPU metrics (driver not visible in toolserver)
            </div>
          )}

          <div className="meta" style={{ marginTop: 10 }}>
            Last update: {new Date(latest.time).toLocaleTimeString()}
          </div>

          <div className="mt-12">
            <div className="meta" style={{ marginBottom: 6 }}>
              CPU (last 60s)
            </div>
            <div className="spark">
              {history.map((s, i) => (
                <div
                  key={i}
                  style={{ height: `${s.cpu_percent}%` }}
                />
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
