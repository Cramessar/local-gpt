import os
from typing import List, Dict, Any, Optional

import chromadb
from chromadb.config import Settings

from embeddings import embed_texts

_DB_PATH = os.getenv("RAG_DB_PATH", "/data/chroma")
_COLL = "localgpt_docs"

# Read telemetry/reset flags from env so code & env always agree.
# Only set fields that matter; let the rest use Chroma defaults to reduce mismatch surface.
_ANON = os.getenv("CHROMA_ANONYMIZED_TELEMETRY", "false").lower() in ("1", "true", "yes")
_ALLOW_RESET = os.getenv("CHROMA_ALLOW_RESET", "true").lower() in ("1", "true", "yes")

_client: Optional[chromadb.api.client.ClientAPI] = None
_coll = None

def _get_client():
    global _client
    if _client is not None:
        return _client
    settings = Settings(
        is_persistent=True,
        anonymized_telemetry=_ANON,
        allow_reset=_ALLOW_RESET,
        # Note: no other Settings fields to keep parity with env defaults
    )
    # Lazy init; if an old instance was created with different settings, change the path
    # OR wipe the old dir/volume before retrying.
    _client = chromadb.PersistentClient(path=_DB_PATH, settings=settings)
    return _client

def _get_collection():
    global _coll
    if _coll is not None:
        return _coll
    client = _get_client()
    _coll = client.get_or_create_collection(_COLL)
    return _coll

def add_docs(chunks: List[Dict[str, Any]]) -> int:
    coll = _get_collection()
    ids = [c["id"] for c in chunks]
    docs = [c["text"] for c in chunks]
    metas= [c.get("meta", {}) for c in chunks]
    embeds = embed_texts(docs)
    coll.add(ids=ids, documents=docs, metadatas=metas, embeddings=embeds)
    return len(docs)

def query(text: str, k=5):
    coll = _get_collection()
    qembed = embed_texts([text])[0]
    res = coll.query(query_embeddings=[qembed], n_results=k)
    docs = res.get("documents", [[]])[0]
    metas= res.get("metadatas", [[]])[0]
    return [{"text": d, "meta": m} for d, m in zip(docs, metas)]
