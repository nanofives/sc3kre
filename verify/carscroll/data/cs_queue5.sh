#!/usr/bin/env bash
set -u
S=/c/Users/maria/Desktop/Proyectos/Simcity_stock_pausetrips/re/harness
LOG=$S/cs_queue.log
BER='C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\Cities\Berlin, Germany.sc3'
until grep -q "QUEUE4 DONE" $LOG; do sleep 20; done
blk() { echo "A0:0,I:15,$1:20,I:10,A1:0,I:15,$1:20,I:10,A1:0,I:15,$1:20,I:10,A0:0,I:15,$1:20,I:10"; }
run() { echo "$(date +%T) start $3" >> $LOG; (cd $S && ./cs_arm.sh "$@") >> $LOG 2>&1; echo "$(date +%T) end $3" >> $LOG; }
run inst_cs_stock "$BER" S1c "s3:10,$(blk H),$(blk HB),$(blk AR),A1:0,P:15,PH:20,P:10,s3:15" off "--settle 90"
run inst_cs_stock "$BER" S3c "s3:10,$(blk H),$(blk AR)" filler "--settle 90"
echo "$(date +%T) QUEUE5 DONE" >> $LOG
