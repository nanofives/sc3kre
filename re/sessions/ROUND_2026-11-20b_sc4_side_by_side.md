# Round 2026-11-20b: side-by-side pictures, SimCity 4 against SimCity 3000

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md.
Owner (2026-11-20): "i want better images, a side by side of sc4 and sc3 buildings converted", for the Simtropolis
buildings post. Owner call the same day: pictures of SimCity 4's OWN (Maxis / EA) buildings may go in forum posts,
community SC4 buildings may not (memory: project-sc3kre-publish-policy). The post today:
verify/showcase/site/make_st_post_buildings.py -> .happy-share/cmwgg6bdp01jhmz1b3kp9os44/simtropolis_buildings_post.html
(6 SC4 pictures, all plain game crops). The only earlier comparison sheet is small and dull:
verify/sc4conv/owner_shots/04_sc4_look_vs_converted_zoom4.jpg (verify/sc4conv/work/shots_offline.py, JMyers, not
publishable).

## Stream sc4cmp (opus / medium)

1. Forum-ready side-by-side pictures, one building per picture (or two per picture if they read well at 1280 px
   wide), left "SimCity 4", right "SimCity 3000", same side of the building, same scale where the two cameras allow,
   readable names, no lab wording (no "frame match", "slot", "view S", ids). A neutral background that suits both
   games. 1280 px wide at most, JPEG.
2. The SimCity 4 side should look like SimCity 4: the building as SC4 draws it, with its lot props and lot textures
   where the converter has them. Suggested route: the converter already builds the building, props and lot textures
   as boxes painted with SC4's own pictures, and those pictures were made for SC4's camera, so drawing the same model
   through SC4's camera (re/tools/sc4conv/reproject.py has the camera math) gives SC4's look. Check it against SC4's
   own view pictures and say how close it is. If a real SC4 screenshot route is practical (SC4 runs windowed with
   -w, no real mouse or keyboard ever), say what it would take, but do not depend on it.
3. The SimCity 3000 side: the converted building as the game draws it (the bldrender frame the game shows, zoom 4,
   with the SC3 lawn, props and lot textures), and where an in-game picture already exists
   (verify/sc4civ, sc4lottex, sc4ci owner_shots) a third, in-game column is welcome.
4. Buildings (all SimCity 4's own, from the install): Small Police Station, Small Fire Station, Mayor's House, Gazebo
   or another park, Courthouse or another reward, a landmark, Small Shops, Retail Stores, Lam Banking, Ferrrara Inc.,
   Eyler Refining, Vilett Textiles, Lee Avionics, Pumpkin Acres. Pick the best 8 to 12 for the post and say why.
   Also one picture with all four view rotations side by side for one civic building.
5. Output: verify/sc4cmp/forum/*.jpg (local only, never in git or docs), a script that rebuilds them
   (re/tools/sc4conv/compare_sheet.py or verify/sc4cmp/work, your call: no EA data in it), verify/sc4cmp/RESULTS.md with
   the list and captions written in plain English (no em-dashes, semicolons, emoji, ellipsis, intensifiers), so the
   orchestrator can put them in the post.

## Rules

SC4 install read in place (C:\Program Files (x86)\Steam\steamapps\common\SimCity 4 Deluxe\), EA content never in the
repo, docs/ or a release. No community buildings in the forum set. No git add / commit. Kill only PIDs you started.
