# RESULTS - sc3mods release 2026-11-17 + LAN 2026-11-17b

Replaces `sc3mods-2026-11-10d` (GitHub) and LAN `2026-11-10d`. Owner call 2026-11-17: "can you make a release in the
meantime?" after the junction rounds were reviewed (final1117 sheet, then "Fix 31-33 first", merged 73826b8).
Source: main 73826b8 (+ this record).

| what | merges | record |
|---|---|---|
| `sc3mods_patch.sh`, the exe patch for Linux / macOS (Wine, Lutris, CrossOver) | be6f100 | verify/lxpatch/RESULTS.md |
| Land value average capped at 255 (sc3simrun LVWRAP), property tax no longer collapses | 32b29cf | verify/lvwrap/RESULTS.md |
| Sandbox mode + gentler abandonment (sc3simrun SANDBOX / GENTLE, off by default; GitHub issue #3) | 2b564ed | verify/abandon/RESULTS.md |
| Road junction rounds 2026-11-14b and 2026-11-15b (diagfix, orthfix, diagxnet, shortarm): rail / highway kept and crossing art under diagonals, junction boxes, 135-degree bends, corners, BVQUAD, on-ramps beside diagonal avenues (diamond), art fixes | 40107e1 .. 73826b8 | verify/xsect, verify/diagfix, verify/orthfix, verify/diagxnet, verify/shortarm, verify/final1115, verify/final1117 |

## Stage and checks

- DLLs: `stage/bins_1117` = all 12 mod DLLs built from main b6281ac (dev/integ1117) + main's sc3lang tables; no C
  change since (73826b8 changed only the avenue_dbv_t pack).
- Stage source: backups `stage/src_netmod_backup_20261115`, `_20261117`, `_20261117b`. Ledger 26 packs; every SHIP
  table count matched (ROUND_2026-11-14b_junctions.md, ROUND_2026-11-15b_owner_review.md).
- `stage_lan_release.py --game stage/src --bins stage/bins_1117 ... --label 2026-11-17b --community stage/community_1106`:
  3,680 files, 767.2 MB. Against LAN 2026-11-10d: the 12 DLLs, 7 lang tables, mods/netmod and `sc3mods_patch.sh` (LF).
- Final check on a fresh tree from the 2026-11-17 stage (dev/final1117, no hand installs, verify/final1117): 80-case
  sweep, reverse draw orders, the case 80 diamond, rail / highway drawn across a diagonal; 39 green, 3 amber (31-33),
  0 red. 31-33 then fixed (avenue_dbv_t 0.2.0, verify/shortarm) and re-staged as 2026-11-17b.
- Jotti's malware scan: all 12 release DLLs 0 / 13, `sc3mods_patch.sh` 0 / 14.

## Zip

The 10d zip (downloaded back from GitHub, SHA-256 matched the 10d record) with the 12 DLLs, sc3lang and sc3natworld.bin
from `stage/bins_1117`, `mods/` rebuilt from stage/src for every `mods/` path of the LAN manifest (154 files, the
overlay SYS.PAK without the community lines, as in 10d), `sc3mods_patch.sh` added, README.txt updated (header
2026-11-17, WHAT'S INSIDE and INSTALL lines for the .sh, NEW IN 2026-11-17). 194 entries: 192 equal to the LAN
manifest, 1 differs by design (overlay SYS.PAK), README.txt not in it. `sc3mods_2026-11-17.zip` 92,358,415 bytes,
SHA-256 48B0628786D6607DBA7E91D6DDE9F86AC1600C4181620FE06AF5A82277E1EDAF.

Not checked (owner): macOS, a real Steam exe with the .sh, the mods page rows in a language other than Spanish.

GitHub: `sc3mods-2026-11-17`, target a62e8cc, https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-11-17, asset downloaded back, SHA-256 matches. The 10d notes start with a "superseded" line.
