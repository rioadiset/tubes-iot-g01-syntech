#!/usr/bin/env python3
"""
pcap_overhead.py — verifikasi overhead dari tangkapan Wireshark (wokwi.pcap).

Menghitung per protokol (HTTP port 80, MQTT port 1883):
  jumlah frame, total byte frame, byte payload TCP, byte header (frame - payload TCP),
  jumlah handshake TCP (SYN), dan jumlah paket MQTT per jenis (PUBLISH, PUBACK, ...).

Pakai:
  python3 bagianB/analisis/pcap_overhead.py bagianB/data/wokwi.pcap ["YYYY-MM-DD HH:MM:SS"]
(argumen kedua opsional: hanya hitung paket sejak waktu WIB tsb, untuk membuang percobaan awal)
Hanya pustaka standar Python. Jika jenis link tidak dikenali, buka file di Wireshark
(Statistics -> Conversations / Protocol Hierarchy) sebagai gantinya.
"""
import struct
import sys
from collections import Counter, defaultdict

MQTT_TYPE = {1: "CONNECT", 2: "CONNACK", 3: "PUBLISH", 4: "PUBACK", 8: "SUBSCRIBE", 9: "SUBACK",
             10: "UNSUBSCRIBE", 11: "UNSUBACK", 12: "PINGREQ", 13: "PINGRESP", 14: "DISCONNECT"}


def l3_offset(link, pkt):
    if link == 1:                      # Ethernet
        et = struct.unpack("!H", pkt[12:14])[0]
        return 14 if et == 0x0800 else None
    if link in (101, 228):             # raw IPv4
        return 0
    if link == 113:                    # Linux cooked (SLL)
        return 16
    if link in (105, 127):             # 802.11 (+radiotap)
        off = struct.unpack("<H", pkt[2:4])[0] if link == 127 else 0
        fc = pkt[off]
        hdr = 24 + (2 if (fc & 0xF0) == 0x80 else 0)   # QoS data
        snap = off + hdr
        return snap + 8 if pkt[snap:snap + 3] == b"\xaa\xaa\x03" else None
    return None


def mqtt_types(data):
    out, i = [], 0
    while i < len(data):
        t = data[i] >> 4
        mult, rl, j = 1, 0, i + 1
        while j < len(data):
            b = data[j]
            rl += (b & 127) * mult
            mult *= 128
            j += 1
            if not b & 128:
                break
        if j + rl > len(data):
            break
        out.append(MQTT_TYPE.get(t, f"type{t}"))
        i = j + rl
    return out


def iter_pcapng(raw):
    """Hasilkan (linktype, orig_len, data, ts_detik) dari file pcapng (keluaran default tshark)."""
    pos, links, endian, tsres = 0, [], "<", []
    while pos + 12 <= len(raw):
        btype = struct.unpack(endian + "I", raw[pos:pos + 4])[0]
        if btype == 0x0A0D0D0A:                      # Section Header Block
            endian = "<" if raw[pos + 8:pos + 12] == b"\x4d\x3c\x2b\x1a" else ">"
            links, tsres = [], []
        blen = struct.unpack(endian + "I", raw[pos + 4:pos + 8])[0]
        body = raw[pos + 8:pos + blen - 4]
        if btype == 1:                               # Interface Description Block
            links.append(struct.unpack(endian + "H", body[:2])[0])
            res, o = 1e-6, 8                         # default mikrodetik; baca opsi if_tsresol (kode 9)
            while o + 4 <= len(body):
                code, olen = struct.unpack(endian + "HH", body[o:o + 4])
                if code == 0:
                    break
                if code == 9:
                    v = body[o + 4]
                    res = 2.0 ** -(v & 0x7F) if v & 0x80 else 10.0 ** -v
                o += 4 + ((olen + 3) & ~3)
            tsres.append(res)
        elif btype == 6:                             # Enhanced Packet Block
            iid, th, tl, cap, orig = struct.unpack(endian + "IIIII", body[:20])
            ts = ((th << 32) | tl) * tsres[iid]
            yield links[iid], orig, body[20:20 + cap], ts
        pos += blen


