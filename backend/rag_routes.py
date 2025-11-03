import contextlib
# backend/rag_routes.py
import os
import uuid
import logging
from typing import List, Tuple, Optional, Iterable

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from file_extract import extract_text_from_file
from vectorstore import add_docs

UPLOAD_DIR = os.environ.get("FILE_SANDBOX", "/data/files")
os.makedirs(UPLOAD_DIR, exist_ok=True)

logger = logging.getLogger("rag")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

router = APIRouter()


def _clean_text(s: Optional[str]) -> str:
    if not s:
        return ""
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.strip() for ln in s.split("\n")]
    return "\n".join(lines).strip()


def _chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200, min_chunk_chars: int = 40) -> List[str]:
    text = _clean_text(text)
    if not text:
        return []
    chunks: List[str] = []
    n = len(text)
    start = 0
    while start < n:
        end = min(n, start + chunk_size)
        if end < n:
            cut_nl = text.rfind("\n", start, end)
            cut_sp = text.rfind(" ", start, end)
            cut = max(cut_nl, cut_sp)
            if cut != -1 and cut > start + 100:
                end = cut
        chunk = text[start:end].strip()
        if len(chunk) >= min_chunk_chars:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(end - overlap, 0)
        if len(chunks) > 50000:
            break
    return chunks


async def _save_streaming(upload: UploadFile) -> Tuple[str, str, int]:
    """
    Save an UploadFile to disk in chunks. Returns (dest_path, saved_name, byte_count).
    This avoids the occasional b'' return you can get from a single .read().
    """
    if not upload.filename:
        raise HTTPException(400, "Missing filename")

    safe_name = f"{uuid.uuid4().hex}_{os.path.basename(upload.filename)}"
    dest_path = os.path.join(UPLOAD_DIR, safe_name)

    size = 0
    try:
        with open(dest_path, "wb") as out:
            while True:
                chunk = await upload.read(1024 * 1024)  # 1 MiB
                if not chunk:
                    break
                out.write(chunk)
                size += len(chunk)
    finally:
        # reset file pointer for any further processing (usually not needed, but safe)
        try:
            await upload.seek(0)
        except Exception:
            pass

    if size == 0:
        # Delete the 0-byte file so list view stays honest
        with contextlib.suppress(Exception):
            os.remove(dest_path)
        raise HTTPException(
            400,
            "Empty upload (0 bytes). Ensure the browser sent multipart/form-data with a real file.",
        )

    return dest_path, safe_name, size


@router.get("/rag/list")
def rag_list():
    items = []
    try:
        for name in sorted(os.listdir(UPLOAD_DIR)):
            path = os.path.join(UPLOAD_DIR, name)
            if os.path.isfile(path):
                try:
                    items.append({"name": name, "bytes": os.path.getsize(path)})
                except Exception:
                    items.append({"name": name, "bytes": None})
    except Exception as e:
        raise HTTPException(500, f"List failed: {e}")
    return {"dir": UPLOAD_DIR, "files": items}


@router.post("/rag/upload")
async def rag_upload(
    request: Request,
    collection: str = Form("default"),
    file: Optional[UploadFile] = File(None),
    files: Optional[List[UploadFile]] = File(None),
):
    """
    Accepts:
      - file=<UploadFile>
      - files=<UploadFile> (single)
      - files=<UploadFile>[] (multiple)
      - ANY other field name containing UploadFile(s)
    """
    # Collect UploadFile objects from declared params first…
    candidates: List[UploadFile] = []
    if file is not None:
        candidates.append(file)
    if files:
        candidates.extend([f for f in files if f is not None])

    # …then sweep the raw form in case the frontend used different field names (e.g., 'files[]')
    try:
        form = await request.form()
        for key, val in form.multi_items():
            if isinstance(val, UploadFile) and val not in candidates:
                candidates.append(val)
            # val can also be list-like, but FormData already flattens via multi_items()
    except Exception:
        pass

    if not candidates:
        raise HTTPException(400, "No file(s) provided. Use field name 'file' or 'files' (array) in multipart/form-data.")

    indexed = []
    total_chunks = 0

    for up in candidates:
        dest_path, saved_name, nbytes = await _save_streaming(up)
        logger.info(f"[RAG] Saved upload -> {dest_path} ({nbytes} bytes)")

        try:
            text, meta_hint = extract_text_from_file(dest_path)
        except Exception as e:
            logger.exception(f"[RAG] Extraction hard failure for {up.filename}: {e}")
            raise HTTPException(500, f"Failed to extract text: {e}")

        text = _clean_text(text)
        engine = (meta_hint or {}).get("engine")
        ext = (meta_hint or {}).get("ext")
        note = (meta_hint or {}).get("note")
        preview = (text[:300] + "…") if text and len(text) > 300 else (text or "")

        info = {
            "filename": up.filename,
            "saved_as": saved_name,
            "bytes": nbytes,
            "ext": ext,
            "engine": engine,
            "note": note,
            "chars_extracted": len(text or ""),
        }

        if not text:
            logger.warning(f"[RAG] Empty text for '{up.filename}'. engine={engine} ext={ext}")
            indexed.append({"filename": up.filename, "chunks": 0, "info": info, "preview": preview})
            continue

        chunks = _chunk_text(text)
        if not chunks:
            logger.warning(f"[RAG] 0 chunks after chunking for '{up.filename}'.")
            indexed.append({"filename": up.filename, "chunks": 0, "info": info, "preview": preview})
            continue

        metadatas = [{"filename": up.filename, "chunk": i} for i in range(len(chunks))]
        try:
            add_docs(chunks, metadatas, collection=collection)
        except Exception as e:
            logger.exception(f"[RAG] Vector add failed for '{up.filename}': {e}")
            raise HTTPException(500, f"Failed to index chunks: {e}")

        logger.info(f"[RAG] Indexed {len(chunks)} chunk(s) for '{up.filename}' into '{collection}'.")
        total_chunks += len(chunks)
        indexed.append({"filename": up.filename, "chunks": len(chunks), "info": info, "preview": preview})

    return JSONResponse(
        {"ok": total_chunks > 0, "indexed": indexed, "total_chunks": total_chunks, "collection": collection},
        status_code=200,
    )


@router.get("/rag/diag")
def rag_diag():
    out = {
        "have_pymupdf": False,
        "have_pdfminer": False,
        "have_pdfplumber": False,
        "have_python_docx": False,
        "have_openpyxl": False,
        "have_pytesseract": False,
        "have_tesseract_cmd": False,
    }
    try:
        import fitz; out["have_pymupdf"] = True
    except Exception: pass
    try:
        import pdfminer; out["have_pdfminer"] = True
    except Exception: pass
    try:
        import pdfplumber; out["have_pdfplumber"] = True
    except Exception: pass
    try:
        import docx; out["have_python_docx"] = True
    except Exception: pass
    try:
        import openpyxl; out["have_openpyxl"] = True
    except Exception: pass
    try:
        import pytesseract; out["have_pytesseract"] = True
    except Exception: pass
    try:
        from shutil import which
        out["have_tesseract_cmd"] = bool(which("tesseract"))
    except Exception:
        out["have_tesseract_cmd"] = False
    return out


@router.get("/rag/file/{saved_name}")
def rag_get_saved(saved_name: str):
    path = os.path.join(UPLOAD_DIR, os.path.basename(saved_name))
    if not os.path.isfile(path):
        raise HTTPException(404, "Not found")
    try:
        with open(path, "rb") as f:
            data = f.read()
    except Exception as e:
        raise HTTPException(500, f"Failed to read: {e}")
    return PlainTextResponse(data, media_type="application/octet-stream")
