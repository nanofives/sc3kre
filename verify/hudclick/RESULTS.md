# RESULTS: hudclick (2026-10-15)

Pre-registration: `PRE.md` (b5de74a, committed before the first run). Branch `child/hudclick` from `round/1012` (145f492).
Stock tree `C:\Users\maria\Desktop\Proyectos\Simcity_hudclick` (every DLL and SC3U.exe SHA-256-identical to `original\`,
`Cities\` copied). Mods built from the worktree into `MAIN\re\harness\inst_hudclick` (sc3resize, sc3bigcity,
sc3overscroll, sc3simrun, sc3perf, mods_launch; no sc3netmod, the tree has no netmod package). Europolis, maximized,
client 3840x1984. Run folders, frames and logs: `MAIN\verify\hudclick\{F1..F5,N1,D1}` (gitignored).

**Verdict: no miss. Nothing in the HUDSCALE code changes.** Every click on a dialog opened from the enlarged HUD hit, in
arm N (HUD scale off), F (Fit, 3.307x) and D (200%). The menuscale failure does not carry over, for two measured reasons:
1. In a city, the dialogs opened from the HUD do not run their modal loop inside the click that opened them. Every
   message while they are up reaches the wndproc at depth 0, where HUDSCALE maps normally.
2. Dialogs are drawn at native size and position, so a click on one needs no conversion. HUDSCALE leaves it alone at any
   depth (at depth 0 because the point is outside every enlarged rect, at depth 1 because nothing is mapped there).

## How the frames were taken

Desktop grabs cannot be used here: with the game window not in the foreground the game presents black with a white box
(first run `F1/raw0.png`, the same limit as `verify/menucrop`). So every frame in this file is the game's own presented
frame, written by a new diag in sc3resize (`SC3RESIZE_FRAMEDUMP=<prefix>`, off unless set): the next Blt onto the primary
writes its source after the HUDSCALE pass, i.e. what the player sees. Driver: `re/tools/hudclick_launch.py`,
`hudclick_step.py`, `hudclick_arm.py`. Hit/miss is read from the frame and from the UI tree (`uiwin_dump.py`) after the
click, depth and mapping from `SC3RESIZE_HUDSCALE_MLOG=1`.

## Census: which dialogs nest (prediction P3)

| dialog (how opened) | opener press/release depth | messages while open | arms |
|---|---|---|---|
| Preferencias (Options flyout item 1) | 0 / 0, both mapped | depth 0 | N F D |
| Presupuesto (Review flyout item 3) | 0 / 0, mapped | depth 0 | N F D |
| Ordenanzas (Review item 5) | 0 / 0, mapped | depth 0 | F |
| Mapa de vecinos (Review item 4) | 0 / 0, mapped | depth 0 | F |
| Reunirse (Meet Advisor button) | 0 / 0, mapped | depth 0 | N F D |
| Guardar ciudad (Options item 4, Save As) | 0 / 0, mapped | depth 0 | F |
| Load (Options item 5): "¿Quieres guardar esta ciudad?" box | 0 / 0, mapped | depth 0 | F |
| Salir (Options item 7, quit question) | 0 / 0, mapped | depth 0 | F |
| Indagar (query tool, click on a building) | 0 / 0, city point, not mapped | **depth 1** | N F D |

Only the query dialog runs its loop inside a click handler (the city click's release), like menuscale's main-menu case.
Static side (`PRE.md`): the window manager's modal loop is GZWIND `FUN_10020971` (vtable `0x1002db80` slot `+0xa0`),
closed by `vt+0x44(0xd, win, id)` from 49 sites. The depth-0 dialogs are still modal for the HUD where the stock game says
so (below), so their loop runs too, only not under our mouse branch: the HUD click is handled first and the dialog opens
later from the game's own loop. `[UNCERTAIN]` which call path runs it; the depth is the measured fact.

## Arms N / F / D (predictions P1, P2, P4, P5)

Per dialog: open, one click on its own control, one click on an enlarged side-panel button, close. UI state after every
step was identical across the three arms (`arm.json` per run).

| dialog | own control clicked | N | F | D |
|---|---|---|---|---|
| Preferencias | "Ir a los desastres automático" | unticked | unticked | unticked |
| Presupuesto | "Ingresos" tab | income page | income page | income page |
| Reunirse | first advisor | "Concejales finanzas" page | same | same |
| Indagar (depth 1) | "Declarar histórico" | ticked | ticked | ticked |
| Ordenanzas | "Ahorro agua" (F only) | | unticked, total 11,983 -> 11,481 | |
| Mapa de vecinos | Sheaton (F only) | | Ciudad = Sheaton, its deal listed | |
| Guardar ciudad | "Craterville" in the list (F only) | | Nombre = Craterville | |

Every close (close box, check button, Cancelar) closed its dialog in every arm. Sheets: `MAIN\verify\hudclick\
{N1,F4,D1}_controls.png` (each dialog before / after its control click), `F5\ord_sheet.png`.

Side-panel click while the dialog is up (zoning, or landscaping in the query round):

| dialog | N (stock) | F, D |
|---|---|---|
| Preferencias, Presupuesto, Indagar | nothing opens | nothing opens (F/D: mapped at depth 0, or unmapped at depth 1 for Indagar) |
| Reunirse | the zoning flyout opens with the dialog still up | the same: the click was mapped and the flyout opened |
| Ordenanzas (F only) | not run | F: the zoning flyout opens with the dialog still up (mapped, depth 0) |

- **P1 met.** All dialog-control clicks hit in N, F and D.
- **P2 met for Preferencias, Presupuesto and Indagar, wrong for Reunirse.** Where the stock game ignores the HUD during a
  dialog, so does the mod. Reunirse does not block the HUD in the stock game (measured in N); with HUDSCALE the click on the
  enlarged button is mapped (depth 0) and hits. Ordenanzas lets the HUD through in F; its N arm was not run.
- **P3** as in the census: depth >= 1 only for Indagar (6 button messages of 38 in F4 and in D1, all its own).
- **P4: the stale-capture case does not occur.** Every opener's release came at depth 0 and was mapped
  (`HUDSCALE> up ... -> native`), which clears the capture before the dialog opens. Indagar is opened by a city click,
  never mapped, so it never sets the capture. The press after a close (the query press after Reunirse closed) queried the
  same building at P in N, F and D ("Galería empresarial Florencio"). Deviation from PRE: that city press after the close
  was made after Reunirse only, not after every dialog; the opener depths above are what excludes the mechanism.
- **P5 met.** Arm N: 0 `HSMLOG>` and 0 `HUDSCALE>` lines.

## Code

- `sc3resize.c`: FRAMEDUMP diag only (`rz_fd_maybe`, one guarded call in the Blt hook, one env read). Off unless
  `SC3RESIZE_FRAMEDUMP` is set. No HUDSCALE change.
- `re/tools/hudclick_launch.py`, `hudclick_step.py`, `hudclick_arm.py`: the drivers above.

## Not checked

- Owner hand test with a real mouse and focus.
- Dialogs opened by keyboard or from other tools on the city (bulldozing a landmark, reward placement, disasters). The
  query case shows a city-click dialog nests. Its own clicks are fine for the same reason as above (native dialog).
- A press that starts on the enlarged HUD and is released over the city with the query tool active.
- Window sizes other than maximized 3840x1984.
