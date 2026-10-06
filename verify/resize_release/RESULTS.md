# RESULTS — sc3resize release 2026-10-06

Owner hand test 2026-10-06 on the build from `7a02700`: "we can ship this mod, it works".
Release source: `42049c3` (adds the cluster default and the default-log cap on top of the tested
build). Package built locally into `re/harness/dist/sc3resize_2026-10-06/` (gitignored, binaries are
not committed).

## Contents

| file | bytes | SHA-256 |
|---|---|---|
| `sc3resize.dll` | 198,144 | `8A579A493019B551E13205FF4B05AE4E229A75F35FC098E4800BF5CC657D2A33` |
| `resize_launch.exe` | 121,344 | `4EB213BB44E9F41E8B51886C9247F86BD15E837090ECC97A7AA9F1DDE9584D59` |
| `README.txt` | — | install, uninstall, options, known limits |
| `sc3resize_2026-10-06.zip` | 182,990 | `51D09580057B4A19E82B949B8BC0255100E93C86404736562636C48D6850CAF2` |

## Offline gates (same table as `verify/resize_ship/PRE.md`)

| gate | result |
|---|---|
| builds clean, no warnings | PASS (0 warning/error lines in the build output) |
| `sc3resize.dll` PE32 x86, DLL flag | PASS (machine `0x14c`, magic `0x10b`, DLL) |
| `resize_launch.exe` PE32 x86 console | PASS |
| imports KERNEL32 + USER32 only | PASS (DLL: KERNEL32, USER32. Loader: KERNEL32) |
| hook prologues | unchanged since 2026-08-28. Every installer is fail-closed on the expected bytes |
| loader injects `sc3resize.dll` from its own directory | PASS by inspection, loader source unchanged |

## Smoke test of the package, no environment set

Package copied to a folder at `bin` depth, every `SC3RESIZE_*` variable cleared, launched with
Europolis. Default log written to `Apps\sc3resize.log` (copied to `verify/resize_dialogs/pkg_smoke.log`,
then the file was deleted from the game folder).

- `FLAGS>`: `cluster=1 kidfix=1 artguard=1 edgefix=1 edgescroll=0 barspan=1 sidespan=1 viewfix=1 dialogs=1`.
- Maximized 1680x979: bar `[0 923 1680 979]` full width, side panel `[1584 0 1680 815]` full height,
  city view `[0 0 1680 979]`.
- Reunirse opened centered on (791,461), map-area center (792,461).
- 0 access violations. Log 326,720 bytes for the session.

Staged install untouched afterwards: `SIMSPR.DLL` `f5b9f1d9`, `GZGraphicD.dll` `acefadf0`.
