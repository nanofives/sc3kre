# INPUT PROBE RESULT (run 36) — the clamp is INNOCENT. Blocker is SIMUI hit-testing.

## The measurement

62 clicks logged. **Zero flagged as outside the clamp.** The stored rect read correctly at click
time and tracked every resize:

```
STOREDRECT rect AFTER {0,0,2048,1081}
INPUT> click raw=(1342,675) clamp bounds=2048x1081 (stored rect [0 0 2048 1081])
STOREDRECT rect AFTER {0,0,1920,1009}
INPUT> click raw=(1096,641) clamp bounds=1920x1009 (stored rect [0 0 1920 1009])
```

## ⭐ And the clicks were ON TARGET, which is what makes this decisive

At 1920x1009 cluster mode puts the bar at **`[1120 953 1719 1009]`**. From the log:

```
(1251,970)  (1604,979)  (1628,974)  (1609,972)  (1622,963)  (1703,968)
```

**All six are inside that rectangle.** So the owner was clicking the relocated bar, the coordinates
arrived **unclamped and correct**, and the UI still did not respond.

Without the position check this would have been a weak result - "no clicks were flagged" is
consistent with "the owner never clicked the HUD". Comparing the click coordinates against the
computed bar rect is what turns it into evidence.

## Verdict: possibility (2), confirmed

`INPUT_CLAMP.md` set out two options. **The stored rect is correct and the clamp passes clicks
through untouched.** The mouse-coordinate path is NOT the blocker, and the D-004 fix already keeps
that rect current.

**The blocker is further up, in SIMUI's hit-testing** - whatever decides which window owns a point
is still using native geometry.

## The next target, now concrete

`FUN_10017e2f` dispatches the finished event with:

```c
(**(code **)(**(int **)((int)this + 0x30) + 100))(&local_14);   /* 100 = 0x64 */
```

So the UI event system is entered through **the object at `window+0x30`, vtable slot `+0x64`**.
That is the door the hit-test lives behind.

The board has carried *"the real hit-test dispatcher was not located `[UNCERTAIN]`"* since the HUD
reflow work. It is now reachable: read `window+0x30`'s class, resolve `vt+0x64`, and follow it to
the point-in-window test.

## What this changes about the standing board note

The board says *"input picking reads a different size source than the blit"*. **That framing is now
wrong.** The coordinate path reads the SAME source as the blit (the stored rect, `win+0x38..0x44`)
and is correct. The divergence is not in the coordinates - it is in whatever compares them against
window geometry.
