# Round 2026-11-21: Simtropolis feedback (pop-up slowdown, mods hidden by the overlay, SC4-like styles, civic styles)

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspaces from main.
A player wrote on the sc3mods Simtropolis thread (2026-11-21):
1. "the simulation speed drops when a pop-up menu appears. It isn't a big issue"
2. "I tried to install this agricultural mod that I used before but it doesn't appear in-game ... doesn't throw any
   errors when it installs" (mod name unknown yet: we ask after the work)
3. "building styles ... work like SC4? choosing a building style doesn't change the appearance of existing buildings,
   but it does affect what buildings get built. And perhaps this could even extend to the civic buildings as well, so
   you could mix and match what schools/parks/hospitals/etc. appear in a city."
Owner (2026-11-21): all four, in this order, one stream at a time; the reply to the player after the work.

## Stream popslow (opus / high): simulation speed with a pop-up open

Measure game days per real second (or sim ticks) with no pop-up and with common pop-ups open (query window, a
petition / Reunirse, budget, the mods page, a newspaper or advisor message, the Rewards list), mods on and mods off
(sc3dev run -Stock), at Normal and at an Auto / 200% interface scale. Find the cause with evidence (memory notes on
DLGSCALE / NATIVETEXT / FONTCACHE: per-glyph GPU waits in video memory slowed Reunirse before; also a modal loop, a
redraw every frame, a timer). Stock behaviour stays (if the stock game also slows, say by how much and whether the mods
make it worse). Fix what the mods cause, behind the usual switch rules. Results verify/popslow/RESULTS.md.

## Stream overlaymerge (after popslow): other mods hidden by the netmod overlay

With sc3netmod the game reads mods\netmod\overlay copies of SYS.PAK and some Apps\Res files instead of the Apps ones
(memory project-simtropolis-feedback-1114: "the game reads mods\netmod\overlay\Apps\Sys\SYS.PAK"), so a mod that edits
the Apps originals installs fine but is never seen. List exactly which files the overlay shadows. Make sc3netmod (or the
overlay build) notice stock files a player changed after our install (hash against the stock hashes we know) and merge
the player's change into the served copy where the format allows (IXF records, SYS.PAK ini sections), else warn in the
log and in game. Test with a hand-made test mod of each kind (a BUILDFAM / occupant edit like a farm mod would make, a
SYS.PAK ini edit) and with the community mods' own patch. Results verify/overlaymerge/RESULTS.md.

## Stream stylepick (after overlaymerge): SC4-like building style choice

Today (memory project-building-styles-mixing, re/analysis/BUILDING_PICK.md): the stock style picker re-skins every
live building (SetCityScheme 0x10006589), and the style mix (sc3netmod, netpack style_sets, ids +400000 / +1500000,
weights in BUILDFAM, switch STYLEMIX) grows all three styles at once. Goal: the game's style choice picks which style
NEW growables use, existing buildings keep their look, plus a "Mixed" choice (today's behaviour). Evidence first (how
the picker reaches SetCityScheme, what is saved, whether family weights can change at run time), then the hook, the
weights, save / load, mods page row. Results verify/stylepick/RESULTS.md.

## Stream civicstyle (after stylepick): civic buildings per style

The style sets hold European and Asian art for the stock civic buildings. Offer them as looks in the civic list window
(round 2026-11-19k civdlg): Police Station North American / European / Asian, and so on for every civic button and
park that has set art, without the player importing anything. Results verify/civicstyle/RESULTS.md.

## Rules

Windowed game, never the real mouse or keyboard, test slot, kill only PIDs you started, delete BMP dumps, no git add /
commit. EA content (set art) only in the test tree and release assets as today, never in git or docs.
