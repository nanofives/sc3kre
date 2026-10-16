#!/usr/bin/env bash
set -u
S=/c/Users/maria/Desktop/Proyectos/Simcity_stock_pausetrips/re/harness
LOG=$S/cs_queue.log
BER='C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\Cities\Berlin, Germany.sc3'
until grep -q "QUEUE8 DONE" $LOG; do sleep 20; done
blk() { echo "A0:0,I:15,$1:20,I:10,A1:0,I:15,$1:20,I:10,A1:0,I:15,$1:20,I:10,A0:0,I:15,$1:20,I:10"; }
echo "$(date +%T) start S1e" >> $LOG
(cd $S && ./cs_arm.sh inst_cs_stock "$BER" S1e "s3:10,$(blk H),$(blk HB),$(blk AR),A1:0,P:15,PH:20,P:10,s3:15" off "--settle 90") >> $LOG 2>&1
echo "$(date +%T) end S1e" >> $LOG
echo "$(date +%T) QUEUE9 DONE" >> $LOG
