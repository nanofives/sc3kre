#!/usr/bin/env bash
set -u
S=/c/Users/maria/Desktop/Proyectos/Simcity_stock_pausetrips/re/harness
LOG=$S/cs_queue.log
E1K='C:\Users\maria\Desktop\Proyectos\Simcity\verify\perf1024\europolis1024_v2_test.sc3'
until grep -q "QUEUE V5 DONE" $LOG; do sleep 20; done
mv1() { echo "$1:0,W:3,C:0,I:30,I:15,$2:20,I:10"; }
xb() { echo "$(mv1 X0 $1),$(mv1 X1 $1),$(mv1 X1 $1),$(mv1 X0 $1)"; }
echo "$(date +%T) start R2c" >> $LOG
(cd $S && LOG_S=1 ./cs_arm.sh inst_cf_full "$E1K" R2c "Z:2,s3:20,$(xb HG),$(xb H),$(xb AR),$(xb OS)" replace "--settle 90 --safe") >> $LOG 2>&1
echo "$(date +%T) end R2c" >> $LOG
echo "$(date +%T) QUEUE R3 DONE" >> $LOG
