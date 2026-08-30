# PRE-REGISTRATION — System-B grid re-show (step 8c), the defect A+B fix

Committed **before** the hand-test. Owner is the instrument (real-display run).

## Why

Diagnosis (`RESIZABLE_WINDOW.md` §9, `verify/resize_objreregister/`): buildings, roads, terrain and
zones are **System-B tile drawables** on the `iso+0x24` cell grid. They re-register only on a view
**transition**, via `FUN_100071a3`'s inner loop — which a resize never triggers. That is why after a
resize the new area is black until a scroll (terrain/zones) and buildings/roads never return; and why a
manual data-layer toggle repaired the screen (it drove that transition). Step 8a/8b (added prior) only
handle the sprite/object grid `iso+0x380`, not System B.

## The change (`re/harness/src/sc3resize.c`, new step 8c after 8a/8b)

Extract `FUN_100071a3`'s synchronous inner loop, **net-zero** (no zoom/rotation change, invisible): for
every occupied cell of `iso+0x24`, call `FUN_10006c67` (hide, drawable vtable +0x38) then
`FUN_10006efc` (show, +0x34). Both key off the current zoom/scale, so sublayer bits end where they
started and every occupied cell re-issues its draw into the freshly rebuilt buffer.

- Cell layout (confirmed `FUN_10005b42`): grid `iso+0x24` = `int[rows]` of `cols`×`0x14`-byte cells;
  `cell+0` = drawable, `cell+0x11 & 0x40` = occupied. Dims: `rows=iso+0x14`, `cols=iso+0x18`.
- `iso+0x28` = ZOOM, `iso+0x2c` = ROTATION (both corrected this session; the 5 sublayers are LOD
  buckets, not content categories, so there is no per-index "buildings"/"roads").
- Call args `(drawable, zoom, rot, row, col)`, `ecx=iso`, both `__thiscall` — from `FUN_100071a3:61-64`.
- The show/hide primitives self-lock via `iso+0x46c` when async (`iso+0x3c9`), so no outer render lock.
- **EXPECT-OR-REFUSE:** grid dims sanity-bounded `[1,4096]`; grid ptr, each row ptr, and each drawable
  `IsBadReadPtr`-gated; a bad cell is skipped and counted, never chased. Whole step under the SEH
  fault catcher (`g_rz_step = 8`). If the grid header is bad, logs `REFUSE grid re-show` and does
  nothing.

8a/8b (sprite re-register) and all prior fixes are retained. No on-disk patch.

## Outcomes, committed in advance

| observation | verdict |
|---|---|
| Log `[step 8c] grid re-show RxC: N occupied, N re-shown` AND after a resize **buildings, roads, terrain and zones all render** with no manual layer toggle | **PASS — defects A and B fixed, mod complete end-to-end** |
| 8c runs (occupied>0, re-shown>0) but buildings/roads still missing until a layer toggle | **FAIL** — the per-cell show is not sufficient / not the same as the toggle path; report counts, do not iterate blind |
| Log `REFUSE grid re-show` (bad grid header) | **VOID** — the cell-grid offsets are wrong for this build/state; re-derive before retrying |
| Many `bad` cells (badcell large vs occupied) | **diagnostic** — cell layout offset is off; the re-show did little. Report the counts |
| `FAULT CAUGHT` at step 8 (code + MODULE+RVA) | **FAIL** — `FUN_10006c67`/`FUN_10006efc` faulted on a cell; the log localises it |
| Terrain/zones now fill the new area immediately (no scroll needed) but buildings/roads still need a toggle | **PARTIAL** — defect A fixed, B not; narrows B to a building/road-specific path |
| Crash / hang | **FAIL** — restore, report the last `RZ` line and the 8c counts |

**Decisive:** after a resize, with NO manual layer toggle, do buildings and roads render.

## Falsifiability

If 8c reports a healthy `occupied`/`re-shown` count and buildings/roads are STILL gone without a toggle,
then re-issuing `+0x34` per cell is not equivalent to the in-game toggle — the toggle does something
extra (a cross-DLL step, or a different draw target), and the surgical extract is insufficient. That is
a real result; next step would be Option B (drive a real transition via `FUN_10006a55`) or reading the
cross-DLL data-view handler, not iterating on 8c.

## Protocol

Harness claimed `handtest`. Owner launches (`resize_launch.exe -- <city>`, `SC3RESIZE_LOG` set, no
`-kill`), resizes by hand, reports what renders **before** touching any layer control. Prior log
archived `re/harness/sc3resize_handtest.objrereg.log`. Install (`SIMSPR f5b9f1d9`, `GZGraphicD
acefadf0`) verified before/after; no on-disk change.

## STATUS

Built + string-verified (`step 8c] grid re-show`, `REFUSE grid re-show` present; 8a/8b + all prior
fixes retained; PE32; install intact). Pre-registered. Awaiting the owner hand-test.
