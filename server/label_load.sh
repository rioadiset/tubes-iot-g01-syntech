#!/usr/bin/env bash
# label_load.sh — beri beban CPU server + catat label server_load otomatis
# Pakai: ./label_load.sh 30m   (beri jeda >= 1 jam antar kejadian)
DUR=${1:-30m}
LOG="$HOME/label_log.csv"
[ -f "$LOG" ] || echo "event_id,class,start_wib,end_wib,ac1_setpoint_c,ac2_on,photo_file,pic,notes" > "$LOG"
ID=$(( $(wc -l < "$LOG") ))
START=$(date '+%F %T')
stress-ng --cpu 0 --timeout "$DUR" --metrics-brief
END=$(date '+%F %T')
echo "$ID,server_load,$START,$END,,,,Rio,stress-ng cpu $DUR" >> "$LOG"
echo "Tercatat: event $ID ($START -> $END). Lengkapi setpoint AC & nama foto di $LOG"
