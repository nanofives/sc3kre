# PRE-REGISTRATION — resizable-frame hand-test on the owner's REAL display (committed before hand-off)

Owner: resizeship session. Date 2026-08-26. The owner will drag/maximize the window on a real foreground
display and report what they see (the D-004 observation the headless harness cannot make). No harness run,
no lease — the owner launches the patched game normally.

## What this build IS and IS NOT
- **IS:** the **style flip** — WS_THICKFRAME|WS_MAXIMIZEBOX added to the "Gonzo" window (GZGraphicD, 3 bytes),
  so the frame can be dragged/maximized. Plus the owner's four-recipe SIMSPR (`scroll_speed=8 +
  drag_divisor=4 + drag_deadzone=2 + resize_rectfix`).
- **IS NOT:** the **bridge** (re-render on resize). Established this session: the resize routine **cannot ship
  as a pure DLL** — SIMSPR has no global for the live iso-view/bridge pointers (the harness captures them via
  hooks; `sc3probe.c:8234,8251`), and the render lever `FUN_10018cdf` needs the bridge. So a real drag will
  NOT re-render the iso view in this build; making it re-render is a probe-driven follow-up.
- `resize_rectfix` is **inert on a real drag** here: it hooks Init `FUN_10005b42`, which a real WM_SIZE does
  not call (WM_SIZE → GZGraphicD `vt+0x30`, never SIMSPR Init). It is in the build per the owner's
  standing-build request, harmless.

## The patches (independently `--diff`-verified, length-preserving)
- GZGraphicD `resizable_frame`: **3 bytes** — `0x10017ca4` `1b→3b`, `0x10018223` `01→05`, `0x10018570`
  `c8→cd`. sha `8999940929d032468e21ef95cbf6a80b1bc763f16a39b98b152f5d9c4c709c2d`, 163840 b.
- SIMSPR four-recipe: **45 bytes / 13 runs** (5 scroll + 2 drag + 2 dead-zone + 36 resize_rectfix). sha
  `f5b9f1d9864798d6aa528c82149bb5470ebeb3aee63eae90d623908af31510eb`, 512000 b.

## Outcomes, committed in advance (what the owner should look for)
The primary questions this build answers on a real display: **(1) does the frame drag and STAY (trap 2)?**
and **(2) what does a DirectDraw-windowed client resize do to the view with no bridge?**

| observation | meaning |
|---|---|
| **Frame drags and stays put** (does not snap back) | trap-2 analysis holds: the SetWindowPos snap-back (`FUN_1001854a`) is not on the WM_SIZE path. The flip works. |
| **Frame snaps back / re-centres after drag** | trap 2 WRONG — a mode-apply or per-frame refit is defeating the flip; report, the bridge needs a lock suppression too. |
| **Maximize button present and maximizes** | WS_MAXIMIZEBOX took. |
| iso view **stretched** to fill the new frame | the DirectDraw blit scales — the render target is unchanged; a bridge would resize it. |
| iso view **clipped / black margins** (city stays top-left, new area black) | the render target is NOT resized and the blit is 1:1 — the expected no-bridge outcome; the bridge (render-target resize + `FUN_10018cdf` refill) is the fix. |
| iso viewport **fully black** after resize | the windowed blit broke on the size change — report; a device-surface question (D-004). |
| **crash on drag/resize** | the DirectDraw windowed path faulted on the client-size change — a real-display finding for D-004; restore and report the moment. |
| **HUD not composited / mis-placed** | EXPECTED, not a regression — the separate item-2 reflow (`FUN_100270e5`, no branch above width 800). |

## What a negative is NOT — the next step is known
If the view stretches/clips/blacks (no bridge, as expected), that is **not a dead end**: the render-target
resize + refill routine is specified and its rendering is de-risked by the harness's own resize path. And if
surfaces turn out to need re-creating, the hook is device interface slot **`+0x50`** (the toggle's recreate
path, already located), not SetMode. The bridge would be delivered probe-driven (the harness captures the
iso/bridge pointers a pure DLL cannot).

## Provenance / restore
Both modules staged into the live install (the owner's authorised change). **One-line restore to shipped is
in the report and the BOARD standing rule.** No measurement taken by me; the owner is the instrument.

## STATUS
Both patches BUILT + `--diff`-verified. Pre-registered. Staged into the live install for the hand-test.
