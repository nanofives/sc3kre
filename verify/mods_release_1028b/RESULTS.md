# RESULTS - sc3mods release 2026-10-28b + LAN republish

Replaces `sc3mods-2026-10-28`. Owner call 2026-10-28: "Release to the LAN and GitHub" after the 10-28 feedback round
(`re/sessions/ROUND_2026-10-28_modspage_autosave.md`). Source as of `a12fbe4`. Changes since 10-28 (`9f842f7`):

| what | commits | shipped files |
|---|---|---|
| modsui: mods page buttons bottom-left on the OK row, camera sliders on one blue panel, navy labels | a12c45e | sc3resize.dll |
| autosave3: three files (auto 5 min / 10 min / 1 h), one queued save at a time, interval restarts after a load | d6f413c | sc3autosave.dll |

`git diff 9f842f7 a12fbe4 -- re/harness/src`: sc3autosave.c, sc3resize.c only. Every other DLL and data file is the
10-28 one (`stage/bins_1028b` = `stage/bins_1028` + the two rebuilt DLLs, zip built from the 10-28 zip as downloaded
back from GitHub with the two DLLs and README replaced; every zip file `cmp`-equal to `stage/release`).

Not fixed: the owner's crash loading an autosave from the main menu (MARIANO-PC, Big One, 1024) did not reproduce in 11
loads with the owner's own files (`verify/autosave3/RESULTS.md`). Not fixed: the blue box the game draws behind its text
buttons (`verify/modsui/RESULTS.md`).

## Stage and checks

- `stage_lan_release.py --game stage/src --bins stage/bins_1028b --stock-modules original/modules --menu-bg <10-28 zip>
  --perf-ini <10-28 zip> --out stage/release --label 2026-10-28b`: 3,606 files, 697.3 MB.
- Launch check (stage/release patched, windowed, no input): Big One, `8 mod(s) loaded`, sc3autosave
  `CITY> lock 0, interval starts` and the progress service wrapped, only the benign `0xC0000096 @ SC3U+0x84122`.
  Then `-Restore`, logs deleted, 3,606 manifest files re-hashed: 0 changed, 0 missing, 0 extra.

LAN: `deploy_lan_release.sh` sent 2 of 3,606 files (0.6 MB). Served label `2026-10-28b`, served sc3resize and
sc3autosave SHA-256 match the stage.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/sc3resize.dll | 445952 | CB013A6157DE2F7974AC2465A2CF49B06D6AC07E110D90E5A8AF9E13552BB853 |
| Apps/sc3autosave.dll | 130560 | 8C9CAC951F900B98B32AC602F44B9DCF58CE41B32346D0541A6B2A4F1F5A2C3A |
| README.txt | | 2026-10-28b section, autosave file names, keep= removed from the options |
| every other file | | as `verify/mods_release_1028/RESULTS.md` |
| `sc3mods_2026-10-28b.zip` | 43,614,187 | 74BC4F5DC9ECA41E7AF273C342A0B60024C5FCE9360BB879FE963966188EA0EF |
