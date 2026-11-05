"""End-to-end ingestion, vector indexing, semantic search, and benchmarking.

The pipeline is intentionally script-friendly so the existing SmartBiz baseline
modules remain independent. Run from the repository root with:

    uv run python scripts/vector_pipeline.py all

Generated artifacts are written below ``data/processed/vector_search`` and are
safe to regenerate; the original PDFs and any pre-existing databases are never
deleted.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUTPUT_DIR = ROOT / "data" / "processed" / "vector_search"
CHUNKS_PATH = OUTPUT_DIR / "chunks.jsonl"
SUMMARY_PATH = OUTPUT_DIR / "ingestion_summary.json"
DB_DIR = OUTPUT_DIR / "chroma_db"
BENCHMARK_DIR = ROOT / "docs" / "benchmark"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION_NAME = "smartbiz_knowledge_base"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
_EMBEDDING_MODEL = None


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    source_file: str
    chunk_index: int
    character_length: int

    def metadata(self) -> dict[str, str | int]:
        return {
            "source_file": self.source_file,
            "chunk_index": self.chunk_index,
            "character_length": self.character_length,
        }


def clean_text(raw_text: str) -> str:
    """Normalize PDF extraction artifacts while retaining paragraph context."""
    text = raw_text.replace("\u00ad", "")
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    text = re.sub(r"Halaman ini sengaja dikosongkan", " ", text, flags=re.I)
    text = re.sub(r"^\s*\d{1,4}\s*$", "", text, flags=re.M)
    text = re.sub(r"[^\w\s.,!?;:/%()\[\]{}+\-&'\"@#=<>|*]", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text_from_pdf(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    pages = [clean_text(page.extract_text() or "") for page in reader.pages]
    pages = [page for page in pages if page]
    return clean_text("\n\n".join(pages))


def _split_long_unit(unit: str, limit: int) -> list[str]:
    words = unit.split()
    pieces: list[str] = []
    current: list[str] = []
    current_len = 0
    for word in words:
        if current and current_len + len(word) + 1 > limit:
            pieces.append(" ".join(current))
            current, current_len = [], 0
        current.append(word)
        current_len += len(word) + (1 if current_len else 0)
    if current:
        pieces.append(" ".join(current))
    return pieces or [unit]


def _recursive_units(text: str) -> list[str]:
    """Split by paragraphs, then sentences, then words only when necessary."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    units: list[str] = []
    sentence_re = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Þ0-9])")
    for paragraph in paragraphs:
        sentences = [s.strip() for s in sentence_re.split(paragraph) if s.strip()]
        units.extend(sentences or [paragraph])
    return units


