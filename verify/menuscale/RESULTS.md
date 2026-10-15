# RESULTS: menuscale (2026-10-14)

Pre-registration: `PRE.md` (17c9449, committed before the first run). Branch `child/menuscale` from `round/1012`.
Instance `MAIN\re\harness\inst_menuscale` (all six binaries built from the worktree, owner's `menu_bg.bmp`), live
install, `mods_launch.exe -multi -- -intro:off`. Display 3840x2040, maximized client 3840x1984. Grabs, dumps, logs and
`owner_shots\` are local (`MAIN\verify\menuscale\`, gitignored).

**Verdict: PASS.** Code as tested = 05f7b92. Two defects of the first build (17c9449) were found by the runs and fixed
before the arms below were re-run (section "Defects found").

## Seen vs logged

Menu frames were SEEN on screen in every arm. The menucrop limit (white frame while unfocused) did not reproduce:
the source frame always had content (`stock 203934` on the first frame, as on 2026-10-11), and desktop grabs showed the
menu both on the scaled path and on the 1:1 control (arm C). `[UNCERTAIN]` why menucrop saw white. Two views are kept
apart below: the DLL dump (`SC3RESIZE_MENUSCALE_DUMP`: what MENUSCALE composed and sent to the window, plus the source
frame, mask and picture it used) and the desktop grab (`sc3io`, no focus taken). Dump vs grab, whole client:

| run | client | differing pixels | where |
|---|---|---|---|
| A0 | 3840x1984 | 3,156 | rows 18..50 = the live sc3perf FPS text |
| A | 1680x1050 / 1680x979 / 1000x900 | 766 / 667 / 329 | FPS text + the two rounded bottom window corners (Windows 11) |
| F (final build, after a dialog opened and closed with box-only blits) | 3840x1984 | 1,139 | FPS text only |

## Rect (pre-registered)

| client | predicted | logged |
|---|---|---|
| 3840x1984 | `[597 0 3242 1984]` | `[597 0 3242 1984] = 2645x1984 (x3.3067)` |
| 1680x1050 | `[140 0 1540 1050]` | same |
| 1680x979 | `[187 0 1492 979]` | same |
| 1000x900 | `[0 75 1000 825]` | same |
| 800x600 | no MENUSCALE line | none; native path `swap ... stock 203934` as before |

## Arms

| arm | result |
|---|---|
| A | Clicks on the drawn buttons at 3840x1984: "Nueva Ciudad" opened "Nuevas opciones de ciudad" (seen), "Difícil" radio set, close box closed it. "Cargar Ciudad" opened "Cargar ciudad", "Europolis" selected in the list (preview and name changed), close box closed it. "Preferencias" opened, "Ver consejos al iniciar" toggled, close box closed it. "Salir" opened the quit dialog, "Cancelar" closed it and the game kept running. At 1680x979 "Nueva Ciudad" opened the dialog and its close box closed it. Log: every button message mapped, e.g. `client (1359,961) -> frame (230,290)` |
| B | `SC3RESIZE_MENUSCALE_FILTER=0`: `re/tools/menuscale_check.py` recomputes the rect from the dumped frame, mask and picture: 0 mismatches of 5,247,680 rect pixels, 0 of 2,370,880 margin pixels. Same check on bilinear dumps (A2 3840x1984, A2 1000x900, F, G): 0 mismatches each |
| C | `SC3RESIZE_MENUSCALE=0`: log `MENUBG> first centred present: dest [0 56 3840 2040] -> frame at [1520 748 2320 1348]`, no MENUSCALE rect line. Click at frame (230,290) + (1520,692) opened New City, seen 1:1 in the middle. PRE wrote the expected string as `[1520 692 2320 1292]`: the log prints dest (screen) coordinates, dest top 56, so the client offset (1520,692) is as predicted and the string was not |
| D | From the scaled maximized menu: "Cargar Ciudad", "Europolis", check button. Log: `MENUSCALE> menu over: full-window present of another frame`, once, no MENUSCALE line after it, `HOLD> released after 194 held present(s)` as before. Grabs every 1.2 s: the loading dialog over the picture, then the city with its HUD. No menu frame in a city grab, no crash |
| G (extra) | no `menu_bg.bmp`: stock picture as background (`missing - using the stock background`), rect scaled, check 0 mismatches. Owner shot 8 |

## Performance (log, every 2 s, final build)

| client | static menu, per present | worst static | dialog opening |
|---|---|---|---|
| 3840x1984 | read 0.13-0.15, compose 0.005-0.008, blit 0.001 ms | 0.36-0.54 ms | one present 31.9-34.5 ms (whole rect recomposed) |
| 1680x979 | read 0.13-0.15, compose 0.004-0.006, blit 0.001 ms | 0.27-0.76 ms | first present after the resize 9.7 ms |

120 presents per 2 s at the menu. "Read" is the lock + compare of the 800x600 source, every present.

## Defects found and fixed (first build 17c9449, run A0)

1. **Whole-client GDI blit every present: 10-20 ms at 3840x1984.** Now only the recomposed box goes out, and the whole
   client on a new size, the first scaled present, and after WM_PAINT / WM_ERASEBKGND / WM_NCPAINT / WM_SIZE /
   WM_ACTIVATE(APP) / WM_WINDOWPOSCHANGED / WM_DISPLAYCHANGE. A once-a-second safety repaint was tried and measured as
   the 14-17 ms worst present, so it is opt-in (`SC3RESIZE_MENUSCALE_REFRESH=<ms>`). Unchanged rows of the source are
   skipped by a row compare (read about 2 ms -> 0.13-0.34 ms).
2. **Clicks inside "Preferencias" missed.** The first build mapped only depth-0 messages, as HUDSCALE does. The
   "Preferencias" button runs a modal loop inside its handler (`msg 0x0202 ... depth 1` for the button's own release),
   so every later click came at depth 1 and was left in client coordinates: the close box at client (2645,270) did
   nothing. Now a message is left alone only when it carries exactly our last frame point within 500 ms: a
   WM_MOUSEMOVE at any depth (the game's queued repost, logged after every click at the menu:
   `msg 0x0200 at our last frame point (540,310), depth 0, left unmapped`) or a button message at depth > 0.

## Not checked

- Owner hand test with a real mouse, focus and hover.
- Partial presents: none happened at the menu in any run (`0 partial` in every timing line), so `rz_ms_partial` ran 0
  times. It recomposes the box fed by the sub-rect and drops the present if no frame is cached.
- The WINSC3BMP registry override and New City into a terrain (only Load City was taken into a city).
