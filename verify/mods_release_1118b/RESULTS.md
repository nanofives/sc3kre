# RESULTS - sc3mods release 2026-11-18b + LAN 2026-11-18b

Replaces sc3mods-2026-11-18. Owner calls 2026-11-18: style mix switch (Simtropolis NicoMT), faster highway cars as a
mods page row, on by default, x1.5, curves stock (Simtropolis Spamoidutout). Source: main ea8053d.

| what | merges | record |
|---|---|---|
| "Building style mix" row, SC3NETMOD_STYLEMIX=0 (weight-0 BUILDFAM copy, saved mix buildings keep their look) | 5acc061 | verify/stylemix/RESULTS.md |
| "Faster highway cars" row, sc3simrun HWYSPEED x1.5 on lanes above e3 66000, default on, SC3SIMRUN_HWYSPEED=0 | 4dadae2 | verify/hwyspeed/RESULTS.md, re/analysis/VEHICLE_SPEED.md |

## Stage and checks

- DLLs from main into stage/build_1118b: sc3netmod, sc3resize, sc3simrun. stage/bins_1118b = bins_1118 + those + the 7
  lang tables (sc3lang check: 348 keys, 0 missing). Jotti: 0 / 13 each.
- stage_lan_release.py label 2026-11-18b: 3,679 files, against 2026-11-18 exactly 10 changed (3 DLLs, 7 lang tables).
  stage/release swapped (old: stage/release_1118_old), LAN deploy incremental (10 files, 1.6 MB), served label
  2026-11-18b 3679.
- Smoke: dev tree from the new stage with the shipped DLLs, xsect_sweep_built.sc3 loaded windowed: log
  "stylemix: on" and "### HWYSPEED: on, factor_pct=150 threshold=66000, 2 of 2 slots armed", only the usual startup
  0xC0000096 VEH line.

## Zip

The 2026-11-18 zip tree with the 3 DLLs and Apps/sc3lang from the repo, README.txt (header 2026-11-18b, NEW IN
2026-11-18b). 193 entries: 191 equal to the LAN manifest, overlay SYS.PAK differs by design, README.txt not in it.
sc3mods_2026-11-18b.zip, SHA-256 E6C3855FDC06172B4709157F51C6351A96856B37718FA12BB6A2927FDB558B62.

Not checked: the mods page in languages other than Spanish (de, fr, it, nl, sv row texts are the children's translations).