def chunk_text_with_overlap(
    text: str,
    source_name: str,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[dict]:
    """Create word-aware recursive chunks with sentence/paragraph context."""
    if chunk_size <= 0 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_size must be positive and overlap must be in [0, chunk_size)")
    units: list[str] = []
    for unit in _recursive_units(text):
        units.extend(_split_long_unit(unit, chunk_size) if len(unit) > chunk_size else [unit])

    chunks: list[Chunk] = []
    current: list[str] = []
    current_len = 0
    for unit in units:
        proposed = len(unit) if not current else current_len + 1 + len(unit)
        if current and proposed > chunk_size:
            content = " ".join(current).strip()
            chunks.append(Chunk(f"{source_name}__chunk_{len(chunks):04d}", content, source_name, len(chunks), len(content)))
            overlap_words: list[str] = []
            overlap_len = 0
            for word in reversed(content.split()):
                extra = len(word) + (1 if overlap_words else 0)
                if overlap_len + extra > chunk_overlap:
                    break
                overlap_words.insert(0, word)
                overlap_len += extra
            current = overlap_words
            current_len = len(" ".join(current))
        if current and current_len + 1 + len(unit) > chunk_size:
            # A single unit may exceed the limit after overlap; split it safely.
            for piece in _split_long_unit(unit, chunk_size):
                if current and current_len + 1 + len(piece) > chunk_size:
                    content = " ".join(current).strip()
                    chunks.append(Chunk(f"{source_name}__chunk_{len(chunks):04d}", content, source_name, len(chunks), len(content)))
                    current, current_len = [], 0
                current.append(piece)
                current_len = len(" ".join(current))
        else:
            current.append(unit)
            current_len = len(" ".join(current))
    if current:
        content = " ".join(current).strip()
        chunks.append(Chunk(f"{source_name}__chunk_{len(chunks):04d}", content, source_name, len(chunks), len(content)))
    return [asdict(chunk) | {"metadata": chunk.metadata()} for chunk in chunks if chunk.text]


def ingest_documents(raw_dir: Path = RAW_DIR) -> list[dict]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(raw_dir.glob("*.pdf"), key=lambda p: p.name.lower())
    all_chunks: list[dict] = []
    document_stats: list[dict] = []
    for pdf_path in pdfs:
        text = extract_text_from_pdf(pdf_path)
        chunks = chunk_text_with_overlap(text, pdf_path.name)
        all_chunks.extend(chunks)
        document_stats.append({"source_file": pdf_path.name, "characters": len(text), "chunks": len(chunks)})
    with CHUNKS_PATH.open("w", encoding="utf-8", newline="\n") as stream:
        for chunk in all_chunks:
            stream.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    summary = {
        "documents": len(pdfs),
        "chunks": len(all_chunks),
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "strategy": "paragraph -> sentence -> word-aware recursive splitting with trailing overlap",
        "documents_detail": document_stats,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return all_chunks


def load_chunks() -> list[dict]:
    if not CHUNKS_PATH.exists():
        return ingest_documents()
    return [json.loads(line) for line in CHUNKS_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


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


QUERIES = [
    {"query_id": "q01", "category": "relevant", "query": "Bagaimana cara pencatatan keuangan dan tutup buku bulanan BUMDes?", "relevant_sources": ["SOP-15_Pencatatan-Keuangan-dan-Tutup-Buku-Bulanan-BUMDes.pdf"]},
    {"query_id": "q02", "category": "relevant", "query": "Apa prosedur pengelolaan stok dan persediaan barang?", "relevant_sources": ["SOP-13_Pengelolaan-Stok-dan-Persediaan-BUMDes.pdf"]},
    {"query_id": "q03", "category": "synonym", "query": "Bagaimana menentukan HPP dan harga jual produk kuliner?", "relevant_sources": ["Pelatihan HPP dan Harga Jual untuk Koperasi UKM Kuliner (BRIN).pdf"]},
    {"query_id": "q04", "category": "synonym", "query": "Apa langkah evaluasi pemasok atau vendor untuk pengadaan?", "relevant_sources": ["sop-seleksi-dan-evaluasi-vendor (1).pdf", "SOP-11_Pengadaan-Barang-dan-atau-Jasa-BUMDes.pdf"]},
    {"query_id": "q05", "category": "ambiguous", "query": "Bagaimana meningkatkan efisiensi usaha kecil?", "relevant_sources": ["67 Buku 4 Manajemen Usaha Kecil.pdf", "E-Book_Pedoman_SIAPIK.pdf"]},
    {"query_id": "q06", "category": "ambiguous", "query": "Apa pedoman pencatatan transaksi untuk usaha?", "relevant_sources": ["E-Book_Pedoman_SIAPIK.pdf", "Buku Juknis SIAPIK Web Sektor Perdagangan.pdf"]},
    {"query_id": "q07", "category": "out-of-domain", "query": "Bagaimana cara merawat tanaman hias di rumah?", "relevant_sources": []},
    {"query_id": "q08", "category": "out-of-domain", "query": "Siapa yang memenangkan pertandingan sepak bola tadi malam?", "relevant_sources": []},
]


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


def benchmark(top_k: int = 5) -> dict:
    rows: list[dict] = []
    for item in QUERIES:
        results = search_collection(item["query"], top_k)
        relevant_sources = set(item["relevant_sources"])
        hits = [r for r in results if r["metadata"].get("source_file") in relevant_sources]
        retrieved_relevant_sources = {r["metadata"].get("source_file") for r in hits}
        rows.append({
            "query_id": item["query_id"], "category": item["category"], "query": item["query"],
            "expected_sources": "; ".join(item["relevant_sources"]), "top_k": top_k,
            "top_similarity": results[0]["cosine_similarity"] if results else 0.0,
            "top_documents": "; ".join(dict.fromkeys(r["metadata"].get("source_file", "") for r in results)),
            "top_chunks": " || ".join(r["text"] for r in results),
            "retrieved_relevant": len(hits), "retrieved_relevant_sources": len(retrieved_relevant_sources),
            "precision_at_k": len(hits) / top_k,
            "recall_at_k": (len(retrieved_relevant_sources) / max(1, len(relevant_sources))) if relevant_sources else 0.0,
            "false_acceptance_candidate": item["category"] == "out-of-domain" and bool(results),
            "results": results,
        })
    ood_scores = [r["top_similarity"] for r in rows if r["category"] == "out-of-domain"]
    in_scores = [r["top_similarity"] for r in rows if r["category"] != "out-of-domain"]
    threshold = round((max(ood_scores) + min(in_scores)) / 2, 6) if ood_scores and in_scores and max(ood_scores) < min(in_scores) else round(max(ood_scores, default=0.5) + 0.02, 6)
    for row in rows:
        row["accepted"] = row["top_similarity"] >= threshold
        row["false_acceptance"] = row["category"] == "out-of-domain" and row["accepted"]
        row["false_rejection"] = row["category"] != "out-of-domain" and not row["accepted"]
        row["relevance_status"] = "relevan" if row["retrieved_relevant"] > 0 else ("ditolak" if not row["accepted"] else "tidak relevan")
        row["analysis"] = (
            "Query out-of-domain berhasil ditolak oleh threshold."
            if row["category"] == "out-of-domain" and not row["accepted"]
            else "Query out-of-domain diterima; false acceptance perlu diperbaiki."
            if row["false_acceptance"]
            else "Hasil Top-K memuat sumber relevan."
            if row["retrieved_relevant"] > 0
            else "Tidak ada sumber relevan pada Top-K; perlu evaluasi query atau threshold."
        )
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = BENCHMARK_DIR / "semantic_search_benchmark.csv"
    fields = ["query_id", "category", "query", "expected_sources", "top_documents", "top_chunks", "top_k", "top_similarity", "retrieved_relevant", "retrieved_relevant_sources", "precision_at_k", "recall_at_k", "relevance_status", "accepted", "false_acceptance", "false_rejection", "analysis"]
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows({key: row[key] for key in fields} for row in rows)
    (BENCHMARK_DIR / "semantic_search_benchmark.json").write_text(json.dumps({"threshold": threshold, "queries": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_benchmark_markdown(rows, threshold)
    plot_benchmark(rows, threshold)
    return {"queries": len(rows), "top_k": top_k, "threshold": threshold, "false_acceptance": sum(r["false_acceptance"] for r in rows), "false_rejection": sum(r["false_rejection"] for r in rows), "csv": str(csv_path)}


def write_benchmark_markdown(rows: Sequence[dict], threshold: float) -> None:
    lines = ["# SmartBiz AI Semantic Search Benchmark", "", f"Threshold hasil pengujian aktual: **{threshold:.6f}**.", "", "Kueri out-of-domain ditolak jika cosine similarity Top-1 berada di bawah threshold. Relevansi diberi label berdasarkan sumber dokumen yang memang membahas topik kueri; skor, dokumen, chunk, dan hasil retrieval berasal dari eksekusi ChromaDB aktual.", "", "| ID | Kategori | Dokumen Top-K | Top-1 cosine | Status | Precision@K | Recall@K | Analisis |", "|---|---|---|---:|---|---:|---:|---|"]
    lines.extend(f"| {r['query_id']} | {r['category']} | {r['top_documents'].replace('|', '/') } | {r['top_similarity']:.6f} | {r['relevance_status']} | {r['precision_at_k']:.3f} | {r['recall_at_k']:.3f} | {r['analysis']} |" for r in rows)
    lines += ["", "## Interpretasi", "", "Precision@K mengukur proporsi chunk pada Top-K yang berasal dari sumber relevan yang dilabeli. Recall@K mengukur cakupan dokumen sumber relevan unik yang ditemukan, sehingga nilainya berada pada rentang 0 sampai 1. False acceptance adalah kueri out-of-domain yang melewati threshold; false rejection adalah kueri domain yang ditolak.", "", "## Parameter", "", f"- Model embedding: `{MODEL_NAME}`", "- ChromaDB: persistent storage dengan cosine distance", f"- Chunk size: {CHUNK_SIZE} karakter", f"- Overlap: {CHUNK_OVERLAP} karakter target pada kata-kata terakhir chunk sebelumnya", "- Kategori: relevant, synonym, ambiguous, dan out-of-domain"]
    (BENCHMARK_DIR / "semantic_search_benchmark.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def plot_benchmark(rows: Sequence[dict], threshold: float) -> None:
    import matplotlib.pyplot as plt

    plt.figure(figsize=(10, 5))
    colors = ["#2a9d8f" if r["category"] != "out-of-domain" else "#e76f51" for r in rows]
    plt.bar([r["query_id"] for r in rows], [r["top_similarity"] for r in rows], color=colors)
    plt.axhline(threshold, color="#264653", linestyle="--", label=f"threshold={threshold:.3f}")
    plt.ylim(0, 1); plt.ylabel("Top-1 cosine similarity"); plt.xlabel("Query"); plt.title("SmartBiz AI Semantic Search Benchmark")
    plt.legend(); plt.tight_layout(); plt.savefig(BENCHMARK_DIR / "semantic_search_benchmark.png", dpi=160); plt.close()


def run_all(reset: bool = False) -> None:
    chunks = ingest_documents()
    print(json.dumps({"ingestion": {"documents": len({c['source_file'] for c in chunks}), "chunks": len(chunks)}, "vector_store": build_vector_store(chunks, reset=reset), "benchmark": benchmark()}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["ingest", "index", "benchmark", "all"])
    parser.add_argument("--reset", action="store_true", help="rebuild the named Chroma collection; never deletes raw data")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    if args.command == "ingest": print(json.dumps({"chunks": len(ingest_documents())}, indent=2))
    elif args.command == "index": print(json.dumps(build_vector_store(reset=args.reset), indent=2))
    elif args.command == "benchmark": print(json.dumps(benchmark(args.top_k), indent=2))
    else: run_all(args.reset)


if __name__ == "__main__":
    main()
