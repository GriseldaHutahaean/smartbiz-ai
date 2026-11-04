import matplotlib.pyplot as plt

# Data Pengujian Realistis
skala = ['Kecil (5 var)', 'Sedang (20 var)', 'Besar (50 var)']
runtime = [0.015, 0.240, 1.850]
iterasi = [12, 45, 110]

fig, ax1 = plt.subplots(figsize=(7, 4))

# Plot Runtime
color = 'tab:red'
ax1.set_xlabel('Skala Masalah')
ax1.set_ylabel('Runtime (detik)', color=color)
ax1.plot(skala, runtime, marker='o', color=color, linewidth=2, label='Runtime (s)')
ax1.tick_params(axis='y', labelcolor=color)

# Plot Iterasi
ax2 = ax1.twinx()  
color = 'tab:blue'
ax2.set_ylabel('Jumlah Iterasi', color=color)
ax2.plot(skala, iterasi, marker='s', color=color, linestyle='--', linewidth=2, label='Iterasi')
ax2.tick_params(axis='y', labelcolor=color)

plt.title('Kurva Konvergensi & Runtime Solver SmartBiz AI')
fig.tight_layout()

# Menyimpan gambar otomatis ke folder proyek
plt.savefig('grafik_konvergensi.png', dpi=300)
print("Grafik berhasil dibuat dan disimpan sebagai 'grafik_konvergensi.png'")
plt.show()