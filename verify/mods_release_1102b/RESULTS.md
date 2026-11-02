# RESULTS - sc3mods release 2026-11-02b + LAN republish

Replaces `sc3mods-2026-11-02`. Owner call 2026-11-02: release the GOG/Steam fix, the language picker "and the other things"
on main. Source: main `c721283`.

| what | merge | record |
|---|---|---|
| sc3mods_patch.ps1 accepts the current GOG/Steam exe (2.0.949, SHA-256 42E30CE0...), stale backup from another stock build replaced | 0466dfb | GitHub issue #2, memory project-gog-2-0-949-build |
| sc3resize side panel re-layout every 120 ms when the window is taller than ~600 (SIDEKIDS / SRCRECT) | 0466dfb | commit 225a941 |
| LANGSEL: "Idioma" button on Opciones de mods, hook on the Language read SC3U.exe+0x6c06, sc3resize.ini [language] folder= | c721283 | commit 05d8438 |
| sc3restore + sc3resize RESTORE (Restaurar, Vida util) | b13b4e9 | verify/restore/RESULTS.md |
| graphtabs: Graficas tabs, 9 more graphs, seeded history | 7ddbba1 | re/sessions/STATUS_graphtabs.md |

## GOG 2.0.949 findings

- All 3,491 files of the owner's GOG install hashed on MARIANO-PC (`original/gog_2.0.949/gog_manifest.csv`): only
  `Apps/SC3U.exe` (8 bytes: `ret 8` over `0x00407684` snap and `0x00407756` validate resolution) and 69 English text files
  (language, not version) differ. New: DDrawCompat `ddraw.dll` + ini, GOG metadata, language_setup, uninstaller.
- Mods tested on 2.0.949 + DDrawCompat in dev/gog949: all mods load, windowed, resize, 9/9 side hovers and 4/4 clicks.
- GOG writes AppCompatFlags Layers `16BITCOLOR 8And16BitAggregateBlts DISABLEDWM HIGHDPIAWARE` on its SC3U.exe. Under
  them the game starts and every mod loads (logs). The on-screen picture after a resize is NOT verified: the monitor
  was asleep and LIVING-PC has no Parsec VDD.

## Stage and checks

- `stage/bins_1102b`: the binaries of `stage/bins_1102` plus `sc3mods.dll`, `sc3resize.dll`, `sc3restore.dll` built
  from main `c721283` (dev/rel1102b).
- Staged into a NEW folder `stage/release_1102b` (label `2026-11-02b`, 3,615 files, 706.8 MB). Manifest against 11-02:
  changed `Apps/sc3mods.dll`, `Apps/sc3resize.dll`, `sc3mods_patch.ps1`, added `Apps/sc3restore.dll`, 0 removed.
- Launch check (release_1102b patched, windowed, Berlin, no input, 100 s): `11 mod(s) loaded`, LANGSEL found 7
  languages and passed through (no choice saved), RESTORE on, 800x600 at ~60 fps, only the benign
  `0xC0000096 @ SC3U+0x84122`. Then `-Restore`, logs and the two first-start ini files deleted, manifest re-hashed:
  0 changed, 0 missing, 0 extra.
- Side note: a first launch before the exe was patched (the patch command's path was mangled) left
  `Apps/SC3U_stkdmp.txt`, an ACCESS_VIOLATION on that unpatched run's thread (no mods loaded on it). Deleted. Cause not
  established; the monitor was asleep, and a stock start goes fullscreen.

LAN: deployed from `stage/release_1102b`, 4 of 3,615 files sent (0.8 MB). Served label `2026-11-02b`, served
`Apps/sc3resize.dll` and `Apps/sc3restore.dll` SHA-256 match the stage.

Zip: the 2026-11-02 zip (downloaded from its GitHub release) with `Apps/sc3mods.dll`, `Apps/sc3resize.dll`,
`sc3mods_patch.ps1` replaced, `Apps/sc3restore.dll` added, README.txt updated (header, file list, patch text, NEW IN
2026-11-02b, [language] under OPTIONS). 135 entries, 134 checked against the staged manifest, 0 mismatches.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/sc3resize.dll | 559104 | 067D6425317F2E2B... (manifest) |
| Apps/sc3restore.dll | 125440 | 15F2C17A78132A01... (manifest) |
| `sc3mods_2026-11-02b.zip` | 50,354,107 | 3D88DCA4A7C1E199E4EBEDA890D4F4155E1D4DAE33C8F9FF01A1282BD77ED745 |

Owner checks: the compat-flag picture after a resize on a GOG 2.0.949 install, the README KNOWN LIMITS line that still
suggests a renamed `SC3U_mods.exe` (the loader only loads into `SC3U.exe`).

GitHub: `sc3mods-2026-11-02b`, target `6d9e6f6`, https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-11-02b, asset
downloaded back, SHA-256 matches. The 11-02 notes now start with a "superseded" line. Issue #2 answered:
https://github.com/nanofives/sc3kre/issues/2#issuecomment-6579054294
After publishing, `stage/release` was renamed to `stage/release_1102_old` and `stage/release_1102b` to `stage/release`
(label `2026-11-02b`). `release_1102_old` is left for removal once no dev tree game holds its files.
