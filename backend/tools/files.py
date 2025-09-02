import os
from pathlib import Path

SANDBOX = Path(os.getenv("FILE_SANDBOX", "/data/files"))
SANDBOX.mkdir(parents=True, exist_ok=True)

def _safe(p: str) -> Path:
    target = (SANDBOX / p).resolve()
    if not str(target).startswith(str(SANDBOX.resolve())):
        raise ValueError("Path escapes sandbox")
    return target

def list_files(subpath: str = ".", **kwargs):
    base = _safe(subpath)
    out = []
    for item in base.glob("**/*"):
        if item.is_file():
            out.append(str(item.relative_to(SANDBOX)))
    return {"files": out}

def read_file(path: str, **kwargs):
    p = _safe(path)
    return {"path": path, "content": p.read_text(encoding="utf-8")}

def write_file(path: str, content: str, **kwargs):
    p = _safe(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"ok": True, "path": path, "bytes": len(content.encode("utf-8"))}
