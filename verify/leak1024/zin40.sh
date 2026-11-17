#!/bin/bash
cd /c/Users/maria/Desktop/Proyectos/Simcity
o=verify/leak1024/runs; C="Europolis 1024.sc3"
py -3.12 verify/leak1024/rotmem.py Eur_B_zin40 --n 40 --gap 2 --wait 150 --zin 10 --city "$C" --env SC3PERF_SPR_IMGREF=0 --shots 1 > $o/Eur_B_zin40.txt 2>&1; tail -1 $o/Eur_B_zin40.txt
py -3.12 verify/leak1024/rotmem.py Eur_A_zin40 --n 40 --gap 2 --wait 150 --zin 10 --city "$C" > $o/Eur_A_zin40.txt 2>&1; tail -1 $o/Eur_A_zin40.txt
ARM=trace_Eur_B_zin CITY="$C" ZIN=10 bash verify/leak1024/trace_arm.sh SC3PERF_SPR_IMGREF=0 > $o/trace_Eur_B_zin.txt 2>&1; tail -n 14 $o/trace_Eur_B_zin.txt
