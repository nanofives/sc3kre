# RESULTS — edge-scroll band (`SC3RESIZE_EDGEFIX`), arm T only

Run 2026-10-05. Pre-registration `PRE.md`, committed in `03ca3c3` before the run. Build
`sc3resize.dll` 192,512 B. `Cities\Europolis.sc3`, `SC3RESIZE_CLUSTER=1`, `edgefix=1` read back from
`FLAGS>` with the variable unset. Files beside this one: `T/run.log`, `T/probe.txt`,
`T/edge_probe.json`, `T/poke.txt`, `T/enable.txt`.

**Deviation:** the Parsec virtual display would not attach (`ChangeDisplaySettingsExW` returned -1,
twice). The run used the real monitor `DISPLAY2`, 1920x1080 at 100% scaling, the same geometry.
Window moved there with `SWP_NOACTIVATE`. Client 800x600 at native, 1920x1009 maximized.

## Verdict: VOID, by two pre-registered VOID conditions. Arm C was not run.

1. `en=0` at every probe point, at native size too.
2. Zero hook calls at the two new-band points.

Both conditions are now explained, and each changes what the next step is. Rows 1 and 5 (band
geometry) were measured and match the prediction.

## What passed

**Row 1, bands at maximized:** `EDGE> bands rebuilt from bounds [0 0 1824 953]: inner [64 48 1760
905] L [0 0 64 953] T [0 0 1824 48] R [1760 0 1824 953] B [0 905 1824 953]`. That is the formula with
W = 704 + 1120 and H = 544 + 409.

**Row 5, after restore to 800x600:** `bands rebuilt from bounds [0 0 704 544]: inner [64 48 640 496]`,
which is native exactly. The old write never shrank the bounds.

The cache saw the engine's native bounds `[0 0 704 544]` on first sight, as predicted.

## Finding 1 — map input beyond the native 800x600 is dead in the current build (causal)

Posted moves at (1792,336) and (480,929) never reached the band test. Every point inside 800x600
did. Live read at 1920x1009: the city view's hit rect `+0x14` = `[0 0 800 600]` and its local rect
`+0x80` = `[0 0 800 600]`, although the mod logged writing the hit rect to `[0 0 1920 1009]`.

**Causal test** (`T/poke.txt`): with the hit rect at 800x600, the band test was called 0 times for
moves at (1792,336) and (480,929), and 3 times at (480,336). After writing `+0x1c/+0x20` = 1920/1009
in-process, it was called 3 times at all three points.

**Cause, from the source:** the cascade added on 2026-09-02 (`37989b5`, after the input fixes in
`7a67b9f`) runs the root's `vt+0x14c` after `rz_input_geometry`. That rebuilds every derived `+0x14`
rect from the local `+0x80` rect `[CONFIRMED @ SIMUI 0x1006c61b]`, and the mod widens only the
derived one. So the cascade puts the city view back to 800x600. This is a regression of the
owner-verified map fix, and it affects clicks, zoning and right-drag pan beyond 800x600, not only
edge scroll. It fits the 2026-09-07 "view does not pan" result: those drags started at (900,500).

**Fix, not yet built:** set the city view's LOCAL rect `+0x80` to the client size as well, so the
cascade derives the right hit rect. Needs its own PRE.

## Finding 2 — `+0x177` is "scroll in progress", not an edge-scroll enable

`FUN_10042cd3` (outer `vt+0x38`) is its only setter. One spoofed arrow tap (`T/enable.txt`): setter
calls `1,1,1,1,0`, and the byte read 0 before and after. Every SIMSPR caller of `vt+0x38(1)` is
keyboard-driven: `FUN_1004979a`, `FUN_1004985a`, and `FUN_10043daf`, which polls the arrow keys while
a scroll runs. The band test `FUN_10043a38` returns early while `+0x177 == 0`.

**So, from SIMSPR alone, the mouse bands do not START a scroll.** They only set direction flags
while one is already running. `[UNCERTAIN]` whether another module calls outer `vt+0x38(1)` from the
cursor position. Only SIMSPR was searched. The CAMERA_MODDING `edge_margin` C3 was a geometry
observation and never saw a scroll triggered by the mouse.

## What this means for the owner's request

"Match the edge-scroll band to the new window bounds" is done at the geometry level (rows 1 and 5).
Whether it does anything a player can feel depends on a question the owner can answer in seconds
from a native, unmodded game: **does resting the mouse at the screen edge scroll the map with no
key pressed?** If no, the bands are a keyboard-scroll detail and the feature does not exist to
match. If yes, the starter is outside SIMSPR and is the next thing to find.

## Next

1. Owner question above.
2. PRE + build for the city view local-rect fix (Finding 1). It restores map input beyond 800x600
   and is a precondition for any edge test at large sizes.
3. Arm C only if the bands turn out to be player-visible.
