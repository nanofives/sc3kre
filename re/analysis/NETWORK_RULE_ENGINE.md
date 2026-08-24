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
- `id != 0` → **creation.** `this->vtable[0x48](&obj, GZIID_cISC3Occupant 0xc14f8955, id, state)`
  — ⚠️ **CORRECTED 2026-08-24: `0xc14f8955` is an INTERFACE id, not a GZCLSID.** See §11. The piece id
  and the state byte are the **two constructor arguments**. Read ground height, set position via
  `obj->vtable[0xec]`, insert with `layer->vtable[0x3c]`. If insertion fails and `predB || predC`
  and the incumbent is removable, remove it and retry.
- On success, when the network is ROAD / RAIL / HIGHWAY only: `this->[0x34]->vtable[0x3c](x, y,
  &state)` — a per-tile side-table write.

Coordinates are **24.8 fixed point** (`<<8`).

~~`[UNCERTAIN]` the identity of GZCLSID `0xc14f8955`, the network-piece class. Not in SIMNTWRK.~~
**BOTH CLAUSES WRONG — corrected 2026-08-24, see §11.** `0xc14f8955` is `GZIID_cISC3Occupant`, an
interface id (and `GZCOM_INTERFACE_CATALOGUE.md` §27c had already said so on 2026-08-18, which this
file was never updated to match). The piece classes **are** in SIMNTWRK, built by the 22-case factory
`FUN_1000bdcd`.

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
- ~~`[UNCERTAIN]` GZCLSID `0xc14f8955`, the network-piece class (outside SIMNTWRK).~~ **CLOSED §11.**
- ~~`[UNCERTAIN]` the class behind IID `0x41658d28`~~ **CLOSED §11:** `0x41658d28` is the piece
  object's **primary** interface at offset 0 (QI `FUN_1000cdac`), implemented by the 22 classes
  `FUN_1000bdcd` builds. `cISC3Occupant` is a subobject at `this+4`. Still open: the `+0x18` flag
  bits `0x400`/`0x4000` semantics, and the facing convention (narrowed, §11.4).
- ~~`[UNCERTAIN]` `*_Protected.txt` → netType binding (§6), settleable by differential.~~ **CLOSED
  statically 2026-08-24 at C3, no run spent — `NETWORK_TYPES.md` §9.**
- Not read: `FUN_1000abde`, `FUN_100167d4`, `FUN_1001a2c0`, `FUN_1001a056` bodies (call edges only).

Confidence: **C2** for the structural trace; **C3** for the `dir` decode (forward and inverse tables
agree 25/25) and the selector decode (code plus 4,219 shipped rules, zero exceptions).

---

## 11. ⭐ U-076 CLOSED (2026-08-24) — the piece factory is in SIMNTWRK, and `0xc14f8955` was never a class id

### 11.1 The correction, and how the error propagated

**`0xc14f8955` is `GZIID_cISC3Occupant`, an INTERFACE id.** `vtable[0x48](&obj, 0xc14f8955, id, state)`
is not `CreateInstance(clsid, …)`; the second argument is the *requested interface*.

The two conclusions built on the misread — "the class is not in SIMNTWRK" and "absent from SIMDIRT"
(`U-066`) — are artifacts of it. There is no registrar for `0xc14f8955` anywhere because a class id is
not what it is.

> **This was already known and this file contradicted it.**
> `GZCOM_INTERFACE_CATALOGUE.md` §27c named `GZIID_cISC3Occupant = 0xc14f8955` on **2026-08-18**.
> `U-076` was filed on 2026-08-23 from this file's stale label, so an uncertainty was opened against a
> question the project had already answered. **Two docs disagreed and the tracker followed the wrong
> one.** When a doc labels a bare constant, grep the catalogue before filing.

The distinguishing test is cheap and is the method note worth keeping: the dword `55 89 4f c1` occurs
**67 times, all of them in `.text`, in no `.rdata` table**, and eleven of those sites are
byte-identical 44–52 byte **QueryInterface** bodies, one per module —

`SIMNTWRK 0x10023852`, `SIMGEOM 0x1001ca50`, `SIMSERV 0x10014bd0`, `SIMUTIL 0x10019670`,
`SIMDSTR 0x1002dc65`, `SIMECO 0x10014838`, `SIMRCI 0x1003d154`, `SIMMISC 0x100356b2`,
`SimTransit 0x10015ac0`, `SIMSPR 0x1001bbae`, `STRTSIM 0x10016051`

