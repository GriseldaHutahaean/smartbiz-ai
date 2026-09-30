# Analisis Sensitivitas Solver GA

## Metode Pengujian

Pengujian memakai data asli di `data/smartbiz_json/` dan solver `scripts/solver.py`. Stok awal dihitung dari jumlah `quantity_change`, target diambil dari `initial_stock`, dan opsi batch beserta biayanya berasal dari `production_options.json`.

Semua percobaan memakai CPython 3.14 pada Windows dan seed 42. Waktu adalah rata-rata tiga pemanggilan terpisah yang diukur dengan `time.perf_counter`; setiap pemanggilan membangun populasi dari awal. Untuk checkpoint generasi, ukuran populasi ditetapkan 60. Untuk variasi populasi, jumlah generasi ditetapkan 50. Biaya UCS dari runner yang ada digunakan sebagai pembanding eksak.

Ukuran masalah dinyatakan dengan jumlah state pada graph produksi yang dibentuk dari stok saat ini sampai target. Semua produk pada dataset memiliki empat opsi batch.

## Skala Kecil dan Besar

P005 merupakan kasus pencarian terkecil yang memerlukan produksi: kekurangan stok 3 unit dan graph 1 state. P008 merupakan kasus terbesar: kekurangan 102 unit dan graph 21 state.

| Produk | State graph | Generasi | Waktu rata-rata (ms) | Biaya GA (Rp) | Biaya UCS (Rp) |
| --- | ---: | ---: | ---: | ---: | ---: |
| P005 | 1 | 0 | 0.331 | 17,500 | 17,500 |
| P005 | 1 | 10 | 12.706 | 17,500 | 17,500 |
| P005 | 1 | 30 | 39.086 | 17,500 | 17,500 |
| P005 | 1 | 60 | 76.042 | 17,500 | 17,500 |
| P005 | 1 | 150 | 181.845 | 17,500 | 17,500 |
| P008 | 21 | 0 | 1.805 | 698,750 | 262,500 |
| P008 | 21 | 10 | 59.898 | 357,500 | 262,500 |
| P008 | 21 | 30 | 227.242 | 262,500 | 262,500 |
| P008 | 21 | 60 | 497.810 | 262,500 | 262,500 |
| P008 | 21 | 150 | 1,356.930 | 262,500 | 262,500 |

Dengan seed ini, P005 sudah menemukan biaya UCS dari populasi awal. Pada P008, biaya turun dari Rp698.750 pada generasi 0 menjadi Rp262.500 pada generasi 30, lalu tidak berubah pada checkpoint 60 dan 150. Ini menunjukkan konvergensi untuk kasus dan seed yang diuji, bukan jaminan konvergensi untuk setiap seed.

## Variasi Ukuran Populasi

Kasus P008 diuji pada 50 generasi dengan seed tetap.

| Ukuran populasi | Waktu rata-rata (ms) | Biaya GA (Rp) | Biaya UCS (Rp) |
| ---: | ---: | ---: | ---: |
| 20 | 121.488 | 262,500 | 262,500 |
| 60 | 328.433 | 262,500 | 262,500 |
| 100 | 522.529 | 262,500 | 262,500 |

Pada percobaan ini, ukuran populasi lebih besar menambah waktu eksekusi, sementara biaya terbaik tidak berubah. Untuk produk P008 dan seed 42, populasi 20 sudah cukup menemukan biaya UCS pada 50 generasi.

## Interpretasi dan Batasan

- Untuk konfigurasi default (`population_size=60`, `generations=150`) dan seed 1, pemeriksaan terpisah mendapatkan biaya GA yang sama dengan UCS pada seluruh 30 produk.
- P005 dan P008 juga mencapai biaya UCS pada percobaan seed 42 yang dilaporkan di atas.
- Hasil bergantung pada seed dan parameter GA. Kesamaan dengan UCS pada percobaan tersebut tidak mengubah sifat GA yang stokastik.
- Dataset hanya menyediakan skala sampai 21 state graph pada produk yang memerlukan produksi. Hasil ini belum membuktikan performa pada skala enterprise yang lebih besar.
- Waktu bergantung pada perangkat keras, versi Python, dan beban sistem; angka di tabel adalah pengukuran lokal, bukan jaminan waktu produksi.