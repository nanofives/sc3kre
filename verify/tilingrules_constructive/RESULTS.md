# T2 constructive rung — RESULTS

**Verdict: CONSTRUCTIVE POSITIVE. T2 MET, 2026-08-25.** A surgical 2-line edit to
`ROAD_GRND_SimpleRules.txt` re-skins a freshly-drawn straight road tile from the straight piece
(29) to the curve piece (11203). The intended piece appears exactly where designed. Measured on the
**saved network layer** (byte-level, camera- and pixel-independent) — C4-grade.

This is the constructive complement to T1 (which was destructive: breaking `ROAD_GRND_Set.txt` made
road tiles vanish). T1 showed rules are honoured; T2 shows the tiler can be **aimed**.

## ⚠️ Pre-registration provenance — read this before trusting the "predicted" claims
The prediction (edited SimpleRules → drawn straight-mask tiles = **11203**) was committed **before**
run #6 was approved. For this run that fact is attested by the **orchestrator transcript** (the
prediction was stated to the orchestrator ahead of the fire order), **not** by `PRE.md`'s own
filesystem timestamp — `PRE.md` was untracked and its mtime is ~1 minute before this file, so it
cannot self-certify. **Process fix adopted going forward:** `PRE.md` is now git-trackable
(`.gitignore` whitelist `!/verify/*/*PRE.md`) and is to be `git commit`-ed BEFORE the lease is taken,
so git supplies a tamper-evident pre-run timestamp and pre-registration becomes a fact, not an
assertion. Also note: the three `.sc3` saves are **not retained** (game content must never reach the
public repo), so the per-run piece counts and hashes below are the SOLE record and are not
recomputable — they are written here in full for that reason.

## Method — a saved-file oracle, not pixels

Farmsville's load camera is non-deterministic (U-082), so pixel A/B is unreliable. Instead the
result is scored on the saved city's network layer, decoded per-tile by `re/tools/network_layer.py`
(SIMNTWRK layer `0x2147c2dd`; tile record = word0 packed coord, word1 = pieceId|state). The drawn
road is isolated by `--diff baseline after` and each ADDED tile classified by its 4-neighbour mask
(5/10 = straight). The piece id at occupant `+8` is the rule-resolved render piece, baked at build
time — so this reads what the tiler chose, independent of how/where it was drawn.

Procedure (all three runs identical): path-load Farmsville (N=192, paused), dismiss tip
`0xE2FA5BC2`, `fire:0x10004001` (Roads tool), `drag:400,560,640,680`, `fire:0x10009002` (Save
overwrites Farmsville.sc3), copy save out, restore baseline, `--diff`. Game content backed up and
hash-restored every run (Farmsville `9776e016…`, rule files == 68-file backup).

## The three runs — same drawn road, world (146, y160..172): 2 stubs + 11 straight-mask tiles

| run | rule edit | ADDED straight-mask (5/10) tiles | saved-file sha256 |
|---|---|---|---|
| STOCK (control) | none | **piece 29** ×11 | `d8da5e03…` |
| EDITED `final.txt` | mask5/10 29→11203 | **piece 29 ×11 (UNCHANGED)** | `d8da5e03…` (byte-identical to stock) |
| EDITED `SimpleRules` | lines 77/105 29→11203 | **piece 11203 ×11 (CHANGED)** | `32f593d8…` |

The endpoint stubs (mask 8 / mask 2) stayed piece 11225 in all three — the SimpleRules edit was
surgical (bare `1,10`/`1,5` rules only), so only the isolated-straight middles changed.

## Two findings, both cited

### 1. `ROAD_GRND_final.txt` is NOT the drawn-piece lever (the byte-identical negative)
Editing `final.txt`'s mask-5/10 straight entries (29→11203) produced a **byte-identical save** to the
stock run — zero effect. Explained by the executed pipeline for a drawn tile, from the decompilation
[CONFIRMED @ 0x1001547b / 0x100175ed / 0x10019768]:

  **SimpleRules (group 8, fixpoint, FIRST) → ComplexRules (group 0x18) → final (group 4, LAST).**

`final` runs last and only resolves tiles the earlier passes left open. SimpleRules' fixpoint sets a
straight to 29 first, so `final` never re-touches it. Measurement and static trace agree exactly.
(The "group" constant is a neighbourhood-radius + priority threshold, not a table index. `*_Set.txt`
loads via FUN_10016d87 into a separate table set; `*_Convert.txt` via FUN_10017f98 into another.)

### 2. `ROAD_GRND_SimpleRules.txt` IS the lever (the positive)
The rule that fires for an isolated straight is the BARE selector with no conditions:
line 77 `1,10`/`2,0`/`5,255,7425` (N+S) and line 105 `1,5`/`2,0`/`5,255,7424` (W+E). Editing ONLY
those two result lines to the curve value (2867969 / 2867968 = 11203) changed the drawn straight to
a curve, with zero perturbation of the 69 `3,dir,<val>` neighbour-condition lines that decide *which*
rule fires. Predicted 11203, measured 11203 — the prediction was committed in `PRE.md` before the run.

## What this establishes for a modder

**A network can be re-tuned so it draws differently but correctly, by editing the plain-text tiling
rules — and the authoritative stage for a drawn tile's piece is SimpleRules (fixpoint), not final.**
A tiling mod that wants to change what a topology (straight/curve/T/…) renders as must edit the
SimpleRules result line for the rule that fires, not `final.txt`. This is the practical recipe for
"a new road type" by re-skin/re-tune within the closed 6-network set (a 7th network remains
impossible without code patches).

## Limits on record (unchanged fences)
- **Render/build-path result, no SIMULATION claim.** Whether traffic/growth react was not measured;
  the sim was paused. (The unpause primitive is being built by bigcities; a sim-level tiling test is
  the documented follow-up, and the fence stays until such a test actually runs.)
- One edit of one kind (straight→curve) to one network (road). Other topologies/networks untested.
- Convert (a later stage) does not mask a fresh straight — confirmed by the stock control (drawn
  straights = 29, not a Convert variant). Whether it masks other pieces is untested.

## Install / provenance
Install carried the camera session's `SIMSPR.DLL` scroll mod throughout — neutral for a saved-file
piece-id oracle (SIMSPR is render/camera; SIMNTWRK resolves the piece). Left untouched; dirty lease
releases audited. Farmsville.sc3 never persisted a road (baseline restored + hash-verified each run).
Saves are deterministic (identical draw → byte-identical save), which is why the final-edit null is
byte-exact.
