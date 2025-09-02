import os
from typing import Tuple

# ---------- Plain text helpers ----------

def _read_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def _read_md(path: str) -> str:
    return _read_txt(path)

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

def _read_csv(path: str) -> str:
    try:
        import pandas as pd
    except Exception:
        return ""
    try:
        df = pd.read_csv(path)
        return df.to_csv(index=False)
    except Exception:
        return ""

def _read_xlsx(path: str) -> str:
    try:
        import pandas as pd
    except Exception:
        return ""
    try:
        xls = pd.read_excel(path, sheet_name=None)
        parts = []
        for name, df in xls.items():
            parts.append(f"# Sheet: {name}\n")
            parts.append(df.to_csv(index=False))
        return "\n".join(parts)
    except Exception:
        return ""

# ---------- PDF helpers ----------

def _read_pdf_pymupdf(path: str) -> Tuple[str, bool]:
    """
    Returns (text, is_likely_scanned).
    """
    try:
        import fitz  # PyMuPDF
    except Exception:
        return "", False

    text = ""
    scanned = False
    try:
        doc = fitz.open(path)
        for page in doc:
            page_text = page.get_text("text") or ""
            text += page_text + "\n"
            if not page_text.strip():
                # no text; if images exist, likely scanned
                if page.get_images(full=True):
                    scanned = True
    except Exception:
        return "", False

    return text.strip(), scanned

def _read_pdf_pdfminer(path: str) -> str:
    """
    Fallback pure-Python extractor for tricky PDFs.
    """
    try:
        from pdfminer.high_level import extract_text
    except Exception:
        return ""
    try:
        return (extract_text(path) or "").strip()
    except Exception:
        return ""

# ---------- Unified entry point ----------

def extract_text_from_file(path: str) -> Tuple[str, dict]:
    """
    Extract text and return (text, meta).
    meta = {"ext": ".pdf", "note": "...", "engine": "pymupdf|pdfminer|plain"}
    """
    ext = os.path.splitext(path)[1].lower()
    meta = {"ext": ext, "note": "", "engine": ""}

    if ext == ".txt":
        meta["engine"] = "plain"
        txt = _read_txt(path)

    elif ext == ".md":
        meta["engine"] = "plain"
        txt = _read_md(path)

    elif ext == ".docx":
        meta["engine"] = "python-docx"
        meta["note"] = "docx parsed"
        txt = _read_docx(path)

    elif ext == ".csv":
        meta["engine"] = "pandas"
        meta["note"] = "csv parsed to text"
        txt = _read_csv(path)

    elif ext in (".xlsx", ".xlsm", ".xls"):
        meta["engine"] = "pandas"
        meta["note"] = "excel parsed to text"
        txt = _read_xlsx(path)

    elif ext == ".pdf":
        # Try PyMuPDF first
        txt, scanned = _read_pdf_pymupdf(path)
        meta["engine"] = "pymupdf"
        if scanned and not txt:
            meta["note"] = "pdf likely scanned (no selectable text)"

        # Fallback to pdfminer if empty
        if not txt:
            fallback = _read_pdf_pdfminer(path)
            if fallback:
                txt = fallback
                meta["engine"] = "pdfminer"
                if not meta["note"]:
                    meta["note"] = "parsed by pdfminer (fallback)"

    else:
        txt = ""

    return (txt or "").strip(), meta
