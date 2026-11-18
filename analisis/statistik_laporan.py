#!/usr/bin/env python3
"""
statistik_laporan.py — hitung semua angka Bagian A yang dikutip di laporan.

Masukan : data/dataset_berlabel.csv (keluaran label_dataset.py) dan data/label_log.csv
Keluaran: analisis/hasil/statistik_laporan.json  (dibaca skrip pengisi laporan)
          analisis/hasil/statistik_laporan.txt   (ringkasan untuk dibaca manusia)

Pakai:
  python3 analisis/statistik_laporan.py --data data/dataset_berlabel.csv --log data/label_log.csv \
      [--start "2026-11-12 00:00:00"] [--end "2026-11-19 00:00:00"]

Metode:
  * Kelengkapan = received / expected x 100; expected = detik dalam [start, end) / 30.
    Jika data berakhir sebelum --end, end = waktu sampel terakhir + 30 s (dilaporkan sebagai "per tanggal").
  * SD = simpangan baku sampel (n-1).
  * Celah = selisih antarsampel > 65 s. Outlier = |z| > 3 terhadap rerata periode.
  * Respons AC #2 = rerata suhu 30 menit sebelum vs 30-60 menit sesudah setiap nyala/mati.
  * Perbandingan kelas dicocokkan per jam-dalam-hari (hour-matched) agar tidak bias pola harian.
Hanya pustaka standar Python.
"""
import argparse
import csv
import json
import os
import statistics as st
from collections import Counter, defaultdict
from datetime import datetime, timedelta

FMT = "%Y-%m-%d %H:%M:%S"
DT = 30


def p(s):
    return datetime.strptime(s.strip(), FMT if len(s.strip()) > 16 else "%Y-%m-%d %H:%M")


