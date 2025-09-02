import os
import uuid
import logging
from typing import List, Tuple, Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

from file_extract import extract_text_from_file  # your existing helper
from vectorstore import add_docs                 # your existing vector add

# ---------------------------
# Setup
# ---------------------------

UPLOAD_DIR = os.environ.get("FILE_SANDBOX", "/data/files")
os.makedirs(UPLOAD_DIR, exist_ok=True)

logger = logging.getLogger("rag")
if not logger.handlers:
    # Basic console logging (INFO by default)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

router = APIRouter()


# ---------------------------
# Utilities
# ---------------------------

def _clean_text(s: Optional[str]) -> str:
    if not s:
        return ""
    # Normalize newlines, strip obvious “empty” padding
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse long runs of whitespace but keep paragraph breaks
    lines = [ln.strip() for ln in s.split("\n")]
    # Keep blank lines (paragraph hints) but avoid long whitespace streaks
    return "\n".join(lines).strip()


def _chunk_text(
    text: str,
    chunk_size: int = 1200,
    overlap: int = 200,
    min_chunk_chars: int = 40,
) -> List[str]:
    """
    Greedy word/line-aware chunking with overlap.
    Ensures we only keep chunks with meaningful content.
    """
    text = _clean_text(text)
    if not text:
        return []

    chunks: List[str] = []
    n = len(text)
    start = 0

    while start < n:
        end = min(n, start + chunk_size)

        if end < n:
            # Try to cut on a newline, otherwise last space, to make nicer chunks
            cut_nl = text.rfind("\n", start, end)
            cut_sp = text.rfind(" ", start, end)
            cut = max(cut_nl, cut_sp)
            if cut != -1 and cut > start + 100:  # avoid microscopic tail chunks
                end = cut

        chunk = text[start:end].strip()
        if len(chunk) >= min_chunk_chars:
            chunks.append(chunk)

        if end >= n:
            break
        # Move with overlap
        start = max(end - overlap, 0)

        # Safety to avoid infinite loop if something goes off
        if len(chunks) > 50000:  # absurdly high guardrail
            break

    return chunks


def _save_upload_to_disk(upload: UploadFile) -> Tuple[str, str, int]:
    """
    Save the upload to /data/files (or FILE_SANDBOX), return (saved_path, safe_name, nbytes).
    """
    if not upload.filename:
        raise HTTPException(400, "Missing filename")

    safe_name = f"{uuid.uuid4().hex}_{os.path.basename(upload.filename)}"
    dest_path = os.path.join(UPLOAD_DIR, safe_name)

    # Read whole file into memory then write (fast & simple)
    # If you want streaming save for large files, switch to chunked write.
    data = upload.file.read()
    with open(dest_path, "wb") as f:
        f.write(data)

    return dest_path, safe_name, len(data)


# ---------------------------
# Routes
# ---------------------------

@router.post("/rag/upload")
async def rag_upload(
    file: UploadFile = File(..., description="Single file upload"),
    collection: str = Form("default"),
):
    """
    Upload ONE file, extract text, chunk, and index into the given collection.
    Returns detailed diagnostics so the UI can explain success/failure clearly.
    """
    # Save
    dest_path, safe_name, nbytes = _save_upload_to_disk(file)
    logger.info(f"[RAG] Saved upload -> {dest_path} ({nbytes} bytes)")

    # Extract (your helper decides which backend to use & returns meta)
    try:
        text, meta_hint = extract_text_from_file(dest_path)
    except Exception as e:
        logger.exception(f"[RAG] Extraction hard failure for {file.filename}: {e}")
        raise HTTPException(500, f"Failed to extract text: {e}")

    text = _clean_text(text)
    engine = (meta_hint or {}).get("engine")
    ext = (meta_hint or {}).get("ext")
    note = (meta_hint or {}).get("note")

    # Log a short preview to help debug "0 chunks" scenarios
    preview = (text[:300] + "…") if text and len(text) > 300 else (text or "")
    logger.info(
        f"[RAG] Extracted from '{file.filename}' via {engine or 'unknown'} "
        f"(ext={ext}, note={note}) | chars={len(text)} | preview={preview!r}"
    )

    info = {
        "filename": file.filename,
        "saved_as": safe_name,
        "bytes": nbytes,
        "ext": ext,
        "engine": engine,
        "note": note,
        "chars_extracted": len(text or ""),
    }

    # If no text -> short-circuit with a very explicit message
    if not text:
        message = (
            "No extractable text found. If this is a scanned PDF, enable OCR or upload a text-based version. "
            "DOCX files must contain real text (not images)."
        )
        logger.warning(f"[RAG] Empty text for '{file.filename}'. {message}")
        return JSONResponse(
            {
                "ok": False,
                "indexed": [{"filename": file.filename, "chunks": 0, "info": info}],
                "total_chunks": 0,
                "message": message,
            },
            status_code=200,
        )

    # Chunk
    chunks = _chunk_text(text)
    if not chunks:
        message = (
            "Text was extracted but chunking produced 0 chunks. "
            "This can happen when the document only has very short lines or heavy non-text content."
        )
        logger.warning(f"[RAG] 0 chunks after chunking for '{file.filename}'.")
        return JSONResponse(
            {
                "ok": False,
                "indexed": [{"filename": file.filename, "chunks": 0, "info": info}],
                "total_chunks": 0,
                "message": message,
                "preview": preview,
            },
            status_code=200,
        )

    # Index
    metadatas = [{"filename": file.filename, "chunk": i} for i in range(len(chunks))]
    try:
        added = add_docs(chunks, metadatas, collection=collection)
    except Exception as e:
        logger.exception(f"[RAG] Vector add failed for '{file.filename}': {e}")
        raise HTTPException(500, f"Failed to index chunks: {e}")

    logger.info(
        f"[RAG] Indexed {len(chunks)} chunk(s) for '{file.filename}' into collection '{collection}'."
    )

    return JSONResponse(
        {
            "ok": True,
            "indexed": [{"filename": file.filename, "chunks": len(chunks), "info": info}],
            "total_chunks": len(chunks),
            "added": added,
            "collection": collection,
            # A tiny preview helps users confirm we actually saw their doc
            "preview": preview,
        },
        status_code=200,
    )


@router.get("/rag/diag")
def rag_diag():
    """
    Lightweight diagnostic of available PDF parsers so you can see what's inside the container.
    """
    out = {"have_pymupdf": False, "have_pdfminer": False, "have_pdfplumber": False, "have_python_docx": False}
    try:
        import fitz  # PyMuPDF
        out["have_pymupdf"] = True
    except Exception:
        pass
    try:
        import pdfminer  # pdfminer.six
        out["have_pdfminer"] = True
    except Exception:
        pass
    try:
        import pdfplumber  # noqa
        out["have_pdfplumber"] = True
    except Exception:
        pass
    try:
        import docx  # python-docx
        out["have_python_docx"] = True
    except Exception:
        pass
    return out


# Optional: quick route to read back the raw file (handy while debugging)
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
    # Just dump as binary/text—only for debugging!
    return PlainTextResponse(data, media_type="application/octet-stream")
