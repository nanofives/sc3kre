# The game's options dialog ("Preferencias") and the HUD scale option added to it (task hudopt, 2026-10-11)

Owner request 2026-10-11: pick the HUD scale inside the game's own options dialog instead of an env var.
Choices Off / Fit / 125% / 150% / 200%, crisp by default with a separate Smooth switch, default Off.

Builds on `re/analysis/PREFS_UI.md` (2026-08-20), which decoded this dialog's widget vocabulary and added a
camera-speed slider to it from the probe. Everything below about the dialog is re-read from the decompilation
for this task. Evidence images: `verify/hudopt/` (MAIN, gitignored).

## 1. Which dialog

There is ONE options dialog and both entry points open it:

| entry | what was seen |
|---|---|
| In a city: last side-panel button (sliders + disk) -> flyout -> first item (sliders icon) | "Preferencias", 480x472 (`verify/hudopt/02_prefs.png`) |
| Main menu: "Preferencias" | the same dialog, same layout (`40_menu_prefs_hudopt0.png`, `41_menu_prefs.png`) |

The controls added by the mod show up in both (log line `HUDOPT> Preferences ...` from each).

## 2. How it is built: code, not data

| fact | value |
|---|---|
| builder | SIMUI `FUN_100564d9`, called from the controller's message handler `FUN_10055e07` on message `0xa2bf8ace` `[CONFIRMED @ SIMUI 0x10055e07]` |
| size | `vt+0xc0(0x1e0, 0x1d8)` = 480x472, then centred on the parent `[CONFIRMED @ SIMUI 0x100564d9]` |
| title | resource string `0x14e` of group `0x029541f4` via `FUN_1008ebbd` / `FUN_1008ebf9`, set with `vt+0x10c` |
| child ids | `0x02F95AD6..0x02F95B11` (`0x02F95B20..0x02F95B4F` have no hit in any module's decomp export) |
| frames | `FUN_10058c80`; "Opciones generales" frame `0x02F95ADB` at local `(6, 346)`, 468x76 |
| labels | `FUN_1005844a` (font `0xf`, colour `(0x79, 0x7d, 0xb5)`) |
| radio groups | `FUN_10059ccf(id, rect, &out)`: factory `+0x48` CreateOptionGroup, then `+0x38` AddOption(id, str, 0, 0, 0) per option, `+0x34` Select(id), `vt+0xc` window, `+0xcc` SetXY, parent `+0x34` AddChild |
| checkboxes | `FUN_10058d67`: factory `+0x3c`(id, str, 0, 0, 0), `+0x34` SetState, `+0x74(3,1,2,2)`, `+0x60` font, `+0x64` colours, `+0x1c` window |
| sliders | `FUN_10058e75`, factory `+0x50` (PREFS_UI.md) |
| widget factory | SIMUI `FUN_10085065` |

There is no dialog layout record in the IXF archives (PREFS_UI.md, section 1), so a control can only be added
by calling the factory at runtime. The mod does that. No game file on disk is touched.

### Radio group layout (GZWIND)

Options stack top to bottom and wrap to a new column when the next one would pass the group's height
`[CONFIRMED @ GZWIND 0x1000337d]`. Column pitch is the widest option so far (a running max, not per column).
The group's size limits are min = content extent, max = `0xffff` `[CONFIRMED @ GZWIND 0x1000318d, 0x10002a4a]`.
Measured: after the five AddOption calls the group window was 170 wide while its third column ended at 185, so
the tail of the last option took no clicks (`19c.png`). A SetRect after AddChild restores the full width
(`21c.png`, the same click now selects 200%).

## 3. OK and Cancel

Every close goes through `FUN_100562b1(this, win, id)` `[CONFIRMED @ SIMUI 0x10055e07, 0x10058f14]`:

| how | id | applies the radio groups? |
|---|---|---|
| OK button (`0x02F95AD8`) | `0x02F95AD8` | yes, `FUN_100593ac` runs first |
| Enter key (msg 5, key `0xd`) | `0x02F95AD8` | no, `FUN_100593ac` is not called on this path |
| Esc key (key `0x1b`) | `0x02F95AD6` | no, and audio settings are reverted to the stored ones |
| close box (command `0x42b7c353`) | `0x02F95AD6` | no |

`FUN_100562b1` ends with `FUN_10085091()->vt+0x44(0xd, win, id)` (closes the modal dialog with that result).
The game's own checkboxes apply live on click (messages `0x3ea..0x3f0`), its radio groups only on the OK
button. Measured: after a click on any radio button, the game's or ours, a posted Enter does not close the
dialog. With no prior radio click, Enter closes it as OK (`HUDOPT> OK ... (unchanged)`). Stock behaviour.

### Where the game keeps these settings

The OK handler writes into the struct behind `FUN_1008e998()` (`vt+0x2c`, `+0x30`, `+0x34`, `+0x38` blocks).
Its serializer was not found (PREFS_UI.md, section 6), so the HUD option does not try to live there.

## 4. The HUD scale option (sc3resize HUDOPT)

Two SIMUI entry detours (prologues checked against the anchor bytes first, both or neither):

| site | prologue | what the detour does |
|---|---|---|
| `0x10055e07` controller message handler | `55 8b ec 83 ec 18` | after the original handles `0xa2bf8ace`, adds a label, a 5-option group and a checkbox to the new window |
| `0x100562b1` close | `55 8b ec 51 51` | before the original runs, reads the controls back; on `0x02F95AD8` applies them and writes the ini, on anything else applies nothing |

Controls (local coordinates, right half of "Opciones generales"):

| id | widget | where | text (es / en) |
|---|---|---|---|
| `0x02F95B46` | label | `(250, 346)` w 180 | "Escala de la interfaz:" / "Interface scale:" |
| `0x02F95B40` | option group | `(250, 364)`, 218x36, 2 rows | |
| `0x02F95B41..45` | options | | "Normal", "Ajustar"/"Fit", "125%", "150%", "200%" |
| `0x02F95B47` | checkbox | `(250, 400)` w 120 | "Suavizado" / "Smooth" |

Our ids fall outside every id range the dialog's command handler `FUN_10058f14` acts on, so a click on them only
runs the widget's own behaviour. Reading back uses the same calls as the game's OK handler `FUN_100593ac`:
`win->vt+0x80(id, 0xa1336cc0, &o)` then `o->vt+0x30()` (selected id), and `win->vt+0x80(id, 0x8810, &o)` then
`o->vt+0x38()` (checked).

**Text language.** The game's locale id (SC3U `FUN_004845fe` -> `vt+0x74`, compared with -1 at `0x0040586a`) reads
**1 on this Spanish install**, so it cannot pick the text. The mod loads the dialog's own title resource
(`0x14e` / `0x029541f4`) and uses Spanish when it reads "Preferencias". Logged: `HUDOPT> dialog title resource:
"Preferencias" -> Spanish text`. `sc3resize.ini [hud] lang=es|en` overrides.

**Applying.** On OK the values go straight into `g_hudscale` / `g_hs_filter`, which the HUDSCALE present pass and
the wndproc mouse map read every frame and every message on the game thread, so the change shows on the next
frame. Turning it Off makes the next present skip the pass and the mouse map stop. Measured both ways at
1200x900 (`08_after_ok_150_smooth.png`, `17_normal_ok.png`).

**Persistence.** `sc3resize.ini` beside `sc3resize.dll`:

```ini
[hud]
scale=150    ; 0 off, 1 fit, 100..400 percent (the dialog offers 125/150/200)
smooth=1     ; 0 nearest (crisp), 1 bilinear
;lang=es     ; optional, text language of the controls
```

Read once at startup. `SC3RESIZE_HUDSCALE` / `SC3RESIZE_HUDSCALE_FILTER` still override it (testing). No ini and
no env = Off. `SC3RESIZE_HUDOPT=0`: no detours and the ini is not read, which is the env-only behaviour of main.

## 5. Two HUDSCALE findings made while testing the option

1. **Double-mapped mouse moves (fixed, `SC3RESIZE_HUDSCALE_REPOST`).** With the HUD enlarged, every mouse move
   came back through the queue about 15 ms later carrying the native point the mod had produced, with the same
   `GetMessageTime` (`HSMLOG>` diag, `SC3RESIZE_HUDSCALE_MLOG=1`). The physical cursor never moved and no mod
   posts it (sc3overscroll posts moves only during an off-window drag). The game, or a layer under it, re-posts
   the move. The wndproc mapped it a second time: `(1100,332) -> (1120,446) -> (1120,537)`, so hovering the
   enlarged "Preferencias" flyout icon showed the "Guardar como" tooltip and the click opened nothing. A move
   whose point equals our last output within 500 ms now passes through unmapped. After it: the click opens
   Preferences (`28_prefs_from_scaled_flyout.png`). This matches the unexplained flyout misfire in
   `HUD_SCALE.md` (item click landing on the button one mapping further). Who posts the move is `[UNCERTAIN]`.
2. **Open flyout + window resize with the HUD enlarged leaves a stale side panel (NOT fixed).** Repro: HUD scale
   on at 1200x900, open the settings flyout, maximize. The enlarged panel then shows the pre-resize panel with the
   flyout and duplicated buttons, while the live tree has the flyout closed and the buttons re-docked
   (`uitree_max.txt`), so clicks land on the real layout (`30c.png`, `32c.png`, persists > 1 min). Controls:
   same steps with the HUD at Normal draw a correct panel (`33c.png`); HUD enlarged and maximize without an open
   flyout is correct (`34c.png`). Cause not established.
