#!/usr/bin/env bash
# label.sh — catat kejadian berlabel secara real-time (jam WIB otomatis)
#
# Pakai:
#   ./label.sh start <kondisi> ["catatan"]
#   ./label.sh stop  <kondisi> <nama_foto> ["catatan tambahan"]
#   ./label.sh status
#
# Kondisi yang valid: dual_ac | occupied | ac1_ubah | tidak_pasti
# Setiap kondisi dicatat TERPISAH. Dua kondisi boleh aktif bersamaan
# (mis. occupied + dual_ac) -> masing-masing di-start/stop sendiri.
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$DIR/data/label_log.csv"
STATE="$DIR/label/.state"
PIC="${PIC:-${USER:-anon}}"
VALID="dual_ac occupied ac1_ubah tidak_pasti"
now() { TZ=Asia/Jakarta date '+%F %T'; }
mkdir -p "$STATE"
[ -f "$LOG" ] || echo "event_id,kondisi,mulai_wib,selesai_wib,foto,pic,catatan" > "$LOG"

cmd="${1:-status}"; kond="${2:-}"
if [ "$cmd" != "status" ] && [[ " $VALID " != *" $kond "* ]]; then
  echo "Kondisi tidak valid: '$kond'. Pilih: $VALID"; exit 1
fi

case "$cmd" in
  start)
    [ -f "$STATE/$kond" ] && { echo "$kond sudah aktif sejak $(head -1 "$STATE/$kond")"; exit 1; }
    printf '%s\n%s\n' "$(now)" "${3:-}" > "$STATE/$kond"
    echo "START $kond @ $(head -1 "$STATE/$kond")"
    ls "$STATE" | grep -v "^$kond$" | sed 's/^/  (kondisi lain yang sedang aktif: /;s/$/)/' || true
    ;;
  stop)
    [ -f "$STATE/$kond" ] || { echo "$kond belum di-start"; exit 1; }
    foto="${3:?nama file foto wajib diisi}"
    mulai="$(sed -n 1p "$STATE/$kond")"; cat1="$(sed -n 2p "$STATE/$kond")"
    id=$(( $(wc -l < "$LOG") ))
    note="$(echo "$cat1 ${4:-}" | sed 's/,/;/g;s/^ *//;s/ *$//')"
    echo "$id,$kond,$mulai,$(now),$foto,$PIC,$note" >> "$LOG"
    rm "$STATE/$kond"
    echo "STOP  $kond -> event $id tercatat ($mulai s.d. $(now))"
    ;;
  status)
    if [ -z "$(ls -A "$STATE")" ]; then echo "Tidak ada kondisi aktif (= idle)"; else
      for f in "$STATE"/*; do echo "AKTIF: $(basename "$f") sejak $(head -1 "$f")"; done; fi
    echo "Total event tercatat: $(( $(wc -l < "$LOG") - 1 ))"
    ;;
  *) echo "Perintah: start | stop | status"; exit 1;;
esac
