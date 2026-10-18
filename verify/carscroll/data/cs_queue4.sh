#!/usr/bin/env bash
set -u
S=/c/Users/maria/Desktop/Proyectos/Simcity_stock_pausetrips/re/harness
LOG=$S/cs_queue.log
BER='C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\Cities\Berlin, Germany.sc3'
until grep -q "QUEUE3 DONE" $LOG; do sleep 20; done
blk() { echo "A0:0,I:15,$1:20,I:10,A1:0,I:15,$1:20,I:10,A1:0,I:15,$1:20,I:10,A0:0,I:15,$1:20,I:10"; }
echo "$(date +%T) start C3" >> $LOG
(cd $S && CS_LITE=1 ./cs_arm.sh inst_cs_stock "$BER" C3 "s4:10,$(blk H),$(blk AR)" replace "--settle 90") >> $LOG 2>&1
echo "$(date +%T) end C3" >> $LOG
echo "$(date +%T) QUEUE4 DONE" >> $LOG
