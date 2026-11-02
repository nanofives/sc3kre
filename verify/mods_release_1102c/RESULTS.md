# RESULTS - sc3mods release 2026-11-02c + LAN republish

Replaces `sc3mods-2026-11-02b`. Owner call 2026-11-02: publish the round "SC3 graphs tabs + Vida util/restore/query UI
round" (re/sessions/ROUND_2026-11-02_graphs_restoreui.md). Binaries built from main `c961a08` (source tree = f711993 after the
history clean-up below; only verify screenshots and run logs differ).

| what | record |
|---|---|
| Ver datos tabs on Graficas + Cuadros, rounded (r 9), Cuadros font 0x11; Cuadros Agua + Transporte, Educacion / Salud bars | re/sessions/STATUS_graphs2.md, STATUS_roundtabs.md, STATUS_tabfont.md |
| RCI A / P bars = valves 5001 / 8001 capacity in use, 75% tick, tooltip; no agricultural bar (owner call) | verify/rcibars/RESULTS.md |
| Restore at 50% (restore.ini cost_percent), Vida util hourglass icon, list/footer layout, grey Como nuevo, Sustituir font, more "?" rows | verify/restoreui/RESULTS.md |
| Sirens: per-vehicle state (stock +0x90 shared and uninitialized), roll 20% of stock, 30 s cooldown | verify/sirens/RESULTS.md, re/analysis/SIRENS.md |

## Stage and checks

- `stage/bins_1102c` = `stage/bins_1102b` with sc3resize.dll, sc3restore.dll, sc3simrun.dll rebuilt from c961a08 (dev/merge1102).
- `stage_lan_release.py --game stage/src --bins stage/bins_1102c --stock-modules original/modules --menu-bg stage/release/Apps/menu_bg.bmp
  --perf-ini stage/release/Apps/perf.ini --out stage/release_1102c --label 2026-11-02c`: 3,615 files, 706.8 MB. Manifest against
  11-02b: changed Apps/sc3resize.dll, Apps/sc3restore.dll, Apps/sc3simrun.dll, 0 added, 0 removed.
- Launch check (release_1102c patched, windowed, Berlin, no input, 100 s): `11 mod(s) loaded`; RESTORE, VDTABS (tabs, bars, trip
  modes), RCIBARS (commercial 56%, industrial 17%), SIRENS (6 patch sites) all on; only the benign `0xC0000096 @ SC3U+0x84122`.
  Then `-Restore`, 12 logs + dataview.ini + landfill.ini deleted, manifest re-hashed: 0 changed, 0 missing, 0 extra.
- Not checked in this launch: clicks on the new tabs and buttons (each child checked its own in its tree).

Zip: the 11-02b zip (downloaded from its release, SHA-256 3D88DCA4...) with the 3 DLLs replaced and README.txt updated (header,
sc3simrun line, NEW IN 2026-11-02c). 135 entries, 134 checked against the staged manifest, 0 mismatches.
`sc3mods_2026-11-02c.zip` 50,610,823 bytes, SHA-256 552E24CE54BD768424687E1A5105B4D276AF2B7265258B440151E4F547E244E5.

History clean-up: the round's merges had force-added verify/*/owner_shots/*.png and verify/*/runs/ (game screenshots, logs). Before
the push they were removed from the 19 unpushed commits (filter-branch, origin/main..HEAD); the files stay on disk, untracked.

GitHub: `sc3mods-2026-11-02c`, target `839e612`, https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-11-02c, asset
downloaded back, SHA-256 matches. The 11-02b notes now start with a "superseded" line.

LAN: `deploy_lan_release.sh stage/release_1102c` sent 3 of 3,615 files (0.9 MB). Served label `2026-11-02c`, served
sc3resize / sc3restore / sc3simrun SHA-256 match the stage. Then `stage/release` -> `stage/release_1102b_old`,
`stage/release_1102c` -> `stage/release`.
