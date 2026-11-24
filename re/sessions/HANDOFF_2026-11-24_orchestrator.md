# Handoff 2026-11-24 (orchestrator "SC3: pending items after recent rounds + SC4 style status"), before the LIVING-PC token-leak reboot

Safe point: nothing of mine is running. main pushed through 1b8c9913 (+ this file). Latest release still
sc3mods-2026-11-21. Merged on main since then (not released): bakedsharp, civlot, firedist, sc4art, darktone (all
importer / converter, live on GitHub Pages), pw1024 (sc3bigcity GRIDCAP: power and water reach across 1024 maps, needs
a mods release to reach players), lotgrow research (LOT_SHAPES section 11).

## Children (claude2), told to reach a safe point and write their STATUS before the reboot

| child | session | brief | state |
|---|---|---|---|
| objprops | cmwus2lhl3bfvp115i6wqhbt5 | re/sessions/ROUND_2026-11-24c_obj_lots.md (stream objprops) | game props on OBJ lots, then re-render sample pack pictures (bldpack owner_shots 00 + 13) for the post. STATUS_objprops.md |
| lotgrowb | cmwuss0o73i9dp115ns7bb82l | re/sessions/ROUND_2026-11-24d_lotgrow_build.md | non-square growables full version. Milestone 1: sc3simrun LOTGROW, 9 rule slots armed, lockstep VERIFY identical in Sacramento (1,487 / 1,487); next Europolis 1024 VERIFY, then non-square install; importer side only after objprops merges. STATUS_lotgrowb.md |
| stylepal | cmwtwvnef2fqhp115jbnecchd | re/sessions/ROUND_2026-11-23d_style_palette.md | idle, waiting for the owner's lot colour pick (card: swap yard lots + c / swap only / c / b, and reverse direction yes/no). verify/stylepal/RESULTS.md |

After the reboot: resume children if stopped (memory reference-resume-stopped-children), merge each when it reports
(commit in its wt with git add -u / -f, merge --no-ff, records with -f, push, sc3dev remove, close_child).

## Waiting on the owner

1. Lot colour option for style copies (stylepal), both directions or NA cities only.
2. Whether to prepare a mods release (pw1024 GRIDCAP + later LOTGROW).
3. Posting the Simtropolis draft: .happy-share/cmwgg6bdp01jhmz1b3kp9os44/simtropolis_post_1123.html + _links.html
   (generator verify/showcase/site/make_st_post_1123.py). Rebuild it after objprops re-renders the sample pack
   pictures (the generator reads verify/bldpack/owner_shots/00_whole_pack_z3.jpg and 13_berlin_skyscraper_zoom3.jpg).
   Lines in it speaking for the owner to confirm: night mode "wish list, no promises", networks answer, "@SC4 gamer".
   Possible additions: the 1024 power / water fix (player paragraph in verify/pw1024/RESULTS.md) once released.

## Leftovers

dev\nopause and dev\civlot: one locked log each, delete after the reboot. BOARD.md "Current state 2026-11-23" lists the
open items (STRTSIM crash under churn seen once, civlot unchecked items, firedist done).

## Children at their safe points (both reported before the reboot)

- objprops: props built (BA prop library Apps\Res\BA\PROPS read from the player's install, paved lots for shops /
  offices / industry, `x_props` switch), Python = page on 80 frames, sample pack 236 props, new overview
  verify/objprops/work/whole_pack_z3_new.jpg. Left: Berlin skyscraper picture (load last autosave), full suite (new
  goldens for OBJ growables), *_pre_objprops copies, sync_css --publish, RESULTS.md. Commit note: bldprops.py needs -f;
  docs/buildings/index.html picked up a baked_sharp line from the shared guide template (darktone's, expected).
- lotgrowb: sc3simrun LOTGROW built, lockstep VERIFY identical (Sacramento 1,487 / 1,487, Europolis 1024 99,891 /
  99,891; dense commercial 0x1000c3eb not exercised yet). Test pack 38000-38005 installed in its tree. Left: sc3resize
  rebuild for the mods page row, non-square growth runs (Sacramento, Berlin, Madison), importer side after objprops
  merges, suite, RESULTS.md.
