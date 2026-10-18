#!/usr/bin/env bash
# carscroll route-car fix arms (verify/carscroll/PRE.md addendum 8)
set -u
S=/c/Users/maria/Desktop/Proyectos/Simcity_stock_pausetrips/re/harness
LOG=$S/cs_queue.log
BER='C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\Cities\Berlin, Germany.sc3'
E1K='C:\Users\maria\Desktop\Proyectos\Simcity\verify\perf1024\europolis1024_v2_test.sc3'
xb() { local o="I:15,$1:20,I:10"; echo "X0:0,W:3,$o,X1:0,W:3,$o,X1:0,W:3,$o,X0:0,W:3,$o"; }
cyc() { local c="W:3,I:8,HG:10,I:8,H:10,I:8,AR:8,I:8"; echo "X0:0,$c,X1:0,$c,X1:0,$c,X0:0,$c"; }
SOAK="HG:60,I:5,H:60,I:5,AR:60,I:5,HB:30,I:5"
run() { echo "$(date +%T) start $3" >> $LOG; (cd $S && ./cs_arm.sh "$@") >> $LOG 2>&1; echo "$(date +%T) end $3" >> $LOG; }
LOG_S=1 run inst_cf_stock "$BER" R1 "s3:10,$(xb HG),$(xb HG),$(xb H),$(xb H),$(xb HB),$(xb HB),$(xb AR),$(xb AR),X1:0,P:15,PH:20,P:10,s3:15" replace "--settle 90"
LOG_S=1 run inst_cf_full "$E1K" R2 "Z:2,s3:20,$(xb HG),$(xb H),$(xb AR),$(xb OS)" replace "--settle 90 --safe"
CS_LITE=1 LOG_S=5 run inst_cf_full "$E1K" C4 "Z:2,s3:20,$(cyc),$(cyc)" replace "--settle 90 --safe"
CS_LITE=1 LOG_S=5 run inst_cf_full "$E1K" L5 "Z:2,s4:10,X1:0,$SOAK,$SOAK,$SOAK,$SOAK" replace "--settle 90 --safe"
V="s3:10,X0:0,A0:0,W:3,I:8,H*:6,I:5,HG*:6,I:5,A1:0,W:3,I:8,H*:6,I:5,HG*:6,I:5,X1:0,W:3,I:10,H*:6,I:5,HG*:6,I:5"
CS_FRAME_MS=80 CS_FRAMEDUMP='C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\re\harness\inst_cf_stock\frames\V4_' LOG_S=1 run inst_cf_stock "$BER" V4 "$V" replace "--settle 90"
echo "$(date +%T) QUEUE R DONE" >> $LOG
