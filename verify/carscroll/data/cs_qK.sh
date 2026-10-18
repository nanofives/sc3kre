#!/usr/bin/env bash
set -u
S=/c/Users/maria/Desktop/Proyectos/Simcity_stock_pausetrips/re/harness
LOG=$S/cs_queue.log
BER='C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\Cities\Berlin, Germany.sc3'
until grep -q "QUEUE J DONE" $LOG; do sleep 20; done
os1() { echo "$1:0,W:3,C:0,I:3,MV:5,I:20,I:15,OS:4,I:10,I:30"; }
osb() { echo "$(os1 X0),$(os1 X1),$(os1 X1),$(os1 X0)"; }
echo "$(date +%T) start R3c" >> $LOG
(cd $S && LOG_S=1 CS_OS_DIR=left ./cs_arm.sh inst_cf_full "$BER" R3c "s3:10,$(osb),$(osb)" replace "--settle 90 --safe") >> $LOG 2>&1
echo "$(date +%T) end R3c" >> $LOG
echo "$(date +%T) QUEUE K DONE" >> $LOG
