# roundabout: results (2026-10-13)

PRE: `verify/roundabout/PRE.md` (committed 75641ed before the first launch). Package
`re/tools/netmod/examples/roundabout` (piece 20400 + art recipe + lanes + template `rotonda`). Tree
`Simcity_stock_roundabout` (hard links of `Simcity_stock`, stock DLLs, package installed in overlay mode), control tree
`Simcity_stock_roundabout_ctl` (nothing installed). mods_launch, sc3resize, sc3netmod built from `child/roundabout`.
Every PID mine, stopped with taskkill /PID. Logs, saves, grids, probes and raw frames stay in the instance folders
(`inst_roundabout`, `inst_roundabout_nomod`, `inst_ld`, `inst_roundabout_ctl`). Owner images:
`MAIN\verify\roundabout\owner_shots\` (8 PNG + captions.md).

## Static

| check | outcome |
|---|---|
| `netpack.py validate examples/roundabout` | OK, 0 ERROR, 1 WARNING: the 4 orientations are identical (the pinwheel is symmetric under the quarter turn) |
| two `build` runs | 25 files, sha256 identical |
| `netpack.py selftest` | 0 failures |
| id clash | `example_roundabout` and `example_roundabout_art` folded in and removed; no other package declares 20400 |

## Run R: Roadless Paradise copy (PIDs 15568, 36276 no mod, 27628, 27928)

| arm | outcome | verdict |
|---|---|---|
| L | `template roundabout/rotonda, 4 orientation(s), 4 cell(s), cost 400, flags 3`; `1 template(s), 3 of 3 slots wrapped`; `overlay: ON (23 file(s))` | met |
| K | `key T -> template 0 roundabout/rotonda (On-ramp tool selected)`, `key R -> roundabout/rotonda orientation 1` | met (the log index is 0-based, PRE wrote "template 1") |
| P | `rot 1 PLACED at (120,120) 2x2, 4 cell(s), cost 400, funds 24835 -> 24435`; cells `20400.3 20400.0 / 20400.2 20400.1` | met |
| C | (121,117..119) 29.1, (122..124,121) 29.0, (120,122..124) 29.1, far ends 11225.x; template unchanged | met |
| N | (117..119,121) 29.0, far end (116,121) 11225.3: a straight that ends against the closed W side of (120,121); template unchanged | met |
| N2 | (117..119,120) 11204.2 and (117..119,121) 11204.0 (avenue), far end (116,120/121) 11203.3 / 11203.2; template unchanged | met (SIM window); in the picture the avenue meets the block where the W exit is |
| V | 20 in-process dumps, zooms 0..4 x rotations 0..3: the block draws as a roundabout at zooms 1..4 in all 4 rotations (contact sheet, owner shot 02) | met for zooms 1..4; zoom 0 not judged (the block is a few pixels and my crop was off its centre) |
| S | log `save: 4 variant tile(s) written as base, section 0x4E56 written`; `netvariant.py scan`: 0 raw variant tiles, section lists (120,120) (120,121) (121,120) (121,121) as 39 -> 20400 | met |
| S0 | same save, instance without sc3netmod: grid x/z 112..129 equal to S except the 4 cells, which read `39.3 39.0 / 39.2 39.1` (owner shot 04) | met |
| S1 | with the mod: `load: variant section 4 entries, 4 to restore, 0 not installed`, `all 4 variant tiles restored`; grid equal to S | met |
| B | Demolish on (121,121): all 4 cells gone, exit roads ended 11225.x, the avenue end turned into a loop 11203.0 / 11203.1 at x 119 (owner shot 05) | met |

## Run T: Berlin, site (25,181) .. (26,182) (arm PIDs 35540, 19660, 8128; control 43920)

| arm | outcome | verdict |
|---|---|---|
| TP | `rot 0 PLACED at (25,181) 2x2, 4 cell(s), cost 400, funds 117006 -> 116606`, over the four stock road cells; (25,180) 39.2 -> 11203.2; exit roads unchanged. Same result when placed again on PID 19660 | met as SIM (placement over existing road cells works) |
| TR | 8 minutes, speed 4, about 2,600 game days each (`probe_T2.jsonl`, `probe_C2.jsonl`, `rb_ring.py`): arm 87 ring moves with the order, **0 against**, 41 ring -> outside, 49 into the ring (0 failed). Control: 44 with, **32 against**, 44 out, 58 in | met |
| TR, closed side | (25,180) became a curve whose arms point away from the ring: 0 moves from it into (25,181) in the arm, 15 in the control | observation |
| TD | lanekit's live grid `+0x6c` on the 4 site cells: 33 samples every 5 s, sum 113 (9 non-zero) arm vs 125 (14 non-zero) control | no prediction (stock SimTransit, density ignores lanes, as lanekit showed) |
| TS | save on PID 19660: `4 variant tile(s) written as base`; scan: 0 raw variant tiles, 4 cells in 0x4E56; reload with the mod: `all 4 variant tiles restored`, grid x 20..31 / z 176..187 equal | met |

Not pre-registered, seen in the pictures (owner shot 07): with the ring at zoom 4, 4 of 9 consecutive grabs show a car
or truck drawn over the central island. The street-sim lanes of 20400 are lanekit's curves 768 / 1025 / 257 in the T
frame (`quarter.lanes.json`), which were not drawn to follow the art's ring radius. Lane geometry vs art radius was
not measured `[UNCERTAIN]`.

### lanedensity build (not pre-registered here)

`lanedensity`'s sc3netmod.dll (`MAIN\re\harness\inst_lanedensity`, built from child/lanedensity 08384b1, sha256
`5a3746293c39f6e5...`, its own arms still running at the time) on my tree, instance `inst_ld`, the TS save, 14 months
each with `ld_probe.py --start 4` (monthly published grid `+0x60`, months 3..14 averaged):

| | OFF (`SC3NETMOD_LANEDENSITY=0`) | ON (default, variants) | OFF2 |
|---|---|---|---|
| ring (25,181) (26,181) (25,182) (26,182) | 0.0 / 5.7 / 0.0 / 5.7, sum 11.3 | 18.7 / 19.2 / 18.7 / 0.0, sum 56.5 | 1.0 / 12.2 / 0.0 / 6.6, sum 19.8 |
| N exit (26,180) | 7.0 | 18.7 | 12.2 |
| (25,180) | 8.7 | 29.0 | 18.1 |
| whole map mean | 13.29 | 13.14 | 13.25 |

ON log: `honoured steps=85 neighbours closed=45 wrong-way fails=0 arrivals refused=0`; per cell (entry, exit) counts:
(26,181) z- -> x- 41, (25,181) x+ -> z+ 41, (25,182) z- -> x+ 1: every router step through the ring followed the ring
order. Density moved from (26,182) onto (25,181) / (25,182). The values are small (this junction carries little routed
traffic) and OFF vs OFF2 differ by 75 %, so the size of the change is not established from one run per arm.

## Deviations

1. Run R, B: the first reload (PID 27628) opened in the saved camera rotation 3; `mt_drive.py goto` looped and I
   stopped it; the next `nramp_cam.py` call was followed by the game exiting with no crash log and no Windows event.
   Cause not established. B was done on a fresh reload (PID 27928) after setting rotation 0 first.
2. Run T: the first probes (camera placed by `nramp_cam.py` direct camera calls) saw 0 street-sim moves in 120 s in
   both games. Stopped, cameras moved with lanekit's method (minimap click (758,503) + two zoom-in clicks), probes
   restarted (`probe_T2`, `probe_C2`, the numbers above).
3. Run T: after the probes, an `nramp_cam.py` call on the running arm sim left it stopped (0 days in 21 s, `bracket`
   1; lanekit saw the same once) and sc3resize's dump trigger stopped answering. The traffic and density samples were
   already taken (days advanced in every sample). TS ran on a relaunch (PID 19660) with the template placed again.
   Rule kept for later runs: no `nramp_cam.py` while the sim runs.

Functions read for this task: none new (package and verification only). Code paths used are cited in MULTITILE.md,
NET_LANES.md, NET_ART.md and NETVARIANT.md.
