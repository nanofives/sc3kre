# netvariant: results (2026-10-13)

PRE: `verify/netvariant/PRE.md` (commit `ea83d76`), addendum 1 committed before the X runs. Analysis:
`re/analysis/NETVARIANT.md`. Build: `sc3netmod.dll` from `child/netvariant`. Arm S1 and the first X1 try ran on the first cut
(`ea83d76`, crossing switch site only, same save/load code); every later arm ran on the 16-site build. The source was
then changed in comments only; the final build's sha256 is `f6e2a686efbb3a1fbf5c3a5595b481fec197355a9195a8ce14744e8eec02771e`.

Tree `Simcity_stock_netvariant` (hard links of Simcity_stock, stock DLLs, Spanish). Mod data `verify/netvariant/mod_blue`
(`newpiece.py build`, id 20029 from 29, manifest `"base": 29`, `Apps\Res\netmod_variants.txt`). `inst_netvariant` =
sc3resize + sc3netmod; `inst_nvstock` = sc3resize only, run with the mod data UNinstalled (`link_tree.py --verify`:
3,488 linked, 0 de-linked = byte-stock data). sc3resize is there for its in-process frame DUMP; it does not touch
networks or saves. City: newpiece arm M's save (Roadless Paradise, 22 tiles of 20029).

**Frames:** every frame below is sc3resize's in-process DUMP of the presented back buffer (`np_drive.py shot`). A desktop
grab was refused by sc3io (window off every monitor after a move to DISPLAY2, which does not exist on this desk now), so
grabs were not used. Live tile reads: `np_drive.py cells` (Frida, read only).

## Crossings

| arm | setup | input | result | prediction |
|---|---|---|---|---|
| X1 first try | mod + sc3netmod, switch site only | Rail, drag across x=102 | rail stops at the road, no crossing, `crossing-switch lookups mapped=0` | not met; led to addendum 1 |
| X1 | mod + sc3netmod (16 sites) | Rail (0x10004101), drag 185,353 -> 265,313 | **(102,155) 29-class tile -> piece 69 state 1**, rail 44 on x=100..106 at y=155 (both sides), the other 10 tiles of x=102 stay **20029** and blue; log `crossing-switch lookups mapped=1, predicate id reads mapped=17` | met |
| P1 | same game | Wires (0x10005001), drag 162,343 -> 242,303 | **(102,152) -> piece 67 state 1**, line 92/14 on x=97..107 at y=152, rest of the road 20029 | met |
| X1 save | same game, Save | | file: 69 at (102,155), 67 at (102,152) (state 1, props 0x3000), the 20 remaining variant tiles stored as 29 + section | met |
| X0 | mod + sc3netmod, `SC3NETMOD_CROSS=0` | as X1 | rail only on x=103..107 (one side), (102,155) stays 20029 | met (opt-out = stock behaviour, as newpiece XM) |
| XS | stock instance, data uninstalled | load X1's save | 69 and 67 kept, the 20 tiles live as 29, no crash | not pre-registered |
| XL | mod + sc3netmod | load X1's save | 69/67 kept, all 20 variants restored (`load: all 20 variant tiles restored`) | not pre-registered |

Frames looked at: `X1_rail.png` + `X1_rail_zoom.png` (rail through the blue road, crossing tile grey, blue on both sides),
`P1_power.png` + `P1_power_zoom.png` (pylons across the road, grey crossing tile), `X0_rail.png`.

**Crossing look (design, owner to confirm):** the crossing tile is the stock 69/67, so the variant colour is lost on that
one tile. Keeping it needs a variant crossing piece (new art) and a matrix row, not done.

### T: traffic (exploratory)

A direct run over a crossing built by the DLL was not done: Roadless Paradise has no traffic, and in Berlin the rail
tool refused the spot tried (red marker, nothing built, `T_04_cmp.png`); no further attempt. Evidence used instead:
newpiece's arm TM (Berlin, every surface straight 29 set to 20029, 120 s of sim, no DLL). Its city already holds 76
crossings 69/67; 29 of them touch a 20029 tile. After the run all 29 carry surface density, and on 8 it rose (TM source
-> TM_after, `surf_live`, grid cell `(N-1-x)*N+y`); several others sat at the 255 cap before and after. Density only rises
when trips are routed through a cell, so trips do route across crossings next to the variant. The crossing the DLL builds
is the same stock piece with the same record fields. This is not a measurement of a DLL-built crossing under traffic.

## Saves

| arm | setup | input | result | prediction |
|---|---|---|---|---|
| S1 | mod + sc3netmod | load M's raw save, Save | 22 tiles 20029 -> 29, x/y/z/state/props unchanged, every other tile identical; section 0x4E56, 280 bytes, 22 entries; log `save: 22 variant tile(s) written as base` | met |
| S2 | stock instance | load S1's save | no crash, 22 tiles live as 29, grey (`S2_01_city.png`), money and date as S1 | met |
| S2 save | stock | Save | surface network identical to S1's; **the 0x4E56 section is gone**; 3 other sections differ (sim state) | recorded (no prediction) |
| S3 | mod + sc3netmod | load S1's save | `load: all 22 variant tiles restored`; the 22 tiles live as 20029 with the same states as M; blue (`S3_01_city.png`) | met |
| S3 save | | Save | network sections 0, 1 and 0x4E56 byte-identical to S1's | met |
| S4a | stock instance | load S3's save | no crash, 22 tiles live as 29 | met |
| S4b | mod + sc3netmod | load S3's save | all 22 restored as 20029 | met (second round trip) |
| S5 | mod + sc3netmod | load S2's save (re-saved by stock) | `load: no variant section`; the 22 tiles stay 29 | recorded: stock re-save loses the variants, keeps the road |
| S5b | mod + sc3netmod | load S4a's save (also re-saved by stock) | same as S5 (`S5b_01_city.png`) | same |
| SB | mod + sc3netmod, `SC3NETMOD_SAVEBASE=0` | load M, Save | no section, surface section byte-identical to M (raw 20029 kept) | met |
| R | | | old raw save opened with the mod and saved once = S1 | met (repair by one save) |
| FB | offline | `netvariant.py fallback` on M's raw save | network sections 0, 1, 0x4E56 byte-identical to S1's in-game save | met |
| FBS | stock instance | load FB | no crash, the 22 tiles live as 29 | met |

Old raw save without the mod at all: newpiece arm R (tiles dropped on load and on the next save) stands. The repair is
either one save with the mod (S1) or `netvariant.py fallback` offline (FB, FBS).

## Not covered
Owner's dev install and the release layout (DLL in Apps); 1024 cities; other bases (highway, rail, power, bridges);
removing a crossing again; a traffic run over a DLL-built crossing.
