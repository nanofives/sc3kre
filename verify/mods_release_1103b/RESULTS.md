# RESULTS - sc3mods release 2026-11-03b + LAN republish

Replaces `sc3mods-2026-11-03`. Owner call 2026-11-03: publish round 11-03 (re/sessions/ROUND_2026-11-03_owner_feedback.md).
Source: main `6e99ead`.

| what | record |
|---|---|
| stationwarn: stations the router cannot use blink red, "?" reason row, count on Cuadros Transporte | verify/stationwarn/RESULTS.md, re/analysis/STATION_RULE.md |
| placehints4 + tripmonth: halo only with Shift, station placement reach / trips / red, dead-end track, exact per-class reach, 2-3 line Shift label, trip months close from load | verify/placehints4, verify/tripmonth |
| uipolish + arrowsv: music volume 0 while inactive, Vida Útil footer band, arrows centred | verify/uipolish, verify/arrowsv |

## Stage and checks

- `stage/bins_1103b` = `stage/bins_1103` with `sc3resize.dll` rebuilt from 6e99ead (dev/chk1103b). Only sc3resize sources and the
  language tables changed since cc6a1e3; the other DLLs are byte-identical to 11-03.
- Staged into `stage/release_1103b` (label `2026-11-03b`, 3,622 files, 707.1 MB). Against 11-03: changed Apps/sc3resize.dll and
  the 7 Apps/sc3lang tables (306 keys), 0 added, 0 removed.
- Launch check (patched, windowed, Berlin, no input, 100 s): `11 mod(s) loaded`, LANG es 306 keys, RESTOREFIX, STATIONWARN
  (scan 86 stations, 2 not connected), PLACEHINTS on; only the benign `0xC0000096 @ SC3U+0x84122`. MUSICFOCUS logged nothing
  (it logs on a focus change, none happened). Then `-Restore`, logs and first-start ini files deleted, manifest re-hashed:
  0 changed, 0 missing, 0 extra.
- Owner checks: physical Shift key, music actually quiet in the background (audio not capturable).

Zip: the 11-03 zip with Apps/sc3resize.dll and Apps/sc3lang/*.txt replaced, README.txt updated (header, NEW IN 2026-11-03b).
142 entries, 141 checked against the staged manifest, 0 mismatches. `sc3mods_2026-11-03b.zip` 50,712,727 bytes, SHA-256
B526D5D1D9F79023DE8FD37C265784523DA46257129EA632CED50067ABE44871.
