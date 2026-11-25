# lfstall results (2026-11-25)

Player report against sc3landfill (sc3mods-2026-11-24): "I zoned a landfill and things were working fine when all of
the sudden lots started being covered in garbage despite the landfill not being filled. The graph shows some line
dropping. I also noticed that one of the tiles became unselectable. Creating another landfill solved the issue, but that
one spot is still acting weird. This happened before on a previous patch." Their screenshots: one landfill, 36% full
(58,290 t free), Environment graph "to landfill" about equal to "garbage made" every month, then 0 in the last month.

Tree `dev\lfstall\tree`, mods from `dev\lfstall\inst`, posted input only (sc3io), pictures by the game's frame dump into
`MAIN\verify\lfstall\owner_shots\` (not committed). Log lines from `inst\sc3landfill.log` with
`SC3LANDFILL_VERBOSE=1`.

## Cause

`g_dev`, the landfill developer (the `this` of UpdateCell SIMRCI `0x10019de1`), was taken from the first UpdateCell
call of the process and never again. Every city has its own developer object. In a second city in the same game (Load
City, or New City after playing a city with a landfill) the wrapper `lf_update` saw `dev != g_dev` and ran the stock
UpdateCell for every cell, so no per-landfill pending ever went down. The router (SIMECO `0x100094a2`, replaced) still
charged each garbage request to the landfill's pending (`grp_take`). Once pending reached the landfill's room,
`grp_free` was 0 and the router refused all garbage: it stayed on the lots, the stock deposits drained what the valve
still held and then stopped ("to landfill" 0), and the landfill stayed part empty.

This matches the player's graph: deposits followed production every month (stock deposits were working), then stopped
in one month, with no slow build-up first. The stuck state was only in sc3landfill's memory: the game's own valve was
clean (Frida read in the stuck city: valve waiting 0, room 1,824,956). Restarting the game cleared it. A second
landfill helped because it was a new group with pending 0 (the router sent garbage there), and it would have stalled the
same way after taking its own room. The first landfill kept its stuck pending ("that one spot is still acting weird").

The orchestrator's leading hypothesis (the stock deposit step puts nothing down for that landfill) was not it. In the
first city of a session the heap list and deposits behave normally (Moscow, 191 cells, one heap entry, every
UpdateCell put down its landfill's whole pending: `HEAPS> 1 heap entries, 1 origins, 0 on a non-landfill cell`).

## Fix (re/harness/src/sc3landfill.c, LFSTALL)

- The groups, their pendings and the developer belong to one city, keyed by its garbage valve (router `self+0x158` =
  developer `+0x3c`). A new valve drops every group and pending (`CITY>` log line). `lf_update` adopts each city's
  developer (`DEV> ... a new city's`), and the router drops a stale developer so the Vaciar button never uses a freed one.
- The router keeps sum(pending) = valve waiting from its side too: when the valve holds less than the pendings claim, the
  difference comes off the largest pendings (the shortfall half of `reconcile`, which `lf_update` already did). Pending
  only rises together with the valve's waiting, so a shortfall means garbage left the valve without passing the wrapper.
  That pending is phantom, and this alone keeps a landfill from blocking if the wrapper ever misses its developer.
- Self-heal, two triggers, `HEAL>` log line. Off: `SC3LANDFILL_HEAL=0` or `heal=0` in landfill.ini.
  - Router side: a landfill that refuses garbage while it has room (pending >= room) more than 100,000 times with no
    UpdateCell of its cells in between. Covers any case where the wrapper stops running for a landfill.
  - UpdateCell side: 32 of a landfill's own UpdateCells in a row with pending and room, a heap visible or the cell
    active (so the stock code could start one), and nothing put down.
  - Either way the landfill's pending is released: the valve's waiting drops by the same amount through its own adder
    vt+0x40, so waiting = sum of pendings still holds, and the landfill takes garbage again. The released garbage is
    gone (like a free export), and the log says how much.
- Saves: nothing new is saved. Pending is transient, so a city saved while stuck loads clean.
- Diagnostics with verbose=1: `HEAPS>` (heap list by origin cell, zone, label, active, fill), `BOOK>` (valve room
  against the sum of active cell room and valve waiting against the sum of pendings, on the sim thread, once a minute),
  `LEFTOVER>`. `SC3LANDFILL_TEST_FIRSTDEV=1` brings back the old first-developer capture (test only, to show the heal).

## A/B

All runs: Moscow (or Madison) first, then Load City Farmsville in the same game, top speed, verbose log.

