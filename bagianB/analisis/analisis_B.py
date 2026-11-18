#!/usr/bin/env python3
"""
analisis_B.py — olah log Serial Bagian B (S1–S6) menjadi metrik & grafik.

Masukan : salinan Serial Monitor Wokwi apa adanya (boleh bercampur baris '#').
Keluaran (folder bagianB/hasil/):
  log_B.csv          log per pesan (baris DATA saja) -> data mentah untuk dikumpulkan
  ringkasan_B.txt    RTT (mean, median, sd, P95), PDR, overhead per skenario
  tabel_B.md         tabel siap tempel ke laporan
  B1_boxplot.png     boxplot RTT per skenario
  B2_cdf.png         CDF RTT per skenario

Pakai:
  python3 bagianB/analisis/analisis_B.py --log bagianB/data/serial_wokwi.txt

Overhead dihitung dari spesifikasi protokol (MQTT 3.1.1 OASIS §2–3) dan
ukuran header HTTP yang terukur langsung oleh firmware (req_b, resp_b).
Verifikasi dengan Wireshark: bagianB/analisis/pcap_overhead.py.
"""
import argparse
import csv
import math
import os
import re
import statistics as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

KOLOM = ["skenario", "seq", "payload_b", "protokol", "status", "rtt_ms", "req_b", "resp_b",
         "http_code", "reconn", "rssi_dbm", "t_ms", "suhu_c", "rh"]
NAMA = {"S1": "HTTP 20 B", "S2": "HTTP 500 B", "S3": "MQTT QoS0 20 B",
        "S4": "MQTT QoS0 500 B", "S5": "MQTT QoS1 20 B", "S6": "MQTT QoS1 500 B"}
TCPIP = 40  # header IPv4 (20 B, RFC 791) + TCP (20 B, RFC 9293) minimum per segmen


def rl_bytes(n):
    """Jumlah byte 'Remaining Length' MQTT (variable byte integer)."""
    return 1 if n < 128 else 2 if n < 16384 else 3 if n < 2097152 else 4


def mqtt_publish_size(topic_len, payload, qos):
    rl = 2 + topic_len + (2 if qos > 0 else 0) + payload
    return 1 + rl_bytes(rl) + rl


