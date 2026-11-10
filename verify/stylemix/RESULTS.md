# stylemix: the three building styles grow side by side, at random, in one city (2026-11-10)

Verdict: **works, data only, no code.** A netpack package (`style_mix`) adds every European and Asian building that
re-skins a zoned building as a NEW building next to the North American one. In Moscow it grew 2,887 European and
2,833 Asian buildings by the first autosave, the three styles stand in one view, save and reload with the mod pass,
switching the city's style inside one session keeps the art, and a save loaded without the mod does not crash.

Asked by a Simtropolis player. Static RE: `re/analysis/BUILDING_PICK.md` sections 0, 3 and 6 (A).

Two findings changed the picture on the way:

1. **Every city stores its own style.** Record `{0x0525A6B9, 0x4525A6E2, 1}`, 12 bytes = building set, flora,
   landscape, read on load by SIMINIT `FUN_10009e1f` and passed to `SetCityScheme`. Moscow, Berlin, London and most
   shipped European cities are saved with the European set, Seoul and Craterville with the Asian one, Madison,
   Sacramento, Farmsville and Roadless Paradise with the default. So "keep the building set at 0" is per city, not a
   game option, and the first runs below had the European set active without being asked to.
2. **A load without the mod keeps the buildings.** Each copy is replaced on load by another building of the same
   building type, measured on a save taken while still paused. growable's note for 36001 says those lots came back
   empty. That disagrees and is worth a paused recheck there.

## What was built

| File | What |
|---|---|
| `re/tools/netmod/netpack_stylesets.py` | new: compiles the `style_sets` manifest key |
| `re/tools/netmod/netpack.py` | wires `style_sets` into compile, merge (collisions, Korea pair, set DATs, BUILDFAM lines) and the report (also prints growables now) |
| `re/tools/netmod/netpack.schema.json` | `style_sets` property + `$defs/style_set` |
| `re/tools/netmod/stylemix_build.py` + `manifest.json` | the package, written by script (`--euro N --asian N` set the weights) |
| `re/tools/netmod/examples/style_mix/README.md` | player-facing description |
| `verify/stylemix/*.py` | the checks below: style counts, legend sheet, live scheme read, save scheme read/patch, no-mod diff |

Manifest:

```json
"style_sets": [{"set": "e523f3fb", "offset": 400000, "weight": 1},
               {"set": "6523f3d5", "offset": 1500000, "weight": 1}]
```

