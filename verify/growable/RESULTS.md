# growable: a custom zoned building ADDED to the growth pool (2026-11-10)

Verdict: **works, data only, no code.** A new residential building (occupant id 36001, a red copy of Pitched Roof
Cottage) was added to BUILDFAM family 11 next to the 12 stock members. Nothing stock was replaced. It grew in game
on its own (954 lots in the first autosave of Moscow), survives save and reload with the mod, and a save loaded
without the mod does not crash: the lots come back empty and regrow with stock houses.

Requirement found on the way: the exemplar must sit in a container listed in `[OccAttribCache]`. Moved to a new
container reached only through a `[DBSegments]` row, the game crashed in the residential developer twice out of two
runs (arm OC below).

Question from a Simtropolis player. Static RE: `re/analysis/BUILDING_PICK.md` section 6 (C).

## What was built

Reproducible as a netpack package. No hand-edited bytes.

| File | What |
|---|---|
| `re/tools/netmod/netpack_growables.py` | new: compiles and merges the `growables` manifest key |
| `re/tools/netmod/netpack.py` | wires `growables` into compile, merge and the build report (+42 / -10 lines) |
| `re/tools/netmod/netpack.schema.json` | `growables` property + `$defs/growable` |
| `re/tools/netmod/examples/growable_test/manifest.json` | the test package |

Manifest entry:

```json
{"id": 36001, "base": 3065, "family": 11, "weight": 50,
 "name": {"*": "Casa roja de prueba", "ENGLISH": "Casa roja de prueba"},
 "art": {"recolor": "red"}}
```

What one entry becomes (offline build checked with `ixf_parse`, then installed):

| Piece | Key / value | Container |
|---|---|---|
| Exemplar | TKB1 `{0x207EDC0E, 0x57E, 36001}`, a copy of 3065's record: prop 0x64 = `Casa roja de prueba`, prop 0x65 = 3100 (0x0C1C), prop 0x66 footprint unchanged (1x1), prop 0x67 -> `{0x6300, 0x55908ADB, 36001}`, prop 0x6D -> `{0x2026960B, 0xA1096A4F, 36001}` | `Res\Occupant\OccupantAttribs_Korea.IXF` (`[OccAttribCache]` Entry5) |
| Frame table | `{0x6300, 0x55908ADB, 36001}`, 20 frames, pointing at `{0x4E3D0034, 0x8CA10000..}` once merged with the road packages (`0x4E3D0001` in a stand-alone build) | `Res\Sprites\CSAttrib_Korea.IXF` |
| Pixels | 3065's frames recoloured red, keys `(group, 36001 << 16 \| ordinal)` | `Res\Sprites\4E3D0034_netpack.DAT` (netpack's merged DAT) |
| Name | `{0x2026960B, 0xA1096A4F, 36001}` in 7 language folders | `Res\Text\<lang>\SC3StringsNetpack.IXF` |
| Family line | `Key: 1406,545184782,36001,50` inserted right after `BuildingCount`, count 12 -> 13 | `Res\BUILDFAM.IXF` record `{0x81F53D09, 0x01F58D3D, 11}` |

Why the family line goes first: the parser `SIMGEOM 0x10001250` reads `LandUse`, `BuildingCount`, then `Key:`
lines until it has resolved `BuildingCount` of them. A key with weight 0 or one the attrib cache cannot resolve
(`vt+0x14` with `0x21183b00`) lowers the count instead [CONFIRMED @ 0x1000136f]. A line placed first is always read.
Free id: base `0x207EDC0E` ids top out at 35,005 (661 building exemplars counted in the dev tree).

Family 11 after the patch (LandUse 3100, "Residential Low Density Low Land Value"): 36001 at weight 50, then the 12
stock members at weight 1 (112, 113, 114, 3012, 3013, 3025, 3065, 3066, 3067, 3072, 3074, 3075).

