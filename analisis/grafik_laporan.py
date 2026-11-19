#!/usr/bin/env python3
"""
grafik_laporan.py — buat Gambar C.2 laporan: deret waktu suhu & kelembapan dengan arsiran kelas.

Masukan : data/dataset_berlabel.csv (keluaran label_dataset.py)
Keluaran: laporan/A_timeseries.png

Pakai:
  python3 analisis/grafik_laporan.py --data data/dataset_berlabel.csv --out laporan/A_timeseries.png
Butuh matplotlib.
"""
import argparse
import csv
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as md  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

WARNA = {"dual_ac": ("#58d68d", 0.25), "idle_siang": ("#f9e79f", 0.35), "anomali": ("#999999", 0.25)}


def rentang(t, rows, label):
    out, mulai = [], None
    for ti, r in zip(t, rows):
        if r["label_utama"] == label and mulai is None:
            mulai = ti
        if r["label_utama"] != label and mulai is not None:
            out.append((mulai, ti))
            mulai = None
    if mulai:
        out.append((mulai, t[-1]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/dataset_berlabel.csv")
    ap.add_argument("--out", default="laporan/A_timeseries.png")
    a = ap.parse_args()
    plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "Liberation Serif", "DejaVu Serif"]})

    rows = list(csv.DictReader(open(a.data)))
    t = [datetime.strptime(r["waktu_wib"], "%Y-%m-%d %H:%M:%S") for r in rows]
    suhu = [float(r["suhu_c"]) for r in rows]
    rh = [float(r["kelembapan_rh"]) for r in rows]

    fig, ax = plt.subplots(figsize=(10, 4.2))
    for lab, (c, al) in WARNA.items():
        for x0, x1 in rentang(t, rows, lab):
            ax.axvspan(x0, x1, color=c, alpha=al, lw=0)
    ax.plot(t, suhu, lw=0.6, color="#c0392b")
    ax2 = ax.twinx()
    ax2.plot(t, rh, lw=0.6, color="#2471a3", alpha=0.7)
    hs = [plt.Line2D([], [], color="#c0392b", label="Suhu (°C)"),
          plt.Line2D([], [], color="#2471a3", label="Kelembapan (%RH)"),
          Patch(color="#58d68d", alpha=0.4, label="dual_ac"), Patch(color="#f9e79f", alpha=0.6, label="idle_siang"),
          Patch(facecolor="white", edgecolor="#bbb", label="idle_malam"), Patch(color="#999999", alpha=0.4, label="anomali")]
    ax.legend(handles=hs, loc="upper left", fontsize=8, ncol=6, framealpha=1)
    ax.set_ylabel("Suhu (°C)")
    ax2.set_ylabel("Kelembapan (%RH)")
    ax.set_xlabel("Waktu (WIB)")
    ax.xaxis.set_major_formatter(md.DateFormatter("%d/%m %H:%M"))
    ax.set_ylim(21, 31.5)
    ax2.set_ylim(38, 62)
    ax.grid(alpha=.3)
    fig.tight_layout()
    fig.savefig(a.out, dpi=170)
    print(f"Tersimpan: {a.out}")


if __name__ == "__main__":
    main()
