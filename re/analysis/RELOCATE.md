# Moving reward / landmark buildings, and placing buildings over zoned ones (sc3resize RELOCATE + PLOPOVER, task relocate 2026-10-28)

Owner requests (2026-10-28):

- A: "podemos agregar un botón en el '?' de un edificio especial de premios o remarcables para recolocarlo? al hacerlo
  demuele el original y reemplaza la ubicación del otro"
- B: "colocar edificios de prop puede hacerse sobre edificios con zonas? que sea autodemoler y colocar?"

Code: `re/harness/src/sc3resize.c`, block `RELOCATE + PLOPOVER` after `qi_install`. Switches: `SC3RESIZE_RELOCATE=0` removes
the button. `SC3RESIZE_PLOPOVER=0` makes zoned buildings refuse a placement again (stock). With both at 0 nothing is
installed. Evidence: `verify/relocate/RESULTS.md`. Census tool: `re/tools/relocate_probe.py`.

## 1. The placement path

| piece | address | what it does |
|---|---|---|
| building layer | city vt+0x138, interface vtable SIMGEOM `0x100292c0` | |
| CanPlace kinds 0..3 | layer +0x24..+0x30 = `0x10006a65`, `a82`, `aa0`, `abe` | `0x10006ba6(coord, key, bounds, cost, free 0, kind, doPlace 0)` `[CONFIRMED @ SIMGEOM 0x10006a65]` |
| multi-cell | layer +0x34 = `0x10006adc` -> `0x10006df6` | not hooked |
| Place kinds 0..3 | layer +0x38..+0x44 = `0x10006b02`..`0x10006b5f` | `0x10006ba6(..., free, kind, doPlace 1)` |
| check + place | `0x10006ba6` | key -> attrib (size), in-city test, site check `0x100072f6`, with doPlace: funds test unless free, then commit `0x10007760` |
| site check | `0x100072f6` | water (DirtBag +0x54) or shoreline rules, terrain levelling DirtBag +0x100, layer +0x34 vt+0x50, then the occupant loop below. Adds the build price `budget vt+0x54(type id)` unless free |
| occupant loop | `0x100076a2..0x1000770f` | for each occupant in the footprint (manager +0x74): accepted only if IsGeomFlag(0x400) or (IsGeomFlag(0x400000) and IsGeomFlag(0x800)), then CanUserRemove (vt+0x74). The per-tile price `budget vt+0x58(7)` ([ebp-0x30]) is added once per occupant into [ebp-0x14] `[CONFIRMED @ 0x100076b4..0x100076f5, disassembly]` |
| commit | `0x10007760` | removes flora (0x400) and 0x800+0x400000 occupants (power-line pieces), inserts, zone 22 over the footprint (zone vt+0x38, `0x10007d1b`), withdraws the cost unless free |
| tool factory | layer +0x70 = `0x10007e64(key, oneShot, free, riid, out)` | ctor `0x10009443`: key at tool+0x108, free at tool+0x114, one-shot at tool+0x115 (sets +0x3b after a placement, base `0x1002141b` then ends the tool) |
| tool from a key | layer +0x54 = `0x10007d5b` | factory then out vt+0x2c (select), out vt+8. The picker's OK goes through +0x50 `0x10007d99`, same factory, free 0 |
| tool Apply | vt+0x48 of tool vtables `0x10029504` (plain), `0x10029734`, `0x100295e4`, `0x1002968c` | calls CanPlace with tool+0x108, then Place with tool+0x114 as `free` |

