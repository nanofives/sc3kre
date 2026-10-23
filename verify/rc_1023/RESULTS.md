# RESULTS: release candidate 2026-10-23 (branch rc/1023)

Branch `rc/1023` (worktree `Simcity_wt_rc`) = `main` 1b3cbee + `child/cityzoom` 38cf00e (merge fb99f9e) + the owner hand-test
fixes below (head 28f7537). Played from `Proyectos\Simcity_rc` (staged 2026-10-23 with `stage_lan_release.py`, 3,602 files).
NOT deployed to the LAN server.

⚠️ `Simcity_rc\manifest.json` is stale: `Apps\sc3resize.dll` (3F00868F78CB863B) and `Apps\sc3overscroll.dll` (67376B406F5BA9B6)
were replaced by hand during the hand test. Rebuild all 9 binaries from the rc/1023 head and re-stage before any deploy.

## Session smoke test (owner away, before the hand test)

Europolis, maximized 3840x1984, posted input, frames by FRAMEDUMP. Zoom x1 -> x2 -> x3 and back with the centre kept,
3 maximize/restore cycles, 120 s at speed 4 (4/4/2088 -> 7/28/2090, 58-60 fps), no VEH fault but the known benign
`0xC0000096 @ SC3U+0x84122`. Desktop grabs showed a stale menu picture while the game was not foreground: use FRAMEDUMP.

## Owner hand test, fixes made (all sc3resize unless noted; each has an off switch)

| # | owner report | cause (measured) | fix | evidence |
|---:|---|---|---|---|
| 1 | Reunirse drawn over Preferencias | DLGSCALE drew dialogs in child-list order, which is front-first | draw back to front, cost label last | log order: Preferencias (opened later) listed first |
| 2 | intro logo: menu picture outside 4:3 | MENUSCALE treated every pre-city 800x600 frame as the menu | margins black unless >= 1/10 of the frame is menu background | log: 0 bg px at 1.1 s (black), 203,934 at 71 s (picture) |
| 3 | which UI elements still need rescaling? | | HSCENSUS: one log line per distinct UI window and what HUD scale did (`NOT SCALED` / `KEPT NATIVE`) | 40 entries so far, none native; the census list is still to be read after a full UI tour |
| 4 | right-drag makes the cursor smaller | stock pan arrows: 15x8 art in a 32x32 cursor, hotspot at the tip | PANCURSOR v2: while the right button is held, each arrow is rebuilt once, art 3/4 of the canvas, centred | real-mouse drags (mouse_event + GetCursorInfo), road tool and no tool, windowed and maximized: every hold showed the rebuilt arrow, hotspot (32,32); offline render of all 8 arrows |
| 5 | still marker at the press point offset up-left at zoom 6/7, small everywhere | 32x32 `anchor point cursor.BMP` Blt (GZGraphicD+0x18c89) into the frame at the anchor in VIEW px | ANCHORMARK: re-aimed at anchor x f and drawn at the cursor's bitmap size (64), in the outer Blt hook so DEFER replays it | mid-drag frame dumps at x1 and x3: marker centred on the press point, 0 marker px at the old x3 spot |
| 6 | zoom while dragging: arrow gone until the next move, camera stops at zoom 6/7 | stock zoom ends the drag, a CITYZOOM step clears its velocity; both rebuilt only on the next move | DRAGKICK: one WM_MOUSEMOVE (in view px) posted after the zoom while the button is held | owner log: every zoom during a drag posted the move |
| 7 | much faster at the closest levels | drag velocity capped at 80 VIEW px per tick = f x on screen | DRAGCAP: clamp to 80 / f after the drag move (city view vt +0x40) | first build did not install: sc3overscroll ARROWS held the slot; both now chain it with an atomic swap |
| 8 | "+" at max zoom while dragging: camera shoots off | after the stock zoom the game re-read the pointer through GZWIND FUN_10020260 (GetCursorPos + ScreenToClient, unmapped): view mouse (2034,992) = client point, velocity 26.7, 26.7 | CURSORMAP: that helper maps city points by f | probe: velocity 9,0 before and after the '+' |
| 9 | buildings cut by horizontal lines, closest zoom only | x3 view 1280x662; 662 = 82 x 8 + 6, an undrawn 6-row band carried through the view by the scroll copy | ALIGN8: CITYZOOM view rounded up to a multiple of 8 (1280x664) | 30 scroll frames at x3: moving band in 30/30 before, 0/30 after |

Switches: `SC3RESIZE_PANCURSOR`, `_ANCHORMARK`, `_DRAGKICK`, `_DRAGCAP`, `_CURSORMAP`, `_HSCENSUS` (=0 off).

## Still open for the owner

1. Zoom while dragging, after fixes 6-9: arrow stays, camera keeps moving, top speed equal at every level, no flight on
   '+' at max. Speed below the cap was not changed; if x3 still feels faster the next suspect is frame rate (the drag
   moves a fixed step per frame and x3 presents at ~60 fps against fewer at x1).
2. CURSORMAP side effects: hover and tool previews at x2 / x3 now read view pixels through the same helper. Expected to
   be right, not checked one by one.
3. Census: open every window once (budget, graphs, maps, news, ordinances, neighbours, query, save/load, petitioners),
   then read `HSCENSUS>` lines marked NOT SCALED / KEPT NATIVE.
4. Not touched this round: undo (Ctrl+Z, Ctrl release, minimap buttons), fullscreen (Alt+Enter, size remembered),
   save/load while zoomed, terrain editor, a second monitor, `sc3simrun` soak at the top speed, the 1024 city.
5. Package art changed after the 2026-10-21 LAN republish is not in `Simcity_stock_avint` (the stage source).
6. The PANCURSOR per-call diagnostics were removed in v2; HSCENSUS stays on by default (one line per distinct window).

## Before a release

Merge rc/1023 into main, rebuild the 9 binaries, re-stage, smoke test the package, then deploy (LAN) or publish (GitHub,
notes per VOICE.md).
