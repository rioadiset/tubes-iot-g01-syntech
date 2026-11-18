#!/usr/bin/env python3
"""
analisis_A.py — ringkasan & grafik Bagian A dari dataset_berlabel.csv.

Keluaran (folder analisis/hasil/):
  ringkasan.txt              kelengkapan, celah, reboot, RSSI, statistik per kelas
  01_timeseries.png          suhu & kelembapan + arsiran label
  02_boxplot_kelas.png       sebaran suhu & kelembapan per label_utama (data latih)
  03_rssi.png                RSSI terhadap waktu
  04_kelengkapan_harian.png  kelengkapan sampel per hari

Pakai:
  python3 analisis/analisis_A.py --data data/dataset_berlabel.csv
Butuh: matplotlib  (sudo apt install python3-matplotlib)
"""
import argparse
import csv
import os
import statistics as st
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

FMT = "%Y-%m-%d %H:%M:%S"
INTERVAL = 30
WARNA = {"dual_ac": "#3b82f6", "occupied": "#f59e0b", "campuran": "#a855f7", "anomali": "#9ca3af"}
KELAS_LATIH = ["idle", "dual_ac", "occupied"]


def f(x):
    return float(x) if x not in ("", None) else None


def segmen(rows, key):
    """Gabungkan sampel berurutan dengan label sama menjadi (mulai, selesai, label)."""
    out, cur = [], None
    for r in rows:
        lab = r[key]
        if cur and cur[2] == lab and (r["t"] - cur[1]).total_seconds() <= 3 * INTERVAL:
            cur[1] = r["t"]
        else:
            if cur:
                out.append(tuple(cur))
            cur = [r["t"], r["t"], lab]
    if cur:
        out.append(tuple(cur))
    return out


