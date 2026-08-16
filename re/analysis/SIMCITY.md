# SIMCITY.DLL — GZCOM director analysis

**Binary:** `Apps\SIMCITY.DLL` — PE32 x86, image base `0x10000000`, 892 functions
(Ghidra decomp ok=892/892). SHA-256 `5654604896340ea2212eeffa3097b2feb30aa16e302564fc5de2cf350372a8c1`.
Version resource: `SimCity 3000`, `2.0.949`, `Copyright © 1999 Maxis`, `OriginalFilename SC3U.EXE`.
All facts below are `[CONFIRMED @ 0xADDR]` from `re/ghidra_export_simcity/` unless marked `[UNCERTAIN]`/`[iOS-HINT]`.

## 1. Purpose

SIMCITY.DLL is **not** a layer module — it registers no `SC3*Layer` class and its
`strings.csv` contains no layer-name strings. It is the engine's **master simulation
clock / calendar / scheduler**, plus two small support services (a named-object registry
and a text-token substitution table). Grounding:

- Imports and strings are dominated by timing and threading: `timeGetTime`
  (`WINMM.dll`), `QueryPerformanceCounter`/`QueryPerformanceFrequency`,
  `_beginthreadex`/`_endthreadex`, `CreateSemaphoreA`/`ReleaseSemaphore`,
  `InitializeCriticalSection`, `SuspendThread`/`ResumeThread`/`QueueUserAPC`
  `[CONFIRMED @ strings.csv 0x10016142–0x1001654c]`.
- Calendar strings: `Sunday`…`Monday`, `%2u/%2u/%2u`/`%2u.%2u.%2u`/`%2u-%2u-%2u`,
  with CRT `time`/`mktime`/`localtime`/`_timezone`/`_daylight` `[CONFIRMED @ 0x100171e0, 0x10017254]`.
- Text tokens: `%MAYOR%`, `%YOURNAME%`, `%CITYNAME%`, `%YOURCITY%`, `%POPULATION%`,
  `%YEAR%`, `%PARADENAME%`, `%ANYNEIGHBOR%`, and default name `*NONAME*`
  `[CONFIRMED @ 0x10017348–0x100173a8]`.

Its role relative to the other modules: it exposes the clock through a GZCOM class so the
layer modules register periodic-update callbacks on it. It provides the **tick entry point
and the order layers are driven**, but it does not itself name or contain any layer.

## 2. Director + registrations

```
GZDllGetGZCOMDirector  0x100089b1  → guarded once-init → director ctor FUN_10002491
                                    → returns &DAT_10017448 (the static director)
director ctor          0x10002491  vtables PTR_FUN_100131fc / PTR_LAB_100131d0
register_class wrapper 0x10008d37  inserts {clsid, factory, 0} into map at director+0x14
                                   (via FUN_10008fc8)
```

The director registers **exactly 4 classes** `[CONFIRMED @ 0x10002491 lines 20–23]`:

| GZCLSID | factory RVA | `operator_new` size | ctor RVA | what it builds |
|---|---|---:|---|---|
| `7000` (0x1B58) | `0x1000251d` | `0x70` | `0x10001000` | scheduler/clock class (6 circular callback lists) |
| `0xa1a166cc` | `0x100025bf` | `0x218` | `0x10002709` | **the city-simulator coordinator** |
| `0xe0992413` | `0x1000254f` | `0xb8` | `0x1000e449` | named-object registry (returns `obj+4` sub-interface) |
| `0x80f6a7ed` | `0x1000258d` | `0xc` | `0x1000eb30` | small object, vtable `PTR_LAB_10013f78` `[UNCERTAIN purpose]` |

Note the `0xe0992413` factory returns `object+4` (a secondary interface): `FUN_1000254f`
returns `-(puVar2 != 0) & (puVar2 + 1)` `[CONFIRMED @ 0x1000254f line 25]`.

No `SC3*Layer` string exists here; the layer→module map in `MODULE_MAP.md` already places
all `SC3*Layer` classes in other modules. **OPEN:** the human-readable class names for these
4 GZCLSIDs are not present as strings; class identity is inferred from behaviour only.

## 3. Key subsystems

