# STATUS zoomcrash (child of "SC3: owner bugs 10-23", 2026-10-25)

State: FIXED + stub audit done. Worktree `Simcity_wt_zoomcrash`, branch `child/zoomcrash` from main 54bf548. Nothing
committed (claude2 policy).

Cause: the CITYZOOM skip path in zc_wrap0 / zc_wrap1 (ZOOMCENTER, iso vt+0x60/+0x64) ended in a bare `ret`, but the
originals return with `ret 4`. So each step left 4 bytes on the stack, and FUN_10042d8a popped the wrong ESI / EBX. On the
minimap-button path, sc3undo's thiscall helper (`mov esp, ebx`) turned that into a bad ESP and a silent 0xC0000005 kill
with no handler. The '+' key path survived by luck. Not size related. Fix: `ret 4` in both. Detail:
`verify/zoomcrash/RESULTS.md`.

Audit (orchestrator request): every naked stub in the 7 mods was checked against its original's `ret N` by disassembly
(table in RESULTS). A new runtime audit, `re/tools/hook_audit.py`, diffs the live game against its disk files: 319 install
points and 154 hook entries. Unfixed build: exactly 2 MISMATCH (the zoom slots). Fixed build: 0 MISMATCH. The 3 CHECK
rows are indirect call sites, verified by hand. No other mismatch found, so no other change.

Tests (fixed build): minimap buttons and +/- keys, in and out, x2 and x3, with scrolling, at 2560x1351, 2561x1351,
2560x1350 and 3808x1984. Plus button-only runs at 2560x1440, 2400x1299, 1920x1080 and with the off switch. 0 crashes.

## Files to commit (from the worktree)
- `re/harness/src/sc3resize.c` (the fix + comment, 10 lines)
- `verify/zoomcrash/RESULTS.md`
- `re/tools/hook_audit.py`, `re/tools/exit_catch.py`, `re/tools/zoom_stalk.py`, `re/tools/zoomcrash_run.py`
- this file

Local only (gitignored): `MAIN\verify\zoomcrash\owner_shots\01..05_*.png`, `MAIN\verify\zoomcrash\runs\` (audit
listings `hook_audit_fixed.txt` / `hook_audit_unfixed.txt`, traces, logs).

Needs owner check: the mouse wheel at zoom 4 (same wrapper, not drivable by posted messages).
