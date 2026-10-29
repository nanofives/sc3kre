# STATUS zonedemo (2026-10-29)

## goal
Owner 2026-10-29: (1) zoning over zoned buildings of another zone type demolishes them and zones the cells, same type
stays as stock; (2) DeZone demolishes the zoned buildings on the cells it de-zones.

## verdict + deciding RVA
Done. Stock refuses every building cell for every zone tool: CanZone SIMRCI `0x1003559f` (zone iface vtable
`0x1004d1e0` +0x84), PlaceZone `0x1003591f` (+0x88), called by the zone tool (vtable `0x1004c06c`) at `0x1000b7f3` /
`0x1000b8cc` and by its cost slots `0x1000b931` / `0x1000b973`. sc3resize ZONEDEMO wraps both slots for calls from the
zone tool only. Spec `re/analysis/ZONEDEMO.md`.

## built
`dev\zonedemo\inst\sc3resize.dll` (sc3dev build zonedemo -Mods sc3resize, no warnings).

## proven game-side vs static only
Game-side (Berlin, `verify/zonedemo/RESULTS.md`): stock refusal (S), Res Low over industrial (T1, 9 removed, $180),
Res Low over residential untouched (T2), DeZone over a mixed block (T3, 61 removed, $448), undo of T3 (restored,
refunded, maps identical). Static only: switch off, airport/seaport/landfill unchanged, slope cells.

## blocked on
Nothing.

## files owned (worktree dev\zonedemo\wt, nothing committed)
- `re/harness/src/sc3resize.c` (block ZONEDEMO after ROADOVER + its thread start next to ro_thread, +155 lines)
- `re/analysis/ZONEDEMO.md` (new)
- `re/tools/zonedemo_probe.py` (new)
- `verify/zonedemo/RESULTS.md` (new)
- this file, `MAIN\re\sessions\STATUS_zonedemo.md`
Pictures in `MAIN\verify\zonedemo\owner_shots\` (never git add).

## game-harness need
None. No game running.

## asks of other sessions
None. Switch: reuses "Construir sobre zonas" (g_plopover), no mods-page change, so no collision with the mods page
layout stream.
