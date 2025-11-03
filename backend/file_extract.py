import os
import io
from typing import Tuple, Optional

# ---------- Text helpers ----------

def _safe_decode(b: bytes) -> str:
    # Prefer utf-8, try chardet if available, fall back to latin-1
    try:
        return b.decode("utf-8", errors="ignore")
    except Exception:
        pass
    try:
        import chardet  # optional
        enc = (chardet.detect(b).get("encoding") or "utf-8")
        return b.decode(enc, errors="ignore")
    except Exception:
        return b.decode("latin-1", errors="ignore")


def _read_txt(path: str) -> str:
    with open(path, "rb") as f:
        return _safe_decode(f.read())


def _read_md(path: str) -> str:
    return _read_txt(path)


def _read_csv(path: str) -> str:
    # Keep it simple & offline: just decode file bytes (it’s already CSV text)
    return _read_txt(path)


def _read_xlsx(path: str) -> str:
    """
    Read Excel using openpyxl (no pandas). Emits a simple, row-wise text dump.
    """
    try:
        import openpyxl
    except Exception:
        return ""

    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        parts = []
        for ws in wb.worksheets:
            parts.append(f"# Sheet: {ws.title}")
            for row in ws.iter_rows(values_only=True):
                parts.append(" ".join("" if v is None else str(v) for v in row))
        return "\n".join(parts)
    except Exception:
        return ""


def _read_docx(path: str) -> str:
    try:
        import docx  # python-docx
    except Exception:
        return ""
    try:
        doc = docx.Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        return ""


# ---------- PDF helpers ----------

def _read_pdf_pymupdf(path: str) -> Tuple[str, bool, int]:
    """
    Returns (text, is_likely_scanned, pages)
    """
    try:
        import fitz  # PyMuPDF
    except Exception:
        return "", False, 0

    text = []
    scanned = False
    pages = 0

    try:
        doc = fitz.open(path)
        pages = doc.page_count
        for page in doc:
            page_text = page.get_text("text") or ""
            if not page_text.strip():
                # Heuristic: no selectable text, but page has images -> likely scanned
                try:
                    if page.get_images(full=True):
                        scanned = True
                except Exception:
                    pass
            text.append(page_text)
    except Exception:
        return "", False, pages

    return ("\n".join(text)).strip(), scanned, pages


def _read_pdf_pdfminer(path: str) -> Tuple[str, int]:
    """
    Fallback PDF extractor using pdfminer.six (pure Python).
    Returns (text, pages_guess)
    """
    try:
        from pdfminer.high_level import extract_text
    except Exception:
        return "", 0
    try:
        # pdfminer doesn't expose page count easily here; we skip it.
        return (extract_text(path) or "").strip(), 0
    except Exception:
        return "", 0


# ---------- Unified entry point ----------

def extract_text_from_file(path: str) -> Tuple[str, dict]:
    """
    Extract text and return (text, meta).
    meta = {
      "ext": ".pdf",
      "note": "...",
      "engine": "pymupdf|pdfminer|docx|xlsx|csv|text",
      "pages": int,
      "chars": int
    }
    """
    ext = os.path.splitext(path)[1].lower()
    meta = {"ext": ext, "note": "", "engine": "", "pages": 0, "chars": 0}

    # ---- Plain/structured text types
    if ext == ".txt":
        meta["engine"] = "text"
        txt = _read_txt(path)

    elif ext == ".md":
        meta["engine"] = "text"
        txt = _read_md(path)

    elif ext == ".csv":
        meta["engine"] = "csv"
        meta["note"] = "csv decoded to text"
        txt = _read_csv(path)

    elif ext in (".xlsx", ".xlsm", ".xls"):
        meta["engine"] = "xlsx"
        meta["note"] = "excel parsed to text"
        txt = _read_xlsx(path)

    elif ext == ".docx":
        meta["engine"] = "docx"
        meta["note"] = "docx parsed"
        txt = _read_docx(path)

    # ---- PDFs
    elif ext == ".pdf":
        txt, scanned, pages = _read_pdf_pymupdf(path)
        meta["engine"] = "pymupdf"
        meta["pages"] = pages
        if scanned and not txt:
            meta["note"] = "pdf likely scanned (no selectable text)"

        if not txt:
            fallback_txt, _ = _read_pdf_pdfminer(path)
            if fallback_txt:
                txt = fallback_txt
                meta["engine"] = "pdfminer"
                if not meta["note"]:
                    meta["note"] = "parsed by pdfminer (fallback)"

    else:
        # Unknown extension → try best-effort text decode
        meta["engine"] = "text"
        try:
            with open(path, "rb") as f:
                txt = _safe_decode(f.read())
            meta["note"] = "best-effort decode"
        except Exception:
            txt = ""

    txt = (txt or "").strip()
    meta["chars"] = len(txt)

    return txt, meta
