# Tubes IoT — Monitoring Termal Ruang Server Lab & Perbandingan HTTP vs MQTT

**Kelompok G01 SYNTECH** · Kelas Gab 1 · Internet of Things: Protokol, Platform, dan AI (AAK4WBB3) · Telkom University Purwokerto

| Nama | NIM | Peran |
|---|---|---|
| Rio Adi Setiono (ketua) | 2311101001 | Perangkat, firmware, dataset |
| Krisdiana | 2311101011 | Eksperimen protokol |
| Asa Purwaningsih | 2311101012 | Analisis & laporan |

- **Bagian A:** ESP32 + DHT11 di ruang server Lab Network Security → WiFi lab → HTTP GET ke ThingSpeak **channel 3569769** tiap 30 s.
  Periode resmi: **12 Nov 2026 00:00 – 19 Nov 2026 00:00 WIB**. AC #1 dikunci 20 °C; AC #2 dinyalakan manual (dicatat dari laporan grup WA).
- **Bagian B:** ESP32 + DHT11 fisik, server HTTP lokal (keep-alive, port 8080) dan broker Mosquitto (port 1883) di laptop pada LAN yang sama; 6 skenario × 100 pesan; capture tshark.

## Struktur
```
tubes_iot_bagianA/        firmware Bagian A (salin secrets.example.h -> secrets.h lalu isi)
bagianB/
  fisik/                  firmware Bagian B (versi final), server_lokal.py, mosquitto_g01.conf, README_FISIK.md
  wokwi/                  versi Wokwi (dipakai di run awal; gateway publik Wokwi gagal)
  analisis/               analisis_B.py (RTT, PDR, overhead, grafik), pcap_overhead.py (verifikasi pcap)
  data/                   serial_fisik.txt, fisik.pcap, exp/exp_S1..S6.csv, serial_run1.txt, wokwi_run1.pcap
  hasil/                  ringkasan_B.txt, tabel_B.md, B1_boxplot.png, B2_cdf.png, pcap_fisik.txt
data/                     feeds_*.csv (ekspor mentah ThingSpeak), label_log.csv, label_log_lampiran.csv, dataset_berlabel.csv
analisis/                 label_dataset.py, statistik_laporan.py, analisis_A.py, buat_dataset_uas.py, hasil/
label/label.sh            pencatat kejadian (start/stop) ke data/label_log.csv
uas/                      dataset siap pakai untuk UAS (lihat uas/README_UAS.md)
bukti/                    foto instalasi, screenshot channel, bukti kejadian
laporan/                  laporan (DOCX) dan gambar laporan
PEDOMAN_LABEL.md          definisi kelas, aturan overlap, sumber label
```

## Kebutuhan
- Arduino IDE / `arduino-cli` + core `esp32:esp32`; pustaka **DHT sensor library** (Adafruit), **Adafruit Unified Sensor**, **MQTT** (256dpi)
- Python 3.10+; `matplotlib` (`sudo apt install python3-matplotlib`) — skrip lain hanya pustaka standar
- Bagian B: `mosquitto`, `tshark`/Wireshark

**Kredensial tidak ada di repo.** Salin `secrets.example.h` menjadi `secrets.h` di folder firmware masing-masing lalu isi SSID, password, dan Write API Key / IP server. `secrets.h` ada di `.gitignore`.

## Reproduksi Bagian A
```bash
# 1. ekspor ThingSpeak: Data Import/Export -> Download, simpan sebagai data/feeds_<tanggal>.csv
python3 analisis/label_dataset.py --feeds data/feeds_<tanggal>.csv --log data/label_log.csv --out data/dataset_berlabel.csv
python3 analisis/statistik_laporan.py          # angka laporan -> analisis/hasil/statistik_laporan.txt/.json
python3 analisis/analisis_A.py --data data/dataset_berlabel.csv   # 4 grafik + ringkasan
python3 analisis/buat_dataset_uas.py           # uas/dataset_uas.csv
```

## Reproduksi Bagian B
```bash
python3 bagianB/analisis/analisis_B.py --log bagianB/data/serial_fisik.txt
python3 bagianB/analisis/pcap_overhead.py bagianB/data/fisik.pcap "2026-11-16 16:23:50"
```
Hasil harus sama dengan `bagianB/hasil/` dan baris `SUM` di akhir `serial_fisik.txt`. Cara menjalankan ulang eksperimen: `bagianB/fisik/README_FISIK.md`.

## Firmware
```bash
arduino-cli compile --fqbn esp32:esp32:esp32 tubes_iot_bagianA
arduino-cli upload  -p /dev/ttyUSB0 --fqbn esp32:esp32:esp32 tubes_iot_bagianA
```

## Mencatat kejadian
```bash
export PIC=Rio
./label/label.sh start occupied "praktikum modul X, 20 orang"
./label/label.sh stop  occupied G01_occupied_20261118_0800.jpg
```
Kejadian `dual_ac` diambil dari laporan nyala/mati AC #2 di grup WA (lihat `PEDOMAN_LABEL.md` §3).

## Penggunaan AI
Claude (Anthropic) dipakai untuk membantu firmware, skrip analisis, dan draf laporan; rincian, bagian yang dikoreksi/ditolak, dan cara verifikasi ada di Tabel D.1 laporan.
