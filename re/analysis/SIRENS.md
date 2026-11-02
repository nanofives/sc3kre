# Emergency-vehicle sirens: what plays them, why they loop, the SIRENS fix (task sirens, 2026-11-02)

Owner, 2026-11-02: "avoid looping sirens sounds during gameplay, lower their chances significantly".
Fix: sc3simrun SIRENS block. Measurements: `verify/sirens/RESULTS.md`. Probe: `re/tools/siren_probe.py`.

## 1. The data side (AUDIO.INI)

`Apps\Res\Sound\AUDIO.INI` `[Actor]` (format comment in the file: `SfxId, pri, vol, language, type, absolutepaths,
driveby, special1, special2`; type 0 = special2 is the honk, 1 = altitude, 2 = neither):

| id | name | locale | type | driveby (looped while tracked) |
|---|---|---|---|---|
| 113 | VehicleFireEngine | 1 | 0 | `sfx\vehicles\sirenf.xa` |
| 114 | VehiclePolice | 1 | 0 | `sfx\vehicles\sirenp.xa` |
| 130 | VehicleAmbulance / VehicleEuroAmbulance | 1 / 2 | 0 | `sirena.xa` / `ESirenA.xa` |
| 115..125 | cars | 0 | 0 | none (honk only) |
| 150 | VehicleTrain | 0 | 2 | `train.xa` |

No `[Options]` key tunes the siren chance or a cooldown. The keys the game reads are listed in
`AUDIO_CLUSTER1.md` section 2 (`FUN_100053e3`). Other siren-like files are not vehicle sirens: `[Sparse]` building
loops (`Polvehg.xa` 0x17c, `FireStn.xa` 0x100, ...), `CRIME.FSC` alarms (crime ambience), `WrnSiren.xa` 48 (disaster
early warning). Those were not probed and are left stock; the vehicle actor below is the one with the loop.

## 2. Who decides a siren (STRTSIM)

- `0x100198c0` (Linux `cSSVehicle::DecideSirenState`, `[LINUX-HINT]`, same body): `rand(100) < 0x50 -> 0`, else
  `rand(2)` 0 -> 1, 1 -> 2 `[CONFIRMED @ STRTSIM 0x100198cc: cmp eax,0x50 / jae]`. 20% of calls give a siren.
  Live: 609 calls in 5 min in Berlin, 497 / 54 / 58 for 0 / 1 / 2 (verify/sirens/A0_baseline.log).
- Caller `0x100172fe` (vehicle placement): BoxX event 1 (placed) then event 5 (state) for the sound id at
  vehicle descriptor +0x30 `[CONFIRMED @ STRTSIM 0x100172fe]`.
- `0x1001b340` (`sc3_vehicle_move_stages_update`) re-rolls the same way while the vehicle drives, inlined
  (`cmp eax,0x50` at `0x1001b44c`), and sends event 5 for the id at descriptor +0x38: every 4th stage with
  `rand(2) == 0` `[CONFIRMED @ STRTSIM 0x1001b340]`. Live: every fire-engine event 5 came from here
  (return `STRTSIM+0x1001b492`).
- `0x10018750` sends event 3 (position) for both ids every 10th vehicle tick; `0x1001c9e0` sends event 2 (+0x30 id)
  and event 4 (+0x38 id) when the vehicle goes.

The fire engine's siren id 113 sits at descriptor +0x38. In 3 Berlin runs only fire engines carried a siren id
(police 114 and ambulance 130 got no event).

## 3. Who plays it (AUDIO)

AudioManager `mgr = *(AUDIO 0x10026f00)`; sound objects at `mgr + 0x190 + id*4`. Dispatcher
`0x10008d77` thiscall(cmd, id, vehicle, a, b): 1 -> slot +0x24, 2 -> +0x34, 3 -> +0x30, 4 -> +0x54, 5 -> +0x38,
6 -> +0x3c `[CONFIRMED @ 0x10008d77]`.

Actor object (0xb8 bytes, ctor `0x10012d97`, vtable `0x100210ec`, parser `0x10002e5a`): +0x18 id, +0x38 type,
+0x3c driveby stream, +0x88 tracked vehicle, +0x90 siren state, +0xb0 target volume, +0xb4 current volume.

