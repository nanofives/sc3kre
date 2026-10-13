# netpack: network mod packages (netmod framework step 1, 2026-10-13)

**Status: game-proven on stock DLLs** (`verify/netpack/RESULTS.md`, PRE `8b381a8`). Two example packages installed
by the tool render in game (blue variant road 20029, red-reskinned highway 73), the variant's name shows in the query
dialog, and uninstalling them leaves the test tree byte-identical to the stock install (3,488 of 3,488 files).

Owner intent: a framework to add textures, artwork, interactions and variants to the existing game. The blue road is
a test fixture, not content.

Files: `re/tools/netmod/netpack.py` (CLI), `netpack_rules.py` (rule edits, also a library for the netrules editor),
`netpack.schema.json` (manifest JSON Schema, draft 2020-12), `examples/example_blue_road`, `examples/example_reskin`,
`re/harness/src/sc3netmod.c` (overlay + per-package variant tables).

## 1. A package

One folder, one `manifest.json`, optional PNG art. Nothing else.

```json
{
  "netpack": 1, "name": "example_blue_road", "version": "1.0.0", "author": "...", "description": "...",
  "game": {"Apps/SIMNTWRK.DLL": "<sha256 of the stock file the package was made against>"},
  "variants": [{"id": 20029, "base": 29, "network": "ROAD", "name": {"*": "Blue road", "ENGLISH": "Carretera azul"},
                "art": {"from": 29, "recolor": "blue"}, "trblkatt": "copy_base"}],
  "reskins":  [{"piece": 73, "art": {"recolor": "red"}}],
  "rules":    [{"file": "ROAD_GRND_SimpleRules.txt", "op": "set_results",
                "match": {"selector": 10, "conds": [], "results": [[255, "29:1"]]}, "results": [[255, "20029:1"]]}],
  "ini":      [{"file": "Occupant.ini", "section": "...", "key": "...", "value": "...", "op": "set"}]
}
```

| part | meaning | checks (`validate`, `install`) |
|---|---|---|
| `game` | path -> sha256 anchors | refused if the tree's file differs |
| `variants[]` | a NEW piece id that behaves as `base` (exemplar, cost, traffic, crossings, saved id) and draws its own art | id 1..65535, no stock exemplar, not 15130..15141 (`FUN_1001a5f2`), not in the Set; base has an exemplar and is in `<network>_GRND_Set.txt`; no other installed package declares the id |
| `variants[].art` | start from the frames of `from` (default `base`), optional `recolor`, then any `png_dir` PNG replaces its frame | PNG size must equal the frame (`sprite_patch.image_to_surface`); a PNG that names no frame is refused |
| `variants[].name` | piece name, one string or `{language folder or "*": text}` | written per `Apps\Res\Text\<folder>` |
| `variants[].trblkatt` | `copy_base` (default): the base's TrBlkAtt records re-keyed to the new id, every language; `none` | the reserved index must have room (161 free slots per language) |
| `reskins[]` | new art for the frames of an EXISTING piece | no two packages reskin the same frame table; pieces that share the table are reported |
| `rules[]` | TilingRules edits, section 4 | every match count must equal `expect` (default 1); stage lint |
| `ini[]` | keys inside a SYS.PAK member: `set` (existing key), `add` (new key), `append` (line even if the key exists) | member, section and key found exactly as required |

Art file names inside `png_dir`: frame position k in the piece's table -> `z{zoom}_r{rot}.png` with zoom `(k % 20) // 4`,
rotation slot `k % 4`, layer `k // 20` (`l{layer}_z.._r...png` for layer > 0); the layout netcat measured over all 380
pieces. `netpack.py export-art <piece> <dir>` writes the stock frames under exactly these names, which is the starting
point for authoring. Transparency is the colour key: alpha below 128 = transparent.

Recolour: `blue` and `green` are newpiece.py's 5/6/5 tints (the 20029 art game-proven in `verify/newpiece`); `red`,
`gray`, `yellow` or `{"mul": [r,g,b], "add": [r,g,b]}` work on 8-bit channels. No pixel can land on the colour key.

## 2. What install builds (all packages merged, every time, from the stock files)

Merge order is package NAME order, so install order does not change a byte (selftest U3).

