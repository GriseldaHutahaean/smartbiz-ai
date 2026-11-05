"""Fast tests for deterministic ingestion/chunking behavior."""

from vector_pipeline import chunk_text_with_overlap, clean_text


def test_clean_text_preserves_paragraphs_and_repairs_hyphenated_lines():
    raw = "Judul-\nlanjutan\n\nParagraf kedua.\n\nHalaman ini sengaja dikosongkan\n\n12"
    cleaned = clean_text(raw)
    assert "Judullanjutan" in cleaned
    assert "Halaman ini sengaja dikosongkan" not in cleaned
    assert "\n\n" in cleaned


def test_chunking_is_word_aware_and_has_required_metadata():
    text = "Paragraf pertama berisi prosedur pembelian.\n\nParagraf kedua berisi prosedur stok dan persediaan." * 5
    chunks = chunk_text_with_overlap(text, "contoh.pdf", chunk_size=120, chunk_overlap=20)
    assert len(chunks) > 1
    assert all(chunk["text"] == chunk["text"].strip() for chunk in chunks)
    assert all(not chunk["text"].startswith(" ") and not chunk["text"].endswith(" ") for chunk in chunks)
    assert all(chunk["metadata"]["source_file"] == "contoh.pdf" for chunk in chunks)
    assert all(chunk["metadata"]["character_length"] == len(chunk["text"]) for chunk in chunks)
    assert [chunk["metadata"]["chunk_index"] for chunk in chunks] == list(range(len(chunks)))
