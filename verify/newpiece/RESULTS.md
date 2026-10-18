# newpiece: RESULTS (2026-10-12)

**Verdict: the hello world works.** SC3U accepts a network piece id that does not exist in stock (20029), placed by the
road tiler, drawn with its own art at all 5 zooms and 4 rotations, identified by "Copiar ID", saved, reloaded, and
routed by the traffic sim. It needs no code patch and no change to any shipped container except the per-language
TrBlkAtt (optional, see T) and the two TilingRules text files.
What the new id loses is the hardcoded whitelists: rail and power lines will not cross it (measured), plus the static
list in `re/analysis/NEW_PIECE.md` section 4.

Pre-registration: `PRE.md`, committed `17ce472` before the first run, addendum `25d1db9` before arm T.
Tree: `Simcity_stock_newpiece` (hard links of `Simcity_stock`, stock DLLs, Spanish), instance `inst_newpiece` with
`mods_launch -multi` + `sc3resize.dll` from `child/newpiece`. Mod files: `verify/newpiece/mod_blue/manifest.json`.
Every arm ran in my own pid only; all stopped. Saves stay in the instance folder (game content, not committed).

## Capture note (affects every frame below)

On this machine today every desktop grab of an SC3 window came back white, including the owner's release layout
(`Simcity_stock\Apps\mods_launch.exe`), on the 125 % monitors and the 100 % one, maximized or not, renamed exe or not,
DPI-aware or not. The game kept presenting (sc3perf CSV, sc3resize log). So every frame here is sc3resize's
in-process DUMP of the presented frame (`frame_with_hud`, captured right after a full present, `np_drive.py shot`).
That is the game's own back buffer, so it shows what the game drew, not what reached the glass. Cause of the white
screen not established. Instance ini: `sc3resize.ini [display] dpiaware=0` from the third launch on; window moved to
DISPLAY2 (100 %) so input and frame coordinates coincide.

## Arms

| arm | tree | city | input | result | prediction |
|---|---|---|---|---|---|
| C | mod off | Roadless Paradise copy | pan, Roads, 2 drags, Save | straights = 29, state 0 (x axis) / 1 (y axis), props 0x3000, ends 11225 | met |
| M | mod on | same | same input | 22 straights = **20029**, same state as C per tile, props 0x3000; 4 straights next to the junction stay 29 (contextual rules); ends, curves, slope piece 32 unchanged; same cost (§24,493) | met |
| M (live) | | | Frida, piece occupants | class `SIMNTWRK+0x2B5DC` (road, kind 1), attrib `{0xE223741F,0xA317745F,0x4E3D}` | met |
| M (query) | | | ? tool on (102,157), Copiar ID | `network.piece_id: 20029`, `network.sets: ROAD`, `object.key: 0xE223741F 0xA317745F 0x00004E3D`, `network.trblkatt_key: ... 0x004E3D01` (`M_copiar_id.txt`) | met |
| L | mod on | M's save | load only | tiles read back 20029 live, drawn blue | met |
| L | | | 4 rotations, 5 zooms | blue in every frame, road direction correct in every rotation | met |
| XM | mod on | M's save | Rail tool, drag across the blue road at (102,156) | rail laid on one side only (x 103..106), road tile unchanged, no crossing | met (static `0x100167d4`) |
| XC | mod off | C's save | identical rail drag | crossing: (102,156) 29 -> **69**, rail on both sides | met |
| PM | mod on | M's save | Wires tool, same drag | power line on one side only, no crossing | not pre-registered, same path |
| PC | mod off | C's save | identical | (102,156) 29 -> **67**, line on both sides | |
| R | mod off | M's save | load, save | no crash; the 22 tiles with no exemplar are invisible, absent from the live occupant grid, and **dropped from the next save** (diff: -22 tiles) | exploratory |
| TC / TM | mod on | Berlin copy; TM has all 7,419 surface piece-29 tiles set to 20029 by `NetworkEditor` | P, speed 3, 120 s, P, Save | date 2/9/2067 -> 8/16/2067 in both (gate passed); TM draws its straights blue | gate met |
| TN | mod built `--no-trblk` | TM's city | same | no crash, same density as TM | ablation |

### T: traffic on the new piece (one run per arm)

Grid index calibrated first: SimTransit cell (x, y) of the network layer is byte `(N-1-x)*N + y` (98.4 % of Berlin's
surf_live mass on road cells with it, 31-35 % with the five other orders).

| | piece on S | surf_live on S | cells on S that rose above baseline | zero -> nonzero on S | surf_live all cells |
|---|---|---|---|---|---|
| baseline (stock file) | 29 | 320,410 | | | 1,000,139 |
| TC | 29 | 370,701 | 3,448 | 451 | 1,120,117 |
| TM | 20029 | 359,631 | 3,166 | 388 | 1,076,621 |
| TN (no TrBlkAtt records) | 20029 | 359,199 | 3,154 | 357 | 1,096,680 |

Density only falls by the monthly decrement, so a cell can rise only if trips are routed through it: 3,166 switched
cells rose and 388 went from 0 to traffic in TM. **Traffic routes over 20029.** TM is 3.0 % under TC on S; with one run
per arm the run-to-run spread is not measured, so that gap is not a finding. TrBlkAtt records for the new id are not
needed for routing or for stability over six months; what they feed (piece vtable +0x54, `0x1000d225`) is not traced.

This is also the **first game load of a network layer edited by `network_layer.NetworkEditor`**: 7,419 set_piece edits,
loaded, simulated, saved, read back (fence in `TILINGRULES_MODDING.md` "never loaded by the game" is closed for
set_piece).

## Step A, in game
Arm C is the rotation diff the brief asked for: the same road drawn along x saves state 0, along y state 1, in save
word0 bits 30-31, with word1's high half 0x3000 on every tile; the live piece occupant carries the same bits
(`+0x10 >> 30`). Static proof and the tool fix: `5197c46`.

## Frames looked at
`frames_stock_vs_new.png` (offline render, stock vs tinted), `C_01_city`, `C_03_road1`, `C_04_road2`, `M_04_roads`
(blue straights), `M_05_query` (Indagar on a blue tile), `L_01_city` (after reload), `L_rot_sheet` (4 rotations),
`L_zoom_sheet` + `L_zoomin1/2` (5 zooms), `XM_rail` (rail stops at the road), `PM_power`, `R_01_city` (mod removed: the
new tiles are gone, stock pieces stay), `T_sheet` (TC/TM before and after, dates), `TN_after120s`.

## Not covered
Highway, rail, pipes, subway, bridges, slopes, ComplexRules contexts, other topologies, a 1024 city, an English
install, the owner's dev install (MAIN\Apps). Vehicle sprites on the new piece were not checked frame by frame.
