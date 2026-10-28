# STATUS modsui
- goal: Opciones de mods page: buttons bottom-left at OK height without blue box; camera sliders on a light-blue panel.
- verdict: placement + panel done and seen in game. Blue box NOT removed (game's own button draw, OK tick has it). See verify/modsui/RESULTS.md.
- built: dev\modsui\inst\sc3resize.dll. Proven game-side: both pages, click on Opciones de mods / Volver switches.
- blocked on: nothing; blue box needs an owner-drawn button or a backing panel (owner call).
- files owned: re/harness/src/sc3resize.c, verify/modsui/RESULTS.md, re/sessions/STATUS_modsui.md
- game-harness need: none. needs owner check: look at the pictures.