def desc(v):
    return {"n": len(v), "min": min(v), "max": max(v), "mean": st.mean(v), "sd": st.stdev(v)} if len(v) > 1 else {"n": len(v)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/dataset_berlabel.csv")
    ap.add_argument("--log", default="data/label_log.csv")
    ap.add_argument("--start", default="2026-11-12 00:00:00")
    ap.add_argument("--end", default="2026-11-19 00:00:00")
    ap.add_argument("--out", default="analisis/hasil")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    R = list(csv.DictReader(open(a.data)))
    t = [p(r["waktu_wib"]) for r in R]
    T = [float(r["suhu_c"]) for r in R]
    H = [float(r["kelembapan_rh"]) for r in R]
    S = [float(r["rssi_dbm"]) for r in R]
    t0, t1 = p(a.start), p(a.end)
    lengkap_periode = t[-1] + timedelta(seconds=DT) >= t1
    tend = t1 if lengkap_periode else t[-1] + timedelta(seconds=DT)
    expected = int((tend - t0).total_seconds() // DT)
    N = {"start": a.start, "end": tend.strftime(FMT), "data_terakhir": t[-1].strftime(FMT),
         "periode_penuh": lengkap_periode, "expected": expected, "received": len(R),
         "kelengkapan": len(R) / expected * 100, "expected_penuh": int((t1 - t0).total_seconds() // DT)}

    gaps = [(x.strftime(FMT), y.strftime(FMT), (y - x).total_seconds()) for x, y in zip(t, t[1:]) if (y - x).total_seconds() > 65]
    up = [int(r["uptime_s"]) for r in R]
    seq = [int(r["seq"]) for r in R]
    N.update(celah=gaps, celah_maks=max((y - x).total_seconds() for x, y in zip(t, t[1:])),
             reboot=sum(1 for x, y in zip(up, up[1:]) if y < x),
             seq_hilang=(seq[-1] - seq[0] + 1) - len(seq),
             sensor_gagal=sum(1 for r in R if r["status_sensor"] != "1"),
             err_kirim=int(R[-1]["err_count"]) - int(R[0]["err_count"]))

    N["stat"] = {"suhu": desc(T), "suhu_bulat": desc([float(r["suhu_bulat_c"]) for r in R]),
                 "rh": desc(H), "rssi": desc(S)}

    # outlier |z|>3, dikelompokkan per jam
    out = {}
    for nama, v in (("suhu", T), ("rh", H), ("rssi", S)):
        m, s = st.mean(v), st.stdev(v)
        idx = [i for i, x in enumerate(v) if abs(x - m) > 3 * s]
        jam = Counter(t[i].strftime("%Y-%m-%d %H") for i in idx)
        out[nama] = {"n": len(idx), "batas_bawah": m - 3 * s, "batas_atas": m + 3 * s,
                     "nilai": sorted({v[i] for i in idx}), "jam_terbanyak": jam.most_common(6)}
    N["outlier"] = out
    jumps = [(i, T[i + 1] - T[i]) for i in range(len(T) - 1) if abs(T[i + 1] - T[i]) >= 1.5]
    N["lonjakan_suhu"] = {"n": len(jumps), "semua_lintas_bulat": all(int(T[i]) != int(T[i + 1]) for i, _ in jumps)}

    # label & kelas
    N["label_utama"] = dict(Counter(r["label_utama"] for r in R))
    N["transisi"] = sum(int(r["transisi"]) for r in R)
    latih = [i for i, r in enumerate(R) if r["label_utama"] in ("idle", "dual_ac", "occupied") and r["transisi"] == "0"]
    kelas = defaultdict(list)
    for i in latih:
        kelas[R[i]["label_utama"]].append(i)
    N["kelas"] = {k: {"suhu": desc([T[i] for i in v]), "rh": desc([H[i] for i in v])} for k, v in kelas.items()}
    # idle dipecah siang (07.30-20.00) / malam
    siang = lambda x: (x.hour, x.minute) >= (7, 30) and x.hour < 20
    for nm, f in (("idle_siang", siang), ("idle_malam", lambda x: not siang(x))):
        v = [i for i in kelas["idle"] if f(t[i])]
        N["kelas"][nm] = {"suhu": desc([T[i] for i in v]), "rh": desc([H[i] for i in v])}
    # hour-matched: selisih dual_ac - idle pada jam yang sama, berbobot jumlah sampel dual_ac
    by = defaultdict(lambda: defaultdict(list))
    for i in latih:
        by[R[i]["label_utama"]][t[i].hour].append(T[i])
    num = den = 0
    perjam = {}
    for h, v in by["dual_ac"].items():
        if by["idle"].get(h):
            d = st.mean(v) - st.mean(by["idle"][h])
            perjam[h] = (st.mean(v), st.mean(by["idle"][h]), len(v), len(by["idle"][h]))
            num += d * len(v)
            den += len(v)
    N["hour_matched"] = {"selisih": num / den if den else None, "per_jam": perjam}
    for nm, (h0, h1) in (("tengah_hari", (11, 15)),):
        g = lambda k: [T[i] for i in kelas[k] if h0 <= t[i].hour < h1]
        N[nm] = {"dual_ac": desc(g("dual_ac")), "idle": desc(g("idle"))}

    # kejadian & respons AC2
    log = list(csv.DictReader(open(a.log)))
    ev = []
    for r in log:
        b = p(r["selesai_wib"]) if r["selesai_wib"].strip() else None
        ev.append({"id": r["event_id"], "k": r["kondisi"], "a": p(r["mulai_wib"]), "b": b})
    N["kejadian"] = {k: sum(1 for e in ev if e["k"] == k) for k in ("dual_ac", "occupied", "ac1_ubah", "tidak_pasti")}

    def mean_win(x, y):
        v = [T[i] for i, ti in enumerate(t) if x <= ti < y]
        return (st.mean(v), len(v)) if v else (None, 0)
    resp = []
    for e in ev:
        if e["k"] != "dual_ac":
            continue
        for aksi, w in (("nyala", e["a"]), ("mati", e["b"])):
            if w is None or w + timedelta(minutes=60) > t[-1]:
                continue
            sb, _ = mean_win(w - timedelta(minutes=30), w)
            ss, _ = mean_win(w + timedelta(minutes=30), w + timedelta(minutes=60))
            resp.append({"id": e["id"], "aksi": aksi, "waktu": w.strftime("%Y-%m-%d %H:%M"), "sebelum": sb, "sesudah": ss, "delta": ss - sb})
    N["respons_ac2"] = resp

    # segmen idle (interval AC#2 mati, tanpa kondisi lain) >= 60 menit
    seg, cur = [], None
    for i, r in enumerate(R):
        if r["label_utama"] == "idle":
            cur = cur or [t[i], t[i]]
            cur[1] = t[i]
        elif cur:
            seg.append(cur)
            cur = None
    if cur:
        seg.append(cur)
    seg = [(x.strftime("%Y-%m-%d %H:%M"), y.strftime("%Y-%m-%d %H:%M")) for x, y in seg if (y - x) >= timedelta(minutes=60)]
    N["segmen_idle"] = seg

    # uji silang dua DHT11 (Bagian B, 16 Nov 16.24-16.44)
    a0, a1 = p("2026-11-16 16:24:00"), p("2026-11-16 16:45:00")
    v = [i for i, ti in enumerate(t) if a0 <= ti < a1]
    if v:
        N["uji_silang_A"] = {"n": len(v), "suhu": st.mean([T[i] for i in v]), "rh": st.mean([H[i] for i in v])}

    json.dump(N, open(os.path.join(a.out, "statistik_laporan.json"), "w"), indent=1, default=str)
    L = [f"Periode {N['start']} s.d. {N['end']} (data terakhir {N['data_terakhir']}, periode penuh: {N['periode_penuh']})",
         f"Kelengkapan {N['received']}/{N['expected']} = {N['kelengkapan']:.2f} %  (expected periode penuh {N['expected_penuh']})",
         f"Celah>65s {len(gaps)}, celah maks {N['celah_maks']:.0f} s, reboot {N['reboot']}, seq hilang {N['seq_hilang']}, sensor gagal {N['sensor_gagal']}, gagal kirim {N['err_kirim']}"]
    for k, d in N["stat"].items():
        L.append(f"{k:10s} n={d['n']} min={d['min']} max={d['max']} mean={d['mean']:.2f} sd={d['sd']:.2f}")
    L.append(f"Outlier: { {k: (o['n'], o['jam_terbanyak'][:3]) for k, o in out.items()} }")
    L.append(f"Lonjakan suhu >=1.5: {N['lonjakan_suhu']}")
    L.append(f"Label: {N['label_utama']}  transisi={N['transisi']}  kejadian={N['kejadian']}")
    for k, d in N["kelas"].items():
        if d["suhu"]["n"] > 1:
            L.append(f"  {k:11s} suhu {d['suhu']['mean']:.2f}±{d['suhu']['sd']:.2f} (n={d['suhu']['n']})  rh {d['rh']['mean']:.2f}")
    L.append(f"Hour-matched dual_ac - idle = {N['hour_matched']['selisih']:.2f} C")
    L.append(f"Tengah hari 11-15: {N['tengah_hari']}")
    for r in resp:
        L.append(f"  AC2 {r['aksi']:5s} {r['waktu']}: {r['sebelum']:.2f} -> {r['sesudah']:.2f} ({r['delta']:+.2f})")
    L.append(f"Segmen idle >=60 menit: {len(seg)} {seg}")
    L.append(f"Uji silang: {N.get('uji_silang_A')}")
    txt = "\n".join(L)
    print(txt)
    open(os.path.join(a.out, "statistik_laporan.txt"), "w").write(txt + "\n")


if __name__ == "__main__":
    main()
