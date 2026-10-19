# RAMPFIRST routing speed on Europolis 1024 (rf1024, 2026-10-18)

Verdict: **no measurable cost on 1024 with sc3perf's 8 workers.** Pooled ms per trip off 0.0659, on 0.0650 (on/off 0.987)
over the 12 windows outside one slow block. All 16 windows pooled: 1.060, but that figure comes from one block (see below).
Europolis has no highways, so RAMPFIRST never offered a ramp (log: `ramp offers=0`): this measures the cost of the hook
itself, not of ramp choices. Zero faults.

## Method
Instance `Simcity_stock_highways\re\harness\inst_rf1024`: sc3resize + sc3bigcity (size 1024) + sc3perf (built from this
worktree, `traffic_mt=8`, **batch mode `traffic_mt_smooth=0`**, because ld_alt reads per-batch time) + sc3netmod built from
main f21b9fc. Fresh copy of `verify/perf1024/europolis1024_v2.sc3`, PID 43596 (stopped), speed 3.
`ld_alt.py --export sc3netmod_rf_set --warmup 90 --window 30 --settle 2 --blocks 4` (16 windows, ABBA, one game).
Metric: sc3perf TRAFFIC_MT batch wall ms / trips routed on workers. Data `data/euro_mt_alt.json`.
`hwtrips_probe.py --timing` not used: it hooks route_trip in the sim thread, which sc3perf's workers replace.

## Numbers (ms per trip, per window)
| block | off | on | on/off |
|---|---|---|---|
| 1 | 0.0652, 0.0655 | 0.0692, 0.0659 | 1.032 |
| 2 | 0.0656, 0.0660 | 0.0618, 0.0630 | 0.950 |
| 3 | 0.0731, 0.0834 | 0.1283, 0.0835 | 1.319 |
| 4 | 0.0666, 0.0665 | 0.0658, 0.0649 | 0.982 |

Block 3 is a slow state of the game (the on window read 0.128, the trailing off window 0.083, same as the second on):
trips per second fell from about 2,900 to 1,900..2,400 for those windows, the between-game / within-game noise already in
`project-perf-between-game-noise`. It hit off and on windows alike, so it is not attributed to RAMPFIRST. Excluding it:
off 0.0659 (0.0652..0.0666), on 0.0650 (0.0618..0.0692), blocks 1.032, 0.950, 0.982. Spread between blocks is larger
than any effect.

Sim days per real minute: not read directly (no date counter in ld_alt). Proxy, trips routed per real second per window:
2,390..4,259 with no on/off pattern. sc3perf `BUSY` reported one date stall (1.7 s) near the end, after the windows.
Faults: `sc3netmod.log` 0 (hwy, rbt, all stats lines `faults=0`); sc3perf TRAFFIC_MT 0 faults over 2,073,443 trips
routed on workers (at 757 s). Highway share: not available, 0 ramp offers (no highways in the city).

## 1.57x block after load
Did not show in the first 8 windows (blocks 1, 2: 1.03, 0.95). The one outlier came later (block 3) and hit both arms.

## Not covered
Batch mode only, not `traffic_mt_smooth=1` (the owner's default). A city with highways on 1024 would exercise the ramp
rule itself: Europolis cannot.
