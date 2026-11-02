# placehints RESULTS (round 2026-11-02b)

Build: `dev\placehints\inst\sc3resize.dll` from child/placehints (main be42ba9 + this stream), loader from the same tree.
Driving: posted input only (sc3io messages, `roadover_drive.py tool`, a scratch pixel driver), no real mouse or
keyboard. Pictures: `MAIN\verify\placehints\owner_shots\` (frame dumps, 800x600 windowed). Detail and RVAs:
`re/analysis/PLACEHINTS.md`.

## A. "Tráfico aéreo: Escaso" with airport demand

Answered statically (decomp + PE constants), `PLACEHINTS.md` A. The row is commercial supply (valve 5000) divided by
4,000 per airport building (SIMMISC `0x1000f49c`, seaport `0x1000fc5d` with valve 8000). It reads neither demand,
nor the A / P bars, nor power. "Vuelos puntuales 98%" is the cap of that row. Not run live.

## B. Airport / seaport zone drag

| case | result | picture |
|---|---|---|
| Berlin, airport drag over a forest (flora) | stock blue preview, label `$7,500 \| Aeropuerto 15 celdas, 0 sin transporte (rojo) \| capacidad C +7500, uso 57% a 56% \| techo C 860 a 880 \| necesita energia y agua`. 15 cells x $500 = the stock cost | `B1_airport_drag.png` |
| Roadless Paradise, drag away from the rail line | every cell red, `112 celdas, 112 sin transporte`, capacity +0 | `B2_airport_red_no_transport.png` |
| Roadless Paradise, drag across the rail's 6-cell reach | red past 6 cells, zone colour inside: `110 celdas, 65 sin transporte`, `+22500` (45 x 500) | `B4_airport_partial.png` |
| Roadless Paradise, seaport drag | label `Puerto 10 celdas ... cap. I +2500 ... muelles: ...` | `B3_seaport_drag.png` |
| stock refused (no funds, or over buildings) | the stock red stays, no extra marking, label still shows the numbers | seen in runs, not kept |

The label was first cut at 256 px with "..." (two limits in SC3U, `PLACEHINTS.md` B). Lifted while a hint shows.
The B pictures are from before the wording was shortened ("capacidad" became "cap.", the seaport line hit 768 px).
Final wording built, not re-shot.

## C. Plop land value halo

| case | result | picture |
|---|---|---|
| Big Park (14312, R 50 C 30 I 10, 3x3) | halo in the highlight colour where R rises by >= a quarter of the peak, `R +32%  C +18%  I +5% \| marcado R +8% o mas hasta 10 celdas`. Buildings in the halo are tinted by the game's own highlight | `C1b_park_halo_open.png` |
| Small Park (14311, 1x1) | `R +3%  C +1%  I 0%`, matches the `LAND_VALUE.md` 6 replay (1x1 park: +3) | `C4_small_park.png` |
| Big Park inside one block (earlier build, all changed blocks) | R +38%, matches `LAND_VALUE.md` 6 (3x3 one block: +38) | log only |
| Esc after the park preview | halo gone, view as stock | `C2_after_esc.png` |
| road tool right after the park tool | plain `$10` label (first build kept the park text, fixed by the caller check) | `C3_road_label_plain.png` |

## Not covered

- Power, water and the pier water run are not drawn per cell (`PLACEHINTS.md` B, plan there).
- Aura, crime and pollution are not in the plop label yet (`PLACEHINTS.md` C).
- No real-mouse test: the hover label follows posted moves only. Owner check: drag an airport and a park by hand.
- No check with the other mods loaded (this inst held sc3resize only). The hooked slots (SIMSPR view +0x50, SIMRCI zone
  tool +0x54, SIMGEOM building tool +0x54, SC3U 0x00443149 / 0x00442f16) are not patched by any other mod source
  (grep of `re/harness/src`, 2026-11-02). TIPCURSOR patches code inside `0x1004a3d7`, which the wrap calls unchanged.
- Off switch `SC3RESIZE_PLACEHINTS=0` not launched.