### 3.1 The simulation clock (`0x10009b35` ctor, object 0x78 bytes)

`FUN_10009b35` builds the live clock the simulator runs on (distinct from the registered
`7000` class; it is allocated internally by the simulator, see §3.2). Layout confirmed by
the ctor and every accessor below:

- **7 circular doubly-linked callback lists**, node size `0x1c`, self-linked heads at
  dwords `[1]`..`[7]` (byte `0x04`..`0x1c`) `[CONFIRMED @ 0x10009b35 lines 23–56]`.
  Lists `[1..6]` (byte `0x04`,`0x08`,`0x0c`,`0x10`,`0x14`,`0x18`) are the 6 **period
  buckets**; list `[7]` (byte `0x1c`) is the **absolute-time alarm list**.
- byte `0x48` = calendar date object (`FUN_100092b6`), byte `0x4c` = **current sim day/tick
  counter**, byte `0x50` = **speed = ticks-per-day, default `0x5a0` = 1440**
  `[CONFIRMED @ 0x10009b35 line 63]`, byte `0x58` = `timeGetTime` reference, byte `0x60` =
  **ms per tick = `86400000 / speed`** (86400000 = ms/day) `[CONFIRMED @ line 72]`, bytes
  `0x64`/`0x68` = derived sleep thresholds `(ms_per_tick/24)` and `/60`, floored to
  `DAT_10017278`, byte `0x6c` = critical-section lock (`FUN_1000d283`, new `0x24`).

**Speed / accessors:**
- `FUN_1000a066` **SetSpeed**: writes `0x50=speed`, `0x60=86400000/speed`, and the two
  thresholds `[CONFIRMED @ 0x1000a066]`. `FUN_1000a0c7` **GetSpeed** reads `0x50`.
- `FUN_1000a0ec`/`FUN_1000a145` **Pause/Resume**: adjust pause counter `0x54` and
  accumulate paused real-time via `timeGetTime` into `0x5c`/`0x58` under the lock
  `[CONFIRMED]`. `FUN_1000a1a4` reads the pause count `0x54`.
- `FUN_10009e53`/`FUN_10009e79` **GetTime/SetTime** read/write `0x4c` under the lock.
- `FUN_10009d5a` **Start**: registers thread callback `LAB_1000a854` on the thread object
  at `+0x20` (its vtable `+0x24`), calls its vtable `+0x14(1000,0)`, sets running flag
  `0x74=1` `[CONFIRMED @ 0x10009d5a]`. `FUN_10009dc2` **Stop** calls thread vtable `+0x1c`,
  clears `0x74`. The clock therefore runs on its **own worker thread** (`_beginthreadex`
  in `FUN_1000d0a9`).

**Scheduling API** (each takes a callback + a 1..6 bucket selector):
- `FUN_1000a330` (repeating) / `FUN_1000a641` (one-shot) **AddPeriodic** — insert into
  bucket list `+0x04..+0x18` selected by param `1..6` `[CONFIRMED]`.
- `FUN_1000a488` / `FUN_1000a796` **RemovePeriodic** — same 1..6 selector.
- `FUN_1000a234` (repeat) / `FUN_1000a546` (one-shot) **AddAlarm** — insert into the
  absolute-time list `+0x1c`, keyed on due-time vs current `0x4c` `[CONFIRMED]`.
- `FUN_1000a2af` / `FUN_1000a5c0` **RemoveAlarm**.

**Callback node** (0x1c bytes): `[0]`/`[1]` next/prev, `[2]` = callback target
(COM object *or* raw function pointer), `[4]` = due time (alarms), `[5]` = user data,
`[6]` = call-convention flag `[CONFIRMED @ 0x1000a915 lines 30–39]`.

### 3.2 The TICK entry point and drive order — `FUN_1000a915` → `FUN_1000a9b1` → `FUN_1000aa4d`

This is the answer to the priority question. The worker thread drives a **cascading
multi-rate scheduler**:

