# NETWORK_RULE_ENGINE.md — how SC3K evaluates network tiling rules

Traced 2026-08-23. SIMNTWRK.DLL, image base `0x10000000`. Closes `SIMNTWRK.md` §7 open item 7
("the rule *evaluation* path was never traced").

Companion documents: `re/analysis/formats/TILINGRULES.md` (the file format),
`re/analysis/NETWORK_TYPES.md` (the netType enum), `re/tools/tilingrules.py` (parser/writer).

**All three previously undecoded rule fields are now decoded**, each with two independent witnesses:
the `dir` field, the `1,` selector, and the `state` byte. See §4.

## 1. The pipeline

```
[other module] --vtable +0xac / +0xb0 / +0xf0 on GZCLSID 0x2171c021-->
      FUN_1000abde        FUN_100151f1              FUN_10014a23
      (not read)          rect invalidate/retile    drag/build commit
                                   \                    /
                                    FUN_10016a25  (gather tiles in bbox by predicate)
                                            |
                                    FUN_1001547b   sc3_ntwrk_apply_tiling_rules
                                            |
        +---------------------+--------------+------------------+
   32x32 occupancy mask   pre-filter    drag commit      THREE RULE STAGES
   + 8-connected flood    FUN_100167d4  FUN_1001a2c0    FUN_10016327 x3
     fill (<=32 iters)    FUN_1001a7f7  + FUN_100165d8
```

`FUN_1001547b` is **internal** — it has no vtable pointer and three in-module callers, all of which
*are* vtable slots of the `0x2171c021` class (vtable base `0x1002c7bc`). So evaluation is always
entered cross-module. `[UNCERTAIN]` which module/UI action drives each of `+0xac`/`+0xb0`/`+0xf0`;
that needs an xref sweep outside SIMNTWRK.

### Entry points

| slot | function | role |
|---|---|---|
| `+0xb0` | `FUN_100151f1` | **rectangle invalidate / retile.** `(this, bbox6, netMask)`. Early-outs on the `0x7fffffff` sentinel, then per bit of `netMask`: `bit0\|bit1`→HIGHWAY then ROAD, `bit2`→RAIL, `bit5`→POWER, `bit3`→PIPE, `bit4`→SUBWAY. The shape expected for city load and post-bulldoze refresh. |
| `+0xf0` | `FUN_10014a23` | **drag/build.** Funds check, then bridge path (netType 1–4 only, path length > 3) or normal path. For HIGHWAY it runs a **second** `FUN_1001547b` pass with netType 1 — highways retile the roads they touch. |
| `+0xac` | `FUN_1000abde` | reaches `FUN_1001547b`; not read. `[UNCERTAIN]` |

### Phase 1 — occupancy mask and the "dilation pass"

Scan radius `r = 5` for netType 1, 4, 6 (ROAD, HIGHWAY, SUBWAY), else `r = 2`. Per node, scan
`[x-r, x+r) × [y-r, y+r)`, bounds-checked against the map object's `+0xcc` (width) / `+0xd0`
(height).

The bit table is 32 dwords `1u << k` at `0x10031340`–`0x100313bf`; **`DAT_10031380` is element 16,
the centre** — so the previously recorded "32x32 adjacency bitmask via DAT_10031380" is an index
into the middle of a larger table, not the table's base.

A cell's occupancy bit is set if it is in the caller's node list (`FUN_100162f5`, comparing both
coords masked `0xffffff00`, i.e. integer-tile equality) **or** the layer returns an occupant
(`+0x78`) that satisfies predicate A.

Then a fixpoint loop, hard-capped at **32 iterations**: horizontal
`w[i] = (w[i]>>1 | w[i]<<1 | w[i]) & occ[i]`, then vertical
`w[i+1] = (w[i] | w[i+1] | w[i+2]) & occ[i+1]`. This is an **8-connected flood fill outward from
the origin tile, clipped to a 32×32 window** — that is what the "dilation pass" in earlier notes
actually is.

### Phase 4 — three stages, in this order

```
1. Simple  (DAT_10032318+)  mode 8     run to FIXPOINT      (repeat while list size changes)
2. Complex (DAT_10032330+)  mode 0x18  at most 5 passes
3. final   (DAT_10032300+)  mode 4     exactly once
```
`[CONFIRMED @ 0x1001547b:565, 581, 597]`

**This corrects the container→file binding, which is not in address order:**

