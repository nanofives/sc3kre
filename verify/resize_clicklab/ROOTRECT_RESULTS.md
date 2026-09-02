# ROOTRECT_RESULTS.md — **T-PASS.** Two integers unclamp the hover label (2026-09-01)

Scored against `ROOTRECT_PRE.md` (committed `05b9359`, before the write). Live write into the owner's
running session: root `0x5a94a8` `+0x88 = 2048`, `+0x8c = 1081`. Nothing else written.
Raw: `tooltip_fixed.json`.

| cursor (client) | label rect, after |
|---|---|
| (1768, 1065) | `[1736 1036 1787 1052]` |
| (1808, 1073) | `[1791 1018 1839 1034]` |
| (2016, 833) | `[1898 816 1983 832]` |
| (2004, 958) | `[1919 932 2000 948]` |
| (740, 596) | `[641 579 772 595]` |

**Right edge reached 2000** — it was `798` in all 51 pre-write samples. **Top reached 1036** — it was
capped at `582`. The label also still tracks correctly in the old top-left region, so the old
behaviour was not traded for the new one.

## Why one run settled it

Three independent lines agreed *before* the write:

1. **Static.** `FUN_00443331` clamps to `vt+0xa0()` / `vt+0xa4()` on the root window, and there is
   **no 800 / 600 / 798 / 598 immediate anywhere in the function** — the only immediates in the clamp
   are `2` and `-2` `[CONFIRMED @ 0x00443331, 0x004435ec..0x0044364b]`. The bound is data, not code.
   Those two slots are `FUN_00441d3e` and `FUN_00441d45`, which return `*(root+0x88)` and
   `*(root+0x8c)` `[CONFIRMED @ 0x00441d3e, 0x00441d45]`.
2. **Live read.** Root `0x5a94a8` held `rect+0x14 = [0 0 2048 1081]` against
   `ext+0x80 = [0 0 800 600]`.
3. **Our own mod's source.** `rz_fix_hud_parents` widens `+0x14..+0x20` only and returns at the root
   by design — the comment says `"reached the root - leave it alone"` — so `+0x88/+0x8c` had never
   been written by anything.

`798 = 800-2` and `582 = 600-2-16` (16 = the label height) follow from (1) applied to (2)
arithmetically. That is why the measurement was predicted rather than explained afterwards.

## Still open

- **`T-SIDE` risk is unretired.** Other readers of `root+0x88/+0x8c` were never enumerated. None
  misbehaved in the observed session, but nothing systematic looked for them.
- **The fix is not in the mod.** It exists only as a Frida write into one live process
  (`re/tools/frida_rootrect.py`). Building it in means writing the two fields next to the existing
  PARENT fix in `sc3resize.c` and rebuilding, which needs the game closed — the DLL is loaded in the
  running process, so the link would fail `LNK1104`.
- The `winMgr` path in `frida_rootrect.py` reads `+0x50` and returns garbage; the correct chain is
  `sink+0x38`, which the tooltip object's `+0x04` confirms (it is the sink, `0x590358`, the same
  pointer the mod logs as the event sink). Cosmetic bug in the tool, not in the finding.
