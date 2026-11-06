"""Backward-compatible entry point for SmartBiz document ingestion.

The implementation lives in :mod:`vector_pipeline` so the same cleaning and
word-aware recursive chunking logic is used by ingestion, indexing, and search.
"""

from pathlib import Path

from vector_pipeline import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    clean_text,
    chunk_text_with_overlap,
    extract_text_from_pdf as _extract_text_from_pdf,
    ingest_documents,
)


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract and clean one PDF using the shared pipeline implementation."""
    return _extract_text_from_pdf(Path(pdf_path))


def process_all_documents(raw_folder_path: str) -> list[dict]:
    """Process all PDFs and persist the shared chunk artifact."""
    return ingest_documents(Path(raw_folder_path))


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    chunks = process_all_documents(str(project_root / "data" / "raw"))
    print(
        f"Processed {len({chunk['source_file'] for chunk in chunks})} PDFs into {len(chunks)} chunks."
    )
    print(f"Parameters: chunk_size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP}")
