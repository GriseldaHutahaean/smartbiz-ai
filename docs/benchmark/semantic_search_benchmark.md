# SmartBiz AI Semantic Search Benchmark

Threshold hasil pengujian aktual: **0.484877**.

Kueri out-of-domain ditolak jika cosine similarity Top-1 berada di bawah threshold. Relevansi diberi label berdasarkan sumber dokumen yang memang membahas topik kueri; skor, dokumen, chunk, dan hasil retrieval berasal dari eksekusi ChromaDB aktual.

| ID | Kategori | Dokumen Top-K | Top-1 cosine | Status | Precision@K | Recall@K | Analisis |
|---|---|---|---:|---|---:|---:|---|
| q01 | relevant | E-Book_Pedoman_SIAPIK.pdf; 5 Pedoman Teknis Pertanian.pdf | 0.630493 | tidak relevan | 0.000 | 0.000 | Tidak ada sumber relevan pada Top-K; perlu evaluasi query atau threshold. |
| q02 | relevant | SOP-13_Pengelolaan-Stok-dan-Persediaan-BUMDes.pdf; Pengumuman_Modul_Pengantar_Manajemen_Rantai_Pasok.pdf; E-Book_Pedoman_SIAPIK.pdf; 67 Buku 4 Manajemen Usaha Kecil.pdf | 0.677125 | relevan | 0.400 | 1.000 | Hasil Top-K memuat sumber relevan. |
| q03 | synonym | Pelatihan HPP dan Harga Jual untuk Koperasi UKM Kuliner (BRIN).pdf; E-Book_Pedoman_SIAPIK.pdf | 0.733545 | relevan | 0.600 | 1.000 | Hasil Top-K memuat sumber relevan. |
| q04 | synonym | sop-seleksi-dan-evaluasi-vendor (1).pdf; sop-penerimaan-dan-penyimpanan-bahan-baku.pdf | 0.735832 | relevan | 0.800 | 0.500 | Hasil Top-K memuat sumber relevan. |
| q05 | ambiguous | 67 Buku 4 Manajemen Usaha Kecil.pdf | 0.718464 | relevan | 1.000 | 0.500 | Hasil Top-K memuat sumber relevan. |
| q06 | ambiguous | Pedoman Teknis Manufaktur.pdf; Buku Juknis SIAPIK Web Sektor Perdagangan.pdf | 0.752275 | relevan | 0.800 | 0.500 | Hasil Top-K memuat sumber relevan. |
| q07 | out-of-domain | Pengumuman_Modul_Pengantar_Manajemen_Rantai_Pasok.pdf; E-Book_Pedoman_SIAPIK.pdf; 67 Buku 4 Manajemen Usaha Kecil.pdf | 0.339261 | ditolak | 0.000 | 0.000 | Query out-of-domain berhasil ditolak oleh threshold. |
| q08 | out-of-domain | SOP-13_Pengelolaan-Stok-dan-Persediaan-BUMDes.pdf; Buku Juknis SIAPIK Web Sektor Perdagangan.pdf; E-Book_Pedoman_SIAPIK.pdf | 0.189549 | ditolak | 0.000 | 0.000 | Query out-of-domain berhasil ditolak oleh threshold. |

## Interpretasi

Precision@K mengukur proporsi chunk pada Top-K yang berasal dari sumber relevan yang dilabeli. Recall@K mengukur cakupan dokumen sumber relevan unik yang ditemukan, sehingga nilainya berada pada rentang 0 sampai 1. False acceptance adalah kueri out-of-domain yang melewati threshold; false rejection adalah kueri domain yang ditolak.

## Parameter

- Model embedding: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- ChromaDB: persistent storage dengan cosine distance
- Chunk size: 1000 karakter
- Overlap: 150 karakter target pada kata-kata terakhir chunk sebelumnya
- Kategori: relevant, synonym, ambiguous, dan out-of-domain
