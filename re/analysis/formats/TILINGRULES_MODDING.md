# Editing SimCity 3000's network tiling rules — the working procedure

**Status: validated in the running game 2026-08-25.** Replacing `ROAD_GRND_Set.txt` with a 7-byte
`{99999}` made **every road tile vanish** — the corridor, the level-crossing road surface, the
streets inside a settlement (houses intact) and the vehicles on them — **while the railway drew
normally** from its own untouched Set file. Record: `verify/tilingrules_read_test/RESULTS.md`.

This is a how-to. The format spec is [TILINGRULES.md](TILINGRULES.md); the engine that consumes it
is `re/analysis/NETWORK_RULE_ENGINE.md`; the netType enum is `re/analysis/NETWORK_TYPES.md`.

Tool: `re/tools/tilingrules.py`. `--selftest` round-trips **68/68 files byte-identically**;
`--crosscheck` accounts for **13,040 of 13,040 rule values with 0 unexplained**; `--lint` reports 0
findings on the shipped set.

## What you can and cannot do

| | |
|---|---|
| **Retune** an existing network's tiling — which piece appears for which neighbourhood | ✅ possible, **game-proven** |
| **Re-skin** an existing network (its art is chosen by piece id → exemplar → sprite) | ✅ possible |
| **Add a 7th network type** | ❌ **impossible without patching code** |

The negative is settled and worth not re-litigating: a closed 6-member enum appears in if/else
cascades across **11 functions**, `*6` is baked into the piece-matrix address computation, the 42
predicate vtables end flush with no room for a 43rd, and `MenuItem.INI` carries fixed GUIDs.

## Where the files are, and when they load

`Apps\Res\TilingRules\` — **68 loose text files**, read **unconditionally at startup**, 1,735–1,749 ms,
**with no city loaded**. (An earlier note claimed they load "with the network layers during city
setup". That is wrong.)

Four format families, by filename:

| family | files |
|---|---|
| BRACED | `*_Set.txt`, `DIAG_Set.txt`, `ROAD_GRND_FinalRules.txt`, `networkIntesection.txt` |
| COUNTED_LIST | `*_Protected.txt`, `*_Bridges.txt`, `Collapse.txt`, `*_Exits.txt` |
| COUNTED_PAIRS | `*_Convert.txt`, `*_Complex_Convert.txt` |
| RULES | `*_SimpleRules.txt`, `*_ComplexRules.txt`, `*_final.txt`, `*_SlopeRULES.txt`, `Landfill*.txt` |

Not all 68 are consumed by the same loader: `FUN_100196ce` reads the COUNTED_LIST set and a **second
parser `FUN_10019600`** reads the Convert / Complex_Convert families. The full accounting is in
`NETWORK_TYPES.md` §9 — **use that, do not count filenames.**

## ⚠️ The ordering trap — this has caught two separate analysis passes

The six `*_Protected.txt` vectors are **not** in netType order. Reading them off the slot addresses,
or off the file load order, gives the wrong answer:

| netType | network | slot | file |
|--:|---|---|---|
| 1 | ROAD | `0x10032394` | `Road_GRND_Protected.txt` |
| 2 | RAIL | `0x1003239c` | `RAIL_GRND_Protected.txt` |
| 3 | POWER | `0x100323a8` | `POWR_GRND_Protected.txt` |
| 4 | HIGHWAY | `0x10032398` | `HWAY_GRND_Protected.txt` |
| 5 | PIPE | `0x100323a4` | `PIPE_GRND_Protected.txt` |
| 6 | SUBWAY | `0x100323a0` | `SUBW_GRND_Protected.txt` |

**The slots' address order is ROAD, HWAY, RAIL, SUBW, PIPE, POWR** — a real ordering in the binary,
just not the one that answers the question. That is precisely why the wrong mapping kept looking
plausible. Established at C3 by three independent cascades: `NETWORK_TYPES.md` §9.

## The `state` byte, if you are authoring rotations

`state` is a **rigid quarter turn toward increasing `dir` index**: a piece's canonical edge `c`
presents at world direction `(c + state) mod 4`. Confirmed at C3 by three independent witnesses with
zero counterexamples across 95 final-stage rules, 1,660 stage-1 results and 249 convert pairs
(`NETWORK_RULE_ENGINE.md` §13).

**There is no global compass zero, and looking for one is the wrong question.** `state 0` is the
identity permutation; the absolute facing of `state 0` is **per-piece exemplar data**. The shipped
data carries **two authoring zeros**, one quarter turn apart — every piece family ships as two ids
90° apart, so `id2 state s` = `id1 state (s+1)`. The per-piece state-0 connection sets are tabulated
in §13.5.

> ⚠️ **The rotation sense and the per-piece zero are safe to build on. The word "clockwise" is not.**
> All of it is proved in tile-index `(dx, dy)` terms; the W/N/E/S labels come from a convention that
> was never independently re-derived. If that convention is wrong, the rotation sense is unaffected
> and every compass word flips.

## The procedure

```powershell
# 0. back up. Apps\Res IS GAME CONTENT.
$bak = 'verify\tilingrules_read_test\TilingRules.bak'
if (-not (Test-Path $bak)) { Copy-Item -Recurse 'Apps\Res\TilingRules' $bak }
"backup files: $((Get-ChildItem $bak -File).Count) (must be 68)"

