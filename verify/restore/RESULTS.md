# restore: results (child restore, 2026-11-02)

Owner request: a "Restaurar" button (cost = build price x fraction of life used) in a building's info dialog for
buildings with a lifespan, and a list of every such building opened from a button next to the Reunirse close box.
Mechanism and evidence: `re/analysis/RESTORE.md`.

## Verdict

Both parts built and checked in game: dev/restore tree, stock "Berlin, Germany", 800x600 windowed, posted input only,
frames from SC3RESIZE_FRAMEDUMP. Pictures: `MAIN\verify\restore\owner_shots\` (gitignored, local).

| # | check | result |
|---|---|---|
| 1 | "?" on the coal plant at (59, 222) | "Restaurar §1,246": age 234 of 939 months, price 5000; the game's own line reads "Edad (max) 19 años (78 años)" (shot 1). An earlier run: 341 months, §1,815, "28 años" |
| 2 | click Restaurar | age 234 -> 0, funds 117,006 -> 115,760; the dialog closed and reopened on the plant 15 to 31 ms after the click (3 runs) showing "0 años (78 años)" and "Restaurado (§1,246)" (shot 2) |
| 3 | Reunirse | "Vida útil" left of the close box (shot 3) |
| 4 | Vida útil | 216 buildings with a lifespan alive (229 incl. defunct), 256x256 scanned in 23.6 ms, least life left first, 7 a page, 31 pages (shot 4) |
| 5 | Restaurar on row 1 (water pump) | "Restaurado por §291", funds 115,760 -> 115,469 (shot 5) |
| 6 | Restaurar todos | 216 restored, §102,832 paid, funds 115,469 -> 12,637, every row "Como nuevo" (shot 6) |
| 7 | Volver | the stock Reunirse page back, advisors and petitions (shot 7) |
| 8 | price rose while the list was open | "El costo subió a §107,360: pulsá de nuevo", nothing charged, list refreshed (shot 8) |
| 9 | close box while our list is shown, then Reunirse again | closes; new page object gets its button again, no fault |
| 10 | petitions the game adds while our list is up | hidden after each page message (5 logged in 45 s), list stays clean (shot 9, 45 s after opening) |
| 12 | coal plant aged to 879 of 939 months (test export, past DeclineAge 751) | output 6000 -> 1820 of 6000 on the next update (the game's own derate: 6000 - 6000 x 132 / 188 = 1788 at 883) (shot 10) |
| 13 | restore it from "?" | cost 4,702 = 5000 x 883 / 939 = 4,701.8 rounded; IsDefunct 0 right after; output 1788 -> 6000 on the next update, age 3 (shot 11) |
| 14 | dead coal plant (rubble) at (59, 164): age 1005 of 823, IsDefunct 1 | "?" shows "(Muerta)", "Coste de limpieza", no Restaurar button; it is not in the list either (shot 12) |
| 11 | `SC3RESIZE_RESTORE=0` | "RESTORE> off", stock query dialog and Reunirse, query -> OK -> Reunirse sequence ran clean |

Static only (not exercised in game): the "Sin fondos (§N)" refusal caption in the query dialog (the funds check itself
ran in check 8's path with the price ceiling), incinerator and recycling center (no such building in Berlin; their
IBuildingMortal slots were read from the PE and match).

## Fault found and fixed during the round

The first part-2 build crashed the game on the next Reunirse open (0xC0000005 calling into the heap from SIMUI
0x1002c7ce). Cause: SIMUI FUN_100042f7 takes five stack args (`ret 0x14` at 0x10004402), Ghidra shows four, and the
detour popped 16 bytes. Proof: the same sequence ran clean with `SC3RESIZE_RESTORE=0` and with the 5-arg detour.

## Files

New: `re/harness/src/sc3restore.c`, `re/harness/src/sc3resize_restore.c` (both under the ignored `/re/*`, like every
other source there: commit with `git add -f`), `re/analysis/RESTORE.md`, `re/tools/restore_lab.py`, this file.
Changed: `re/harness/src/sc3resize.c` (include, query-dialog hook lines, `SC3RESIZE_RESTORE`, `rm_install`, test
message), sc3restore added to the mod lists in `sc3mods.c`, `build_mod.ps1`, `sc3dev.ps1`, `sc3wait.py`,
`stage_lan_release.py`.

## Lab

```
py -3.12 re/tools/restore_lab.py up --tag T            # launch Berlin in dev/restore/tree
py -3.12 re/tools/restore_lab.py query --tag T 59 222  # "?" on the coal plant (WM_RZ_RESTORE 1)
py -3.12 re/tools/restore_lab.py click --tag T 265 375 # Restaurar
py -3.12 re/tools/restore_lab.py log --tag T 20
```

## Frame rate with the list open (orchestrator question, 2026-11-02)

One game (run `p1`), no Frida attached (no run of this stream ever attached Frida), sim running, 800x600, shared PC
(two other children's games running: dev/graphtabs, dev/gog949). sc3perf's one-a-second CSV, 30 s per phase:

| phase | CSV rows | fps avg (min / max) | frame_ms avg |
|---|---|---|---|
| Reunirse closed, after the list (D) | 25 | 49.0 (4.2 / 113.1) | 47.5 |
| Reunirse open, stock page (B) | 40 | 0.2 (0 / 1.0) | 300.9 |
| Reunirse open, Vida útil page (C) | 28 | 0.8 (0 / 2.0) | 663.3 |

The low rate comes with Reunirse being open: the stock page alone presents 0.2 frames a second, our page about one a
second (frames about 1 s apart, so frame_ms is the gap between presents). Closing it brings 49 fps back. The 30 s of
city view right after loading (A) read 5.3 fps and are not used as the reference: the game was still settling after
the load.

**When the cell scan runs** (`sc3restore_list`, 256x256): on opening the page, after a row restore or "Restaurar todos",
and on the page's own periodic message 0x22c05b3f while our page is shown (about every 4 to 6 s). Page arrows do
not scan, nothing scans per frame or per redraw, and nothing scans once the page is closed. Measured in `p1`: 8 scans
while the page was up (one on open, the rest from the periodic message), 19 to 48 ms each, one outlier at 191 ms; 0
scans in the 30 s after closing.
