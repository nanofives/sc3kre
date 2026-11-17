#!/bin/bash
# 100 paused rotations on Europolis 1024: arm A (shipped) / B (SPR_IMGREF=0) at loaded zoom and at widest zoom (zout 6)
cd /c/Users/maria/Desktop/Proyectos/Simcity
o=verify/leak1024/runs; mkdir -p $o
C="Europolis 1024.sc3"
py -3.12 verify/leak1024/rotmem.py A_z4 --n 100 --gap 2 --wait 150 --city "$C" > $o/A_z4.txt 2>&1; echo "[1/4] $(tail -1 $o/A_z4.txt)"
py -3.12 verify/leak1024/rotmem.py A_wide --n 100 --gap 2 --wait 150 --zout 6 --city "$C" > $o/A_wide.txt 2>&1; echo "[2/4] $(tail -1 $o/A_wide.txt)"
py -3.12 verify/leak1024/rotmem.py B_z4 --n 100 --gap 2 --wait 150 --city "$C" --env SC3PERF_SPR_IMGREF=0 > $o/B_z4.txt 2>&1; echo "[3/4] $(tail -1 $o/B_z4.txt)"
cp dev/leak1024/inst/sc3resize.log $o/B_z4_sc3resize.log
py -3.12 verify/leak1024/rotmem.py B_wide --n 100 --gap 2 --wait 150 --zout 6 --city "$C" --env SC3PERF_SPR_IMGREF=0 > $o/B_wide.txt 2>&1; echo "[4/4] $(tail -1 $o/B_wide.txt)"
cp dev/leak1024/inst/sc3resize.log $o/B_wide_sc3resize.log
