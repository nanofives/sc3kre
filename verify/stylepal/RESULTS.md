# stylepal results (round 2026-11-23d): why style copies read as another neighbourhood, and three recolour options

Evidence and mock-ups only. Nothing built, nothing installed outside `dev\stylepal\tree`, and the tree's art is back to
the original (byte compare against `dev\stylepal\orig`). The owner picks an option before anything is built.
All pictures hold EA art: local only (`verify\` is gitignored). Game runs: windowed, posted input and Frida game calls
only, the real mouse and keyboard never used, only PIDs this session started were stopped, harness claimed and released.

## Verdict

1. **The dark blob is mostly four yard lots, not the houses.** 3032, 3034, 3041 and 3042 are 1x1 class 3300
   (residential light, mid wealth) filler lots. North American art: a bright lawn with a vegetable patch, a pool
   yard, a play yard with a shed, a fenced lawn. European art: dark allotment gardens and a dirt yard. The Asian set
   uses the same pixels as the European one for all four (16 of 16 frames equal each). In the Sacramento after-save
   they are 3,355 of 7,131 European copies, and 450 of the 667 copies within 30 cells of the owner's camera
   (`owner_shots/07`).
2. **What differs, in order of weight** (zoom 3, lot diamond, CIELAB):
   - Lawn lightness and saturation. Same ids, North American against European: yard lots L 52-61 against 40-44,
     a* -26..-29 against -15..-19 (duller, olive). Class means for low-density residential: L 53 / 51 / 54 against
     40 / 40 / 45 (low / mid / high wealth).
   - Garden-plot share: soil and olive ground (brown class) 0.28-0.52 of the yard lots against 0.01-0.26. Class 3300:
     0.36 against 0.10.
   - Pools: blue 0.16 of class 3300 North American lots against 0.01 European. Recolouring cannot add them.
   - Building palette: European roofs are red-brown (building pixels a* +9..+11, b* +16..+17 for 3100 / 3300 against
     -3..-6 / +12..+14). This is the style itself, and the owner's complaint is the ground.
   - The reverse holds in a European city (Moscow): the North American copies' bright lawns stand out among the
     host's dark lots and white flower beds (`owner_shots/03`, left).
3. **In the owner's scene** (pixels where new buildings grew, same camera): lawn L 55 -> 43, a* -30 -> -17, brown
   share 0.15 -> 0.33, pools 0.09 -> 0.03.
4. **Recommendation: option c for European and Asian copies, a for North American copies, buildings untouched.**
   c puts the scene's lawn share back to the host's 0.48 and the yard lots stop reading as allotments. b's building
   tint is hard to see at 30 % and costs part of the style. Tuning worth one more check after the pick: match each copy
   to its own base building's lawn instead of the class mean (the yard lots' North American lawns are L 57-61, the
   class mean is 51, so c lands at lawn L 50 against the scene's 55).

## The options, in game (`owner_shots/`)

| option | rule | scene: lawn L / a* | lawn share | brown share |
|---|---|---|---|---|
| host (before the pick) | | 55 / -30 | 0.48 | 0.15 |
| now | stock copy art | 43 / -17 | 0.39 | 0.33 |
| a | lot ground only: lawn shifted by host lawn mean - copy lawn mean (per class, Lab, texture kept), soil lifted by the same L | 49 / -23 | 0.39 | 0.32 |
| b | a + every other opaque pixel shifted 30 % toward the host building mean | 53 / -23 | 0.44 | 0.26 |
| c | a + soil turned into lawn with strength (copy soil share - host soil share) / copy soil share per class: the class's own wealth look | 50 / -23 | 0.48 | 0.23 |

- `01_sacramento_options_detail.jpg`: the owner's detail crop, before / now / a / b / c. `02_..._wide.jpg`: the full
  view. Same cell (95, 65), zoom 3, 1430x900. Phase correlation against the owner's frame: offset (0, 0) for all five.
- `03_moscow_na_copies_options.jpg`: Moscow (European set) after picking North American with Mix off
  (`04_moscow_pick_north_american_mix_off.png`): 10,595 North American copies grew in 5 min at speed 4 with churn.
  Now / a / b at cell (52, 222). c = a in this direction (the North American lots have less soil than the European
  host, so there is nothing to turn into lawn).
- `05` / `06`: per-building previews at 2.5x (host art, copy art, a, b, c) for the yard lots and four houses.
- c by wealth, soil-to-lawn strength from the data: 3100 low 0.40, 3300 mid 0.71, 3500 high 0.25, 3900 0.58,
  4100 0.63, 4700 0.56, 4500 / 6100 / 6300 0 (the copy has no more soil than the host). North American low-wealth
  lots keep the most soil (0.18), so low wealth stays plainer. High wealth (3500) keeps more than mid because North
  American 3500 lots carry 0.11 soil and the European ones only 0.15.

Known artefacts: soil = hue 62..95, chroma > 14, L < 62 inside the lot diamond (soil measured at hue 65-93, roofs
37-55, light paths L > 70). Roof pixels with a soil hue that dip into the diamond can still shift a little. Stone
wall bases at chroma 10-14 were excluded after the first preview tinted them green.

## How the copies' art is stored, and what each option costs

- **True colour, no palette.** Every frame is a format-1 RGB565 sprite with colour key 0xF81F (BUILDING_ART.md 1).
  The 255-colour limit per frame is an authoring trace, not a runtime palette. Recolouring = rewriting pixel records.
  No CSAttrib frame tables change for European and Asian copies.
- **European copies**: their pixels are only in `5432D60E_netpack_set.DAT` (11.1 MB, 2,400 records, written by
  netpack `style_sets`), drawn by the copies only. 2,272 records are RCI growables (the rest civic copies). Recolour
  time 35 s on this PC. Size unchanged when the container is rebuilt (the mock-up appended, 21.3 MB).
- **Asian copies**: `547B7DF5_netpack_set.DAT` (20.4 MB), same treatment.
- **North American copies** (+2600000): they reuse the stock frame tables and stock pixel records. A recolour needs
  their own copies: a frame table per copy (156 copies) in `CSAttrib_Korea.IXF`, about 10 MB of pixel records in a new DAT, and
  prop 0x67 of each copy pointed at its table. 443 of the 3,242 stock records are shared with ids no set re-skins, which is why
  the mock-up left them alone. This is a `netpack_stylesets.py` change (style_mix 1.2.x).
- **One art set per host?** The European and Asian hosts are close to each other (class 3300 lawn L 40 against 43,
  3100 40 against 48), both far from North American (51-54). A European copy recoloured for a North American city
  would be too bright in an Asian city. Two ways:
  1. Data only, one variant: European and Asian copies recoloured for a North American host (set 0, the New City
     default), North American copies for a European host. Mismatch left: a European copy in an Asian city, an Asian
     copy in a European city, a North American copy in an Asian city.
  2. Per host: the default copy pixels = the North American-host variant, and each set folder
     `Res\Sprites\BuildingSets\<set>\` gets an extra DAT with that host's variant of the other styles' copies.
     SetCityScheme registers every `*.DAT` in the city's set folder at the front (FUN_1000641b), and set 0 loads
     nothing, so the city's own set would pick the variant. [UNCERTAIN: not run. Whether the sprite image manager
     prefers the set folder's record for a pixel key the netpack DAT also holds, and whether the netmod overlay serves
     a file inside that folder to the game's directory scan.] Size: about +11 / +20 / +10 MB per extra host variant.
- **Install time**: the recolour runs once at package build, players get finished DATs. Re-installing style_mix
  re-merges all 25 packages on a dev PC (about 45 min, memory project-stylepick).
- **Publish policy**: recoloured EA pixels are the same kind of data the style DATs already ship under the owner's
  exception (memory project-sc3kre-publish-policy). No change in kind.

## Measurement (step 1)

Tools in `work/` (local): `extract.py` (zoom 0-3 frames of all 235 family members in the three styles: 235 North
American, 119 European, 128 Asian; BUILDING_PICK.md counts 121 European overrides, 2 not square or without a
16-frame table), `measure.py`, `class_table.md` (all 56 class x style cells), `measure.json` (per building).

Masks from the lot geometry, no colour guess (BUILDING_ART.md 2-3: the (L, T) pixel is the lot's left vertex,
width n x W): ground-plane u = x/W - 2(y-T)/W, v = x/W + 2(y-T)/W, lot = 0 <= u, v <= n. "lot" = opaque inside the
diamond, "front" = the band nearest the viewer (u < 0.25 n or v > 0.75 n), "building" = opaque above the diamond
(walls rise up the screen from the footprint, so these are never ground). Checked on 1x1 / 2x2 / 3x3 lots in all
three styles (`work/mask_check.png`). Pixel classes in Lab: lawn = hue 95-200 and chroma > 12, soil/brown = hue
35-95 and chroma > 10, grey = chroma <= 10, blue = hue 200-300, red = rest.

Land value bands (SC3ZoneLayer.ini `[ZoneDeveloperDescriptions]`, rows 1 and 3): residential density 1 low 3100 = LV 1-75,
mid 3300 = 76-170 (row 3), high 3500 = 151-255 (row 1 only), density 2 3700 / 3900 / 4100, density 3 4300 / 4500 /
4700. Commercial 5100 LV 1-89 / 5500 90-253 (light), 5700 / 6100 (medium), 6300 / 6700 (dense).

Excerpt (lot diamond, zoom 3 slots 0-3, n = buildings):

| class | style | n | lawn L / a* / b* | lawn | soil | grey | blue | building L / a* / b* |
|---|---|---|---|---|---|---|---|---|
| 3100 R light, low | NA | 12 | 53 / -21 / 26 | 0.46 | 0.18 | 0.27 | 0.05 | 57 / -3 / 14 |
| 3100 R light, low | EU | 8 | 40 / -14 / 25 | 0.19 | 0.29 | 0.44 | 0.03 | 48 / 9 / 16 |
| 3100 R light, low | AS | 9 | 48 / -12 / 22 | 0.19 | 0.18 | 0.51 | 0.10 | 53 / -2 / 5 |
| 3300 R light, mid | NA | 12 | 51 / -25 / 29 | 0.46 | 0.10 | 0.19 | 0.16 | 56 / -6 / 12 |
| 3300 R light, mid | EU | 12 | 40 / -16 / 28 | 0.30 | 0.36 | 0.25 | 0.01 | 44 / 11 / 17 |
| 3300 R light, mid | AS | 12 | 43 / -17 / 26 | 0.25 | 0.21 | 0.35 | 0.10 | 50 / 0 / -2 |
| 3500 R light, high | NA | 17 | 54 / -25 / 27 | 0.51 | 0.11 | 0.22 | 0.10 | 57 / -8 / 13 |
| 3500 R light, high | EU | 15 | 45 / -22 / 26 | 0.42 | 0.15 | 0.35 | 0.04 | 51 / -12 / 16 |
| 3500 R light, high | AS | 16 | 45 / -21 / 26 | 0.33 | 0.12 | 0.37 | 0.14 | 57 / -5 / 4 |

Commercial and industrial lots are mostly paving in every style (grey 0.55-0.84), so the ground gap is a residential
matter. Full table: `work/class_table.md`.

## How (commands)

| step | command |
|---|---|
| frames | `py -3.12 work/extract.py` -> `work/frames.pkl` |
| measure | `py -3.12 work/measure.py` -> `work/measure.json` |
| recolour (dev tree only, originals kept in `dev\stylepal\orig`) | `py -3.12 work/recolor.py eu|na none|a|b|c` |
| scene frames | `test-slot bash -c 'py -3.12 work/run_scene.py eu sp_after6.sc3 sac 95,65 -- a b c none'` (the owner's after-save copied into the tree as `sp_after6.sc3`, churn anarchy 0) |
| Moscow growth | `work/moscow_grow.py 6`: City Properties posted as the menu message `{0x025F0A91, 0x1000900A}` through the framework message service (the CLOSEX path, `lab.py menucmd`), clicks posted at 800x600. Log: `stylepick: ... skin E523F3FB -> E523F3FB, style North American`, 631 members left out |
| sheets | `work/sheet_scene.py` |

## Found on the way

- The runner hung once: the game inherits a `capture_output` pipe of the launching subprocess, so `subprocess.run`
  waits for the game to exit. Launch with null handles.
- `lab.py dump` works while City Properties is open (the dialog frames were dumped modal).

## Owner pick (2026-11-24)
EU/AS copies: c. NA copies: a. One variant (North American host). Per-id lawn match: yes.


## Build (round 2026-11-24e, style_mix 1.3.0): what the owner picked, built into the package

Owner picks (2026-11-24): European and Asian copies get c, North American copies get a, one art variant, per-building
tuning. Built in the package build, so players get finished DATs. Nothing in git yet, the files are listed in
`re/sessions/STATUS_stylepal.md`.

### What was built (worktree `dev\stylepal\wt`, branch child/stylepal from main 3b561f75)

| file | change |
|---|---|
| `re/tools/netmod/netpack_lotcolour.py` (new) | per-building lot statistics and the recolour, from `work/recolor.py`. Elementwise numpy only (no matrix products, so no CPU-dependent BLAS sums), fixed record order, QFS quick compression |
| `re/tools/netmod/netpack_stylesets.py` | manifest key `"lot_colour"` (`lawn_soil` = option c, `lawn` = option a). European / Asian entries: each grown copy's pixel records recoloured toward the North American art of the same id. North American entry: each copy gets its own frame table (group 0x2627D60F, instance = copy id) and its own pixels (`Res\Sprites²7D60E_netpack_set.DAT`), prop 0x67 pointed at the table. Stock tables and pixels are never written. Civic copies are not recoloured. The build refuses if a stock sprite container already uses either group |
| `re/tools/netmod/netpack.py` | report line per entry: buildings, records, already matching, skipped |
| `re/tools/netmod/netpack.schema.json` | `lot_colour` on `style_set` |
| `re/tools/netmod/examples/style_mix/manifest.json`, `README.md` | 1.3.0, `lot_colour` on all three entries, a README section for players |
| `re/tools/qfs.py` | back-reference copy by slices instead of byte by byte. Same output: 1,620 records of three stock DATs decoded byte-identical against main's qfs.py |

Per building, not per class: host and copy means come from that building's zoom 3 frames (table entries 12-15) inside
the lot diamond. If the host or the copy has fewer than 100 lawn pixels, the lawn is not shifted. Soil-to-lawn strength:
s = (copy soil share - host soil share) / copy soil share, clamped to 0..1. North American copies are tuned toward the
other sets' art of the same id, with the European and Asian pixels pooled.

### Numbers

- Build report: European 113 buildings / 2,176 records recoloured (8 already matched), Asian 118 / 2,064 (12), North
  American 133 / 2,880 (8), 0 skipped (all square lots with full 16-frame tables).
- Per building, zoom 3 lot lawn L (`work/check_build.py`, `work/check_build.json`): 3032 European 41.3 -> 59.4 (host
  59.8), 3034 36.3 -> 53.8 (51.6), 3041 40.0 -> 60.7 (56.2), 3042 44.6 -> 57.1 (56.5). Mean over all copies: European
  48.0 -> 51.6 (host 51.7), Asian 51.6 -> 52.5 (52.4), North American 52.3 -> 48.0 (host 48.9).
- Scene, owner's camera (`work/scene_measure.py`, changed = RGB differs by more than 16 between the owner's before frame
  and the stock-art frame, 0.297 of the picture; all rows on the same pixels, `work/scene_numbers_build.txt`):

| | lawn L / a* | lawn share | brown share |
|---|---|---|---|
| host (before the pick) | 55.5 / -31.2 | 0.47 | 0.15 |
| now (stock copy art) | 42.5 / -18.6 | 0.39 | 0.35 |
| mock-up a | 49.0 / -24.8 | 0.40 | 0.34 |
| mock-up c (class means) | 49.9 / -24.2 | 0.49 | 0.25 |
| **built 1.3.0** | **53.6 / -24.9** | **0.46** | **0.28** |

  Per-building tuning closes most of the lawn lightness gap that mock-up c left (49.9 -> 53.6 against the host's 55.5).
  Its share of lot soil is a little higher than c's (0.28 against 0.25), because each building now keeps the plots its
  own North American version has. Pixels outside the copies: 1.9 % differ from the owner's frame (traffic).
  These scene numbers use a different mask from the first round's table (0.297 against 0.402 changed share), so
  the mock-up rows were measured again here with this mask.
- Moscow, North American copies (cell (52, 222), pixels mock-up a changed, 0.192 of the picture,
  `work/moscow_numbers_build.txt`): copies' lawn L 52.4 (stock art) -> 43.0 (mock-up a) -> 41.3 (built). The built
  frame differs from the stock-art frame on 0.877 of the copy pixels and 0.070 of the rest (traffic, animation).

### In game (`dev\stylepal	ree`, windowed, posted input, test slot, harness claimed)

- `owner_shots/11_sacramento_built_detail.jpg`, `12_..._wide.jpg`: before / now / mock-up c / built, owner's camera.
- `owner_shots/13_moscow_built.jpg`: Moscow now / mock-up a / built.
- `owner_shots/10_build_per_building.png`: zoom 3 frame 0, host / copy art / built copy, yard lots and houses.
- Save and reload: the Sacramento after-save ran 150 s with 1.3.0, alive, autosave `sp_after6 (auto 5 min).sc3` written,
  reloaded as `sp_reload.sc3`: the same look (`runs/sp/sp_sac_reload_95_65_z3.png`).
- Package removed: `netpack.py uninstall style_mix`, then the owner's after-save (7,131 European copies) loaded,
  unpaused and ran 60 s: alive, no fault in the log except the game's own SC3U.exe+0x84122 start probe.
  No European art shows at the owner's camera (`runs/sp/sp_sac_removed_95_65_z3.png`, `fd/rm_3_late.png`).

### Size and time

| | 1.2.0 | 1.3.0 |
|---|---|---|
| style_mix files (DATs + CSAttrib_Korea) | 31.7 MB (11.12 + 20.42 + 0.14) | 45.5 MB (11.16 + 20.45 + 13.67 new North American DAT + 0.21) |
| `netpack.py build style_mix` alone | 1.9 s | 2 min 14 s (6 min 25 s before the decode speed-ups, same bytes) |
| install into a tree with 24 other packages | 12 min 16 s for uninstall + install (verify/mods_release_1121, 2026-11-21) | install 823 s, uninstall 1,172 s, both measured today with the building suite running beside them part of the time |

The extra install time is the recolour (about 2 min 12 s on this PC). Every install or uninstall of any package re-merges all
packages, so each one now pays that 2 min.

### Checks

- Building suite, normal mode (41 steps, covers qfs.py through bldimport): 41 of 41 passed, wall 2,503 s
  (`suite/run.log`).
- `netpack.py validate examples/style_mix`: passes, report above.
- `netpack.py selftest`: see STATUS (result added when it finishes).

### Stage source for the next release

`stage\src` still holds style_mix 1.2.0. Before the next release, as in verify/mods_release_1121: back up
`stage\src\mods
etmod`, then from main after the merge
`py -3.12 re/tools/netmod/netpack.py uninstall style_mix --tree stage/src --allow-tree` and
`py -3.12 re/tools/netmod/netpack.py install re/tools/netmod/examples/style_mix --tree stage/src --allow-tree`
(about 15-35 min on LIVING-PC). The new `2627D60E_netpack_set.DAT` (13.7 MB) then ships in the overlay with the other
two set DATs. Same publish class as those (EA pixels, recoloured), under the owner's existing exception.
