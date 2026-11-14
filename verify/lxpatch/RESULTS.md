# lxpatch: sc3mods_patch.sh for Linux / macOS (2026-11-14)

Player report (Simtropolis): runs the mods under Wine (Lutris, GOG build), patched SC3U.exe on a Windows PC because the
patch is PowerShell. Asked for a tool-agnostic patch.

## What was built (worktree dev\lxpatch\wt, branch child/lxpatch, nothing committed)

- `re/scripts/sc3mods_patch.sh`: POSIX sh. Tools: sh, dd, od, wc, cp, mv, rm, cut, tr, sed, grep, printf, sha256sum or
  shasum -a 256. No Python, PowerShell, xxd, `stat -c`, `head -c`, `sed -i`, `truncate`.
- `re/tools/lxpatch_gen.py`: runs the real `.ps1` on copies of each stock exe, diffs the result and writes the
  GENERATED block of the `.sh` (header byte ranges + appended tail as printf octal, stock and patched SHA-256).
  `--check` exits 1 when the block is stale (it is current: rc 0).
- Behaviour copied from the `.ps1`: same builds (2.0.0.3 `49DD55E1...`, 2.0.949 `42E30CE0...`), signed copy recognised by
  the same normalisation (cut at the security directory, security dir + checksum zeroed), already-patched detection
  by the `.sc3mod` section, same `SC3U.exe.orig` backup name/location and replace-on-other-build rule, `--restore`,
  unknown exe refused with a report and nothing changed. The patched file is hashed against the generator's expected
  SHA-256 before it replaces the exe.
- Not copied: the "game is running" check (no portable equivalent; README says close the game), the `-DllName` option.
- Ship: `stage_lan_release.py` copies the `.sh` next to the `.ps1` (LF forced), `.gitignore` gets `!/re/scripts/*.sh` and
  `!/.gitattributes`, new `.gitattributes` (`*.sh text eol=lf`), README section "Linux and macOS (Wine, Lutris, CrossOver)".

## Proof (copies in a scratch folder, originals untouched; Git Bash `sh`, `.ps1` under pwsh 7)

Inputs: `original\SC3U.exe` (2.0.0.3), `original\gog_2.0.949\Apps\SC3U.exe` (2.0.949), synthetic signed copy of 2.0.949
(6,008-byte certificate appended, security dir + checksum set, as in verify/steamsig).

| check | 2.0.0.3 | 2.0.949 | 2.0.949 signed copy |
|---|---|---|---|
| `.sh` output byte-identical to `.ps1` output (cmp + SHA-256) | PASS `e5b6330c...` | PASS `85be3349...` | PASS `85be3349...` |
| backup `SC3U.exe.orig` equals the input | PASS | PASS | PASS (keeps the signed file) |
| second `.sh` run: exit 0, exe unchanged, "already imports" | PASS | PASS | PASS |
| `.sh --restore` returns the input bytes, backup removed | PASS | PASS | PASS |
| `.ps1` patch, then `.sh --restore` | PASS | PASS | PASS |
| `.sh` patch, then `.ps1 -Restore` | PASS | PASS | PASS |
| `.sh` reports a `.ps1`-patched exe as already patched | PASS | PASS | PASS |

Unknown exe (one byte changed in .text): exit 1, report printed (size, timestamp, checksum, security dir, normalised
hash, sections), exe unchanged: PASS.

Also run under `dash` (strictest sh available here): patch of 2.0.0.3 and of the signed copy gives the same hashes, and
`--restore` returns the input: PASS.

## Launch check (one launch)

Tree `dev\lxpatch\tree\Apps\SC3U.exe` deleted (it was hard-linked), stock 2.0.0.3 copied in, patched with the `.sh`
(SHA-256 `e5b6330c...`), `sc3dev.ps1 run lxpatch`. `dev\lxpatch\inst\sc3mods.log`: "mod-load start ... (static import,
process init)", all 11 mods loaded, "11 mod(s) loaded". PID 10112 stopped by PID, harness claim released.

## Real Linux run (orchestrator, 2026-11-14)

Debian 13 x86_64 (`mariano-server`, kernel 6.12.116, `/bin/sh` -> `/usr/bin/dash`, GNU coreutils), copies of both stock
exes in a temp folder (deleted after), `sh sc3mods_patch.sh` from that folder:

| check | 2.0.0.3 | 2.0.949 |
|---|---|---|
| patch: rc 0, new SHA-256 | `e5b6330c46e3a3c8...` (= `.ps1` output) | `85be3349f976905f...` (= `.ps1` output) |
| second run: rc 0, exe unchanged | PASS | PASS |
| `--restore`: rc 0, stock hash back, `.orig` removed | `49dd55e183c68dff...` PASS | `42e30ce0e3188c4b...` PASS |

The missing-`sc3mods.dll` warning printed as designed (only the exe was copied). Signed copy not run there.

## Not run (needs owner check)

- WSL is not installed, so Git Bash / dash only on this PC. A real Linux userland was covered on the server (above).
- No macOS. Lines that differ there and were not run: the `shasum -a 256` branch of `sha256()`, BSD `od -An -tu1 -j -N`
  and `od -tx1`, BSD `dd` with `bs=<N> count=1` for the signature cut, BSD `wc -c` padding (stripped with `tr`),
  `grep -aq -e A -e B` on `version.dll`. Each is POSIX or documented BSD behaviour but unproven here.
- Real Steam exe (same open item as verify/steamsig); the ARM / big-endian hosts (`od -tu1` is used so endianness
  does not matter).
- The "release zip": only the LAN stage script was found that copies the `.ps1`; if the GitHub zip is assembled by hand,
  add `sc3mods_patch.sh` there with LF endings.
