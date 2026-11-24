# Round 2026-11-24: artifacts on converted SC4 buildings (thin props as grey slabs, floating shards)

Orchestrator: "SC3: pending items after recent rounds + SC4 style status". Rules: re/sessions/CHILD_PROTOCOL.md.
Owner 2026-11-24: "I still see artifacts on most SC4 buildings in the post". Crops of the SC3 frames of four sheets:
verify/forumshots/owner_sc4_artifacts.jpg (Mayor's House, Hagia Sofia, Alamo, Small Police Station; sheets in
verify/sc4cmp/forum/13, 14, 04, 01). Seen:
1. Thin props drawn as tall grey / white opaque panels instead of thin objects: the lamp posts of the Mayor's House
   and the Small Police Station; the police patrol cars read as white blobs.
2. Floating shards: a white sliver in the air left of Hagia Sofia's minaret by the dome, a flat white wedge on its
   right minaret, a loose fragment on the Alamo's ruined right side.
3. Stretched side walls (Alamo right half, Hagia Sofia buttresses): the known 45 vs 30 degree limit. Out of scope
   unless a cause other than the camera shows up.
Earlier work: verify/sc4props, sc4trees (peel until no open sample), sc4ground, firedist (edge-on faces k >= 3.0,
hand table, S3D vertex formats), bakedsharp. Formats: re/analysis/SC4_FORMATS.md.

## Stream sc4art (opus / medium)

1. For each artifact above, find which mesh, prop, texture or render step makes those pixels (trace the frame pixels
   back to the face / prop row / view, as firedist did). Measure, do not guess.
2. Categories 1 and 2: fix them in the converter and the page (Python = page byte for byte) when the cause is a
   converter fault (alpha not read, prop billboard drawn without its mask, wrong view for a prop, mesh pieces outside
   the model's own outline, peel limits, etc.). If a cause is inherent, say so with evidence.
3. Count over the full install conversion how many models change. Every non-SC4 golden byte identical.
4. Re-make every forum sheet in verify/sc4cmp/forum/ whose frames change (in-city strips from new game frames only
   where the frame changed), look at each one, and give before/after crops of the four buildings above.
5. Full suite (CHILD_PROTOCOL suite modes), sync_css.py --publish if the page changed, guide line only if a stated
   limit changes. Results verify/sc4art/RESULTS.md, STATUS re/sessions/STATUS_sc4art.md.

## Rules

SC4 install read in place, EA content never in git or docs. Windowed game, never the real mouse or keyboard, test
slot, harness claim before game runs, kill only PIDs you started, delete BMP dumps, no git add / commit.