- **`FUN_1000a915` = tick tier 1 (fastest).** Increments `+0x40`, then walks bucket-1 list
  `+0x04` and fires every callback. For a COM callback (`node[6]==0`) it calls
  `(*vtable+0xc)(&msg)` with a 4-dword message `{node[5], 1, 0, 0}` — the `1` is the bucket
  index; for a raw callback it calls `node[2](node[5])`. When `+0x40 == DAT_10017280` it
  resets and calls `FUN_1000a9b1` `[CONFIRMED @ 0x1000a915]`.
- **`FUN_1000a9b1` = tick tier 2.** Same over bucket-2 list `+0x08`, message index `2`.
  When `+0x44 == DAT_1001727c` it resets and calls `FUN_1000aa4d` `[CONFIRMED]`.
- **`FUN_1000aa4d` = day tier.** Increments the **day counter `+0x4c`**, then fires, in
  this order `[CONFIRMED @ 0x1000aa4d]`:
  1. bucket-3 list `+0x0c` — **every day**;
  2. bucket-4 list `+0x10` — if `FUN_100096f0` (day-of-week) signals a week boundary;
  3. bucket-5 list `+0x14` — if `FUN_100095ce` (month component) signals a month boundary;
  4. bucket-6 list `+0x18` — if `FUN_100095af` (year-end distance) signals a year boundary;
  5. the **alarm list `+0x1c`** — fire and remove every node whose `node[4] == day`.

So the **drive order per day** is: bucket1 (sub-tick) → bucket2 → bucket3 (daily) →
bucket4 (weekly) → bucket5 (monthly) → bucket6 (yearly) → due alarms. Layer modules attach
their per-tick / per-day / per-month update handlers by choosing a bucket. `DAT_10017280`
and `DAT_1001727c` are the tier divisors (ticks-per-tier-2, tier-2-per-day) `[UNCERTAIN
values — read as globals, not constants in these bodies]`.

**OPEN:** the thread procedure `LAB_1000a854` (registered in `FUN_10009d5a`) is a bare label
with no exported body, so the edge `LAB_1000a854 → FUN_1000a915` (the real-time pacing that
decides when a tick fires from `timeGetTime`/`0x60`) is not in the export. `FUN_1000a915`
is confirmed as tier-1 by its direct call into `FUN_1000a9b1`; its invocation from the
thread loop is `[UNCERTAIN]`.

### 3.3 Calendar

A full Gregorian date subsystem drives the day/week/month/year boundaries:
- `FUN_100092b6` builds "today" from `localtime` → `FUN_10009511(mon+1, mday, year+0x76c)`
  (`0x76c` = 1900) `[CONFIRMED @ 0x100092b6]`.
- `FUN_10009380` is-DST; `FUN_100093e6` DST start, `FUN_10009473` DST end — with
  hard-coded special years `0x7b6` (1974) and `0x7b7` (1975) and cutover `0x7c3` (1987)
  `[CONFIRMED @ 0x100093e6 lines 14–27]`.
- `FUN_1000a02f` hour-of-day: `((t - timezone) % 0xe10) / 0x3c` with DST `+0xe10`
  (`0xe10`=3600 s/hr, `0x3c`=60) `[CONFIRMED]`.
- `FUN_100096f0` day-of-week `((serial+1)%7+6)%7+1` (serial from `/0x15180`, 86400 s/day).
- Constants: `0x15180`=86400 (s/day), `0x1c20`=7200, `0xe10`=3600.

### 3.4 Threading / high-res timer helpers

- `FUN_1000d0a9` **thread start**: `_beginthreadex(...,LAB_1000d08f,args,...)`, stores
  handle at `this+0xc`, thread id at `this+0x10` `[CONFIRMED]`.
- `FUN_1000d283` **lock ctor**: `InitializeCriticalSection`; the lock object's vtable
  `+4`/`+8` are Enter/Leave, used by every clock method above.
- `FUN_1000d931` **hi-res timer init**: `QueryPerformanceFrequency`, precomputes scale
  factors into `_DAT_10017608..0x10017650` `[CONFIRMED]`. `FUN_1000d9db`/`FUN_1000da1b`
  read `QueryPerformanceCounter` (delta and raw). `FUN_1000addd` sets a `timeGetTime`
  baseline (uses current time if arg `0xffffffff`).

### 3.5 RNG and support services

