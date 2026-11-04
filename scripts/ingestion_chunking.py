# ==============================================================================
# TUGAS 3 - MILESTONE 3: SMARTBIZ AI (KELOMPOK 9)
# Modul: Ekstraksi, Pembersihan, dan Chunking Dokumen SOP (Poin 2 & 3)
# ==============================================================================

import os  # Modul bawaan Python untuk mengelola file dan path direktori
import re  # Modul Regular Expression bawaan Python untuk pembersihan pola teks
from pypdf import PdfReader  # Library pembaca konten teks dari file PDF


def clean_text(raw_text: str) -> str:
    """Fungsi Poin 2: Membersihkan teks mentah hasil ekstraksi PDF.
    
    Menghapus karakter aneh, nomor halaman mandiri, teks kosong berlebih,
    dan kalimat boilerplate seperti 'Halaman ini sengaja dikosongkan'.
    """
    # 1. Menghapus teks umum dokumen kosong yang sering muncul di PDF resmi
    cleaned = re.sub(r"Halaman ini sengaja dikosongkan", "", raw_text, flags=re.IGNORECASE)

    # 2. Menghapus karakter non-standar/aneh (tetap izinkan huruf, angka, tanda baca biasa)
    cleaned = re.sub(r"[^\w\s.,!?:;\-\(\)/%]", " ", cleaned)

    # 3. Menghapus baris yang hanya berisi angka saja (nomor halaman terpisah)
    cleaned = re.sub(r"^\s*\d+\s*$", "", cleaned, flags=re.MULTILINE)

    # 4. Mengubah spasi berlebih menjadi satu spasi tunggal
    cleaned = re.sub(r"[ \t]+", " ", cleaned)

    # 5. Merapikan baris kosong berlebih (maksimal 2 enter)
    cleaned = re.sub(r"\n\s*\n+", "\n\n", cleaned)

    # 6. Membersihkan spasi di awal dan akhir dokumen
    return cleaned.strip()


def extract_text_from_pdf(pdf_path: str) -> str:
    """Fungsi Poin 2: Membuka file PDF dan mengekstrak seluruh teks halamannya."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"File tidak ditemukan di: {pdf_path}")

    reader = PdfReader(pdf_path)
    all_pages_text = []

    # Membaca per halaman
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            all_pages_text.append(page_text)

    # Gabungkan teks seluruh halaman lalu bersihkan
    combined_raw_text = "\n".join(all_pages_text)
    return clean_text(combined_raw_text)


def chunk_text_with_overlap(
    text: str,
    source_name: str,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
) -> list[dict]:
    """Fungsi Poin 3: Memotong teks panjang menjadi chunks terstruktur dengan overlap.
    
    Menjamin 'word-aware' di awal dan akhir potongan sehingga tidak membelah kata.
    """
    chunks = []
    start_index = 0
    total_length = len(text)
    chunk_counter = 1

    while start_index < total_length:
        end_index = start_index + chunk_size

        # Word-aware pada batas akhir: cari spasi terdekat sebelum batas potongan
        if end_index < total_length:
            next_space = text.rfind(" ", start_index, end_index)
            if next_space != -1 and next_space > start_index:
                end_index = next_space

        chunk_content = text[start_index:end_index].strip()

        if chunk_content:
            chunks.append(
                {
                    "chunk_id": f"{source_name}_chunk_{chunk_counter}",
                    "text": chunk_content,
                    "metadata": {
                        "source_file": source_name,
                        "chunk_index": chunk_counter,
                        "character_length": len(chunk_content),
                    },
                }
            )
            chunk_counter += 1

        # Geser posisi awal mundur sebesar overlap
        next_start = end_index - chunk_overlap

        # Word-aware pada batas awal overlap: cari spasi terdekat agar tidak memenggal kata
        if next_start > 0 and next_start < total_length:
            space_pos = text.find(" ", next_start)
            if space_pos != -1 and space_pos < end_index:
                next_start = space_pos + 1

        # Mencegah loop tak terhingga jika pergeseran tidak maju
        if next_start <= start_index:
            next_start = end_index

        start_index = next_start

    return chunks


def process_all_documents(raw_folder_path: str) -> list[dict]:
    """Fungsi Pembungkus: Membaca seluruh file PDF di folder data/raw
    dan mengembalikan seluruh chunks dari semua dokumen.
    """
    all_chunks = []
    # Ambil semua file yang berakhiran .pdf di folder raw
    pdf_files = [f for f in os.listdir(raw_folder_path) if f.lower().endswith(".pdf")]

    print(f"\nMemulai pemrosesan total {len(pdf_files)} dokumen PDF...")

    for file_name in pdf_files:
        full_path = os.path.join(raw_folder_path, file_name)
        try:
            # Ekstrak dan bersihkan teks (Poin 2)
            cleaned_text = extract_text_from_pdf(full_path)
            # Potong teks dengan overlap (Poin 3)
            doc_chunks = chunk_text_with_overlap(cleaned_text, source_name=file_name)
            all_chunks.extend(doc_chunks)
            print(f"  -> Selesai: {file_name} ({len(doc_chunks)} chunks)")
        except Exception as err:
            print(f"  [X] Gagal membaca {file_name}: {err}")

    return all_chunks


# ==============================================================================
# PENGUJIAN MANDIRI POIN 2 & 3
# ==============================================================================
if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, ".."))
    raw_folder = os.path.join(project_root, "data", "raw")

    print("==================================================")
    print("DEMO PENGUJIAN PIPELINE INGESTION & CHUNKING")
    print("==================================================")

    # Menjalankan pemrosesan ke seluruh 15 dokumen PDF
    total_chunks = process_all_documents(raw_folder)

    print("\n==================================================")
    print(f"[SUKSES TOTAL] Berhasil memproses semua dokumen!")
    print(f"Total keseluruhan chunks siap indeks: {len(total_chunks)} potongan.")
    print("==================================================")