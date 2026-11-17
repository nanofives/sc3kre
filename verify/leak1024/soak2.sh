#!/bin/bash
cd /c/Users/maria/Desktop/Proyectos/Simcity
o=verify/leak1024/runs
C="Europolis 1024.sc3"
py -3.12 verify/leak1024/soak.py soak_B --city "$C" --env SC3PERF_SPR_IMGREF=0 2>&1 | tee $o/soak_B.txt
py -3.12 verify/leak1024/soak.py soak_A --city "$C" 2>&1 | tee $o/soak_A.txt
