#!/usr/bin/env bash
# cs_queue.sh - carscroll counted arms (verify/carscroll/PRE.md + addendum 1), one game at a time
set -u
S=/c/Users/maria/Desktop/Proyectos/Simcity_stock_pausetrips/re/harness
LOG=$S/cs_queue.log
BER='C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\Cities\Berlin, Germany.sc3'
E1K='C:\Users\maria\Desktop\Proyectos\Simcity\verify\perf1024\europolis1024_v2_test.sc3'
blk() { echo "A0:0,I:15,$1:20,I:10,A1:0,I:15,$1:20,I:10,A1:0,I:15,$1:20,I:10,A0:0,I:15,$1:20,I:10"; }
cyc() { local c="H:10,I:8,AR:8,I:8,HB:8,I:8"; echo "A0:0,$c,A1:0,$c,A1:0,$c,A0:0,$c"; }
os3() { echo "OS:5,I:8,OS:5,I:8,OS:5,I:8"; }
OSB="A1:0,$(os3),A0:0,$(os3),$(os3),A1:0,$(os3)"
SOAK="H:60,I:5,AR:60,I:5,HB:30,I:5"
SOAK6="$SOAK,$SOAK,$SOAK,$SOAK,$SOAK,$SOAK"
run() { echo "$(date +%T) start $3" >> $LOG; (cd $S && ./cs_arm.sh "$@") >> $LOG 2>&1; echo "$(date +%T) end $3" >> $LOG; }
SB="s3:10,$(blk H),$(blk HB),$(blk AR),A1:0,P:15,PH:20,P:10,s3:15"
[ "${ONLY:-}" = "" ] || set -- $ONLY
run inst_cs_stock "$BER" S1 "$SB" off "--settle 90"
run inst_cs_stock "$BER" S2 "$SB" replace "--settle 90"
run inst_cs_stock "$BER" S3 "s3:10,$(blk H),$(blk AR)" filler "--settle 90"
run inst_cs_n0 "$BER" N0 "s3:15,H:20,I:15,AR:20,I:15" off "--settle 90"
CS_LITE=1 run inst_cs_stock "$BER" C1 "s3:10,$(cyc),$(cyc),$(cyc)" replace "--settle 90"
run inst_cs_full "$BER" F2 "s3:10,$(blk H),$(blk AR),$OSB" replace "--settle 90 --safe"
run inst_cs_full "$E1K" F1 "Z:2,s3:20,$(blk H),$(blk AR),$OSB" replace "--settle 90 --safe"
CS_LITE=1 run inst_cs_full "$E1K" C2 "Z:2,s3:20,$(cyc),$(cyc)" replace "--settle 90 --safe"
CS_LITE=1 run inst_cs_stock "$BER" L1 "s4:10,$SOAK6" replace "--settle 90"
CS_LITE=1 run inst_cs_full "$E1K" L2 "Z:2,s4:10,$SOAK6" replace "--settle 90 --safe"
echo "$(date +%T) QUEUE DONE" >> $LOG
