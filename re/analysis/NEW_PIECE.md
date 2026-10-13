# Adding a NEW network piece id (netmod stage 3, 2026-10-12)

**Status: game-proven on stock DLLs** (`verify/newpiece/RESULTS.md`, PRE `17ce472`). Road piece 29 (straight) cloned
as id **20029** with blue art: placed by the road tiler, drawn at 5 zooms x 4 rotations, "Copiar ID" reports it, it
survives save and reload, and the traffic sim routes over it. No code patch.

Tool: `re/tools/netmod/newpiece.py` (build / install / uninstall / check). Helpers: `ixf_insert.py` (write and append
IXF records), `link_tree.py` (hard-linked test tree), `np_drive.py` / `np_arm.py` (drive one -multi instance, in-process
frame dumps). Catalog of existing pieces: sibling `netcat` (`re/tools/netmod/netcat.py`, `re/analysis/NETMOD_CATALOG.md`).

## 1. The chain a piece id goes through

| hop | key | file | code |
|---|---|---|---|
| 1. membership -> piece class | id in `TilingRules\<NET>_GRND_Set.txt` | text, loaded at startup | lists `0x10032348..60` filled by `FUN_1001746e`; class by `FUN_1001a5f2` (ROAD only -> kind 1; ROAD+RAIL 5; ROAD+HWAY 6, or 0xe for 15130..15141) |
| 2. tiler emits it | RESULT `5,255,<id*256+state>` in `<NET>_GRND_SimpleRules.txt` (or Complex/final) | text | `FUN_1001547b` stages `[CONFIRMED @0x1001547b:565/581/597]` |
| 3. exemplar | `{0xE223741F, 0xA317745F, id}` | `Res\Occupant\OccupantAttribs*.IXF`, TKB1 | loaded by the piece's `FUN_1000c80b` -> `FUN_10023936` `[CONFIRMED @SIMNTWRK 0x1000c80b]` |
| 4. frame table | exemplar prop 0x67 `{0x6300, group, inst}` | `Res\Sprites\CSAttrib*.IXF`, `BIN\r` v1, 20 frames x 15 bytes | |
| 5. pixels | each frame's (group, instance), type 0 pixels + type 1 anchor | any `Res\Sprites\*.DAT` | `*.DAT` in Res\Sprites is enumerated, SC3U `0x0040b761` (`*.SII` -> sc3imageinfo, `*.DAT` -> sc3dbssprite) |
| 6. street sim graph | `{0x625C6226, 0x825C6289, id*0x100+state}` | `Res\SSimData\<lang>\TrBlkAtt.IXF` | piece vt+0x50 `0x1000d1cf` (key), vt+0x54 `0x1000d225` (load) |
| 7. save | word1 & 0xffff = id, word0 bits 30-31 = state | city `.sc3`, group 0x2147c2dd | saver `0x1000ca2c` (section 5) |