- `FUN_100071ce` seeds an RNG from `time`+`mktime`+`_timezone` `[CONFIRMED]`.
- `FUN_1000e449`/`FUN_1000e4fe` **named-object registry** (class `0xe0992413`): 4 map/list
  heads (self-referential at `[0x25..0x2a]`), default entry `*NONAME*` `[CONFIRMED @ 0x1000e4fe line 29]`.
- Text-token service: `FUN_1000f16b` (and siblings) install tokens into 8 global tables
  (`DAT_10017688`, `0x100176a0`, `0x100176b8`, `0x100176d0`, `0x100176e8`, `0x10017700`,
  `0x10017718`, `0x10017730`). `FUN_1000f352` resolves a token by trying all 8 tables in
  order `[CONFIRMED @ 0x1000f352]`.

### 3.6 Simulator lifecycle (`0xa1a166cc` object, `0x218` bytes)

- `FUN_10002709` **ctor**: zero-init, three sub-objects via `FUN_10004dc7`, three locks via
  `FUN_1000d283`, calendar via `FUN_100092b6`, `[0x4f]=0x76c` (year 1900), `[0x53]=[0x54]=2`,
  pulls two service pointers from `FUN_10008775` (vtable `+0x20`, `+0x6c`) `[CONFIRMED]`.
- `FUN_10003ea6` **Init/Start** (1015 bytes) — the boot sequence:
  1. Subscribes `this` to 13 message ids via the message server (`FUN_100086c5`, vtable
     `+0x14` = AddNotification): `0x111fdae5, 0xc2684065, 0xc2a35d7e, 0xc2a35d80,
     0xe31e2463, 0x231e2493, 0xc35d7e35, 0x635d7e4a, 0x35d7e51, 0x635d7e57, 0x624a8220,
     0x624a8221, 0x54e23ee9` `[CONFIRMED @ 0x10003ea6 lines 37–62]`.
  2. Creates the clock (`new 0x78` → `FUN_10009b35`) at `this+0x130`, AddRefs it (`+4`),
     calls `+0xc` and `+0x18` `[CONFIRMED]`.
  3. Instantiates sub-classes by GZCLSID (see §5), stores at `this+0x124/0x84/0x88/0x8c/0x90`.
  4. `FUN_100069d8` wires the subsystem vector `this+0x94..0x98` (each entry vtable `+0x24`).
  5. Enumerates registered items via service `DAT_100174ac` and per item runs a filter over
     the `+0x94/+0x98` vector (each entry vtable `+0x38`, on hit calls target vtable `+0x14`).
  6. Sets initialized flag `this+0x28 = 1`.
- `FUN_10004e30` **Shutdown** (742 bytes): mirror image — releases sub-objects and
  **unsubscribes the same 13 message ids** via message server vtable `+0x18`
  (RemoveNotification) `[CONFIRMED @ 0x10004e30 lines 113–138]`.

## 4. Data / tunables (raw hex)

| Value | Meaning | Where |
|---|---|---|
| `0x5a0` = 1440 | default clock speed (game-min/day; ticks-per-day) | `0x10009b35` |
| `86400000` | ms per day; `ms_per_tick = 86400000 / speed` | `0x10009b35`, `0x1000a066` |
| `0x15180` = 86400 | seconds per day (serial-date divisor) | `0x100093e6`, `0x100096f0` |
| `0xe10` = 3600 / `0x1c20` = 7200 | seconds/hour, 2h (DST offsets) | `0x1000a02f`, `0x100093e6` |
| `0x3c` = 60 | minutes/seconds divisor | `0x1000a02f` |
| `0x76c` = 1900 | tm_year epoch offset | `0x100092b6`, `0x10002709[0x4f]` |
| `0x7b6/0x7b7/0x7c3` = 1974/1975/1987 | DST special-case years | `0x100093e6` |
| `0x12345678` | sentinel written by `FUN_1000cef6` | `0x1000cef6[5]` |
| `DAT_10017278` | min sleep-threshold floor | `0x10009b35`, `0x1000a066` |
| `DAT_10017280`, `DAT_1001727c` | tick-cascade tier divisors | `0x1000a915`, `0x1000a9b1` |
| tokens `%MAYOR%…%ANYNEIGHBOR%`, `*NONAME*` | text-substitution keys | strings `0x10017348–0x100173a8` |

