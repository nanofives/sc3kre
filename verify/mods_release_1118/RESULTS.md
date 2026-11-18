# RESULTS - sc3mods release 2026-11-18 + LAN 2026-11-18

Replaces `sc3mods-2026-11-17c` (GitHub) and LAN `2026-11-17c`. Owner calls 2026-11-17: "Yes, release" (after the
gallery got 49 / 51 / 53), "Ship it, better than before" (49 at 3 rows), "Keep the new ends", "English only", "Take it
out" (highway_core). Source: main be34cac (round brief `re/sessions/ROUND_2026-11-17b_leak1024_dbvx.md`).

| what | merges | record |
|---|---|---|
| Junctions 49 / 51 / 53 on short arms: diagonal_boulevard 0.3.1 (short-arm templates 23..30) + sc3netmod DBVCAPNEAR, DBVXENDCAP, DAVSHORTBOX | 6af72fe | verify/dbvx49/RESULTS.md |
| The ENGLISH text folder gets English names and the English Engineer's Report question (netpack.py `_names`) | 70e08d1 | round brief, "Owner calls" |
| highway_core uninstalled from the release source | 70e08d1 (stage only) | round brief, "Owner calls" |

## Stage and checks

- stage/src: highway_core uninstalled, then diagonal_boulevard 0.3.0 -> 0.3.1 (backups `stage/src_netmod_backup_20261117c`
  and `_20261117d`). Ledger 25 packs. `tables/diagonal_boulevard.txt` = dbvx49's tested table byte for byte. ENGLISH
  `SC3StringsNetpack*.IXF` = English-UK byte for byte.
- Offline rebuild check (merge from the ledger): old names + highway_core = the 17c overlay byte for byte (130 files),
  the names change alone touches the 2 ENGLISH text files, removing highway_core 57 files.
- DLL: `stage/build_1118/sc3netmod.dll` from main (SHA-256 D9397B3F5C862C62C99594C431E781140205CCA71CDA5E38CCD2B2EC30D5B9E0).
  `stage/bins_1118` = `bins_1117c` + that DLL. Jotti's malware scan: 0 / 13.
- `stage_lan_release.py ... --bins stage/bins_1118 --label 2026-11-18 --community stage/community_1106`: 3,679 files.
  Against 17c: 60 changed (59 in mods/netmod, Apps/sc3netmod.dll), 1 removed (mods/netmod/tables/highway_core.txt).
  `stage/release` swapped (old: `stage/release_1117c_old`). LAN deploy incremental (60 files, 67.0 MB), served label
  `2026-11-18 3679`, served sc3netmod.dll SHA-256 matches.
- Smoke: a dev tree from the new stage with the exact staged DLLs, xsect_sweep_built.sc3 loaded windowed: drew the mod's
  pieces (diagonal avenue under a highway), dbv load stats with the new end caps, 0 VEH faults besides the usual startup
  0xC0000096 at SC3U.exe+0x84122. Fix evidence: verify/dbvx49 (80-case sweep, both draw orders, Berlin 0 cells differ).

## Zip

The 2026-11-17c zip tree with `Apps/sc3netmod.dll` from `stage/bins_1118`, `mods/` rebuilt from stage/src for every
`mods/` path of the new LAN manifest (153 files), README.txt updated (header 2026-11-18, NEW IN 2026-11-18). 193 entries:
191 equal to the LAN manifest, 1 differs by design (overlay SYS.PAK without the community lines, unchanged from 17c),
README.txt not in it. `sc3mods_2026-11-18.zip` 92,266,673 bytes,
SHA-256 D62A0944AE4C83F303697489497E81C6C9B69A747C7D4318F8A243FEA0303745.

A player who unzips over 17c keeps `mods\netmod\tables\highway_core.txt` (sc3netmod reads every tables\*.txt): two
variant ids without art and the hwyt rule, which runs only with SC3NETMOD_HWYT=1. README says it can be deleted.

Open: 49 at 3 rows keeps a 1-row stock avenue stub above the box (dbvx49 section "Open", gallery ISSUES 7).
