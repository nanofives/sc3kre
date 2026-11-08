# RESULTS - LAN republish 2026-11-08 (terrain panel TREEBAR + FILLSLICE)

Owner call 2026-11-08: "Commit and publish the terrain fixes to the LAN build". LAN only, no GitHub release.
Source: main `a6fce38` (only sc3resize.c / sc3resize_terrpanel.c changed since 11-06).

- `stage/bins_1108` = `stage/bins_1106` with `sc3resize.dll` rebuilt from main (`build_mod.ps1 -Mod sc3resize`).
- `stage_lan_release.py --game stage/src --bins stage/bins_1108 --out stage/release_1108 --label 2026-11-08
  --community stage/community_1106`: 3,643 files, 711.6 MB. Against 11-06: 1 changed (`Apps/sc3resize.dll`), 0 added, 0 removed.
- Launch check (staged folder patched with sc3mods_patch.ps1, windowed, Berlin, no input, 150 s): `11 mod(s) loaded`,
  NATWORLD / TERRPANEL / FORESTTOOL on, city HUD visible, only the benign `0xC0000096 @ SC3U+0x84122`. Then -Restore,
  13 logs + dataview.ini + landfill.ini deleted, manifest re-hashed: 0 changed, 0 missing, 0 extra.
- Deploy: 1 of 3,643 files sent (0.7 MB). Served manifest label 2026-11-08, 3,643 files, served sc3resize.dll = staged.
  `stage/release` -> `stage/release_1106_old`, `stage/release_1108` -> `stage/release`.

Game test of the feature itself: verify/terrpanel/RESULTS.md (TREEBAR + FILLSLICE).
