# RESULTS - sc3overscroll (2026-10-06)

Iterative owner hand tests, not pre-registered. Each finding drove the next build. Logs are in this
folder and `verify/mods_combo/` (not committed). Design and the reasoning: `re/analysis/formats/CAMERA_OVERSCROLL.md`.

| run | build | who | result |
|---|---|---|---|
| 1 | overscroll v1 (game pick at 8 probes) | Claude | Europolis: 25 posted right-drags reach the corner, steps past the edge accepted then refused at the limit, 0 faults (`edge1.png`) |
| 2 | same | owner | "works", asks for sliding when the push is blocked |
| 3 | + slide v1 (axis parts, 2:1 edge directions) | Claude | never slid, every blocked step "nothing left to slide along" |
| 4, 5 | slide v2 (turn up to 90 degrees, full speed) | Claude, owner | slides (4,097+ in run 4). Owner: sloppy, speeds up when pushing almost perpendicular |
| 6 | slide v3 (turn up to 75, speed x cos, last side first) | owner | "still off": caught on terrain slopes near the edge |
| 7, 8 | limit v2 (flat, altitude 0) | Claude | no step past the edge ever accepted. Debug: centre tile (275,91) on a 256 map, ~20 tiles off the drawn edge (Europolis sits at altitude 75) |
| 9, 10 | limit v3 (flat, median edge height) | Claude, owner | Europolis: reference 75, overscroll and sliding work (`flat9.png`). Owner: "feels right" |
| combo 1 | all three mods | owner | 1024 map: north/west edges stop early, right-drag stops there. Log: reference height 41 for the whole map |
| combo 2 | limit v4 (nearest-edge height, +-24 cell average) | owner | "works fine" |
| combo 3 | + edge scroll while placing, from the GZGraphicD blit | owner | works, UI flickers while the camera moves |
| 12, 13 | tick moved to SIMSPR `FUN_10042a95` | Claude | first try passed the sub-object as the view: `ecx` vtable `+0x676ac`, outer at `ecx-4` (`run13.log`), fixed |
| combo 4 | same | owner | "No flicker now" |
