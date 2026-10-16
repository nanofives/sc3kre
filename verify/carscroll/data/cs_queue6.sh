#!/usr/bin/env bash
set -u
S=/c/Users/maria/Desktop/Proyectos/Simcity_stock_pausetrips/re/harness
LOG=$S/cs_queue.log
BER='C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\Cities\Berlin, Germany.sc3'
until grep -q "QUEUE5 DONE" $LOG; do sleep 20; done
V="s3:10,A0:0,HS*:5,I:4,A1:0,HS*:5,I:4,A0:0,HS*:5,I:4,A1:0,HS*:5,I:4"
run() { echo "$(date +%T) start $3" >> $LOG; (cd $S && ./cs_arm.sh "$@") >> $LOG 2>&1; echo "$(date +%T) end $3" >> $LOG; }
CS_FRAME_MS=80 CS_FRAMEDUMP='C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\re\harness\inst_cs_stock\frames\V2o_' run inst_cs_stock "$BER" V2o "$V" off "--settle 90"
CS_FRAME_MS=80 CS_FRAMEDUMP='C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\re\harness\inst_cs_stock\frames\V2r_' run inst_cs_stock "$BER" V2r "$V" replace "--settle 90"
echo "$(date +%T) QUEUE6 DONE" >> $LOG