What one set becomes (computed at install time from the tree's own set archives, so the package holds no game art):

| Piece | Key / value | Container |
|---|---|---|
| Exemplar | the SET's TKB1 record, verbatim, at `{0x207EDC0E, 0x57E, id + offset}`. prop 0x67 (the set's frame table) and prop 0x6D (the set's name in `SC3MBEStringsBuildings.IXF`, a stock `[DBSegments]` row) unchanged | `OccupantAttribs_Korea.IXF` (`[OccAttribCache]` Entry5) |
| Frame tables | the set's `0x6300` records (and `0x6301` for 3 European / 5 Asian buildings) named by prop 0x67, verbatim, keys unchanged (groups `0x5432D60F` / `0x547B7DF6`, no stock container uses them) | `CSAttrib_Korea.IXF` |
| Pixels | every type 0 + type 1 record those tables name, verbatim, in the set DAT's order | `Res\Sprites\5432D60E_netpack_set.DAT` (10.4 MB), `547B7DF5_netpack_set.DAT` (18.8 MB) |
| Family lines | `Key: 1406,545184782,<id + offset>,<member weight x weight>` in every family that lists the base id, inserted after `BuildingCount` with the count raised (the growables line insert, `netpack_growables.patch_buildfam`) | `Res\BUILDFAM.IXF` |

| Set | Buildings | Frame tables | Pixel records | Family lines | Families |
|---|---|---|---|---|---|
| `e523f3fb` European, ids + 400000 | 121 | 121 | 4,608 | 145 | 23 (1, 4, 7-17, 19, 20, 22-25, 28-31) |
| `6523f3d5` Asian, ids + 1500000 | 130 | 130 | 4,864 | 154 | 21 (same without 19, 20) |

30 base ids sit in more than one family, so a building gets a line in each of them. Members a set does not re-skin
keep the base art only, exactly as in a stock set city. Industrial families have no set buildings.

Mix ratio: a member of weight w keeps its stock line and gains one line per set at w x weight. With 1 / 1 a building
both sets re-skin grows in each style a third of the time. Base lines are never edited, so other packages' inserts
keep working and the base share cannot be lowered below the set shares without editing stock lines.

**Install** (dev tree, overlay mode): the 20 road packages of the staged release (`packs\` and `ledger.json` from
`stage/src/mods/netmod`), then `growable_test`, then `style_mix`. Overlay against the staged release: added
`BUILDFAM.IXF`, `5432D60E_netpack_set.DAT`, `547B7DF5_netpack_set.DAT`. Changed `OccupantAttribs_Korea.IXF`,
`CSAttrib_Korea.IXF` (1,231 -> 1,483 records each: +1 growable, +251 style), `4E3D0034_netpack.DAT` and the 7
`SC3StringsNetpack.IXF` (growable_test's art and name). `SYS.PAK` and every road file unchanged. Family 11 after
both: 36001 (weight 50), 8 European + 9 Asian lines, then the 12 stock lines, `BuildingCount` 12 -> 30.
`uninstall style_mix` takes the Korea pair back to 1,232 records and removes both set DATs.

**Capacity:** there is no 1,023 cap. netpack rebuilds each container with an index sized to fit
(`ixf_insert.new_container`), the staged release already held 1,231 records, and this run loaded 1,483 with no fault.
For comparison the set DATs that `SetCityScheme` registers in GZResourceD hold 5,808 and 7,124 records. The
"1,024 slots" figure is the size of the index reserved in shipped files, not a reader limit.

## Evidence

Dev workspace `dev/stylemix`, city `Moscow, Russia.sc3` (24,512 occupants as shipped). Windowed, posted keys and
clicks only (0x50 unpause, 0x34 speed 4, minimap clicks, the Load dialog). Churn sped up with `inst\simrun.ini`
`[churn] anarchy_res=5000, anarchy_com=5000`. Autosave every 150 s. Counts from `occupant_layer.py`
(`re/tools/netmod/stylemix_verify_count.py`). "Mixable" = base buildings whose id has style copies. Live style read
from memory with `stylemix_verify_scheme.py` (scheme manager = `*(app + 0x108)`, vtable checked =
SIMINIT+0x2f528, `+0x50` = current building set).

| Save | City style | Occupants | Base (mixable ids) | European | Asian | 36001 |
|---|---|---|---|---|---|---|
| Moscow as shipped | European | 24,512 | 24,512 (0) | 0 | 0 | 0 |
| (1) first autosave, mod on | European | 25,011 | 19,291 (9,499) | **2,887** | **2,833** | 855 |
| (2) save A (next autosave) | European | 25,260 | 18,475 (9,194) | 3,628 | 3,157 | 811 |
| (3) A reloaded with the mod, next autosave | European | 25,170 | 18,336 (9,052) | 3,644 | 3,190 | 811 |
| (4) A with its style set to 0 (copy patched), next autosave B | **0** | 25,193 | 18,470 (9,130) | 3,607 | 3,116 | 811 |
| (6) B loaded WITHOUT the mod, saved while still paused | 0 | 25,193 | 25,193 | 0 | 0 | 811 |
| (6) B loaded without the mod, 150 s later | 0 | 25,290 | 25,290 | 0 | 0 | 898 |

1. **The copies grow.** 2,887 European and 2,833 Asian buildings by the first autosave (88 and 84 distinct ids),
   from 121 / 130 available. European and Asian came out within 2% of each other, as equal weights predict. They are
   not a third each of the mixable buildings yet because Moscow starts with 24,512 base buildings and only new growth
   draws from the mix.
2. **All three styles in one view** (`MAIN\verify\stylemix\owner_shots\`, not committed):
   `s8_set0_three_styles.png`, save A with its style set to 0, live set read back as 0: North American base buildings
   (purple-brick blocks top left and top right, the white palace, the tall tower), European copies (mansard roofs) and
   Asian copies (the blue and brick towers on the left). `legend_3020.png` and `legend_r0.png` show the three art
   variants of the same ids, drawn from the frame tables the game uses, to read the shots against.
   `s5_euro_set_active.png` is the same street with the city's own European style active: every building that is a
   base id draws European, the copies are unchanged. That pair is the clearest picture of what the mix adds.
3. **Save and reload with the mod:** save A reloaded with no fault (`s6_reload_with_mod_euro_set.png`, same
   buildings), and its next autosave still holds 3,644 European and 3,190 Asian copies. The set-0 save B was written
   by the game with style 0 in its scheme record, so the patched style survives a save.
4. **Player picks a style, with the mix installed.** A city's style is its own (finding 1), so this happens when a
   player plays a city saved with a set, or starts a new city with one. Measured both ways in one session:
   `stylemix_B_euro.sc3` (B with style European) launched, live set `0xE523F3FB`, then `sB0.sc3` (B with style 0)
   loaded through the Load dialog, live set `0`. That second load runs the set switch-away path (`FUN_10006b0a`
   unregisters the set DAT from the sprite image manager, `vt+0x30`), and the European copies still drew afterwards
   (`s10_after_switch_euro_to_0.png`), so the unregister does not drop the copies' pixels, which come from our own
   DAT. With a set active every base id it re-skins draws in that set's style too, so a European city with the mix
   shows European and Asian only for those buildings (about two thirds European). Nothing breaks, the mix is just
   uneven.
5. **Load WITHOUT the mod** (package uninstalled, the other 21 kept): no crash, no VEH fault. The copies do not
   become empty lots. On load each copy is replaced by another building of the **same building type** (t18): of
   6,723 copies, 942 became their own base id and 5,781 another member, all 6,723 of the same type, the occupant
   count is unchanged (25,193) and no other lot changed (`stylemix_verify_nomod_diff.py`, save taken while still
   paused, so no sim time passed). `s11_load_without_mod.png` shows the street with North American buildings where
   the copies were. Which branch of `SIMGEOM 0x1001e516` / `0x10002cc2` picks the substitute was not traced.

Every run logs one `0xC0000096 at SC3U.exe+0x84122` VEH entry about 50 ms after start. It is in every dev tree's
log and predates this work.

Which set is which: `e523f3fb` is European, `6523f3d5` Asian. Each set exemplar names itself through prop 0x6D in
group `0x453BBDE0` (`SC3MBEStringsBuildings.IXF`, English-UK): 403065 "Old Charmer", 404008 "La de da Shops" against
1503065 "Kamagaland Cottage", 1504008 "Kwang-Hwa Computer Shops". The legend art agrees (half-timbering and mansards
against glass towers). The `[BuildingSets]` sound field is 2 for `e523f3fb` and 1 for `6523f3d5`.

## Not checked

- Population: it fell from 902,494 to about 795,000 over the European-style runs and stood at 767,903 in save B.
  churn at anarchy 5000 rebuilds lots all the time, which empties them while they rebuild. No control run without
  the mix was made, so whether the mix plays a part is open.
- A new city started with a set picked in the New City dialog (only city loads were run). The same `SetCityScheme`
  runs, so the outcome should match case 4, but that was not watched.
- Switching between the two sets directly (European to Asian) in one session. European to 0 was run.
- The app preference `SimSettings.buildingSetId` (`SC3.cfg` record `0xA352F1B5`, byte 137 of its payload, European
  in MAIN and every dev tree). Setting it to 0 in the tree changed nothing for a loaded city. Its use, probably the
  New City default, was not traced.
- Weights other than 1 / 1, the query dialog ("Copiar ID") on a copy, every zoom level and rotation.
- How the copies' names show in game: the TKB1 text (prop 0x64) holds the base name, the name key points at the
  set's own string.

## Files

- Commit (from `dev/stylemix/wt`): `re/tools/netmod/netpack_stylesets.py`, `re/tools/netmod/netpack.py`,
  `re/tools/netmod/netpack.schema.json`, `re/tools/netmod/stylemix_build.py`,
  `re/tools/netmod/examples/style_mix/manifest.json`, `re/tools/netmod/examples/style_mix/README.md`,
  `re/analysis/BUILDING_PICK.md`, `verify/stylemix/RESULTS.md`, `re/tools/netmod/stylemix_verify_count.py`,
  `re/tools/netmod/stylemix_verify_legend.py`, `re/tools/netmod/stylemix_verify_scheme.py`,
  `re/tools/netmod/stylemix_verify_setscheme.py`, `re/tools/netmod/stylemix_verify_nomod_diff.py`.
  MAIN: `re/sessions/STATUS_stylemix.md`.
- Not committed: `MAIN\verify\stylemix\owner_shots\*.png` (game art), the saves in `dev/stylemix/tree/Cities`.
