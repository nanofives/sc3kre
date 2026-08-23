# TILINGRULES.md — `Apps\Res\TilingRules\*.txt`, the network auto-tiling ruleset

Documented 2026-08-23. Parser/writer: `re/tools/tilingrules.py` (`--selftest` = **68/68
byte-identical round-trip, 68/68 structurally valid**).

68 loose plain-text files. Per network, they declare which tile pieces exist and how pieces
connect. This is the highest-leverage modding surface in the game: no container, no compression,
no repack, editable in Notepad.

## Status: game-verified on both counts

| claim | evidence |
|---|---|
| the files are **read**, from this directory | **T0** — all 48 referenced files opened, every one `-> ok`, at 1,735–1,749 ms during startup. `verify/tilingrules_read_test/RESULTS.md` |
| their **contents are consumed** into engine records | **T1b** — cutting `ROAD_GRND_Set.txt` from 109 ids to 1 moved the per-id append count (`SIMNTWRK 0x1001b456`) from **448 → 340**, the exact −108 predicted in advance, with the per-file control (`0x1001746e`) unmoved at **7** |

Not established: that the resulting records change *rendered* behaviour. That needs the visual
test, blocked on `U-068`.

## Uniformity

All 68 files: **CRLF**, **pure ASCII**, **no tabs**. Measured, not assumed.

One exception to the numeric convention: `networkIntesection.txt` stores **quoted, zero-padded**
numbers in a nested C-style initializer (`{{"0", "00004500", "00004300"}, …}`) — a 3×3 matrix in a
format nothing else uses. It is also referenced by no module. Both facts point to a dev leftover.
Consequence for tooling: a rebuild that re-renders tokens via `str(int(v))` silently rewrites
`00004500` to `4500`. `tilingrules.py` re-emits untouched tokens as their original bytes.

## The four families

`tilingrules.py --selftest` classifies all 68 with no residue:
**RULES 31, COUNTED_PAIRS 15, COUNTED_LIST 13, BRACED 9.**

### BRACED — `*_Set.txt`, `DIAG_Set.txt`, `ROAD_GRND_FinalRules.txt`, `networkIntesection.txt`

```
{29, 31, 32, 35, 39, 43, 63, 64, 67, 69, 81, 82, 83, 87, 88, 1998, 1999,
 9051, 11201, ... 18070}
```

A flat piece-id list. **Braces, commas, and line breaks are noise.**

Witness `FUN_1001746e` `[CONFIRMED]`: `FUN_10017596` reads the whole file into a `0x20000` buffer,
then a `strtok` loop takes each token, skips to its first digit, `atoi`s it, and appends a 12-byte
record `{0xE223741F, 0xA317745F, value}` via `FUN_1001b456`. So *any* integer token is an entry and
punctuation is irrelevant to the game.

Two corrections to earlier notes:

- `sc3_ntwrk_parse_set_line` @ `0x1001746e` is **misnamed**. It is called **once per Set file** —
  7 unrolled call sites in `FUN_10016d87` — and the `strtok` loop is *inside* it. Measured: exactly
  7 hits per run, invariant under file contents.
- The **per-id** append is its callee `FUN_1001b456`, which has **exactly one call site in the
  whole module**, making its hit count a clean per-record counter.

Stock id counts: ROAD 109, HWAY 191, RAIL 38, SUBW 38, PIPE 32, POWR 26, DIAG 14 — **448 total**,
which is exactly the measured append count.

### COUNTED_LIST — `*_Protected.txt`, `*_Bridges.txt`, `Collapse.txt`, `*_Exits.txt`

```
66        <- N
63
64
...
```

Line 1 is `N`; exactly `N` single-integer lines follow. Verified for all 13.

`PIPE_GRND_Bridges.txt` and `SUBW_GRND_Bridges.txt` both declare **0**. That is the data-side
confirmation of the code-side finding that **only 4 of 6 networks can bridge** — `FUN_10017f98`
builds only 4 `*_Bridges.txt` paths, and the two extra files ship empty and unread.

### COUNTED_PAIRS — `*_Convert.txt`, `*_Complex_Convert.txt`

```
184       <- N
17152,7424
17153,7425
...
```