| containers | ruleset |
|---|---|
| `DAT_10032300..0x10032314` | `*_final.txt` |
| `DAT_10032318..0x1003232c` | `*_SimpleRules` |
| `DAT_10032330..0x10032344` | `*_ComplexRules` |

The "mode" number is literally the **exclusive upper bound on the `dir` index** the collector may
report (§4.1). It is a mode, not a limit — 4, 8, 0x18.

## 2. Per-tile evaluation — `FUN_10016327`

Per node in the work list:

1. **Flatness guard** — `FUN_10016ccd` requires all four terrain corner heights equal. **Nodes on
   slopes are skipped entirely.** (`FUN_10016d00` is the looser sibling: two opposite pairs equal
   and `|diff| <= 2`, i.e. a legal single-axis slope.)
2. **Collect** — `FUN_10019768` builds the observed neighbourhood: `{u32 dirMask; vector<Rec6>}`
   (`FUN_10022186` zeroes 4 dwords). Mode `0x18` walks the full 5×5 box and never touches
   `dirMask`; modes 4/8 walk 3×3 and set `dirMask |= 1<<dir` via `FUN_10022092`, but only when
   `(dir & 0xff) < mode`. Map edges also contribute: `x==0`→bit 3, `x==w-2`→bit 1, `y==0`→bit 0,
   `y==h-2`→bit 2, so **the city boundary can act as a neighbour**.
3. **Match** — `FUN_100228ff` steps rule-set pointers, then rules at **stride 0x10**, calling
   `FUN_100222f9` until one returns non-zero. **First match wins; there is no scoring.**
4. **Count** — `FUN_1002217a` = `(end - begin) / 6`, the result record count. Zero → skip.
5. **Validate** — per result record: decode `dir`, form the target coord, require in-bounds
   (`layer+0x68`) and flat (`FUN_10016ccd`), fetch the occupant, get its piece id
   (`FUN_1001a93d`, via IID `0x41658d28` slot `+0x30`), and **reject the whole rule** if
   `(!predA && !predC)`, or if the target is Protected (`FUN_1001a7f7`) — except for the
   "clear an empty cell" case `id==0 && state==5`. Bails on first failure.
   **netType 3 (POWER) is exempted from the Protected check here.**
6. **Commit** — `FUN_100165d8`, then `FUN_1000d4cf()` if `this+0x68 != 0`.
7. **Requeue** — each target coord goes to the changed-list, except `id==0 && state==0` records,
   which go to a deferred list.

## 3. Commit — `FUN_100165d8`

Per 6-byte record `{u32 id; u8 dir; u8 state}`:

- `id == 0` → **removal.** Fetch occupant, check `+0x74` (removable), then `layer+0x48`.
- `id != 0` → **creation.** `this->vtable[0x48](&obj, GZCLSID 0xc14f8955, id, state)` — the piece id
  and the state byte are the **two constructor arguments**. Read ground height, set position via
  `obj->vtable[0xec]`, insert with `layer->vtable[0x3c]`. If insertion fails and `predB || predC`
  and the incumbent is removable, remove it and retry.
- On success, when the network is ROAD / RAIL / HIGHWAY only: `this->[0x34]->vtable[0x3c](x, y,
  &state)` — a per-tile side-table write.

Coordinates are **24.8 fixed point** (`<<8`).

`[UNCERTAIN]` the identity of GZCLSID `0xc14f8955`, the network-piece class. Not in SIMNTWRK.

## 4. The three decoded fields

### 4.1 `dir` — a 5×5 neighbourhood index. `255` = the tile itself.

`FUN_1002205c` is a pure lookup, **no special-casing and no bounds check**:

```c
*dx = (&DAT_10032134)[dir*2];
*dy = (&DAT_10032135)[dir*2];
```

Table at **`0x10032134`**, 32 slots of `{int8 dx, int8 dy}`, dumped from the anchored DLL:

| dir | (dx,dy) | dir | (dx,dy) | dir | (dx,dy) | dir | (dx,dy) |
|---:|---|---:|---|---:|---|---:|---|
|0|(-1, 0) W|6|(+1,+1) SE|12|( 0,-2)|18|(+2,+2)|
|1|( 0,-1) N|7|(-1,+1) SW|13|(+1,-2)|19|(+1,+2)|
|2|(+1, 0) E|8|(-2, 0)|14|(+2,-2)|20|( 0,+2)|
|3|( 0,+1) S|9|(-2,-1)|15|(+2,-1)|21|(-1,+2)|
|4|(-1,-1) NW|10|(-2,-2)|16|(+2, 0)|22|(-2,+2)|
|5|(+1,-1) NE|11|(-1,-2)|17|(+2,+1)|23|(-2,+1)|
|**0x1f (=255)**|**( 0, 0) — the tile itself**|24..30|(0,0) pad| | | | |

