# Pedoman Pelabelan Dataset — Kelompok G01 (SYNTECH)

Sistem: ESP32 + DHT11 → ThingSpeak (channel 3569769), interval 30 detik.
Lokasi: ruang server Lab Network Security, Telkom University Purwokerto (dua unit AC; AC #1 menyala 24 jam).
Periode rekaman resmi: **Kamis, 12 Nov 2026 00:00 WIB s.d. Kamis, 19 Nov 2026 00:00 WIB** (7 × 24 jam, 20.160 sampel).

## 1. Kondisi baseline

Pada Kamis, 12 Nov 2026 (±14.10 WIB), AC #1 dikunci pada setpoint **20 °C** dan tidak diubah hingga akhir periode. Penetapan ini menghilangkan variasi setpoint AC #1 (sebelumnya berkisar 16–25 °C sesuai keinginan pengguna) sebagai variabel pengganggu. Sampel pada 12 Nov 00:00 hingga penguncian, ditambah 30 menit stabilisasi, tetap dihitung dalam kelengkapan perekaman, tetapi diberi penanda `ac1_ubah` sehingga dikecualikan dari data latih. Data sebelum 12 Nov tidak digabungkan dengan dataset utama.

## 2. Kelas dan kondisi yang dicatat

| Kode | Definisi operasional | Sumber label |
|---|---|---|
| `idle` | AC #1 pada 20 °C, AC #2 mati, dan kurang dari 3 orang di lab | Turunan (tidak ada kondisi lain aktif) |
| `dual_ac` | AC #2 menyala bersama AC #1 | Laporan nyala/mati AC #2 di grup WA (bertimestamp) |
| `occupied` | Terdapat ≥ 3 orang di dalam lab (praktikum, rapat, kerja kelompok) | Jadwal praktikum resmi + laporan grup |
| `ac1_ubah` | **Bukan kelas.** Setpoint AC #1 menyimpang dari 20 °C | Laporan / pemeriksaan harian |
| `tidak_pasti` | **Bukan kelas.** Perubahan bacaan yang tidak dapat dijelaskan oleh catatan mana pun | Pemeriksaan data (Bagian 5) |

Kondisi pintu dibuka tidak digunakan sebagai kelas. Kebijakan lab membatasi pintu terbuka maksimal sekitar 1 menit, setara dua sampel, sehingga efeknya tidak terukur dan kelasnya tidak dapat dibedakan dari `idle`.

## 3. Pencatatan AC #2 (revisi 17 Nov 2026)

Rencana awal memakai timer AC #2 07.30–20.00 pada hari kerja. Dalam pelaksanaannya AC #2 **dioperasikan manual** oleh pengguna lab sesuai kebutuhan ruangan, sehingga label `dual_ac` diambil dari **laporan nyala/mati di grup WhatsApp asisten** yang bertimestamp otomatis, bukan dari jadwal. Jam yang dipakai adalah jam yang ditulis di pesan (bukan jam kirim pesan); selisih keduanya ≤ 2 menit.

| Tanggal | AC #2 nyala | AC #2 mati | Sumber |
|---|---|---|---|
| Jum, 13 Nov | 09.46 | 16.25 | Pesan WA 09.46 dan 16.25 |
| Jum, 13 Nov | 18.10 | 19.01 | Pesan WA 18.12 dan 19.01 |
| Sab–Min, 14–15 Nov | — | — | AC #2 mati sepanjang hari |
| Sen, 16 Nov | 12.10 | 20.16 | Pesan WA 12.10 dan 20.17 |
| Sel, 17 Nov | 12.37 | (isi saat dimatikan) | Pesan WA 12.37 |

Di luar interval tersebut AC #2 mati (`idle`). Bukti: tangkapan layar percakapan grup (`bukti/G01_log_ac2_wa.jpg`) ditambah foto panel/remote AC #2 bila tersedia. Konsistensi label diperiksa terhadap data: setiap kali AC #2 dinyalakan, suhu rata-rata 30–60 menit sesudahnya turun 1,0–2,4 °C dibanding 30 menit sebelumnya, dan naik kembali setelah AC #2 dimatikan. `label/isi_jadwal.py` tidak dipakai lagi.

## 4. Penanganan kejadian yang berlangsung bersamaan

Setiap kondisi dicatat sebagai interval waktu yang terpisah, satu baris per kondisi, sehingga dua atau lebih kondisi diperbolehkan tumpang tindih tanpa harus memilih salah satunya saat pencatatan. Sebagai contoh, praktikum pukul 08.00–10.00 ketika AC #2 menyala sesuai jadwal dicatat dua baris berikut.

```
4,dual_ac,2026-11-16 12:10:00,2026-11-16 20:16:00,G01_log_ac2_wa.jpg,Rio,laporan WA 12.10 / 20.17
7,occupied,2026-11-16 08:00:00,2026-11-16 10:00:00,G01_occupied_20261116_0800.jpg,Rio,praktikum modul X
```

Label per sampel kemudian diturunkan secara otomatis dan deterministik oleh `analisis/label_dataset.py` dengan aturan berikut:

1. **Label multi-kondisi (utama).** Setiap sampel memperoleh kolom biner `dual_ac` dan `occupied` (0/1) serta kolom `label_kombinasi`, misalnya `dual_ac+occupied`. Representasi ini tidak membuang informasi apa pun.
2. **Label tunggal (`label_utama`)** untuk keperluan klasifikasi satu kelas, diterapkan berurutan:
   - `ac1_ubah` atau `tidak_pasti` aktif → `anomali` (dikecualikan dari pelatihan);
   - tidak ada kondisi aktif → `idle`;
   - tepat satu kondisi aktif → nama kondisi tersebut;
   - dua kondisi aktif → `campuran`.

   Sampel `campuran` tidak dipaksa masuk ke salah satu kelas. Alasannya, efek termal setiap kondisi bersifat aditif, sehingga aturan prioritas akan memberi label yang sama pada pola bacaan yang berbeda. Akibatnya, kondisi yang sama dapat berlabel tidak konsisten.
3. **Masa transisi.** Sampel dalam 10 menit pertama setelah awal atau akhir suatu kejadian ditandai `transisi = 1`, karena suhu ruangan belum stabil.
4. **Kondisi yang sama tidak boleh tumpang tindih dengan dirinya sendiri.** Jika suatu kondisi berhenti lalu aktif kembali dalam selang < 10 menit, keduanya digabung menjadi satu kejadian.

Dengan aturan ini, satu kondisi fisik selalu menghasilkan label yang sama, siapa pun pencatatnya.

## 5. Pengendalian kualitas label

Pencatatan manual berpotensi terlewat, terutama ketika lab dipakai oleh dosen atau pengguna lain. Karena itu diterapkan tiga lapis pengendalian:

1. **Jadwal tetap dan pengumuman.** Jadwal AC #2 dan larangan mengubah AC #1 diumumkan di grup asisten dan ditempel pada unit AC. Pengguna diminta melaporkan setiap penyimpangan dengan format singkat.
2. **Pemeriksaan harian.** Setpoint AC #1 dan status AC #2 diperiksa serta difoto setiap pagi dan sore.
3. **Pemeriksaan data.** Di akhir periode, perubahan suhu atau kelembapan yang tidak sesuai dengan jadwal maupun laporan (misalnya suhu turun ≥ 2 °C ketika AC #2 seharusnya mati) dicocokkan dengan bukti yang tersedia. Segmen yang tidak dapat dijelaskan diberi penanda `tidak_pasti` dan dikecualikan dari pelatihan. Jumlah segmen ini dilaporkan sebagai ukuran ketidakpastian label.

## 6. Kejadian `occupied`

Sumber utama label `occupied` adalah jadwal praktikum resmi di lab tersebut, ditambah laporan pemakaian lab di luar jadwal melalui grup asisten. Target minimal ≥ 5 kejadian. Apabila hingga Senin, 16 Nov jumlahnya belum mencukupi, sesi kerja kelompok ≥ 3 orang selama 60 menit dilakukan di lab sebagai kejadian terkendali.

## 7. Bukti dan pencatatan

- Setiap kejadian wajib memiliki foto bertimestamp bernama `G01_<kondisi>_YYYYMMDD_HHMM.jpg` di folder `bukti/`. Foto `dual_ac` memperlihatkan AC #2 menyala atau layar remote, sedangkan foto `occupied` memperlihatkan suasana ruangan.
- Kejadian di luar jadwal dicatat secara real-time dengan `label/label.sh`, atau dicatat mundur berdasarkan laporan grup bertimestamp. Sumber bukti ditulis di kolom `catatan`.

## 8. Keterbatasan

Penyimpangan jadwal yang tidak dilaporkan dan tidak terdeteksi pada pemeriksaan data akan menghasilkan label yang tidak sesuai. Risiko ini dikurangi melalui tiga lapis pengendalian pada Bagian 5 dan dilaporkan sebagai sumber ketidakpastian label.

## 9. Penggunaan untuk UAS

- **Klasifikasi multi-label:** target berupa `dual_ac` dan `occupied`. Sampel `anomali` dikecualikan.
- **Klasifikasi satu kelas:** target berupa `label_utama` (`idle`, `dual_ac`, `occupied`) dengan sampel `campuran`, `anomali`, dan `transisi = 1` dikecualikan dari data latih. Jumlah sampel yang dikecualikan dilaporkan.
- Fitur suhu memakai `suhu_bulat_c` atau moving average, karena desimal DHT11 merupakan noise (resolusi efektif 1 °C).
