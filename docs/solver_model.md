# Model Matematis Solver GA Produksi

Dokumen ini menjelaskan model yang digunakan oleh `scripts/solver.py`. Perhitungan stok, target, opsi batch, dan biaya mengikuti tabel JSON yang sudah tersedia.

## Data dan Notasi

Untuk setiap produk $p$, definisikan:

- $S_p$: stok saat ini, dihitung sebagai jumlah `quantity_change` pada `inventory_history.json` untuk produk $p$.
- $T_p$: target stok, yaitu nilai `initial_stock` produk $p$ di `products.json`.
- $O_p$: kumpulan opsi produksi pada `production_options.json`.
- Opsi $o \in O_p$ memiliki $u_{p,o}$ unit produksi dan biaya $c_{p,o}$.

Stok saat ini dan target diperlakukan persis seperti pada runner UCS. Produk dianalisis secara independen; dataset tidak menyediakan batas anggaran atau kapasitas produksi bersama yang digunakan oleh solver ini.

## Variabel Keputusan

Kromosom untuk produk $p$ adalah urutan opsi batch dengan panjang hingga $L_p$:

$$
\mathbf{x}_p = (x_{p,1}, x_{p,2}, \ldots, x_{p,L_p}), \qquad x_{p,k} \in O_p.
$$

Opsi yang sama boleh muncul lebih dari sekali, yang berarti batch tersebut diproduksi berulang. Batas panjang efektif $L_p$ diturunkan dari jumlah state pada graph produksi produk tersebut, bukan dari batas produksi bisnis tambahan.

Decoder membaca urutan dari kiri ke kanan dan berhenti pada indeks pertama yang mencapai target:

$$
j_p^* = \min \left\{j : S_p + \sum_{k=1}^{j} u_{p,x_{p,k}} \ge T_p \right\}.
$$

Batch setelah $j_p^*$ diabaikan. Stok yang melewati target tetap layak karena kondisi goal yang digunakan adalah stok akhir minimal sebesar target. Jika $S_p \ge T_p$, rencana kosong memiliki biaya nol.

## Fungsi Tujuan

Untuk kromosom yang mencapai target, biaya produksinya adalah:

$$
C_p(\mathbf{x}_p) = \sum_{k=1}^{j_p^*} c_{p,x_{p,k}}.
$$

Tujuan optimasi adalah mencari urutan batch yang memenuhi target dengan biaya sekecil mungkin:

$$
\min_{\mathbf{x}_p} C_p(\mathbf{x}_p)
\quad \text{dengan syarat} \quad
S_p + \sum_{k=1}^{j_p^*} u_{p,x_{p,k}} \ge T_p.
$$

Jika tidak ada jalur dari stok awal yang dapat mencapai target menggunakan opsi yang tersedia, solver mengembalikan `None`.

## Fitness dan Evolusi

Fitness dibandingkan secara leksikografis, dengan nilai lebih kecil dianggap lebih baik:

$$
F_p(\mathbf{x}_p) =
\begin{cases}
(0, 0, C_p), & \text{jika target tercapai}, \\
(1, T_p - S_p^{\mathrm{akhir}}, C_p^{\mathrm{parsial}}), & \text{jika target belum tercapai}.
\end{cases}
$$

Dengan urutan ini, kromosom layak selalu mengungguli kromosom tidak layak; di antara rencana layak, biaya lebih rendah dipilih. Populasi awal dibangun dari batch yang dapat meneruskan jalur ke target. Keturunan hasil crossover atau mutasi yang belum layak tetap dapat dinilai, tetapi akan berada di bawah kandidat layak.

Solver menggunakan:

- **Seleksi:** tournament selection; kandidat terbaik dalam sampel turnamen menjadi induk.
- **Elitisme:** sejumlah kromosom terbaik disalin ke generasi berikutnya tanpa perubahan.
- **Crossover:** menggabungkan prefix satu induk dengan suffix induk lain.
- **Mutasi:** secara probabilistik mengganti, menyisipkan, atau menghapus gen opsi batch.
- **Seed opsional:** memungkinkan hasil evolusi diulang untuk pengujian yang sama.

Parameter populasi, generasi, ukuran turnamen, jumlah elite, dan mutation rate dapat diatur melalui fungsi solver atau CLI.

## Batasan dan Interpretasi Hasil

Optimasi dilakukan per produk, tanpa batas anggaran atau kapasitas bersama. Solver tidak meramalkan permintaan dari `sales.json`; targetnya tetap `initial_stock`, sesuai perilaku runner UCS yang ada.

GA bersifat stokastik dan tidak menjamin optimum global. UCS berfungsi sebagai pembanding deterministik pada ruang keputusan yang sama. Pada pengujian dataset dengan parameter default dan seed 1, biaya GA sama dengan UCS untuk seluruh 30 produk; hasil pengujian tersebut merupakan pengamatan pada konfigurasi itu, bukan jaminan untuk semua seed atau dataset.