# RESULTS - sc3mods release 2026-10-29d + LAN republish

Replaces `sc3mods-2026-10-29c`. Owner reports 2026-10-29: Ver datos pollution radios ignored at big UI scale; MARIANO-PC crash
18:04 after 72 min on Big One (address space exhausted). Source as of `39d4342`.

| what | commits | record |
|---|---|---|
| VDRADIO: the sharp Ver datos twin copies the native view's shown-layer bytes and redraws on change | 0c23f38 | verify/vdradio/RESULTS.md |
| SURFFREE + RESHOWONCE: release old view surfaces on a resize / zoom step, keep art cached through the re-show (15 min soak 348->1140 MB became 281->325 MB) | 39d4342 | verify/memleak/RESULTS.md |
| sc3autosave MINFREE + FAULTFIX, sc3resize LOGTAIL + NULLLOCK (the GZGraphicD+0x1465D crash) | 39d4342 | verify/memleak/RESULTS.md |

Shipped: sc3resize.dll, sc3autosave.dll, sc3perf.dll (diagnostic line only), README.txt.

## Stage and checks

- `stage/bins_1029d` = `stage/bins_1029c` + the three DLLs built from main. Label `2026-10-29d`, 3,612 files, 706.0 MB.
- Launch check (stage/release patched, windowed, no input): Berlin, `8 mod(s) loaded`, `NULLLOCK` wrapped, SURFFREE released the
  HUD and side surfaces on the first layout through FUN_10014410, only the benign `0xC0000096 @ SC3U+0x84122`. Then `-Restore`, logs
  deleted, 3,612 manifest files re-hashed: 0 changed, 0 missing, 0 extra.

LAN: 3 of 3,612 files sent (0.8 MB). Served label `2026-10-29d`.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/sc3resize.dll | 476672 | DBCF8159E3C1EAB0C5D34C615B7FFBF82AF14831EA7FA02B4624B268C01F9947 |
| Apps/sc3autosave.dll | 133120 | 30B157C8D6611D84E6A99F1F64CF011C572A45A527A260E8A50A0B684A2FC911 |
| Apps/sc3perf.dll | 191488 | 6A25ACE1AA0E1EAAE4981BEA7DCEC87942B9A01E57B7F84A0C26676B59647882 |
| README.txt | | 2026-10-29d section |
| every other file | | as `verify/mods_release_1029c/RESULTS.md` |
| `sc3mods_2026-10-29d.zip` | 50,225,632 | 4629FCE09DFD2167F22DD3E2533A7878CF73B05B44D1E634B3F832D0E31F651A |

Owner checks: zoom steps with Ver datos open, Alt+Enter after resizes (not run by memleak), a long session on Big One.

GitHub: `sc3mods-2026-10-29d`, target `900dbec`, https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-10-29d, asset
downloaded back, SHA-256 matches. The 10-29c notes now start with a "superseded" line.
