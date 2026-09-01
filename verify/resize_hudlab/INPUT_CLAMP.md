# INPUT COORDINATE MAPPING — the clamp, located statically (2026-09-01, no lease)

Owner: the clustered HUD is not clickable. Found without a lease, by following the WndProc.

## Every mouse coordinate is clamped before the UI sees it

`FUN_10017e2f` is the window proc; all mouse messages (`0x200` MOUSEMOVE, `0x201`/`0x204` button
down, `0x202`/`0x205` up, `0x20a` wheel) funnel into **`FUN_100178a6`**, which builds the event
struct from `lParam`. At `LAB_10017aaa`:

```c
if ((int)*puVar7 < 0) { *puVar7 = 0; }                    /* x < 0  -> 0     */
else {
    param_1 = (**(code **)(*local_8 + 0x68))();           /* vt+0x68 = WIDTH */
    if ((int)param_1 <= (int)*puVar7)
        *puVar7 = (**(code **)(*piVar1 + 0x68))() - 1;    /* x >= w -> w-1   */
}
/* identical for y with vt+0x6c = HEIGHT */
```

`[CONFIRMED @ GZGraphicD 0x100178a6]`

**Every click is clamped into `[0, width-1] x [0, height-1]`.** A click outside that box does not
miss — it is *moved* to the edge and delivered there, which is why a relocated HUD is unreachable
rather than merely unresponsive.

## The bound is a field this mod already writes

From the board's vtable read of the window class:

| slot | body | meaning |
|---|---|---|
| `vt+0x68` | `mov eax,[ecx+0x40]; sub eax,[ecx+0x38]; ret` | **WIDTH** |
| `vt+0x6c` | `mov eax,[ecx+0x44]; sub eax,[ecx+0x3c]; ret` | **HEIGHT** |

Both read the **stored RECT at `win+0x38..0x44`** — exactly what `rz_set_stored_rect` (the D-004
fix) writes on `WM_SIZE`, on the same object, via the same `GZGraphicD+0x6cdb8` global.

## Two possibilities, distinguishable, neither guessed

1. **The stored rect is STALE at click time** — clamp is 800x600 and the corner HUD is unreachable
   by construction. The fix is then small: keep that rect current.
2. **The stored rect is correct** (2048x1081), the clamp passes clicks through, and the blocker is
   further up in SIMUI's hit-testing.

`[UNCERTAIN]` which. The mod logs `STOREDRECT rect AFTER {0,0,2048,1081}` on resize, which *suggests*
(2) — but **nothing has checked the value at click time**, and the game's own `WM_SIZE` handler
(`vt+0x30` -> `FUN_100185f5`) also touches this area.

## The probe (built, `SC3RESIZE_INPUT=1`)

On each button-down, log the raw click coordinates and the **live** clamp bounds read from
`win+0x38..0x44`, flagging any click outside them. One line per click, read-only, no dispatch
through anything. It separates (1) from (2) outright.

## Why this matters beyond the HUD

The board has carried *"navigation works only in the top-left 800x600 (input picking reads a
different size source than the blit) — not investigated"* since the viewport work. **This is that
defect**, and it is now located to a specific instruction sequence rather than a symptom. Whatever
the probe says, the clamp itself is no longer unknown.
