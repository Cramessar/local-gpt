# backend/chunking.py
import os

def split_into_chunks(text: str) -> list[str]:
    size = int(os.getenv("CHUNK_SIZE", 800))
    overlap = int(os.getenv("CHUNK_OVERLAP", 120))
    text = (text or "").replace("\x00", " ").strip()
    parts, i, n = [], 0, len(text)
    step = max(size - overlap, 1)
    while i < n:
        parts.append(text[i:i+size])
        i += step
    # keep only meaningful chunks (very small filter)
    return [p for p in parts if len(p.strip()) >= 20]
