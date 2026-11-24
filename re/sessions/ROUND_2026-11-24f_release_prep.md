# Round 2026-11-24f: prepare the next sc3mods release (do not publish), then re-take the style-pick picture

Orchestrator: "SC3: pending items after recent rounds + SC4 style status". Owner 2026-11-24: "Prepare it" (publishing
waits for his OK), and for the forum post: "Re-take after release, and make sure that there's not a lot of abandonment
and garbage on the pictures". Latest published: sc3mods-2026-11-21 (verify/mods_release_1121/RESULTS.md, recipe there).

Changes on main since sc3mods-2026-11-21 that reach the release:
- pw1024: sc3bigcity GRIDCAP (power 600 / water 500 flood caps scale above 256 cells), verify/pw1024/RESULTS.md.
- lotgrowb: sc3simrun LOTGROW (non-square zoned buildings, 9 SIMRCI rule slots), sc3resize mods page row "Non-square
  zoned buildings" + left-column row spacing 15 -> 14 px, lang keys, verify/lotgrowb/RESULTS.md.
- stylepal: style_mix 1.3.0 (lot colours of style copies, new 2627D60E_netpack_set.DAT 13.7 MB recoloured EA pixels,
  same kind as the two set DATs shipped under the owner's exception), verify/stylepal/RESULTS.md "Stage source for the
  next release".
- Importer / converter work (bakedsharp, civlot, firedist, sc4art, darktone, objprops, lotgrowb importer side) is live
  on GitHub Pages already, not in the zip.

## Stream relprep2 (opus / medium)

1. stage/src: back up mods\netmod, then `netpack.py uninstall style_mix` and install style_mix 1.3.0 from main (each step
   re-merges all packages, 14-20 min each: run in the background with a long timeout). Check overlay_base.txt.
2. Build every changed mod from main into stage/build_<label> (build_mod.ps1, clear CL): at least sc3bigcity,
   sc3simrun, sc3resize, plus anything else whose source changed since 08c0357 (check git diff). bins = previous bins +
   them + the 7 lang tables (sc3lang check 0 missing). stage_lan_release.py ... --out stage/release_<label>, compare
   manifests with stage/release (list every changed file and why). Label: the date you finish (2026-11-24 or -25).
3. Smoke test in a tree from the new stage with the shipped DLLs (sc3dev new <x> -Base stage/release_<label> -NoBuild):
   - Berlin and Sacramento start + load, log lines of GRIDCAP, LOTGROW (9/9 armed), style_mix 1.3.0 in the netmod log;
     VEH lines explained.
   - A 1024 city (Europolis 1024 or verify/pw1024's repro save): power and water reach end to end.
   - The mods page (both pages) in Spanish and English with the new row, a picture each, nothing overlapping
     (lotgrowb changed the left-column spacing and took no picture: look closely).
   - A few minutes of growth in Sacramento with the style pick European: the new lot colours show.
   Any crash: stop and report.
4. Jotti every changed DLL (0 / N expected).
5. Zip from the 2026-11-21 zip tree with the changed DLLs, Apps/sc3lang, the changed mods/netmod files (style_mix 1.3.0
   tables and art, overlay files the reinstall changed), README.txt header + "NEW IN <label>" (plain English, VOICE
   rules: no em-dashes, semicolons, emoji, ellipsis, intensifiers, numbers only from RESULTS files), checked against
   the LAN manifest. Draft GitHub notes in the same voice.
6. Do NOT swap stage/release, deploy, or create a GitHub release.
7. Forum picture (in the prepared release tree, after step 3): re-take the style-pick before/after like
   verify/forumshots/style_pick_before_after.jpg (Sacramento, same camera idea, European picked, Mix off) with
   style_mix 1.3.0. Owner: no visible abandonment or garbage. Pick a healthy area (check the frames for abandoned
   buildings, the crime / garbage data views or rubble before choosing the camera), keep power, water and services in
   place, and if the stock churn run needs it, Sandbox (no abandonment) on for the run, and say so in the caption notes.
   Look at every frame. Output verify/relprep2/style_pick_before_after.jpg + notes.
   Results verify/mods_release_<label>/RESULTS.md (draft), zip path, notes path, STATUS re/sessions/STATUS_relprep2.md.

Rules: windowed game, posted input or Frida only, kill only PIDs you started, test slot, harness claim, delete BMP
dumps, no git add / commit.
