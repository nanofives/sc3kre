# RESULTS — side panel missing when maximized

Run 2026-09-07. Pre-registration: `PRE.md` (written before the build). Build: `sc3resize.dll`
190,464 B. City `Cities\Europolis.sc3`, recipe `SC3RESIZE_CLUSTER=1`, arms `SC3RESIZE_KIDFIX=1`
(treatment, `treat/run.log`) and `=0` (control, `ctrl/run.log`). Screenshots via
`re/tools/sc3io_cli.py grab`, which refuses to save an untrustworthy frame.

## Verdict

**The child double-translate was real and is fixed. It is NOT the cause of the missing side
panel.** Three of four pre-registered predictions PASS; prediction 4, the owner-facing observable,
**FAILS** — and that failure is informative, because it was pre-committed as meaning "the child
rects were never the reason the panel does not paint".

## What is proven

**1. The double-translate is arithmetic, and the fix removes it.** Clean A/B, same build, one flag,
same click sequence, same maximize to virtual client 2048x1081 (`dx,dy = 1248,481`):

| window | native paint (parent-rel) | control `KIDFIX=0` window | treatment `KIDFIX=1` window | client bound |
|---|---|---|---|---|
| `[3]` child of minimap | `[138 72 147 87]` | `[3274 1470 3283 1485]` ❌ | `[2026 989 2035 1004]` ✅ | 2048x1081 |
| `[4]`–`[9]` children of side panel | `[0 0 36 442]` | `[3200 962 3236 1404]` ❌ | `[1952 481 1988 923]` ✅ | 2048x1081 |

Control values are the parent's **new** origin plus the already-translated rect — the delta applied
twice. Treatment values are the parent's new origin plus the **unmodified** parent-relative rect,
which is the native relationship preserved. `ctrl/run.log:125820`, `treat/run.log:144096`.

**2. The root/child classifier is correct on all 10 windows.** `WINCAP>` at native
(`treat/run.log:4087-130206`): `0x0EE6A250`, `0x0D36D050`, `0x0D36C420` → `root` (origin delta
`0,0`); `0x0DB06110` → `CHILD` (delta `640,436` = the minimap's origin); six windows at
`[0 0 36 442]` → `CHILD` (delta `704,0` = the side panel's origin). No root was misclassified: the
RCI indicator `0x0EE6A250` still moves to `[1847 1001 1888 1089]`, so the pre-registered
"some root stops moving" FAIL signature did not fire.

**3. No new fault.** No `VEH` line at the cluster step in either arm, so `IsBadReadPtr(w, 0xa0)`
does cover the `+0x14..0x20` read as assumed.

## What is refuted

**Prediction 4 FAILS: the panel is still absent when maximized.** With the children on-screen and
correct, the panel region `[1952 481 2048 923]` is pure city in the treatment arm — and the control
arm's same region is pure city too. So the panel's absence does not depend on where the children
are. `crop_ctrl_max_after_clicks.png` vs the treatment's `panel_crop.png`: both show no panel.

**Prediction 2 was mis-framed by me.** I predicted "no `<<< PAINT/WINDOW DIVERGE` line remains".
That was wrong as stated: for a child, `paint != window` is the *correct* state, because `+0x90` is
parent-relative. The substantive half of the prediction — every rect inside the live client —
passes. The label has been corrected in the code to print `(child: parent-relative, expected)`, so
only an unexplained mismatch on a **root** is flagged from now on.

## The real trigger, newly isolated

The symptom is **not** "resize misplaces the panel". It is a conjunction, and neither half alone
does it:

| sequence | panel after |
|---|---|
| load → maximize (no clicks) | **present**, buttons and all — in BOTH arms (`ctrl_max.png` and `kidfix_max.png`, panel region pixel-identical, 6076 unique colours each) |
| load → click the tool buttons at native, no resize | **present** (`crop_n1_after_clicks.png`; survived clicks at y=30,90,150,210,290,400,440,480) |
| load → click the tool buttons → **then** maximize | **GONE**, in both arms |
| … → then restore down | **still gone** — it does not recover |

So the panel is lost only once the six `[0 0 36 442]` side-panel page children have been registered
(which is what clicking a tool button does) **and** a resize then happens. That reframes the bug:
the geometry of those children is now correct and they still do not paint, so the next suspect is
the panel's **paint/surface path for an active tool page**, not its rect. This also explains why the
earlier session's before/after screenshots looked like a geometry bug — the broken shot came from a
session that had already clicked the buttons, the healthy one had not.

⚠️ **Trap for the next reader:** my first treatment shot showed the panel and the pre-fix shot did
not, which looked like proof the fix worked. It was a confound — the two runs had different window
populations (4 vs 11 registered painter windows). The control arm at matched population is what
settled it. Do not compare screenshots across runs without checking `WINCAP>` counts.

## Kept anyway

`SC3RESIZE_KIDFIX` ships **default 1**. The double-translate wrote rects up to `x=3274` on a
2048-wide client — an unconditional out-of-bounds geometry write with no upside — and removing it is
correct independently of the panel symptom. `=0` retains the old behaviour as the control arm.

## Next

The panel's paint path with an active tool page. Concretely: after clicks + maximize, the container
`[1]` is at the right rect and the six pages are at the right rect, yet nothing blits. Find what
`0x0D36CCA8`'s painter reads besides `+0x90` and `+0x14..0x20` — most likely a surface handle or a
per-page visibility/active index that the resize invalidates. `SC3RESIZE_SIDESPAN` and
`rz_side_fit_surface` are the untested levers already in the source.
