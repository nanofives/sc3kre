# netbridge pre-registration (2026-10-13)

Task: netmod framework step 4a. Highway / rail / power bases for variants, bridges as moddable data, variant crossing
art. Branch `child/netbridge` from `round/1012` (8b9ea76). Test tree `Simcity_stock_netbridge` (hard links to
`Simcity_stock`, `link_tree.py`), instance `Simcity_stock_netbridge\re\harness\inst_netbridge`. Stock DLLs, overlay
install, my build of `sc3netmod.dll`, `sc3resize.dll` only for the in-process frame DUMP.

Everything below was written before the code it tests. Each arm names what would count as a pass and as a fail.

## 0. Static facts this plan rests on (read before writing it)

| fact | where |
|---|---|
| Drag/build is manager vt+0xf0 = `FUN_10014a23` (manager vtable `0x1002c7bc`, read from the PE). Bridge path when netType is 1/2/3 (vt+0x144 = `FUN_1000122a`) or 4 (vt+0x148 = `FUN_10002693`), the network's Bridges vector is non-empty and the path holds more than 3 cells | `[CONFIRMED @0x10014a23]` |
| Bridges file: first token discarded, every other token pushed (`FUN_100196ce`, delimiters `" ,\n\t"` at `0x10031f0c`) | `[CONFIRMED @0x100196ce]` |
| Road/rail/power builder takes the FIRST record whose axis matches and `minLen <= L`; HWAY builder takes the first whose axis key (0..3) matches, minLen not read | `[CONFIRMED @0x1000122a, 0x10002693]` |
| A, B, D, E lists copy into 5-slot stack buffers, C into 20, no bounds check (both builders) | `[CONFIRMED @0x1000122a, 0x10002693]` |
| Every placed bridge tile goes through `FUN_10008919` -> manager vt+0x48(`0xc14f8955`, id, state): the piece class comes from Set membership, so a new id that is in the base's Sets gets the base's class | `[CONFIRMED @0x10008919]` |
| Removal: vt+0x100 `FUN_1001d761` -> vt+0x104 `FUN_1001da5f` finds the Collapse.txt group holding the removed id (group size <= 29, `0x1d < n` aborts) and removes every neighbour within 8 cells whose id (`FUN_1001a93d`, 5 sites) is in that group | `[CONFIRMED @0x1001da5f]` |
| Crossing tile: `FUN_100167d4` reads the matrix value then calls `FUN_1002207c(value, &id, &state)` at `0x10016953`; the existing occupant is `[ebp-8]` | `[CONFIRMED @0x100167d4, disassembly]` |
| `FUN_10009bc7` (cell -> piece id) is called only from `FUN_10009d20` (19 sites), `FUN_1000aaba` only from `FUN_1000abde` (10 sites): the highway diagonal / onramp code | PE call scan |
| The tiler reports a neighbour's (id, state) through the Convert tables (`FUN_1001a85a`, last matching row wins) | `TILER_SIM.md` 6, 7 |

## 1. Offline arm S1: Convert inheritance (done before any code, numbers are the pre-registered baseline)

Simulator (`netrules preview`, validated in `TILER_SIM.md`). Edit: every stage-rule RESULT that places the base, at any
dir, retargeted to the variant; variant added to the Set. Two variants: with and without Convert rows
`(variant, s) -> (base, s)` for s = 0..3 in both Convert files. "pure swap" = a tile that changes exactly base/s ->
variant/s; "other" = any other tile that changes.

| net, base -> variant | city | without Convert: diff / other | with Convert: diff / other |
|---|---|---|---|
| HWAY 73 -> 20073 | Berlin | 230 / 36 | 194 / 0 |
| HWAY 73 -> 20073 | London | 192 / 18 | 174 / 0 |
| HWAY 73 -> 20073 | Madrid | 312 / 33 | 281 / 0 |
| HWAY 73 -> 20073 | Seoul | 342 / 34 | 308 / 0 |
| HWAY 73 -> 20073 | Sacramento | 288 / 34 | 254 / 0 |
| RAIL 44 -> 20044 | Berlin / Madrid / Seoul | 349/0, 353/4, 470/0 | 349/0, 350/0, 470/0 |
| POWR 14 -> 20014 | Berlin / Madrid / Seoul | 27/21, 3/1, 2/0 | 15/0, 2/0, 2/0 |
| ROAD 29 -> 20029 | Berlin / Madrid / Seoul | 8216/818, 9759/561, 5839/288 | 7400/0, 9198/0, 5551/0 |

