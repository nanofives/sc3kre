# crashguard: the "crash after 20 minutes" (Simtropolis reports, 2026-11-10)

Reports: two Simtropolis players (one of them mmpalhano) crash after about 20 minutes of play.

Verdict: **reproduced, root cause found in our own code, fixed.** sc3resize took one reference too few on the
valve layer every time it read the demand valves (graphs and RCI bars; measured rate about one per game month at
speed 4). The layer starts with
about 100 references on Europolis 1024, so after about 100 game months it was destroyed under the sim thread and the
next `sc3_valvelayer_end_of_month` crashed. Fix VALVEREF in `sc3resize_graphs.c` (`gn_ctx`) and
`sc3resize_rcibars.c` (`rcb_read`). The crash guards ported from thronevintagetech's SC3KU package do not prevent this
crash, but RCZERO's log line is what found it.

## Run 1: soak with the ported guards (sc3perf RCZERO + VALVESHUT), stock sc3resize

Europolis 1024 (dev tree `crashguard`, windowed 800x600, all 11 mods), speed 4, no input after the unpause. Unpaused
07:04, crashed 07:29 at game day 3073 (about 101 months). Memory was flat (private 242 -> 324 MB, largest free block
792 -> 744 MB), so not the 10-29 address-space leak.

```
[2298087.178 ms] RCZERO> #1 Release at count 0 skipped: object 0x14F8E938 vtable SIMRCI.DLL+0x4CEE4, caller SIMRCI.DLL+0x2F336, thread 11284
   ... 32 lines in 0.4 ms, same object, callers SIMRCI+0x2F336 / +0x25DEC / SIMMISC+0x2906A / SIMRCI+0x2F491 (x28) ...
[2298904.314 ms][tid 22c4] RZ   *** VEH FAULT *** code=0xC0000005 at SIMRCI.DLL+0x312CC   access=READ addr=0x00000008
   esi=14F8E938  [esp] = SIMRCI.DLL+0x2F1D2 (sc3_valvelayer_end_of_month)
```

- `0x1004cee4` is the valve layer's main vtable (slots 0/1/2 = `sc3_valvelayer_queryinterface` 0x1002ef6b /
  `_addref` 0x1004312b / `_release` 0x1002efb8, +0xc = `sc3_valvelayer_end_of_month` 0x1002efe8, +0x38 the deleting
  destructor), right after its cISC3CityLayer interface vtable 0x1004ce9c. Count at +8 (AddRef `inc [esi+8]`).
  [CONFIRMED, PE vtable read]
- The 32 releases at 0 came from the valve agent classes' shutdown-style methods (each releases its `+8` layer
  pointer and its list's references), on the game thread. The sim thread then ran end_of_month on the layer
  (`esi`) and faulted in a valve's `vt+0x78` (FUN_100312c9 reads `[this+0xc]+8`, `this+0xc` = 0).

## Run 2: RCTRACE (new sc3perf diagnostic)

`rc_trace=SIMRCI.DLL:0x4cee4` counts every AddRef / Release on objects with that vtable per call site (return address
and the next one up the stack). Valve layer count over the first three minutes: 100, 99, 95. Every game site was
balanced (SIMUI +6 / -6, ...); sc3resize was +5 / -10:

```
net -5  (+0 -5)  sc3resize.dll+0x5D4AB < ...      Release, through the thiscall helper rz_thiscall_ret
net -5  (+0 -5)  sc3resize.dll+0x5D4AB < ...      a second Release, other stack
net +5  (+5 -0)  SIMRCI.DLL+0x2EFB2 < sc3resize   AddRef inside the layer's QueryInterface
```

The three readers of the valve layer in sc3resize all do `L = city vt+0x1b8(0x80f1e6d3)`, then
`QI(L, 0x40a42f1c, &vl)`, then use `vl` and Release it. `gn_ctx` (GRAPHNEW) and `rcb_read` (RCIBARS) also Released
`L`. City `vt+0x1b8` is `cISC3City::GetSpecificLayer(ulong)` (CodeView) and returns a borrowed pointer: no AddRef from
it appears in the trace. So each call was 1 AddRef and 2 Releases. `ph_valves` (PLACEHINTS) never released `L` and was
already right.

## Fix: VALVEREF

`gn_ctx` and `rcb_read` no longer Release `L`; only the QI reference is released. No other `GetSpecificLayer` call in
any mod source.

## Run 3: fix + RCTRACE

Same city and settings (sc3resize.dll sha256 prefix e0981c7367057904, sc3perf.dll fecc741d7a6fec68). Unpaused
07:40, stopped by me at 08:06 at game day 3588 (about 118 months, 515 days past run 1's crash). No fault besides
the startup `0xC0000096 @ SC3U+0x84122`, 0 RCZERO lines, private memory 281 MB at the end.

| t (s) | valve layer count | adds | releases |
|---|---|---|---|
| 63 | 102 | 117 | 18 |
| 543 | 102 | 188 | 89 |
| 1023 | 102 | 263 | 164 |
| 1503 | 102 | 340 | 241 |

sc3resize +113 / -113 over the run (one round per game month), SIMUI +115 / -115.

## The ported crash guards (kept, all on by default, each with an off switch)

From thronevintagetech's SC3KU Enhancement Package v2026.11.09 (MIT), checked against our SIMRCI disassembly:

- **RCZERO** (sc3perf `rc_zero`): a Release that finds the count already 0 returns 0 instead of running the deleting
  destructor again (the stock F2/F3 bodies and our atomic copy did). Logged with caller and vtable. It turned run 1's
  double destruction into a clean log line, which is how the over-release was found.
- **VALVESHUT** (sc3perf `valve_guard`, `valve_hold`, `valve_lock`): in `sc3_valvelayer_shutdown` 0x1002ecbc the
  second drain loop gets the null check the first loop has (0x1002ed56 / 0x1002ed5e), both loops leave on an empty
  tree, the forwarder 0x1002e9da refuses a NULL `+0x38`, Shutdown re-entry for the same layer returns at once, the
  layer holds a reference while Shutdown runs, and Shutdown and the forwarder share one lock. Installed at 1.3 s on
  all runs (`VALVESHUT> SIMRCI ...: guard=1 hold=1 lock=1`). No re-entry or refused call was logged in these runs;
  the teardown paths (New City / Load City from a loaded city) were not exercised (needs a free screen: owner check).

## Not checked

- New City and Load City from a loaded city with these builds (the saltfix record's SIMRCI crash 25-160 s after a
  New City is still open; whether VALVESHUT changes it is unknown).
- English-UK and other cities. The layer's starting count on other cities was not measured, so how many months the
  old build lasted elsewhere is [UNCERTAIN].
- thronevintagetech's Combined package has the same over-release (`graphsampling.inc` 696-699 and its copies of
  `sc3resize_graphs.c` / `sc3resize_rcibars.c`), so their players hit the same crash until they take the fix.