```c
if ((param_1 == 1) || (param_1 == 0x58d) || (param_1 == -0x7e3f3484) || (param_1 == -0x3eb076ab))
```

`-0x3eb076ab` = `0xc14f8955`. `[CONFIRMED @ 0x10023852, SIMNTWRK.DLL]`

**A QueryInterface body is what an interface id looks like and what a class id never looks like.**
Whenever a "GZCLSID" is only ever seen as an argument and never in a `.rdata` table, check for an iid
first.

### 11.2 The real factory: `FUN_1000bdcd`, 22 kinds, in SIMNTWRK

`FUN_100165d8`'s `this` has vtable **`0x1002c7bc`**, pinned by three slot hits each unique in the
image: `+0x48` = `0x1001363a`, `+0x11c` = `0x1001a719`, `+0x130` = `0x1001a7d2` (the last two being
two of the six per-network membership predicates `FUN_1001a5f2` calls at `+0x11c`…`+0x130`).

Slot `+0x48` = **`FUN_1001363a`** `[CONFIRMED @ 0x1001363a, SIMNTWRK.DLL]`:

```c
kind = FUN_1001a5f2(this, id);           // classify piece id -> 1..0xf
FUN_1000bdcd(kind, 0x41658d28, &piece);  // <-- the factory; 0x41658d28 is the PRIMARY interface
piece->vt[0x10](id, state);              // <-- the two construction arguments
piece->vt[0x00](0xc14f8955, ppOut);      // <-- QI to cISC3Occupant, returned to the caller
```

The argument order is itself the proof: `0xc14f8955` reaches `vt[0x00]`, QueryInterface. The value
handed to the factory is `0x41658d28`.

**`FUN_1000bdcd` @ `0x1000bdcd` (1239 bytes) is the registrar** `[CONFIRMED @ 0x1000bdcd]` — a
`switch` on `(kind & 0xff) - 1` with **22 cases**, each `operator new(0x20)` (`0x1c` for kinds 9, 10
and 19), a base ctor (`FUN_1000d2da` / `FUN_1000d0fc`), then two vtable stores `*this = vt1`,
`this[1] = vt2`:

| kind | size | vt1 (primary, `0x41658d28`) | vt2 (`cISC3Occupant` at `this+4`) |
|---:|---:|---|---|
| 1 | 0x20 | `0x1002b724` | `0x1002b5dc` |
| 2 | 0x20 | `0x1002b3cc` | `0x1002b284` |
| 3 | 0x20 | `0x1002b220` | `0x1002b0d8` |
| 4 | 0x20 | `0x1002b074` | `0x1002af2c` |
| 5 | 0x20 | `0x1002ad1c` | `0x1002abd4` |
| 6 | 0x20 | `0x1002ab70` | `0x1002aa28` |
| 7 | 0x20 | `0x1002a9c4` | `0x1002a87c` |
| 8 | 0x20 | `0x1002a818` | `0x1002a6d0` |
| 9 | 0x1c | `0x1002aec8` | `0x1002ad80` |
| 10 | 0x1c | `0x1002b578` | `0x1002b430` |
| 11 | 0x20 | `0x1002a66c` | `0x1002a524` |
| 12 | 0x20 | `0x1002a4c0` | `0x1002a378` |
| 13 | 0x20 | `0x1002a314` | `0x1002a1cc` |
| 14 | 0x20 | `0x1002a168` | `0x1002a020` |
| 15 | 0x20 | `0x10029fbc` | `0x10029e74` |
| 16 | 0x20 | `0x10029e10` | `0x10029cc8` |
| 17 | 0x20 | `0x10029c64` | `0x10029b1c` |
| 18 | 0x20 | `0x10029ab8` | `0x10029970` |
| 19 | 0x1c | `0x1002990c` | `0x100297c4` |
| 20 | 0x20 | `0x10029760` | `0x10029618` |
| 21 | 0x20 | `0x100295b4` | `0x1002946c` |
| 22 | 0x20 | `0x10029408` | `0x100292c0` |

`FUN_1001a5f2` @ `0x1001a5f2` only ever yields **1..0xf**, so kinds `0x10`..`0x16` are reached from
some other caller — `[UNCERTAIN]` which. It selects the kind from six runtime-built id lists at
`DAT_10032348`, `4c`, `50`, `54`, `58`, `5c` (12-byte entries, id at `+8`), with two id-range special
cases: `0x3b1a`..`0x3b25` (15130..15141) maps to kind `0xe`/`0xf` instead of `6`/`2`.

