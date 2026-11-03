# Round 2026-11-03: owner feedback on sc3mods-2026-11-03
Orchestrator: "SC3 graphs tabs + Vida util/restore/query UI round". Rules: re/sessions/CHILD_PROTOCOL.md. Workspaces from main b200b92.
New UI text: SC3TR(es,"<mod>.<key>","es","en"), then `py re/tools/sc3lang.py convert --apply | extract | check`, add fr/de/it/nl/sv.

| stream | owner report (2026-11-03) | expected |
|---|---|---|
| placehints4 | "without shift it should hide the area affecting a ploppable building"; "is it possible to add public transport to the shift visualization?" | halo only while Shift is held; transit in the Shift view (proposal first) |
| uipolish | "pause music on loss of focus"; Vida Util footer (shot .happy-uploads\image-1793717000484.png): "add a continuous stripe at the bottom so it doesn't look the blue area disconnected" | music pauses when the game window loses focus and resumes on focus; one continuous light-blue strip under the footer buttons |
| stationwarn | "add an indicator when a station of any kind can't receive passengers because it's poorly connected" | find the game's rule for a station receiving trips (rail/subway/bus/elevated, ports?), flag the ones that fail it on the map with a clear in-world marker (+ "?" row and a list/count), cite RVAs |