Line 1 is `N`; exactly `N` `from,to` lines follow. A piece-id remap. Verified for all 15.

### RULES — `*_SimpleRules.txt`, `*_ComplexRules.txt`, `*_final.txt`, `*_SlopeRULES.txt`, `Landfill*.txt`

```
0,430              header: 430 rules follow
1,8                selector
2,0                length prefix: 0 condition lines
4,1                length prefix: 1 result line
5,255,2873600      result
1,256              next rule
2,2
3,6,8962           condition
3,255,2867970      condition
4,1
5,255,8962
```

Per rule, in order: one `1,selector`; one `2,C2`; exactly `C2` × `3,dir,val`; one `4,C4`; exactly
`C4` × `5,dir,val`.

**Opcode 2 and opcode 4 are length prefixes.** `opcode2 == len(3-block)` and
`opcode4 == len(5-block)` hold for **100% of all 4,219 rules across all 31 RULES files**. Arity is
fixed: `1`→2 fields, `2`→2, `3`→3, `4`→2, `5`→3. No other opcode occurs.

The declared header count equals the number of `1,` lines in every file.

Token-parser witness: `FUN_10022676` — a 9-state per-token parser building 6-byte
`{u32 id; u8 dir; u8 state}` records via `FUN_100229e8`, with `0xff` mapped to `0x1f`.
**Corrected 2026-08-23:** the nesting is a **`0x10`-byte rule entry** `{u32 selector; vector<Group>}`
holding **`0x18`-byte condition/result groups** `{vector<Rec6> conds; vector<Rec6> results}`
(`FUN_10022a7e` appends the 0x10-byte entries). An earlier draft attached the `0x18` to the rule
entry, which is the wrong level.

## The `val` encoding — 100% accounted for

Reading `val >> 8` as a piece id, `tilingrules.py --crosscheck` accounts for **every one of the
13,040 rule values**:

| net | total | sentinel | own Set | crossed net | unexplained |
|---|---:|---:|---:|---:|---:|
| ROAD | 3,374 | 1,035 | 2,339 | 0 | 0 |
| RAIL | 966 | 8 | 958 | 0 | 0 |
| HWAY | 5,780 | 1,455 | 4,325 | 0 | 0 |
| SUBW | 1,468 | 16 | 1,452 | 0 | 0 |
| POWR | 462 | 48 | 398 | **16** | 0 |
| PIPE | 990 | 8 | 982 | 0 | 0 |
| **total** | **13,040** | **2,570** | **10,454** | **16** | **0** |

- **Sentinels** are `val < 256`, and the only values that ever occur are **`{0, 1, 5}`**.
- Every non-sentinel `val >> 8` is a piece id in the network's **own** `_Set.txt`, with exactly one
  class of exception.
- **The exception is fully explained.** POWR's 16 outliers are 4 pieces × 4 occurrences:
  **29 (Road), 44 (Railroad), 73 (Highway), 15051 (a HWAY piece)** — i.e. power lines crossing
  other networks. The iOS sibling names the corresponding classes `goPowerRoad` and `goPowerRail`
  `[iOS-HINT]`.

A naive check that ignored sentinels scored only 69% on ROAD and 75% on HWAY, which looks like a
broken hypothesis and is not: those two networks simply carry the most sentinel values.

**This is strong support, not a decode.** It shows `val >> 8` behaves like a piece id everywhere.

## All three fields are now DECODED — see `re/analysis/NETWORK_RULE_ENGINE.md` §4

This section previously listed the selector, `dir`, and the low byte as undecoded. The rule
*evaluation* path was traced on 2026-08-23 and all three fell out, each with two independent
witnesses. Summary:

- **`dir` = an index into a 24-entry 5×5-neighbourhood offset table** at `0x10032134`
  (`FUN_1002205c`): 0–3 orthogonal, 4–7 diagonal, 8–23 the distance-2 ring. **`255`/`0x1f` = the
  tile itself, `(0,0)`.** Confirmed by an inverse table at `0x10032118` that inverts it 25/25.
