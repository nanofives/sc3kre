# RESULTS - sc3mods release 2026-11-03c + LAN republish

Replaces `sc3mods-2026-11-03b`. Owner call 2026-11-03: publish the ghost-tiles fix (verify/ghosttiles/RESULTS.md, GHOSTFIX:
highlighter pushes keep the tools' wipe rect +0x50; stationwarn's blink had shrunk it). Source: main `9309a63`.

- `stage/bins_1103c` = `stage/bins_1103b` with `sc3resize.dll` rebuilt from 9309a63 (dev/rel1103c). Only
  sc3resize_stationwarn.c and sc3resize_placehints.c changed since a895a3f.
- Staged into `stage/release_1103c` (label `2026-11-03c`, 3,622 files). Against 11-03b: changed Apps/sc3resize.dll only.
- Launch check (patched, windowed, Berlin, no input, 100 s): `11 mod(s) loaded`, STATIONWARN scan 86 / 2 not connected,
  `GHOSTFIX> on`; only the benign `0xC0000096 @ SC3U+0x84122`. Then `-Restore`, logs and first-start ini files deleted,
  manifest re-hashed: 0 changed, 0 missing, 0 extra.
- Zip: the 11-03b zip with Apps/sc3resize.dll replaced, README.txt updated (header, NEW IN 2026-11-03c). 142 entries, 141 checked,
  0 mismatches. `sc3mods_2026-11-03c.zip` 50,713,048 bytes, SHA-256 6FC437D892949D0BA4CA3286F01BF361A21C4A7EDCE392552D696525A95CDC8B.

GitHub: `sc3mods-2026-11-03c`, target `0b8f2d2`, https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-11-03c, asset
downloaded back, SHA-256 matches. The 11-03b notes start with a "superseded" line.
LAN: deployed from `stage/release_1103c`, served label `2026-11-03c`, served sc3resize.dll matches the stage. Then
`stage/release` -> `stage/release_1103b_old`, `stage/release_1103c` -> `stage/release`.
