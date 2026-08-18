# city_load_test — RESULTS (run 2026-08-17, windowed-mode / launch-harness session)

Run by the only live session driving the actual game. SHA-256 of each file confirmed
against MANIFEST.txt before loading. Loaded via the working windowed build
(`-nocom -windowed -origin -fix16 -fitclient -nointro`, injected `sc3probe.dll`), one file
at a time, presented as `Cities\Mount Herrang.sc3` with the real Mount Herrang moved aside so
there was exactly one candidate (see caveat 1). Every load confirmed VISUALLY by a human.

## Verdict: all four rungs LOAD

| rung | SHA-256 (16) | result |
|---|---|---|
| T0 control | e520defbd777fb81 | **LOADS** — city appears (once the name collision was removed) |
| T1 byte-identical rewrite | e520defbd777fb81 | **LOADS** by identity — same bytes as T0, not re-run |
| T2 recompressed (our QFS quick=0) | f9141e28893cb2fa | **LOADS, looks right** — the sharp test passes |
| T3 one-tile edit (28,0 -> Landfill) | 494bf35b0465d888 | **LOADS** — the game accepted the edited file |

Per the README's pre-registered outcomes this is the success case: "T0 and T1 load, T2 loads,
T3 loads — the writer is validated end to end and the toolkit's central claim is no longer
structural-only." **The game loads files this project wrote, including the compressor's output
(T2) and an edited file (T3).**

## Caveat 1 — a NAME-COLLISION crash (harness/presentation, NOT the writer)

First attempt copied a test file into `Cities\` under a distinct FILENAME while the shipped
`Mount Herrang.sc3` was still present. Both files carry the same INTERNAL city name
("Mount Herrang"), and loading the copy **crashed** (hard, access violation). A stock city
loaded fine in the same session, and T0 is byte-identical to a shipped file, so per the ladder
this implicates the load path, not the bytes. Removing the duplicate (one candidate at a time,
real file moved aside) fixed it: T0/T2/T3 then loaded. **Actionable for the toolkit/users:**
do not place a written city alongside another with the same internal name; match the filename
to the intended city or ensure a unique internal name.

## Caveat 2 — RESOLVED: T3 edit confirmed visually at (28,0), crash was our instrumentation

Follow-up run done with the probe's framebuffer sampling disabled (`-quiet`). Result,
user-confirmed:
- **The run stays up** past the earlier ~35 s point - no self-close. So the earlier T3 crash was
  the probe's `FBHUNT`/`WINDUMP` surface sampling, NOT the game rejecting T3 and NOT a sim
  inconsistency.
- **Tile (28,0) shows LANDFILL** in the zone overlay, amid Residential. The single-byte edit our
  writer made (body offset 114,715, slot 1 -> 17) RENDERS in-game at exactly the intended tile.

So T3 is fully cleared: the edited file loads, is stable, and the edit is visibly correct at the
right place.

## What is settled vs not

- SETTLED: the game ACCEPTS and LOADS files the writer produced - container, our QFS compressor
  (quick=0), and a single-tile zone-raster edit. The central claim is validated.
- NOT SETTLED: that the edit renders correctly at (28,0); that the sim treats the edited tile
  consistently over time; that the ~35 s T3 crash is unrelated to the edit. These need the
  follow-up run.
