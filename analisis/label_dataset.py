#!/usr/bin/env python3
"""
label_dataset.py — gabungkan data ThingSpeak dengan label_log.csv
menjadi dataset berlabel per sampel, sesuai PEDOMAN_LABEL.md.

Aturan inti (lihat PEDOMAN_LABEL.md):
  * Setiap kondisi (dual_ac, occupied, ac1_ubah, tidak_pasti) dicatat sebagai interval
    TERPISAH dan boleh tumpang tindih.
  * Per sampel dibuat kolom biner 0/1 untuk tiap kondisi (multi-label).
  * label_utama (single-label) diturunkan secara deterministik:
        0 kondisi aktif  -> idle_siang (08.00-20.00) atau idle_malam (20.00-08.00)
        1 kondisi aktif  -> nama kondisi tersebut
        >=2 kondisi aktif -> campuran   (TIDAK dipaksa ke salah satu kelas)
        ac1_ubah / tidak_pasti aktif -> anomali (dikecualikan dari pelatihan)
  * transisi = 1 untuk sampel dalam N menit setelah mulai/selesainya
    kejadian apa pun (efek termal belum stabil).

Pakai:
  python3 analisis/label_dataset.py \
      --feeds data/feeds.csv --log data/label_log.csv \
      --out data/dataset_berlabel.csv

Hanya memakai pustaka standar Python (tanpa pandas).
"""
import argparse
import csv
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

KONDISI = ["dual_ac", "occupied", "ac1_ubah", "tidak_pasti"]
ANOMALI = {"ac1_ubah", "tidak_pasti"}  # bukan kelas; penanda data dikecualikan
WIB = timezone(timedelta(hours=7))
FMT = "%Y-%m-%d %H:%M:%S"


