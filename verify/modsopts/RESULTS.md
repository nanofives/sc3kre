# modsopts: Edificios + autosave "ciudad original" on the mods page (2026-10-28)

Code: `sc3resize.c` (MODSPAGE block: ids `MP_H_BLD..MP_AS_UNAUTO` 0x02F95B66..69, free in every export), `sc3autosave.c` (`ini_read`).

| item | result |
|---|---|
| Section "Edificios" / "Buildings": "Boton Mover" (RELOCATE), "Construir sobre zonas" (PLOPOVER) | DONE. Applied at once on OK (globals set). Persisted in `sc3resize.ini [buildings] mover= plopover=` (default 1, read at start, env `SC3RESIZE_RELOCATE/PLOPOVER` still override). Only changed rows are written, cancel writes nothing. |
| Hooks stay installed | The SIMGEOM hooks and the query-dialog detour used to install only when a flag was on at start. Now they install unless the env turns BOTH off (`g_rl_envoff`); the behaviour already gated on the flags at run time. So turning one on again after start works. |
| Autosave: "Guardar en la ciudad original" = UNAUTO | DONE. `autosave.ini [autosave] unauto=` (default 1) read in `ini_read`, the watcher's re-read applies it at once, env `SC3AUTOSAVE_UNAUTO` still overrides. Log line "INI> autosave.ini changed ... unauto N". |
| Layout | Autosave row at y 252, Edificios heading 278 / boxes 296, "Al reiniciar" block moved to 324 / 342 / 362 / 382. Last row ends near y 400, buttons at 434. Edificios only shown when the RELOCATE hooks are in (SIMGEOM matched). |

## Check (Berlin, posted input, FRAMEDUMP, windowed)
- Mods page shows the new rows: `owner_shots/mods_page.png` (Frankfurt, ES).
- Berlin, "?" of the Brandenburg Gate (18010): Mover present (`gate_mover_on.png`); untick Mover + OK -> log `Mover button off from the mods page`, "?" has no Mover (`gate_mover_off.png`); tick again + OK -> `Mover button on`, "?" has Mover again, no restart (`gate_mover_back.png`, log `Mover button added`).
- `sc3resize.ini` got `mover=0` then `mover=1`. `autosave.ini` got `unauto=0` then `unauto=1`; sc3autosave.log `INI> autosave.ini changed: ... unauto 0` right after OK.
- Reopening the page shows the stored values.

Not tested in game: PLOPOVER box (same code path as Mover, flag read at `rl` placement at run time), English text, cancel path.
Pictures (not for git): MAIN\verify\modsopts\owner_shots\.

## Round 2 (same day): four more rows
Code: `sc3resize.c` (ids 0x02F95B6A..74), `sc3perf.c` (`sc3perf_cap_get/set`), `sc3overscroll.c` (`sc3overscroll_opt_get/set`, push thread now always started).
Layout reflowed: Rendimiento + Edificios side by side (y 146..200), FPS limit row 206, Autosave 232..290, Camara 298..360 (the two sliders panel left, overscroll slider + push right), "Al reiniciar" 374..430 (three boxes on the last row). Camera panel + heading moved off the right column of Rendimiento.

| row | ini | applies |
|---|---|---|
| Limite de FPS (Monitor / 30 / 60 / 120 / Sin limite) | perf.ini [perf] fps_cap = -1 / 30 / 60 / 120 / 0 | LIVE: sc3perf's stats thread re-reads g_cap every ~1 s; the new export sets it. Log `CAP> frame cap now 60 fps (setting 60)`, overlay showed 60 fps. A cap of another value in the ini shows no radio selected and stays untouched. |
| Empujar camara al construir | overscroll.ini [edge] push | LIVE: `push_start` reads g_push at every drag. The low-level hook used to start only when push=1 at start, now it always starts (idle when push=0). Label shortened from "Empujar la camara en el borde al construir" to fit the column. |
| Mas alla del borde slider (10 steps 50..95, leftmost = off) | overscroll.ini [camera] overscroll | LIVE: `allowed()` reads g_overscroll on every camera move. Replaces the checkbox "Camara mas alla del borde" (MP_OVERSC removed). 50 is the floor, 95 the max. |
| 60 min in the autosave group | autosave.ini [autosave] minutes=60 | LIVE through the watcher's re-read: log `every 3600 s`. |

Check (Berlin, posted input): set 60 fps + 60 min + push off + slider leftmost, OK -> perf.ini `fps_cap=60`, overscroll.ini `overscroll=50` / `push=0`, sc3overscroll.log `OPT: edge push 0`, sc3perf.log `frame cap now 60`; reopened page shows the stored values; then 60 min + OK -> autosave.ini `minutes=60` (my first click had hit 30 min, the radio column is x 436 for 30, 510 for 60).
Not tested: the slider's effect on the camera (only the written value and the live setter), English text, the FPS=Monitor / 120 / no-limit options, cancel path. "Sin limite" label ends at x 635 of 638, tight (group width 340 could drop to 320).
Pictures (not for git): MAINerify\modsopts\owner_shots\ mods_page.png (defaults), mods_page_changed.png (before OK), mods_page_reopened.png (stored values). Round-1 gate pictures were deleted by mistake; the round-1 table above stands.
