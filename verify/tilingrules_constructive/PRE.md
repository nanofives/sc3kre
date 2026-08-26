# T2 constructive rung — PRE-REGISTRATION (committed before any run)

Date 2026-08-25. Owner-approved: interactive-draw, straight→curve (loud). Session `roadtypes`.

## Verdict this run rests on (verified first-hand before firing)
`final` (mask→piece SELECTION) is consulted only on the interactive BUILD path, never on city load.
- Load `FUN_1000d6b3` reads occupant `+8` (piece id) verbatim, no rule lookup [CONFIRMED @ 0x1000d6b3].
- `+8` low 16 = piece id [CONFIRMED @ 0x1000d594].
- Build/apply `FUN_100165d8` bakes the rule-resolved piece id via factory `0xc14f8955`
  [CONFIRMED @ 0x100165d8:56], called by the retiler `FUN_1001547b:544`.
⇒ To make `final` change what is drawn, a road must be DRAWN after load, not reloaded.

## The edit (byte-verified on scratch; live `final.txt` stock hash `d2cfde00…ecfb`)
`ROAD_GRND_final.txt`: `--replace-id 7424 2867968` + `--replace-id 7425 2867969`
(mask 5 & 10 straights, piece 29 s0/s1 → curve piece 11203 s0/s1). Each op must report exactly 1
replacement. Both curve pieces already allowed in `ROAD_GRND_Set.txt`.

## Fixtures / install (all verified stock before run)
- `Cities\Farmsville.sc3` sha256 `9776e016…4eb7`, 249,277 B, N=192. NOT saved during runs → untouched.
- `Apps\Res\TilingRules` = backup byte-identical; `Set.txt` `9926948a…1358`.
- Install stock; SIMSPR restored to shipped `eec71500…291d` (5 slots 32.0).

## Run design — REVISED to a SAVED-FILE oracle (camera-independent; Farmsville load camera is
## non-deterministic, U-082, so pixels can't be matched). Owner-approved 2026-08-25.
Oracle: `re/tools/network_layer.py` decodes the SIMNTWRK network layer (`0x2147c2dd`) to per-tile
(x,y,pieceId,state). Validated: reproduces Farmsville road 2232 tiles (1041× id29, 37× id11203),
rail 545; mask convention confirmed (baseline straight-mask 5/10 tiles dominantly id29). `--diff
baseline after` isolates a drawn road's ADDED tiles and classifies each by 4-neighbour mask.

Sequence (both runs): `0xE2FA5BC2@20;fire:0x10004001;drag:400,560,640,680;wait:2000;fire:0x10009002@30;wait:12000`
(dismiss tip, Roads tool, lay road on open land, Save overwrites Farmsville.sc3, wait for write).
- **Run STOCK (control):** back up Farmsville.sc3; run; copy the saved Farmsville.sc3 → scratch
  `road_stock.sc3`; restore backup + verify `9776e016…`. `--diff` → ADDED straight-mask tiles' piece.
- **Run EDITED:** apply the two `final.txt` edits (verify 2-line blast radius, 67 files unchanged);
  back up Farmsville.sc3; run; copy saved → `road_edited.sc3`; restore backup + `final.txt`; verify
  hashes (`final.txt` `d2cfde00…ecfb`, all 68 == backup). `--diff` → ADDED straight-mask tiles' piece.
Camera position is irrelevant; only that the drag lays road (funds move) with some straight-mask tiles.

## Pre-committed outcomes (discriminator, on the SAVED network layer)
1. **CONSTRUCTIVE-POSITIVE (expected):** STOCK run's ADDED straight-mask (5/10) tiles carry piece
   **29**; EDITED run's ADDED straight-mask tiles carry piece **11203** (the curve), same drawing
   procedure. ⇒ the `final` edit re-skins freshly-drawn straights from the straight piece to the curve
   piece, on the build path. **T2 met** (constructive, camera- and pixel-independent, C4-grade).
2. **CONVERT MASKS IT:** STOCK added straights are a variant (44/92/…) not 29 → the edit on `final`'s
   29 is downstream-remapped, so straights don't change. A real pipeline finding (names Convert as the
   authoritative stage for fresh straights). Not wasted.
3. **NO STRAIGHT-MASK TILES ADDED / crash / edit unread:** drag produced no straights (re-run longer
   drag), or a crash, or 111-TilingRules filetrace absent. Investigate.

## Controls
RAIL layer untouched (cross-network) · pre-existing road tiles untouched (only ADDED tiles judged) ·
STOCK run is the same-procedure control for the EDITED run · funds delta = road-laid oracle · 111
TilingRules filetrace lines each · both saves diffed against the identical stock baseline.

## Protocol
`SC3_SESSION=roadtypes`; `capture.ps1` self-acquires/releases the lease (do NOT wrap). Keep
`-filetrace`. Restore `TilingRules` in a `finally`, re-verify hashes. NEVER commit `TilingRules.bak/`
or captured frames. Never kill a process not mine.

---

## RUN #6 PRE-REGISTRATION — the SimpleRules constructive test (committed before the run)

Lever CONFIRMED by measurement + static trace: for a DRAWN tile the pipeline is SimpleRules (group-8
fixpoint, FIRST) → ComplexRules → final (LAST). `final.txt` is not authoritative (byte-identical
stock/edited saves). The authoritative stage for an isolated straight is the BARE SimpleRules rule.

EDIT (applied, byte-verified): `ROAD_GRND_SimpleRules.txt` line 77 `5,255,7425`→`5,255,2867969`,
line 105 `5,255,7424`→`5,255,2867968` (bare `1,10`/`1,5` straight rules → curve 11203). Blast radius
= exactly 2 result lines; 67 other files stock; tool parse clean (430 rules).

RUN: same proven sequence `0xE2FA5BC2@20;fire:0x10004001;drag:400,560,640,680;wait:2000;fire:0x10009002@30;wait:12000`,
path-load Farmsville, `-filetrace`. Copy saved → `road_simple.sc3`; restore Farmsville + SimpleRules;
verify Farmsville `9776e016…`, SimpleRules == backup, 68/68 == backup.

CONTROL: reuse existing `road_stock.sc3` (stock rules, drawn straights = piece 29). One arm.

PRE-COMMITTED OUTCOMES (on `--diff` ADDED straight-mask 5/10 tiles):
1. **CONSTRUCTIVE-POSITIVE (predicted):** ADDED straight-mask tiles carry piece **11203** (curve),
   vs the stock control's 29. ⇒ a SimpleRules edit re-skins a drawn straight to the curve piece.
   T2 constructive rung MET (camera- and pixel-independent, byte-level, C4-grade).
2. **STILL 29:** a CONDITIONAL SimpleRules rule (not the bare `1,10`/`1,5`) fired for the isolated
   straight → locate it (worker `[UNCERTAIN]`). A finding, not a waste.
3. **Broken/over-broad/crash:** investigate.
