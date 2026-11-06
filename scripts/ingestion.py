"""Ingestion: extract PDFs under ``data/raw``, clean the text, and split it
into word-aware overlapping chunks ready for embedding.

Run from the repository root with:

    uv run python scripts/ingestion.py

Generated artifacts are written below ``data/processed/vector_search`` and are
safe to regenerate; the original PDFs are never deleted.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUTPUT_DIR = ROOT / "data" / "processed" / "vector_search"
CHUNKS_PATH = OUTPUT_DIR / "chunks.jsonl"
SUMMARY_PATH = OUTPUT_DIR / "ingestion_summary.json"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


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
    text = re.sub(r"Halaman ini sengaja dikosongkan", " ", text, flags=re.I)
    text = re.sub(r"^\s*\d{1,4}\s*$", "", text, flags=re.M)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    chunks = ingest_documents()
    print(json.dumps({
        "documents": len({c["source_file"] for c in chunks}),
        "chunks": len(chunks),
        "chunks_file": str(CHUNKS_PATH),
        "summary_file": str(SUMMARY_PATH),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()