| output | content | why there |
|---|---|---|
| `Apps\Res\Occupant\OccupantAttribs_Korea.IXF` | one exemplar per variant: the base's TKB1 record, prop 0x67 -> `{0x6300, 0x55908ADB, id}`, prop 0x6D -> `{0x2026960B, 0xA1096A4F, id}` when named | SYS.PAK `Default.ini [DBSegments] 0x55908ADC` lists it, GOG does not ship it (`NEW_PIECE.md` 2) |
| `Apps\Res\Sprites\CSAttrib_Korea.IXF` | one frame table per variant, frames pointed at the new records | `[DBSegments] 0x55908ADB` |
| `Apps\Res\Sprites\4E3D00nn_netpack.DAT` | anchor (verbatim) + pixel record per distinct source frame, key `(group, piece << 16 | ordinal)`; a new group every 1,022 records | `Res\Sprites\*.DAT` is listed at startup (arm F: SC3U and SIMSPR call `FindFirstFileA "...\Res\Sprites\*.DAT"`) |
| `Apps\Res\Sprites\CSATTRIB.IXF` (or whichever CSAttrib holds the table) | copy with each reskinned piece's frame table rewritten in place (same size: only the frames' group/instance change) | the stock exemplar keeps pointing at its table, so no exemplar edit |
| `Apps\Res\SSimData\<lang>\TrBlkAtt.IXF` | copy + appended records, old bytes kept (`ixf_insert.append`) | no loose override exists for it (`NETMOD_CATALOG.md` 5) |
| `Apps\Res\TilingRules\<NET>_GRND_Set.txt` + edited rule files | variant ids added to the Set, then the packages' rule edits | the tiler reads these loose files (`TILINGRULES.md` T0) |
| `Apps\Res\Text\<lang>\SC3StringsNetpack.IXF` | name records `{0x2026960B, 0xA1096A4F, id}`, u32 length + cp1252 text | new file |
| `Apps\Sys\SYS.PAK` | copy with `Default.ini [DBSegments]` += `0xa1096a4f=0x80c381d7;Res\Text\%Language%\SC3StringsNetpack.IXF` (only when a variant is named) plus the packages' `ini` edits | the text containers are opened by the names in that list, not by folder listing (arm O); the shipped list already repeats key 0xa1096a4f (`SC3StringsBuildings.IXF`, `SC3StringsBuildings_Holidays.IXF`); SYS.PAK wins over loose ini files `[CONFIRMED @ 0x004872e8]` |
| `mods\netmod\tables\<package>.txt` | `<variant> <base>` per line | read by `sc3netmod.dll` (section 5) |

Measured in arm N: a SYS.PAK whose `Default.ini` grew by one line (+67 bytes, rebuilt by `syspak_parse.build`) loads,
and the container it names is opened. That is the first game load of a length-changing SYS.PAK in this project, and it
closes gap 1 of the capability map in practice: a package can add `[DBSegments]` lines, so the Korea pair is no longer
the only place new containers can go. netpack still merges into the Korea pair (1,023 variants fit).

## 3. Delivery: overlay (default) vs direct, decided by arm F

