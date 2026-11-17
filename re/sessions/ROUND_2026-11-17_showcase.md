# Round 2026-11-17: showcase gallery of every junction the road mod builds (for Simtropolis)

Orchestrator: "SC3 Simtropolis feedback triage (Wine patch, land value 255, avenues, UI rescale)".
Rules: `re/sessions/CHILD_PROTOCOL.md`. Base: the staged build 2026-11-17b (stage/release), main 73826b8.

## Owner request (Mariano, 2026-11-17)

"can you launch a child to build a gallery of ALL the intersections you have built in this mod to showcase on
simtropolis?"

## What "all" means

Every junction / network piece family the road mod (sc3netmod + its packages) draws, not only this week's rounds.
Start from the installed package list (`stage/src/mods/netmod/ledger.json`, 26 packs) and each pack's README /
manifest under `re/tools/netmod/examples/<pack>/`, plus the netmod blocks in `re/harness/src/sc3netmod*.c`. Expected
families (check, do not assume): avenues (2 lanes each way, one-way halves) and their T / cross / corner / U-turn ends
/ merges / taper into a road; boulevards (3 + 3) and their junction boxes / corners / slopes; avenue and boulevard
diamonds; diagonal avenues and diagonal boulevards with every junction (crossings, T, corners, bends into a road,
diagonal x diagonal boxes); rail level crossings and highway underpasses on straight and diagonal bands; roundabouts
(2x2 automatic, closed quarter, big roundabout); highway pieces (cloverleaf, diagonal cloverleaf, trumpet, x
cloverleaf, s-curve, on-ramps incl. the case 80 diamond beside a diagonal avenue, slopes, ask / capped joins); road
slope ends. Write the inventory first (`verify/showcase/INVENTORY.md`: family, pack, what to build) and send it to the
orchestrator before shooting.

## How it should look (it is for players, not a regression)

- English game text (memory reference-english-screenshots: English-UK text swap in your tree, SC3MODS_LANG=en).
- No HUD in the shots (the hide-UI toggle, memory project-uitoggle-hide-ui, or FRAMEDUMP of the view only).
- Each junction in a believable setting: a flat or gently rolling map with some zoned and grown buildings around, not
  a bare grass sandbox. Cars moving (sim running) where traffic exists. A copy of a shipped city or a developed
  sandbox, your call, in YOUR tree only.
- Per junction: one close-up (zoom 4) and one wider view (zoom 3); the best camera rotation for each (views 0-3).
- A few animated GIFs of traffic through the best junctions (short, under ~5 MB each).

## Deliverables (in `verify/showcase/`)

- `shots/<family>/<nn>_<name>_z4.png` and `_z3.png`, full resolution, plus forum copies 1280 px wide as JPEG
  (quality 88) in `forum/`.
- `sheets/<family>.jpg`: one contact sheet per family, labelled tiles, phone-readable (<= 1400 px wide).
- `gifs/*.gif`.
- `CAPTIONS.md`: one caption per image, ENGLISH, written for players: facts only, what the junction is and how to
  build it (which drag makes it), no adjectives / intensifiers, no em-dashes, no semicolons, no emoji, no ellipsis,
  never invent a number (these go out under Mariano's name).
- `INVENTORY.md` (above).
- Phone-sized JPEG previews of the sheets to the orchestrator as you finish each family.

## Owner decisions 2026-11-17

- "Yes, reshoot": transport-only on the flat xsect sandbox, each junction alone, 6-row arms, GIFs without traffic.
  (He had asked why the child grew buildings when the gallery is about transport.)
- "Yes, investigate": the 17 diagonal junctions that broke in the developed city (arms cut to 4 rows) go to diagfix
  in `dev/diagarm` as a player-facing bug class.
- Rotation leak found by this child (ISSUES.md item 1) -> child rotleak: stock SIMSPR extra AddRef in
  PrepareImage, made ~5x worse by sc3perf's sprite budget; fix SPR_IMGREF in progress.

## Rules

- No code or package changes: this is shooting what the build ships. If a junction looks broken in the showcase
  setting, do NOT fix it: note it in `verify/showcase/ISSUES.md` with a picture and tell the orchestrator.
- Never take over the real mouse or keyboard (posted messages / Frida game calls only), windowed game, test slot for
  long runs, never kill by name, delete BMP dumps once converted.
