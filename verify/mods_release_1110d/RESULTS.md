# RESULTS - sc3mods release 2026-11-10d + LAN 2026-11-10d

Replaces `sc3mods-2026-11-10c` (GitHub) and LAN `2026-11-10c`. Owner calls 2026-11-10: "Release now" for all three
building features, and "Ship it in the zip" for the style art (29 MB of building-set art copied unchanged from the
game, a release asset only, like the road data). Source: main after `3c8247a` (merges of child/stylemix, child/batslots,
child/batconvert).

| what | merge | record |
|---|---|---|
| style_mix: the European and Asian building sets grow next to the North American one at random (netpack style_sets, ids +400000 / +1500000) | 1dce4f6 | verify/stylemix/RESULTS.md |
| bat_slots: 16 growable slot buildings (36100..36121) in [ReplaceableBuildings], skinned with a .bld through the stock Replace dialog | 9495982 | verify/batslots/RESULTS.md |
| tools\bat_growables.ps1: every Building Architect building becomes its own growable building (37000..), player-side, -Restore | 3c8247a | verify/batconvert/RESULTS.md |
| stage_lan_release.py ships `tools\bat_growables.ps1` (unrun) | this commit | this file |

## Stage and checks

- DLLs: `stage/bins_1110b` unchanged (no mod source change since 10b).
- Stage source: `stage/src_bak_1110d` = backup of `stage/src/mods/netmod`. `netpack install --tree stage/src --allow-tree`
  of `netmod/examples/style_mix` then `netmod/examples/bat_slots` (ledger: 22 packs).
- `stage_lan_release.py ... --bins stage/bins_1110b ... --out stage/release_1110d --label 2026-11-10d --community
  stage/community_1106`: 3,650 files, 743.0 MB. Against LAN 2026-11-10c: 11 changed (Korea pair, `4E3D0034_netpack.DAT`,
  7 `SC3StringsNetpack.IXF`, overlay SYS.PAK), 5 added (`BUILDFAM.IXF`, `4E3D0035_netpack.DAT`,
  `5432D60E_netpack_set.DAT`, `547B7DF5_netpack_set.DAT`, `tools/bat_growables.ps1`), 0 removed. Staged overlay
  SYS.PAK: 16 slot rows in [ReplaceableBuildings] and the Civic Deals lines; stage/src's: the 16 slot rows only.
- End-to-end check on the staged tree (patched exe, SC3U.exe direct, windowed, no SC3* overrides besides the window):
  `tools\bat_growables.ps1` under Windows PowerShell 5.1 converted 12 of the 15 BAT buildings (3 off by default);
  stage/src's Korea / CSAttrib_Korea / BUILDFAM still equal the manifest (the tool did not write through the hard
  links). Sacramento, CA at speed 4: `11 mod(s) loaded`, CRASHGUARD + VALVESHUT lines, only the benign
  `0xC0000096 @ SC3U+0x84122`. First autosave (4.5 min): stock 15,894, slots 24, converted BAT 17 (7 ids), European
  333, Asian 96 (`re/tools/batgrow_count.py`). Then `bat_growables.ps1 -Restore` (11 files put back), sc3mods_patch
  `-Restore`, logs / ini / autosave deleted, manifest: 0 changed, 0 missing, 0 extra.
- Jotti (13 engines): `tools/bat_growables.ps1`, `community/community_patch.ps1`, `sc3mods_patch.ps1` 0 of 13 each. The
  DLLs are 10b's, scanned clean then.

LAN: `deploy_lan_release.sh stage/release_1110d` sent 16 of 3,650 files (32.7 MB). Served label `2026-11-10d`, served
`547B7DF5_netpack_set.DAT` and `tools/bat_growables.ps1` = staged. `stage/release` -> `stage/release_1110c_old`,
`stage/release_1110d` -> `stage/release`.

Zip: the 10c zip with `mods/` rebuilt from stage/src for every `mods/` path of the LAN manifest (125 files, the overlay
SYS.PAK without the community lines, as in 10c), `tools/bat_growables.ps1` added, README.txt updated (header 2026-11-10d,
NEW IN 2026-11-10d, WHAT'S INSIDE lines). 164 entries, 163 checked against the LAN manifest, 1 differs by design (the
overlay SYS.PAK), README.txt not in it. `sc3mods_2026-11-10d.zip` 78,727,036 bytes, SHA-256
E09F2ECEFF110C6CC5FCDFB774964907977A4E1390E7CB5C38C9FBBC0E850237.

Not checked (owner): the Building Replacement Manager window (New City flow) with the slots, a 2x2 BAT on a 2x2 slot, a
.bld the player adds with "Edit list" then converted, a European-style city with the mix.
