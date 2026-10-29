# zonedemo results (2026-10-29)

Spec and RVAs: `re/analysis/ZONEDEMO.md`. Tree `dev\zonedemo\tree` (from main 584ab1f = release sc3mods-2026-10-29),
mods from `dev\zonedemo\inst`, city Berlin. Driving: posted input only (`re/tools/roadover_drive.py`: camera, hold,
release, shot), tool selected by menu command through `rb_lab.np`, undo by sc3undo's `WM_APP + 0x5d0` command. Cells and
funds: `re/tools/zonedemo_probe.py` (`map`, `zmap`, `canzone`). Pictures: `MAIN\verify\zonedemo\owner_shots\` (not
committed).

Test block (x, z): industrial zone 9 buildings at x 26..28 along z 203..223, across a road (x 25) from residential
zone 2 / 3 houses at x 18..24, commercial zone 6 at x 21..24, z 203..206.

| case | result | evidence |
|---|---|---|
| S stock (`-Stock`, CanZone called from Frida) | Ind Low, Res Low, Res High and DeZone over the R3 block x 134..137, z 143..146 (all houses): ok 0, cost 0. DeZone and Res Low over the C5 block x 151..155, z 144..146: ok 0. A rect with an empty column (x 133..137): ok 1, cost of the empty cells only. So stock refuses every building cell for every zone tool and DeZone leaves buildings standing | probe output in the session log |
| T1 Res Low over industrial buildings, x 26..28, z 211..214 (sim running) | **met.** Preview blue over the buildings, label $180 = zoning 12 cells x $10 + bulldozing 9 buildings $60 (eight 1x1 at $5, one 2x2 at $20). Release: 9 removed, the 12 cells read zone 1, funds 132,853 -> 132,673 (-$180). The sim was on top speed and new houses (type 3100) grew there within seconds | `T1a_before_industrial.png`, `T1b_preview_res_over_industrial_180.png`, `T1c_after_demolished_zoned_res.png`, log `ZONEDEMO> zone 1 over 9 zoned building(s) (9 removed), 12 cell(s): placed, zoning $120 + bulldozing $60; funds 132853 -> 132673` |
| T2 Res Low over residential houses, x 20..24, z 213..217 (paused) | **met.** Preview red, label $0, houses untouched, funds 132,212 before and after. No ZONEDEMO line: every building was the tool's own class, so the stock call ran unchanged | `T2a_before_houses.png`, `T2b_preview_res_over_res_red_0.png`, `T2c_after_untouched.png` |
| T3 DeZone over a mixed block x 18..28, z 203..210 (R 2 / 3, C 6, I 9, roads; paused) | **met.** Preview blue over all of it, label $448 = de-zoning 64 cells x $2 + bulldozing 61 buildings $320. Release: 61 removed, roads kept, funds 132,212 -> 131,764 (-$448) | `T3a_before_mixed_block.png`, `T3b_preview_dezone_448.png`, `T3c_after_all_demolished.png`, log `ZONEDEMO> zone 0 over 61 zoned building(s) (61 removed), 64 cell(s): placed, zoning $128 + bulldozing $320; funds 132212 -> 131764` |
| T3 undo | **met.** sc3undo entry `zone: 0 inserted, 61 removed, 64 zone cell(s), $448`. Undo: `125 op(s), 0 failed, $448 refunded, 16 ms`. Occupant and zone maps of x 18..30, z 203..210 after the undo are identical to the ones read before T3, funds 132,212 | `T3d_undo_restored_refunded.png`, `sc3undo.log` |
| charge once per building | **met.** The 2x2 at (26..27, 213..214) in T1 and (26..27, 208..209) in T3 is charged $20 once | logs above |

Not run: the switch off (`SC3RESIZE_ZONEDEMO=0`, or the checkbox off) in game. Both return to the stock call before
any change (`zd_install` logs `ZONEDEMO> off`, the wrappers test `g_plopover` first). Undo of T1: sc3undo records only
while paused, as for every tool. Commercial or industrial tools over another class, funds short, a building half
outside the drag, slopes. The airport / seaport / landfill tools: unchanged by design (`ZONEDEMO.md` 2).
