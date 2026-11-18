#!/usr/bin/env python3
"""
isi_jadwal.py — tambahkan kejadian dual_ac sesuai JADWAL TETAP AC #2 ke label_log.csv.

Jadwal (timer AC #2, hari kerja): 07:30-20:00. Sabtu, Minggu, dan tanggal
--libur dilewati (AC #2 mati -> idle). Pakai --akhir-pekan bila timer
ternyata juga aktif di Sabtu/Minggu.

Jalankan SEKALI di akhir periode, lalu koreksi baris yang menyimpang berdasarkan
laporan grup (hapus/ubah jam) dan tambahkan kejadian di luar jadwal secara manual.

  python3 label/isi_jadwal.py --mulai 2026-11-12 --selesai 2026-11-18 \
      --jeda 2026-11-13,2026-11-16,2026-11-17 [--libur YYYY-MM-DD]
"""
import argparse, csv
from datetime import date, timedelta

BLOK = [("07:30:00", "20:00:00")]

ap = argparse.ArgumentParser()
ap.add_argument("--mulai", required=True); ap.add_argument("--selesai", required=True)
ap.add_argument("--libur", default="", help="tanggal libur tambahan, pisah koma")
ap.add_argument("--log", default="data/label_log.csv"); ap.add_argument("--pic", default="jadwal")
ap.add_argument("--akhir-pekan", action="store_true", help="AC #2 juga menyala Sabtu/Minggu")
ap.add_argument("--jeda", default="", help="tanggal dengan jeda AC #2 mati 12:00-13:00, pisah koma")
a = ap.parse_args()

libur = {date.fromisoformat(x) for x in a.libur.split(",") if x.strip()}
jeda = {date.fromisoformat(x) for x in a.jeda.split(",") if x.strip()}
with open(a.log) as f:
    n = sum(1 for _ in f) - 1
d, akhir, rows = date.fromisoformat(a.mulai), date.fromisoformat(a.selesai), []
while d <= akhir:
    if (d.weekday() < 5 or a.akhir_pekan) and d not in libur:
        blok = [("07:30:00", "12:00:00"), ("13:00:00", "20:00:00")] if d in jeda else BLOK
        for m, s in blok:
            n += 1
            foto = f"G01_dual_ac_{d:%Y%m%d}_{m[:2]}{m[3:5]}.jpg"
            rows.append([n, "dual_ac", f"{d} {m}", f"{d} {s}", foto, a.pic, "timer 07.30-20.00; set=20" + ("; jeda 12-13" if d in jeda else "")])
    d += timedelta(days=1)
with open(a.log, "a", newline="") as f:
    csv.writer(f).writerows(rows)
print(f"{len(rows)} kejadian dual_ac ditambahkan ke {a.log}. Koreksi penyimpangan secara manual.")