Hop 5 was proven by building the art in a NEW group (`0x4E3D0001`) that no code computes: the game drew it, so the
pixels are reached through the exemplar's frame table, not from `id << 16` in Roads.DAT's group 5.
Hop 6 is optional for routing and stability (arm TN). netcat decoded TrBlkAtt as the street-level pedestrian and vehicle
graphs read by STRTSIM (`FUN_10016aa5`, `FUN_1000cf69`, `FUN_1002066a`; netcat's finding, not re-read here), so a piece
without it is expected to lose animated cars and people, not traffic density. Not checked frame by frame.

## 2. Where the new records go without rewriting shipped files

SYS.PAK `Default.ini [DBSegments]` lists two containers that the GOG install does not ship:
`0x55908ADB = Res\Sprites\CSAttrib_Korea.IXF` and `0x55908ADC = Res\Occupant\OccupantAttribs_Korea.IXF` (the latter also
`[OccAttribCache] Entry5`). The game opens them if present. They are the mod's own containers:

- `OccupantAttribs_Korea.IXF`: the exemplar, a byte copy of the source piece's TKB1 record with prop 0x67 rewritten
  to `{0x6300, 0x55908ADB, id}`. The `_2` containers follow the same convention (their 0x67 group is their CSAttrib
  segment id `0x552D8026`), so this is the shipped pattern, not a guess.
- `CSAttrib_Korea.IXF`: the frame table, frames pointed at the new art.
- `Res\Sprites\<group>_<name>.DAT`: anchors verbatim + recoloured pixels (filename prefix = record group, as every
  shipped DAT does).

Unavoidable edits (copied, never edited through a link): `ROAD_GRND_Set.txt` (+ the id), `ROAD_GRND_SimpleRules.txt`
(the RESULT lines), and optionally TrBlkAtt per language (appended with `ixf_insert.append`, old bytes untouched, the
index has 161 free slots of the 1,024 it reserves).

A second mod cannot also use the Korea pair. More free names need a SYS.PAK `[DBSegments]` key, which `syspak_mod.py`
cannot add today (gap 1 of the capability map). Several pieces fit in one Korea pair: the containers take up to 1,023
records each.

## 3. Recipe

```
py -3.12 re/tools/netmod/link_tree.py  C:\...\Simcity_stock  C:\...\Simcity_stock_<name>
py -3.12 re/tools/netmod/newpiece.py build --stock C:\...\Simcity_stock --out <moddir> --id 20029 --src 29 --tint blue
py -3.12 re/tools/netmod/newpiece.py install --mod <moddir> --tree C:\...\Simcity_stock_<name> --stock C:\...\Simcity_stock
py -3.12 re/tools/netmod/newpiece.py check --tree C:\...\Simcity_stock_<name> --id 20029
```
`--no-trblk`, `--no-rules`, `--no-set` drop parts; `uninstall` relinks the stock files and deletes the new ones.
To author art instead of tinting, export the 20 pixel records with `sprite_patch.py --export`, edit, and swap them in
before `new_container` (same size rule as `SPRITE_MODDING.md`).

Rules for the id: 16 bits (save word1 & 0xffff, piece +0x18 low half `[CONFIRMED @0x1000c80b]`); the rule value
`id*256+state` must fit the parser (5,127,425 for 20029 worked); not in 15130..15141 (special-cased by `FUN_1001a5f2`);
not an id that already has an exemplar (build refuses). Highest stock id is 18091.

## 4. What the new id loses: the hardcoded id lists in SIMNTWRK

Measured:
- **Rail and power lines do not cross it.** Same drag in both trees: over piece 29 the game makes a level crossing (69)
  or a power crossing (67); over 20029 the rail or line stops at the road and the road tile is unchanged
  (`verify/newpiece` arms XC/XM, PC/PM). Cause `[CONFIRMED @0x100167d4]`: a crossing forms only over 0x1d, 0x2c, 0x49,
  0x0e, 0x0f, 0x5c, 0x2bc4, 0x3acb; any other existing piece returns without placing.
- **A save that holds the id loses those tiles when loaded without the mod**: no crash, the tiles are not created and
  the next save drops them (arm R, -22 tiles). Players must keep the mod for as long as the save has the piece.

Static only (read, not run). Each compares the piece id against a fixed list, so a new id takes the "other" branch:
- `0x1001ab26`, `0x1001abb2`, `0x1001ac2b`, `0x1001acbe`, `0x1001af19`, `0x1001afc7`, `0x1001b07c`, `0x1001b10c`,
  `0x1001b1a1`, `0x1001b248`, `0x1001b2e0`: predicates that read the occupant's piece id (vt+0x5c(0xffff)) and accept
  only listed ids, e.g. `0x1001abb2` accepts {0x1d, 0x2bc4, 0x2c, 0x49, 0x3acb, 0x1e, 0x2d}, `0x1001af19` accepts per
  rotation {0x47,0x49,0x3e86,0x5c,0xf} / {0x1d,0x2bc4,0x45,0x5c} / {0x49,0x3e86} / {0x2bc4}. Which game action each
  predicate gates is not traced.
- `0x1000de17`: a piece 0x1d is randomly replaced by 0x3ac0 / 0x3ac1 / a third id (decoration variants). A new id gets
  none.
- `0x10009d20`, `0x1000abde`: crossing and diagonal code with 0x49 / 0x3acb literals.
- Crossing matrix `DAT_100318ac` (6x6, netcat dumped it): a new id has no row, so no crossing piece exists for it.
What it keeps (measured): road class (kind 1, `SIMNTWRK+0x2B5DC`), the road cost, the straight's tiling (its neighbours
tile around it as around 29), traffic density routing over it.

## 5. Save format: the state field (settled in this task)

`state` = save word0 bits 30-31, `props` = word1 >> 16. The saver `FUN_1000ca2c` (piece occupant vt+0x24, called per cell
by `FUN_10012fc3` at `0x10013070`) writes coord via record vt+0x30 (`0x1000d4d2`), state `occ+0x10 >> 0x1e` via vt+0x38
(`0x1000d50b`), id and props `0x63559421/1e/20/1f` via vt+0x84 (`0x1000d5f5`), and occupant `+0xc` bits 25/24 via vt+0x3c
(`0x1000d536`, word1 bits 28/29) `[CONFIRMED @0x1000ca2c]`. In game: a road along x saves state 0, along y state 1, word1
high half 0x3000 (arm C). `network_layer.py` now names them `state`/`props` and the instances surface/pipe/subway
(`--selftest-fields` 5/5 over 421,792 shipped tiles). Its `set_piece` writer has now been loaded by the game (7,419 edits,
Berlin, arm TM), which lifts that fence for `set_piece`; `add_tile` remains unloaded.

## 6. What the next stages need (as I read the owner goal: more texture variants and interactions)

| want | lever | tool state |
|---|---|---|
| a different look for an existing piece everywhere | reskin its frames (`sprite_patch.py`) | works; note 89 pieces draw from Utilities.DAT, not Roads.DAT (netcat) |
| a NEW look as an extra variant that coexists with the stock one | this recipe: new id + rule RESULT | works for one id per bare rule; `newpiece.py` clones any `--src`; needs a rule editor that targets contextual rules |
| variants chosen by context (next to buildings, near water) | ComplexRules / conditions | no ComplexRules semantics yet (gap 5) |
| random variants like 0x3ac0/0x3ac1 | `0x1000de17` is code | needs a patch, or a ComplexRules lever if one exists |
| the new piece crossing rail / power / highway | crossing matrix + the 0x100167d4 list are code | needs a code patch (mod DLL) or reusing a crossing-capable id |
| more mod containers than the Korea pair | SYS.PAK `[DBSegments]` key | `syspak_mod.py` cannot add keys (gap 1) |
| new art at a different size | anchor record + .SII | untested (`SPRITE_MODDING.md` rule 1) |
| highway / rail / bridges | same chain, other Set/rule files; bridges use `*_Bridges.txt` (netcat decoded) | untested here |
| screen capture on this machine | desktop grabs were white on 2026-10-12 | `np_drive.py shot` uses sc3resize's in-process DUMP |
