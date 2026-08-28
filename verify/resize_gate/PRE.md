# PRE-REGISTRATION — load-readiness gate witness (committed BEFORE the lease)

**Change.** The poll now defers a resize until BOTH (a) >= `g_ready_ms` (default 3000) ms since bridge
capture AND (b) the render target has a real backing (`*(R+0x44)+0xf0` nonzero = one frame drawn),
then proceeds on a later poll. Cheap preventive hygiene against resizing mid-load.

**Test.** Fire the external resize EARLY (~t+5s, during load), gate at default 3000ms, `MINZOOM=0`.
This is exactly run-2's early scenario, now with the gate.

| # | reading | verdict |
|---|---|---|
| 1 | `RZ DEFER` logged, THEN later `size change` + all 9 steps, no fault | ⭐ **PASS** — the gate defers during load and the resize still lands once ready |
| 2 | resize fires immediately with no DEFER (already past 3000ms / backing present) | inconclusive on the defer path — report timing; the gate is at least not blocking |
| 3 | `DEFER` logged but the resize NEVER lands | **FAIL** — the gate is too strict / the retry path is broken |
| 4 | crash / fault | **FAIL** — SEH catcher (still in this build) names the step |

**Pre-registered read:** the DEFER reason (time vs backing) and the delay between first DEFER and the
eventual `size change`.
