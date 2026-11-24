# RESULTS: power and water stop about mid map on 1024 cities (round 2026-11-23e, child pw1024)

Player report and picture: `verify/forumshots/player_power_water_1024.png`. A power line and a pipe from the map edge
stop carrying power and water about mid map. A second plant past that point powers its own patch but never joins.

## Cause [CONFIRMED]

Both coverage layers grow a 1-bit region from each source with SIMUTIL `sc3_bitraster_grow_capped` `0x1000bbfc`
`(region, mask, width, cap, &row_lo, &row_hi)`. One iteration is a horizontal pass (`0x1000bce2`, 1 cell left and right)
then a vertical pass (`0x1000be48`, 1 row up and down). So k iterations reach at most k cells from the seed along each
axis. The loop stops when nothing grows or after `cap` iterations.

| layer | caller | seed | cap | push | call |
|---|---|---|---:|---|---|
| power | `sc3_power_distribute_region` `0x10004e57` (from the tick `0x10004c1f`) | each plant not yet inside a region | 600 | `0x10004e85` | `0x10004e99` |
| water | `FUN_1000e8c4` (water layer tick) | each source with capacity (`+0x1a` != 0) | 500 | `0x1000eab9` | `0x1000eac9` |

These are the only two callers of `0x1000bbfc` (E8 scan of SIMUTIL `.text`). The later water supply walk
(`FUN_1000f163`, `FUN_1000f345`) is masked by the capped region, so watered cells never pass it. Coordinates on these
paths are int or ushort (`FUN_1000f0be` x and y ushort), so nothing else wraps at 1024.

So a line carries power 600 cells from its plant and water 500 cells from its tower or pump. On the shipped sizes
(256 and below) a straight run never reaches that. On a 512 map a straight pipe can lose its last 11 cells. On 768 and
1024 both stop well short. A plant past the cut seeds its own 600-cell region: the player's "new powered zone, no
connection".

The cut is distance from the seed, not an absolute coordinate or a raster size: in Europolis 1024 (shipped caps) the
capped water regions end at x 493, 501, 726, 744, 750, 992 and 1001 depending on the seed (`ab/bigcity_D_*.log`).

## Reproduction (shipped caps, `SC3BIGCITY_GRIDCAP=2` = wrapper installed, shipped caps kept, logging only)

New City 1024 in `dev\pw1024\tree` (posted clicks only). Coal plant at x 2 row 500, power line x 7..1023 row 501
(bridges over the river), water tower at x 2 row 520 (powered by a short line), pipe x 4..1023 row 520. Saved as
`pw1024_repro_1024.sc3` (networks checked offline: line 1017 tiles with no gap, pipe 1020 tiles with no gap).

```
GRIDCAP power: cap reached (600 iterations, width 1024, seed row 500): region x 0..602 rows 498..505
GRIDCAP water: cap reached (500 iterations, width 1024, seed row 520): region x 2..502 rows 520..521
```

Pictures (`owner_shots/`):
- `before_water_1024_pipe_stops.png`: underground view, the watered band along the pipe ends partway (the player's picture).
- `before_power_1024_zones_grey_past_600.png`: power data view over a zoned strip x 560..650. Blue (powered) to x 602, grey after it.

## Fix: sc3bigcity GRIDCAP block

`re/harness/src/sc3bigcity.c` (worktree `dev\pw1024\wt`). Both calls go through a wrapper that passes
`cap * width / 128` when the map is wider than 256 (512: 2400 / 2000, 1024: 4800 / 4000) and the shipped cap otherwise,
so stock sizes run as before. Each patch checks the shipped bytes first (`68 58 02 00 00` + `e8 5e 6d 00 00`,
`68 f4 01 00 00` + `e8 2e d1 ff ff`). `SC3BIGCITY_GRIDCAP=0` leaves SIMUTIL alone, `=2` keeps the shipped caps and logs.

Why `/128` and not `/256` (the stock margin): Europolis 1024 needs 1930 water iterations (its pipes wind), 97% of a
`/256` cap of 2000. The loop still ends when nothing grows, so the larger cap costs nothing where networks end sooner.

## Checks

| arm | city | caps | result |
|---|---|---|---|
| A | repro 1024 | shipped | power x 0..602, water x 2..502 (cap reached every pass). 90 days / 60 s from minute 2 |
| B | repro 1024 | /256 | power 1022 iterations, x 0..1023, 0.8-1.2 ms. Water 1022 iterations, x 2..1023, 0.24-0.42 ms. 90 days / 60 s |
| C | save written by the fixed build, reloaded | /256 | same regions as B. 90 days / 60 s |
| G | repro 1024 | /128 (final) | same regions as B, power 0.69-1.34 ms, water 0.24-0.43 ms. 91 days / 61 s |
| D, H | Europolis 1024 | shipped | every power and water fill hits the cap. Power 35-41 ms per call, water 12-25 ms per call, 8 water calls per pass. 71-81 days / 60 s (minutes 3-4) |
| E | Europolis 1024 | /256 | power 1034 iterations, water 1930, whole map in one call each. 78-79 days / 60 s |
| I | Europolis 1024 | /128 (final) | power 1034 iterations (80-99 ms), water 1930 (112-138 ms), whole map x 0..1023. 83-84 days / 60 s (minutes 3-5) |
| F | Europolis 256 | fix build | no GRIDCAP line (width 256 keeps the shipped caps). 90 days / 60 s |

Speed 3 nominal = 90 days / 60 s. Days per minute come from sc3perf `DAYS>` lines (`ab/perf_*.log`). The fix shows
no slowdown on the dense city: one fill per pass instead of several capped ones, 80-140 ms per fill about every 22 s
of play.

Pictures after the fix (repro city, same camera spots):
- `after_power_1024_zones_all_powered.png`: the whole zoned strip x 560..650 is blue (powered).
- `after_water_1024_pipe_watered.png`: the watered band runs the full pipe, past the point where it stopped.
Both were taken with the `/256` build. The repro city's fills end at 1022 iterations, under both caps, so `/128` gives
the same picture (arm G logs).

## Files
- `pw1024_repro_1024.sc3` (repro city, shipped-cap session), `pw1024_fixed_saved.sc3` (autosave written by the fixed build)
- `before_gridcap2.log`, `fix_gridcap1.log`, `ab/` (per-arm sc3bigcity and sc3perf logs), `*_run.sh` / `*_run.out`
- the repro city also holds a 15-cell pipe spur at x 518 rows 513..528 (from the pipe-tool capture), harmless

## Not done
- No 512 or 768 city was run. The cut is distance from the seed (above), so on 512 only a pipe longer than 500 cells is
  affected, which the code reading gives directly.
- `SC3BIGCITY_GRIDCAP=0` was not run in game (it returns before any write, read in the source).
