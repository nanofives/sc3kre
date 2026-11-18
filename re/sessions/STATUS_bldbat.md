# STATUS bldbat (round 2026-11-18e)

## goal
Real four-view, all-zoom frames for any Building Architect .bld, rendered by the BA's own batch renderer, windowed
only. Steps 1-4 of the brief.

## verdict + deciding RVA
DONE, steps 1-4 (2026-11-18). Full write-up: verify/bldbat/RESULTS.md, format notes re/analysis/BLD_FORMAT.md 5.
- Step 1: Baapp windowed with no mode switch. Only GZGraphicD can switch modes in that process: 1 SetDisplayMode site
  (0x10011f73) + 1 exclusive-coop site (0x1001250d), both behind set_display_mode(1). bawinonly.dll guards both, plus
  the sc3winonly patches, fail-closed. 71 launches, external sampler: 0 mode changes.
- Stock Baapp heap bug fixed in the same DLL (STRTOKFIX, 0x419e04 / 0x41a429); FIX16 required.
- Step 2: Baapp embeds the BA code (no SIMBABLD load). FUN_004044a9 = SIMBABLD 0x12001faf; app DAT_004954e0, vtable
  0x480c78, slot +0x10. 17 of 17 shipped .bld rendered; 237 of 240 frames same size/anchor as BAT.DAT; 12 of 15
  buildings RMS <= 8.6; 3 have shipped entries missing textures.
- Step 3: embedded part > BACustom file with identical content > flat face (runs X/Y/W). `bldfile.py parts`.
- Step 4: `bldfile.py render <folder> --game <tree> --out x.ixf [--install]`; importer reads it as "bat", 17 of 17.

## built
- bawinonly.dll + BaappW.exe in dev\bldbat\tree\Apps (ba_patch.py). Tree BAT.DAT now holds the 17 renders
  (backup BAT.DAT.bldbat-orig); bldimport test install of Zweikky + Trash & Burn in the tree's overlay.

## proven game-side vs static only
- Game-side (Baapp runs): windowed safety, both crash fixes, renders, custom-part precedence, importer path.
- Not done: in-game growth of the new art (SC3U); classifier page against the merged BAT.DAT.
- Static only / UNCERTAIN: texture hash function; why the renderer's instance is not the .bld id (+0x1a8 stays 0);
  why 3 shipped BAT.DAT entries lack textures.

## blocked on
-

## files owned (worktree dev\bldbat\wt; new files are hidden by the deny-by-default .gitignore: git add -f)
- re/harness/src/bawinonly.c            (new, add -f)
- re/tools/bldbat/ba_patch.py           (new, add -f)
- re/tools/bldbat/ba_gate.py            (new, add -f)
- re/tools/bldbat/ba_render.py          (new, add -f)
- re/tools/bldimport/bldfile.py         (modified: parts, render, custom_textures, ixf_buildings, rekey, install)
- re/analysis/BLD_FORMAT.md             (modified: section 5)
In MAIN: verify/bldbat/RESULTS.md, re/sessions/STATUS_bldbat.md. Not for commit: verify/bldbat/runs/, owner_shots/
(game art), ghidra/SC3_Baapp, re/ghidra_export_baapp/, original/modules/Baapp.exe (+ ANCHORS.txt line).

## game-harness need
dev\bldbat\tree only. Frida 17 + Python 3.12. No SC3U launches.

## asks of other sessions
- Orchestrator: decide the player-side route (needs Frida today).