No `.IXF`/resource/property keys and no exemplar keys are referenced in the read set.
**OPEN:** the 13 subscribed message ids and the consumed GZCLSIDs (§5) are opaque 32-bit
values; no string maps them to names in this module.

## 5. Cross-module edges

From `FUN_10003ea6` (`GetClassObject` = `FUN_100089a5`, framework vtable `+0x30`):

| GZCLSID | IID | stored at | follow-up call |
|---|---|---|---|
| `7000` | `6000` | `this+0x124` | this module's **own** clock class; vtable `+0xc(this)` |
| `0xe150e7bb` | `0xa1478afe` | `this+0x84` | `+0xc(this, 0x1787abd, 0x826cb9b6, 0x426cb9b3, 0xa26cb9af, 1)` |
| `0xe150e7bb` | `0xa1478afe` | `this+0x88` | `+0xc(this, 0x41c4bf8e, 0xc2bdf178, 0xd2bdf178, 0xe2bdf178, 2)` |
| `0xe150e7bb` | `0xa1478afe` | `this+0x8c` | `+0xc(this, 0x51c4bf8e, 0x2bdf19f, 0x12bdf19f, 0x22bdf19f, 4)` |
| `0x41d30404` | `0xe2bb294f` | `this+0x90` | `+0xc(this, 0xa1bc8323)` |

Also uses framework singletons: message server (`FUN_100086c5` → `FUN_100087a1`),
a service (`FUN_10008775`), and enumerator service `DAT_100174ac` (vtable `+0x14`/`+0x28`).
**OPEN:** the owning modules for `0xe150e7bb`/`0x41d30404` are not resolvable from this
binary (GZCLSIDs are matched at runtime against `SYS.PAK`/`CitySim.ini`, per MODULE_MAP.md).