**24 = a 5×5 neighbourhood minus its centre.** 0–3 orthogonal, 4–7 diagonal, 8–23 the 16-cell
Chebyshev-distance-2 ring walked from `(-2,0)`. The table is padded to 32 so a 5-bit index is
always in range, and the parser's `0xff → 0x1f` remap lands on `(0,0)`.

Three confirmations:

1. **An inverse table.** `FUN_1002203e` is `dir = DAT_10032118[(dx+2)*5 + (dy+2)]`, a 25-entry
   reverse lookup that inverts the forward table **cell for cell, 25/25**, with the centre holding
   `0x1f`.
2. **Consumers** decode via `FUN_1002205c` and form `((x>>8)+dx)*0x100` in both `FUN_10016327` and
   `FUN_100165d8`.
3. **The data agrees with zero exceptions.** Measured over the shipped files with
   `tilingrules.py`: `dir` takes exactly `0..23` plus `255`, and the per-family ranges match the
   stage modes (§4.4).

This was predicted from the data before the table was read: the field's 24 distinct values and its
frequency tiers (0–3 most used, 4–7 middle, 8–23 rare in four groups of four) implied the 5×5
model, and the table confirmed it exactly.

**Do not conflate this with the slope path.** `FUN_1001a1f3` is *not* a neighbour signature: it
reads the four **terrain corner heights** of one tile and emits `{0, h1-h0, h2-h0, h3-h0}`, matched
against 8 rows of `DAT_1003193c` = `[0,-1,-1,0] [0,0,-1,-1] [0,1,1,0] [0,0,1,1]` and the same at
magnitude 2. Four slope directions × two magnitudes. So `FUN_1001a2c0`, currently named
`sc3_ntwrk_lookup_tile_rule`, is a **slope → sloped-piece** lookup and should be renamed.

### 4.2 The `1,` selector — a bitmask of which directions have a neighbour. `0x100` = wildcard.

`FUN_100222f9`: `if (selector == 0x100 || selector == observed.dirMask) { evaluate }` — exact
equality, with `0x100` as an unconditional pass.

`dirMask` is written **only** by `FUN_10022092`: `*(uint*)this |= param_2 << (dir & 0x1f)`, always
with `param_2 == 1`. So it is one bit per `dir` index, masked to 5 bits. Bit assignment is pinned
by the city-edge block: **west→bit0, north→bit1, east→bit2, south→bit3**, matching dirs 0/1/2/3.

Because the bit is only set when `dir < mode` and `mode <= 0x18`, **bit 8 can never be set in a
real mask**, so `0x100` is unreachable as data and functions purely as "match any neighbourhood".

Values that `TILINGRULES.md` listed as unexplained now read directly: `0` = no flagged direction,
`1` = W, `2` = N, `4` = E, `8` = S, `72` = `0x48` = S+SE, `195` = `0xC3` = W+N+SE+SW.

`[UNCERTAIN]` *which predicate* sets a bit is fully identified only for the city-edge contributor;
the other call sites are gated on a `0x41658d28`-interface query whose class is unidentified. This
affects the semantic label per bit, not the encoding.

### 4.3 The `state` byte (`val & 0xff`) — two disjoint roles, selected by `id`

Comparator `FUN_100220c5`:

```c
if (rule.dir == obs.dir && rule.id == obs.id)
    if (rule.state == obs.state || (rule.state == 0 && (obs.state == 0 || obs.state == 5)))
        return 1;
```

Byte-exact, with one relaxation: a rule `state` of `0` also accepts an observed `5`, so a rule
written as `0` means **"empty or absent"**.

**Role A, `id == 0` — an occupancy sentinel.** Written by `FUN_10019768` / `FUN_1001a056`:

| state | meaning |
|---:|---|
| `5` | out of city bounds, or no occupant, or occupant carries flag `0x400` |
| `1` | as above **and** the tile is in the caller's pending list |
| `0` | occupant present but rejected by the class filter, lacking flag `0x400` |

**Role B, `id != 0` — a 2-bit piece orientation/variant.** Measured over every shipped rule value
`>= 256`: `state` is **only ever `{0,1,2,3}`** (counts 8428 / 3475 / 6181 / 3138), never anything
else. Three code witnesses:

1. It is a **construction argument**: `factory(0xc14f8955, id, state)`, fed by `FUN_1002207c` =
   `{v>>8, (char)v}`.
