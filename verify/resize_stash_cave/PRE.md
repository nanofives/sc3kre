# PRE-REGISTRATION — bridge_stash CAVE witness (committed BEFORE the lease)

Owner: resizeship session. 2026-08-26. The falsifier already passed (g_bridge survives+validates a resize,
single view). This witnesses the pure-DLL STASH CAVE itself: does the position-independent inline hook at
FUN_10016eba write the SAME valid bridge pointer into the .data slot that the harness's independent
g_bridge capture proved good? Direct comparison, not a proxy.

## Instrument
Probe `sc3probe.dll` sha256 `5bf13b679ef95d545f33ba560a511dcb1546640e24558f188f562143c3a527b8` (281088 b).
`stash_witness` (SC3PROBE_STASH_WITNESS) now also reads the cave's `.data` slot: slot0 `SIMSPR+0x72f80`
(bridge), slot1 `SIMSPR+0x72f84` (generation), and compares slot0 to `g_bridge`, validates its `+0x18` iso
vtable, PRE- and POST-resize. **SIMSPR = shipped + `bridge_stash` ONLY** (isolate the cave; 27 bytes / 5
runs, sha of the built DLL recorded at run; position-independent, assembly-verified). Env `SC3PROBE_RESIZE=1
RESIZETO=1280x1024 RESIZEAT=22 SC3PROBE_STASH_WITNESS=1`, Europolis, `-AtSec` under 800.

## Outcomes, committed in advance
| slot (PRE and POST) | conclusion |
|---|---|
| **slot0 == g_bridge, slot0 bridge readable, iso(slot0+0x18) vtable OK, gen >= 1 - BOTH phases** | **CAVE STASH CONFIRMED** - the pure-DLL position-independent cave wrote the same valid pointer the independent capture proved good, and it survives the resize. The stash mechanism ships. |
| slot0 == 0 | the cave did not fire (hook not hit / not staged) - report, VOID for the cave. |
| slot0 != g_bridge (both nonzero) | the cave stashed a DIFFERENT pointer (wrong ECX at the hook, or FUN_10016eba `this` != bridge) - report. |
| slot0 valid PRE but 0 / unreadable POST | the stashed pointer went stale across the resize - report; a per-resize re-capture would be needed. |
| iso(slot0+0x18) vtable mismatch | slot0+0x18 is not the iso class - the one-stash-yields-both assumption fails; report. |

Also confirms: generation increments (>=1 per FUN_10016eba call); SIMSPR runtime base (position-independence
tested if relocated). g_bridge validation (the falsifier) re-runs alongside as the control.

## Provenance / restore
SIMSPR = shipped + bridge_stash for the run (isolates the cave; camera reverts to stock, irrelevant here).
**Owner's four-recipe gentle build re-staged + verified as the LAST action** (BOARD standing rule).
GZGraphicD stays as the live hardened build. Own lease + own harness claim (probe rebuilt `5bf13b67`).

## STATUS
Cave BUILT + `--diff`-verified (27 bytes / 5 runs, position-independent, no absolute address). Probe BUILT.
Pre-registered. Not yet run.
