# RESULTS - sc3mods release 2026-11-17c + LAN 2026-11-17c

Replaces `sc3mods-2026-11-17` (GitHub) and LAN `2026-11-17b`. Owner call 2026-11-17: "Yes, release now", after the
rotation leak fix and the short diagonal boulevard arms were merged. Source: main 60d89c2 (17ed4e8 adds records only).

| what | merges | record |
|---|---|---|
| Rotation / zoom memory leak (sc3perf SPR_IMGREF, off: `SC3PERF_SPR_IMGREF=0`, `perf.ini spr_imgref=0`) | fd32aff | verify/rotleak/RESULTS.md |
| Short diagonal boulevard arms convert (sc3netmod DBVSHORT, off: `SC3NETMOD_DBVSHORT=0`), 19 34 43 45 50 52 54 55. 49 51 53 still mixed | 60d89c2 | verify/diagarm/RESULTS.md |

Not in the build: 8c2e413 (roadloss) changes only the offline zoning tool `city_write`, which is not shipped.

## Stage and checks

- DLLs: `stage/build_1117c` = sc3perf.dll and sc3netmod.dll built from main. `stage/bins_1117c` = `stage/bins_1117`
  with those two replaced. No pack, art or table change, so stage/src (ledger 26 packs) is unchanged.
  sc3perf.dll SHA-256 32012949DFFDCB2228DBF2C39F259FE4F56956273EE0A0E957A2B8377BB43EA4,
  sc3netmod.dll 2CDFE20C624832E2FB5995B8D5460BD3D331DE00A17EF40233950D019D81EEAE.
- Jotti's malware scan: sc3perf.dll 0 / 13, sc3netmod.dll 0 / 13.
- `stage_lan_release.py --bins stage/bins_1117c ... --label 2026-11-17c`: 3,680 files. Against 2026-11-17b: 2 changed
  (Apps/sc3netmod.dll, Apps/sc3perf.dll). `stage/release` swapped (old one kept as `stage/release_1117b_old`), LAN
  deploy incremental (2 of 3,680 files, 0.7 MB), served label `2026-11-17c 3680`, served sc3perf.dll SHA-256 matches.
- Fix evidence is in the two child records (100-rotation and 15-minute A/B for SPR_IMGREF, both draw orders and the
  77-case regression for DBVSHORT). No separate release sweep: the rest of the build is byte-identical to 2026-11-17b.

## Zip

The 2026-11-17 zip tree with the two DLLs from `stage/bins_1117c` and README.txt updated (header 2026-11-17c, NEW IN
2026-11-17c). 194 entries: 192 equal to the LAN manifest, 1 differs by design (overlay SYS.PAK without the community
lines, as in 11-17), README.txt not in it. `sc3mods_2026-11-17c.zip` 92,360,034 bytes,
SHA-256 FD2033E28457F1DD1FE1903A1B2B5C64A2F7F34BAC0338D8B8974801D583E6EA.

Not checked (owner): a hand session turning the view many times on the released build, 1024 cities for the leak.
