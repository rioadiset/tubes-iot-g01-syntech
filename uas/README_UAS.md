# Dataset Bagian A untuk UAS (Machine Learning)

Soal: *"dataset Bagian A akan dipakai lagi untuk model Machine Learning di UAS. Simpan baik-baik."*

## Isi folder
| File | Isi |
|---|---|
| `dataset_uas.csv` | Semua sampel periode resmi (30 s) + fitur waktu + label. Kolom `pakai_latih = 1` = siap dipakai melatih model |
| `ringkasan_uas.txt` | Jumlah sampel per kelas |

Sumber asli (jangan diubah, semua di `data/`):
- `data/feeds_<tanggal>.csv` — ekspor mentah ThingSpeak channel 3569769 (UTC, field1–7)
- `data/label_log.csv` — log kejadian (dual_ac dari laporan WA AC #2, occupied dari label.sh)
- `data/dataset_berlabel.csv` — hasil gabungan data + label

## Kolom `dataset_uas.csv`
| Kolom | Arti |
|---|---|
| `waktu_wib` | Waktu sampel (WIB, UTC+7) |
| `jam`, `menit_hari`, `hari_ke`, `akhir_pekan` | Fitur waktu (hari_ke 1 = Senin) |
| `suhu_c`, `suhu_bulat_c` | Suhu DHT11; resolusi efektif 1 °C sehingga `suhu_bulat_c` lebih jujur |
| `kelembapan_rh` | Kelembapan (%RH, bilangan bulat) |
| `rssi_dbm` | Kekuatan sinyal WiFi |
| `dual_ac`, `occupied` | Label multi-kondisi (0/1) |
| `label_kombinasi`, `label_utama` | Label gabungan / tunggal (idle, dual_ac, occupied, campuran, anomali) |
| `transisi` | 1 = 10 menit setelah kondisi berubah (suhu belum stabil) |
| `pakai_latih` | 1 = kelas valid dan bukan transisi |

## Catatan untuk pemodelan
- Pakai **pembagian berbasis waktu** (mis. per hari), bukan acak per sampel: sampel 30 s yang berdekatan hampir identik sehingga split acak membuat akurasi terlihat terlalu tinggi.
- Hati-hati dengan fitur `jam`: AC #2 lebih sering menyala siang hari, sehingga model bisa "menebak dari jam". Bandingkan model dengan dan tanpa fitur waktu.
- Fitur turunan yang wajar: selisih suhu 10/30 menit (laju perubahan), rerata bergulir.
- Kelas tidak seimbang (idle jauh lebih banyak) → laporkan F1/recall per kelas, bukan hanya akurasi.

## Membuat ulang
```bash
python3 analisis/label_dataset.py --feeds data/feeds_<tanggal>.csv --log data/label_log.csv --out data/dataset_berlabel.csv
python3 analisis/buat_dataset_uas.py --data data/dataset_berlabel.csv --out uas
```