| run | build | result | evidence |
|---|---|---|---|
| A, before | sc3landfill as released (plus diagnostics) | **STUCK.** No `DEV>` line for Farmsville (its UpdateCells ran stock), group fill/room frozen, pending one minute apart: 23,128, 430,200, 840,224, 1,249,260, 1,445,416, 1,575,083 = room, then refusals ("short of local room" 31,735, then 80,183). Query: "Este vertedero: 10% completo, 19,809 de 196,602 ton." (stock panel 11%, the same 1-point gap as the player's 36/37), garbage on the lots behind. Valve read by Frida in that state: waiting 0, room 1,824,956. | `owner_shots/01_stuck_landfill_z3_r0.png` (lots still clean), `02_stuck_1_query.png` (10%, garbage on the lots) |
| B, after | LFSTALL fix | **FLOWS.** `DEV> ... a new city's (the previous one was dropped)`, `CITY> new city (valve 0x1554AEB8, was 0x1505DEA8)`. Pending one minute apart: 1,036, 1,812, 1,392, 1,348, 1,404, 1,408, 1,184, with fill 424,841 to 664,244. Query at Dec 1909: "33% completo, 66,340 de 196,602 ton.", lots clean. A fire stopped the clock after 6 minutes. | `owner_shots/03_fixed_1_query.png`, `MAIN\verify\lfstall\after_fix_sc3landfill.log` |
| bookkeeping | LFSTALL fix | **EXACT** at every `BOOK>` line (once a minute, on the sim thread, after reconcile): 2 in Moscow (694,928 / 607,443) and 8 in Farmsville (1,573,222 down to 1,301,776). Valve room = sum of active cell room, valve waiting = sum of pendings (1,352 / 1,036 / 1,812 / 1,392 / 1,348 / 1,404 / 1,408 / 1,184). | same log |
| stuck save, fresh game | LFSTALL fix | **FLOWS.** `Farmsville stuck (auto 5 min).sc3` (autosaved in run A, 14 s before the stall) as the first city of a new process: `BOOK>` equal from the first update (valve room 1,313,700, waiting 1,048), then pending 1,068 / 1,088 / 768, fill rising, 547 deposits in 3 minutes. Nothing stuck is in the save: pending is not saved, and the valve is clean (above). | `MAIN\verify\lfstall\stucksave_and_heal_sc3landfill.log` |
| heal, router side | fix without the router reconcile, `SC3LANDFILL_TEST_FIRSTDEV=1` (old bug forced) | **RECOVERS.** Pending reached room after about 4 minutes, refusals counted (blocked 28,121, 77,921), then `HEAL> landfill #1 (60 cells, room 1575083): pending 1575083 was not going down (no UpdateCell of it ran, blocked 100001): released 0` and the router took garbage again (pending 927,285, 1,337,905). "released 0": the valve held nothing, the whole pending was phantom. | same log |
| router reconcile | final build, `SC3LANDFILL_TEST_FIRSTDEV=1` | **NEVER BLOCKS.** Madison first, then Farmsville with the old bug forced (the wrapper never sees Farmsville's developer, its UpdateCells run stock). Pending one minute apart over 8 minutes: 1,644, 1,400, 776, 960, 1,152, 1,460, 1,028, 704. No refusals, no heal needed (heals 0, blocked 0). The router drops the phantom pending as the stock deposits drain the valve. | `MAIN\verify\lfstall\forced_bug_final_sc3landfill.log` |
| UpdateCell-side heal | | Not triggered in any run (no case found where UpdateCells run with pending and room and put nothing down). Static only. | |

## The unselectable tile

Stock. Every landfill heap piece the developer places is set not user-removable: occupant vt+0x78 `SetUserRemove(0)`
right after the zone layer places it, in the deposit loop (SIMRCI `0x10019de1`, the `0x2716` start piece), in
createNewHeap (`0x1001a447`) and in insertLandfillTile (`0x1001a186`). The circled piece in the player's picture is a
heap piece at the heap's edge (the `0x2716` start piece looks like a small shed). Not ours, left as is.

## Harness note

sc3autosave writes beside the loaded city. A Load City from the in-game dialog lists `MAIN\Cities`, so the first
before-arm run wrote `Farmsville (auto 5 min).sc3` into `MAIN\Cities`. It was moved to
`dev\lfstall\tree\Cities\Farmsville stuck (auto 5 min).sc3` (MAIN\Cities has nothing new now). The later runs left
sc3autosave out (`SC3MODS_LIST`).

## Needs owner check

- Nothing visual changed. A hand check on the owner's side would be: play a city with a landfill, Load City another one
  with a landfill (or New City and zone one), run a few game years, the landfill keeps taking garbage.
- The self-heal releases garbage that cannot be put down (it disappears, as if exported for free). Only reached when
  something outside this fix goes wrong, logged as `HEAL>`. Switch: `heal=0` in landfill.ini.

## Files

- `re/harness/src/sc3landfill.c` (LFSTALL block: city_check, heal, router reconcile, developer adoption, diagnostics)
- `re/analysis/LANDFILL.md` (section 5)
- `verify/lfstall/RESULTS.md`
