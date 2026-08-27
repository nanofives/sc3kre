# PRE-REGISTRATION — hardened X-cave re-witness (committed BEFORE the lease)

Owner: resizeship session. 2026-08-26. The X-cave was shipped ABSOLUTE and would crash on WM_CLOSE when
GZGraphicD relocates (measured: base is a load-order coin flip). Hardened to position-independent
(call/pop EIP, ebx-relative IAT/strings). Owner: "do not ship the fix on inspection alone" - so this
witnesses the hardened cave actually quits the game, ideally under relocation (the failure case).

## Instrument
Probe `sc3probe.dll` sha256 `f13c9d3a4068964b84d4ef93a578fada434eb8947d4ca4298ba9ac4e5421bed7` (280576 b),
verb `SC3PROBE_XCLOSE_TEST`: at t+12s, `PostMessageA(gameHwnd, WM_CLOSE, 0, 0)` and log the GZGraphicD
runtime base. **Run WITHOUT `SC3PROBE_RESIZE`** so the message reaches the game's own WndProc (no harness
subclass) and hits the cave. GZGraphicD = `resizable_frame` + hardened `close_button_quit` (sha
`acefadf09eaba4b0…`). SIMSPR = live four-recipe (irrelevant to WM_CLOSE). `-AtSec 60` (the game should quit
well before that).

## Outcomes, committed in advance
| observation | conclusion |
|---|---|
| **game exits cleanly ~t+12s** (process gone, no `C0000005`, no exception in the log) | the hardened cave works - `PostQuitMessage` fired, the PeekMessage loop exited. If GZGraphicD base != 0x10000000, this specifically clears the relocation case the absolute version would have crashed on. |
| **crash / `C0000005`** right after the WM_CLOSE line | the cave FAULTED - position-independence is wrong; do NOT ship, report the fault. |
| game runs to `-AtSec` (no exit) | WM_CLOSE did not reach the cave or the cave did not PostQuitMessage; report (the je-redirect or the resolve failed - check fail-closed). |
| no game window at t+12s | VOID - report only that. |

## Base note (first-class)
Log records GZGraphicD base. **relocated (base != 0x10000000) is the STRONG result** - it exercises the exact
condition that crashed the absolute cave. base == 0x10000000 is a weaker pass (the absolute version would
also have survived); if so, note the run did not exercise relocation, though the code is base-agnostic by
construction.

## STATUS
Probe BUILT (`f13c9d3a…`), hardened GZGraphicD staged (`acefadf0…`, --diff 72 bytes / combined). Harness
claim held. Pre-registered. Not yet run.
