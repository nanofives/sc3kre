# RESULTS - sc3mods release 2026-10-28c + LAN republish

Replaces `sc3mods-2026-10-28b`. Owner report 2026-10-28 (second crash loading Big One.autosave2 from the main menu on
MARIANO-PC, logs pulled from that PC). Source as of `6b43bfb`. Changes since 10-28b (`1a68628`):

| what | commits | shipped files |
|---|---|---|
| INITSLACK: the game's own city-view render target (SIMSPR 0x10005cf8 / 0x10005df1) gets 8 guard rows; an odd client height (2560x1351) let the first 2x blit after a load write one row past the surface (GZGraphicD+0x253E) | c544cee | sc3resize.dll |
| OVNEST: a nested full-client Blt no longer restores the outer present's overlay pixels (sc3perf+0x6D9F NULL read) | c544cee | sc3perf.dll |

Cause, repro and A/B (odd 1351 crashes with INITSLACK=0, even 1350 does not): `verify/edgeload/RESULTS.md`.
`git diff 1a68628 6b43bfb -- re/harness/src`: sc3resize.c, sc3perf.c only. Every other file is the 10-28b one.

## Stage and checks

- `stage/bins_1028c` = `stage/bins_1028b` + sc3resize / sc3perf built from main. Staged with the same command as 10-28b,
  label `2026-10-28c`: 3,606 files, 697.3 MB.
- Launch check (stage/release patched, windowed, no input): Big One, `8 mod(s) loaded`, `INITSLACK: city view Init pads
  its render target by 8 guard rows`, only the benign `0xC0000096 @ SC3U+0x84122`. Then `-Restore`, logs deleted,
  3,606 manifest files re-hashed: 0 changed, 0 missing, 0 extra.

LAN: 2 of 3,606 files sent (0.6 MB). Served label `2026-10-28c`, served sc3resize and sc3perf SHA-256 match the stage.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/sc3resize.dll | 446464 | A2CE09989F539337744C97199A481D9AAE42167A51B843DF987043AE52626DA0 |
| Apps/sc3perf.dll | 190976 | 242A1BBB1779C3CAF3D4727186A5B73874B19FF77C253413AC210CAA22638A52 |
| README.txt | | 2026-10-28c section |
| every other file | | as `verify/mods_release_1028b/RESULTS.md` |
| `sc3mods_2026-10-28c.zip` | 43,615,253 | 140F7D90DBF955CEDA37085E36FCE9CF2DEE5DACA641C92A132BD82BCEA636DF |

Owner check pending: Big One.autosave2 from the main menu with the window maximized on MARIANO-PC.

GitHub: `sc3mods-2026-10-28c`, target `451dc44`, https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-10-28c, asset
downloaded back, SHA-256 matches. The 10-28b notes now start with a "superseded" line.
