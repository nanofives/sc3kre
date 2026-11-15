# Round 2026-11-15: GitHub issue #3, Sandbox mode and gentler abandonment

Orchestrator: "SC3 Simtropolis feedback triage (Wine patch, land value 255, avenues, UI rescale)".
Rules: `re/sessions/CHILD_PROTOCOL.md`. Workspace `dev\abandon` made from main `c65b8f5`.

## The request

GitHub issue nanofives/sc3kre #3 (nyh-workshop, 2026-11-14), "Additional enhancement: Leisure/Sandbox play and
tweak building abandon when demand is low":
1. A "Sandbox" mode where buildings are not abandoned.
2. Softer abandonment: slightly low demand should not abandon buildings quickly (the reporter saw one abandoned
   building in a high-land-value estate); abandonment as usual only on really poor conditions.

## Owner decisions (Mariano, 2026-11-15)

- **Sandbox stops everything**: standing buildings never abandon for any reason in the zone evaluators (radiation,
  no power / transport / water, negative demand, low land value). The disaster path (SIMDSTR) is NOT in scope.
- **Gentler abandonment**: low demand empties buildings only when net demand is below a set SHARE of its range
  (for example the bottom quarter), the share in `simrun.ini`. Above it, the negative-demand roll does not fire.
- **The broken downgrade is NOT fixed now** (pick_lower_value always returns 0, so step (d) removes instead of
  downgrading). Note it, do not change it.
- Both are off by default unless stated otherwise below; switches on the "Turn mods on/off" page + `simrun.ini`
  (a per-city setting would need save support: not now). Sandbox default OFF. Gentler abandonment: propose the
  default with numbers from the in-game check, owner decides.

## Survey (SimGolf orchestrator via the worker, 2026-11-15, NOT verified in game: check every item)

Sources: `re/analysis/ZONE_REDEVELOPMENT.md`, `LAND_VALUE.md`, `BUILDING_PICK.md`, `SIMDSTR.md`,
`re/ghidra_export_simrci/functions/10028f12_sc3_resdev_evaluate_tile.c` lines 185-262, `re/harness/src/sc3simrun.c`
612-668 (CHURN), `re/harness/src/sc3resize.c` 9165 (mods page rows).

- Every branch that takes a standing residential building down posts one call with flag 2:
  `sc3_resdev_post_state_change` (SIMRCI `0x10029a38`, C2). The notes call flag 2 both "abandon" and "demolish";
  abandoned occupant types are 15100 in Occupant.ini. **Prove flag 2 live first** (Frida or TTD on 0x10029a38).
- Commercial `0x1000fd53` and industrial `0x10017fc0` evaluators are only called "the same shape": read them
  branch by branch.
- Order for a standing building in `sc3_resdev_evaluate_tile` (`0x10028f12`, C2):
  (a) radioactive: flag 2, no roll;
  (b) unpowered, beyond MaxDistFromTransport, an unidentified read `+0x88 vt+0x68 == 1`, or no plumbing byte at
      density above 1: `rand(100) < NoServicePercentage / x` (SC3Tune.ini R 15, C 35, I 30);
  (c) demand < 0: `rand(-range) < -(netDemand / x)`, one pass per building about every 30 game days
      (`sc3_zone_tick_develop_tiles` `0x1003372a` checks W*H/30 tiles a day); x = the building's `vt+0x40`, meaning
      not in the repo;
  (d) land value below half the class floor: flag 2, no roll (pick_lower_value `0x100297fb` / `0x10018e45` returns 0).
- Not found as abandonment inputs: crime, garbage. Pollution is read but not mapped (maybe the `+0x88` read).
- Separate disaster abandonment: SIMDSTR `DAT_10039b88` / `b8c` (Destruction / AbandonLikelihood). Out of scope.
- Risks: with Sandbox on, oversupply never shrinks; population / jobs accounting with buildings that never empty is
  not documented (check it in game: a Sandbox city with negative demand for a few years).
