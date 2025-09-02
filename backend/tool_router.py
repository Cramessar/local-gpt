from fastapi import APIRouter, UploadFile, File, Form
from pydantic import BaseModel
from typing import Any, Dict
from tools import TOOL_REGISTRY

router = APIRouter()

class ToolRequest(BaseModel):
    name: str
    args: Dict[str, Any] = {}

@router.get("/health")
def health():
    return {"ok": True}

@router.post("/tool")
def run_tool(req: ToolRequest):
    func = TOOL_REGISTRY.get(req.name)
    if not func:
        return {"error": f"Unknown tool {req.name}"}
    try:
        return func(**(req.args or {}))
    except Exception as e:
        return {"error": str(e)}

@router.post("/rag/upload")
async def rag_upload(file: UploadFile = File(...), doc_id: str = Form(None)):
    content = (await file.read()).decode("utf-8", errors="ignore")
    from tools.rag import rag_upsert
    rid = doc_id or file.filename
    return rag_upsert([{"id": rid, "text": content, "metadata": {"filename": file.filename}}])
