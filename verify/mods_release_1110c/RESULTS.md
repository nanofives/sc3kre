# RESULTS - sc3mods release 2026-11-10c + LAN 2026-11-10c

Replaces `sc3mods-2026-11-10b` (GitHub) and LAN `2026-11-10b`. Owner call 2026-11-10: "yes" to merging child/growable
and fixing the Civic Deals SYS.PAK problem for a 2026-11-10c release. Source: main `6bcf051`.

| what | commit | record |
|---|---|---|
| community_patch.ps1 writes the Civic Deals petitions into `mods\netmod\overlay\Apps\Sys\SYS.PAK` too; -Restore takes them out of it | 53bd2c1 | this file |
| merge child/growable: netpack `growables` (additive custom zoned buildings), example package growable_test (not installed in the release) | 42b6c90 / 6bcf051 | verify/growable/RESULTS.md |

## The Civic Deals problem (found by the growable child)

sc3netmod answers the game's reads of `Apps\Sys\SYS.PAK` from the road packages' own copy: in the 10b smoke log
`overlay: CreateFileA "...\Apps\Sys\SYS.PAK" -> "...\mods\netmod\overlay\Apps\Sys\SYS.PAK"`. community_patch.ps1 wrote
the petitions (PetitionerExtraInfo.ini 0xD9 / 0xDA / 0xDB, PetitionerManager.ini NumberOfPetitionerMessages 210 -> 212)
only into `Apps\Sys\SYS.PAK`, so with the road mod installed the game read a SYS.PAK without them. Released that way
since the community mods shipped (sc3mods-2026-11-06). LAN 2026-11-10b: Apps copy `bb4e3126...` had the lines, overlay
copy `73a49107...` (= stage/src) did not.

Fix: the SYS.PAK edit is a function applied to both copies. The overlay copy is edited in place without a backup (a new
release replaces it, so an old backup could put back a stale road SYS.PAK); -Restore removes the inserted lines and puts
212 back to 210. Test on a scratch copy of stage/src's Apps\Sys, Apps\Res\Text, the overlay SYS.PAK and the community
folder: install (3 + 3 changes), rerun ("already done" for both), both copies then hold `0x000000D9=19,2`,
`0x000000DA=19,2`, `0x000000DB=19,2` and `NumberOfPetitionerMessages=212`; -Restore (overlay 4 changes undone, 50
files) = every file byte-identical to before.

## Stage and checks

- DLLs: `stage/bins_1110b` unchanged (no mod source change since 10b: `git diff 5152803 HEAD -- re/harness/src` empty).
- `stage_lan_release.py --game stage/src --bins stage/bins_1110b --stock-modules original/modules --menu-bg
  stage/release/Apps/menu_bg.bmp --perf-ini stage/release/Apps/perf.ini --out stage/release_1110c --label 2026-11-10c
  --community stage/community_1106`: 3,645 files. Community step: `SYS.PAK: 3 change(s)`, `mods\netmod SYS.PAK: 3
  change(s)`. Against LAN 2026-11-10b: 2 changed (`community/community_patch.ps1`, the overlay SYS.PAK, now
  `4c032224...` with the petition lines), 0 added, 0 removed. stage/src's overlay SYS.PAK still `73a49107...`.
- Launch check (patched, SC3U.exe direct, windowed, Berlin, no input, ~2 min): `11 mod(s) loaded`, CRASHGUARD and
  VALVESHUT lines, the game opened the overlay SYS.PAK, only the benign `0xC0000096 @ SC3U+0x84122`. Then `-Restore`,
  logs + dataview.ini + landfill.ini deleted, manifest: 0 changed, 0 missing, 0 extra.
- Not checked in game: the Civic Deals offers actually appearing in Reunirse (needs the meeting screen: owner check).

LAN: `deploy_lan_release.sh stage/release_1110c` sent 2 of 3,645 files (0.3 MB). Served label `2026-11-10c`, served
overlay SYS.PAK = staged. `stage/release` -> `stage/release_1110b_old`, `stage/release_1110c` -> `stage/release`.

Zip: the 10b zip with `community/community_patch.ps1` replaced and README.txt updated (header 2026-11-10c, NEW IN
2026-11-10c, install step 4 says to run community_patch.ps1 again after a new sc3mods release). Only those 2 entries
differ from 10b. Its `mods\` is still the unpatched one: 121 files, all byte-identical to stage/src (players run
community_patch.ps1 themselves; the LAN tree has the community mods pre-installed, so its overlay SYS.PAK differs from
the zip's by design). 159 entries. `sc3mods_2026-11-10c.zip` 51,926,579 bytes, SHA-256
EB8CB4707536B4BBE91D700A000F89B18FA426EAA3F3FD0DFA11F0F57091F3CB.
