# PRE-REGISTRATION — U-069 downward resize (committed BEFORE the lease)

**Question.** Every resize so far was UPWARD (grew the view). Does a DOWNWARD resize (shrink) work, or
does the routine only handle growth? `U-069`.

**Method.** Europolis, `-windowed -fix16`, load zoom, gate + SEH catcher + census all on. Resize UP to
1280x1024 (settle), then **DOWN to 800x600** — the actual U-069 test. Same build as the census run.

| # | reading | verdict |
|---|---|---|
| 1 | DOWN resize: all 9 steps, no fault, census shows a full 800x600 frame (bbox ~800x600, high non-zero, no content stranded beyond 800x600) | ⭐ **PASS** — downward resize works |
| 2 | `FAULT CAUGHT ... STEP n` on the down resize | **FAIL** — shrink hits a fault the grow path did not; the SEH catcher names the step+address |
| 3 | steps complete but census shows content still spanning 1280x1024 (stale, not shrunk) or garbage | **FAIL** — surfaces/extent not shrunk correctly; report bbox |
| 4 | the DOWN resize never triggers (poll sees no mismatch) | inconclusive — the shrink did not reach the routine; report client sizes |

**Pre-registered reads:** the `extent AFTER` for the down step (should be 800x600, cell plausible), the
census bbox (should be ~800x600, NOT 1280 and NOT beyond), and any DEFER/FAULT lines.

⚠️ Shrinking frees nothing of ours (the routine recreates surfaces at the new size via the same
FUN_10009efb path); the risk is a size-down assumption in the engine's own builders/present. The census
"beyond 800x600" counter now reads the OPPOSITE way: after a shrink to 800x600 it SHOULD be ~0 (no
content beyond the new smaller extent). A large beyond-count after the shrink = stale large surface.
