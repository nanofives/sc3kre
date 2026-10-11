# RESULTS - sc3mods release 2026-10-11

Owner hand test 2026-10-11 on the combo build (resize, bigcity, overscroll, simrun, perf): "everything works fine",
then the speed keys were changed to not unpause (b06f291) and re-checked live. Release source: `5656eb4`.
The binaries are the tested ones from `re/harness/combo/`, each built from source unchanged since and committed.
Package built locally into `re/harness/dist/sc3mods_2026-10-11/` (gitignored, binaries are not committed).

## Contents

| file | bytes | SHA-256 |
|---|---|---|
| `README.txt` | 5,064 | `21649878FFBC67D0B0FE92954F5A1974A2F9D17C0E29732411C2052CF09B3E3B` |
| `mods_launch.exe` | 122,368 | `B56216AB8DA867C0B155464A0F4BEA800AA990DAC18112D6D26D860096C0AFAA` |
| `perf.ini` | 2,090 | `2B1C536C2C1284C5AAFF63EDDE74D5ACAE45557D75ED2CEC73AC93A3E3F86164` |
| `sc3resize.dll` | 212,992 | `04059AA21C6E682D4F42F2D9F1515918A8EF1426368BA7826A2B74B4BA019A36` |
| `sc3bigcity.dll` | 137,728 | `CBBE0C97961E029E8C62940BD29B6A5B3E1EE4FF5EF59EAB0659283A55428101` |
| `sc3overscroll.dll` | 123,392 | `BB0E81BDDFE4D772272BA0C27F133D0A5642F3DEFE798B5E4A307729CF4220C0` |
| `sc3simrun.dll` | 115,712 | `58A946F2CC9021272C55C3DB8F15C38B06C72D8490D0E9F40F592C0459FDD287` |
| `sc3perf.dll` | 178,176 | `BAA78D5A11E8B007EDEA18CB49F52BCEE3F8695E9FC3586332398A1C3C817E38` |
| `sc3mods_2026-10-11.zip` | 515,209 | `EBFF7EC3AB50C3ECAD79F3CF9D43C037A5A5B97E675C2CE31922BFAAE287F84D` |

`perf.ini` is the tested `combo/perf.ini` with the `traffic_mt=8` line moved under its comment (same 31 keys and values).
It ships because the code default for `sysmem` is 0 and the tested setting is 1.

sc3overscroll.dll differs from release sc3mods-2026-10-06 (arrows_keep, true_center, front_wall from ed2294a).

Not shipped: `menu_bg.bmp` and `menu_orig.raw` (game-art derived; without them MENUBG logs "missing - off" and the
stock menu shows), `sc3perf_names.txt` (diagnostic, the busy line shows MODULE+offset without it), `sc3startsize.dll`.

## Offline gates

| gate | result |
|---|---|
| all six binaries PE32 x86 (machine `0x14c`, magic `0x10b`), DLL flag on the five DLLs | PASS |
| imports | system DLLs only: KERNEL32 (all), USER32 (resize, overscroll, perf), GDI32 (resize, perf) |
| source of each binary unchanged since its build and committed | PASS (mtimes and `git log`) |
| README voice check | 0 em-dashes, 0 semicolons, 0 ellipses, ASCII, CRLF |

## Smoke test of the package, no environment set

Package copied to `re/harness/pkgtest_1011/` (bin depth), no `SC3*` variables, launched with
`verify/perf1024/europolis1024_v2_test.sc3` (1024 map).

- All five mods loaded and logged beside the DLLs. sc3perf read the shipped `perf.ini` (`sysmem=1`, `traffic_mt` 8 workers,
  background queue on). sc3simrun `run_while_scrolling=1 patched=1`.
- Key 3: clock speed 129600 (666 ms per day), still paused. Key P: pause depth 1 -> 0.
- Maximized 1680x979: side panel, bottom bar and minimap in place (screenshot checked). One minimap capture (MINICLASS).
- 75 s at speed 3: `DAYS> 43 days in 60 s`, median 655 ms (nominal 666), max 18.8 s right after load.
- WM_CLOSE: process gone in 3 s.
- VEH log: 3 entries, all known and benign: `SC3U+0x84122` (startup privileged-instruction probe) and twice
  `KERNEL32+0x2CC02` (handled IsBadReadPtr probe). No unhandled fault.

Test folder deleted afterwards. Three stale `Apps\sc3perf_*.log` files from earlier runs were removed from the game folder.

## Published

GitHub release `sc3mods-2026-10-11` on nanofives/sc3kre, target `5656eb4`:
https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-10-11
Asset downloaded back with `gh release download`: SHA-256 `EBFF7EC3AB50C3ECAD79F3CF9D43C037A5A5B97E675C2CE31922BFAAE287F84D`, matches.
