#!/usr/bin/env bash
# ct3_queue.sh - cartrips3 (M3) arms one after the other (verify/cartrips3/PRE.md + addendum 1).
set -u
P=/c/Users/maria/Desktop/Proyectos
S=$P/Simcity_stock_pausetrips/re/harness
TOOLS=$P/Simcity_wt/cartrips2/re/tools
DLL=$S/build_ct3/sc3cartrips.dll
LOG=$S/ct3_queue.log
BER="C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\Cities\Berlin, Germany.sc3"
E1K="C:\Users\maria\Desktop\Proyectos\Simcity\verify\perf1024\europolis1024_v2_test.sc3"
winp() { cygpath -w "$1"; }
wait_free() { while tasklist //FI "IMAGENAME eq SC3U.exe" | grep -q SC3U; do sleep 5; done; }
ini() { printf '[cartrips]\r\n%s' "$2" > "$1/cartrips.ini"; }
archive() { for f in sc3cartrips.log cartrips_trips.bin cartrips_graphs.bin cartrips_routes.bin; do [ -f "$1/$f" ] && mv "$1/$f" "$1/$2_$f"; done; }
run() {   # inst city arm schedule groups extra
  wait_free; cp "$DLL" "$1/sc3cartrips.dll"
  echo "$(date +%T) start $3" >> $LOG
  (cd $TOOLS && CT_GROUPS=$5 py -3.12 ct_run.py --inst "$(winp $1)" --city "$2" --arm $3 --schedule "$4" $6 > "$1/run_$3.out" 2>&1)
  sleep 3; wait_free; archive "$1" "$3"
  echo "$(date +%T) end $3: $(tail -1 $1/run_$3.out)" >> $LOG
}
alt() {   # inst city arm schedule extra
  wait_free; cp "$DLL" "$1/sc3cartrips.dll"
  echo "$(date +%T) start $3" >> $LOG
  (cd $TOOLS && CT_GROUPS=none py -3.12 ct_run.py --inst "$(winp $1)" --city "$2" --arm $3 --schedule "$4" $5 > "$1/run_$3.out" 2>&1) &
  until grep -q " phase s" "$1/run_$3.out" 2>/dev/null; do sleep 3; done
  pid=$(cut -d' ' -f1 "$1/pid_$3.txt")
  (cd $TOOLS && SC3_PID=$pid py -3.12 ctm_modealt.py --window 45 --settle 30 --blocks 6 --out "$(winp $1)/$3_alt.json" > "$1/$3_alt.out" 2>&1)
  wait; sleep 3; wait_free; archive "$1" "$3"
  echo "$(date +%T) end $3: $(tail -4 $1/$3_alt.out | tr '\n' ' ')" >> $LOG
}
for arm in "$@"; do case $arm in
  R1) ini $S/inst_ct3_stock $'mode=replace\r\nlog_s=1\r\n'; run $S/inst_ct3_stock "$BER" R1 "s1:60,s2:60,s3:120,s4:120,P:40,s3:60" rem,acc,ag "";;
  R2) ini $S/inst_ct3_full $'mode=replace\r\nlog_s=1\r\n'; run $S/inst_ct3_full "$E1K" R2 "Z:2,s3:120,s4:120,P:30,s3:60" none "--safe --settle 90";;
  R2b) ini $S/inst_ct3_full $'mode=replace\r\nlog_s=1\r\n'; run $S/inst_ct3_full "$E1K" R2b "Z:3,s3:120,s4:120,P:30,s3:60" none "--safe --settle 90";;
  FL) ini $S/inst_ct3_stock $'mode=filler\r\nlog_s=1\r\n'; run $S/inst_ct3_stock "$BER" FL "s3:120,s4:60" none "";;
  L1) ini $S/inst_ct3_stock $'mode=replace\r\nlog_s=5\r\n'; run $S/inst_ct3_stock "$BER" L1 "s3:600,s4:1200" none "";;
  L2) ini $S/inst_ct3_full $'mode=replace\r\nlog_s=5\r\n'; run $S/inst_ct3_full "$E1K" L2 "Z:3,s3:900,s4:900" none "--safe --settle 90";;
  PZ) ini $S/inst_ct3_stock $'mode=replace\r\nlog_s=1\r\n'; run $S/inst_ct3_stock "$BER" PZ "s3:90,P:30,s3:60" none "";;
  CA) ini $S/inst_ct3_stock $'mode=replace\r\nlog_s=5\r\ntime_agents=1\r\n'; alt $S/inst_ct3_stock "$BER" CA "s3:1500" "";;
esac; done
echo "$(date +%T) queue done" >> $LOG
