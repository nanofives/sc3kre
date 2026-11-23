# STATUS firedist (round 2026-11-23c)

## goal
Owner: the converted Large Fire Station has a distortion on the parking side (sheet 18). Find the cause, fix or propose.

## verdict
Not the civlot turn: turned frames = unturned frames with the slot moved by one (alpha equal, zooms 3 and 4); the
installed frames are byte for byte the turned render. Cause: SC4's view mesh puts the bay-door wall at the eave line
(plane z = 15 m), about 3.9 m in front of the doors (apron paint depth measured from views S and E). View E, which the
sheet's slot is built from, paints the covered apron floor over 9.75 of the plane's 10.9 m, and SC3 draws it on a
vertical plane. Next slot (view S): leaning eave faces at 3.5-3.9 SC3 px per SC4 texel (every other face of 16 models:
<= 2.1). No other converted civic look has it. Detail: verify/firedist/RESULTS.md.

## built
Nothing in the converter. Offline mock of a per-face frontal source (work/mock_frontal.py), owner_shots 05.

## proven game-side vs static only
Renderer frames only (the game draws bldimport's frames, compared byte for byte). No game run.

## blocked on
Nothing. Owner / orchestrator call: build the per-face frontal source (with its seams), or leave it and drop sheet 18.

## files owned
- verify/firedist/RESULTS.md (tracked)
- re/sessions/STATUS_firedist.md
- local only: verify/firedist/work/*.py, verify/firedist/owner_shots/*
- dev\firedist\wt: no changes

## game-harness need
None.

## asks of other sessions
None.
