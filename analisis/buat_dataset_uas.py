#!/usr/bin/env python3
"""
buat_dataset_uas.py — siapkan dataset Bagian A untuk model Machine Learning (UAS).

Masukan : data/dataset_berlabel.csv (keluaran label_dataset.py)
Keluaran: uas/dataset_uas.csv  — semua sampel periode resmi + fitur waktu + kolom pakai_latih
          uas/ringkasan_uas.txt — jumlah sampel per kelas

Aturan pakai_latih = 1 bila label_utama ∈ {idle, dual_ac, occupied} dan transisi = 0
(anomali/campuran/transisi tetap disimpan agar bisa dianalisis, tetapi tidak dipakai melatih model).

Pakai:
  python3 analisis/buat_dataset_uas.py --data data/dataset_berlabel.csv --out uas
Hanya pustaka standar Python.
"""
import argparse
import csv
import os
from collections import Counter
from datetime import datetime

KELAS = {"idle", "dual_ac", "occupied"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/dataset_berlabel.csv")
    ap.add_argument("--out", default="uas")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rows = list(csv.DictReader(open(a.data)))
    kolom = ["waktu_wib", "jam", "menit_hari", "hari_ke", "akhir_pekan", "suhu_c", "suhu_bulat_c", "kelembapan_rh",
             "rssi_dbm", "dual_ac", "occupied", "label_kombinasi", "label_utama", "transisi", "pakai_latih"]
    hit = Counter()
    with open(os.path.join(a.out, "dataset_uas.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=kolom)
        w.writeheader()
        for r in rows:
            t = datetime.strptime(r["waktu_wib"], "%Y-%m-%d %H:%M:%S")
            latih = int(r["label_utama"] in KELAS and r["transisi"] == "0")
            hit[(r["label_utama"], latih)] += 1
            w.writerow({"waktu_wib": r["waktu_wib"], "jam": t.hour, "menit_hari": t.hour * 60 + t.minute,
                        "hari_ke": t.isoweekday(), "akhir_pekan": int(t.isoweekday() >= 6),
                        "suhu_c": r["suhu_c"], "suhu_bulat_c": r["suhu_bulat_c"], "kelembapan_rh": r["kelembapan_rh"],
                        "rssi_dbm": r["rssi_dbm"], "dual_ac": r["dual_ac"], "occupied": r["occupied"],
                        "label_kombinasi": r["label_kombinasi"], "label_utama": r["label_utama"],
                        "transisi": r["transisi"], "pakai_latih": latih})
    L = [f"Sumber: {a.data}", f"Periode: {rows[0]['waktu_wib']} s.d. {rows[-1]['waktu_wib']}", f"Total sampel: {len(rows)}"]
    for (lab, latih), n in sorted(hit.items()):
        L.append(f"  {lab:9s} pakai_latih={latih}: {n}")
    txt = "\n".join(L)
    print(txt)
    open(os.path.join(a.out, "ringkasan_uas.txt"), "w").write(txt + "\n")


if __name__ == "__main__":
    main()