def ringkas(v):
    return f"n={len(v):5d}  mean={st.mean(v):6.2f}  sd={st.pstdev(v):5.2f}  min={min(v):5.1f}  max={max(v):5.1f}" if v else "n=0"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/dataset_berlabel.csv")
    ap.add_argument("--start", default="2026-11-12 00:00:00")
    ap.add_argument("--end", default="2026-11-19 00:00:00")
    ap.add_argument("--out", default="analisis/hasil")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    t0, t1 = datetime.strptime(a.start, FMT), datetime.strptime(a.end, FMT)

    rows = []
    with open(a.data, newline="") as fh:
        for r in csv.DictReader(fh):
            r["t"] = datetime.strptime(r["waktu_wib"], FMT)
            rows.append(r)
    rows.sort(key=lambda r: r["t"])

    L = []
    expected = (t1 - t0).total_seconds() / INTERVAL
    L.append(f"Periode       : {a.start} s.d. {a.end} WIB")
    L.append(f"Kelengkapan   : {len(rows)} / {expected:.0f} = {len(rows) / expected * 100:.2f} %")

    # celah & reboot
    gaps, reboots = [], []
    for p, q in zip(rows, rows[1:]):
        g = (q["t"] - p["t"]).total_seconds()
        if g > 2 * INTERVAL + 5:
            gaps.append((p["t"], q["t"], g))
        if int(q["uptime_s"] or 0) < int(p["uptime_s"] or 0):
            reboots.append(q["t"])
    L.append(f"Celah > 65 s  : {len(gaps)} kali, total {sum(g for *_, g in gaps) / 60:.1f} menit")
    for s, e, g in sorted(gaps, key=lambda x: -x[2])[:10]:
        L.append(f"   {s:%m-%d %H:%M:%S} -> {e:%H:%M:%S}  ({g:.0f} s)")
    L.append(f"Reboot        : {len(reboots)} kali {[f'{x:%m-%d %H:%M}' for x in reboots]}")
    L.append(f"Sensor gagal  : {sum(1 for r in rows if r['status_sensor'] == '0')} sampel")
    L.append(f"Gagal kirim   : {int(rows[-1]['err_count']) - int(rows[0]['err_count'])} (selisih err_count)")
    rssi = [int(r["rssi_dbm"]) for r in rows if r["rssi_dbm"]]
    L.append(f"RSSI (dBm)    : {ringkas(rssi)}")

    # label
    L.append("\nSampel per label_utama : " + str(dict(Counter(r["label_utama"] for r in rows))))
    latih = [r for r in rows if r["label_utama"] in KELAS_LATIH and r["transisi"] == "0"]
    L.append(f"Data latih (tanpa campuran/anomali/transisi): {len(latih)} sampel, "
             f"dikecualikan {len(rows) - len(latih)}")
    L.append("\nStatistik per kelas (data latih):")
    for k in KELAS_LATIH:
        sub = [r for r in latih if r["label_utama"] == k]
        L.append(f"  {k:9s} suhu_bulat : {ringkas([f(r['suhu_bulat_c']) for r in sub if r['suhu_bulat_c']])}")
        L.append(f"  {'':9s} kelembapan : {ringkas([f(r['kelembapan_rh']) for r in sub if r['kelembapan_rh']])}")
    ev = defaultdict(set)
    for r in rows:
        for e in filter(None, r["event_ids"].split(";")):
            ev[e].add(r["label_kombinasi"])
    L.append(f"\nJumlah event dengan sampel di periode: {len(ev)}")

    txt = "\n".join(L)
    print(txt)
    with open(os.path.join(a.out, "ringkasan.txt"), "w") as fh:
        fh.write(txt + "\n")

    T = [r["t"] for r in rows]
    fmt = mdates.DateFormatter("%d/%m\n%H:%M")

    # 01 timeseries
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
    ax1.plot(T, [f(r["suhu_c"]) for r in rows], lw=0.4, color="#ef4444", alpha=0.35, label="suhu mentah")
    ax1.plot(T, [f(r["suhu_bulat_c"]) for r in rows], lw=0.9, color="#b91c1c", label="suhu dibulatkan")
    ax2.plot(T, [f(r["kelembapan_rh"]) for r in rows], lw=0.8, color="#0e7490", label="kelembapan")
    for s, e, lab in segmen(rows, "label_utama"):
        if lab in WARNA:
            for ax in (ax1, ax2):
                ax.axvspan(s, e + timedelta(seconds=INTERVAL), color=WARNA[lab], alpha=0.18, lw=0)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c, alpha=0.3) for c in WARNA.values()]
    ax1.legend(handles + ax1.get_legend_handles_labels()[0], list(WARNA) + ["suhu mentah", "suhu dibulatkan"],
               loc="upper left", ncol=6, fontsize=8)
    ax1.set_ylabel("Suhu (°C)")
    ax2.set_ylabel("Kelembapan (%RH)")
    ax2.xaxis.set_major_formatter(fmt)
    ax1.set_title("Suhu & kelembapan ruang server (arsiran = label; putih = idle)")
    fig.tight_layout()
    fig.savefig(os.path.join(a.out, "01_timeseries.png"), dpi=150)
    plt.close(fig)

    # 02 boxplot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
    for ax, col, yl in ((ax1, "suhu_bulat_c", "Suhu (°C)"), (ax2, "kelembapan_rh", "Kelembapan (%RH)")):
        data = [[f(r[col]) for r in latih if r["label_utama"] == k and r[col]] for k in KELAS_LATIH]
        ax.boxplot([d or [float("nan")] for d in data], tick_labels=KELAS_LATIH)
        ax.set_ylabel(yl)
    fig.suptitle("Sebaran per kelas (data latih)")
    fig.tight_layout()
    fig.savefig(os.path.join(a.out, "02_boxplot_kelas.png"), dpi=150)
    plt.close(fig)

    # 03 RSSI
    fig, ax = plt.subplots(figsize=(14, 3))
    ax.plot(T, [int(r["rssi_dbm"]) for r in rows], lw=0.6, color="#16a34a")
    for s, e, _ in gaps:
        ax.axvspan(s, e, color="#ef4444", alpha=0.4)
    ax.set_ylabel("RSSI (dBm)")
    ax.set_title("RSSI terhadap waktu (merah = celah data)")
    ax.xaxis.set_major_formatter(fmt)
    fig.tight_layout()
    fig.savefig(os.path.join(a.out, "03_rssi.png"), dpi=150)
    plt.close(fig)

    # 04 kelengkapan harian
    per = Counter(r["t"].date() for r in rows)
    days, d = [], t0.date()
    while d < t1.date() or (d == t1.date() and t1.time() > datetime.min.time()):
        days.append(d)
        d += timedelta(days=1)
    pct = [per.get(x, 0) / (86400 / INTERVAL) * 100 for x in days]
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.bar([x.strftime("%a %d/%m") for x in days], pct, color="#64748b")
    ax.axhline(95, ls="--", color="#ef4444", lw=1)
    ax.set_ylim(min(80, min(pct) - 2), 101)
    ax.set_ylabel("Kelengkapan (%)")
    ax.set_title("Kelengkapan sampel per hari (garis = 95 %)")
    fig.tight_layout()
    fig.savefig(os.path.join(a.out, "04_kelengkapan_harian.png"), dpi=150)
    plt.close(fig)
    print(f"\nGrafik tersimpan di {a.out}/")


if __name__ == "__main__":
    main()