2. It alone distinguishes **four orientations of one piece**: slope table `DAT_100319dc` rows 0–3
   are `11262/0, 11262/1, 11262/2, 11262/3` and rows 4–7 are `11263/0..3`.
3. It **flips when a crossing's two networks swap roles**: the 6×6 crossing matrix `DAT_100318ac`
   is symmetric in `id` and antisymmetric in `state` — `69/0`↔`69/1`, `11258/2`↔`11258/0`, etc.

The state is also a first-class field in the **Convert tables**: `FUN_1001a85a` scans 16-byte
records `{fromId, fromState, toId, toState}`, which is why a shipped pair like `17152,7424` reads as
id 67 state 0 → id 29 state 0.

`[UNCERTAIN]` the geometric convention — which of `0/1/2/3` is which facing. Settling it needs the
class behind occupant `vtable[0xa0]`/`+0x1c`, or a rendered A/B (place one piece, flip only the
state byte, observe rotation) — which is blocked on `U-068`.

### 4.4 The mode ↔ ruleset binding, and a free consistency check

| pass | ruleset | mode | dirs usable | measured dirs in shipped files | measured selectors |
|---|---|---:|---|---|---|
| 1 | `*_SimpleRules` | 8 | 0..7 | `{0..7, 255}` | 214 distinct, `0x01..0xff` |
| 2 | `*_ComplexRules` | 0x18 | 0..23 | `{0..23, 255}` | **`0x100` only** |
| 3 | `*_final` | 4 | 0..3 | **`{255}` only** | exactly `0x0..0xf`, all 16 |

Zero exceptions across 4,219 rules. `*_final` is **centre-only**; `*_ComplexRules` declines to use a
mask at all despite its mode allowing 24 bits. Both are useful invariants for a rule editor.

Also measured: `Landfill*` (loaded by SIMRCI, not SIMNTWRK) uses selector `0x100` only with dirs
`{0..7, 255}`. The six **dead** `*_SlopeRULES` use selectors `{5,10,20,40,80,160}` with dirs
`{0..3,255}` — bits 0..7 set, which no mode-4 stage could ever match. Consistent with them being
abandoned.

## 5. The 42 predicate handlers

Not "~50": **exactly 42**, `DAT_100323c0..0x10032464`, vtables `0x1002c414..0x1002c748` step `0x14`.
The block ends flush against the next class's vtable at `0x1002c75c`, so 42 × 5 slots is a hard
bound.

They are **stateless GZCOM predicate functors**, IID `0xA1C085DB`. Interface is 5 slots; four are
byte-identical across all 42 (`QueryInterface`, `AddRef`, `Release`, deleting dtor) and **only
`+0xc` differs** — a hand-written `bool Test(subject)` with its constants as immediates. The engine
calls only `+0xc`. `FUN_1001a98b` is 13 bytes: `{vtable*, refcount}`, **no data field**, so
behaviour cannot be parameterised. The ABI confirms it: `this` in ECX is discarded, the stack
argument becomes the vcall receiver, `ret 4`.

`FUN_1001547b` loads a **triple** per netType — positive predicate, negation, crossing:

| netType | layer | positive | negation | crossing |
|---|---|---|---|---|
| 1 ROAD | `+0x3c` | `…3c0` | `…3e4` | `…400` |
| 2 RAIL | `+0x3c` | `…3c8` | `…3ec` | `…404` |
| 3 POWER | `+0x3c` | `…3d4` | `…3f8` | `…408` |
| 4 HIGHWAY | `+0x3c` | `…3c4` | `…3e8` | `…40c` |
| 5 PIPE | `+0x40` | `…3d0` | `…3f4` | **`…3e0` (generic)** |
| 6 SUBWAY | `+0x44` | `…3cc` | `…3f0` | **`…3e0` (generic)** |

**Only ROAD/RAIL/POWER/HIGHWAY get a real crossing predicate.** Those are exactly the four networks
with a `*_Bridges.txt`, which was established independently from the loader building only 4 paths
and from the two extra files shipping with `0` entries. Three routes, one conclusion.

### The network flag bits, which self-check

| bit | meaning |
|---|---|
| `0x800` | surface network present |
| `0x8000` / `0x10000` / `0x20000` | road / highway / rail |
| `0x40000` / `0x400000` / `0x800000` | subway / power / pipe |

