#!/usr/bin/env bash
# cs_queue2.sh - carscroll addendum-2 arms (final build ede5732a), after cs_queue.sh
set -u
S=/c/Users/maria/Desktop/Proyectos/Simcity_stock_pausetrips/re/harness
LOG=$S/cs_queue.log
BER='C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\Cities\Berlin, Germany.sc3'
until grep -q "QUEUE DONE" $LOG; do sleep 20; done
while tasklist //FI "IMAGENAME eq SC3U.exe" | grep -q SC3U; do sleep 10; done
cp $S/build_cs/sc3simrun.dll $S/inst_cs_stock/sc3simrun.dll; cp $S/build_cs/sc3simrun.dll $S/inst_cs_full/sc3simrun.dll
echo "$(date +%T) instances now sc3simrun $(sha256sum $S/inst_cs_stock/sc3simrun.dll | cut -c1-8)" >> $LOG
blk() { echo "A0:0,I:15,$1:20,I:10,A1:0,I:15,$1:20,I:10,A1:0,I:15,$1:20,I:10,A0:0,I:15,$1:20,I:10"; }
SOAK="H:60,I:5,AR:60,I:5,HB:30,I:5"
run() { echo "$(date +%T) start $3" >> $LOG; (cd $S && ./cs_arm.sh "$@") >> $LOG 2>&1; echo "$(date +%T) end $3" >> $LOG; }
run inst_cs_stock "$BER" S1b "s3:10,$(blk H),$(blk HB),$(blk AR),A1:0,P:15,PH:20,P:10,s3:15" off "--settle 90"
run inst_cs_stock "$BER" S3b "s3:10,$(blk H),$(blk AR)" filler "--settle 90"
CS_LITE=1 run inst_cs_stock "$BER" L3 "s4:10,$SOAK,$SOAK,$SOAK,$SOAK" off "--settle 90"
V="s3:10,A0:0,H*:6,I:4,A1:0,H*:6,I:4,A0:0,AR*:3,I:4,A1:0,AR*:3,I:4"
CS_FRAMEDUMP='C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\re\harness\inst_cs_stock\frames\V1o_' run inst_cs_stock "$BER" V1o "$V" off "--settle 90"
CS_FRAMEDUMP='C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\re\harness\inst_cs_stock\frames\V1r_' run inst_cs_stock "$BER" V1r "$V" replace "--settle 90"
echo "$(date +%T) QUEUE2 DONE" >> $LOG
