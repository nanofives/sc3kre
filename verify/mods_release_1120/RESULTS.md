# RESULTS - sc3mods release 2026-11-20 + LAN 2026-11-20

Replaces sc3mods-2026-11-19c. Owner calls 2026-11-20: "True 2x3, patch drawing", "Allow 5x5", "Prepare it", "Yes,
release". Source: main 25d1834.

| what | merges | record |
|---|---|---|
| sc3perf LOTRECT: non-square building sprites register, draw, clip, pick and sort as X x Z, saves record the true footprint (9 save routines), mods page row "Non-square buildings" (sc3resize), lang tables | 96a80c3 | verify/lotdraw/RESULTS.md, re/analysis/LOT_SHAPES.md |
| importer: landmarks and rewards on [w, d] lots and 5x5, SC4 lots kept (page only, already live) | 74f9b9b | verify/lotshape/RESULTS.md |

## Stage and checks

- sc3perf (209,408 bytes) and sc3resize (755,200 bytes) from main into stage/build_1120. stage/bins_1120 = bins_1119c
  + those + the 7 lang tables (358 keys each, 0 missing). Jotti: 0 / 13 each.
- stage_lan_release.py label 2026-11-20: 3,679 files, against 2026-11-19c exactly 9 changed (2 DLLs, 7 lang tables).
  stage/release swapped (old: stage/release_1119c_old), LAN deploy incremental (9 files, 1.1 MB), served 2026-11-20.
- Smoke: dev tree from the new stage with the shipped DLLs, Berlin loaded windowed and drawn (picture checked). Log:
  "LOTRECT> 29 SIMSPR sites patched", "LOTRECT> save footprint: 9 of 9 occupant descriptor fillers". VEH lines: the
  usual startup 0xC0000096 at SC3U.exe+0x84122, and one first-chance 0xC0000005 read at KERNEL32+0x2D2D0 at 2.6 s whose
  return address is sc3resize+0x48A57, after `call ebx` with ebx = the IsBadReadPtr import (sc3resize+0x489D2 loads it
  from 0x10088120): a handled IsBadReadPtr probe of 0xE4 bytes across an unmapped page, the game went on to load Berlin.
  Not from LOTRECT. Non-square buildings were not re-placed on the shipped files (no saved test city survived), they
  were tested in game on the same source by lotdraw and lotshape.

## Zip

The 2026-11-19c zip tree with sc3perf.dll, sc3resize.dll and Apps/sc3lang from the stage, README.txt (header
2026-11-20, NEW IN 2026-11-20). 198 entries: 191 equal to the LAN manifest, overlay SYS.PAK differs by design,
README.txt and the 5 tools\bld_render files not in it. sc3mods_2026-11-20.zip, SHA-256
947C6B738F1A2617D4A86742E04F32D034DED1AF95B2A3A6DB94166628A910C9.

GitHub: `sc3mods-2026-11-20`, target 25d1834, asset downloaded back, SHA-256 matches. The 2026-11-19c notes start with
a "superseded" line. Repo README "Speed and stability" updated.
