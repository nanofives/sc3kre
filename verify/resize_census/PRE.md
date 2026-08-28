# PRE-REGISTRATION — in-mod pixel census, settle on-screen correctness (before the lease)

**Question.** Does the resized frame actually FILL the window, or is it clipped to the old 800x600
top-left? The `PrintWindow` screenshot was `D-004`-ambiguous; this reads the engine's own surfaces.

**Instrument.** After the resize, census (RAW, no vf1c) BOTH the render target `iso+0x74` (rasterization)
and the blit-dest `iso+0x4ec` (composite): non-zero %, content bbox, and **non-zero count in the area
beyond 800x600** — the discriminator between full and clipped.

**Method.** Europolis (dense, ~2M pop fills the screen), `-windowed -fix16`, **load zoom (MINZOOM=0)**,
gate default (fires after load), resize to 2048x1152 at t+42s.

| # | reading | verdict |
|---|---|---|
| 1 | both surfaces: content **beyond 800x600 > 0**, bbox extends toward 2048x1152 | ⭐ **NOT clipped** — the frame fills the resized window |
| 2 | render target fills but blit-dest does NOT (beyond=0) | rasterization works, the **composite is clipped** — the present path still needs work |
| 3 | both clipped (beyond=0, bbox ~800x600) | the routine renders old-extent only — a real clip, reopen |
| 4 | a surface has no readable backing | report; census inconclusive for it |

⚠️ At load zoom on a 2M-pop city the scene SHOULD extend well past 800x600, so beyond=0 would be
meaningful (clip), not just "small scene". Still: `beyond>0` is the positive signal; a low total-% at
min zoom would be ambiguous, which is why this runs at load zoom, not min.
