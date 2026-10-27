#!/bin/bash
# One arm of the AUDIODIV A/B on the reproduced path. Posted input only (sc3io), own pid only.
#   ad_run.sh <tag> <city> <soak s> [env K=V ...]
# Path: load <city>, Layers -> Subsuelo -> Caneria agua (pipes, AUDIO +0x9cc == 2), unpause, minimap jump to the
# y=0 edge, zoom to 5, maximize, rotate twice (y=0 becomes a front edge), zoom + twice (cityzoom x3), push
# down+right 10 x 2.5 s past y=0, slide along the edge for <soak> s, then up+left back inside the map for 75 s. ad_probe.py records the ambient state.
set -u
TAG=$1; CITY=$2; SOAK=$3; shift 3
HERE=$(cd "$(dirname "$0")" && pwd)
INST=$HERE/../../re/harness/inst_ad
APPS=/c/Users/maria/Desktop/Proyectos/Simcity_audiodiv_t/Apps
OUT=$HERE/data/$TAG
mkdir -p "$OUT"
envs=(); for kv in "$@"; do envs+=(--env "$kv"); done
PID=$(py -3.12 "$HERE/ad_launch.py" "$TAG" --city "$CITY" "${envs[@]}")
echo "[1/7] launch pid $PID PASS"
alive() { tasklist //FI "PID eq $PID" | grep -q SC3U; }
py -3.12 -c "import time; time.sleep(40)"
alive || { echo "[2/7] load DEAD"; exit 1; }
py -3.12 "$HERE/ad_setup.py" "$PID" pipes "$OUT/setup.png" > "$OUT/setup.txt" 2>&1 && echo "[2/7] setup PASS" || echo "[2/7] setup FAIL"
py -3.12 "$HERE/ad_probe.py" "$PID" $((SOAK + 200)) "$OUT/probe.jsonl" > "$OUT/probe.out" 2>&1 &
PROBE=$!
py -3.12 -c "import time; time.sleep(4)"
py -3.12 "$HERE/ad_drive.py" "$PID" "mm:3460:1871,wait:3,mm:3460:1871,wait:4,mm:3397:1811,wait:3,mm:3397:1811,wait:4" > "$OUT/drive.txt" 2>&1
alive && echo "[3/7] rotate + x3 PASS" || { echo "[3/7] rotate + x3 DEAD"; }
if alive; then
  py -3.12 "$HERE/ad_drive.py" "$PID" "down+right:10:2.5,wait:3" >> "$OUT/drive.txt" 2>&1
  alive && echo "[4/7] push past y=0 PASS (alive)" || echo "[4/7] push past y=0 DEAD"
fi
if alive; then
  py -3.12 -c "import sys; sys.path.insert(0, r'C:\Users\maria\Desktop\Proyectos\Simcity\re\tools'); import os; os.environ['SC3_PID']='$PID'; import sc3io; sc3io.grab(sc3io.game_hwnd($PID)).save(r'$(cygpath -w "$OUT")\past_edge.png')"
  t0=$(date +%s)
  while [ $(( $(date +%s) - t0 )) -lt "$SOAK" ] && alive; do
    py -3.12 "$HERE/ad_drive.py" "$PID" "right:2:2,down+right:1:2,left:2:2,down+right:1:2,wait:10" >> "$OUT/drive.txt" 2>&1
  done
  alive && echo "[5/7] soak ${SOAK} s past the edge PASS (alive)" || echo "[5/7] soak DEAD after $(( $(date +%s) - t0 )) s"
fi
if alive; then
  py -3.12 "$HERE/ad_drive.py" "$PID" "up+left:8:2.5,wait:75" >> "$OUT/drive.txt" 2>&1
  alive && echo "[6/7] back inside the map 75 s PASS (alive)" || echo "[6/7] back inside DEAD"
fi
wait $PROBE 2>/dev/null
cp "$INST"/*.log "$OUT/"
[ -f "$APPS/SC3U_stkdmp.txt" ] && mv "$APPS/SC3U_stkdmp.txt" "$OUT/"
if alive; then
  py -3.12 -c "import ctypes,sys; sys.path.insert(0, r'C:\Users\maria\Desktop\Proyectos\Simcity\re\tools'); import os; os.environ['SC3_PID']='$PID'; import sc3io; ctypes.windll.user32.PostMessageW(sc3io.game_hwnd($PID), 0x10, 0, 0)"
  py -3.12 -c "import time; time.sleep(15)"
  alive && taskkill //PID "$PID" //F > /dev/null
fi
echo "[7/7] $TAG done: zero events $(grep -c '^zero' "$OUT/probe.out"), fault lines $(grep -a -c 'VEH FAULT.*AUDIO' "$OUT/sc3resize.log")"
