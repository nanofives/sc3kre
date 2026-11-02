# RESULTS - sc3mods release 2026-11-02 + LAN republish

Replaces `sc3mods-2026-11-01`. Owner call 2026-11-01: "Publish an sc3mods release now with CHURN". Source as of `5b5de31`.

| what | merge | record |
|---|---|---|
| sc3simrun CHURN: the anarchy redevelopment roll off for R/C/I (`simrun.ini [churn]`, `SC3SIMRUN_CHURN=0`) | 5b5de31 | verify/churn/RESULTS.md |

## Stage and checks

- `stage/bins_1102`: the 10 binaries of `stage/bins_1101` plus `sc3simrun.dll` rebuilt from main `5b5de31`.
- Staged into a NEW folder `stage/release_1102` (label `2026-11-02`, 3,614 files, 706.6 MB): two other sessions' games
  (dev/perfdlg, dev/railgap, trees hard-linked from `stage/release`) were running, and the stage script rmtree's its
  output. Manifest against 11-01: 1 changed (`Apps/sc3simrun.dll`), 0 added, 0 removed.
- Launch check (release_1102 patched, windowed, Moscow, no input, 90 s after unpause): `10 mod(s) loaded`,
  `### CHURN: 3 site(s) armed`, only the benign `0xC0000096 @ SC3U+0x84122`. Then `-Restore`, the 11 logs and the two
  first-start ini files deleted, manifest re-hashed: 0 changed, 0 missing, 0 extra.

LAN: deployed from `stage/release_1102`, 1 of 3,614 files sent (0.1 MB). Served label `2026-11-02`, served
`Apps/sc3simrun.dll` SHA-256 matches.

Zip: the 2026-11-01 zip (downloaded from its GitHub release, 50,266,703 bytes as recorded) with `Apps/sc3simrun.dll`
replaced and README.txt updated (header, sc3simrun line, NEW IN 2026-11-02, `[churn]` under OPTIONS). 134 entries,
133 checked against the staged manifest, 0 mismatches, sc3mods_patch.ps1 equal to the stage copy.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/sc3simrun.dll | 122880 | E5770121180B308C448AECBA4C8BEF3F18CBD07CAAFC98ABAD92021D08620F22 |
| other 10 binaries | | unchanged, see verify/mods_release_1101/RESULTS.md |
| `sc3mods_2026-11-02.zip` | 50,491,116 | 86EF0CF2F438B6E9E715478807E85D3CBFAA7DE7E8AA0DC1D52884981255D74A |

Owner checks: a built-up city over a few game years, working buildings no longer rebuilt as the same thing, upgrades
still happening.

GitHub: `sc3mods-2026-11-02`, target `13f1978`, https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-11-02, asset
downloaded back, SHA-256 matches. The 11-01 notes now start with a "superseded" line.
After publishing, `stage/release` was renamed to `stage/release_1101_old` and `stage/release_1102` to `stage/release`
(label `2026-11-02`). `release_1101_old` is left for removal once no dev tree game holds its files.
