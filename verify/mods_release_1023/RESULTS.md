# RESULTS - sc3mods release 2026-10-23

Replaces `sc3mods-2026-10-12`. Built from the hand-tested release candidate `Proyectos\Simcity_rc` (branch `rc/1023`,
merged into `main` 734ad5f, re-staged from `main`, `verify/rc_1023/RESULTS.md`). Release target `60f22ea` (main after
the pre-publish scrub). No binary source changed between the re-stage (`c145e88`) and the target.

**Owner decision 2026-10-23:** ship the netmod road data (`mods\netmod\overlay` + `tables`, 109 files, 61 MB of
modified game `.DAT` / `.IXF` / `.PAK`). It is built from the game's own files, so it is a second exception to the
tools-and-notes-only publish policy (after `menu_bg.bmp`), risk accepted by the owner.

## Contents

122 zip entries: `README.txt` + 121 files from `Simcity_rc`, every one matching the RC `manifest.json` SHA-256
(0 mismatches). Not shipped: `sc3resize.ini` and the other per-PC ini/log files, Cities, game files.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/mods_launch.exe | 147,968 | 45E9C3218083B69D17D67748E882160AC063AEDA30359DDB40A6A0B1B1D9BEC1 |
| Apps/version.dll | 117,248 | DE51B269B21C936A3B2238B77DA497D870F3A8B2B280444A631247F12FAE3F53 |
| Apps/sc3resize.dll | 355,840 | 302ADAB7C5B33860467089D066C27179603D6446CBB4FB16658B7096215EF197 |
| Apps/sc3bigcity.dll | 139,264 | 980DDA5499AB2729B7CC313F3DF7042B662D52AD091500A4D5551D400175F10B |
| Apps/sc3overscroll.dll | 127,488 | F098E2D44C12A247449FC03B0915FB88BA42892BDE41476E7C8E52426858FEFE |
| Apps/sc3simrun.dll | 121,856 | 889CBDFDEB685E37DC19095740ACAAA356D482BCDEC004208B148494AD646814 |
| Apps/sc3perf.dll | 183,808 | FE4585022DE0E3C3B2424094CCF8FC635BCC899915AAAAC18326720EF24989DC |
| Apps/sc3netmod.dll | 380,416 | ED5DF1F8556325D7253A816C98982CA7AF762D3AE5CB51B9A53BC9AAAD92D111 |
| Apps/sc3undo.dll | 147,968 | B0BE523718ABBAA3F8B9CE60612A54EDA686392D6DE3470391055C8174E82E46 |
| Apps/perf.ini | 2,103 | A4C2D0A33FFDB98605ABAF75E4BB8EA9D5A9444F0C8FDAF93AF7707443B7BC04 |
| Apps/menu_bg.bmp | 4,717,638 | 10792812B2BAED12A62D9207FE47FB0E3FD827E3B5B642F3C2C8A253856945AE |
| Jugar SimCity (mods).bat | 64 | 70F3E4370A98BB02547F7B3C54A02B940D857ACB76A5E657E6B9D7F54D714C22 |
| `mods/netmod/**` | 109 files | each matches the RC manifest |
| `README.txt` | 5641 | \0C848FFF85C09C932E69473EF89760A18BB935B825AF585C8B2E3CE75AB0416 |
| `sc3mods_2026-10-23.zip` | 41977876 | \E42182ED956C931762D993EC6299C9D34BCA08CF88FA43BDC9573C9861A8C39 |

## Testing

No separate package install test. The 121 files are byte-identical to `Simcity_rc`, which had the session smoke test
and launch checks (`verify/rc_1023`) and the owner's hand test of the intro logo margins on 2026-10-23 (maximized: logo
black margins, menu picture margins). The zip was tested with `zipfile.testzip` and every entry re-hashed.

## Published

GitHub release `sc3mods-2026-10-23` on nanofives/sc3kre, target `60f22ea393ba31175f1d3573a3d39301be4de6eb`:
https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-10-23
Asset downloaded back with `gh release download`: SHA-256 matches. The 2026-10-12 notes now start with a "superseded"
line pointing here.
