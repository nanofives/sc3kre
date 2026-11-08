# RESULTS - sc3mods release 2026-11-08 + LAN republish 2026-11-08b

Replaces `sc3mods-2026-11-06` (GitHub) and LAN `2026-11-08` (which held TREEBAR + FILLSLICE only).
Owner call 2026-11-08: "Publish to LAN and make a GitHub release". Source: main `85f797c`.

Content: terrain panel TREEBAR + FILLSLICE (`a6fce38`, verify/terrpanel/RESULTS.md) and UNIFIEDFPS (`85f797c`: the FPS /
profiler text at the HUD factor with Consolas on every screen, the terrain editor included; LIVING-PC 1600x1200: terrain
screen and city both 200%, same font, no change on Accept).

- `stage/bins_1108b` = `stage/bins_1108` with `sc3resize.dll` and `sc3perf.dll` rebuilt from main (`build_mod.ps1`).
- `stage_lan_release.py ... --bins stage/bins_1108b --out stage/release_1108b --label 2026-11-08b --community stage/community_1106`:
  3,643 files, 711.6 MB. Against LAN 2026-11-08: 2 changed (`Apps/sc3resize.dll`, `Apps/sc3perf.dll`), 0 added, 0 removed.
- Launch check (patched, windowed, Berlin, no input, 150 s): `11 mod(s) loaded`, NATWORLD / TERRPANEL on, city HUD visible,
  sc3perf `overlay text at 100% (scaled font)`, only the benign `0xC0000096 @ SC3U+0x84122`. Then -Restore, logs + dataview.ini +
  landfill.ini deleted, manifest re-hashed: 0 changed, 0 missing, 0 extra.
- LAN: 2 of 3,643 files sent (0.9 MB). Served label 2026-11-08b, served sc3resize.dll and sc3perf.dll = staged.
  `stage/release` -> `stage/release_1108_old`, `stage/release_1108b` -> `stage/release`.

Zip: the 11-06 zip (downloaded back, SHA-256 741EE678... as recorded) with Apps/sc3resize.dll, Apps/sc3perf.dll and
README.txt (NEW IN 2026-11-08) replaced. 157 entries, 156 checked against the staged manifest, 0 mismatches (README.txt is not
in it). `sc3mods_2026-11-08.zip` 51,423,662 bytes, SHA-256 D1C397BDB4156E3A06165ABB68FC501F15C901E0DACD6C1180A25E43A107700E.

GitHub: `sc3mods-2026-11-08`, target 85f797c, https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-11-08, asset
downloaded back, SHA-256 matches. The 11-06 notes start with a "superseded" line. Repo README mods section updated.

Not checked: the FPS text on the owner's 2560x1351 window (only 800x600 and 1600x1200 here).
