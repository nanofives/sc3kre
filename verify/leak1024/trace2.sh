#!/bin/bash
cd /c/Users/maria/Desktop/Proyectos/Simcity
ARM=trace_Eur_B CITY="Europolis 1024.sc3" bash verify/leak1024/trace_arm.sh SC3PERF_SPR_IMGREF=0 > verify/leak1024/runs/trace_Eur_B.txt 2>&1
ARM=trace_Ber_B CITY="rotleak Berlin.sc3" bash verify/leak1024/trace_arm.sh SC3PERF_SPR_IMGREF=0 > verify/leak1024/runs/trace_Ber_B.txt 2>&1
