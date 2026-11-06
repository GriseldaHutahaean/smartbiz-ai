"""
Script bukti Raw vs Cleaned untuk subbab 3.1.1.

PENEMPATAN:
    Taruh file ini di dalam folder "evidence" yang berada SATU LEVEL
    dengan folder "scripts" dan "data" di repo kamu, contoh:

    C:\\Users\\Asus\\OneDrive\\Dokumen\\GitHub\\smartbiz-ai\\
        scripts\\
            vector_pipeline.py
        data\\
            raw\\
                Pedoman Teknis Manufaktur.pdf
                SOP-11_Pengadaan-Barang-dan-atau-Jasa-BUMDes.pdf
                ...
        evidence\\
            make_evidence.py   <-- file ini

CARA MENJALANKAN (PowerShell, dari root repo smartbiz-ai):
    mkdir evidence              # kalau foldernya belum ada
    # salin/paste file ini ke dalam folder evidence/
    cd evidence
    python make_evidence.py

Jika strukturmu berbeda, cukup ubah variabel SCRIPTS_DIR dan RAW_DIR
di bawah supaya menunjuk ke lokasi scripts/vector_pipeline.py dan
data/raw/ yang sebenarnya.
"""
import sys
from pathlib import Path

# --- Sesuaikan jika struktur folder repo kamu berbeda ---
REPO_ROOT = Path(__file__).resolve().parent.parent      # satu level di atas evidence/
SCRIPTS_DIR = REPO_ROOT / "scripts"
RAW_DIR = REPO_ROOT / "data" / "raw"
# ----------------------------------------------------------

if not SCRIPTS_DIR.exists():
    sys.exit(
        f"Folder scripts tidak ditemukan di: {SCRIPTS_DIR}\n"
        "Pastikan file ini berada di dalam folder 'evidence' yang sejajar "
        "dengan folder 'scripts' dan 'data' di repo-mu, lalu jalankan ulang."
    )
if not RAW_DIR.exists():
    sys.exit(
        f"Folder data/raw tidak ditemukan di: {RAW_DIR}\n"
        "Pastikan file ini berada di dalam folder 'evidence' yang sejajar "
        "dengan folder 'scripts' dan 'data' di repo-mu, lalu jalankan ulang."
    )

sys.path.insert(0, str(SCRIPTS_DIR))
from vector_pipeline import clean_text          # noqa: E402
from pypdf import PdfReader                     # noqa: E402

examples = [
    {
        "label": "1. Spasi tidak teratur + Nomor halaman ikut terbaca",
        "file": "Pedoman Teknis Manufaktur.pdf",
        "page": 5,
    },
    {
        "label": "2. Kata terpotong (hyphenation di akhir baris)",
        "file": "Pedoman Teknis Manufaktur.pdf",
        "page": 14,
    },
    {
        "label": "3. Simbol tidak standar (bullet non-ASCII)",
        "file": "SOP-11_Pengadaan-Barang-dan-atau-Jasa-BUMDes.pdf",
        "page": 0,
    },
]

for ex in examples:
    pdf_path = RAW_DIR / ex["file"]
    if not pdf_path.exists():
        print(f"[DILEWATI] Berkas tidak ditemukan: {pdf_path}")
        continue

    reader = PdfReader(str(pdf_path))
    raw = reader.pages[ex["page"]].extract_text() or ""
    cleaned = clean_text(raw)

    print("=" * 90)
    print(ex["label"], "|", ex["file"], "| halaman", ex["page"] + 1)
    print("-" * 90)
    print("RAW (potongan):")
    print(raw[:300])
    print("-" * 90)
    print("CLEANED (potongan):")
    print(cleaned[:300])
    print()