| slot | RVA | event | what it does |
|---|---|---|---|
| 8 | `0x10013730` | tick | ramps +0xb4 toward +0xb0 by 0x32; from 0 starts the stream with vt+0x1c(vol,1,1) (looped); at 0 stops it and untracks |
| 12 | `0x100134fb` | 3 position | zoom < 4 -> untrack. Else if (+0x38 != 0 or **+0x90 != 0**) and (nothing tracked or this vehicle): volume = `0x1001349f`; > 0 -> track it, 3D position; 0 -> untrack |
| 13 | `0x10013873` | 2 gone | untrack if it is the tracked one |
| 14 | `0x100138a8` | 5 state | **only if vehicle == +0x88**: +0x90 = state; state 0 -> untrack |
| 21 | `0x10013b5a` | 4 gone | tracked one: volume 0 at once, stop stream, untrack |

`0x1001349f`: volume = mgr+0x2c - (5 - zoom) * mgr+0x60 (VehicleAttenuation) when zoom > 3, mgr+0x9cc == 0 and
`0x1001341d` says the vehicle's screen point is inside the view.

## 4. Why it loops

1. +0x90 is one field per sound id, not per vehicle. Event 5 reaches it only for the vehicle already tracked, so the
   20% roll of an untracked vehicle is thrown away.
2. Nothing clears +0x90 on untrack (slots 8, 13, 21 leave it), and the ctor chain (`0x10012d97`, `0x10012691`,
   `0x1001ac37`) never writes it `[CONFIRMED by disassembly of 0x10012d97: no store to +0x90]`. Live value at attach:
   1145980204 = bytes `,END`, heap text, on all three actors (verify/sirens/A0_baseline.log).
3. So from the first frame every on-screen fire engine passes the slot-12 test, gets tracked, and plays the looped
   siren until it despawns (event 4); the next fire engine on screen takes over at once. Probe, stock, fire engines
   counted as on screen: 5 starts in 120 s, all on vehicles that had never been sent a siren-on state
   (verify/sirens/A1b_diag.log).
4. The latch turns off only when the tracked vehicle itself re-rolls 0, and then the id is silent for the session
   (B0: `fire:state0:tracked` after the first siren, +0x90 = 0 at the end).
5. The start value is whatever the heap held: ",END" in A0 / A1b / B0, 0 on all three actors in C0 (and on police in
   A1b). With 0 from the start no siren ever plays, not even for a vehicle that rolled one. So stock is either
   "every on-screen emergency vehicle, back to back" or "never", per session.

## 5. Fix (sc3simrun SIRENS, `SC3SIMRUN_SIRENS=0` or `[sirens] enabled=0` = stock)

Three parts, each with its own switch for A/B: (a) `per_vehicle` (env `SC3SIMRUN_SIREN_PERVEH`, 0 = off),
(b) `chance_pct` (`SC3SIMRUN_SIREN_PCT`, 100 = off), (c) `cooldown_s` (`SC3SIMRUN_SIREN_COOL`, 0 = off). With (a) off
and (c) on, the stock latch decides and the cooldown only holds it at 0 for that call (restored after).


- (b) CHANCE: imm8 0x50 at STRTSIM `0x100198ce` and `0x1001b44e` becomes `100 - 20 * chance_pct / 100`
  (`[sirens] chance_pct`, % of the stock chance, default 20 = 4 vehicles in 100, 0 = never, 500 = all).
- (a) PERVEH: AUDIO vtable `0x100210ec` slots 12, 13, 14, 21 wrapped for type-0 actors (+0x38 == 0): a table of
  (actor, vehicle) -> state from slot 14, cleared by slots 13 / 21 and by a state 0; before each slot-12 call
  +0x90 = that vehicle's state. The stock slots do the rest.
- (c) COOLDOWN: per actor, while it tracks or is audible the clock is reset; after that a new vehicle cannot start it for
  `[sirens] cooldown_s` (default 30) seconds.
- Each site's bytes / slot values are compared with the shipped ones first; a mismatch leaves that part stock.

## 6. Measured (verify/sirens/RESULTS.md)

Berlin, zoom 5, probe `--force-visible`, 300 s per arm: stock B0 1 start then latch dead (tracked re-roll 0);
stock A1b 5 back-to-back starts in 120 s, none on a vehicle with a siren roll; fix defaults B1 0 starts (13 rolls all
0); fix at 100% chance B2 4 starts on rolled vehicles, B3 with 30 s cooldown 7 starts on rolled vehicles, gaps 15-60 s,
489 cooldown blocks.

Per part, siren starts per 120 s (C-series, final build): stock 5 (A1b, latch ",END"), 0.4 (B0), 0 (C0, latch 0);
(a) only 0.4, all on rolled vehicles, 21% of rolls on; (a)+(b)+(c) 0.2 (C2 + B1), 3.1-3.2% of rolls on.
