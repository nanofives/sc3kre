# RESULTS — U-069 downward resize (2026-08-29). ⭐ PASS. PRE git (u069_v2).
# Downward resize works; no fault; the frame shrinks correctly to the new extent.

Europolis, load zoom, gate + census + SEH on. **Three resizes fired, TWO of them DOWNWARD:**

| t | resize | direction | steps | fault | render-target census |
|---|---|---|---|---|---|
| 27.9s | client 800x600 vs RT **2048x1081** | ⬇ **DOWN** (auto-un-maximize) | 9/9 | none | 800x600, bbox 785x597, beyond=0 |
| 41.0s | 800x600 -> **1280x1024** | ⬆ up | 9/9 | none | 1280x1024, bbox 1207x686, beyond=6555 |
| 50.1s | **1280x1024 -> 800x600** | ⬇ **DOWN** (the scripted test) | 9/9 | none | **800x600, bbox r0..599 c0..799 (full), beyond-800x600=0** |

**Verdict: downward resize WORKS.** Both downward resizes (2048x1081->800x600 and 1280x1024->800x600)
completed all 9 steps with **zero faults**, `extent AFTER` = 800x600 with plausible cells, and the
render-target census shows the frame correctly at the smaller extent: **bounding box fills the full
800x600 and `beyond-800x600 = 0`** — i.e. the surfaces/extent shrank correctly and NO stale
large-size content is stranded. A clip or stale-large-buffer would show a 1280-wide bbox or content
beyond 800x600; it shows neither.

## Honest caveats (artifacts, not defects)
- **Low non-zero % (0.8% / 18.5%)** on some census reads: the camera had scrolled to a far corner
  (extent origin e.g. `-2625,1111` = mostly ocean/empty), so the *scene* was sparse at that moment.
  The structural discriminators (bbox = new extent, beyond=0, no fault) are what U-069 needs and they
  hold; the fill % is a camera-position artifact of when the census sampled.
- **`blit-dest iso+0x4ec: no readable backing`** on two census reads: the census fires 2 s after the
  resize and can catch the blit-dest between frames (its backing is transient, per the standing
  `sub+0xf0` note). The **render-target** census is the reliable witness and shows the correct shrink;
  the blit-dest transient is timing, not a shrink defect (the render target IS backed and full-extent).

## Status
`U-069` (downward resize) is **answered: it works**, with the OOB clamp fix (FIX A) in place — no
shrink-specific fault across two downward resizes. Combined with the upward census (`resize_census`),
the routine handles resize in **both directions** on a settled city.

## State
No fault, no orphan. Owner build verified `f5b9f1d9` / `acefadf0`. Mod patches nothing on disk. Lease +
claim released.
