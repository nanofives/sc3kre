# Round 2026-11-18e: compatibility with Simtropolis building packs

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspaces from main 8a206e5+.

## Owner (2026-11-18)

"can we add a layer of compatibility for buildings in packs within simtropolis?" Packs on Simtropolis hold Building
Architect .bld files, often with custom BA parts (Apps\BACustom\{Paints,Details,Props}: bmp / tga / met / txt) that the
.bld names; some older ones come from Maxis' SC3URK (format unknown until the owner sends samples). Simtropolis blocks
automated downloads (403), so sample packs come from the owner.

## Stream bldbat (opus / high): real four-view frames for any .bld, rendered by the game's Building Architect

Background: verify/bldfile/RESULTS.md ("Real frames for every .bld"): the BA batch renderer
sc3_bat_export_rendered_buildings_ixf (SIMBABLD 0x12001faf), slot +0x10 of the BA app object (vtable 0x12069a84,
singleton DAT_12079434), only inside Apps\Baapp.exe, writes an IXF in BAT.DAT format. Blocker: Baapp has no windowed
option, a launch could switch the display mode (hard rule: windowed only).
Do:
1. Make Baapp.exe open windowed in a dev tree (how it opens its display, GZGraphicD path, the windowed byte / FIX16 /
   DPI work sc3resize and sc3winonly do for SC3U), proven windowed WITHOUT a mode switch before any full launch:
   static first, then a launch under the virtual display or with the patch verified in memory. If you cannot prove it
   safe, stop and tell the orchestrator.
2. Drive the batch renderer (Frida, exceptions: propagate) on a folder of .bld files, read the output with
   bldfile.bat_frames, and compare against BAT.DAT frames for the shipped buildings (should match).
3. Custom parts: a .bld that names BACustom parts renders right only with them installed: list the names a .bld
   needs (bldfile already parses them), and what the renderer does when one is missing.
4. Wire it as `bldfile.py render <folder> --game <tree>` (Python, dev side) producing a BAT-format IXF the importer
   (Python and page) already reads as the "bat" art source. A player-side route comes later (orchestrator decides).
Results verify/bldbat/RESULTS.md, notes in re/analysis/BLD_FORMAT.md.

## Later (needs owner samples)

Pack reader: zip / folder -> buildings, BACustom parts, other items; install parts with backups; dependency report;
SC3URK format.