def parse_wib(s):
    s = s.strip()
    for f in (FMT, "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            pass
    raise ValueError(f"format waktu tidak dikenal: '{s}' (pakai YYYY-MM-DD HH:MM[:SS])")


def baca_log(path, t0, t1):
    events, errors, warns = [], [], []
    with open(path, newline="") as f:
        for i, r in enumerate(csv.DictReader(f), start=2):
            try:
                k = r["kondisi"].strip()
                a = parse_wib(r["mulai_wib"])
                if r["selesai_wib"].strip():
                    b = parse_wib(r["selesai_wib"])
                else:  # kejadian masih berlangsung -> sampai akhir periode
                    b = t1
                    warns.append(f"baris {i}: event {r['event_id']} belum punya waktu selesai (dianggap berlangsung)")
            except Exception as e:  # noqa: BLE001
                errors.append(f"baris {i}: {e}")
                continue
            if k not in KONDISI:
                errors.append(f"baris {i}: kondisi '{k}' tidak dikenal (valid: {KONDISI})")
                continue
            if b <= a:
                errors.append(f"baris {i}: selesai ({b}) tidak setelah mulai ({a})")
                continue
            if a < t0 or b > t1:
                warns.append(f"baris {i}: event {r['event_id']} sebagian/seluruhnya di luar periode rekaman")
            if not r.get("foto", "").strip():
                warns.append(f"baris {i}: event {r['event_id']} tanpa foto bukti")
            events.append({"id": r["event_id"].strip(), "k": k, "a": a, "b": b})
    # kondisi yang sama tidak boleh tumpang tindih dengan dirinya sendiri
    for k in KONDISI:
        ev = sorted((e for e in events if e["k"] == k), key=lambda e: e["a"])
        for p, q in zip(ev, ev[1:]):
            if q["a"] < p["b"]:
                errors.append(f"{k}: event {p['id']} dan {q['id']} tumpang tindih (gabungkan jadi satu event)")
    return events, errors, warns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feeds", required=True, help="CSV ekspor ThingSpeak")
    ap.add_argument("--log", required=True, help="label_log.csv")
    ap.add_argument("--out", required=True, help="CSV keluaran berlabel")
    ap.add_argument("--start", default="2026-11-11 18:00:00", help="mulai periode resmi (WIB)")
    ap.add_argument("--end", default="2026-11-18 18:00:00", help="akhir periode resmi (WIB)")
    ap.add_argument("--transisi", type=int, default=10, help="menit masa transisi setelah mulai/selesai")
    ap.add_argument("--siang", default="08:00-20:00", help="rentang jam kelas idle_siang (sisanya idle_malam)")
    a = ap.parse_args()

    t0, t1 = parse_wib(a.start), parse_wib(a.end)
    events, errors, warns = baca_log(a.log, t0, t1)
    for w in warns:
        print("PERINGATAN:", w)
    if errors:
        for e in errors:
            print("ERROR:", e)
        sys.exit("Perbaiki label_log.csv dulu.")

    batas = [(e["a"], e["b"]) for e in events]
    sa, sb = [tuple(map(int, x.split(":"))) for x in a.siang.split("-")]
    d = t0.date()
    while d <= t1.date():   # pergantian idle_siang <-> idle_malam juga diberi masa transisi
        for hh, mm in (sa, sb):
            x = datetime(d.year, d.month, d.day, hh, mm)
            batas.append((x, x))
        d += timedelta(days=1)
    siang = lambda t: sa <= (t.hour, t.minute) < sb
    dt_trans = timedelta(minutes=a.transisi)

    rows_out, n_label, n_trans = [], Counter(), 0
    with open(a.feeds, newline="") as f:
        for r in csv.DictReader(f):
            t = datetime.fromisoformat(r["created_at"].replace(" UTC", "+00:00")).astimezone(WIB).replace(tzinfo=None)
            if t < t0 or t >= t1:
                continue
            aktif = {k: 0 for k in KONDISI}
            ids = []
            for e in events:
                if e["a"] <= t < e["b"]:
                    aktif[e["k"]] = 1
                    ids.append(e["id"])
            n = sum(aktif.values())
            on = [k for k in KONDISI if aktif[k]]
            utama = ("anomali" if any(aktif[k] for k in ANOMALI)
                     else ("idle_siang" if siang(t) else "idle_malam") if n == 0
                     else on[0] if n == 1 else "campuran")
            trans = int(any(0 <= (t - x).total_seconds() < dt_trans.total_seconds()
                            for ab in batas for x in ab))
            suhu = r["field1"]
            rows_out.append({
                "waktu_wib": t.strftime(FMT), "entry_id": r["entry_id"], "seq": r["field4"],
                "suhu_c": suhu, "suhu_bulat_c": math.floor(float(suhu)) if suhu else "",
                "kelembapan_rh": r["field2"], "rssi_dbm": r["field3"], "uptime_s": r["field5"],
                "err_count": r["field6"], "status_sensor": r["field7"],
                **aktif, "n_kondisi": n, "label_kombinasi": "+".join(on) or utama,
                "label_utama": utama, "transisi": trans, "event_ids": ";".join(ids),
            })
            n_label[utama] += 1
            n_trans += trans

    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        w.writerows(rows_out)

    # ---------- ringkasan ----------
    print(f"\nSampel dalam periode: {len(rows_out)}  -> {a.out}")
    print("Sampel per label_utama:", dict(n_label))
    print(f"Sampel transisi ({a.transisi} menit): {n_trans}")
    print("\nKejadian per kondisi (syarat >= 5):")
    for k in KONDISI:
        ev = [e for e in events if e["k"] == k]
        murni = [e for e in ev if not any(o["k"] != k and o["a"] < e["b"] and e["a"] < o["b"] for o in events)]
        status = "bukan kelas" if k in ANOMALI else "OK" if len(ev) >= 5 else "KURANG"
        print(f"  {k:10s} total={len(ev):2d}  murni(tanpa overlap)={len(murni):2d}  [{status}]")
    overl = defaultdict(int)
    for row in rows_out:
        if row["n_kondisi"] >= 2:
            overl[row["label_kombinasi"]] += 1
    if overl:
        print("Kombinasi tumpang tindih (sampel):", dict(overl))


if __name__ == "__main__":
    main()
