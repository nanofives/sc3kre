# abandon: Sandbox and gentler abandonment (GitHub issue #3, round 2026-11-15)

Branch `child/abandon`. Facts: `re/analysis/ZONE_REDEVELOPMENT.md` section 5. Probe: `re/tools/abandon_probe.py`,
report: `re/tools/abandon_report.py`. All runs: dev\abandon tree, windowed 800x600, speed 3, posted input only.

## M2: Sandbox

`sc3simrun` SANDBOX block, `simrun.ini [sandbox] enabled=0` (default off), env `SC3SIMRUN_SANDBOX=1/0`, row
"Sandbox: sin abandono" / "Sandbox: no abandonment" on the "Activar mods" page (left column, "Simulacion").
16 sites, each checked byte for byte: the (b) and (c) roll calls (6) are made to miss, the (a) / (d) / (p) posts (7)
and the 3 industrial farm removals are skipped. Start line: `### SANDBOX: on, ... 16 of 16 sites armed`.

### Berlin, 3 game years per arm (`m2_off.json`, `m2_on.json`)

Two separate games from the same save. The probe also wrote 20% into the three budget tax bytes at the first
snapshot; that did not move R or C demand (R stayed 1,060..1,140, C 800..880 in both arms), so it changed nothing
measurable. Berlin's industrial valve swings by itself.

| | stock | Sandbox |
|---|---|---|
| game days | 1,118 | 1,120 |
| flag-2 abandonments (zone evaluators) | 786 (ind (c) 674, res (b) 65, res (d) 30, com (b) 16, com (d) 1) | 0 |
| abandoned tiles, start / max / end | 58 / 75 / 38 | 58 / 58 / 14 |
| industrial valve | cycles -1,680 .. +1,680 (period about 540 days) | -1,961 from day 540 to the end |
| population (valve 3000 vt+0x28), end | 831,026 | 849,400 |
| jobs (valve 7000 vt+0x2c), end | 442,434 | 450,931 |
| unpowered tiles | 0 | 0 |

### Madrid, 1 game year per arm (`m2_madrid_off.json`, `m2_madrid_on.json`)

Madrid loads with about 800 abandoned tiles, and its power supply falls short during the year, which gives the
no-power case (none of the 13 shipped cities had more than 1 unpowered tile at load: `scan.txt`).

| | stock | Sandbox |
|---|---|---|
| flag-2 abandonments | 2,728 (res (b) 1,326, com (b) 1,065, ind (b) 181, com (d) 100, res (c) 28, res (d) 28) | 0 |
| res (b) fires with "nopower" among the causes (probe) | 197 | blocked |
| unpowered tiles, end | 241 | 1,212 |
| abandoned tiles, end | 141 | 167 |
| population, start 1,176,537 -> end | 1,045,763 | 1,086,250 |
| jobs, start 637,958 -> end | 573,209 | 650,077 |

### Population and jobs with Sandbox (the survey's open question)

- A building that Sandbox keeps occupied keeps its residents and its jobs in the game's totals: population and jobs
  ended higher than stock in both cities (Berlin +18,374 / +8,497, Madrid +40,487 / +76,868). Two separate games per
  city, so the size of the gap is not a controlled number; the direction held in both.
- It also keeps drawing power: Madrid ended with 1,212 unpowered tiles against 241 stock.
- With no industrial abandonment, filled demand stays 0 and the industrial valve stayed at -1,961 for the last 1.5
  years of the Berlin run (stock: abandonments push filled demand negative and the valve recovers). The oversupply
  the survey listed as a risk is real: demand does not come back while Sandbox is on.
- Abandoned tiles still rose 1 -> 14 in the Berlin Sandbox run with zero flag-2 posts from the evaluators. Their
  source was not identified [UNCERTAIN: not the two post functions; the disaster path (SIMDSTR) is a candidate, not
  checked]. Buildings already abandoned recover as stock (Berlin 58 -> 1 in the first 46 days).
- The Sandbox counters count every roll that would have fired, pass after pass on the same buildings (Berlin ind (c)
  67,073), so they are not a building count.

### Toggle page (`owner_shots/mods_page_default.png`, `owner_shots/mods_page_sandbox_on.png`)

