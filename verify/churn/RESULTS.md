# RESULTS - churn: sc3simrun CHURN (anarchy redevelopment off), 2026-11-01

Owner question: why do working buildings keep getting rebuilt while there is demand. Analysis:
`re/analysis/ZONE_REDEVELOPMENT.md`. Owner call 2026-11-01: merge and ship in the next sc3mods release.

## What shipped

sc3simrun CHURN block. `simrun.ini [churn]`: `anarchy_res|com|ind` default 0, `upgrade_X` / `density_X` default -1
(the game's SC3Tune.INI value), `enabled=1`. `SC3SIMRUN_CHURN=0` = stock. Each enabled roll's `cmp eax, [abs32]`
operand is repointed at the mod's DWORD after a byte check (SIMRCI `0x10029503 / 0x1001033b / 0x100187cb` for
anarchy). Log: `CHURN> anarchy_res = 0 ...`, `### CHURN: 3 site(s) armed`.

## Runs (Moscow, windowed, dev/churn tree, speed 3, 120 s, re/tools/churn_probe.py)

| successful develops | stock, 179 game days | CHURN default, 180 game days |
|---|---|---|
| res same-class (anarchy) | 343 | **0** |
| res upgrade | 170 | 130 |
| res new lot | 119 | 96 |
| com same-class (anarchy) | 133 | **0** |
| com upgrade | 394 | 145 |
| com new lot | 154 | 16 |
| ind | not hooked | 0 same, 8 upgrade, 4 new |

Raw probe JSON is gitignored (the stock run used the build before the CHURN block). Separate games, so only the
anarchy rows are a controlled comparison. Zone layer ticks = game days in both runs, 2,184 tiles per tick.
No crash in either run. Not hand-tested by the owner.
