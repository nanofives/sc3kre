# Round 2026-11-18: style mix switch + faster highway vehicles (Simtropolis feedback)

Orchestrator: "SC3 Simtropolis feedback triage (Wine patch, land value 255, avenues, UI rescale)".
Rules: `re/sessions/CHILD_PROTOCOL.md`. Workspaces made from main 1f3bd98 (release sc3mods-2026-11-18, base
`stage\release` = LAN 2026-11-18).

| stream | player report (Simtropolis, 2026-11-17/18) | expected |
|---|---|---|
| stylemix | NicoMT: "is it possible to disable the building region style mix? ... it would be useful if it could also be disabled, like the rest of the features included in this mod, in case you want to maintain a consistent building style" | a "Building style mix" row on the Turn mods on/off page, default on (today's behaviour), env switch, cities with mix buildings keep loading |
| hwyspeed | Spamoidutout: "a feature that would be neat is to have vehicles going faster on highways" | how the game sets vehicle speed per network (the animated cars and the trip simulation), then a proposal with an off switch |

The reply already posted promises both as "next" (draft `.happy-share/.../simtropolis_post_1118.html`).

## stylemix

Background: memory note `project-building-styles-mixing`, `re/analysis/BUILDING_PICK.md`, package
`re/tools/netmod/examples/style_mix` (netpack `style_sets`: European set e523f3fb as ids +400000, Asian 6523f3d5 as
+1500000, weight 1 each, art in `mods\netmod\overlay\Apps\Res\Sprites\5432D60E_netpack_set.DAT` / `547B7DF5_...`), the
growables path (BUILDFAM.IXF families, `Key: 1406,545184782,<id>,<weight>`, parser 0x10001250, `[OccAttribCache]`).
Today the mix stops only with the whole road mod ("Avenues and highways" row, `resize.mt_netmod`).

Do:
- Find the cheapest switch that stops NEW mix buildings from growing while the existing ones in a save keep loading,
  and if possible keep their look (exemplars and art still served, only the family Key lines or weights dropped).
  Say which of these it achieves, with evidence. A stock-like fallback (they become a game building of the same type,
  as without the mods) is acceptable if keeping them is not cheap. Never a crash on load.
- Row "Building style mix" in the Features column of the Turn mods on/off page (sc3resize.c MODTOGGLE, memory note
  `project-modtoggle`), default ON, env switch (e.g. `SC3NETMOD_STYLEMIX=0`), text in all 7 languages
  (`re/harness/lang/*.txt`, `py re/tools/sc3lang.py convert --apply | check`).
- Test light (owner rule): a default-style city (Sacramento) for some game months with the row on and off, count new
  growables in the +400000 / +1500000 ranges from the saves, and load a save that has mix buildings with the row off.
  Pictures phone-sized in `verify/stylemix/owner_shots/`.

Model / effort: opus / medium.

## hwyspeed

Background: memory notes `project-highway-trips` (first-arrival walk, ramps hold 0 traffic, RAMPFIRST doubled highway
share) and `project-highway-program`. Retail CodeView symbols name the exe (`original/retail_2.0.949/cv_functions.tsv`,
`cv_vtables.tsv`), DLL exports carry the tracker names, iOS names are hints (`re/ghidra_export_ios`).

Do:
- Static first: where the animated vehicles (automata) get their speed per network type (road, highway, avenue pieces,
  rail), and whether the trip simulation (travel time / cost per network) has its own speed. Cite RVAs.
- Then measure in game (posted input, Frida reads): a car's screen or cell speed on a highway against a road, sim
  running, same zoom.
- Report what "faster on highways" can mean in each layer (looks only, trip choice, both), what each would change
  for the player, and a proposal. Implement only the part that is a clear constant or table with a visible effect,
  behind an off switch and default OFF until the owner has seen a before / after GIF. Anything that changes trip
  choice needs the orchestrator's OK first (it moves traffic and RAMPFIRST's measured shares).
- Notes in `re/analysis/VEHICLE_SPEED.md`, results in `verify/hwyspeed/RESULTS.md`.

Model / effort: opus / high.

## Rules (both)

Windowed game, posted input only (never the real mouse, keyboard or foreground), test slot for long runs, kill only
PIDs you started, delete BMP dumps once converted, STATUS file at every milestone, no `git add` / `git commit`.
English text in the gallery-style pictures is not needed here, the owner reads Spanish UI fine.
