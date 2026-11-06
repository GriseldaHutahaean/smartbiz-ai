"""Indexing: embed chunks produced by ``ingestion.py`` and upsert them into a
persistent ChromaDB collection (cosine distance).

Run from the repository root with:

    uv run python scripts/indexing.py
    uv run python scripts/indexing.py --reset

``--reset`` rebuilds the named Chroma collection; it never deletes the raw
PDFs or the chunks produced by ingestion.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from ingestion import OUTPUT_DIR, load_chunks

DB_DIR = OUTPUT_DIR / "chroma_db"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION_NAME = "smartbiz_knowledge_base"
_EMBEDDING_MODEL = None


def get_embedding_model():
    """Load the embedding model once per process, reusing it for all queries."""
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        from sentence_transformers import SentenceTransformer

        _EMBEDDING_MODEL = SentenceTransformer(MODEL_NAME)
    return _EMBEDDING_MODEL


def build_vector_store(chunks: Sequence[dict] | None = None, reset: bool = False) -> dict:
    """Embed chunks and upsert them into a persistent cosine-distance collection."""
    import chromadb

    chunks = list(chunks or load_chunks())
    DB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(DB_DIR))
    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
    collection = client.get_or_create_collection(
        COLLECTION_NAME,
        metadata={"hnsw:space": "cosine", "embedding_model": MODEL_NAME},
    )
    model = get_embedding_model()
    texts = [chunk["text"] for chunk in chunks]
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True).tolist()
    collection.upsert(
        ids=[chunk["id"] for chunk in chunks],
        documents=texts,
        embeddings=embeddings,
        metadatas=[chunk["metadata"] for chunk in chunks],
    )
    return {"collection": COLLECTION_NAME, "count": collection.count(), "database": str(DB_DIR), "model": MODEL_NAME, "distance": "cosine"}


def search_collection(query: str, top_k: int = 5) -> list[dict]:
    import chromadb

    client = chromadb.PersistentClient(path=str(DB_DIR))
    collection = client.get_collection(COLLECTION_NAME)
    model = get_embedding_model()
    result = collection.query(query_embeddings=model.encode([query], normalize_embeddings=True).tolist(), n_results=top_k, include=["documents", "metadatas", "distances"])
    rows = []
    for i, (doc_id, doc, metadata, distance) in enumerate(zip(result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]), start=1):
        rows.append({"rank": i, "id": doc_id, "text": doc, "metadata": metadata, "cosine_similarity": round(1 - float(distance), 6)})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="rebuild the named Chroma collection; never deletes raw data")
    args = parser.parse_args()
    print(json.dumps(build_vector_store(reset=args.reset), indent=2))


if __name__ == "__main__":
    main()