# STATUS firedist (round 2026-11-23c, second pass: build the per-face rule)

## goal
1. Per-face rule: faces the slot's SC4 view saw edge-on are drawn from the view that sees them most head-on
   (owner "build per-face rule"), plus a hand table for the fire station's door wall (owner call (b)).
2. Side findings: Large Medical Center floating cars, Soccer Field pitch lines.

## verdict
- Rule built in sc4conv (views.edge_on / hand_picks / edge_faces / edge_mask / toned, sc4conv.write_edge) and the page
  (sc4web.js edgeOn ... edgeMask), byte for byte (parity.mjs: 148 + 91 files, 0 differ). k >= 3.0, the substitute view
  must see the face (occlusion test against its own mesh), the copy is 1 cm in front, toned by the measured SC4
  right-wall / frontal ratio (0.5371 / 0.5622 / 0.7133), and its texels are cleared where the slot's own picture has no
  building (so it never draws outside the outline).
- Hand table: HAND_FACES keyed by building tgi + model key of the Large Fire Station, slot 0, plane +z = 15 m, view S.
- Medical Center: the floating cars stand on a 5-storey parking garage prop the converter dropped (S3D vertex format
  0x00000002). s3d.py / sc4web.js now read 0x00000002 and 0x00140002 (same 20-byte layout, install scan). Fixed.
- Soccer Field: pitch lines are pale paint the lawn test clears; no rule separates them (measured). Left (owner (a)).

## built
re/tools/sc4conv/views.py, sc4conv.py, s3d.py; re/tools/bldimport/sc4web.js; webtest/sc4_install_set.json (+2).

## proven game-side vs static only
Renderer frames, parity, suite 41 of 41, non-SC4 goldens = main. In game: Madison (fire station, 4 rotations) and the forumshots Berlin save (06, 07), windowed, PIDs 15444, 21304, 25060 started and stopped by this session.

## blocked on
Nothing.

## files owned
- dev\firedist\wt: re/tools/sc4conv/views.py, re/tools/sc4conv/sc4conv.py, re/tools/sc4conv/s3d.py,
  re/tools/bldimport/sc4web.js, re/tools/bldimport/webtest/sc4_install_set.json, docs/buildings/index.html,
  docs/buildings/importer/sc4web.js
- MAIN, local: verify/bldpack/work/guide_template.html (old copy .pre_firedist), verify/sc4cmp/forum/06, 07, 18 (old
  copies *_pre_firedist.jpg)
- verify/firedist/RESULTS.md (tracked); verify/firedist/work, owner_shots (local)

## game-harness need
Done (claimed and released).

## asks of other sessions
None.
