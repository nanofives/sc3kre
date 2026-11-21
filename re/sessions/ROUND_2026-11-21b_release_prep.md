# Round 2026-11-21b: prepare sc3mods-2026-11-21 (do not publish)

Owner (2026-11-21): "Prepare a release". Changes on main since sc3mods-2026-11-20 (verify/mods_release_1120/RESULTS.md):
nopause (sc3simrun NOPAUSE + sc3resize row), sc3perf stall-sampler guard (5ffc661), overlaymerge (sc3netmod OVMERGE,
sc3perf OVWARN, mods/netmod/overlay_base.txt, stage_lan_release.py), stylepick (sc3netmod STYLEPICK, sc3resize Mix box
+ row, style_mix 1.1.0), civicstyle (sc3resize civic style looks + row, style_mix 1.2.0), lang tables.

## Stream relprep (opus / medium)

1. stage/src: `netpack.py uninstall style_mix` then install 1.2.0 (each step re-merges all packages, about 45 min;
   run in the background with a long timeout), check overlay_base.txt is built.
2. Build every changed mod from main into stage/build_1121 (build_mod.ps1, clear CL), bins_1121 = bins_1120 + them +
   the 7 lang tables (sc3lang check), stage_lan_release.py ... --out stage/release_1121 --label 2026-11-21 (recipe:
   verify/mods_release_1120/RESULTS.md), compare manifests with stage/release (list every changed file and why).
3. Smoke test in a tree made from stage/release_1121 with the shipped DLLs (sc3dev new <x> -Base stage/release_1121
   -NoBuild, shipped sc3mods.dll in tree Apps, the rest in inst, perf.ini): start + load Berlin and Sacramento,
   log lines of NOPAUSE / OVMERGE ("33 stock" etc.) / STYLEPICK / civic styles, VEH lines explained, a picture each;
   the mods page (both pages) in Spanish and English with the new rows, nothing overlapping; the civic list window for
   Police with the three styles; City Properties with the Mix box; the New City window opened 10 times after visiting
   the mods pages (stylepick saw one GZGraphicD+0x18C7A crash in 7): count crashes, and if any, stop and report.
4. Jotti every changed DLL (re-use the scratchpad jotti_scan.py pattern or write one: POST /en-US/submit-file, poll
   /ajax/filescanjobprogress.php).
5. Zip: the 2026-11-20 zip tree (scratchpad rel1120/n, or download sc3mods_2026-11-20.zip from the GitHub release) with
   the changed DLLs, Apps/sc3lang, mods/netmod from stage_lan_release's tree for the changed files (style_mix tables
   and art, overlay_base.txt), README.txt header 2026-11-21 + a "NEW IN 2026-11-21" section (plain English, no
   em-dashes, semicolons, emoji, ellipsis, intensifiers, numbers from RESULTS files only), checked against the LAN
   manifest. Draft GitHub notes in the same voice.
6. Do NOT swap stage/release, deploy, or create a GitHub release. Results verify/mods_release_1121/RESULTS.md (draft),
   the zip path, the notes file path, STATUS re/sessions/STATUS_relprep.md.

Rules: windowed game, posted input or Frida only, kill only PIDs you started, test slot, delete BMP dumps, no git add /
commit.
