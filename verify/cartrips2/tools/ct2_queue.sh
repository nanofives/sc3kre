#!/usr/bin/env bash
# ct2_queue.sh - runs the cartrips2 arms one after the other (verify/cartrips2/PRE.md addenda 1-2).
# usage: ct2_queue.sh ARM [ARM ...]; each arm: write cartrips.ini, ct_run.py, archive <ARM>_* files.
set -u
P=/c/Users/maria/Desktop/Proyectos
S=$P/Simcity_stock_pausetrips/re/harness
R=$P/Simcity_stock_roundabout4/re/harness
TOOLS=$P/Simcity_wt/cartrips2/re/tools
DLL=$S/build_ct2m2b/sc3cartrips.dll
BER="C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\Cities\Berlin, Germany.sc3"
MOS="C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\Cities\Moscow, Russia.sc3"
LON="C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\Cities\London, England.sc3"
E1K="C:\Users\maria\Desktop\Proyectos\Simcity\verify\perf1024\europolis1024_v2_test.sc3"
BERR="C:\Users\maria\Desktop\Proyectos\Simcity_stock_roundabout4\Cities\Berlin, Germany.sc3"
winp() { cygpath -w "$1"; }
wait_free() { while tasklist //FI "IMAGENAME eq SC3U.exe" | grep -q SC3U; do sleep 5; done; }
ini() { printf '[cartrips]\r\nmode=capture\r\nlog_s=5\r\n%s' "$2" > "$1/cartrips.ini"; }
archive() {   # $1 inst $2 arm
  for f in sc3cartrips.log cartrips_trips.bin cartrips_graphs.bin cartrips_routes.bin; do
    [ -f "$1/$f" ] && mv "$1/$f" "$1/$2_$f"; done; }
run() {       # $1 inst $2 city $3 arm $4 schedule $5 extra args
  wait_free
  cp "$DLL" "$1/sc3cartrips.dll"
  echo "$(date +%T) start $3" >> $P/Simcity_stock_pausetrips/re/harness/ct2_queue.log
  (cd $TOOLS && CT_GROUPS=none py -3.12 ct_run.py --inst "$(winp $1)" --city "$2" --arm $3 --schedule "$4" $5 > "$1/run_$3.out" 2>&1)
  sleep 3; wait_free; archive "$1" "$3"
  echo "$(date +%T) end $3: $(tail -1 $1/run_$3.out)" >> $P/Simcity_stock_pausetrips/re/harness/ct2_queue.log
}
alt() {       # $1 inst $2 city $3 arm $4 schedule $5 extra args $6 ctm_alt args
  wait_free
  cp "$DLL" "$1/sc3cartrips.dll"
  echo "$(date +%T) start $3" >> $P/Simcity_stock_pausetrips/re/harness/ct2_queue.log
  (cd $TOOLS && CT_GROUPS=none py -3.12 ct_run.py --inst "$(winp $1)" --city "$2" --arm $3 --schedule "$4" $5 > "$1/run_$3.out" 2>&1) &
  until grep -q " phase s" "$1/run_$3.out" 2>/dev/null; do sleep 3; done
  pid=$(cut -d' ' -f1 "$1/pid_$3.txt")
  (cd $TOOLS && SC3_PID=$pid py -3.12 ctm_alt.py --warmup 60 --window 30 --settle 2 --blocks 10 --out "$(winp $1)/$3_alt.json" $6 > "$1/$3_alt.out" 2>&1)
  wait; sleep 3; wait_free; archive "$1" "$3"
  echo "$(date +%T) end $3: $(tail -3 $1/$3_alt.out | tr '\n' ' ')" >> $P/Simcity_stock_pausetrips/re/harness/ct2_queue.log
}
for arm in "$@"; do case $arm in
  M2B2) ini $S/inst_ct2_stock $'solve=1\r\ndump=1\r\n'; run $S/inst_ct2_stock "$BER" M2B2 "s3:120,s4:120" "";;
  M2M)  ini $S/inst_ct2_stock $'solve=1\r\ndump=1\r\n'; run $S/inst_ct2_stock "$MOS" M2M "s3:120,s4:120" "";;
  M2L)  ini $S/inst_ct2_stock $'solve=1\r\ndump=1\r\n'; run $S/inst_ct2_stock "$LON" M2L "s3:120,s4:120" "";;
  M2E)  ini $S/inst_ct2_full $'solve=1\r\ndump=1\r\n'; run $S/inst_ct2_full "$E1K" M2E "s3:120,s4:120" "--safe --settle 90";;
  M2R)  ini $R/inst_ct2_rbt $'solve=1\r\ndump=1\r\nrect=45,155,70,180\r\n'; run $R/inst_ct2_rbt "$BERR" M2R "s3:120,s4:120" "";;
  F2)   ini $S/inst_ct2_full $'solve=1\r\n'; run $S/inst_ct2_full "$E1K" F2 "s3:900,s4:900" "--safe --settle 90";;
  F1)   ini $S/inst_ct2_stock $'solve=1\r\n'; run $S/inst_ct2_stock "$BER" F1 "s3:600,s4:1200" "";;
  C1)   ini $S/inst_ct2_stock $'time_route=1\r\n'; alt $S/inst_ct2_stock "$BER" C1 "s4:1500" "" "";;
  C2)   ini $S/inst_ct2_full $'time_route=1\r\n'; alt $S/inst_ct2_full "$E1K" C2 "s3:1500" "--safe --settle 90" "--perf";;
esac; done
echo "$(date +%T) queue done" >> $P/Simcity_stock_pausetrips/re/harness/ct2_queue.log
