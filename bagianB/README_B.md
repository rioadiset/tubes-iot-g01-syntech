# Bagian B — HTTP vs MQTT QoS 0 vs QoS 1 (Wokwi + Wireshark)

Soal mengizinkan Bagian B dijalankan di **Wokwi atau perangkat fisik**. ESP32 fisik sedang dipakai untuk merekam Bagian A sampai 19 Nov, jadi Bagian B dijalankan di **simulator Wokwi**.

## Konsep singkat

- **Wokwi** adalah simulator ESP32 di browser. Kode Arduino yang sama berjalan di sana, dan ESP32 virtualnya bisa mengakses internet lewat WiFi `Wokwi-GUEST`.
- **Wireshark** adalah aplikasi untuk melihat isi paket jaringan. Wokwi bisa merekam semua paket ESP32 virtual ke file `wokwi.pcap`, lalu file itu dibuka di Wireshark untuk mengukur **overhead** (ukuran header dibanding payload). Ini salah satu cara mengukur overhead yang diminta soal.

## Desain eksperimen (B1)

| Variabel | Nilai, dijaga sama di semua skenario |
|---|---|
| Perangkat | ESP32 DevKit C v4 (Wokwi), satu firmware |
| Jaringan | Wokwi-GUEST → Public Gateway Wokwi → internet |
| Jumlah pesan | 100 per skenario |
| Jeda | 2 detik antar-pesan |
| Timeout | 5 detik (lewat dari ini = hilang) |
| Isi payload | `Sx,nnnn,` + karakter `x` hingga 20 B atau 500 B |
| Server HTTP | `httpbin.org:80` `POST /status/200`, tanpa TLS |
| Broker MQTT | `test.mosquitto.org:1883`, tanpa TLS |
| HTTP | **keep-alive**: koneksi TCP dipakai ulang, setara dengan MQTT yang memakai satu koneksi persisten. Yang dibandingkan adalah protokol aplikasinya, bukan biaya handshake TCP |
| RTT HTTP | request ditulis → response lengkap diterima |
| RTT MQTT | publish → pesan yang sama kembali dari broker (subscribe ke topik sendiri, QoS sama) |

## Langkah menjalankan (±40 menit, sebagian besar menunggu)

1. Buka <https://wokwi.com>, login, lalu pilih **New Project → ESP32**.
2. Ganti isi tab **sketch.ino** dengan `wokwi/sketch.ino`, dan isi **diagram.json** dengan `wokwi/diagram.json`.
3. Klik **Library Manager** (ikon buku) → **+** → cari **MQTT** (oleh *Joel Gaehwiler*) → tambahkan. Ini sama dengan isi `wokwi/libraries.txt`.
4. Klik **▶ Start**. Serial Monitor akan menampilkan baris `# ...` lalu `DATA,...`. Biarkan berjalan sampai muncul `# SELESAI` (600 pesan × 2 detik ≈ 20–30 menit). **Jangan tutup tab browser**, karena simulasi berhenti kalau tab ditutup atau komputer tidur.
5. **Sebelum menekan Stop:** klik **ikon WiFi** di simulator → **Download PCAP file**, lalu simpan sebagai `bagianB/data/wokwi.pcap`.
6. Salin isi Serial Monitor (blok teksnya dengan mouse, lalu `Ctrl+C`) dan tempel ke file teks `bagianB/data/serial_wokwi.txt`. Supaya aman dari batas scroll Serial Monitor, **salin setiap kali muncul `# Sx selesai`** dan tempel di akhir file yang sama. Baris yang tersalin dua kali otomatis dibuang oleh skrip analisis.
7. Jalankan analisis:

```bash
cd ~/Downloads/"IOT Platfrom"
python3 bagianB/analisis/analisis_B.py --log bagianB/data/serial_wokwi.txt
python3 bagianB/analisis/pcap_overhead.py bagianB/data/wokwi.pcap
```

Hasilnya ada di `bagianB/hasil/`: `log_B.csv` (data mentah per pesan), `ringkasan_B.txt`, `tabel_B.md`, `B1_boxplot.png`, dan `B2_cdf.png`.

> Kalau Serial Monitor terpotong atau ada skenario yang kurang dari 100 pesan, jalankan ulang seluruh simulasi. Jangan menggabungkan potongan log dari run yang berbeda.

## Wireshark (verifikasi overhead + bahan analisis C3)

```bash
sudo apt install wireshark      # pilih "No" saat ditanya non-superuser capture (kita hanya membuka file)
wireshark bagianB/data/wokwi.pcap
```

Ketik filter berikut di kolom *display filter*:

| Filter | Yang dilihat | Untuk analisis |
|---|---|---|
| `tcp.flags.syn==1 && tcp.flags.ack==0` | Handshake TCP | Membuktikan keep-alive (SYN hanya muncul di awal dan saat reconnect) |
| `http.request` | Request HTTP | Ukuran header HTTP (klik paket → *Hypertext Transfer Protocol*) |
| `mqtt.msgtype==3` | PUBLISH | Header MQTT 2 byte + topik |
| `mqtt.msgtype==4` | PUBACK | ACK QoS 1, menjelaskan kenapa QoS 1 lebih lambat |
| `tcp.analysis.retransmission` | Retransmisi TCP | Penjelasan outlier atau anomali RTT |

Menu **Statistics → Protocol Hierarchy** dan **Statistics → Conversations** dapat di-screenshot untuk laporan.

## Keterbatasan (tulis di laporan)

- RTT mencakup jalur Wokwi Public Gateway dan internet, sehingga nilainya lebih besar dan lebih bervariasi dibanding broker di LAN. Perbandingan antar-skenario tetap adil karena jalurnya sama.
- Waktu di pcap bisa berjalan lebih lambat dari waktu nyata jika kecepatan simulasi di bawah 100%. Karena itu RTT diambil dari log perangkat, bukan dari pcap.
- RSSI di Wokwi adalah nilai simulasi (berkisar sekitar −70 s.d. −97 dBm), bukan hasil pengukuran radio nyata, sehingga bonus +5 (dua kondisi sinyal) hanya sah di perangkat fisik. Opsional setelah 19 Nov: set `USE_WOKWI 0`, isi `secrets.h`, lalu jalankan di ESP32 dekat AP dan jauh dari AP.
- Broker dan server yang dipakai adalah layanan publik. Jangan mengirim data pribadi apa pun.
