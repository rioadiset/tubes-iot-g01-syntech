# Bagian B di ESP32 fisik (pengganti Wokwi)

Wokwi gagal empat kali. Pola gagalnya selalu sama: gateway publik `wss://netwi.wokwi.com` memutus koneksi setelah beberapa puluh detik, sehingga Bagian B dijalankan di ESP32 + DHT11 asli. Firmware-nya identik dengan versi Wokwi; perbedaannya hanya `USE_WOKWI 0` (otomatis memakai DHT11 dan `secrets.h`).

Total waktu ±40 menit: 10 menit persiapan + ±25 menit berjalan + 5 menit beres-beres.

## 0. Pilih perangkat

- **Opsi 1, disarankan:** ESP32 + DHT11 pinjaman dari lab. Bagian A tidak terganggu.
- **Opsi 2:** ESP32 Bagian A dipinjam sebentar. Bagian A akan punya celah ±40 menit (kelengkapan tetap ±99 %). Catat jam cabut dan jam pasang kembali di `data/label_log.csv`:
  `n,tidak_pasti,YYYY-MM-DD HH:MM:SS,YYYY-MM-DD HH:MM:SS,,Rio,ESP32 dipakai Bagian B (jeda terencana)`

Wiring DHT11 sama dengan Bagian A: VCC→3V3, GND→GND, DATA→GPIO4.

## 1. Hotspot laptop (internet dari ethernet)

Semua paket ESP32 akan lewat laptop, sehingga Wireshark bisa menangkapnya langsung.

```bash
nmcli device status                       # cari nama interface WiFi, mis. wlp2s0
nmcli device wifi hotspot ifname wlp2s0 ssid G01-B password "PasswordKuat123"
```
Isi `fisik/bagianB_fisik/secrets.h` dengan SSID `G01-B` dan password yang sama. ESP32 hanya mendukung WiFi 2.4 GHz; jika hotspot tidak terdeteksi, tambahkan `band bg` pada perintah di atas.

## 2. Mulai menangkap paket (terminal 1)

```bash
sudo apt install tshark                   # pilih "Yes" jika ditanya non-root capture
cd ~/Downloads/"IOT Platfrom"
sudo tshark -i wlp2s0 -f "tcp port 80 or tcp port 1883" -w bagianB/data/fisik.pcap
```

## 3. Upload & rekam log (terminal 2)

```bash
cd ~/Downloads/"IOT Platfrom"/bagianB/fisik
arduino-cli lib install MQTT
arduino-cli compile --fqbn esp32:esp32:esp32 bagianB_fisik
arduino-cli upload -p /dev/ttyUSB0 --fqbn esp32:esp32:esp32 bagianB_fisik
arduino-cli monitor -p /dev/ttyUSB0 -c baudrate=115200 | tee ../data/serial_fisik.txt
```
Tunggu hingga muncul `# SELESAI` (±25 menit), lalu tekan `Ctrl+C` di kedua terminal.

## 4. Analisis

```bash
cd ~/Downloads/"IOT Platfrom"
python3 bagianB/analisis/analisis_B.py --log bagianB/data/serial_fisik.txt
python3 bagianB/analisis/pcap_overhead.py bagianB/data/fisik.pcap
```

## 5. Jika memakai Opsi 2: kembalikan Bagian A

```bash
cd ~/Downloads/"IOT Platfrom"
arduino-cli upload -p /dev/ttyUSB0 --fqbn esp32:esp32:esp32 tubes_iot_bagianA
```
Pasang kembali di posisi semula, cek di ThingSpeak bahwa entri baru masuk, lalu catat jam pasang di `label_log.csv`.

## Bonus +5 (opsional)

Ulangi langkah 3 di dua posisi dengan selisih RSSI ≥ 15 dB, misalnya ±1 m dari laptop dan di balik tembok. Simpan log sebagai `serial_fisik_dekat.txt` dan `serial_fisik_jauh.txt`, lalu jalankan `analisis_B.py` dengan `--out bagianB/hasil_dekat` dan `--out bagianB/hasil_jauh`.

## Catatan untuk laporan

- Data Wokwi run 1 (S1–S4, tanpa sensor) tetap disimpan sebagai pembanding dan bukti percobaan.
- Kegagalan gateway Wokwi dicatat sebagai keterbatasan alat simulasi: koneksi ke Public IoT Gateway terputus berulang, dan dokumentasi Wokwi menyebut penggunaan gateway publik dapat dibatasi.
