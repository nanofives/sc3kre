# RESULTS - sc3mods release 2026-10-28e + LAN republish

Replaces `sc3mods-2026-10-28d`. Owner requests 2026-10-28: a loaded autosave must not save under the autosave name, the
latest features on the mods page, plus four more page rows (owner: "Add all four"). Source as of `7b5873c`.

| what | commits | record |
|---|---|---|
| UNAUTO: a loaded autosave saves to <city>.sc3 | 379e628 | commit message (Frankfurt check, name read back) |
| modsopts: Edificios (Mover, build over zones, live), FPS cap (live, new sc3perf exports), autosave "save to original city" + 60 min, overscroll slider + edge push (live, new sc3overscroll exports) | 7b5873c | verify/modsopts/RESULTS.md |
| GitHub README: the mods section | ca2f308 | README.md |

Shipped: sc3resize.dll, sc3autosave.dll, sc3perf.dll, sc3overscroll.dll, README.txt. Every other file is the 10-28d one.

## Stage and checks

- `stage/bins_1028e` = `stage/bins_1028d` + the four DLLs built from main. Label `2026-10-28e`, 3,606 files, 697.3 MB.
- Launch check (stage/release patched, windowed, no input): Berlin, `8 mod(s) loaded`, `RELOCATE> on`, sc3overscroll
  `PUSH: low-level mouse hook installed`, sc3perf `fps_cap=-1`, autosave interval started, only the benign
  `0xC0000096 @ SC3U+0x84122`. Then `-Restore`, logs deleted, 3,606 manifest files re-hashed: 0 changed, 0 missing, 0 extra.

LAN: 4 of 3,606 files sent (0.9 MB). Served label `2026-10-28e`, the four served DLLs' SHA-256 match the stage.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/sc3resize.dll | 458752 | 6F5E15E395E692D757372DE15AAFE4B77409197B351F842AFFB99F66549A774C |
| Apps/sc3autosave.dll | 131072 | B5BC8E0E66669B6AFDC46577A33ADCEEC743A91E1678957E8E4895C2AA4B15E7 |
| Apps/sc3perf.dll | 191488 | B37BCEAE6BA4A2ABBAF74C0AFEF804863D80765D26C707D34428C19AAE03123F |
| Apps/sc3overscroll.dll | 134144 | 4E272096C2831B2A17ADCC327B7B4490F7218EB5BCFCD1A94CE3A042026C95C9 |
| README.txt | | 2026-10-28e section, autosave.ini unauto= |
| every other file | | as `verify/mods_release_1028d/RESULTS.md` |
| `sc3mods_2026-10-28e.zip` | 43,623,691 | 46EEFBE0E22C458D2B60B56187F9C3CEF7AEC9213206B86E3EDE436A8B2C3672 |

Not tested by modsopts: the overscroll slider's effect on the camera, the Monitor / 120 / Sin límite radios, English text, cancel.
Owner checks pending: a Save after loading an autosave, plus the 10-28c / 10-28d items.
