from fastapi import APIRouter, UploadFile, File, Form
from pydantic import BaseModel
from typing import Any, Dict
from vectorstore import query as vs_query, recent_chunks as vs_recent

router = APIRouter()

class ToolRequest(BaseModel):
    name: str
    args: Dict[str, Any] = {}

@router.get("/health")
def health():
    return {"ok": True}

@router.post("/tool")
def run_tool(req: ToolRequest):
    name = req.name
    args = req.args or {}

    if name == "rag_query":
        question   = args.get("question") or args.get("q") or ""
        k          = int(args.get("k", 5))
        collection = args.get("collection", "default")
        if not question.strip():
            return {"ok": False, "error": "missing question"}
        res = vs_query(question, k=k, collection=collection)
        # Return a simple, uniform "hits" shape the frontend expects
        hits = [{"text": r["text"], "meta": r.get("metadata", {}), "distance": r.get("distance")}
                for r in res.get("results", [])]
        return {"ok": True, "hits": hits}

    elif name == "rag_recent":
        k          = int(args.get("k", 5))
        collection = args.get("collection", "default")
        hits = vs_recent(k=k, collection=collection)  # [{"text":..., "metadata": {...}}, ...]
        hits = [{"text": h["text"], "meta": h["metadata"]} for h in hits]
        return {"ok": True, "hits": hits}

    return {"ok": False, "error": f"Unknown tool: {name}"}

@router.post("/rag/legacy-upload")
async def rag_upload(file: UploadFile = File(...), doc_id: str = Form(None)):
    content = (await file.read()).decode("utf-8", errors="ignore")
    from tools.rag import rag_upsert
    rid = doc_id or file.filename
    return rag_upsert([{"id": rid, "text": content, "metadata": {"filename": file.filename}}])
