# RESULTS - sc3mods release 2026-11-03 + LAN republish

Replaces `sc3mods-2026-11-02d`. Owner call 2026-11-03: merge placehints3 and publish. Source: main `cc6a1e3`.

| what | record |
|---|---|
| placehints2: hint text only while Shift is held, land value halo in green (new palette row + building tint hook) | verify/placehints2/RESULTS.md |
| placehints3: Shift + release places while a hint tool is active, other tools keep the stock cancel | verify/placehints3/RESULTS.md |

## Stage and checks

- `stage/bins_1103` = `stage/bins_1102d` with `sc3resize.dll` rebuilt from cc6a1e3 (dev/rel1103). Only sc3resize sources and
  the language tables changed since 3339ade, so the other DLLs are byte-identical to 11-02d.
- Staged into `stage/release_1103` (label `2026-11-03`, 3,622 files). Against 11-02d: changed Apps/sc3resize.dll and the 7
  Apps/sc3lang tables (278 keys), 0 added, 0 removed.
- Launch check (patched, windowed, Berlin, no input, 100 s): `11 mod(s) loaded`, LANG es 278 keys, PLACEHINTS on "in green,
  hint text while Shift is held"; only the benign `0xC0000096 @ SC3U+0x84122`. Then `-Restore`, logs and first-start ini
  files deleted, manifest re-hashed: 0 changed, 0 missing, 0 extra.
- Not checked here: the physical Shift key (cannot be posted), which stays an owner check.

Zip: the 11-02d zip with Apps/sc3resize.dll and Apps/sc3lang/*.txt replaced, README.txt updated (header, NEW IN 2026-11-03).
142 entries, 141 checked against the staged manifest, 0 mismatches. `sc3mods_2026-11-03.zip` 50,695,195 bytes, SHA-256
780828BC4B3DD93237A27FEEF6AC44F661EF0D2843277CD7B26E28F262DB0AC3.

GitHub: `sc3mods-2026-11-03`, target `f3653ff`, https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-11-03, asset
downloaded back, SHA-256 matches. The 11-02d notes start with a "superseded" line.

LAN: deployed from `stage/release_1103`, served label `2026-11-03`, served sc3resize.dll and sc3lang/es.txt match the stage.
Then `stage/release` -> `stage/release_1102d_old`, `stage/release_1103` -> `stage/release`.