def iter_pcap(raw):
    endian = "<" if raw[:4] in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1") else ">"
    link = struct.unpack(endian + "I", raw[20:24])[0]
    pos = 24
    while pos + 16 <= len(raw):
        sec, usec, incl, orig = struct.unpack(endian + "IIII", raw[pos:pos + 16])
        yield link, orig, raw[pos + 16:pos + 16 + incl], sec + usec * 1e-6
        pos += 16 + incl


def main(path):
    raw = open(path, "rb").read()
    magic = raw[:4]
    if magic == b"\x0a\x0d\x0d\x0a":
        packets = iter_pcapng(raw)
    elif magic in (b"\xd4\xc3\xb2\xa1", b"\xa1\xb2\xc3\xd4", b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d"):
        packets = iter_pcap(raw)
    else:
        sys.exit("Format file tidak dikenali (bukan pcap/pcapng).")
    stat, mq, link = defaultdict(Counter), Counter(), None
    streams, nextseq = defaultdict(bytearray), {}   # reassembly per arah koneksi MQTT
    for link, orig, pkt, ts in packets:
        if ts < SEJAK:
            continue
        off = l3_offset(link, pkt)
        if off is None or len(pkt) < off + 20 or pkt[off] >> 4 != 4 or pkt[off + 9] != 6:
            continue
        ihl = (pkt[off] & 15) * 4
        tcp = off + ihl
        sp, dp, seqn = struct.unpack("!HHI", pkt[tcp:tcp + 8])
        thl = (pkt[tcp + 12] >> 4) * 4
        flags = pkt[tcp + 13]
        iplen = struct.unpack("!H", pkt[off + 2:off + 4])[0]
        payload = iplen - ihl - thl
        proto = "HTTP" if {80, 8080} & {sp, dp} else "MQTT" if 1883 in (sp, dp) else None
        if not proto:
            continue
        s = stat[proto]
        s["frame"] += 1
        s["byte_frame"] += orig
        s["byte_ip"] += iplen
        s["payload_tcp"] += payload
        s["syn"] += 1 if flags & 0x02 and not flags & 0x10 else 0
        s["ack_kosong"] += 1 if payload == 0 else 0
        if proto == "MQTT" and payload > 0:
            key = (pkt[off + 12:off + 20], sp, dp)
            if nextseq.get(key, seqn) == seqn:          # abaikan retransmisi / segmen tidak berurutan
                streams[key] += pkt[tcp + thl:tcp + thl + payload]
                nextseq[key] = (seqn + payload) & 0xFFFFFFFF
            elif key not in nextseq:
                nextseq[key] = seqn

    for buf in streams.values():
        mq.update(mqtt_types(bytes(buf)))
    print(f"Link type pcap: {link}")
    if not stat:
        sys.exit("Tidak ada paket TCP port 80/1883 yang terbaca. Analisis manual di Wireshark.")
    for p, s in stat.items():
        hdr = s["byte_ip"] - s["payload_tcp"]
        print(f"\n[{p}] frame={s['frame']}  byte_frame={s['byte_frame']}  byte_IP={s['byte_ip']}  "
              f"payload_TCP={s['payload_tcp']}  header_IP+TCP={hdr}  SYN={s['syn']}  ACK_kosong={s['ack_kosong']}")
        if s["payload_tcp"]:
            print(f"   rasio header IP+TCP / payload TCP = {hdr / s['payload_tcp']:.2f}")
    if mq:
        print("\nPaket MQTT per jenis:", dict(mq))
    print("\nCatatan: payload TCP HTTP sudah termasuk header HTTP; payload TCP MQTT termasuk header MQTT.")


SEJAK = 0.0

if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    if len(sys.argv) == 3:                 # opsional: abaikan paket sebelum "YYYY-MM-DD HH:MM:SS" (WIB)
        from datetime import datetime, timedelta, timezone
        SEJAK = datetime.strptime(sys.argv[2], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone(timedelta(hours=7))).timestamp()
    main(sys.argv[1])
