#!/usr/bin/env bash
set -u
S=/c/Users/maria/Desktop/Proyectos/Simcity_stock_pausetrips/re/harness
LOG=$S/cs_queue.log
BER='C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\Cities\Berlin, Germany.sc3'
E1K='C:\Users\maria\Desktop\Proyectos\Simcity\verify\perf1024\europolis1024_v2_test.sc3'
until grep -q "QUEUE R DONE" $LOG; do sleep 20; done
while tasklist //FI "IMAGENAME eq SC3U.exe" | grep -q SC3U; do sleep 10; done
cp $S/build_cf2/sc3cartrips.dll $S/inst_cf_stock/; cp $S/build_cf2/sc3cartrips.dll $S/inst_cf_full/
echo "$(date +%T) inst_cf now sc3cartrips $(sha256sum $S/inst_cf_stock/sc3cartrips.dll | cut -c1-8)" >> $LOG
mv1() { echo "$1:0,W:3,C:0,I:30,I:15,$2:20,I:10"; }
xb() { echo "$(mv1 X0 $1),$(mv1 X1 $1),$(mv1 X1 $1),$(mv1 X0 $1)"; }
SOAK="HG:60,I:5,H:60,I:5,AR:60,I:5,HB:30,I:5"
run() { echo "$(date +%T) start $3" >> $LOG; (cd $S && ./cs_arm.sh "$@") >> $LOG 2>&1; echo "$(date +%T) end $3" >> $LOG; }
LOG_S=1 run inst_cf_stock "$BER" R1b "s3:10,$(xb H),$(xb AR),$(xb H),$(xb AR),$(xb HG),$(xb HB),X1:0,P:15,PH:20,P:10,s3:15" replace "--settle 90"
LOG_S=1 run inst_cf_full "$E1K" R2b "Z:2,s3:20,$(xb HG),$(xb H),$(xb AR),$(xb OS)" replace "--settle 90 --safe"
CS_LITE=1 LOG_S=5 run inst_cf_full "$E1K" L6 "Z:2,s4:10,X1:0,$SOAK,$SOAK,$SOAK" replace "--settle 90 --safe"
echo "$(date +%T) QUEUE R2 DONE" >> $LOG
