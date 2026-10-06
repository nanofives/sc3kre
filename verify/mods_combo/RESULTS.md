# RESULTS - all mods together, release `sc3mods_2026-10-06`

`mods_launch.exe` (`re/harness/src/mods_launch.c`) injects whichever of `sc3resize.dll`,
`sc3bigcity.dll`, `sc3overscroll.dll` sits beside it.

## Combined runs (owner, 2026-10-06)

| run | result |
|---|---|
| 1 | All installers of all three mods went in. Windowed and 16-bit patches exist in all three: the first to load applies them, the others log a pattern mismatch and skip. Owner: on a 1024 map the overscroll limit stopped early at the north/west edges (fixed in overscroll, see `verify/overscroll/RESULTS.md`) |
| 2 | Owner: works |
| 3 | + edge scroll while placing. Owner: works, UI flickers while the camera moves |
| 4 | edge scroll moved to the view tick. Owner: no flicker |

A `0xC0000096` at `SC3U.exe+0x84122` in resize's VEH log at startup is in every earlier resize-only
hand test log (`verify/handtest_1005`, `handtest_1006`, ...). It is not from the combination.

## Release package `sc3mods_2026-10-06` (built from `0fc05b3`)

Every binary is byte-identical to the one in the owner's combined run 4. `sc3resize.dll` and
`sc3bigcity.dll` are the files of their own releases.

| file | bytes | SHA-256 |
|---|---|---|
| `mods_launch.exe` | 122,368 | `E42E6F87F97DD4F023429990CABE20421A2E0F51A3FC8841F370133E49E5C0D4` |
| `sc3resize.dll` | 198,144 | `8A579A493019B551E13205FF4B05AE4E229A75F35FC098E4800BF5CC657D2A33` |
| `sc3bigcity.dll` | 130,560 | `CEEB27FE18C6F48D82F043258FF3F52F448BE6451682C530991AE83B56DA3AA3` |
| `sc3overscroll.dll` | 121,344 | `ECFBF82A583F66F62C96CEA971A9EB1EFF966F2CFA56564619AC90663CF2F2B1` |
| `README.txt` | 2,631 | contents, install, options, known limits |
| `sc3mods_2026-10-06.zip` | 318,784 | `84AA4C611AB3B9E7B3D004DB6859168896A4B379C3E90ED8D0F572E1A4523A65` |

Smoke test of the unzipped package at `bin` depth, no `SC3*_LOG` variables, Europolis:
- bigcity READY with defaults (size 512, not selected), all installers OK.
- overscroll READY (75%, slide, edge scroll, view tick hook).
- resize armed with its shipped flags, default log in `Apps\` (copied to `pkg_smoke_resize.log`, then
  deleted from the game folder).
- Europolis rendered windowed (`pkg_smoke.png`). 0 faults in bigcity and overscroll, resize's only
  VEH entry is the startup one above.
