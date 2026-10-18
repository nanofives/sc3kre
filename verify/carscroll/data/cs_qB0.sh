#!/usr/bin/env bash
set -u
S=/c/Users/maria/Desktop/Proyectos/Simcity_stock_pausetrips/re/harness
LOG=$S/cs_queue.log
BER='C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\Cities\Berlin, Germany.sc3'
blk() { echo "A0:0,I:15,$1:20,I:10,A1:0,I:15,$1:20,I:10,A1:0,I:15,$1:20,I:10,A0:0,I:15,$1:20,I:10"; }
echo "$(date +%T) start B0" >> $LOG
(cd $S && LOG_S=1 ./cs_arm.sh inst_cs_stock "$BER" B0 "s3:10,$(blk H),$(blk HB),$(blk AR)" replace "--settle 90") >> $LOG 2>&1
echo "$(date +%T) end B0" >> $LOG