## 6. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x100089b1,gzcom-director,C2,sc3_simcity_get_director,"PE export; guarded once-init calls ctor FUN_10002491, returns &DAT_10017448"
0x10002491,gzcom-director,C2,sc3_simcity_director_ctor,"sets director vtables, registers 4 classes via FUN_10008d37 lines 20-23"
0x10008d37,gzcom-director,C2,sc3_gzcom_register_class,"stores {clsid,factory,0} into map at this+0x14 via FUN_10008fc8"
0x1000251d,gzcom-factory,C2,sc3_clock_class_factory,"operator_new(0x70) + ctor FUN_10001000 for GZCLSID 7000"
0x100025bf,gzcom-factory,C2,sc3_sim_factory,"operator_new(0x218) + ctor FUN_10002709 for GZCLSID 0xa1a166cc"
0x1000254f,gzcom-factory,C2,sc3_nameservice_factory,"operator_new(0xb8) + ctor FUN_1000e449, returns obj+4 sub-interface"
0x1000258d,gzcom-factory,C1,sc3_smallobj_factory,"operator_new(0xc) + ctor FUN_1000eb30 for GZCLSID 0x80f6a7ed"
0x10001000,scheduler,C2,sc3_scheduler_class_ctor,"builds 6 self-linked 0xc lists, thread pool + lock, calls FUN_10001d20"
0x10002709,simulator,C2,sc3_sim_ctor,"0x218 obj; 3 locks, calendar FUN_100092b6, service ptrs from FUN_10008775"
0x10003ea6,simulator,C2,sc3_sim_start,"subscribes 13 msg ids, creates clock at +0x130, instantiates subsystems"
0x10004e30,simulator,C2,sc3_sim_shutdown,"unsubscribes same 13 msg ids (+0x18), releases sub-objects"
0x100069d8,simulator,C2,sc3_sim_wire_subsystems,"iterates vector +0x94..+0x98 calling each entry vtable+0x24"
0x10009b35,sim-clock,C2,sc3_simclock_ctor,"7 lists 0x1c, calendar +0x48, speed 0x5a0, ms/tick=86400000/speed, lock"
0x10009cb2,sim-clock,C2,sc3_simclock_dtor,"releases 7 lists, thread block, lock +0x1b"
0x10009d5a,sim-clock,C2,sc3_simclock_start,"registers thread proc LAB_1000a854, starts thread, sets running 0x74=1"
0x10009dc2,sim-clock,C2,sc3_simclock_stop,"thread vtable+0x1c, clears running 0x74"
0x10009e53,sim-clock,C2,sc3_simclock_get_time,"reads day counter 0x4c under lock"
0x10009e79,sim-clock,C2,sc3_simclock_set_time,"writes day counter 0x4c under lock"
0x10009f90,sim-clock,C2,sc3_simclock_update_datefields,"sets day-of-week 0x44 (FUN_10009ff4), hour 0x40 (FUN_1000a02f)"
0x1000a066,sim-clock,C2,sc3_simclock_set_speed,"writes speed 0x50, ms/tick 0x60=86400000/speed, thresholds 0x64/0x68"
0x1000a0c7,sim-clock,C2,sc3_simclock_get_speed,"reads speed 0x50 under lock"
0x1000a0ec,sim-clock,C2,sc3_simclock_pause,"increments pause count 0x54, accrues paused time via timeGetTime"
0x1000a145,sim-clock,C2,sc3_simclock_resume,"decrements pause count 0x54, resets timeGetTime base 0x58"
0x1000a1a4,sim-clock,C2,sc3_simclock_get_pausecount,"reads 0x54 under lock"
0x1000a234,sim-clock,C2,sc3_simclock_add_alarm,"inserts callback into abs-time list +0x1c if due>now (repeat flag 1)"
0x1000a546,sim-clock,C2,sc3_simclock_add_alarm_oneshot,"same as add_alarm with one-shot flag 0"
0x1000a2af,sim-clock,C2,sc3_simclock_remove_alarm,"removes matching node from abs-time list +0x1c"
0x1000a5c0,sim-clock,C2,sc3_simclock_remove_alarm_v2,"variant remove from abs-time list +0x1c"
0x1000a330,sim-clock,C2,sc3_simclock_add_periodic,"inserts callback into bucket list (selector 1..6) at +0x04..+0x18, repeat"
0x1000a641,sim-clock,C2,sc3_simclock_add_periodic_oneshot,"same, one-shot flag 0"
0x1000a488,sim-clock,C2,sc3_simclock_remove_periodic,"removes node from bucket list selector 1..6"
0x1000a796,sim-clock,C2,sc3_simclock_remove_periodic_v2,"variant remove from bucket list selector 1..6"
0x1000a915,sim-clock-tick,C2,sc3_simclock_tick_tier1,"fires bucket1 +0x04; on 0x40==DAT_10017280 calls tier2; msg index=1"
0x1000a9b1,sim-clock-tick,C2,sc3_simclock_tick_tier2,"fires bucket2 +0x08; on 0x44==DAT_1001727c calls day tier; msg index=2"
0x1000aa4d,sim-clock-tick,C2,sc3_simclock_tick_day,"advances day 0x4c; fires bucket3 daily,4 weekly,5 monthly,6 yearly, then alarms"
0x100095af,calendar,C2,sc3_cal_days_to_yearend,"date[4] - serial(Dec 31 of year) -> year boundary test"
0x100095ce,calendar,C2,sc3_cal_month_component,"returns month field via FUN_100095ea"
0x100096f0,calendar,C2,sc3_cal_day_of_week,"((serial+1)%7+6)%7+1"
0x1000a02f,calendar,C2,sc3_cal_hour_of_day,"((t-timezone)%0xe10)/0x3c with DST +0xe10"
0x100092b6,calendar,C2,sc3_cal_today,"localtime -> FUN_10009511(mon+1,mday,year+0x76c)"
0x100093e6,calendar,C2,sc3_cal_dst_start,"DST start; special years 0x7b6/0x7b7, cutover 0x7c3"
0x10009473,calendar,C2,sc3_cal_dst_end,"DST end serial; 0x15180 s/day, +0xe10"
0x10009380,calendar,C2,sc3_cal_is_dst,"compares t against dst_start/dst_end; 0 if _daylight==0"
0x100092fa,calendar,C2,sc3_cal_date_copy,"copies date field [+4], sets vtable PTR_LAB_10013978"
0x100071ce,rng,C2,sc3_rng_seed_from_time,"seed from time()+mktime()+_timezone, low nibble from FUN_1000adf8"
0x1000addd,timing,C2,sc3_timer_set_base,"sets timeGetTime baseline (uses now if arg 0xffffffff)"
0x1000d931,timing,C2,sc3_hrtimer_init,"QueryPerformanceFrequency, precomputes scale factors to _DAT_10017608.."
0x1000d9db,timing,C2,sc3_hrtimer_read_delta,"QueryPerformanceCounter minus base at +0x10/+0x14"
0x1000da1b,timing,C2,sc3_hrtimer_read,"raw QueryPerformanceCounter into out param"
0x1000d0a9,threading,C2,sc3_thread_start,"_beginthreadex(LAB_1000d08f,args); handle +0xc, id +0x10"
0x1000d283,threading,C2,sc3_lock_ctor,"InitializeCriticalSection; vtable+4/+8 = Enter/Leave"
0x1000cef6,threading,C1,sc3_thread_obj_ctor,"inits obj with sentinel 0x12345678 at [5], vtable PTR_LAB_10013bd0"
0x100086c5,gzcom-service,C2,sc3_get_message_server,"lazy singleton DAT_100174cc; +0x14 add / +0x18 remove notification"
0x10008775,gzcom-service,C2,sc3_get_service_b,"lazy singleton DAT_100174fc used by sim ctor"
0x100089a5,gzcom-service,C2,sc3_get_class_object,"framework singleton vtable+0x30 = GetClassObject"
0x1000e449,name-service,C2,sc3_nameservice_ctor,"registry obj; 4 map heads self-linked at [0x25..0x2a]"
0x1000e4fe,name-service,C2,sc3_nameservice_names_ctor,"seeds registry with default name *NONAME*"
0x1000eb30,unknown,C1,sc3_smallobj_ctor,"0xc obj: [1]=[2]=0, vtable PTR_LAB_10013f78"
0x1000f16b,text-tokens,C2,sc3_token_install_mayor,"installs %MAYOR% into token table DAT_10017730"
0x1000f352,text-tokens,C2,sc3_token_substitute,"resolves a token across 8 tables 0x10017688..0x10017730 in order"
```

## 7. OPEN (undetermined + missing evidence)

- **Real-time pacing loop.** The clock's thread procedure `LAB_1000a854` (registered in
  `FUN_10009d5a`) has no exported body (bare label — the GZCOM/thread-callback trap). The
  logic that reads `timeGetTime`, compares elapsed against `ms_per_tick` (`0x60`), and calls
  `FUN_1000a915` is therefore not in the export. *Missing:* a disassembly of the range
  `0x1000a854`–`0x1000a915` from live Ghidra.
- **Tier divisors `DAT_10017280`, `DAT_1001727c`.** Read as globals in the tick cascade;
  their initialized values are not in these bodies. *Missing:* `globals.csv` value or the
  writer function.
- **Consumed GZCLSIDs `0xe150e7bb`, `0x41d30404` and the 13 subscribed message ids.** Opaque
  32-bit ids; no name strings here. *Missing:* the `SYS.PAK`/`CitySim.ini` id→name table, or
  a cross-module director scan matching these clsids to a factory in another `Apps\*.DLL`.
- **`0x80f6a7ed` (0xc-byte class) purpose.** Only its ctor was read (two zeroed fields +
  vtable). *Missing:* its vtable methods (`PTR_LAB_10013f78`) and call sites.
- **iOS cross-check not performed.** `goCitySimulator`/clock naming in
  `re/ghidra_export_ios/` was not consulted in this pass; any equivalence is `[iOS-HINT]`
  and unverified. *Missing:* a grep of the iOS export for the clock/tick algorithm to
  corroborate the bucket-cascade structure.
- **Relationship between registered class `7000` (ctor `0x10001000`, 6 lists) and the
  internally-allocated clock (`FUN_10009b35`, 7 lists).** Both are schedulers with similar
  shape but different sizes/list counts; whether `7000` wraps or supersedes the internal
  clock is undetermined. *Missing:* the body behind the `7000` interface methods
  (`this+0x124` in `FUN_10003ea6`).
