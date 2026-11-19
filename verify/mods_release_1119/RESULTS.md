# RESULTS - sc3mods release 2026-11-19 (GitHub only)

Replaces sc3mods-2026-11-18b. Owner call 2026-11-19: the .bld render kit goes "In the next sc3mods zip". Source: main
c2dfac6 (sc3compat-a merged 0cd786a, kit path fix c2dfac6).

| what | merges | record |
|---|---|---|
| tools\bld_render\: bawinonly.dll batch mode + baappw_patch.ps1 + render_bld.ps1 / .cmd + README (no EA files) | 0cd786a, c2dfac6 | verify/sc3compat_a/RESULTS.md |

## Checks

- bawinonly.dll built from main (stage/build_1119), SHA-256 7760FD8534324D2A9126B30F588DF462459A3F41CD44C95708C2D6678B7004B4, Jotti 0 / 13.
- Zip layout test on a fresh dev tree: kit in tree\tools\bld_render, Windows PowerShell 5.1, 2 .bld (Hotel Splash 2x2,
  Headquarters 3x3) rendered in 16 s, exit 0, display modes sampled 600 times, no change; BaappW.exe made from the
  tree's Baapp.exe (GOG 2.0.949). The first run before the fix would have missed Apps from tools\bld_render (fixed in
  c2dfac6: ..\..\Apps is searched too).
- Zip: the 2026-11-18b tree + tools/bld_render (5 files) + README.txt (header 2026-11-19, WHAT'S INSIDE line, NEW IN
  2026-11-19). 198 entries: 191 equal to the LAN manifest, overlay SYS.PAK differs by design, README.txt and the 5 kit
  files not in it. sc3mods_2026-11-19.zip, SHA-256 80AB6218C7509BDE78FCFFB4C4155BEA1294EFEFCEE06553DA3B0C89BDA32E20.
- LAN not restaged: no mod or data file changed (the LAN stage carries no tools\ folder).

GitHub: `sc3mods-2026-11-19`, target 02cea4d, asset downloaded back, SHA-256 matches. The 18b notes start with a "superseded" line.
