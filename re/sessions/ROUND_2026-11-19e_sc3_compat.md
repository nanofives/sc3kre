# Round 2026-11-19e: SC3-side building compatibility (loop until done)

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspaces from main.
Owner (2026-11-19): "also loop the sc3-side compatibility until you're done": 1999 .bld support, the player-side
four-view render tool, the pack reader. Releases still need the owner's OK.

Background: verify/bldfile/RESULTS.md, verify/bldbat/RESULTS.md (BaappW.exe + bawinonly.dll, windowed, no mode switch
over 71 launches; batch renderer FUN_004044a9 driven by Frida; strtok heap fix; FIX16 needed), re/analysis/BLD_FORMAT.md,
re/tools/bldimport/ (bldfile.py, bldimport.py, bldweb.js, classifier.html), re/tools/bldbat/.
Samples (local only): stage/st_packs/maxis_batpatch_1999/ (19 .bld from the 1999 Building Architect patch: today's
reader says "info record too short"), stage/st_packs/maxis_addons_2000/ (Maxis landmark packs: .dat + .pin, an add-on
plugin installer), MAIN\Buildings\*.bld (17 shipped), MAIN\Apps\BACustom\{Paints,Details,Props} (game parts).
Child gamefont is editing classifier.html, sc3ui.css, sync_css.py, sc3font.js now: do not touch those until the
orchestrator says gamefont is merged; then add one hook.

## Stream sc3compat-a (opus / high): 1999 .bld + the player-side render tool

1. The 1999 .bld format (original SC3 Building Architect): what differs from the SC3U one (info record and anything
   else), with offsets, in BLD_FORMAT.md. bldfile.py and bldweb.js read both; all 19 + 17 samples parse, Python and
   page identical (extend the golden tests).
2. Do the 1999 files render in the SC3U Building Architect batch renderer? (bldfile.py render on the 19.)
3. Player-side render tool, no Python, no Frida: bawinonly.dll grows a batch mode: started with a list file (or a
   folder) it waits for the BA app object, calls the batch renderer once on the main thread, writes the BAT-format IXF
   next to the .bld folder (never into the game's BAT.DAT), and exits; every display-mode guard stays, fail closed.
   BaappW.exe is made on the PLAYER's machine from their own Baapp.exe by a script (the sc3mods_patch.ps1 pattern,
   accepted hashes, the strtok fix and FIX16 included), never shipped. A one-click `render_bld.ps1 <folder>` runs it.
   The importer (Python and page) reads that side IXF as the "bat" art source for the .bld files next to it.
4. Proof: render the 17 shipped + the 19 1999 files with the player route on a dev tree (no mode switch, sampled as in
   bldbat), frames equal to the Frida route's, the page installs them with four real views, a few grow in Sacramento.
   Phone-sized pictures in verify/sc3compat_a/owner_shots/. Antivirus: scan the new DLL on Jotti (re/scripts note in
   memory: VERSIONINFO via build_mod AVVERSION).
Results verify/sc3compat_a/RESULTS.md.

## Stream sc3compat-b (opus / medium): the pack reader

1. A new re/tools/bldimport/sc3pack.js (+ Python twin sc3pack.py for tests): open a pack as downloaded (zip, folder,
   zip in zip), sort its files into .bld buildings, Building Architect parts (Paints / Details / Props: bmp, tga, met,
   txt, matched by folder names and content), plugin files (.dat + .pin, the Maxis add-on style: identify only, they
   are ploppables for a later round), readmes, and unknown files; show the sort in the page.
2. Dependency report per .bld: every part name it uses (bldfile already lists them), resolved against the .bld's own
   embedded parts, the pack's parts, and the game's Apps\BACustom (byte-compare same-named files as the BA renderer
   does), with missing ones named.
3. Install parts into Apps\BACustom from the page with backups and Remove putting them back (same backup scheme as the
   importer), never overwriting a different file with the same name without saying so.
4. Test packs: build 3 local test packs from the samples (a plain .bld zip, a .bld + parts pack using parts copied from
   the game's BACustom renamed so they are "new", a zip with a nested zip + readme + plugin files), plus the Maxis
   landmark installers' contents. Golden tests Python vs page in webtest (run_all.sh must pass).
5. Write the page code in sc3pack.js; the hook in classifier.html waits for the orchestrator (gamefont).
Results verify/sc3compat_b/RESULTS.md.

## Rules (both)

Windowed only, posted input only, test slot for long runs, kill only PIDs you started, delete BMP dumps, STATUS at every
milestone, no git add / commit. Never ship EA files (Baapp.exe, BACustom parts, samples) in the repo or a release.
