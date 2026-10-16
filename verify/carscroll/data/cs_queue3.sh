#!/usr/bin/env bash
# cs_queue3.sh - F1 rerun (F1's first launch died 0.2 s after start, before SIMSPR loaded), after cs_queue2.sh
set -u
S=/c/Users/maria/Desktop/Proyectos/Simcity_stock_pausetrips/re/harness
LOG=$S/cs_queue.log
E1K='C:\Users\maria\Desktop\Proyectos\Simcity\verify\perf1024\europolis1024_v2_test.sc3'
until grep -q "QUEUE2 DONE" $LOG; do sleep 20; done
blk() { echo "A0:0,I:15,$1:20,I:10,A1:0,I:15,$1:20,I:10,A1:0,I:15,$1:20,I:10,A0:0,I:15,$1:20,I:10"; }
os3() { echo "OS:5,I:8,OS:5,I:8,OS:5,I:8"; }
OSB="A1:0,$(os3),A0:0,$(os3),$(os3),A1:0,$(os3)"
echo "$(date +%T) start F1r" >> $LOG
(cd $S && ./cs_arm.sh inst_cs_full "$E1K" F1r "Z:2,s3:20,$(blk H),$(blk AR),$OSB" replace "--settle 90 --safe") >> $LOG 2>&1
echo "$(date +%T) end F1r" >> $LOG
echo "$(date +%T) QUEUE3 DONE" >> $LOG
