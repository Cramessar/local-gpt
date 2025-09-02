import os, io, re, json, hashlib
from typing import List, Tuple
import pdfplumber
from docx import Document as DocxDocument
import pandas as pd

# Text split
def _split_text(text: str, chunk_size=900, overlap=150) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    chunks, i = [], 0
    while i < len(text):
        j = min(len(text), i + chunk_size)
        # try to cut on sentence boundary
        cut = text.rfind(". ", i, j)
        if cut == -1 or cut < i + 200:
            cut = j
        chunks.append(text[i:cut].strip())
        i = max(cut - overlap, cut)
    return [c for c in chunks if c]

# Extractors
def _read_pdf(path: str) -> str:
    out = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            out.append(page.extract_text() or "")
    return "\n".join(out)

def _read_docx(path: str) -> str:
    doc = DocxDocument(path)
    return "\n".join(p.text for p in doc.paragraphs)

def _read_csv_xlsx(path: str) -> str:
    if path.lower().endswith(".csv"):
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)
    # smaller textual snapshot, not the entire sheet
    head = df.head(200)
    return head.to_csv(index=False)

def extract_text(path: str) -> str:
    p = path.lower()
    if p.endswith(".pdf"):    return _read_pdf(path)
    if p.endswith(".docx"):   return _read_docx(path)
    if p.endswith(".csv") or p.endswith(".xlsx"): return _read_csv_xlsx(path)
    # fallback: plain text
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()
