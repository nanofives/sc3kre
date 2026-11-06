# CHEATFIX: Extra Cheats' SimDate now changes the date (child/simdate, 2026-11-06)

Symptom (verify/civicdeals/RESULTS.md): `SimDate <m> <d> <y>` left the date unchanged; `dotcom`, `moolah` worked.

## Cause (measured)

- The plugin (upstream src/ExtraCheatsDllDirector.cpp) calls `cISC3City::SetDate(m, d, y)` at vt+0x1ec and
  `GetDate(doy, y)` at vt+0x1e8 (disassembly of SC3KExtraCheats.dll 0x100025c7 / 0x100025eb): the right slots
  (SIMCITY 0x10005398 / slot 122). Not the cause.
- Frida on SIMCITY 0x10005398: never called after `SimDate 5 20 1990`.
- Frida on `cGZCheatCodeManager::DoesCheatCodeMatch` (SC3U 0x0046ac89) and `SendCheatNotifications` (0x0046ac27):
  the text matched id **0xE352E88F**, which the manager's own list names `"sim"` (a stock cheat). The match lower-cases
  the input and returns the first registered cheat the text starts with; "sim" is registered before "SimDate"
  (0x1F92F286), so SimDate could never be reached in any game with the stock cheat list. `moolah` -> 0x35F29FB9 and
  `dotcom` have no shorter stock prefix. Not caused by our mods or the GOG build.

## Fix

`re/harness/src/sc3resize_cheatfix.c` (git add -f): DoesCheatCodeMatch detoured (5-byte `mov eax, 0x4c7a84` prologue).
After the stock match, text "simdate" + space or end with the result "sim" becomes SimDate's id, only while
SC3KExtraCheats.dll is loaded. `SC3RESIZE_CHEATFIX=0` off.

| check (dev/simdate tree with Civic Deals + Extra Cheats, Craterville) | result |
|---|---|
| `SimDate 5 20 1990` | log `CHEATFIX> ... sent to SimDate`; SetDate(5, 20, 1990) returns 1, city+0x138 2427352 -> 2448032; status bar 10/6/1933 -> 5/20/1990 |
| `sim` | still id 0xe352e88f (stock) |
| `simcity` | still its own id 0xe352e809 |