`0x41658d28` sits at offset 0 (QI `FUN_1000cdac` `[CONFIRMED @ 0x1000cdac]`), and the `cISC3Occupant`
subobject is at **`this+4`**, to which `FUN_1000cdac` delegates the other iids via
`FUN_10023852(this+4, …)`. **That closes `U-077`'s class question.**

### 11.3 The network-piece object, field by field

Slot `+0x10` of the primary interface, called with `(id, state)`, is **`FUN_1000c80b`**
`[CONFIRMED @ 0x1000c80b, SIMNTWRK.DLL]`:

```c
key = this->vt[0x60](&tmp, id);        // {0xe223741f, 0xa317745f, id} -- exemplar key, id only
*(u32*)(this+0x14) = (*(u32*)(this+0x14) & 0x3fffffff) | (state << 0x1e);
*(u32*)(this+0x18) = (*(u32*)(this+0x18) ^ id) & 0xffff ^ *(u32*)(this+0x18);
return FUN_10023936(this+4, &key);    // load exemplar into the occupant subobject
```

| offset | bits | meaning | getter | setter |
|---|---|---|---|---|
| `+0x00` | | vt1 (`0x41658d28`) | | |
| `+0x04` | | vt2 (`cISC3Occupant` subobject) | | |
| `+0x0c` | 24, 25 | two flags (written `0x1000c86f`, read `0x1000ca2c`) | | |
| `+0x10` | | resource/handle, `+0x1c` cache (`0x1000d225`) | | |
| **`+0x14`** | **30–31** | **`state` (orientation)** | `+0x38` = `0x1000cca3` | `+0x3c` = `0x1000ccaa` |
| `+0x14` | 0–10 / 11–21 / 22–29 | tile x / y / z (`0x1000c86f`, preserves `& 0xc0000000`) | | |
| `+0x18` | 0–15 | **piece `id`** | `+0x30` = `0x1000cc83` | `+0x34` = `0x1000cc8c` |
| `+0x18` | 16 | flag (property `0x63559421`) | `+0x18` = `0x1000cbee` | `+0x1c` = `0x1000cbf8` |
| `+0x18` | 17 | "has extra" (property `0x6355941e`) | `+0x40` = `0x1000ccc1` | |
| `+0x18` | 18–19 / 20–27 | 2-bit + 8-bit extra (`0x6355941f`, `0x63559420`) | `+0x48` = `0x1000cd01` | `+0x44` = `0x1000ccd3` |

`state` is written `<< 0x1e` with **no mask**, so any value above 3 is silently truncated to 2 bits —
consistent with the measured `{0,1,2,3}`.

### 11.4 U-078: the rotation is confirmed, the compass zero is NOT

**Confirmed.** `cISC3Occupant` slot `+0xb0` is an orientation getter, byte-identical in nine modules
(`SIMNTWRK 0x10023ecc`, `SIMGEOM 0x1001d0cb`, `SIMDSTR 0x1002e2c8`, `SIMECO 0x10014eb2`,
`SIMMISC 0x10035d31`, `SIMRCI 0x1003d7bc`, `SIMSERV 0x1001522f`, `SimTransit 0x1001612a`,
`SIMUTIL 0x10019ceb`):

```c
*param_3 = 0; *param_2 = 0;
switch (*(uint*)(this+0x10) >> 0x1e) {
  case 0: *param_1 = 0;      break;
  case 1: *param_1 = 0x3fff; break;
  case 2: *param_1 = 0x7fff; break;
  case 3: *param_1 = 0xbfff; break;
}
```

`[CONFIRMED @ 0x10023ecc, SIMNTWRK.DLL]`

The **units** are pinned by a consumer: `SIMRCI FUN_100191fe` `[CONFIRMED @ 0x100191fe, SIMRCI.DLL]`
does `render->vt[0x14](x, y, ((a & 0xffff) * 0x168) / 0xffff, 1)` where `0x168` = **360**. So the field
is a 16-bit angle over one turn and `0x4000` is exactly 90°. Same shape at `SIMRCI 0x10029a38` and
`0x1002cd48`.

The **iOS oracle names it**: `SimCity::goOccupant::GetOrientation(u16&, u16&, u16&) const` @
`0x0020718c`, same four literals (iOS packs the 2 bits at byte `+0x2c` bits 3–4 — a different layout,
as expected for `[iOS-HINT]` material). Its setter `SetOrientation` @ `0x002077ac` inverts by
round-to-nearest quarter turn at `0x1fff / 0x5fff / 0x9fff / 0xdfff` (the 45° midpoints). So SC3U slot
`+0xb0` = `GetOrientation`, `+0xb4` (`0x10023f18`, `*out = field >> 0x1e`) = raw index getter, `+0x10c`
(`0x1002403f`) = index setter that repaints on change.

