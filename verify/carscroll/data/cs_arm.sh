#!/usr/bin/env bash
# cs_arm.sh - one carscroll arm (verify/carscroll/PRE.md). usage: cs_arm.sh <inst dir name> <city> <arm> <schedule> <cartrips mode> [extra args]
set -u
P=/c/Users/maria/Desktop/Proyectos
S=$P/Simcity_stock_pausetrips/re/harness
TOOLS=$P/Simcity_wt/carscroll/re/tools
I=$S/$1
while tasklist //FI "IMAGENAME eq SC3U.exe" | grep -q SC3U; do echo "a game is running, waiting"; sleep 10; done
printf '[cartrips]\r\nmode=%s\r\nlog_s=5\r\n' "$5" > "$I/cartrips.ini"
(cd $TOOLS && py -3.12 cs_run.py --inst "$(cygpath -w $I)" --city "$2" --arm $3 --schedule "$4" ${6:-} > "$I/run_$3.out" 2>&1)
sleep 3
for f in sc3cartrips.log sc3simrun.log sc3resize.log sc3perf.log; do [ -f "$I/$f" ] && cp "$I/$f" "$I/$3_$f"; done
tail -3 "$I/run_$3.out"