- **the `1,` selector = a 32-bit bitmask of which directions hold a same-network neighbour**
  (`FUN_100222f9`, `FUN_10022092`: `mask |= 1 << dir`), west→bit0, north→bit1, east→bit2,
  south→bit3. **`256`/`0x100` is an unconditional wildcard** and is unreachable as a real mask.
  So `72` = S+SE and `195` = W+N+SE+SW.
- **`val & 0xff` has two disjoint roles.** With `id == 0` it is an occupancy sentinel
  (`5` empty/out-of-bounds, `1` pending, `0` present-but-filtered). With `id != 0` it is a
  **2-bit piece orientation** — measured over every shipped value `>= 256`, it is only ever
  `{0,1,2,3}`. The comparator `FUN_100220c5` matches it byte-exactly, except a rule `state` of `0`
  also accepts an observed `5`, i.e. "empty or absent".

Still open: which *predicate* sets each selector bit beyond the city-edge contributor, and the
geometric facing convention for state `0/1/2/3`. Both in `NETWORK_RULE_ENGINE.md` §10.

### Invariants worth enforcing in any rule editor

Measured across all 4,219 shipped rules, zero exceptions — these follow from the stage each ruleset
is loaded into (mode 4 / 8 / 0x18, `NETWORK_RULE_ENGINE.md` §4.4):

| ruleset | `dir` values allowed | selector |
|---|---|---|
| `*_SimpleRules` | `0..7`, `255` | `0x01..0xff` |
| `*_ComplexRules` | `0..23`, `255` | **`0x100` only** |
| `*_final` | **`255` only** | exactly `0x0..0xf` |

A `*_final` rule referencing a non-centre `dir`, or a `*_SimpleRules` rule using `dir >= 8`, can
never match.
- ~~what `Protected` / `Convert` / `final` / `Collapse` mean semantically~~ — **resolved
  2026-08-23**, `NETWORK_RULE_ENGINE.md`. `Protected` = piece ids the tiler may not replace or
  remove (`FUN_1001a7f7`); `Convert` = 16-byte `{fromId, fromState, toId, toState}` remap records
  (`FUN_1001a85a`); `final` = the third and last rule stage, run once, centre-only. The handler
  vtables are **42** (not ~50) stateless predicate functors.

## Which files matter

Measured at startup, 2026-08-21/23:

- **48 live** — opened every run.
- **7 lazy** — `LandfillRules1..6.txt`, `LandfillStartRule.txt`. Referenced by `SIMRCI`, not
  `SIMNTWRK`; not loaded at startup.
- **13 dead** — referenced by **no module**: the six `*_SlopeRULES.txt`, three `*_Exits.txt`,
  `networkIntesection.txt`, `ROAD_GRND_FinalRules.txt` (distinct from `ROAD_GRND_final.txt`, which
  *is* read), and `PIPE`/`SUBW_GRND_Bridges.txt`.

**Editing a dead file has no effect and looks like a failed experiment.** `tilingrules.py` tags
every file `live` / `lazy` / `DEAD` so this cannot be tripped over twice.

## Known defect: a case-sensitivity landmine

The game requests **`Road_GRND_Protected.txt`** (mixed case). The shipped file is
**`ROAD_GRND_Protected.txt`**. It works only because NTFS is case-insensitive; all five sibling
networks use the consistent upper-case form. On a case-sensitive filesystem that open fails and
road protected-tile rules load empty. Filed as **U-074**.

## Tool

```powershell
python re/tools/tilingrules.py --selftest        # 68/68 round-trip + structural validation
python re/tools/tilingrules.py --crosscheck      # the value accounting table above
python re/tools/tilingrules.py --show FILE
python re/tools/tilingrules.py --dump FILE --json
python re/tools/tilingrules.py --replace-id FILE OLD NEW
python re/tools/tilingrules.py --set-value FILE INDEX NEW
```

Writes preserve the original wrapping, indentation and CRLF: only edited tokens are re-rendered.
Verified — `--replace-id 11225 12345` on `ROAD_GRND_Set.txt` changed exactly 3 bytes at offsets
170–172, left the length at 744, preserved every CRLF, and the result re-parses clean.

**`Apps\Res\` is GAME content.** Back the directory up before editing and verify the restore by
hash, as `verify/tilingrules_read_test/` does.