Two more SC3U-side witnesses that the byte is an orientation and nothing else:

- `FUN_1000d225` `[CONFIRMED @ 0x1000d225]` builds the graphic key as
  `{0x625c6226, 0x825c6289, pieceId * 0x100 + state}`. **The state is the low byte of the sprite
  resource instance id.**
- `FUN_1000ca2c` `[CONFIRMED @ 0x1000ca2c]` and `FUN_10023b3a` `[CONFIRMED @ 0x10023b3a]` serialise it
  as `field >> 0x1e` through sink slot `+0x38`, beside x/y/z through `+0x30`. Persisted as a bare
  2-bit index.

**So `state N` = `N × 90°` about the single non-zero axis, monotone, with `state 0` = no rotation.**
That kills any non-monotone permutation of the four orthogonals, and it explains why `DAT_1003195c`
(ROAD) can carry the 90° step in the *id*: the id picks the art, the state picks a quarter turn of it,
and for pieces whose art exists in both forms the two are interchangeable.

**Still open, and it must not be guessed.** The ctor names no facing — no rotation matrix, no `dx/dy`
table indexed by `state`, no compass constant on this path. The only geometric consumer is the sprite
lookup, and it is data-driven: which drawing sits at instance `+0`/`+1`/`+2`/`+3` is a property of the
shipped art. The iOS sibling is unhelpful here rather than helpful —
`SimCity::OccupantSprite::setOccupantViewRotation` @ `0x002ac6b8` and `setOccupantBaseRotation` @
`0x002ac7a0` index by `(base + view) % 4` clamped to `getSubAnimCount`, i.e. the **camera** rotation is
added before indexing, so sub-frame 0 is tied to no world direction in code at all. Saying
"state 1 = north" from this evidence would be invention.

> ### ⭐ The A/B is NO LONGER blocked on `U-068`
> This is the actionable change. Take one **asymmetric** piece id (a T-junction or a one-way stub),
> extract resource instances `pieceId*0x100 + 0..3` under `{0x625c6226, 0x825c6289}` from the shipped
> resource files, and render the four. `GetOrientation` already establishes they are in 90° order, so
> only the zero reference and the sense remain, and two of the four frames settle both. **No game run,
> no in-city rendering, so the `U-068` block does not apply.**

### 11.5 Residuals

1. `[UNCERTAIN]` the compass zero and the rotation sense of `state`. Route in the box above.
2. `[UNCERTAIN]` which caller supplies factory kinds `0x10`..`0x16`; `FUN_1001a5f2` yields only `1..0xf`.
3. `[UNCERTAIN]` **highest-value remaining lead** — the concrete implementation of interface
   `0x82237425` slot `+0xb0`, called from `FUN_1000cd35` `[CONFIRMED @ 0x1000cd35]` as
   `vt[0xb0](x, y, z, state, &b0, &b1, &b2, &b3)`, returning four bytes. The declared vtable
   `0x1002bdcc` (QI `0x1000db84`) is abstract — every slot `+0x98`..`+0xb4` is the stub `0x1002670e`.
   **Four booleans from a coordinate plus a state is the shape of a per-side connectivity query, which
   would pin the facing from code alone.**
4. `[UNCERTAIN]` semantics of `+0x18` bits 18–19 and 20–27 (`0x6355941f`, `0x63559420`) and the two
   `+0x0c` flags.
5. `[UNCERTAIN]` `0x81c0cb7c`, unchanged from `U-044`.
6. Not done: mapping the six piece-id lists `DAT_10032348`..`5c` to the six network types.

### 11.6 Verification done before promotion

Four claims re-read from the export by the orchestrator rather than accepted on report: the
`0x10023852` QI body (`param_1 == -0x3eb076ab` present), the `0x10023ecc` switch literals, the
`0x1001363a` call sequence *including the argument order that proves the iid/clsid distinction*, and
`0x1000c80b`'s unmasked `param_2 << 0x1e`. All four match.

One figure differs harmlessly from the catalogue: §27c says the iid occurs in **52 functions**, this
pass counts **67 dword occurrences**. Both can hold — occurrences per function are not 1:1 — but do not
quote them as the same measurement.

Confidence: **C2** for the factory/field trace (decompilation read, callees resolved, named);
`GetOrientation`'s angle semantics are **C3** (nine byte-identical SC3U implementations, a consumer that
converts to 360°, and a named iOS witness).
