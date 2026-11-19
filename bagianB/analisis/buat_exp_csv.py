#!/usr/bin/env python3
"""
buat_exp_csv.py — ubah log Serial Bagian B menjadi exp_S1.csv ... exp_S6.csv (format soal).

Masukan : bagianB/data/serial_fisik.txt (baris "DATA,..." dari firmware bagianB_fisik)
          format DATA: skenario,seq,payload_b,protokol,status,rtt_ms,req_b,resp_b,http_code,reconn,rssi_dbm,t_ms,suhu_c,rh
Keluaran: bagianB/data/exp/exp_S<n>.csv
          header: skenario,seq,payload_byte,t_kirim_ms,t_terima_ms,rtt_ms,status,rssi_dbm

Catatan pengolahan (didokumentasikan di laporan B.3):
  * t_terima_ms = millis() ESP32 saat baris DATA ditulis (kolom t_ms dari firmware).
  * t_kirim_ms  = t_terima_ms - rtt_ms (nilai turunan, presisi 3 desimal), karena firmware
    hanya mencetak waktu terima dan RTT terukur.
  * Duplikat (skenario, seq) diambil yang pertama; tidak ada baris yang diubah atau dibuang selain itu.

Pakai:
  python3 bagianB/analisis/buat_exp_csv.py --log bagianB/data/serial_fisik.txt --out bagianB/data/exp
Hanya pustaka standar Python.
"""
import argparse
import csv
import os

KOLOM = ["skenario", "seq", "payload_b", "protokol", "status", "rtt_ms", "req_b", "resp_b",
         "http_code", "reconn", "rssi_dbm", "t_ms", "suhu_c", "rh"]
HEADER = ["skenario", "seq", "payload_byte", "t_kirim_ms", "t_terima_ms", "rtt_ms", "status", "rssi_dbm"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="bagianB/data/serial_fisik.txt")
    ap.add_argument("--out", default="bagianB/data/exp")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    per, seen = {}, set()
    for line in open(a.log, encoding="utf-8", errors="ignore"):
        line = line.strip()
        if not line.startswith("DATA,"):
            continue
        p = line.split(",")[1:]
        if len(p) not in (len(KOLOM), len(KOLOM) - 2):
            continue
        r = dict(zip(KOLOM, p))
        k = (r["skenario"], r["seq"])
        if k in seen:
            continue
        seen.add(k)
        t1 = int(r["t_ms"])
        rtt = float(r["rtt_ms"])
        per.setdefault(r["skenario"], []).append(
            [r["skenario"], r["seq"], r["payload_b"], f"{t1 - rtt:.3f}", t1, r["rtt_ms"], r["status"], r["rssi_dbm"]])

    for sk, rows in sorted(per.items()):
        path = os.path.join(a.out, f"exp_{sk}.csv")
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(HEADER)
            w.writerows(rows)
        print(f"{path}: {len(rows)} baris")


if __name__ == "__main__":
    main()
