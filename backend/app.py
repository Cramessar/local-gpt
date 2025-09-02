# backend/app.py
import os
import asyncio
import json
import psutil
import datetime
import contextlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

# ---- GPU metrics (optional) ---------------------------------------------------
ENABLE_GPU = os.getenv("ENABLE_GPU_METRICS", "true").lower() in ("1", "true", "yes")
try:
    if ENABLE_GPU:
        from pynvml import (
            nvmlInit, nvmlShutdown, nvmlDeviceGetCount, nvmlDeviceGetHandleByIndex,
            nvmlDeviceGetName, nvmlDeviceGetUtilizationRates,
            nvmlDeviceGetMemoryInfo, nvmlSystemGetDriverVersion
        )
        nvmlInit()
        GPU_OK = True
    else:
        GPU_OK = False
except Exception:
    GPU_OK = False

# ---- FastAPI app --------------------------------------------------------------
APP_TITLE = "Local Tool Server"
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

app = FastAPI(title=APP_TITLE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN, "http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routers AFTER app is created (include_router happens below)
from tool_router import router as tools_router  # noqa: E402
from rag_routes import router as rag_router      # noqa: E402

# ---- Helper: vLLM health ------------------------------------------------------
def _vllm_base():
    host = os.getenv("VLLM_HOST", "vllm")
    port = int(os.getenv("VLLM_PORT", "8000"))
    return f"http://{host}:{port}"

async def _check_vllm_ready(timeout=0.8):
    try:
        import aiohttp  # ensure present in requirements
    except Exception:
        return False, None
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as s:
            async with s.get(f"{_vllm_base()}/health") as r:
                if r.status == 200:
                    try:
                        j = await r.json()
                    except Exception:
                        j = None
                    return True, j
    except Exception:
        pass
    return False, None

# ---- Basic routes -------------------------------------------------------------
@app.get("/")
def root():
    return {"ok": True, "service": APP_TITLE}

@app.get("/health")
async def health():
    ready, _ = await _check_vllm_ready()
    return JSONResponse({"ok": True, "vllm_ready": bool(ready)})

# ---- Resource Monitor: SSE (CPU/Mem + optional GPU) ---------------------------
@app.get("/metrics/sse")
async def metrics_sse():
    async def event_stream():
        psutil.cpu_percent(interval=0.2)  # prime measurement
        last_heartbeat = datetime.datetime.now()
        gpu_driver = None
        if GPU_OK:
            try:
                drv = nvmlSystemGetDriverVersion()
                gpu_driver = drv.decode() if hasattr(drv, "decode") else drv
            except Exception:
                gpu_driver = None

        while True:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            payload = {
                "time": datetime.datetime.now().isoformat(),
                "cpu_percent": cpu,
                "mem_percent": mem.percent,
                "mem_total": mem.total,
                "mem_available": mem.available,
            }

            if GPU_OK:
                try:
                    gcount = nvmlDeviceGetCount()
                    gpus = []
                    for i in range(gcount):
                        h = nvmlDeviceGetHandleByIndex(i)
                        name = nvmlDeviceGetName(h)
                        util = nvmlDeviceGetUtilizationRates(h)
                        m = nvmlDeviceGetMemoryInfo(h)
                        gpus.append({
                            "index": i,
                            "name": name.decode() if hasattr(name, "decode") else str(name),
                            "util_percent": int(util.gpu),
                            "mem_used": int(m.used),
                            "mem_total": int(m.total),
                        })
                    payload["gpus"] = gpus
                    if gpu_driver:
                        payload["gpu_driver"] = gpu_driver
                except Exception:
                    payload["gpus"] = None

            # include vLLM readiness hint every ~5s
            if int(datetime.datetime.now().timestamp()) % 5 == 0:
                ready, _ = await _check_vllm_ready(timeout=0.5)
                payload["vllm_ready"] = bool(ready)

            yield f"data: {json.dumps(payload)}\n\n"

            # heartbeat for proxies
            now = datetime.datetime.now()
            if (now - last_heartbeat).total_seconds() > 15:
                yield ": keep-alive\n\n"
                last_heartbeat = now

            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

# ---- Routers (include AFTER app is created) -----------------------------------
app.include_router(tools_router)
app.include_router(rag_router)

# ---- Cleanup ------------------------------------------------------------------
@app.on_event("shutdown")
def _shutdown_nvml():
    if GPU_OK:
        with contextlib.suppress(Exception):
            nvmlShutdown()
