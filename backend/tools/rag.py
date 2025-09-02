import os
from typing import List
import chromadb
from chromadb.config import Settings

DB_PATH = os.getenv("RAG_DB_PATH", "/data/chroma")
COLLECTION = "local_docs"

_client = chromadb.PersistentClient(path=DB_PATH, settings=Settings(anonymized_telemetry=False))
_coll = _client.get_or_create_collection(COLLECTION)

def rag_upsert(items: List[dict], **kwargs):
    ids = [i.get("id") for i in items]
    docs = [i.get("text") for i in items]
    metas = [i.get("metadata", {}) for i in items]
    _coll.upsert(ids=ids, documents=docs, metadatas=metas)
    return {"ok": True, "count": len(ids)}

def rag_query(query: str, k: int = 4, **kwargs):
    res = _coll.query(query_texts=[query], n_results=k)
    out = []
    for i in range(len(res["ids"][0])):
        out.append({
            "id": res["ids"][0][i],
            "text": res["documents"][0][i],
            "metadata": res["metadatas"][0][i],
            "distance": res.get("distances", [[None]])[0][i],
        })
    return {"matches": out}
