#!/usr/bin/env python3
"""
kalibrasi.py — bandingkan DHT11 Bagian A dengan alat pembanding (kalibrasi offset satu titik).

Masukan:
  data/kalibrasi_manual.csv   bacaan alat pembanding, satu baris per pengamatan:
      waktu_wib,ref_suhu_c,ref_rh,alat,catatan
      2026-11-18 13:00,25.4,52,HTC-1,ditaruh 10 cm dari DHT11
    (ref_rh boleh kosong bila alat hanya mengukur suhu)
  data/feeds_<tanggal>.csv    ekspor ThingSpeak (UTC) yang mencakup waktu pengamatan

Metode:
  Setiap pengamatan dipasangkan dengan RERATA sampel DHT11 dalam ±2 menit (4–8 sampel),
  karena resolusi DHT11 1 °C membuat satu sampel tunggal berosilasi.
  error = DHT11 − pembanding. Dilaporkan: n, bias (rerata error), SD error, MAE, |error| maks,
  dan apakah semua error berada dalam akurasi datasheet (±2 °C, ±5 %RH).
  Koreksi yang disarankan = −bias (offset); hanya berlaku pada rentang suhu yang diuji.

Pakai:
  python3 analisis/kalibrasi.py --feeds data/feeds_<tanggal>.csv [--ref data/kalibrasi_manual.csv]
Hanya pustaka standar Python.
"""
import argparse
import csv
import os
import statistics as st
from datetime import datetime, timedelta, timezone

WIB = timezone(timedelta(hours=7))
JENDELA = timedelta(minutes=2)
AKURASI = {"suhu": 2.0, "rh": 5.0}


def waktu(s):
    s = s.strip()
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S" if len(s) > 16 else "%Y-%m-%d %H:%M")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feeds", required=True)
    ap.add_argument("--ref", default="data/kalibrasi_manual.csv")
    ap.add_argument("--out", default="analisis/hasil")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    data = []
    for r in csv.DictReader(open(a.feeds)):
        try:
            t = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")).astimezone(WIB).replace(tzinfo=None)
            data.append((t, float(r["field1"]), float(r["field2"])))
        except (ValueError, KeyError):
            continue

    baris, err = [], {"suhu": [], "rh": []}
    for r in csv.DictReader(open(a.ref)):
        t = waktu(r["waktu_wib"])
        win = [(s, h) for ti, s, h in data if abs(ti - t) <= JENDELA]
        if not win:
            baris.append(f"{r['waktu_wib']}: tidak ada data DHT11 dalam ±2 menit — dilewati")
            continue
        ds, dh = st.mean(s for s, _ in win), st.mean(h for _, h in win)
        es = ds - float(r["ref_suhu_c"])
        err["suhu"].append(es)
        teks = f"{r['waktu_wib']}  DHT11 {ds:5.2f} °C vs ref {float(r['ref_suhu_c']):5.2f} °C (e {es:+.2f})"
        if r.get("ref_rh", "").strip():
            eh = dh - float(r["ref_rh"])
            err["rh"].append(eh)
            teks += f" | DHT11 {dh:5.1f} %RH vs ref {float(r['ref_rh']):5.1f} %RH (e {eh:+.1f})"
        baris.append(teks + f"  [n={len(win)}, {r.get('alat', '')}]")

    L = ["Perbandingan DHT11 vs alat pembanding (rerata DHT11 ±2 menit)"] + baris + [""]
    for k, satuan in (("suhu", "°C"), ("rh", "%RH")):
        e = err[k]
        if not e:
            continue
        sd = st.stdev(e) if len(e) > 1 else 0.0
        mae = st.mean(abs(x) for x in e)
        mx = max(abs(x) for x in e)
        ok = all(abs(x) <= AKURASI[k] for x in e)
        L.append(f"{k}: n={len(e)} bias={st.mean(e):+.2f} {satuan} SD={sd:.2f} MAE={mae:.2f} |e|maks={mx:.2f} "
                 f"-> {'DALAM' if ok else 'DI LUAR'} akurasi datasheet ±{AKURASI[k]:.0f} {satuan}; "
                 f"koreksi offset = {-st.mean(e):+.2f} {satuan}")
    txt = "\n".join(L)
    print(txt)
    open(os.path.join(a.out, "kalibrasi.txt"), "w").write(txt + "\n")


if __name__ == "__main__":
    main()
