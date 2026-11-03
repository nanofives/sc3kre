# uipolish RESULTS (2026-11-03)

## 1. Pause music on loss of focus (block MUSICFOCUS, `SC3RESIZE_MUSICFOCUS=0` = off), sc3resize.c `rz_musicfocus`
- AUDIO.DLL AudioManager = `*(AUDIO+0x26f00)` (DAT_10026f00): `+0x28` music volume, `+0x24` sound on/off. Message 0x3eb stores `+0x28`
  and calls vtable slot `+0x6c` of the service `FUN_10019c03()` (AUDIO 0x10019c03) with it `[CONFIRMED @ 0x10008d77:189-195]`.
- WM_ACTIVATEAPP false (and WM_SIZE minimized) calls that slot with 0. Active again (and restored while foreground) calls it with `+0x28`.
  `+0x28` is never written, so a player who set music to 0 stays silent and nothing is started. Sound effects are not touched (they keep playing).
- Tested with posted WM_ACTIVATEAPP 0,1,0,0,1: log `MUSICFOCUS> inactive: music volume -> 0 (player's setting 1024 ...)` then `active: ... -> 1024`,
  the repeated 0 is ignored, no fault. Audio itself cannot be captured: owner check by ear.
## 2. Vida util footer band (`SC3RESIZE_RSSTRIP=0` = off), sc3resize_restore.c `rs_flat`
- One flat filled shape window (class 0x4303E5B6 / 0xE303E5AE, style 0x31 through `vt_rect`; colour = colour service vt+0x84 (120,144,248), the box
  blue measured on the shot) spans the footer row edge to edge (8..w-8, 33 tall), created before every footer button so it sits behind them. Disabled.
- No button/pill boxes, so no cap marks and one shade. Earlier tries (6 px button boxes, full-width box) dropped.
- Shots (owner_shots): 01 page 1, 02 page 3, 04 footer zoom, all 800x600.
- No new UI strings.