| step | result |
|---|---|
| open Preferencias -> Opciones de mods -> Activar mods | "Simulacion" heading under the mods column, both rows unticked |
| tick "Sandbox: sin abandono", OK | `MODTOGGLE> +SC3SIMRUN_SANDBOX on at the next start`, sc3mods.ini `[env] SC3SIMRUN_SANDBOX=1` |
| restart with no env set | sc3mods.log `[env] SC3SIMRUN_SANDBOX=1 (sc3mods.ini)`, `### SANDBOX: on ... 16 of 16 sites armed`, page shows the row ticked |
| untick, OK | `MODTOGGLE> +SC3SIMRUN_SANDBOX off`, the key is gone from the ini |

Not checked: the page in the other 6 languages (keys present, `sc3lang.py check` clean), Esc from the page.

## M3: Gentler abandonment (GENTLE block)

`simrun.ini [gentle] enabled=0 share_pct=25`, env `SC3SIMRUN_GENTLE=1/0`, `SC3SIMRUN_GENTLE_SHARE=<pct>`, row
"Abandono mas suave" / "Gentler abandonment". Gate (orchestrator, 2026-11-15): the raw valve value, what the RCI bar
shows, not the net value the roll uses. The (c) roll may fire only while the valve is below
`min + (max - min) * share_pct / 100`; below that line the stock roll runs unchanged.

**How a share maps to the RCI bar.** The valves read -2000..2000, and the HUD draws a negative value as
`value * 1000 / 2000` on a -1000..0 half bar (SIMRCI `0x10042e89`). So the line sits at:

| share_pct | valve line | RCI bar line | meaning |
|---|---|---|---|
| 0 | -2000 | -1000 (bottom) | never |
| 10 | -1600 | -800 | bottom fifth of the negative half |
| 20 | -1200 | -600 | |
| **25** | **-1000** | **-500** | **lower half of the negative half** |
| 30 | -800 | -400 | |
| 40 | -400 | -200 | |
| 50 | 0 | 0 | stock (every negative value) |

Only industry went negative in the test cities (R and C stayed positive in all runs), so every number below is
industrial. The valve moves in steps (about 280), which is why only some buckets have draws.

### Stock: where the negative-demand abandonments happen (bar = the RCI bar when the roll fired)

| city, game days | (c) abandonments | at bar -450..0 (slightly low) | of which bar -150..-101 | per-pass chance at bar -150..-101 |
|---|---|---|---|---|
| Berlin, 746 (`m3_berlin_off.json`) | 332 | 80 (24%) | 27 | 27 / 2,792 draws = 1.0% |
| London, 374 (`m3_london_off.json`) | 276 | 30 (11%) | 30 | 30 / 3,220 draws = 0.9% |

Share table from the same stock draws (abandonments the line would have held):

| share_pct | Berlin, of 332 | London, of 276 |
|---|---|---|
| 10 | 160 (48%) | 93 (34%) |
| 20 | 101 (30%) | 30 (11%) |
| 25 | 80 (24%) | 30 (11%) |
| 30 | 44 (13%) | 30 (11%) |
| 40 | 27 (8%) | 30 (11%) |

### In game with share_pct 25 (`m3_berlin_g25.json`, `m3_london_g25.json`)

| | Berlin stock -> 25 | London stock -> 25 |
|---|---|---|
| (c) abandonments | 332 -> 284 | 276 -> 259 |
| of them with the bar above -500 | 80 -> 0 | 30 -> 0 |
| buckets they fell in (valve) | -2000..-201 -> -1700..-1101 | -2000..-201 -> -2000..-1101 |
| rolls held by the line (per pass, repeats included) | | 2,454 / 2,068 |

The total falls less than the held share: with fewer abandonments early, filled demand stays near 0, net demand
stays more negative, and the rolls below the line fire more often. Abandonment for the other reasons (no service,
low land value) is untouched: Berlin 41 res (b) in both arms.

### Proposed default (owner decides)

**share_pct 25** (whether Gentle is on by default is the owner call). In both cities it removes every negative-demand abandonment while the RCI bar is in the
upper half of its negative side (24% and 11% of them in stock), and leaves the stock behaviour once the bar is in
the lower half. 20 (line at bar -600) holds the same London cases and 21 more Berlin cases; 10 (bar -800) holds
about half of all stock negative-demand abandonments in Berlin. The code default today is Gentle off (`enabled=0`), share 25.

Not done (owner decision): the lower-value picker that always returns 0 (`0x100297fb`, `0x10018e45`).