Each network has three independent encodings (is-X mask, NOT-X mask, crossing-bit) and **all three
agree on all six bits**. `0x800` is absent from exactly PIPE and SUBWAY — the two underground
networks — reproducing the `+0x40`/`+0x44` sub-layer split derived separately in
`NETWORK_TYPES.md` §1.

`[UNCERTAIN]` bits `0x400` and `0x4000`. `0x400` acts as an unconditional accept shortcut. Needs
the class implementing subject `[0x3c]`/`[0x48]`.

## 6. `FUN_1001a7f7` is a PROTECTED test, not an allowed-piece test

`FUN_1001a7f7(netType, pieceId)` linear-scans a per-net int vector and returns 1 on membership.

**It does not scan the `_Set.txt` list.** The Set files load into a different set of vectors,
`DAT_10032348..0x10032360` (7 targets, matching the 7 `_Set.txt` paths including `DIAG_Set.txt`).
`DAT_10032394..a8` are filled by `FUN_100196ce`, the COUNTED_LIST parser, called **11 times** — and
11 is exactly `Collapse.txt` + 6 `*_Protected.txt` + 4 live `*_Bridges.txt`.

So **`Protected` means "this piece id may not be replaced or removed by the tiler"**, and
`NETWORK_TYPES.md` §5's row is right about the vectors but wrong about the source file family.

`[UNCERTAIN]` which `*_Protected.txt` maps to which netType. Load order gives ROAD, HWAY, RAIL,
SUBW, POWR, PIPE, but the decompiler dropped the path→slot association in a reordered block. A
**T1b-style differential would settle it cheaply**: truncate one `*_Protected.txt` and count
appends, exactly as `verify/tilingrules_read_test/` did for the Set list.

## 7. Consequences for the original question

A 7th network needs, on top of the four edits in `NETWORK_TYPES.md` §2:

5. **three new predicate functions** (positive, negation, crossing) plus a **43rd vtable** — and the
   `.rdata` vtable block is contiguous with the next class's, so **there is no slack to extend it in
   place**.

For *modding an existing* network, the engine is now understood well enough to author rules
deliberately rather than by imitation: the neighbourhood model, the selector, the state byte, the
three-stage order, first-match-wins, and the flatness and Protected gates are all documented above.

## 8. Two defects found while tracing

- **Double free.** `FUN_10013771:114-115` calls `free()` on the **global singleton handler** when
  QueryInterface fails; shutdown (`FUN_100119e0`) then frees it again. Reachable with any iid
  outside `{1, 0xA1C085DB}`.
- **Dead predicate.** `DAT_100323fc` (NOT-any-surface) is allocated and freed but **never read** —
  exhaustive raw-grep negative over all 1,353 bodies.

## 9. Corrections this trace lands

1. "~50 handler objects" → **exactly 42**. They are predicate functors, not per-rule-case
   dispatchers (`SIMNTWRK.md` §3.1, §4; `NETWORK_TYPES.md` §2).
2. Container→file binding is **not** in address order (§1).
3. `DAT_10031380` is **element 16** of a 32-dword table at `0x10031340`, not a table base.
4. `FUN_1001a7f7` tests **Protected**, not the Set list (§6).
5. `FUN_1001a2c0` / `FUN_1001a1f3` are a **terrain-slope** path; the current name
   `sc3_ntwrk_lookup_tile_rule` is misleading (§4.1).
6. The parser builds **`0x10`-byte rule entries** holding a vector of **`0x18`-byte
   condition/result groups** — `TILINGRULES.md` had the `0x18` attached to the wrong level.
7. All three fields `TILINGRULES.md` listed as "deliberately NOT decoded" are decoded (§4).

## 10. Remaining gaps

- `[UNCERTAIN]` cross-module callers of vtable `+0xac` / `+0xb0` / `+0xf0` — which UI action drives
  which entry.
- `[UNCERTAIN]` GZCLSID `0xc14f8955`, the network-piece class (outside SIMNTWRK).
- `[UNCERTAIN]` the class behind IID `0x41658d28` and occupant `vtable[0xa0]`/`+0x1c` — needed for
  flag bits `0x400`/`0x4000` and for the state-byte facing convention.
- `[UNCERTAIN]` `*_Protected.txt` → netType binding (§6), settleable by differential.
- Not read: `FUN_1000abde`, `FUN_100167d4`, `FUN_1001a2c0`, `FUN_1001a056` bodies (call edges only).

Confidence: **C2** for the structural trace; **C3** for the `dir` decode (forward and inverse tables
agree 25/25) and the selector decode (code plus 4,219 shipped rules, zero exceptions).
