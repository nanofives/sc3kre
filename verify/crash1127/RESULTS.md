# crash1127: Europolis 1024 / Big One load crash on MARIANO-PC (2026-11-27)

## Report
Owner, MARIANO-PC, release sc3mods-2026-11-26: "Big One and Europolis 1024 both crashed the game".

## Evidence (read-only from MARIANO-PC)
- `Apps\SC3U_stkdmp.txt`: 2 new records, 2026-11-27 00:16:09 and 00:16:22, both ACCESS_VIOLATION at SIMSPR+0x15B9.
- `sc3resize.log` of the second run (thread 4336 = the dump's thread): `VEH FAULT ... SIMSPR.DLL+0x15B9`, READ 0x8,
  15 ms after `INITSLACK> #1 city view Init`. `sc3bigcity.log`: QFS24 true size 38,666,793 bytes = Europolis 1024.
- Stack: cityviewiso_init_city_dbsegment -> occbridge_init -> occbridge_fill_all_tiles -> ... ->
  spr_insert_cell_aligned_sprite 0x100192aa -> spritecellmap_insert 0x10007b4d -> FUN_10006efc -> sprite vt+0x34
  0x10015970 -> FUN_1005ad98 -> FUN_10001592 -> FUN_100015a8. FUN_100015a8 reads the frame's image record
  `[ref+8]` (ref = `*(sprite+0x18) + zoom*0xC`) and calls PrepareImage (ImageMgr slot 0x38, 0x10012b98). The record was 0.
- Binaries on MARIANO-PC = release (SHA-256 of SIMSPR, sc3perf, sc3resize, sc3netmod equal the staged files).
  The netmod overlay had 132 files against the release's 131: an extra `Apps\Res\Sprites\CSATTRIB.IXF`.

## Cause
That `CSATTRIB.IXF` is the avenue_markings reskin of stock piece 11204 (0x2BC4): its 40 frames point at
`0x4E3D0033` instance N instead of stock group 5. The 11-09 release removed it (`verify/mods_release_1109/RESULTS.md`),
but the LAN updater deletes only with `-Prune` and unzipping never deletes, so it stayed. Later netpack builds no longer
hold those instances in `4E3D0033_netpack.DAT`, so every 11204 frame has no image record and the first insert faults.

## Reproduction (LIVING-PC, dev/crash1127, owner's city + ini files, client 2548x1332)
| Run | Overlay | Result |
|---|---|---|
| Europolis 1024, release overlay | 131 files | loads, no fault |
| same + owner's SC3.cfg | 131 | loads, no fault |
| same + owner's CSATTRIB.IXF | 132 | **VEH FAULT SIMSPR+0x15B9 READ 0x8**, game exits (= owner) |
| Big One + owner's CSATTRIB.IXF | 132 | loads, no fault (no 11204 in it) |

## Fix
- **sc3netmod OVSTALE** (`sc3netmod_ovmerge.c`): after `overlay_base.txt` loads, an overlay file that shadows a game
  file but is not listed there is dropped from the served set and logged `### ovstale`. Both the release and
  `netpack.py install` rebuild that list with every shadowing file. Dry run over the release overlay: 34 shadowing
  files, 34 listed, 0 dropped. `SC3NETMOD_OVSTALE=0` serves everything.
- **sc3perf NULLIMG**: the calls to FUN_100015a8 (Prepare) and FUN_100015da (Unprepare, same shape, faults at
  SIMSPR+0x15E9) go through stubs that return 0 for a NULL image record. Every other reader of that ref table already
  tests the record. `SC3PERF_NULLIMG=0` keeps the shipped calls.

## Tests (Europolis 1024 + the stale file)
| Test | Expect | Result |
|---|---|---|
| T1 default | `ovstale: 1 ... dropped: CSATTRIB.IXF`, load clean | met: dropped, view up, alive 30 s, NULLIMG 0 hits |
| T2 `SC3NETMOD_OVSTALE=0`, Prepare guard only | no crash | partial: load passed (512+ guarded prepares), died at 20 s at SIMSPR+0x15E9 (Unprepare) |
| T2b same, Prepare + Unprepare guard | no crash | met: "2 of 2 SIMSPR sites guarded", 1,024+ guarded frames, alive ~4 min, only the benign 0xC0000096 startup line; city drawn (Pob 29,130,776) |

## Owner action
Delete `Simcity\mods\netmod\overlay\Apps\Res\Sprites\CSATTRIB.IXF` on MARIANO-PC, or run `update.bat -Prune` once.
With the new build the file is ignored anyway (`### ovstale` in sc3netmod.log).
Open: Big One loads here even with the file; the owner's dump has only the two Europolis records.
