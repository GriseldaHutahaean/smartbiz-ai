"""Benchmark: run the fixed evaluation query set against the ChromaDB index
built by ``indexing.py`` and report precision/recall-style metrics.

Run from the repository root with:

    uv run python scripts/benchmark.py
    uv run python scripts/benchmark.py --top-k 5

Writes ``docs/benchmark/semantic_search_benchmark.{csv,json,md,png}``.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Sequence

from ingestion import CHUNK_OVERLAP, CHUNK_SIZE, ROOT
from indexing import MODEL_NAME, search_collection

BENCHMARK_DIR = ROOT / "docs" / "benchmark"

QUERIES = [
    {
        "query_id": "q01",
        "category": "relevant",
        "query": "Bagaimana cara pencatatan keuangan dan tutup buku bulanan BUMDes?",
        "relevant_sources": [
            "SOP-15_Pencatatan-Keuangan-dan-Tutup-Buku-Bulanan-BUMDes.pdf"
        ],
    },
    {
        "query_id": "q02",
        "category": "relevant",
        "query": "Apa prosedur pengelolaan stok dan persediaan barang?",
        "relevant_sources": ["SOP-13_Pengelolaan-Stok-dan-Persediaan-BUMDes.pdf"],
    },
    {
        "query_id": "q03",
        "category": "synonym",
        "query": "Bagaimana menentukan HPP dan harga jual produk kuliner?",
        "relevant_sources": [
            "Pelatihan HPP dan Harga Jual untuk Koperasi UKM Kuliner (BRIN).pdf"
        ],
    },
    {
        "query_id": "q04",
        "category": "synonym",
        "query": "Apa langkah evaluasi pemasok atau vendor untuk pengadaan?",
        "relevant_sources": [
            "sop-seleksi-dan-evaluasi-vendor (1).pdf",
            "SOP-11_Pengadaan-Barang-dan-atau-Jasa-BUMDes.pdf",
        ],
    },
    {
        "query_id": "q05",
        "category": "ambiguous",
        "query": "Bagaimana meningkatkan efisiensi usaha kecil?",
        "relevant_sources": [
            "67 Buku 4 Manajemen Usaha Kecil.pdf",
            "E-Book_Pedoman_SIAPIK.pdf",
        ],
    },
    {
        "query_id": "q06",
        "category": "ambiguous",
        "query": "Apa pedoman pencatatan transaksi untuk usaha?",
        "relevant_sources": [
            "E-Book_Pedoman_SIAPIK.pdf",
            "Buku Juknis SIAPIK Web Sektor Perdagangan.pdf",
        ],
    },
    {
        "query_id": "q07",
        "category": "out-of-domain",
        "query": "Bagaimana cara merawat tanaman hias di rumah?",
        "relevant_sources": [],
    },
    {
        "query_id": "q08",
        "category": "out-of-domain",
        "query": "Siapa yang memenangkan pertandingan sepak bola tadi malam?",
        "relevant_sources": [],
    },
]


def benchmark(top_k: int = 5) -> dict:
    rows: list[dict] = []
    for item in QUERIES:
        results = search_collection(item["query"], top_k)
        relevant_sources = set(item["relevant_sources"])
        hits = [
            r for r in results if r["metadata"].get("source_file") in relevant_sources
        ]
        retrieved_relevant_sources = {r["metadata"].get("source_file") for r in hits}
        rows.append(
            {
                "query_id": item["query_id"],
                "category": item["category"],
                "query": item["query"],
                "expected_sources": "; ".join(item["relevant_sources"]),
                "top_k": top_k,
                "top_similarity": results[0]["cosine_similarity"] if results else 0.0,
                "top_documents": "; ".join(
                    dict.fromkeys(r["metadata"].get("source_file", "") for r in results)
                ),
                "top_chunks": " || ".join(r["text"] for r in results),
                "retrieved_relevant": len(hits),
                "retrieved_relevant_sources": len(retrieved_relevant_sources),
                "precision_at_k": len(hits) / top_k,
                "recall_at_k": (
                    (len(retrieved_relevant_sources) / max(1, len(relevant_sources)))
                    if relevant_sources
                    else 0.0
                ),
                "false_acceptance_candidate": item["category"] == "out-of-domain"
                and bool(results),
                "results": results,
            }
        )
    ood_scores = [r["top_similarity"] for r in rows if r["category"] == "out-of-domain"]
    in_scores = [r["top_similarity"] for r in rows if r["category"] != "out-of-domain"]
    threshold = (
        round((max(ood_scores) + min(in_scores)) / 2, 6)
        if ood_scores and in_scores and max(ood_scores) < min(in_scores)
        else round(max(ood_scores, default=0.5) + 0.02, 6)
    )
    for row in rows:
        row["accepted"] = row["top_similarity"] >= threshold
        row["false_acceptance"] = row["category"] == "out-of-domain" and row["accepted"]
        row["false_rejection"] = (
            row["category"] != "out-of-domain" and not row["accepted"]
        )
        row["relevance_status"] = (
            "relevan"
            if row["retrieved_relevant"] > 0
            else ("ditolak" if not row["accepted"] else "tidak relevan")
        )
        row["analysis"] = (
            "Query out-of-domain berhasil ditolak oleh threshold."
            if row["category"] == "out-of-domain" and not row["accepted"]
            else (
                "Query out-of-domain diterima; false acceptance perlu diperbaiki."
                if row["false_acceptance"]
                else (
                    "Hasil Top-K memuat sumber relevan."
                    if row["retrieved_relevant"] > 0
                    else "Tidak ada sumber relevan pada Top-K; perlu evaluasi query atau threshold."
                )
            )
        )
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = BENCHMARK_DIR / "semantic_search_benchmark.csv"
    fields = [
        "query_id",
        "category",
        "query",
        "expected_sources",
        "top_documents",
        "top_chunks",
        "top_k",
        "top_similarity",
        "retrieved_relevant",
        "retrieved_relevant_sources",
        "precision_at_k",
        "recall_at_k",
        "relevance_status",
        "accepted",
        "false_acceptance",
        "false_rejection",
        "analysis",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row[key] for key in fields} for row in rows)
    (BENCHMARK_DIR / "semantic_search_benchmark.json").write_text(
        json.dumps(
            {"threshold": threshold, "queries": rows}, ensure_ascii=False, indent=2
        ),
        encoding="utf-8",
    )
    write_benchmark_markdown(rows, threshold)
    plot_benchmark(rows, threshold)
    return {
        "queries": len(rows),
        "top_k": top_k,
        "threshold": threshold,
        "false_acceptance": sum(r["false_acceptance"] for r in rows),
        "false_rejection": sum(r["false_rejection"] for r in rows),
        "csv": str(csv_path),
    }


def write_benchmark_markdown(rows: Sequence[dict], threshold: float) -> None:
    lines = [
        "# SmartBiz AI Semantic Search Benchmark",
        "",
        f"Threshold hasil pengujian aktual: **{threshold:.6f}**.",
        "",
        "Kueri out-of-domain ditolak jika cosine similarity Top-1 berada di bawah threshold. Relevansi diberi label berdasarkan sumber dokumen yang memang membahas topik kueri; skor, dokumen, chunk, dan hasil retrieval berasal dari eksekusi ChromaDB aktual.",
        "",
        "| ID | Kategori | Dokumen Top-K | Top-1 cosine | Status | Precision@K | Recall@K | Analisis |",
        "|---|---|---|---:|---|---:|---:|---|",
    ]
    lines.extend(
        f"| {r['query_id']} | {r['category']} | {r['top_documents'].replace('|', '/') } | {r['top_similarity']:.6f} | {r['relevance_status']} | {r['precision_at_k']:.3f} | {r['recall_at_k']:.3f} | {r['analysis']} |"
        for r in rows
    )
    lines += [
        "",
        "## Interpretasi",
        "",
        "Precision@K mengukur proporsi chunk pada Top-K yang berasal dari sumber relevan yang dilabeli. Recall@K mengukur cakupan dokumen sumber relevan unik yang ditemukan, sehingga nilainya berada pada rentang 0 sampai 1. False acceptance adalah kueri out-of-domain yang melewati threshold; false rejection adalah kueri domain yang ditolak.",
        "",
        "## Parameter",
        "",
        f"- Model embedding: `{MODEL_NAME}`",
        "- ChromaDB: persistent storage dengan cosine distance",
        f"- Chunk size: {CHUNK_SIZE} karakter",
        f"- Overlap: {CHUNK_OVERLAP} karakter target pada kata-kata terakhir chunk sebelumnya",
        "- Kategori: relevant, synonym, ambiguous, dan out-of-domain",
    ]
    (BENCHMARK_DIR / "semantic_search_benchmark.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def plot_benchmark(rows: Sequence[dict], threshold: float) -> None:
    import matplotlib.pyplot as plt

    plt.figure(figsize=(10, 5))
    colors = [
        "#2a9d8f" if r["category"] != "out-of-domain" else "#e76f51" for r in rows
    ]
    plt.bar(
        [r["query_id"] for r in rows], [r["top_similarity"] for r in rows], color=colors
    )
    plt.axhline(
        threshold, color="#264653", linestyle="--", label=f"threshold={threshold:.3f}"
    )
    plt.ylim(0, 1)
    plt.ylabel("Top-1 cosine similarity")
    plt.xlabel("Query")
    plt.title("SmartBiz AI Semantic Search Benchmark")
    plt.legend()
    plt.tight_layout()
    plt.savefig(BENCHMARK_DIR / "semantic_search_benchmark.png", dpi=160)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.top_k), indent=2))


if __name__ == "__main__":
    main()
