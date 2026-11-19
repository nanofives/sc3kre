# STATUS civrew (round 2026-11-19i)

## goal
Research how civic menu entries and rewards map to buildings, what a new civic building and a new reward need, and
propose the smallest mod change. Research only.

## verdict + deciding RVA
- Civic: a variant needs no menu entry. All 17 plain civic commands meet at SIMGEOM `0x1000b1a3` (plain tool, key at
  `[ebp-0x34]` instance), the sim keys on the type id (SIMSERV `0x1000f006`). Proposal: 5-byte detour at `0x1000b19d`.
- Rewards: a new row never unlocks. Direct-unlock chain SIMADV `0x1000a7fa`, petition answers `0x1000abb2`. Proposal:
  6-byte detour at `0x1000a7fa` + our row loaded with the stock parser (`0x100089bf`).

## built
Nothing (research only).

## proven game-side vs static only
All static (decomp, PE disassembly, ini and IXF data checks). No game run.

## blocked on
Nothing.

## files owned
- `re/analysis/CIVIC_REWARD.md` (new)
- `verify/civrew/RESULTS.md` (new)
- `re/sessions/STATUS_civrew.md` (new)

## game-harness need
None this round. Building the proposal needs one launch per part.

## asks of other sessions
- Owner call: cycling looks on the stock button (smallest) or a list dialog (second step).
- Whoever owns sc3resize RELOCATE / PICKER: `rl_movable` leaves out type 18000 (bldimport landmarks).
