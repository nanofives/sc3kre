#!/bin/bash
cd /c/Users/maria/Desktop/Proyectos/Simcity/verify/leak1024
for spec in "Eur_load|Europolis 1024.sc3|0" "Eur_zin|Europolis 1024.sc3|8" "Ber_load|rotleak Berlin.sc3|0"; do
 IFS='|' read a c z <<< "$spec"
 py -3.12 rotmem.py zs_$a --n 1 --gap 2 --wait 150 --city "$c" --zin $z --shots 1 > runs/zs_$a.txt 2>&1; tail -1 runs/zs_$a.txt
done