def p95(v):
    s = sorted(v)
    return s[math.ceil(0.95 * len(s)) - 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--out", default="bagianB/hasil")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    rows, meta, sums = [], [], {}
    topic = ""
    for line in open(a.log, encoding="utf-8", errors="ignore"):
        line = line.strip()
        if line.startswith("#"):
            meta.append(line)
            m = re.search(r"topic=(\S+)", line)
            if m:
                topic = m.group(1)
        elif line.startswith("DATA,"):
            p = line.split(",")[1:]
            if len(p) in (len(KOLOM), len(KOLOM) - 2):     # log lama tanpa kolom sensor tetap diterima
                rows.append(dict(zip(KOLOM, p + [""] * (len(KOLOM) - len(p)))))
        elif line.startswith("SUM,"):
            p = line.split(",")
            sums[p[1]] = p[2:]
    if not rows:
        raise SystemExit("Tidak ada baris DATA di log.")

    # duplikat seq (mis. log tersalin dua kali) -> ambil yang pertama
    seen, uniq = set(), []
    for r in rows:
        k = (r["skenario"], r["seq"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    rows = uniq

    with open(os.path.join(a.out, "log_B.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=KOLOM)
        w.writeheader()
        w.writerows(rows)

    tlen = len(topic.encode())
    hasil = []
    for sid in NAMA:
        sub = [r for r in rows if r["skenario"] == sid]
        if not sub:
            continue
        ok = [float(r["rtt_ms"]) for r in sub if r["status"] == "ok"]
        P = int(sub[0]["payload_b"])
        proto = sub[0]["protokol"]
        if proto == "http":
            reqh = st.mean(int(r["req_b"]) for r in sub) - P
            resp = st.mean(int(r["resp_b"]) for r in sub if int(r["resp_b"]) > 0) if any(int(r["resp_b"]) for r in sub) else 0
            app_oh = reqh + resp
            seg = 2  # request + response
            rinci = f"header request {reqh:.0f} B + response {resp:.0f} B"
        else:
            q = 1 if proto == "mqtt1" else 0
            pub = mqtt_publish_size(tlen, P, q)
            app_oh = (pub - P) + (4 if q else 0)
            seg = 2 if q else 1
            rinci = f"header PUBLISH {pub - P} B" + (" + PUBACK 4 B" if q else "")
        h = {
            "id": sid, "nama": NAMA[sid], "P": P, "kirim": len(sub), "terima": len(ok),
            "pdr": len(ok) / len(sub) * 100,
            "mean": st.mean(ok) if ok else float("nan"), "median": st.median(ok) if ok else float("nan"),
            "sd": st.pstdev(ok) if ok else float("nan"), "p95": p95(ok) if ok else float("nan"),
            "min": min(ok) if ok else float("nan"), "max": max(ok) if ok else float("nan"),
            "reconn": sum(int(r["reconn"]) for r in sub),
            "app_oh": app_oh, "oh_ratio": app_oh / P, "tot_oh": app_oh + seg * TCPIP,
            "rinci": rinci, "rtt": ok,
        }
        hasil.append(h)

    L = ["Metadata eksperimen:"] + ["  " + m for m in meta[:8]]
    L.append(f"  panjang topik MQTT = {tlen} B")
    sens = [(float(r["suhu_c"]), float(r["rh"])) for r in rows if r["suhu_c"] not in ("", "nan")]
    if sens:
        L.append(f"  bacaan sensor dalam payload: {len(sens)} sampel, suhu {min(t for t, _ in sens):.1f}-{max(t for t, _ in sens):.1f} C, "
                 f"RH {min(h for _, h in sens):.1f}-{max(h for _, h in sens):.1f} %")
    L.append("")
    L.append(f"{'Sk':3s} {'Nama':16s} {'kirim':>5s} {'terima':>6s} {'PDR%':>6s} {'mean':>8s} {'median':>8s} "
             f"{'sd':>7s} {'P95':>8s} {'max':>8s} {'reconn':>6s} {'OH app':>7s} {'OH/P':>6s}")
    for h in hasil:
        L.append(f"{h['id']:3s} {h['nama']:16s} {h['kirim']:5d} {h['terima']:6d} {h['pdr']:6.1f} {h['mean']:8.2f} "
                 f"{h['median']:8.2f} {h['sd']:7.2f} {h['p95']:8.2f} {h['max']:8.2f} {h['reconn']:6d} "
                 f"{h['app_oh']:7.0f} {h['oh_ratio']:6.2f}")
    L.append("\nRTT dalam ms. OH app = byte header lapisan aplikasi per pesan terkirim; OH/P = OH app ÷ payload.")
    for h in hasil:
        L.append(f"  {h['id']}: {h['rinci']}; + TCP/IP min {TCPIP} B × segmen data -> ±{h['tot_oh']:.0f} B")
    if sums:
        L.append("\nCek silang SUM dari perangkat (n_kirim, n_ok, mean, median, sd, p95):")
        for k, v in sums.items():
            L.append(f"  {k}: {v}")
    txt = "\n".join(L)
    print(txt)
    open(os.path.join(a.out, "ringkasan_B.txt"), "w").write(txt + "\n")

    md = ["| Skenario | Payload | Terkirim | Diterima | PDR (%) | Mean (ms) | Median (ms) | SD (ms) | P95 (ms) | Overhead aplikasi (B) | Overhead/payload |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for h in hasil:
        md.append(f"| {h['id']} {h['nama']} | {h['P']} B | {h['kirim']} | {h['terima']} | {h['pdr']:.1f} | {h['mean']:.2f} | "
                  f"{h['median']:.2f} | {h['sd']:.2f} | {h['p95']:.2f} | {h['app_oh']:.0f} | {h['oh_ratio']:.2f} |")
    open(os.path.join(a.out, "tabel_B.md"), "w").write("\n".join(md) + "\n")

    lab = [f"{h['id']}\n{h['nama']}" for h in hasil]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.boxplot([h["rtt"] or [float("nan")] for h in hasil], tick_labels=lab, showfliers=True)
    ax.set_yscale("log")
    ax.set_ylabel("RTT (ms, skala log)")
    ax.set_title("Distribusi RTT per skenario")
    fig.tight_layout()
    fig.savefig(os.path.join(a.out, "B1_boxplot.png"), dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    for h in hasil:
        s = sorted(h["rtt"])
        if s:
            ax.step(s, [(i + 1) / len(s) for i in range(len(s))], where="post", label=f"{h['id']} {h['nama']}")
    ax.set_xscale("log")
    ax.set_xlabel("RTT (ms, skala log)")
    ax.set_ylabel("Proporsi pesan")
    ax.set_title("CDF RTT per skenario")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(a.out, "B2_cdf.png"), dpi=150)
    plt.close(fig)
    print(f"\nHasil tersimpan di {a.out}/")


if __name__ == "__main__":
    main()
