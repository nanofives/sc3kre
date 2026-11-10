# RESULTS - sc3mods release 2026-11-10 + LAN 2026-11-10

Replaces `sc3mods-2026-11-09` (GitHub) and LAN `2026-11-09`. Owner call 2026-11-10: "Release it now (LAN + GitHub)".
Source: main `e238672` (merge of child/avends).

| what | commit | record |
|---|---|---|
| B1 avenue T next to link noses (SC3NETMOD_AVTEE), B2 corner + T over a plain 29, piece 22000 (SC3NETMOD_AVCT29) | d127967 | verify/avends/RESULTS.md |
| E dead-end stub arm (SC3NETMOD_AVSTUB), A1/A2 U-turn ends, piece 22001 (SC3NETMOD_AVUEND) | 79bd838 | verify/avends/RESULTS.md |
| F knot: DBV bend with avenue arm (DBVBENDT), 3-column narrowing run (BVSHORT), narrowing + T 22002..22013 (BVNT), AVL keeps its band map on load re-runs (AVLKEEPMAP) | fe4e741 | verify/avends/RESULTS.md |

Owner Big One (MARIANO-PC autosave): 50 one-way bands, 4 refused (34 / 16 before the round). The 4 left are the D4 chain,
which waits on the owner re-dragging (608,134).

## Stage and checks

- Stage source backup: `stage/src_bak_1110` (`mods/` + the netmod-managed Apps files). `netpack install
  dev/avends/wt/re/tools/netmod/examples/avenue_ends --tree stage/src --allow-tree`. `mods/netmod/overlay` + `tables` are
  byte-identical to the child's tested tree (dev/avends/tree) except SYS.PAK (community inserts are applied at staging).
- `stage/bins_1110` = `stage/bins_1109` with `sc3netmod.dll` rebuilt from main (`build_mod.ps1`, 457,728 bytes, same size as
  the child's tested build).
- `stage_lan_release.py ... --out stage/release_1110 --label 2026-11-10 --community stage/community_1106`: 3,645 files,
  712.3 MB. Against LAN 2026-11-09: 79 changed (sc3netmod.dll + netmod overlay: 53 sprite files, tiling rules 3,
  TRBLKATT/VPATHATT 14, strings, Korea occupants), 1 added (`mods/netmod/tables/avenue_ends.txt`), 0 removed. No -Prune needed.
- Launch check (release_1110 patched, windowed, Berlin, no input, ~120 s): `11 mod(s) loaded`, avenue_ends.txt variants
  22000..22013 read, `avp: ... off (default)`, 0 bad table lines, avl converted 269 / refused 131, avx 473 boxes, 0 reverted;
  only the benign `0xC0000096 @ SC3U+0x84122`. Then `-Restore`, logs + dataview.ini + landfill.ini deleted, manifest check:
  0 changed, 0 missing, 0 extra.

LAN: `deploy_lan_release.sh stage/release_1110` sent 80 of 3,645 files (74.6 MB). Served label `2026-11-10`, served
sc3netmod.dll SHA-256 = staged (6BF6948F...). `stage/release` -> `stage/release_1109_old`, `stage/release_1110` -> `stage/release`.

Zip: the 11-09 zip (downloaded back, SHA-256 C2D77D1B... as recorded) with Apps/sc3netmod.dll and README.txt (NEW IN
2026-11-10) replaced and `mods/` replaced from the stage. 159 entries, 158 checked against the staged manifest, 0 mismatches
(README.txt is not in it), 121 mods files = manifest. `sc3mods_2026-11-10.zip` 51,685,212 bytes, SHA-256
983B27718E368B9B1CF5E9AECCEFCF7C4CF30AC16D06699F9D4B3DE1263C80F4.

Not checked: English-UK game run, bend-x variant of the F knot (stays stock), the 4 Sacramento puts the game refuses (open
item in verify/avends/RESULTS.md, predates this round).
