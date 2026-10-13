# netvariant: pre-registration (written and committed before any game run, 2026-10-13)

Two owner-requested gaps of the new piece id 20029 (blue clone of road straight 29, `verify/newpiece`):
(1) rail and power lines do not cross it; (2) a save holding it, opened without the mod, drops those tiles.
Fix under test: `re/harness/src/sc3netmod.c` (new DLL, injected by `mods_launch.exe`), variant table
`Apps\Res\netmod_variants.txt` = `20029 29` written by `newpiece.py build` (new `"base"` in manifest.json).

## Setup

- Tree `C:\Users\maria\Desktop\Proyectos\Simcity_stock_netvariant\` = hard links of `Simcity_stock`
  (`link_tree.py`), stock GOG DLLs, Spanish text. Mod data from `newpiece.py build --id 20029 --src 29`
  (`verify/netvariant/mod_blue/`), installed/uninstalled with `newpiece.py install|uninstall` (delete + copy).
- Instances (same tree): `re\harness\inst_netvariant\` = mods_launch + sc3resize (child/netvariant build, used
  only for its in-process frame DUMP and Copiar ID) + **sc3netmod**; `re\harness\inst_nvstock\` = mods_launch +
  sc3resize, **no sc3netmod**. "Stock" arms below = inst_nvstock with the mod data UNinstalled: stock DLLs, stock
  data, no network code changed. sc3resize does not touch networks or saves.
- City: `verify/newpiece` arm M's save (`Roadless Paradise` + two roads; 22 tiles of 20029: x=102 y=150..160
  state 1, y=149 x=87..98 state 0). Copied into the instance folder per arm.
- Oracles: (a) the save file read by `network_layer.py` (+ the new section, read by `netvariant.py scan`);
  (b) live cells via `np_drive.py cells` (Frida, read only: piece id, state); (c) frames (sc3io grab, or the
  sc3resize in-process DUMP if grabs are white; which one is said per frame); (d) `sc3netmod.log`.

## Static basis (cited in re/analysis/NETVARIANT.md)

- Crossing creation `FUN_100167d4` reads the existing piece id with `FUN_1001a93d` at `0x10016821` and only
  forms a crossing for {0x49, 0xe, 0xf, 0x1d, 0x2c, 0x5c, 0x2bc4, 0x3acb} -> row of matrix `DAT_100318ac`
  (values id*256+state: road x rail = 69, road x power = 67). sc3netmod redirects that one call so a variant
  reports its base. Further sites only if the inventory finds a gate that the drag reaches first; any such site
  is added in an addendum here BEFORE the run that uses it.
- Save: tile word1 low 16 bits = id, written by `FUN_1000d688` from `FUN_10012fc3` (call at `0x10013082`).
  sc3netmod writes the base id there and the list `{word0, word1 as saved, variant id}` into an extra section
  `{0x206c6e7c, 0x2147c2dd, instance 0x4E56}` with the game's own writer (`FUN_10026129`) after the three
  networks (`0x10012ee0`). Load `FUN_100130e9` reads instances 0..3 by key; sc3netmod reads 0x4E56 at its entry
  and swaps the id back after each tile read (`FUN_1000d6b3` calls at `0x10013264/0x13338/0x1340b`).

## Arms and predictions

**X1 rail, mod + sc3netmod.** Load M's city, Rail tool (0x10004101), drag a rail east-west across x=102 at y=156.
Predict: (102,156) becomes piece 69 (state per stock), rail on both sides of the road, the other 10 blue tiles of
that road stay 20029 and blue, no fault. Log shows `cross lookups mapped` > 0.
**X0 rail, mod + sc3netmod with SC3NETMOD_CROSS=0.** Same input. Predict: as newpiece XM, rail stops at the road,
(102,156) stays 20029 (the opt-out restores stock behaviour).
**P1 power, mod + sc3netmod.** Wires tool (0x10005001), same kind of drag at y=153. Predict (102,153) -> 67, line
on both sides, rest blue.
**T traffic.** After X1, save; the road's tiles on both sides of the crossing remain ROAD pieces in the file
(20029 or 29 for the rest, 69 at the crossing). Routing over a crossing is the stock mechanism (69 is a stock road
piece); a density run is done only if time allows and is labelled exploratory.

**S1 save, mod + sc3netmod.** Load M's city (raw 20029 words), save. Predict: the file's 22 tiles read piece 29
(same x, y, z, state, props as before), a section `{0x206c6e7c,0x2147c2dd,0x4E56}` lists the same 22 tiles with
id 20029; log `save: 22 variant tile(s) written as base`.
**S2 stock open.** inst_nvstock, data uninstalled, load S1's save. Predict: no crash, the 22 tiles live as piece
29, drawn grey (stock straight), the rest of the city identical to S1's file; save -> S2 file: same 206 surface
tiles as S1 (stock rewrites the file without the 0x4E56 section is NOT predicted either way: recorded).
**S3 mod reopen.** inst_netvariant, data installed, load S1's save. Predict: the 22 tiles live as 20029 with the
same state as in M, drawn blue; log `all 22 variant tiles restored`. Save -> S3 file = S1 file's networks
(same 29 words + section).
**S4 second round trip.** S3's save -> stock open (as S2) -> mod reopen (as S3): same results.
**S5 stock resave then mod.** S2's save (written by stock) opened with the mod: if stock dropped the section the
tiles stay 29 (grey) and that is the documented limit; if stock kept it they come back blue. No prediction.
**SB opt-out.** SC3NETMOD_SAVEBASE=0, load M, save: the file keeps raw 20029 words and has no 0x4E56 section.
**R old raw save.** (measured by newpiece arm R: without the mod the 22 tiles are dropped on load and on the next
save). Here: open M's raw save with mod + sc3netmod and save once -> predicted to become an S1-type file (repair
by one save). Offline repair `netvariant.py fallback` (raw ids -> base + section) is checked against S1's file
shape and then loaded in S2/S3 arms if time allows.

## Not claimed
Highway, onramps, subway, pipes, bridges and other bases; variants of rail or power pieces; a crossing over a
variant keeping the variant's look (it becomes the stock crossing tile, by design in this first version);
what the crossing tile turns back into when the rail is removed (recorded if seen, not predicted); 1024 cities;
the owner's dev install.

## Addendum 1 (2026-10-13, after arm S1 and a first X1 attempt, before the X1/X0/P1 runs below)

First X1 attempt (build with only the `0x10016821` site): rail laid from the west and stopped at the blue road,
no crossing, `crossing-switch lookups mapped=0`, so the switch was never reached. A live read-only Frida trace of
the id getters during a second rail drag showed the 20029 reads came from `FUN_1001af19` (vt+0x5c at
`0x1001af4f`), `FUN_1001ade7` (`0x1001ae22`) and `FUN_10014939` (`FUN_1001a93d` at `0x1001497c`). The inventory
(re/analysis/NETVARIANT.md) explains the order: a path planner outside SIMNTWRK asks the rotation-aware predicates
(index 0x10..0x1b of manager vt+0x54) per cell, then SIMNTWRK `FUN_1001547b` calls the crossing `FUN_100167d4`
with the per-network id-list predicate (`FUN_1001ac2b` for rail), and only then the switch.

Hook set for the runs below: the switch site `0x10016821` as before, plus the two id getters `0x1000c2fc`
(vt+0x5c) and `0x1000cc83` (vt+0x30) report the base only while one of 15 wrapped predicates runs on the same
thread: id lists `0x1001ab26/0x1001ac2b/0x1001abb2/0x1001acbe`, flag-or-0xe/0xf `0x1001ad60/0x1001ade7/0x1001ae36`,
rotation lists `0x1001ae85/0x1001af19/0x1001afc7/0x1001b07c/0x1001b10c/0x1001b248/0x1001b1a1/0x1001b2e0`. Not
wrapped: the decoration predicates `0x1001b378/0x1001b3c4`. Predictions for X1, X0, P1 unchanged. Added for X1: the
log shows `predicate id reads mapped` > 0 and `crossing-switch lookups mapped` > 0.
