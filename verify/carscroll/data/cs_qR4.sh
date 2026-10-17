#!/usr/bin/env bash
set -u
S=/c/Users/maria/Desktop/Proyectos/Simcity_stock_pausetrips/re/harness
LOG=$S/cs_queue.log
BER='C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\Cities\Berlin, Germany.sc3'
E1K='C:\Users\maria\Desktop\Proyectos\Simcity\verify\perf1024\europolis1024_v2_test.sc3'
until grep -q "QUEUE R3 DONE" $LOG; do sleep 20; done
SOAK="HG:60,I:5,H:60,I:5,AR:60,I:5,HB:30,I:5"
run() { echo "$(date +%T) start $3" >> $LOG; (cd $S && ./cs_arm.sh "$@") >> $LOG 2>&1; echo "$(date +%T) end $3" >> $LOG; }
CS_LITE=1 LOG_S=5 run inst_cf_full "$E1K" L6 "Z:2,s4:10,X1:0,$SOAK,$SOAK,$SOAK" replace "--settle 90 --safe"
V="s3:10,C:0,I:25,X0:0,A0:0,W:3,I:8,H*:6,I:5,HG*:6,I:5,C:0,I:20,A1:0,W:3,I:8,H*:6,I:5,HG*:6,I:5,C:0,I:20,X1:0,W:3,I:10,H*:6,I:5,HG*:6,I:5"
CS_FRAME_MS=80 CS_FRAMEDUMP='C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\re\harness\inst_cf_stock\frames\V5_' LOG_S=1 run inst_cf_stock "$BER" V5 "$V" replace "--settle 90"
echo "$(date +%T) QUEUE R4 DONE" >> $LOG