Consequence for the design: a variant inherits its base in rule CONDITIONS through Convert rows (data, no DLL).

## 2. Offline arm S2: netpack checks (selftest)

Pass: `netpack.py selftest` passes old U1..U7 unchanged, plus new checks: a `bridges` insert round-trips (stock file
re-emitted byte for byte when no edit), list-length limits refused (A/B/D/E > 5, C > 20), an id in a record that is
in no Set of that network refused, `crossings` refused when `over` is not a variant or `piece` is not a variant of
the matrix piece, inheritance rows present in the merged files. Fail: any old check changes.

## 3. In-game arms (stock DLLs, my tree, overlay install, `sc3netmod.dll` from this branch)

Placement without the mouse: a Frida hook captures manager `this` and the real arguments of vt+0xf0 from one
pixel drag (arm D0), then `nb_drive.py` calls vt+0xf0 on the game thread with a cell list. If D0 shows arguments I
cannot reproduce, I fall back to pixel drags and say so.

| arm | setup | action | pass | fail |
|---|---|---|---|---|
| D0 | stock, no pack | one road pixel drag, hook logs vt+0xf0 args | args logged, road built | no call seen |
| H1 | pack `example_hway_variant` (20073, base 73, recolour, all 73 results retargeted, Convert rows) | load a city with highways, retile message `0x637c0dab` mask 3 over a highway rectangle | live cells in the rect: every tile that `netrules preview --rect` predicts changes 73/s -> 20073/s, no other tile changes; the frame shows the recoloured highway | any non-predicted change, or 73 left where the sim says 20073 |
| H2 | H1 game | road drag across the 20073 highway (vt+0xf0, netType 1) | crossing tile = stock 11258 or 15098 (matrix), the same tile the same drag gives in the control arm H2c (no pack) | no crossing, or a different piece than control |
| H3 | H1 game | rail drag across 20073 | crossing 16006 / 16007 as in control | as H2 |
| H4 | H1 game | save; load the save in a game WITHOUT the DLL (stock) | the stock game loads 73 on those tiles (tile count of the highway unchanged); with the DLL the 20073 come back on the same cells | tiles dropped, or ids not restored |
| H5 | H1 game | traffic: 2 game months with the highway connected | `sim_status`/Copiar ID shows traffic on a 20073 tile non-zero, as on 73 in control | zero on variant, non-zero in control |
| B1 | pack `example_bridge_style` (variants of 87, 88, 11265, 11271, 18050, 18051, recolour, two ROAD records inserted before the stock minLen 1 records) | road drag across water of length < 6 | bridge built of the pack's ids (live cells), frame shows the new colour | stock 87/88 used, or no bridge |
| B1c | stock (no pack) | same drag | stock plain bridge 87/88/11265/11271 + ramps 18050/18051 | (control) |
| B2 | B1 game | bridge of length >= 10 | stock style (minLen 10 record, 81-83/88/11268-11275), since the pack's records only win below the next stock minLen | pack ids used |
| B3 | B1 game | bulldoze one middle bridge tile | the whole bridge goes, as in control B3c (collapse group via the DLL's base mapping) | other bridge tiles stay while control removes them |
| B4 | B1 game | save, load stock | stock plain bridge on the same cells | tiles dropped |
| X1 | packs `example_blue_road` + `example_blue_crossing` (20069 = recolour of 69, `crossings: over 20029, crossing 69 -> 20069`) | rail drag across the blue road | crossing tile = 20069 (live), frame shows the blue crossing; same drag with `SC3NETMOD_XCROSS=0` gives 69 | 69 with the option on |
| X2 | X1 game | save, load stock | 69 on that cell | tile dropped |

Visual checks: in-process DUMP frames (sc3resize). If the display is asleep the frame checks are recorded as pending
and only the live cell reads count.

Not attempted (scope): HWAY bridge styles in game (the format and checks cover them; the HWAY builder needs both
lane records, validated offline only), ramps / onramps / slopes (sibling `netramp`), 1024 cities.
