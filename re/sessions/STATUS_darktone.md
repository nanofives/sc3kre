# STATUS darktone (round 2026-11-24b): protect dark tones in the baked style

## goal
SC4 police cars read as white blobs under the baked tone (y' = 1.33 y^0.75). Keep the cars' dark panels dark,
move the rest least, trees not darker.

## verdict (DONE)
`tone_toe = (1.0, 0.08, 0.20, 0.0, 0.02)` in `baked` / `baked_sharp` (baked_raw* unchanged), **SC4 prop materials
(sc4p_*) only**: protection = (1 - smoothstep(y / 1.0)) x saturation ramp (1 at s <= 0.08, 0 at >= 0.20) x green-lead
ramp (1 at G - max(R, B) <= 0, 0 at >= 0.02); y' = y2 + protection (y - y2). Evidence and numbers:
verify/darktone/RESULTS.md.

## built
- re/tools/bldimport/bldrender.py (`_tone_toe`, STYLES), re/tools/bldimport/bldweb.js (same float32 order),
  docs/buildings/importer/bldweb.js (sync_css.py --publish), docs/buildings/index.html (one clause on baked_sharp).

## proven
- Full suite normal mode with the final curve: 41 of 41 (`dev\darktone\suite_full.log`, wall 1,180 s, peak 5.8 GB on
  the earlier run so the final one ran with PROYECTOS_TEST_MEM_GB=7). Doc line: SUITE_CHANGED=1 39 of 39.
- Non-SC4 goldens vs main: 1,238 same, 46 differ = meta.json render key only (hashes bldrender.py), 0 frames.
- JMyers fit set: 96 of 96 frames byte-identical (no props there).
- Cars (parking rows): darker than 90 6.0% -> 11.0% (SC4 tone 26.8%), median 162 -> 149.
- Vegetation, palette off: greens darker > 8 at 0.28-0.73% on the tree-heavy lots.
- Game side: 17 forum sheets re-made from new in-city frames (dev\darktone\tree, Madison + forumshots' saves).

## blocked on
nothing

## files owned
re/tools/bldimport/bldrender.py, re/tools/bldimport/bldweb.js, docs/buildings/importer/bldweb.js,
docs/buildings/index.html, verify/darktone/RESULTS.md, re/sessions/STATUS_darktone.md
(local only: verify/darktone/{owner_shots,fd,runs,p50t,p100t,logs}, verify/sc4cmp/forum re-made sheets, dev\darktone\work)

## game-harness need
none now (released)

## asks of other sessions
none. Note for the orchestrator: the 255-colour palette re-pick moves a few pixels both ways on any art change (bushes
look a little different with the palette on, unchanged with it off, owner_shots/04).
