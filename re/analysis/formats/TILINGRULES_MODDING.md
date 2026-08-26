# Editing SimCity 3000's network tiling rules — the working procedure

**Status: validated in the running game at BOTH ends, 2026-08-25.**
- **Destructive (T1):** replacing `ROAD_GRND_Set.txt` with a 7-byte `{99999}` made **every road tile
  vanish** — the corridor, the level-crossing road surface, the streets inside a settlement (houses
  intact) and the vehicles on them — **while the railway drew normally** from its own untouched Set
  file. Record: `verify/tilingrules_read_test/RESULTS.md`.
- **Constructive (T2):** a **2-line** edit to `ROAD_GRND_SimpleRules.txt` re-skinned a freshly-drawn
  straight road tile from the straight piece (29) to the curve piece (11203) — the intended piece
  landed exactly where designed, measured byte-level on the saved network layer. So a *substitution
  producing a different-but-valid tiling* is now proven, not just an erasure. Record:
  `verify/tilingrules_constructive/RESULTS.md`.

This is a how-to. The format spec is [TILINGRULES.md](TILINGRULES.md); the engine that consumes it
is `re/analysis/NETWORK_RULE_ENGINE.md`; the netType enum is `re/analysis/NETWORK_TYPES.md`.

Tool: `re/tools/tilingrules.py`. `--selftest` round-trips **68/68 files byte-identically**;
`--crosscheck` accounts for **13,040 of 13,040 rule values with 0 unexplained**; `--lint` reports 0
findings on the shipped set.

## What you can and cannot do

| | |
|---|---|
| **Retune** an existing network's tiling — which piece appears for which neighbourhood | ✅ possible, **game-proven both ways** (T1 erase, T2 substitute) |
| **Re-skin** an existing network (its art is chosen by piece id → exemplar → sprite) | ✅ possible — a drawn straight was re-pointed to the curve piece (T2) |
| **Add a 7th network type** | ❌ **impossible without patching code** |

**So "a new road type" means re-skin + re-tune of one of the six existing networks, not a seventh
network.** You can change what any topology (straight / curve / T / cross / stub / isolated) renders
as, per neighbourhood, and repoint it to a different piece id (→ different exemplar → different
sprite; author sprites with `sprite_patch.py`). What you cannot do is add ROAD-alongside-a-new-name
as a distinct network with its own tool, cost and simulation behaviour — the 6-member enum, the `*6`
piece-matrix stride, the 42 predicate vtables and the fixed `MenuItem.INI` GUIDs all close that off.
A convincing "new road type" is therefore a **reskinned/retuned variant of an existing network**, not
a genuine seventh.

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

## ⭐ Which rule stage chooses the piece — edit SimpleRules, NOT final

**This is the single thing a modder is most likely to get wrong, because `final` is named like the
answer and is the obvious place to look. It is the wrong file.** Measured byte-level + confirmed in the
decompilation 2026-08-25 (`verify/tilingrules_constructive/RESULTS.md`).

When a tile is (re)tiled, the retiler `FUN_1001547b` runs the three RULES-family files **in this
order** `[CONFIRMED @0x1001547b:565/581/597, files mapped @0x100175ed:315/321/327]`:

| order | file | pass | how it runs |
|--:|---|---|---|
| 1 | **`*_SimpleRules.txt`** | group 8 | run to **fixpoint FIRST** |
| 2 | `*_ComplexRules.txt` | group 0x18 | up to 5× (2-tile-radius / intersection pass) |
| 3 | `*_final.txt` | group 4 | **once, LAST** |

`*_final.txt` runs **last and only resolves tiles the earlier passes left open.** SimpleRules'
fixpoint already picks the piece for a normal tile, so **editing `final.txt` for that tile does
nothing.** Proven: editing `ROAD_GRND_final.txt`'s straight entries (29→11203) produced a
**byte-identical save** — zero effect — while the same edit in `ROAD_GRND_SimpleRules.txt` changed the
drawn tile. (The "group" constant is a neighbourhood-radius + priority threshold, not a table index or
a rule filter.)

**Recipe — change what a topology renders as:**
1. Find the rule in `*_SimpleRules.txt` that fires for your case. For an **isolated** run (no
   perpendicular/diagonal context) it is the **bare selector with no conditions**: `1,<mask>` then
   `2,0` then `4,1` then `5,255,<pieceValue>`. Road straight masks: `1,10` (N+S) at line 77 and `1,5`
   (W+E) at line 105 in the shipped file. `<pieceValue> = pieceId*256 + state` (e.g. `7425 = 29*256+1`,
   `2867969 = 11203*256+1`).
2. Edit **only that `5,255,<val>` RESULT line.** ⚠️ **Do NOT `--replace-id` a piece value in
   SimpleRules** — the same value appears dozens of times as a `3,<dir>,<val>` **neighbour-condition**
   (7424/7425 occur 87× each, mostly as conditions), and rewriting those corrupts the matching that
   decides *which* rule fires. Change the result, never the conditions. Use a byte-preserving
   line-targeted edit (or `--set-value` on the exact token index), then `--lint`.
3. A rule with `2,N` (N>0) carries `3,<dir>,<val>` conditions; it fires only when the tile's neighbours
   match, so a contextual variant (road-with-building, traffic texture) is governed by a different
   result line than the bare rule.

`*_Convert.txt` (a later remap of specific ids) does **not** touch a freshly-drawn basic straight —
confirmed by the control (drawn straights = 29, not a Convert variant). It can still remap decorative
ids, so check `--dump` of the Convert file before assuming your target id survives.

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

- **~~A substitution has not been run.~~** ✅ **Done (T2):** a drawn straight was substituted to the
  curve piece via a SimpleRules result edit, measured on the saved file. Two kinds of edit are now
  proven — erase (Set) and substitute (SimpleRules result).
- **Both results are render/build-path, NOT simulation.** T1 stopped tiles being *drawn*; T2 changed
  which *piece* a drawn tile is. Neither shows the **simulation** routes traffic differently. The sim
  was paused for both (path-loaded cities load paused; the unpause message-post primitive is being
  built separately). A sim-level tiling test is the open follow-up, and this fence stays until one
  runs.
- **Scope of T2:** one topology (straight), one network (road), the bare no-context rule. Contextual
  variants, other topologies, other networks, and ComplexRules' role are untested.
- **T1 frames are pre-resize** — says nothing about `U-068`. T2 used no frames at all (saved-file
  oracle), so it is independent of the camera (U-082) and the render defect (U-068) alike.
- Controls that held: T1 status bar character-identical (`Pob: 36,172`, `§45,724`, `5/16/1904`) so no
  sim drift, camera identical to the pixel, **111 `TilingRules` filetrace lines** per run; T2 endpoint
  stubs held at piece 11225 across all three runs (surgical edit) and the stock control's drawn
  straights were 29 (so the effect is the edit, not the drawing procedure).
