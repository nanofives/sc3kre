# firedist results (round 2026-11-23c): the distorted parking side of the converted Large Fire Station

Owner 2026-11-23: "the geometry of the fire station has a weird distortion on the parking side" (sheet
`verify/sc4cmp/forum/18_large_fire_station.jpg`, SC3 side and in-city strip). SC4 install read in place. Pictures with
SC4 art are local only (`owner_shots\`, `work\`, both gitignored). No code changed, no game run, no BMP written.

**Verdict.**

- **Not the civlot turn.** The turned look (2x3, as installed) and the same model on its unturned 3x2 lot give the same
  frames with the slot numbers moved by one: turned slot t = unturned slot t + 1, alpha equal on all 8 frames of zooms 3
  and 4 (1 pixel of 64,000 differs at z4 t3). The colour differences that remain (10,700 to 15,800 pixels at zoom 4) are
  the lot rim, which is lit by world axis, and the 255-colour palette cut. The installed frames are byte for byte this
  session's turned render. No mirror and no wrong rotation sign: in every slot the two walls are the walls of the SC4
  view the slot is built from (owner_shots 01, 02).
- **Cause: SC4's own view mesh puts the bay-door wall at the eave line, about 4 m in front of the doors, and view E
  paints the covered apron floor onto it.** The sheet's SC3 frame is turned slot 3 = unturned slot 0, built from SC4 view
  E (the sheet's SC4 picture). In that view the bay-door wall is the plane z = 15 m, 0 to 10.9 m high, seen at 67.5
  degrees. The doors stand under the roof behind that plane: the yellow apron paint on the plane stops at 4.25 m in view S
  (the ray reaches the ground 3.9 m behind the plane) and at 9.75 to 10.25 m in view E (3.8 to 3.95 m behind). Two views,
  one depth: a covered apron about 3.8 to 3.9 m deep. So in view E 9.75 of the plane's 10.9 m show apron floor, the truck
  and the flags, and the doors do not show. SC3 draws that picture on a vertical plane under the eave: the apron
  continues up the wall to the roof (owner_shots 03, view E panel against view S).
- **A second band on the next side, same family.** Turned slot 2 = unturned slot 3, from view S. SC4's mesh for that view
  closes the +x side with faces that lean out from the wall foot (x = 15 m) to the eave edge (x = 17.85 m at 10.89 m),
  normal (0.97, -0.25, 0). View S sees them at 85 degrees from their normal (n.c = 0.086), SC3 at 62 degrees (n.c =
  0.469): **3.5 to 3.9 SC3 zoom-4 pixels per SC4 texel**, 5,173 pixels (14.4% of the frame's building faces) drawn from
  about 1,100 texels. Every other face of the 16 civic, reward and landmark models measured here is at most 2.1, mostly
  0.6 or 1.5 (owner_shots 04, view S panel).
- **The 1.48 stretch every converted building has.** In each SC3 slot one wall comes from a view that saw it at 67.5
  degrees: measured 1.42 to 1.59 SC3 pixels per texel on the fire station, 1.73 on its -x wall, against 0.62 on the other
  wall (theory: (cos 45 x 5.66) / (cos 67.5 x 7.0) x (cos 30 x 5.66) / (cos 45 x 7.0) = 1.48). That is the known limit of
  the `match` rebuild (SC4_FORMATS 7). On its own it blurs, it does not move things. Here it lands on a wall that is not
  where the SC4 picture has it, so the error shows.
- **Other looks: no such band.** Small Police Station, Large Medical Center, Ranger Station, Soccer Field (the other 4
  turned looks) and Elementary School (not turned) rendered both ways; Small Fire Station, Medical Clinic, City Museum,
  Local Branch Library, Faneuil Hall, Alamo, Independence Hall, Mayor's House, Main Library, Courthouse, City Hall
  measured from round forumshots' conversion. Pixels from faces at 2.5 or more pixels per texel: 0 to 57 per slot on all
  of them, except Large Medical Center slot 0 (3,370, 2.0%, one face with no texels, not looked into). Turned against
  unturned: equal silhouettes on all five turned looks.

## 1. Four ways, zoom 3 and 4

`work/renderall.py`: the six buildings converted with this worktree's `sc4conv.py --growables --all --only ...`
(baked_sharp default; the fire station's OBJ and four view textures are byte for byte round forumshots'), rendered by
`bldimport.render_one` on the unturned lot and, for w > d, through `turned_model`. Each picture: row 1 SC4 views E N W S,
row 2 unturned slots 0 1 2 3, row 3 turned slots 3 0 1 2, so every column is one SC4 view and the two SC3 frames built
from it.

| SC4 view | unturned slot | turned slot | left wall in SC3 | right wall in SC3 | which one is bad |
|---|---|---|---|---|---|
| E | 0 | 3 (the sheet) | -x (tower, windows), view E sees it at 22.5 | +z (bay doors), view E at 67.5 | right: apron floor on the door plane |
| N | 1 | 0 | -z (back, windows) | -x | none |
| W | 2 | 1 | +x (side windows) | -z | none |
| S | 3 | 2 | +z (bay doors), view S at 22.5 | +x, view S at 85 (leaning faces) | right: 3.5-3.9 px per texel smear |

## 2. Numbers

`work/faces.py` (every face: normal, extent, SC4 texels, SC3 pixels), `work/stretch_summary.py` (per model and slot),
`work/unfold.py` (a wall plane laid flat, sampled from each view through its fitted projection, fit 0.45 to 0.56 px),
`work/recess.py` (apron paint per height on the door plane).

Fire station, unturned, largest faces of the two bad slots:

| slot (view) | face | normal | y (m) | x (m) | SC4 texels | SC3 z4 px | px per texel |
|---|---|---|---|---|---|---|---|
| 0 (E) | f49 | +z | 0.74-10.90 | -16.16-4.70 | 1,407 | 2,080 | 1.48 |
| 0 (E) | f5 | +z | 0-10.89 | 4.70-17.85 | 774 | 1,101 | 1.42 |
| 3 (S) | f42 | (0.97, -0.25, 0) | 1.67-10.89 | 15.44-17.85 | 241 | 937 | 3.89 |
| 3 (S) | f50 | (0.97, -0.25, 0) | 0-10.89 | 15.00-17.85 | 255 | 902 | 3.54 |
| 3 (S) | f49 | (0.97, -0.25, 0) | 0-10.89 | 15.00-17.85 | 165 | 647 | 3.93 |

Apron paint on the plane z = 15 (x -11 to 4.5 m, the four bays): view S 36% at 0.75 m, 8% at 3.75 m, 0% from 4.75 m;
view E 30-32% up to 2.25 m, 6-12% up to 9.25 m, 2% at 10.25 m. SC3's own camera (slot 0, elevation 30) looking into a
3.9 m recess would show the floor on the lowest 3.2 m of the plane (a ray drops 1 m per 1.22 m of depth: 3.9 / 1.22).

## 3. Proposal (not built)

**Per face, take the texels from the view that sees that face at 22.5 degrees when the slot's own view saw it nearly
edge-on.** A rule such as: a front face whose SC3 pixels per SC4 texel is above 2.0 (or whose plane is the 67.5-degree
wall and carries ground paint above the bottom quarter) is re-textured from the view that sees it frontally, uv by that
view's fitted projection (both meshes share the model frame). Mock, offline only (`work/mock_frontal.py`, 28 faces of the
fire station moved: the +z door plane of slot 0 to view S, the leaning +x faces of slot 3 to view W), owner_shots 05:

- slot 3 of the sheet: the four arched bays and both trucks show on the door wall instead of apron floor.
- slot 2: a brick wall with two rows of windows instead of the dark smear.
- costs seen in the mock: a white seam strip at the tower corner and a ghost of the chimney top where view S's outline
  meets view E's, the wall still stands at the eave line (no apron under the roof, which SC3 would see over the lowest
  3.2 m), and the doors carry view S's light. This is the `frontal` rebuild's known seam problem (SC4_FORMATS 7), here
  on 2 faces' worth instead of the whole building.

Other routes, cheaper and weaker: (a) leave it and drop the fire station from the forum set (the measurement says no
other converted civic look has it); (b) only for the leaning faces, a vertical stand-in at x = 15 m textured from view W.
A blend of two views was not tried: on the door plane the two views disagree on content (doors against floor), so a blend
would show both.

## 4. Checks

- No code changed in `dev\firedist\wt` (git status clean), so no suite run was needed. The work scripts read the
  worktree's `bldimport.py` / `bldrender.py` / `sc4conv.py` unchanged.
- No game run: the frames the game draws are bldimport's frames, and the installed ones were compared byte for byte.
- Seen in passing, not looked into: Large Medical Center slots 0 and 1 show parked cars at mid-wall height; the Soccer
  Field shows no pitch markings (SC4 view of the goal posts only, lot paint not visible at this scale).

## 5. Pictures (`owner_shots\`, local)

| file | what |
|---|---|
| 01 | Large Fire Station zoom 4: SC4 views E N W S over unturned slots 0-3 over turned slots 3 0 1 2 |
| 02 | the same at zoom 3 |
| 03 | the door plane z = 15 laid flat, as each SC4 view paints it (S frontal: doors; E: apron floor to the eave) |
| 04 | the side plane x = 15 laid flat (W frontal: windows; S: the smear) |
| 05 | mock: as installed against the frontal source, turned slots 3 (the sheet) and 2 |
| 06_* | the other four turned looks and the Elementary School, same layout as 01 |
