#!/usr/bin/env bash
# short overscroll arm (PRE addendum 13): a 4 s arrow hold from a point near the map edge, so the camera goes past the
# edge a little and comes back, instead of R2d / R2e's 20 s flight across the map
set -u
S=/c/Users/maria/Desktop/Proyectos/Simcity_stock_pausetrips/re/harness
LOG=$S/cs_queue.log
BER='C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\Cities\Berlin, Germany.sc3'
until grep -q "QUEUE G DONE" $LOG; do sleep 20; done
mv1() { echo "$1:0,W:3,C:0,I:3,MV:2,I:20,I:15,OS:3,I:10,I:30"; }
xb() { echo "$(mv1 X0),$(mv1 X1),$(mv1 X1),$(mv1 X0)"; }
echo "$(date +%T) start R3" >> $LOG
(cd $S && LOG_S=1 CS_OS_DIR=left ./cs_arm.sh inst_cf_full "$BER" R3 "s3:10,$(xb),$(xb)" replace "--settle 90 --safe") >> $LOG 2>&1
echo "$(date +%T) end R3" >> $LOG
echo "$(date +%T) QUEUE H DONE" >> $LOG
