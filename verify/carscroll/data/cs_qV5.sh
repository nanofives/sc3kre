#!/usr/bin/env bash
set -u
S=/c/Users/maria/Desktop/Proyectos/Simcity_stock_pausetrips/re/harness
LOG=$S/cs_queue.log
BER='C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\Cities\Berlin, Germany.sc3'
until grep -q "QUEUE R2 DONE" $LOG; do sleep 20; done
V="s3:10,C:0,I:25,X0:0,A0:0,W:3,I:8,H*:6,I:5,HG*:6,I:5,C:0,I:20,A1:0,W:3,I:8,H*:6,I:5,HG*:6,I:5,C:0,I:20,X1:0,W:3,I:10,H*:6,I:5,HG*:6,I:5"
echo "$(date +%T) start V5" >> $LOG
(cd $S && CS_FRAME_MS=80 CS_FRAMEDUMP='C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\re\harness\inst_cf_stock\frames\V5_' LOG_S=1 ./cs_arm.sh inst_cf_stock "$BER" V5 "$V" replace "--settle 90") >> $LOG 2>&1
echo "$(date +%T) end V5" >> $LOG
echo "$(date +%T) QUEUE V5 DONE" >> $LOG