**Overlay.** `install` writes the outputs under `<root>\mods\netmod\overlay\<same relative path>` and nothing under
`Apps\`. `sc3netmod.dll` hooks the import slots of `CreateFileA`, `GetFileAttributesA`, `FindFirstFileA`,
`FindNextFileA`, `FindClose` (and `LoadLibraryA/ExA`, to hook each module as it loads) in every module of the game:
a read-only open of `<root>\X` is served from `overlay\X` when that file exists, and a listing of a folder the overlay
mirrors is merged (stock entries first, overlay-only names after). Basis: every game module imports those functions
from KERNEL32.dll by name, ANSI only, and `fopen`/`_sopen` reach `CreateFileA` through the shipped `MSVCRT.DLL`'s own
import (import tables read with pefile).

Arm F (newpiece's blue road files only in the overlay, `SC3NETMOD_FILELOG=1`), every class of file the format uses was
seen going through a hook and served from the overlay, with the calling module:

| file | opened by | how |
|---|---|---|
| `TilingRules\ROAD_GRND_Set.txt`, `ROAD_GRND_SimpleRules.txt` | SIMNTWRK.DLL | `GetFileAttributesA` then `CreateFileA`, redirected |
| `Occupant\OccupantAttribs_Korea.IXF`, `Sprites\CSAttrib_Korea.IXF`, `SSimData\English\TrBlkAtt.IXF` | GZResourceD.dll | `CreateFileA`, redirected |
| `Sprites\*.DAT` listing | SC3U.exe, SIMSPR.DLL | `FindFirstFileA`, merged: 31 entries, 1 from the overlay |
| `Sprites\4E3D0001_NewPiece20029.DAT` | SIMSPR.DLL | `GetFileAttributesA` + `CreateFileA`, redirected |
| `Sys\SYS.PAK` (arm N) | SC3U.exe, simvariables.dll, SIMINIT.DLL | redirected |
| `Text\English\SC3StringsNetpack.IXF` (arm N) | GZResourceD.dll | redirected |

and the blue straights drew. `link_tree.py --verify` after the run: 3,488 linked, 0 de-linked, so the stock files
were not touched. Overlay is therefore the default: the stock install is never written, uninstall is deleting a
folder, and a game started without the DLL is exactly stock.

**Direct** (`install --mode direct`) writes the same files into `Apps\`, for a game run without `sc3netmod.dll`.
Every replaced stock file is copied to `mods\netmod\backup\` first (hash in the ledger), and every target is deleted
before it is written, so a hard-linked tree never writes through to its source. Without the DLL a variant loses the
crossings and the stock-safe saves (`NEW_PIECE.md` 4); reskins and names do not need the DLL.

Ledger: `<root>\mods\netmod\ledger.json` (mode, packages, every output file with its sha256 and, in direct mode, the
stock file's sha256). Installed package sources are copied to `mods\netmod\packs\<name>\` so uninstall and re-merge
do not depend on the original folder. A tree with a `mods\netmod` folder but no ledger, or with newpiece.py files in
`Apps\Res` that no ledger owns, is refused.

## 4. Rule edits (`netpack_rules.py`)

No byte offsets. A rule is found by its number in the STOCK file (`{"rule": N}`, as netcat prints it) and/or by its
exact content (`selector`, `conds`, `results`), and `expect` says how many must match. Edits: `set_results`,
`replace_rule`, `insert_rule` (`before` / `after` / `at`), `delete_rule` on RULES files; `set_add` (Set files),
`list_add` (Protected), `pairs_add` (Convert). Values are raw ints or `"ID:STATE"`. All packages' edits to one file are
applied in one parse, so `{"rule": N}` always means the stock rule N. Rules nobody touched are re-emitted as their
original lines; every live rule file round-trips byte-identical through the parser. New or changed rules pass the
`tilingrules.py --lint` stage invariants (selector bits and dir below the stage mode). DEAD files are refused.

The two `set_results` edits of `example_blue_road` produce the same bytes as newpiece.py's `rules_retarget` (the
game-proven 20029 edit; selftest).

Library use: `netpack_rules.apply(file_name, stock_bytes, edits) -> bytes`, `parse_rules`, `result_ids`.

## 5. sc3netmod.dll changes

- Overlay block (section 3). Off with `SC3NETMOD_OVERLAY=0`; nothing is hooked when `mods\netmod\overlay` is absent.
  `SC3NETMOD_FILELOG=1` logs every hooked call under `Apps\Res` with the calling module.
- Variant tables: every `<root>\mods\netmod\tables\*.txt` in name order, then `Apps\Res\netmod_variants.txt`
  (newpiece.py installs). A variant two tables give different bases is dropped and logged. `SC3NETMOD_TABLE=<file>`
  still reads that one file only. `SC3NETMOD_CROSS=0` and `SC3NETMOD_SAVEBASE=0` are unchanged.

## 6. CLI

```
py -3.12 re/tools/netmod/netpack.py new <dir> [--id 20100 --base 29]   # scaffold: one green variant + its two rule edits
py -3.12 re/tools/netmod/netpack.py export-art <piece> <dir>           # stock frames as PNG, to paint over
py -3.12 re/tools/netmod/netpack.py validate <pack> [--tree <game>]    # alone, or merged with what <game> has installed
py -3.12 re/tools/netmod/netpack.py build <pack> --out <dir>           # deterministic outputs + BUILD.json (inspection)
py -3.12 re/tools/netmod/netpack.py install <pack> --tree <game> [--mode overlay|direct]
py -3.12 re/tools/netmod/netpack.py uninstall <name> --tree <game>
py -3.12 re/tools/netmod/netpack.py list --tree <game>
py -3.12 re/tools/netmod/netpack.py selftest                           # U1..U5 on temporary hard-linked trees
```
The stock files are read from `$SC3_GAME_ROOT` (or the main checkout). `install` refuses the dev install and
`Simcity_stock` unless `--allow-tree`.

## 7. Limits and open points

- Art keeps the source frame sizes (anchor + `.SII` untouched, `SPRITE_MODDING.md` rule 1). Format-0 alpha masks are
  copied, not recoloured.
- A variant's art always derives from STOCK frames, never from another package's reskin.
- A crossing over a variant uses the stock crossing tile (`NETVARIANT.md`); variants of rail, power, highway, pipe,
  subway and bridges as bases are accepted by the format but not proven in game (crossings for them are not wired).
- TrBlkAtt has 161 free index slots per language; `install` refuses past that (it never moves old payloads).
- `ini` edits other than the `[DBSegments]` line were not run in game. Occupant.ini keys are only names; nothing found
  so far reads them for network pieces.
- Not tested: 1024 cities, the owner's dev install (MAIN\Apps), the release layout with the DLL in Apps, two packages
  editing the same rule (the second edit's match then sees the first edit's result and fails loudly if it changed).
