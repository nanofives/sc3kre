# STATUS lxpatch (round 2026-11-14 Simtropolis)

## goal
`re/scripts/sc3mods_patch.sh`: POSIX sh port of `sc3mods_patch.ps1` for Linux/macOS (Wine, Lutris, CrossOver), no
Python/PowerShell/xxd, output byte-identical to the .ps1 on every accepted build. Brief:
`re/sessions/ROUND_2026-11-14_simtropolis.md` (stream `lxpatch`).

## plan
1. Generator `re/tools/lxpatch_gen.py` (Python 3.12, repo only): runs the .ps1 on copies of each stock exe, diffs
   against the input, and rewrites the GENERATED block of the .sh (header byte edits + appended tail as printf octal,
   stock hash, patched hash per build).
2. `re/scripts/sc3mods_patch.sh`: hash / signature normalisation with od+dd, apply by dd+printf, verify result hash,
   same `SC3U.exe.orig` backup rules, `--restore`, idempotent, refuses unknown exes.
3. `.gitignore` line `!/re/scripts/*.sh`, new `.gitattributes` (`*.sh text eol=lf`), release/stage copy of the .sh next to
   the .ps1, README section "Linux and macOS (Wine, Lutris, CrossOver)".
4. Proof in `verify/lxpatch/RESULTS.md` (byte-identical vs .ps1 for 2.0.0.3, 2.0.949, synthetic signed copy; second run
   no-op; --restore; cross-undo .sh <-> .ps1; Git Bash sh; WSL not installed, macOS lines listed as owner check),
   one launch check in `dev\lxpatch\tree`.

## files owned (worktree `dev\lxpatch\wt` unless noted)
- `re/tools/lxpatch_gen.py` (new)
- `re/scripts/sc3mods_patch.sh` (new)
- `.gitignore` (one line), `.gitattributes` (new)
- release assembly script that copies the .ps1 (to be located, probably `re/scripts/lan_release/stage_lan_release.py`)
- `README.md` (one section)
- `verify/lxpatch/RESULTS.md` (main checkout)
- `re/sessions/STATUS_lxpatch.md` (this file)

## state
2026-11-14: DONE, verdict PASS. Nothing committed (orchestrator integrates). Proof: `verify/lxpatch/RESULTS.md`.
Files changed in the worktree: `re/scripts/sc3mods_patch.sh`, `re/tools/lxpatch_gen.py`, `.gitattributes`, `.gitignore`,
`README.md`, `re/scripts/lan_release/stage_lan_release.py`. Needs owner check: macOS lines, a real Linux run (no WSL here).
