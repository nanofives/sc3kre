#!/bin/bash
cd /c/Users/maria/Desktop/Proyectos/Simcity
o=verify/leak1024/runs
B="rotleak Berlin.sc3"
py -3.12 verify/leak1024/rotmem.py Berlin_B20 --n 20 --gap 2 --wait 150 --city "$B" --env SC3PERF_SPR_IMGREF=0 > $o/Berlin_B20.txt 2>&1; echo "$(tail -1 $o/Berlin_B20.txt)"
py -3.12 verify/leak1024/rotmem.py Berlin_A20 --n 20 --gap 2 --wait 150 --city "$B" > $o/Berlin_A20.txt 2>&1; echo "$(tail -1 $o/Berlin_A20.txt)"
py -3.12 verify/leak1024/rotmem.py Eur_B_shots --n 3 --gap 3 --wait 150 --city "Europolis 1024.sc3" --env SC3PERF_SPR_IMGREF=0 --shots 3 > $o/Eur_B_shots.txt 2>&1; echo "$(tail -1 $o/Eur_B_shots.txt)"
