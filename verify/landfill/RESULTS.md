# landfill results (2026-10-30)

Owner request: "Each landfill should be independent, and it should be possible to empty one." Owner choice: A2 + E1
with the per-landfill readout. Spec and RVAs: `re/analysis/LANDFILL.md`. Tree `dev\landfill\tree`, mods from
`dev\landfill\inst`, city Craterville (3 landfills: 56, 32 and 27 cells). Driving: posted input only (sc3io), camera
through `netmod/nramp_cam.py`, pictures by sc3resize's frame dump, driver `re/tools/landfill_check.py`. Pictures:
`MAIN\verify\landfill\owner_shots\` (not committed). Log lines from `inst\sc3landfill.log` and `inst\sc3resize.log`.

| case | result | evidence |
|---|---|---|
| query on the 56-cell landfill | **PASS.** Three lines under the game's own panel: "Este vertedero: 54% completo", "99,939 de 183,495 ton. (libre 83,556)", "Vaciarlo cuesta $4,997", plus a "Vaciar" button bottom left. | `10final_1_query.png` |
| Vaciar on it (dialog open, sim held) | **PASS.** All 56 cells emptied at once, heap art removed, bare landfill ground. Lines now read 0% and "Vaciado: 99,939 ton. por $4,997". Funds 10,933 -> 5,936. The other two landfills are untouched. | `10final_2_emptied.png`, `10final_3_closed.png`, log `EMPTY> landfill at (77, 228): 56 cells, 56 emptied, 999392 units (99939 t), fee $4997, funds 10933 -> 5936` |
| Vaciar on the 32-cell landfill | **PASS.** 36,951 t for $1,848, funds 10,933 -> 9,085, emptied in place, the 56-cell one still full. | `04_query_landfill2_line_cut.png` (earlier two-line layout, line cut, fixed), `05_landfill2_emptied_direct.png` |
| emptied landfill takes garbage again | **PASS.** Within 3 minutes it started its own heap and took deposits (fill 0 -> 6,580 and growing) while the 32-cell one kept filling too. | log `DEPOSIT> cell (81, 228) landfill #1: put down 2128 ...`, `STATS> #1 ... fill 6580` |
| independent service (A2) | **PASS.** The router copy handled 1,029 to 3,432 per-cell landfill requests per run. Deposits landed in two landfills in the same minute, each from its own heap (stock keeps one heap at a time: Phase A measured fills of 0.8% / 57% / 36%). The 27-cell landfill got nothing in these runs because no producer had it as its nearest landfill. | log `DEPOSIT> ... landfill #1 ...` and `... landfill #2 ...` alternating, `STATS> routed 1029 (per cell 1029)` |
| bookkeeping stays exact | **PASS.** Valve free room = sum of (32767 - fill) over active cells, and valve waiting = sum of pendings, measured with Frida at four points (two while running, after an empty, and after an empty with independent off): 2,506,679 / 2,508,801 / 3,451,793 / 3,390,091, waiting 0 each time. | `lf_inv.py` reads (scratchpad), numbers in STATUS |
| `SC3LANDFILL=0` | **PASS.** Log "sc3landfill off: nothing patched". The query dialog is stock (Copiar ID only, no lines, no Vaciar). | `20_switch_off_stock_dialog.png` |
| `SC3LANDFILL_INDEPENDENT=0` | **PASS.** Log "independent=0 (router stock)". Readout and Vaciar still work: 101,589 t for $5,080, bookkeeping exact (3,390,091). | `21_independent_off_empty_still_works.png` |

## Fee

$50 per 1,000 t (`landfill.ini` `fee_per_1000_tons`). This is the game's own export-deal price: `GARBAGE_EXPORT_RATE=5`
per 1,000 garbage units (SIMMISC `0x1001761c`), and one unit is 0.1 t. The game's query panel confirms the scale
(376,821 ton. = 115 cells x 32,767 x 0.1). A full cell costs $164.

## Not run

- `SC3RESIZE_LANDFILL=0` alone (a guard on the same block: no lines, no button). Static only.
- A save made after emptying, reloaded without the mod. Only stock fields change (per-cell fills through the game's
  own SetGarbageValue, valve through its own adders, occupants through decay), so by construction the save is a stock
  save. Not loaded to check.
- A map with landfills far apart (Frankfurt has two, 240 cells apart, but burns all its garbage). In Craterville the
  three landfills are adjacent, so "nearest" splits work between two of them.
- `max_distance` > 0.

## Needs owner check

- Whether the three lines read well at the owner's HUD scale (checked at 1x, 800x600).
- The fee level ($50 per 1,000 t). Change `fee_per_1000_tons` in `landfill.ini` (0 = free).
