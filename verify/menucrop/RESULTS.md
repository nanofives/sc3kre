# RESULTS: menucrop (2026-10-14)

Pre-registration: `PRE.md` (ee211bf, before the first run). Branch `child/menucrop` from `round/1012`. Instance
`MAIN\re\harness\inst_menucrop` (the 2026-10-11 `inst_menubg` mods + the new `sc3resize.dll`), live game install,
`mods_launch.exe -multi -- -intro:off`. Display 3840x2040 here, maximized client 3840x1984 (aspect 1.935).
Grabs, logs and the contact sheet `sheet.png` are local only (`MAIN\verify\menucrop\`, gitignored).

**Verdict: PASS for what this session could see (log + margins); the centred menu frame itself was not seen.**

| arm | menu_bg.bmp | log | maximized margins |
|---|---|---|---|
| A | owner's 1448x1086 24-bit | `loaded menu_bg.bmp 1448x1086`, `cover source [0 169 1448 917]` (748 rows = 1448*1984/3840) | owner's picture, sky band cut top and bottom, not squashed |
| B | none | `missing - using the stock background`, `cover source [0 93 800 506]` | stock picture, cropped |
| C | text file | `not a BMP - using the stock background`, same source | identical to B (same pixel hash) |
| D | owner's as 32-bit (6,290,166 bytes, bpp 32) | `not an uncompressed 24-bit BMP - using the stock background`, same source | identical to B |
| E | owner's, `SC3RESIZE_MENUBGFIT=0` | `stretch source [0 0 1448 1086]` | the 2026-10-11 stretched look (sky visible, buildings squashed) |

At 800x600 every arm logged the whole picture as source (`[0 0 1448 1086]` / `[0 0 800 600]`): a 4:3 picture at a
4:3 client is not cropped.

## Not checked, and why

- **The centred 800x600 menu frame and the "Nueva Ciudad" click.** With the game window not in the foreground the
  game presents its menu frame as plain white (both at 800x600 and maximized; `sc3io` refused the 800x600 grabs as
  99.9% one colour). Taking foreground from a background session is blocked by Windows and would take the PC from the
  owner. Same limit as the 10-12 package smoke test. The frame swap and the mouse shift are untouched by this change
  (only `rz_mb_load` and the source rect in `rz_mb_prepare` changed), and the arms that matter for the fallback (C, D)
  show MENUBG ON (centred present logged), which is what keeps the clicks right. Owner hand test covers it.

## Harness notes

- `-intro:off` skips the intro movie: SC3U `FUN_00403565` reads the `intro` option and compares it with `off`
  `[CONFIRMED @ 0x00403565, string at 0x004f4c34]`. Posted clicks and ESC did not skip the movie.
- The `mods_launch.exe` in `inst_menubg` predates 7c1db20 (unbuffered stdout): piped, its `pid =` line shows only at
  exit. The driver found the new SC3U pid by diffing the process list instead.
