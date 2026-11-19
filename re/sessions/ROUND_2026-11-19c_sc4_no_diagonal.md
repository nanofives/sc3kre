# Round 2026-11-19c: SC4 conversion skips diagonal (45 degree) houses

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspace from main 6fd345f+.
Previous: ROUND_2026-11-18h (sc4conv), ROUND_2026-11-19 (sc4web: the importer page converts SC4, byte-identical).

## Owner (2026-11-19)

"avoid diagonal houses". The JMyers readme: "Some homes are set at a 45 degree angle and are placed on corner lots."
SC3 has no diagonal buildings, so converted 45-degree houses look wrong among stock ones.

## Stream sc4diag (opus / medium)

1. Find how to tell a 45-degree house from the SC4 data, with evidence on the JMyers pack: lot data (corner lots,
   the building's placement / rotation in the lot exemplar), the S3D box (footprint shape and size against the
   lot), or the view pictures (alpha coverage of the box). Prefer data fields over picture heuristics. List every
   JMyers design / colour as diagonal or not, and check the list against the S3D views by eye (one sheet).
2. sc4conv.py and sc4web.js: diagonal buildings are written with enabled false and a note ("diagonal, off by
   default"), and a design whose enabled colour was diagonal gets a non-diagonal colour enabled instead if one
   exists. The page shows the reason on the card. Byte identity Python vs page kept (extend sc4_golden). run_all.sh
   must pass all steps.
3. Re-run the page install in Sacramento: no diagonal house grows (count from the save), picture local only.
Do not edit classifier.html (child sc3ui3 adds a hook there now): put the UI note in sc4web.js.
Results MAIN\verify\sc4diag\RESULTS.md, STATUS MAIN\re\sessions\STATUS_sc4diag.md.

## Rules

Windowed game, posted input only, test slot, kill only PIDs you started, no git add / commit. Nothing from SC4 packs
into the repo or docs/.
