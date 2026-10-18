#!/usr/bin/env bash
# staged-build arms (verify/carscroll/PRE.md addendum 15): sc3cartrips 3f9a2c82 + sc3simrun 0b903bb6
set -u
S=/c/Users/maria/Desktop/Proyectos/Simcity_stock_pausetrips/re/harness
LOG=$S/cs_queue.log
BER='C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\Cities\Berlin, Germany.sc3'
E1K='C:\Users\maria\Desktop\Proyectos\Simcity\verify\perf1024\europolis1024_v2_test.sc3'
until grep -q '"phase": "end"' $S/inst_cf_full/R2f.jsonl 2>/dev/null; do sleep 20; done
while tasklist //FI "IMAGENAME eq SC3U.exe" | grep -q SC3U; do sleep 10; done
sleep 5
for f in sc3cartrips.log sc3simrun.log sc3perf.log; do [ -f "$S/inst_cf_full/$f" ] && cp "$S/inst_cf_full/$f" "$S/inst_cf_full/R2f_$f"; done
echo "$(date +%T) end R2f (logs copied by cs_qJ)" >> $LOG
for i in inst_cf_stock inst_cf_full; do cp $S/build_cf3/sc3cartrips.dll $S/build_cf3/sc3simrun.dll $S/$i/; done
echo "$(date +%T) inst_cf now sc3cartrips $(sha256sum $S/inst_cf_stock/sc3cartrips.dll | cut -c1-8) sc3simrun $(sha256sum $S/inst_cf_stock/sc3simrun.dll | cut -c1-8)" >> $LOG
os1() { echo "$1:0,W:3,C:0,I:3,MV:2,I:20,I:15,OS:3,I:10,I:30"; }
osb() { echo "$(os1 X0),$(os1 X1),$(os1 X1),$(os1 X0)"; }
SOAK="HG:60,I:5,H:60,I:5,AR:60,I:5,HB:30,I:5"
run() { echo "$(date +%T) start $3" >> $LOG; (cd $S && ./cs_arm.sh "$@") >> $LOG 2>&1; echo "$(date +%T) end $3" >> $LOG; }
LOG_S=1 CS_OS_DIR=left run inst_cf_full "$BER" R3b "s3:10,$(osb),$(osb)" replace "--settle 90 --safe"
CS_LITE=1 LOG_S=5 run inst_cf_full "$E1K" L8 "Z:2,s4:10,X1:0,$SOAK,$SOAK,$SOAK" replace "--settle 90 --safe"
V="s3:10,C:0,I:25,X0:0,A0:0,W:3,I:8,H*:6,I:5,HG*:6,I:5,C:0,I:20,A1:0,W:3,I:8,H*:6,I:5,HG*:6,I:5,C:0,I:20,X1:0,W:3,I:10,H*:6,I:5,HG*:6,I:5"
CS_FRAME_MS=80 CS_FRAMEDUMP='C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\re\harness\inst_cf_stock\frames\V6_' LOG_S=1 run inst_cf_stock "$BER" V6 "$V" replace "--settle 90"
echo "$(date +%T) QUEUE J DONE" >> $LOG
