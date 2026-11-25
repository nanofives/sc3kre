# STATUS rotprobe
goal: can an occupant's own rotation draw a building turned, and does it survive save and reload.
verdict: YES, slot (view + rotation) & 3. Deciding code SIMSPR 0x1005aeab (frame), SIMGEOM 0x1001ce12 (state from occupant +0x10 >> 30). Changing a placed occupant live does NOT redraw.
built: nothing (probe only).
proven game-side: load of rotation 1-3 from an edited save draws turned (8 occupants, 2 types); the game's autosave writes a live-changed rotation back.
static only: the plop tool's call site of rotation 0 (candidate 0x10007760); Mayor's House itself (none in shipped cities).
blocked on: nothing.
files owned: re/analysis/BUILDING_ROTATION.md, re/sessions/STATUS_rotprobe.md, verify/rotprobe/** (scripts, owner_shots, test pngs)
game-harness need: released, game stopped.
asks of other sessions: none.
