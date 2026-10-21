# STATUS avrbtfix (2026-10-21)

## goal
Owner img4/img5 (verify/ownerbugs_1021/owner_shots): two parallel avenues, then one more road, and the right avenue became
a column of overlapping "roundabout" pieces. Expected: adding a road never turns an avenue into roundabouts.

## cause (milestone 1, messaged)
- The owner's avenues are DIAGONAL (screen-vertical = world diagonal), DAV converted them. The added road made rows of
  4 cells = a diagonal boulevard band (DBV). DBV REFUSED the band, so the cells kept the stock tiler's ladder
  11203 / 43 / 43 / 11203. Vanilla SC3 (no sc3netmod) draws exactly that "column of circles" (yellow lines; our
  avenue_markings reskin of 11203 makes them white). No block wrote roundabout pieces (no rbt write in the pass).
- DBV refusal: dbv_end_kind knew no end where one drag sticks out by one row past the band (any hand-drawn stagger),
  log "top end: the roads past the band are not an end this package knows"; and a plain cap required SIX empty rows
  past the end, so an unrelated road within 6 rows (img4 has the curved road just below) also refused the band.
- Aligned third road (same start/end rows): DBV converts (both sides checked in game).
- img4 end that "did not convert" (report only): DAV end rows where the two drags' last cells stagger stay stock
  look by design (DAV split rule); not changed.

## design (fix, sc3netmod_dbv.c + offline twin diagbv.py)
1. caps need their stamp rows + one empty row (was six; orchestrator's call); a road that touches still refuses ("touches road").
2. an end shape DBV does not know = RAGGED: the band converts, that end's rows stay with the stock tiler (end row is
   treated like an end row, rows 1..2 past it are path). Still refused: narrowing whose avenue will not convert,
   road beside the end row, fewer than 3 clean rows, junction / stamp conflicts.
Orchestrator 2026-10-21 (2nd message): cap = stamp rows + 1 clear row (DONE, C + twin, check 0 off), and painted
1-row stub caps. IDS GRANTED: 21920..21934 (21935..21949 reserved for avx32). Plan: shapes 12, 123, 23, 01, 012/0 =
14 new pieces 21920..21933 (21934 spare), cell-signature dedupe vs the shipped pieces; the generic closure (dbvstub.py
StubCap) reproduces cap-square / cap-part / cap-x4z3 with 0 new pieces. +-1-row staggered drags: 65% of ends were
ragged (20 shapes); these 5 cover 27.9% of all ends, the rest stay RAGGED (stock end). Owner-like in-game ends were
12 and 123. PLAN SENT, waiting for approval before painting: MAIN verify/avrbtfix/owner_shots/avrbtfix_stub_plan.png,
avrbtfix_stub_mockup.png.

## built (files, uncommitted)
worktree Simcity_wt_avrbtfix (branch child/avrbtfix), to commit by path:
- re/harness/src/sc3netmod_dbv.c
- re/tools/netmod/diagbv.py
- re/tools/netmod/dbvstub.py (new, OPTIONAL: stub-cap plan tool only; nothing loads it; leave out unless the owner
  asks for painted stub caps)
- verify/avrbtfix/RESULTS.md
MAIN (not in git or gitignored as usual): verify/avrbtfix/owner_shots/*.png (frame dumps), this STATUS file

## proven in game vs offline only
in game: reproduction (mod + vanilla); fix: owner-like staggered third road on both avenues -> diagonal boulevards
with one ragged end each; unrelated road 3 rows below a cap kept; axis 1 staggered converts; save + reload 132 tiles
restored, bands intact; rotation 1 shot. Orchestrator's two extra checks (DLL rebuilt with the 1-empty-row cap rule):
other drag order (third road first) = same result as forward (47 / 48 cells, one ragged end each); no-mod load of
that save = stock ids only (35 / 43 / 11203 / 11225 / 39), same look as a pre-fix DBV save without the mod. offline:
diagbv.py check 0 off. CHECKED (messaged). Owner calls (orchestrator relays, no work unless asked): ragged-end look;
two diagonals two cells apart now convert. Stub caps: plan only (ids 21920..21934 granted, not used).

## blocked on
nothing

## files owned
re/sessions/STATUS_avrbtfix.md (MAIN), re/harness/src/sc3netmod_dbv.c, re/tools/netmod/diagbv.py (worktree),
verify/avrbtfix/ (MAIN owner_shots + worktree RESULTS.md)

## instance
Simcity_stock_avrbtfix\re\harness\inst_avrbtfix (lab4.sc3 = fixed case saved; repro_ladder.sc3 = first repro save);
inst_avrbtfix_van = vanilla check (sc3resize only). No game running (PIDs 52864, 32732, 59400, 59748, 70028, 32272, 3068, 23720 all stopped).

## needs owner
look call: a ragged end shows a small stock road end beside the boulevard curb (MAIN verify/avrbtfix/owner_shots/
fix_2_ends_zoom.png). Painted caps for those shapes = new pieces (not built).

## asks of other streams
none