GeomFlag (occ vt+0x48, IsGeomFlag vt+0x3c = `(flags & f) == f`, SIMGEOM `0x1001cef4`), measured over every occupant of
Berlin (`verify/relocate/census_berlin.json`): every building is 0x104 (utility plants 0x400104 / 0x800104, transit
0x4104 / 0x44104, group-demolish 0x40000104), flora 0x404, network pieces 0x800 + 0x4 + type bits (road 0xc804, power
line 0x400804). So the stock rule clears trees and power lines and refuses every building. The zone byte under an
occupant (zone layer vt+0x34) separates them: RCI-grown buildings (SIMGEOM `0x2bbe8` / `0x2a578`) sit on 1..11, civic,
reward and landmark buildings on 22 (or 0 in Berlin's older plops), airport 14, seaport 15, landfill 17.

## 2. Bulldozer

Demolition layer = city vt+0x194 (SIMGEOM vtable `0x1002a7b4`, factory `0x10012cf9`). vt+0x58 `0x100134fb`
Demolish(manager, rect, filter, priv, freeOfCharge, cost*, box*): per occupant, then a network retile message, then
budget Withdraw unless free. vt+0x6c `0x1001408d` DemolishOccupant(occ, priv, cost*, box*, netmask*): the per-occupant
entry, no charge, no removability check, removes the occupant from each manager. No rubble on either path. Per-tile
price `+0x60` = budget vt+0x58(7) times the footprint.

## 3. "Already built"

- Rewards: SIMADV advisor (ctor `0x10017ba8`), items vtable `0x10031178`, byte +0x54 "unlocked" is only ever set
  (`0x100193dc`, `0x1001a3ec`, `0x1001a4ae`). The advisor does not count placed occupants and does not listen to
  occupant events. A reward stays placeable after a demolish. Relocating cannot lose it.
- Landmarks: SIMADV advisor `0x10006656` subscribes to occupant inserted / removed. Insert `0x1000b32a` sets placed=1,
  remove `0x1000b458` sets placed=0. Remove then insert ends at placed=1, the state before the move.
- Business deals (casino, prison, toxic plant, mall, castle): the same advisor calls the budget advisor (city vt+0x1b0,
  SIMADV vtable `0x10030310`, measured) on those events. Remove -> vt+0x18 `0x100060ea(type)`: deal inactive, occupant
  NULL. Insert -> vt+0x14 `0x1000607e(type, occ)`: deal active, occupant = the new building. No payment in either.
  Monthly deal income `0x10006277` sums the active deals that have an occupant. So a move ends and restarts the deal
  with the same monthly amount. Measured on Berlin's Prison: before and after, deal 19004 active, $250/month, total
  $650/month; only the occupant pointer changed.

## 4. What the mod does

1. The 8 layer slots (+0x24..+0x30, +0x38..+0x44) are wrapped. A call made by a building tool is recognised by its key
   pointer: key - 0x108 has one of the four tool vtables. Only those calls set a context. Scripts and direct callers
   stay stock.
2. A cave at `0x100076b4` keeps the stock rule. With the context it also accepts:
   - (B) a building (IsGeomFlag 0x100), CanUserRemove, with zone byte 1..11 under its first cell. It is charged what the
     bulldozer charges (per-tile price times its footprint) and put on a kill list.
   - (A) the occupant being moved, at no cost.
3. A detour on `0x10007760` (the commit, so only after the check passed) removes the original being moved and the kill
   list through DemolishOccupant, then lets the stock commit run. A refused spot demolishes nothing.
4. "Mover" in the "?" dialog. It appears for type ids in `[REWARD_BUILDINGS]` and `[BUSINESS_DEAL_BUILDINGS]`
   (Advisor-CityPlanner.ini) and for landmarks 18001..18999 (CitySim.ini `[AgentTypeHierarchy]`). The click does three
   things:
   - AddRef the occupant and remember its attrib key, type and cell rect.
   - Close the dialog the way its close box does (message 3, p3 1, id `0x42b7c353`).
   - 250 ms later, from a thread timer, make the game's own tool through layer +0x70(key, one-shot 1, free 1) and select
     it (vt+0x2c).

   The timer is needed: started inside the click, the button-up of the same click reached the new tool, which ran
   Apply without a button-down and faulted on its unset +0x10 (SIMGEOM `0x10021a84`, measured).
5. Cost (owner call 2026-10-28): 50% of the building's price plus the bulldozing and levelling the game would charge.
   The tool keeps the game's free flag, so the stock check leaves the price out and the stock commit withdraws nothing.
   CanPlace's stock path hard-codes free 0, so for the move tool the wrapper calls `0x10006ba6` with free 1. The check
   then returns clearing + zoned bulldozing + levelling. The cave tallies the first two, levelling is the rest.
   `rl_cost` adds `RL_PRICE_PCT`% of the price (layer budget +0x30 vt+0x54(type id)) and the bulldozing of the original
   (per-tile price vt+0x58(7) x its footprint, what the bulldozer charges). It writes the total into the check's cost
   output, which the tool shows on the cursor label and tests funds against (+0x34, base `0x100214b8`). After a
   placement the wrapper withdraws the same total (budget vt+0x14, the slot the commit uses) and logs the parts.
   One-line changes: `#define RL_PRICE_PCT 50`, or `SC3RESIZE_RELOCATE_PRICEPCT=<0..100>`.
   `SC3RESIZE_RELOCATE_CLEARCOST=0` drops the bulldozing and levelling charge. Both 0 = free. Escape is the
   stock cancel and leaves the original (tested). Right-click was not tested. The pending move (and our reference) is dropped on the
   next Mover or after the move; across a city change the reference is dropped without Release. If the original is
   gone by the time of the placement (disaster, bulldozed), the move tool refuses every spot.
6. The button goes on the bottom row left of "Copiar ID". When that rect hits one of the game's own controls (the
   "Sustituir" button of the Mayor's House, 308 px dialog), it moves one row up, right-aligned.

## 5. Not covered

- The multi-cell layer slot +0x34 (tools for key instances 0x1f98, 0x1f8b, 0x1f5d) is not wrapped. Those placements
  stay stock.
- No interplay test with sc3undo. Its journal records occupant Remove/Insert during a tool Apply, and the removals here
  go through the manager's Remove, so an undo should restore them. Not run.
- Business-deal moves and the shoreline / plumbing / subway tool kinds were not exercised in game.
