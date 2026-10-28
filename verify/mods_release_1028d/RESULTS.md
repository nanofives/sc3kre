# RESULTS - sc3mods release 2026-10-28d + LAN republish

Replaces `sc3mods-2026-10-28c`. Owner round 2026-10-28 (second feedback batch). Source as of `745e2ca`. Changes since
10-28c (`451dc44`), sc3resize.c only:

| what | commits | record |
|---|---|---|
| modsui2: mods page buttons on the tick's row and height at the panels' left edge, one click switches back (MPHOVER) | c94ffb6 | verify/modsui2/RESULTS.md |
| relocate: "Mover" in the query dialog of rewards, business deals and landmarks, cost = 50% of the price + bulldoze + levelling (owner call), PLOPOVER: building tools demolish zoned buildings under the footprint | 745e2ca | verify/relocate/RESULTS.md, re/analysis/RELOCATE.md |

Also on main, no shipped file: re/analysis/PUBLIC_TRANSIT.md (owner question on public transport, 9799f4b).

## Stage and checks

- `stage/bins_1028d` = `stage/bins_1028c` + sc3resize built from main (merged modsui2 + relocate, not run together by either
  child). Label `2026-10-28d`, 3,606 files, 697.3 MB.
- Launch check (stage/release patched, windowed, no input): Berlin, `8 mod(s) loaded`, `INITSLACK` and `RELOCATE> on`
  logged, only the benign `0xC0000096 @ SC3U+0x84122`. Then `-Restore`, logs deleted, 3,606 manifest files re-hashed:
  0 changed, 0 missing, 0 extra.

LAN: 1 of 3,606 files sent (0.5 MB). Served label `2026-10-28d`, served sc3resize SHA-256 matches the stage.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/sc3resize.dll | 456192 | 4877278DD29A46B62328E33C97D8E7CB5BD58AF4078BD4B2C56D716768846E61 |
| README.txt | | 2026-10-28d section |
| every other file | | as `verify/mods_release_1028c/RESULTS.md` |
| `sc3mods_2026-10-28d.zip` | 43,621,156 | CAB8A77B4E65FB745FD450CF1A70E44AA249CF44CCC94BA3A3134706E881A3DA |

Owner checks pending: Big One.autosave2 maximized (10-28c fix), one real-mouse click on Volver, a Mover by hand.
Not tested by relocate: levelling on a slope, right-click cancel, menus after a move, sc3undo of a move.

GitHub: `sc3mods-2026-10-28d`, target `6604a3a`, https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-10-28d, asset
downloaded back, SHA-256 matches. The 10-28c notes now start with a "superseded" line.
