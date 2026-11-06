# RESULTS - sc3mods release 2026-11-06 + LAN republish

Replaces `sc3mods-2026-11-04b`. Owner call 2026-11-06: ship the community-mods work (re/analysis/COMMUNITY_MODS.md).
Source: main `434a0da`.

- `stage/bins_1106` = `stage/bins_1104` with `sc3resize.dll` rebuilt from main (dev/rel1106; only sc3resize*.c and the 7
  language tables changed since 4d52b33) and `sc3natworld.bin` (natworld_pack.py from the Natural World v1.0 package).
- `stage/community_1106` from `re/tools/community_bundle.py`: the authors' SC3KCivicDeals.dll / SC3KExtraCheats.dll unchanged,
  our MSVC build of re/community/apache, the author's sprites and notices (Apache LICENSE / README / RELINK-LGPL, Civic Deals
  licence and notices), `install_data.json` (SYS.PAK inserts, 18 IXF records en / es, 30 Spanish DLL strings).
- `re/scripts/community_patch.ps1` (PowerShell 5.1, players have no Python) applies install_data.json. Check in dev/rel1106:
  46 files byte-identical to what civicdeals_patch.py + apache_patch.py (game-tested) produce; second run = no change;
  -Restore = 43 data files back to the stage hashes, 0 leftovers, 0 backups. In game (Craterville): 11 mods + the 3 community
  DLLs loaded, NATWORLD / TERRPANEL / CHEATFIX / FORESTTOOL on, Apache petition hooks in, corruptncrazy -> D9 in Reunirse and
  accepted ("Acuerdo privado aprobado", Spanish) with the Apache hooks present, SimDate 3 3 1950 -> date 1950.
- `stage_lan_release.py ... --bins stage/bins_1106 --out stage/release_1106 --label 2026-11-06 --community stage/community_1106`
  (new option: installs the community mods into the staged tree, drops the backups): 3,643 files, 711.6 MB. Against 11-04:
  52 changed (sc3resize.dll, sc3lang 7, SYS.PAK, 42 petition IXFs, sc3mods_patch.ps1), 21 added (3 community DLLs, Apache
  sprites, sc3natworld.bin, community/), 0 removed. stage/src untouched (SYS.PAK hash unchanged).
- Launch check (release_1106 patched, windowed, Berlin, no input, 90 s): `11 mod(s) loaded`, NATWORLD 8 palettes, TERRPANEL,
  CHEATFIX, FORESTTOOL item added, Apache INIT + PETITION_HOOKS_IN; only the benign `0xC0000096 @ SC3U+0x84122`. Then
  -Restore, 13 logs + dataview.ini + landfill.ini deleted, manifest re-hashed: 0 changed, 0 missing, 0 extra.

Zip: the 11-04b zip with Apps/sc3resize.dll, Apps/sc3lang/*.txt and README.txt replaced, Apps/sc3natworld.bin and community/
(15 files) added. 157 entries, 156 checked against the staged manifest, 0 mismatches. `sc3mods_2026-11-06.zip` 51,420,724
bytes, SHA-256 741EE6781AC313343661E98F7A7D1F4C65C0986087AC7D810FFFF2892D03D8A1.

GitHub: `sc3mods-2026-11-06`, target 434a0da, https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-11-06, asset
downloaded back, SHA-256 matches. The 11-04b notes start with a "superseded" line. Repo README mods section updated.
LAN: deployed from stage/release_1106 (73 files, 7.0 MB incremental), served label 2026-11-06, served sc3resize.dll, SYS.PAK,
SC3KUApacheFlyover.dll, community_patch.ps1, sc3natworld.bin match the stage. Then `stage/release` -> `stage/release_1104_old`,
`stage/release_1106` -> `stage/release`.

Not checked: the community installer on English-UK / other-language games in game (records written en, compared with the
Python output only), a real Steam install, the Apache petition without forcing (needs crime > 40).
