# STATUS menumask (child of "SC3: owner bugs 10-23"), 2026-10-26

State: **fixed, checked in game** (milestone 2). Worktree `Simcity_wt_menumask`, branch `child/menumask`, from `742fe1f`.

Cause: the 9 menu button sheets (`MAIN.IXF 0x22729930..38`, magenta key, no alpha) have a 1-px edge ring that Maxis
anti-aliased against the stock picture (7,585 px, alpha mean 0.49). On another picture it draws a stair-step fringe in
the stock colours. MSOPEN (2026-10-25) added 2,878 more stock pixels on the same edges. There is no shadow sprite or
shadow pass. The grey slab under Salir is the button's own opaque art (no correlation with the stock picture) and stays.

Fix: block MENUMASK in `sc3resize.c` (`rz_mk_*` / `g_mk_*`, before `rz_mb_patch_src`, plus hooks in `rz_mb_patch_src`,
`rz_ms_read`, `rz_ms_openbb`, `rz_ms_compose`, `rz_ms_full`, the MENUSCALE dump and the env read). Off switch
`SC3RESIZE_MENUMASK=0`. Sheets are decoded from the game's data at the first menu present (38,010 ring entries, 78 ms).
A frame pixel equal to a sheet's ring value at that spot, with a background neighbour, becomes
`p + (1-a) * (picture - stock)`, in both the scaled and the 1:1 / native paths. MSOPEN keeps the sheets' own border
background. Labels and dialogs are untouched.

Check: owner picture at 2560x1351, maximized 3840x1984 and native 800x600, idle and hover on all buttons: fringe gone.
No menu_bg.bmp at 800x600: pixel-identical to the off arm. New City / Load City / Preferencias: 0 px change inside the
dialogs. Static present cost unchanged (0.020 ms). Details: `verify/menumask/RESULTS.md`. Pictures:
`MAIN\verify\menumask\owner_shots\` (27 before/after PNG + the owner's shot; start with `salir_stock_vs_before_vs_after.png` and `escenario_smoke.png`).

Needs owner check: a look at the menu with the owner's picture. The Salir slab is button art, the same in stock.

## Files to commit (from the worktree)
- `re/harness/src/sc3resize.c` (MENUMASK block and its hooks, as above)
- `re/analysis/RESIZABLE_WINDOW.md` (new subsection "MENUMASK" after the MENUSCALE section)
- `verify/menumask/RESULTS.md`
- from MAIN: `verify/menumask/owner_shots/*.png` (game frames, local only per the publish policy unless the orchestrator decides otherwise)

No ids taken. No game left running (my PIDs 19924, 29448, 29480, 25012, 27196, 15392, 22296, 31624, 30932, 28084,
21824 all closed). Harness claim released. The test tree's `Apps\version.dll` and the instance folders
`re\harness\inst_menumask`, `inst_mm_on`, `inst_mm_off`, `inst_mm_nobg`, `inst_mm_nobg_off` plus `re\harness\dumps\`
are local test files in `Simcity_stock_menumask`.
