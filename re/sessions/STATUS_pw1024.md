# STATUS pw1024 (round 2026-11-23e, orchestrator "SC3: pending items after recent rounds + SC4 style status")

## goal
Player report: on a 1024 map power and water stop spreading about mid map along a power line / pipe.

## verdict + deciding RVA
CAUSE FOUND AND FIXED (game-side). Both coverage fills are iteration-capped flood fills that grow one cell per
iteration per axis, with caps sized for 256 maps.
- power: SIMUTIL `sc3_power_distribute_region` 0x10004e57, `push 0x258` (600) at 0x10004e85, call at 0x10004e99 into
  `sc3_bitraster_grow_capped` 0x1000bbfc [CONFIRMED @ 0x10004e85]
- water: SIMUTIL FUN_1000e8c4 (water layer tick), `push 0x1f4` (500) at 0x1000eab9, call at 0x1000eac9 [CONFIRMED @ 0x1000eab9]
- only these two call 0x1000bbfc (E8 scan of SIMUTIL .text)
Fix: sc3bigcity GRIDCAP block routes both calls through a wrapper that passes cap * width / 128 when width > 256
(1024: 4800 / 4000), the shipped cap otherwise. SC3BIGCITY_GRIDCAP=0 off, =2 log only. /256 was too tight:
Europolis 1024 needs 1930 water iterations.

## built
- dev\pw1024\inst\sc3bigcity.dll (sc3dev build pw1024 -Mods sc3bigcity), clean, final = /128 build

## proven game-side vs static only
Game-side, 1024 New City (dev tree), plant at x 2 row 500 + power line x 7..1023 row 501, water tower x 2 row 520
(powered) + pipe x 4..1023 row 520:
- shipped caps (GRIDCAP=2): power fill "cap reached (600 iterations) region x 0..602"; water "cap reached (500
  iterations) region x 2..502". Pictures: verify/pw1024/owner_shots/before_*.png
- fix (GRIDCAP=1), same save: power "1022 iterations ... region x 0..1023, 0.97 ms"; water "1022 iterations ... region
  x 2..1023, 0.36 ms". Pictures: after_*.png
- reload of a save written by the fixed build: same regions. A/B days per minute: no slowdown (repro 90 vs 90-91,
  Europolis 1024 71-81 shipped vs 83-84 fixed). Europolis 1024 also hit both shipped caps.
- DONE. Full record: verify/pw1024/RESULTS.md

## blocked on
nothing

## files owned
- dev\pw1024\wt\re\harness\src\sc3bigcity.c (GRIDCAP block before "boot", watcher: utilm + env var)
- dev\pw1024\wt\re\tools\pw1024_lab.py (new: long line / pipe builder over nb_drive)
- dev\pw1024\wt\re\analysis\POWER_GRID.md (cap call sites corrected, new section on the cap above 256)
- not committed: dev\pw1024\inst\bigcity.ini (size 1024, selected 1, test setting only)
- MAIN verify\pw1024\ (RESULTS.md, logs, ab_run.sh, repro saves, owner_shots\)
- MAIN re\sessions\STATUS_pw1024.md

## game-harness need
own tree dev\pw1024\tree, windowed

## asks of other sessions
none
