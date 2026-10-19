# hwask results: the game asks before building a highway interchange (2026-10-19)

Owner decision 2026-10-19: "Dialog: default bridge, the game asks whether to build the interchange." Mechanism and
RVAs: `re/analysis/HWY_ASK.md`. Owner sheet: `MAIN\verify\hwask\owner_shots\hwask_sheet.png` (dialog close-ups
`hwask_dialog_crossing.png`, `hwask_dialog_t.png`; game art, not committed).

## Setup

Test tree `Simcity_stock_highways` (hwx_cloverleaf, hwt_trumpet, highway_diagonal_cloverleaf, highway_dd_cloverleaf
installed, then `highway_ask` added with netpack overlay mode), instance `re\harness\inst_hwask`, sc3netmod built from
`Simcity_wt_hwask` (312,832 bytes), lab city `lab.sc3` (Roadless Paradise), funds set to $2,000,000 (hw_lab funds).
Game language folder: `ENGLISH` (Spanish text). Logs: `inst_hwask\sc3netmod_run1.log`, `sc3netmod_run2_reload.log`.

## In game

Run 1 (PID 29528), `hwask1.sc3`:

| step | log | seen |
|---|---|---|
| startup | `overlay: CreateFileA "...\Text\English\SC3StringsNetpack_029541F4.IXF" -> overlay ... ok (GZResourceD.dll)` | the text container is read |
| X: highway 46,27 -> 70,27, then 57,15 -> 57,39 | `hwask: edit: asking for the X cloverleaf at (57,27) turn 0: 68 ramp cells x 75 = 5100` | "Informe de Ingeniería / ¿Quieres construir un enlace de autopista por $5,100? Si eliges No, solo se construye un puente." buttons No / Sí |
| click Sí | `yes: X cloverleaf at (57,27) built, 5100 charged, funds 1990400 -> 1985300`, `hwx: edit: cloverleaf at (57,27): 96 cells written` | cloverleaf |
| X: 105,79 -> 105,99, then 95,89 -> 115,89 | `asking for the X cloverleaf at (105,89) ...` | same question |
| click No | `no: X cloverleaf at (105,89) gets the bridge`, `hwx: edit: clean flyover at (105,89) (the player chose the bridge): 12 cells written` | flyover, no ramps |
| nearby edit: highway 110,83 -> 113,83 | `hwx ... kept=1`, no hwask line (`asked=2` unchanged) | no second question |
| T: highway 131,4 -> 131,44, stem 141,20 -> 132,20 | `asking for the T at (132,19) turn 1: 30 ramp cells x 75 = 2250` | T question (first text, see below) |
| click No | `no: T at (132,19) stays stock (decline remembered, saved with the city)`; cells (132,19) 15053.0 / (132,20) 15054.0 | stem dead-ends with its stock caps |
| nearby edit 136,25 -> 140,25 | no hwask line | no question (that pass box did not hold the whole T: hwt refuses before asking) |
| save | `save: 108 variant tile(s) written as base, 1 T decline(s), section 0x4E56 written` | |

Between the runs: the T text was shortened (the first one, "... la autopista termina en el cruce.", ran into the
frame of the four-line text box) and a log line was added for the declined-T skip; package reinstalled
(`netpack uninstall highway_ask` then `install`, both clean).

Run 2 (PID 15904), `hwask1_reload.sc3` = the run 1 save:

| step | log | seen |
|---|---|---|
| load | `hwask: load: T decline at (132,19) turn 1 (trigger 15053) restored`, `load: variant section 109 entries, 108 to restore`, `all 108 variant tiles restored`, `hwask: load: T at (132,19) not asked on a load pass: the default (stays stock)` | cloverleaf, flyover and stock T as saved |
| edit over the T: highway drag 131,12 -> 131,28 on the existing through highway (pass box holds the whole T) | `hwask: edit: T at (132,19) turn 1 declined before: stays stock, not asked` | no question |
| edit over the flyover: highway drag 105,80 -> 105,98 | `hwx ... kept=3`, no hwask line | flyover kept, no question |
| new T: stem 141,37 -> 132,37 | `asking for the T at (132,36) turn 1: 30 ramp cells x 75 = 2250` | shortened text fits: "... Si eliges No, la autopista acaba aquí." |
| click Sí | `yes: T at (132,36) built, 2250 charged, funds 1944800 -> 1942550`, `hwt: edit: full T at anchor (131,36) turn 1 ...: 50 cells written` | trumpet T |

The HUD keeps dropping after each answer by the stock charge for the drag itself (about $300 per highway cell),
which the game takes after the retile, so after the dialog.

## Not run

- hwdx (diagonal x straight) and hwdd (diagonal x diagonal) questions: same helper, not exercised in game.
- `SC3NETMOD_HWASK=0` in game (offline reading only: `hwask_ok` returns 1, the old automatic path).
- A no-mod load of a save with declines (the entries sit in section 0x4E56, which the stock loader never reads, and
  have id word 0, which earlier sc3netmod loaders skip; not loaded without the mod).
- Offline twins (hwx.py, hwt twin, hwdx.py, hwdd.py) are unchanged: they model the full build, i.e. the "yes" answer.

## Lab traps hit

- rb_lab `cam` once returned a bogus origin right after load; the first drag went to off-screen pixels and built a
  short highway near window 2 ($1,800). Re-running `cam` until the drag pixels map inside 800x600 fixed it (the stub
  is visible in the window 2 shots, south of the flyover).
- After a dialog click the Highway tool shows its hover preview (blue diamond, "$600") at the click point: not a build.
