# backend/vectorstore.py
import os
import uuid
from typing import List, Dict, Any, Optional

import chromadb
from chromadb.utils import embedding_functions
from chromadb.config import Settings

RAG_DB_PATH = os.environ.get("RAG_DB_PATH", "/data/chroma_v2")
TELEMETRY = os.getenv("CHROMA_ANONYMIZED_TELEMETRY", "false").lower() in ("1","true","yes")

# Prefer ONNX MiniLM; fall back to SentenceTransformer if needed
try:
    EMBED_FN = embedding_functions.ONNXMiniLM_L6_V2()
except Exception:
    try:
        EMBED_FN = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
    except Exception:
        EMBED_FN = None  # last resort; will error on add/query

_client: Optional[chromadb.PersistentClient] = None
_collections: Dict[str, chromadb.api.models.Collection.Collection] = {}

def _client_once() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        os.makedirs(RAG_DB_PATH, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=RAG_DB_PATH,
            settings=Settings(anonymized_telemetry=TELEMETRY),
        )
    return _client

def _get_collection(name: str):
    if name in _collections:
        return _collections[name]
    col = _client_once().get_or_create_collection(
        name=name,
        embedding_function=EMBED_FN,
        metadata={"hnsw:space": "cosine"},
    )
    _collections[name] = col
    return col

def add_docs(texts: List[str], metadatas: Optional[List[Dict[str, Any]]] = None, collection: str = "default") -> int:
    if not texts:
        return 0
    col = _get_collection(collection)
    if metadatas is None:
        metadatas = [{} for _ in texts]
    elif len(metadatas) != len(texts):
        if len(metadatas) < len(texts):
            metadatas = metadatas + [{} for _ in range(len(texts) - len(metadatas))]
        else:
            metadatas = metadatas[: len(texts)]
    ids = [str(uuid.uuid4()) for _ in texts]
    col.add(documents=texts, metadatas=metadatas, ids=ids)
    return len(texts)

def query(query_text: str, k: int = 5, collection: str = "default") -> Dict[str, Any]:
    col = _get_collection(collection)
    res = col.query(
        query_texts=[query_text],
        n_results=max(1, int(k)),
        include=["documents", "metadatas", "distances"],  # ← no "ids"
    )

    out = []
    docs  = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    for i in range(len(docs)):
        out.append({
            # no id field — Chroma didn’t return any
            "text": docs[i],
            "metadata": metas[i] if i < len(metas) else {},
            "distance": dists[i] if i < len(dists) else None,
        })
    return {"results": out, "raw": res}


def recent_chunks(k: int = 5, collection: str = "default"):
    """
    Return the first k chunks from the most recently indexed filename
    (based on appearance order) within a collection.
    """
    col = _get_collection(collection)
    items = col.get(include=["metadatas", "documents", "ids"])
    metas = items.get("metadatas", [])
    docs  = items.get("documents", [])
    if not metas or not docs:
        return []

    # Find the latest filename that appears with a non-empty value
    filenames = [m.get("filename", "") for m in metas]
    last = next((fn for fn in reversed(filenames) if fn), filenames[-1] if filenames else "")

    hits = []
    for m, d in zip(metas, docs):
        if m.get("filename") == last:
            hits.append({"text": d, "metadata": m})

    # Keep deterministic order by chunk index if present
    hits.sort(key=lambda h: h["metadata"].get("chunk", 0))
    return hits[:max(1, int(k))]