# 1. look before you edit
py -3.12 re/tools/tilingrules.py --selftest              # 68/68 round-trip
py -3.12 re/tools/tilingrules.py --show  Apps\Res\TilingRules\ROAD_GRND_Set.txt
py -3.12 re/tools/tilingrules.py --dump  Apps\Res\TilingRules\ROAD_GRND_Set.txt --json

# 2. edit
py -3.12 re/tools/tilingrules.py --replace-id Apps\Res\TilingRules\ROAD_GRND_Set.txt 11225 12345
py -3.12 re/tools/tilingrules.py --set-value  Apps\Res\TilingRules\ROAD_GRND_Set.txt 7 4242

# 3. restore, and VERIFY the restore by hash
Copy-Item "$bak\ROAD_GRND_Set.txt" 'Apps\Res\TilingRules\ROAD_GRND_Set.txt' -Force
(Get-FileHash 'Apps\Res\TilingRules\ROAD_GRND_Set.txt' -Algorithm SHA256).Hash
```

Writes **preserve the original wrapping, indentation and CRLF** — only edited tokens are re-rendered.
Verified: `--replace-id 11225 12345` on `ROAD_GRND_Set.txt` changed exactly 3 bytes at offsets
170–172, left the length at 744, preserved every CRLF, and the result re-parses clean.

## ⚠️ Three hazards, all confirmed

**1. Nothing validates your rule file.** A 7-byte `ROAD_GRND_Set.txt` produced **no crash, no error,
no log complaint** — the roads simply stopped drawing. **A malformed rule file gives you an invisible
network, not a diagnostic.** If a network vanishes after an edit, suspect your file first.

**2. A case-sensitivity landmine.** The game requests **`Road_GRND_Protected.txt`** (mixed case); the
shipped file is **`ROAD_GRND_Protected.txt`**. It works only because NTFS is case-insensitive, and
all five sibling networks use the consistent upper-case form. On a case-sensitive filesystem that
open fails and **road protected-tile rules load empty** — vector `0x10032394`, netType 1. Filed as
`U-074`.

**3. A latent double free that YOUR mod can make live.** `SIMNTWRK FUN_10013771` (vtable slot `+0x54`)
calls `handler->QueryInterface(iid, out)` on one of 42 global predicate singletons and, **if that QI
returns false, calls `free()` on the singleton** without nulling it — which teardown then frees again.
As shipped it cannot fire: all 42 handlers accept `0xA1C085DB` and all 25 call sites pass exactly
that. **If you replace or wrap a predicate handler, your slot 0 must accept `0xA1C085DB` (and `1`).**
The crash would surface at teardown, far from your change. Filed as `U-080`.

## Limits of the game-side proof

- **One edit of one kind to one file.** Emptying a Set list is a blunt instrument; a *substitution*
  producing a different-but-valid tiling has not been run.
- **It is a render-path result.** Road tiles stopped being drawn. Nothing here shows the
  **simulation** stopped routing traffic over those tiles.
- **The frames are pre-resize.** This says nothing about `U-068`.
- Controls that did hold, for what they are worth: status bar character-identical
  (`Pob: 36,172`, `§45,724`, `5/16/1904`) so no sim drift, camera identical to the pixel, and **111
  `TilingRules` filetrace lines in each run** — the loader ran identically with the stock and the
  broken file.