Install: `netpack.py install wt/re/tools/netmod/examples/growable_test --tree dev/growable/tree`, merged with the
20 road packages of the staged release (their `packs\` and `ledger.json` copied from `stage/src/mods/netmod`).
Overlay diff against the staged release: `BUILDFAM.IXF` added; `OccupantAttribs_Korea.IXF`, `CSAttrib_Korea.IXF`,
`4E3D0034_netpack.DAT`, the 7 `SC3StringsNetpack.IXF` and `SYS.PAK` changed. `netpack.py uninstall growable_test` gives back the staged overlay
byte for byte except `SYS.PAK` (side finding below).

## Evidence

Dev workspace `dev/growable`, city `Moscow, Russia.sc3` (24,512 occupants, 3,551 of them family-11 houses, the
most of the 16 cities in the tree). Windowed, posted keys only (0x50 unpause, 0x34 speed 4). Churn sped up with
`inst\simrun.ini` `[churn] anarchy_res=5000`. Autosave every 120 to 180 s (`SC3AUTOSAVE_SECONDS`). Counts from
`occupant_layer.py` (key `{0x207EDC0E, 0x57E, id}`).

| Save | Occupants | Family-11 stock ids | id 36001 | LandUse 3100 |
|---|---|---|---|---|
| Moscow as shipped | 24,512 | 3,551 | 0 | 3,551 |
| (1) first autosave, mod on (180 s autosave setting, speed 4) | 24,645 | 3,170 | **954** | 4,124 |
| (3) that save reloaded with the mod, run, resaved | 24,468 | 3,098 | **931** | 4,029 |
| (4) same save loaded WITHOUT the mod, run, resaved | 24,441 | 3,994 | 0 | 4,002 |

1. **The new id grows.** 954 houses with id 36001 in the first autosave, spread across the low-wealth area (densest
   21x21 cell window: 41 of them around cell (232, 56)). Stock family-11 members kept growing too (3,170).
2. **Screenshots** (`MAIN\verify\growable\owner_shots\`, not committed): `t1_red_cluster.png` and
   `t2_red_closeup.png` show the red houses among stock houses. `t0_moscow_start.png` is the city before.
3. **Reload with the mod:** `growable_A.sc3` (copy of save 1) loaded with no fault, red houses on screen
   (`t3_reload_with_mod.png`, `t4_reload_after_run.png`), and its next autosave still holds 931 of id 36001.
4. **Load WITHOUT the mod** (package uninstalled, the other 20 packages kept): no crash, no VEH fault from SIMGEOM or
   SIMRCI. The red houses are gone on load and their lots show as empty zoned land (`t5_load_without_mod.png`). After
   the run the next save holds 0 of id 36001 and 896 more family-11 stock houses than save 3 (3,994 against 3,098):
   the lots regrew with stock buildings (`t6_without_mod_after_run.png`). So an unresolved occupant key is dropped on
   load. Which branch of `SIMGEOM 0x1001e516` / `0x10002cc2` drops it was not traced.

Every run logs one `0xC0000096 at SC3U.exe+0x84122` VEH entry about 1 s after start. The same entry is in
`dev/autosave`'s log, so it predates this work. It does not stop the game.

### Arm OC: is an `[OccAttribCache]` entry needed? Yes, in this test

Set-up (overlay only, restored afterwards): the 36001 exemplar removed from `OccupantAttribs_Korea.IXF` and put
alone in a new `Res\Occupant\OccupantAttribs_GrowTest.IXF`, registered by an added `[DBSegments]` row
`0x47524f57=0x80c381d7;Res\Occupant\OccupantAttribs_GrowTest.IXF` in `Default.ini`. Family line, frame table and
pixels unchanged. The netmod file log shows `GZResourceD.dll` opening the new container through the overlay.

| Run | Result |
|---|---|
| OC 1, fresh Moscow | game gone ~3 s after unpause. VEH: `0xC0000005 at SIMRCI.DLL+0x26D6D`, READ of `0x74AD646C` |
| OC 2, same set-up | same fault, same RVA, ~2.7 s after unpause, READ of `0x74337473` |
| Korea arm (exemplar in Entry5) | 2 launches with the package (save 1, save 3), no such fault. A third launch without the package (save 4) had none either |

`SIMRCI 0x10026D6D` is `mov edx,[eax]` / `call [edx+0x40]` inside `sc3_resdev_place_lots_block_v3`
(`0x10026b01`): the residential developer calling slot `+0x40` on an attrib object whose first dword is not a
valid vtable (`8b 10` mov edx,[eax] at 0x10026D69, `ff 52 40` at 0x10026D6D; the faulting read is edx+0x40). The
VEH stack scan in both runs shows return-address words `SIMGEOM+0x1AED2`, `+0x1CB2B`, `+0x30B00`. Why the object is bad when its exemplar lives outside `[OccAttribCache]` is [UNCERTAIN]:
the attrib-cache build for non-cache containers was not read. Practical rule: put new building exemplars in a
container that `[OccAttribCache]` lists (netpack's Korea pair does this), or add an `[OccAttribCache]` entry for a
new container (not tested).

## Not checked

- The in-game query ("Copiar ID") on a red house. The saved key settles the id.
- An `[OccAttribCache]` entry for a separate container (only "Korea: works" and "no entry: crashes" were run).
- Weights other than 50, a second new building in the same family, other LandUses (commercial, industrial,
  2x2 and larger footprints), a new `[ZoneDeveloperRules]` row.
- Behaviour with a building style (European / Asian set) active. Set 0 only.
- How the game draws a 36001 house at the zoom levels the screenshots did not use.
- Why `t18 == 3100` exceeds the family-11 count by 8 in save 4 (raw numbers in the table).

## Side finding: the staged netmod overlay hides the Civic Deals SYS.PAK edits

`stage/release/Apps/Sys/SYS.PAK` (sha256 `bb4e3126…`) carries the Civic Deals additions
(`PetitionerExtraInfo.ini` + `0x000000D9`, `0x000000DA`, `0x000000DB` = `19,2`; `PetitionerManager.ini`
`NumberOfPetitionerMessages` 210 -> 212). The netmod overlay copy `stage/release/mods/netmod/overlay/Apps/Sys/SYS.PAK`
(`73a49107…`, the hash in `stage/src/mods/netmod/ledger.json`) does not. sc3netmod answers the game's `SYS.PAK`
open from the overlay (netmod file log: `GetFileAttributesA ...\Apps\Sys\SYS.PAK -> overlay exists`), so in the
staged build the Civic Deals lines are not what the game reads. Re-running netpack in a tree merges against that
tree's own SYS.PAK and brings them back, which is the only reason this tree's overlay SYS.PAK differs from the
staged one. In-game effect on the Civic Deals petitioners was not checked. Whether a player's install hits this
depends on whether `community_patch.ps1` runs before or after the netmod overlay is built.

## Files

- Commit: `re/tools/netmod/netpack_growables.py`, `re/tools/netmod/netpack.py`,
  `re/tools/netmod/netpack.schema.json`, `re/tools/netmod/examples/growable_test/manifest.json`,
  `re/analysis/BUILDING_PICK.md`, `verify/growable/RESULTS.md`.
- Not committed: `MAIN\verify\growable\owner_shots\t0..t6*.png`, the saves in `dev/growable/tree/Cities`.
