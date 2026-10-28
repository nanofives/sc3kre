# STATUS modsui2
goal: mods page buttons at tick top/bottom, x 6; one click on Volver / Opciones de mods without moving the mouse.
verdict: fixed. Cause: dialog keeps the hidden button as mouse-over child until a move leaves it. Fix: out-and-back posted moves in mp_show.
built: dev\modsui2 sc3resize.dll. proven game-side: posted clicks both directions. static only: none.
blocked on: nothing. Autosave rotation / load crash from the title: not in the brief text I received, untouched.
files owned: re/harness/src/sc3resize.c, verify/modsui2/RESULTS.md (verify/modsui2/owner_shots is never git add).
