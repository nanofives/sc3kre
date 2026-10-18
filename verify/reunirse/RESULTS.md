# RESULTS: Reunirse keeps its position (child `reunirse`, 2026-10-12)

Pre-registration: `PRE.md` (dcd3e85). Branch `child/reunirse` from `child/hudfix`.
Evidence per arm: `<arm>/ab.json` (dialog rect, window object, both stored slots after every step), mod logs
`re/harness/inst_reunirse/resize_<arm>.log` (MAIN, gitignored), SetRect watcher logs `watch_<arm>.log` (same place).

**Verdict: PASS on positions, visual check PENDING.** The monitor was asleep for the whole session (taskbar clock
frozen at 13:04, then at 14:04), every grab was refused as not credible. No screenshot was looked at. Every position
below is the live `+0x14` rect read from the window tree, not a picture.

## Deviations from PRE.md (stated before scoring)

1. **The page switch is not always the same window object.** PRE assumed it was (first run: `0x11710058` both
   times). Arm A then showed `0x0FACB560` -> `0x0FACADE0`: the game frees the list page and builds the detail page
   in a new window, and the heap only sometimes hands back the same address. The per-object rule in PRE part 2 would
   miss most switches. Added before the B runs that count: detours on the two page BUILDERS
   (`SIMUI+0x4405`, `SIMUI+0x5602`, both `mov eax, imm32` prologues) to note which window is the current
   Reunirse page, and the poll keeps that page when the game put it exactly where the last page closed, at the same
   client size.
2. **Two pre-existing resize rules threw away a dragged position**, found in run B (first build): on a size change a
   dragged dialog was clamped (or left) and then recorded as "ours", so the DLGAREA follow-up poll re-centred it
   33 ms later (`[1350 959]` -> `[417 246]` -> `[160 95]` on restore to 800x600). Under DLGSTAY a dragged dialog now
   stays "dragged" through a resize.
3. **Right-dock false positive**, found in run B2: a detail page clamped flush to `x+w = 800` matched the terrain
   panel heuristic (`right edge == NAT_W`, `left >= 400`) on a later open while maximized and was docked to
   `[1296 312]`. Under DLGSTAY a Reunirse page is never right-docked.
4. Arm S ran on the fix build with `SC3RESIZE_DIALOGS=0 SC3RESIZE_DLGSTAY=0` (as pre-registered). The control A
   that counts is A2 on the FINAL build; A (first build) is kept as extra evidence.

## Results

| Arm | Build, flags | Size | Open | Dragged to P | After opening an advisor | Verdict |
|---|---|---|---|---|---|---|
| S stock ref | first fix build (pre-b6d6c14, every new path off by the flag) `DIALOGS=0 DLGSTAY=0` | 800x600 | [600 284] (stored) | [480 364] | **[600 284]** = detail slot | stock jumps, as predicted |
| A2 control | 5d83da6 `DLGSTAY=0` | 800x600 | [160 95] | [60 215] | **[160 95]** (centred) | jumps, reproduces the report |
| A2 control | same | 1680x979 | [600 284] | [450 484] | **[600 284]** (centred) | jumps |
| B3 fix | 5d83da6 defaults | 800x600 | [160 95] | [60 215] | **[60 215]**, close + reopen [60 215], 2nd advisor [60 215] | PASS |
| B3 fix | same | 1680x979 | [695 580] (kept from 800) | [736 483] | **[736 483]**, reopen [736 483], 2nd advisor [736 483] | PASS |
| K stock DLLs | 5d83da6 defaults, `Simcity_stock_reunirse` | 800x600 | [8 8] (stock) | [-92 128] | **[0 128]** (clamped on screen), reopen [0 128] | PASS (clamp) |
| K stock DLLs | same | 1680x979 | [600 284] | [736 483] | **[736 483]**, reopen, 2nd advisor same | PASS |

Every B3/K page switch and reopen logged `DLGSTAY> ... Reunirse page where the last one closed (dragged) - kept`, and
the window object changed on most of them (`0x11b20a58` -> `0x11b1fc48` -> `0x11b20d28` -> `0x11b204b8` at 800x600).

Size changes (B3):
- 800x600, list dragged to [490 100] (partly past the right edge), advisor -> [416 100 800 454] (clamped 74 px),
  maximize with it open -> stays [416 100], close + reopen maximized -> [416 100 799 454], advisor -> [416 100 800 454]
  (not docked: deviation 3 fixed).
- B2 (same code minus the dock fix): dragged far off-screen at 1680x979, restore to 800x600 -> clamped to
  [417 246 800 600] and stays (deviation 2 fixed), maximize with it open -> stays [416 246] for 8 s.
- Closed at one size and reopened at another: re-centred, as pre-registered. B2: closed at 800x600, maximized,
  reopened -> `DLG> ... -> [600 284 983 638] (client 1680x979)`. (In B3 the maximized first open [695 580] was
  kept because `reunirse_resize.py` had just closed it at [695 580] while maximized: same size, as designed.)

Reopen click: the first click on the Reunirse button right after the X close was sometimes not acted on (no builder
call in the watcher). Seen in B (2 of ~4) and in the control A2 (1 of 2), 0/8 in B2 and 0/6 in B3
(`reunirse_reopen.py`). Present with DLGSTAY off, so not caused by this change. Cause not established.

Faults: each log has exactly one `VEH FAULT`, `0xC0000096` at `SC3U.exe+0x84122`, 21-528 ms after start, before any
dialog exists, in every arm including S and A2. Not related.

## Still open
- Visual check: a screenshot of the detail page sitting where the list page was, at 800x600 and maximized. Pending
  until the display is awake.
- DPI: positions are game client coordinates, so the rule itself does not depend on DPI or monitor size. The owner's
  laptop was not tested.
