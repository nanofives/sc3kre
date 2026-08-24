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
entered cross-module. ~~`[UNCERTAIN]` which module/UI action drives each of `+0xac`/`+0xb0`/`+0xf0`;
that needs an xref sweep outside SIMNTWRK.~~ **SWEEP DONE 2026-08-24 — see §12.** `+0xb0` is driven
by **GZ message `0x637c0dab`** (six posters in SIMGEOM and SIMUTIL) plus one direct call from SIMRCI.
`+0xf0` and `+0xac` have **no cross-module caller in any shipped binary**, which is a finding in its
own right.

### Entry points

| slot | function | role |
|---|---|---|
| `+0xb0` | `FUN_100151f1` | **rectangle invalidate / retile.** `(this, bbox6, netMask)`. Early-outs on the `0x7fffffff` sentinel, then per bit of `netMask`: `bit0\|bit1`→HIGHWAY then ROAD, `bit2`→RAIL, `bit5`→POWER, `bit3`→PIPE, `bit4`→SUBWAY. The shape expected for city load and post-bulldoze refresh. |
| `+0xf0` | `FUN_10014a23` | **drag/build.** Funds check, then bridge path (netType 1–4 only, path length > 3) or normal path. For HIGHWAY it runs a **second** `FUN_1001547b` pass with netType 1 — highways retile the roads they touch. |
| `+0xac` | `FUN_1000abde` | reaches `FUN_1001547b`; not read. **No caller found in any of the 30 binaries (§12.3) — an apparently unreferenced virtual.** |

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

---

## 12. ⭐ U-075 SWEPT and U-080 ADJUDICATED (2026-08-24)

### 12.0 How class identity was established, and why that mattered

The `0x2171c021` class has **three** identity keys, and all 29 DLLs plus `SC3U.exe` were scanned at
raw-byte level for each:

| key | value | proven at |
|---|---|---|
| GZCLSID | `0x2171c021` | factory registration `FUN_1001e866(this, 0x2171c021, FUN_10001138, 0)` `[CONFIRMED @ 0x100010f3, SIMNTWRK.DLL]` |
| ServiceID | `0x2147c2dd` | slot `+0x3c` = `FUN_10013965 { return 0x2147c2dd; }` `[CONFIRMED @ 0x10013965]` |
| IID | `0x4147c2fb` | slot `+0x00` QI `FUN_1001396b` accepts exactly `{0x4147c2fb, 1, 0x58d}` `[CONFIRMED @ 0x1001396b]` |

Key occurrences, each scan run twice (byte scan of `original/modules/*` + `original/SC3U.exe`, and a
full `os.walk` over all 31 exports; both agreed):

- `0x2171c021` — **SIMCITY `0x10005ecd`** and **SIMNTWRK `0x100010f3`** only. Not in `SC3U.exe`.
- `0x2147c2dd` — AUDIO `0x100113ef`, SIMADV `0x10006ef3` + `0x100158bd`, SIMSPR `0x1001758a`,
  SIMNTWRK (3 sites). Not in `SC3U.exe`.
- `0x4147c2fb` — AUDIO `0x1001140a`, SIMADV `0x10006f12` + `0x100158db`, SIMCITY `0x10005ec2`,
  SIMSPR `0x1001759d`, SIMNTWRK `0x10013972`. Not in `SC3U.exe`.

Three acquisition idioms, all confirmed:

1. `GZCOM::GetClassObject(0x2171c021, 0x206c6e7c, &p); p->QI(0x4147c2fb, &out)` — SIMCITY only,
   `FUN_10005e3e`, stored at **city+0xa8** `[CONFIRMED @ 0x10005ecd]`.
2. `city->vtbl[+0x1b8](0x2147c2dd)` then `QI(0x4147c2fb, &out)` — AUDIO `FUN_100112a5` → `this+0x34`;
   SIMADV `FUN_10006c7f` → `this+0x2d8` and `FUN_1001588a` → `this+0x138`; SIMSPR `FUN_100172fe` →
   `this+0x6c` `[CONFIRMED @ 0x100158d1..0x100158e1]`.
3. `GetApp()->GetCity()->vtbl[+0x140]()` — the getter is SIMCITY `FUN_10002b48 { return *(this+0xa8); }`,
   at `+0x140` of city vtable `0x10013260` (its pointer is at `0x100133a0`; `0x100133a0 - 0x10013260 =
   0x140`). Used by SIMNTWRK `FUN_10021b24`, SIMRCI `FUN_1003cf3b`, SIMMISC `FUN_10032100`.

> **`SIMUI.DLL` holds none of the three keys and never calls `city->+0x140`. The UI does not hold this
> object.** So "which UI action drives evaluation" was the wrong shape of question: the UI is not a
> holder, and the drive path is a **message**.

> ### ⚠️ METHOD WARNING — a decompiled-text sweep would have returned a false negative here
> Ghidra rendered **zero** `+ 0xf0))(` sites in SIMNTWRK because it dropped the containing block as
> unreachable. The call is in the bytes at `0x1001491c`. The sweep that found it was an
> **instruction-level scan** (`FF /2` with disp8/disp32 equal to the slot offset) over every `.text`
> in all 30 binaries, followed by resolving the receiver of each candidate.
>
> This is a **different** failure from `U-056` (which is the harness `Grep` tool not seeing the
> ignored export tree). This one is the *export itself* being incomplete because the decompiler
> discarded a block. Both produce a confident "0 matches". **An exhaustive-negative claim about call
> sites needs the disassembly, not the decompilation.**

### 12.1 Slot `+0xb0` → `FUN_100151f1` (rect invalidate / retile) — CLOSED

**The primary entry is a GZ message, not a vtable pointer.** Slot `+0xc` is the class's message
handler `FUN_10013afe`; on type `0x637c0dab` it unpacks a rect and calls `this->vtbl[+0xb0]`
`[CONFIRMED @ 0x10013bdb, SIMNTWRK.DLL]`:

```c
local_24 = (param_1[2] >> 0x10) << 8;   local_20 = (param_1[2] & 0xffff) << 8;
local_18 = (param_1[3] >> 0x10) << 8;   local_14 = (param_1[3] & 0xffff) << 8;
(**(code **)(*(int *)this + 0xb0))(&local_24, param_1[1]);
```

Payload layout: `msg[0]` = type, `msg[1]` = **network bitmask**, `msg[2]` = `(x1<<16)|y1`,
`msg[3]` = `(x2<<16)|y2`. Coordinates are shifted `<< 8` into the 24.8 fixed point the rest of the
engine uses (§3). The class subscribes and unsubscribes to `0x637c0dab` plus seven sibling ids in
`FUN_10013497` / `FUN_10013589`.

**Cross-module posters of `0x637c0dab`** (exhaustive, by byte scan of the immediate):

| module | function | post RVA | bitmask | what the surrounding code does |
|---|---|---|---|---|
| SIMGEOM | `FUN_100134fb` | `0x100135f4` | computed | walks an occupant list, mutates cells, posts the union rect of `piVar4[0..4]` |
| SIMGEOM | `FUN_1001364f` | `0x100138bd` | computed | same shape, nested x/y loop |
| SIMGEOM | `FUN_1001392a` | `0x10013bbd` | computed | same shape; picks pass count 1 or 2 from mask bits `0x10`/`0x02` |
| SIMUTIL | `FUN_100017da` | `0x10001979` | **8** | `layerA->+0x48(occ); layerB->+0x48(occ); occ->+0xcc(&bbox)` then post — occupant add/remove, retile the bbox |
| SIMUTIL | `FUN_10011213` | `0x100113b2` | **8** | byte-identical 528-byte sibling |
| SIMUTIL | `FUN_100120f8` | `0x10012297` | **8** | byte-identical 528-byte sibling |

**One direct cross-module vtable call**, SIMRCI `FUN_1003591f` at `0x10035f66`
`[CONFIRMED @ 0x10035f66, SIMRCI.DLL]`:

```
piVar3 = FUN_1003cf3b();          // GetApp()->GetCity()
piVar3 = city->vtbl[+0x140]();    // the network manager
mov edx,[eax]; lea ecx,[ebp-0x80]; push 0x20; push ecx; mov ecx,eax; call [edx+0xb0]
```

Rect at `[ebp-0x80]`, **bitmask `0x20`**, guarded by `a1 != 0 && piVar3->vtbl[+0x148]() && local_d != 0`
where `a1` is a zone-type index 0..8.

Bitmask decode in `FUN_100151f1` `[CONFIRMED @ 0x100151f1]`, **with the network names from
`NETWORK_TYPES.md` §1 applied**:

| mask bit | netType | network |
|---|---|---|
| bit0 \| bit1 | 4 then 1 | HIGHWAY then ROAD |
| bit2 | 2 | RAIL |
| bit3 (`0x08`) | 5 | PIPE (layer `this+0x40`) |
| bit4 (`0x10`) | 6 | SUBWAY (layer `this+0x44`) |
| bit5 (`0x20`) | 3 | POWER |

So the SIMRCI call is **a zone-type-indexed POWER retile**, and the three SIMUTIL posters
(mask `8`) are **PIPE** retiles on occupant add/remove.

> The reporting sweep listed "which real network each number is" as an open residual. **It is not
> open** — `NETWORK_TYPES.md` §1 closed the netType→network binding, and §9 re-confirmed it three
> ways on 2026-08-24. The names above are applied on that authority.

### 12.2 Slot `+0xf0` → `FUN_10014a23` (drag/build) — CLOSED, and it has NO cross-module caller

Exactly **one** call site at offset `0xf0` in SIMNTWRK, the one Ghidra hid:

```
0x1001491c:  mov ecx,esi ; call [eax+0xf0]     ; eax = [esi], esi = this (from `8b f1` @ 0x10014817)
```
`[CONFIRMED @ 0x1001491c, SIMNTWRK.DLL]` — a **self-call** inside `FUN_10014807`, which is itself
slot `+0xec` of the same vtable.

`FUN_10014807` is reached only from six 29-byte thin wrappers, each a slot of the same vtable, each
hardcoding a network type (names applied per `NETWORK_TYPES.md` §1):

| slot | function | netType | network |
|---|---|---|---|
| `+0x94` | `FUN_100146aa` | 1 | ROAD |
| `+0x98` | `FUN_100146c7` | 4 | HIGHWAY |
| `+0x9c` | `FUN_100146e4` | 2 | RAIL |
| `+0xa0` | `FUN_10014701` | 6 | SUBWAY |
| `+0xa4` | `FUN_1001473b` | 5 | PIPE |
| `+0xa8` | `FUN_1001471e` | 3 | POWER |

Every `FF /2 +0x94..+0xa8` site in every holder module (SIMCITY, SIMSPR, AUDIO, SIMADV, SIMRCI,
SIMMISC, SIMGEOM, SimTransit) was resolved against that module's netmgr-holding field. **Zero hits.**

**So the six public build entries — the obvious "player drags a road" API — have no identified caller
in any shipped binary.** That is the same shape as `U-057` (no shipped writer for zone value 22) and
should be treated with the same care: it is a **measured absence**, not an explanation.

### 12.3 Slot `+0xac` → `FUN_1000abde` — no caller found anywhere

Every offset-`0xac` call site in every holder module resolves to a *different* receiver:

- SIMNTWRK `0x1000498a` (`this+0x54`), `0x10008ab4` (`this+0x30`), `0x1000fa7e` (`this+0x110`) — all a
  dimensions object with `+0xa8`/`+0xac`/`+0xb0`/`+0xb4` width/height getters, **not this class**.
- SIMCITY `0x1000afea`, SIMGEOM `0x10019ef8` — inside the `case 0x8000/0x8001…` GZWin message-map
  boilerplate; the receiver is the *message* object.
- SIMSPR (22 sites), AUDIO (3), SIMADV (2), SIMMISC (6), SIMRCI (3) — none on the module's netmgr field.

Also confirmed: `FUN_1000abde`, `FUN_100151f1`, `FUN_10014a23`, `FUN_10013771` and `FUN_10014807` have
**no direct (non-vtable) callers** in SIMNTWRK.

`[UNCERTAIN]` the one path not excluded statically: the netmgr pointer being passed as a *function
argument* into a module that holds none of the three keys. Closing that needs whole-program dataflow.

### 12.4 U-080 — VERDICT: **LATENT**, not live

Mechanism re-confirmed at byte level. `FUN_10013771` is
`__thiscall bool f(this, void** out, uint32 iid, int index)` (`ret 0xc`; `this` in ECX unused;
`[ebp+8]=out, [ebp+0xc]=iid, [ebp+0x10]=index`) `[CONFIRMED @ 0x10013771]`. When
`handler->vtbl[0](iid, out)` returns false:

```
0x100138c7:  push esi          ; esi = the global singleton
0x100138c8:  call 0x10026665   ; free()
0x100138cd:  pop ecx
             xor al,al ; ret 0xc
```

The global is **not** nulled, and teardown `FUN_100119e0` frees the same 32 globals again before
nulling them. The double free is real.

**Why it cannot fire.** All 42 predicate singletons are allocated in `FUN_10010dff`
(`operator new(8)` + one of 42 distinct vtables). Slot 0 of **all 42** is `FUN_1001a9bb`
`[CONFIRMED @ 0x1001a9bb]`:

```c
if ((param_2 == 1) || (param_2 == -0x5e3f7a25)) { *param_3 = param_1; AddRef(); return 1; }
return 0;
```

`-0x5e3f7a25` = `0xA1C085DB`. And the 32 distinct globals the `switch` selects are all members of that
42-element allocated set (set-difference verified empty).

**Complete iid census at slot `+0x54`: 25 call sites across all 30 binaries, every one passes
`0xA1C085DB`. Zero pass anything else.**

| module | function | indices passed |
|---|---|---|
| SIMNTWRK | `FUN_1000e537` | `0x1c, 0x10, 0x16` |
| SIMNTWRK | `FUN_1000e9e7` | `0x1d, 0x11, 0x17` |
| SIMNTWRK | `FUN_1000ee4b` | `0x1e, 0x12, 0x18` |
| SIMNTWRK | `FUN_1000f2c7` | `0x1f, 0x13, 0x19` |
| SIMNTWRK | `FUN_1000f79c` | `2, 0, 0` |
| SIMNTWRK | `FUN_1000fc45` | `0x21, 0x15, 0x1b` |
| SIMNTWRK | `FUN_100100bc` | `0x20, 0x14, 0x1a` |
| SIMNTWRK | `FUN_10014771` (**slot `+0x114`, self-call**) | `10` |
| **SIMSPR** | `FUN_10018a22` @ `0x10018abf`, `0x10018ae0`, `0x10018b00` | `2, 4, 1` — receiver `*(this+0x6c)` |

⇒ **Every shipped caller passes an iid the handler accepts, so the `free()` at `0x100138c8` is
unreachable in the shipped call graph. LATENT.**

> **Correction to the U-080 premise:** "the only entry is slot `+0x54` from another module" is
> **false**. `FUN_10014771` is itself slot `+0x114` of this vtable and calls
> `this->vtbl[+0x54](&out, 0xa1c085db, 10)` `[CONFIRMED @ 0x10014789]`. Eight of the nine caller
> functions are in-module.

Residual risk, stated rather than rounded off:

- The `default:` arm (index > `0x21`) writes `*out = 0` and returns false **without** freeing, so an
  out-of-range index is harmless.
- If `operator new` in `FUN_10010dff` fails, the global is 0 and `(**(code **)*puVar3)` null-derefs —
  a crash *before* the free, not a double free.
- **Any mod or patch that installs a vtable whose slot 0 rejects `0xA1C085DB` on one of the 32 globals
  turns this live.** As shipped, no such vtable exists. Worth stating in published toolkit docs.

### 12.5 Residuals

1. **Nothing calls `+0xac`.** To close: whole-program dataflow proving the netmgr pointer is never
   passed as an argument into a non-holder module. Byte-level offset scan plus receiver resolution in
   all nine holder modules is negative.
2. **Nothing calls `+0x94`..`+0xa8`, hence nothing calls `+0xec`, hence nothing calls `+0xf0`** except
   the in-module self-call chain. Same missing evidence as (1). Offset `+0xec` is too common (SIMUI
   alone has 138 sites) to resolve by receiver in reasonable time — that is the single missing edge.
3. **`SC3U.exe` is not fully cleared as a holder.** It contains none of the three identity keys, but
   its `city->+0x140` call sites were not enumerated (47 sites at `0xac`, 75 at `0xf0`, unresolved).
4. **No player-action label for the SIMGEOM / SIMUTIL posters.** All six are vtable-only, so naming
   the action needs the callers of *their* slots. Mechanically: SIMUTIL = occupant added/removed →
   retile its bbox, mask 8 (PIPE); SIMGEOM = cell set mutated over a rect → retile the union,
   computed mask.
5. **`FUN_1000d165` in SIMNTWRK is two functions merged by Ghidra.** The `+0x54` call at `0x1000d19e`
   belongs to a separate `__cdecl` thunk whose receiver is `[esp+4]`, not `piVar3` as decompiled. It
   passes iid `0xa1c085db`, index 1. Worth a tracker note independent of `U-080`.

### 12.6 Verification done before promotion

Two load-bearing claims re-read from the export by the orchestrator rather than accepted on report:
`FUN_1001a9bb`'s accepted-iid test (`param_2 == 1 || param_2 == -0x5e3f7a25`, and `-0x5e3f7a25` is
`0xA1C085DB` — this single function is what the entire LATENT verdict rests on), and the
`0x637c0dab` → `vt+0xb0` dispatch with its rect unpack in `FUN_10013afe`. Both match.

Confidence: **C3** for the `+0xb0` drive path (message dispatch read, six posters and one direct
caller enumerated by two agreeing scan methods) and for the `U-080` LATENT verdict (42/42 vtable
slots dumped, 25/25 call sites censused). **C2** for the negative results on `+0xac` / `+0xf0`, which
are measured absences with one un-excluded path each (§12.5).

### 12.7 Three things the tracker knew that the §12 sweep did not (found 2026-08-24 while promoting)

Promoting §11/§12 into `functions.csv` turned up **eleven rows already at C2 or C3**, and three of
them carry information that corrects or enriches the sweep. Recorded here rather than silently
overwritten — the promotion pass deliberately left every already-reviewed row untouched.

**1. `0x1001396b`'s accepted-iid set is LARGER than §12.0 states.** §12.0 says slot `+0x00` "accepts
exactly `{0x4147c2fb, 1, 0x58d}`". The pre-existing C2 note, from an earlier read, records a full
multi-subobject dispatch: `this` for `1 / 0x58d / 0x4147c2fb / 0x206c6e7c / 0x81c0cb7c`, `this+4` for
`0x5e4`, `this+8` for `0x6182ea06`, `this+0xc` for `0x81c0cb7b`. **Treat the tracker's version as
authoritative and §12.0's "exactly" as wrong.** It does not affect the identity argument — the class
does answer to `0x4147c2fb` — but any claim of the form "only these three iids reach this object" is
false, and `0x206c6e7c` (`GZIID_cISC3CityLayer`) being in that set matters for the next point.

**2. The `0x2171c021` class IS the city's transit layer, which names it.** `SIMCITY 0x10002b48` is
already **C3** as `cISC3City::TransitLayer(void)`, "`mov eax,[ecx+0xa8] ; ret`", **vtable slot 80**.
Slot 80 × 4 bytes = **`0x140`**, exactly the offset §12.0 derived independently from the pointer
arithmetic. So the two readings agree, and together they give the class a name: the object SIMCITY
hands out at `city+0xa8` is the **transit layer**, and it is what SIMNTWRK registers as GZCLSID
`0x2171c021`. That also explains `0x206c6e7c` = `GZIID_cISC3CityLayer` appearing in its QI, and it
is corroborated a third time by `SIMCITY 0x10005e3e` (C3, `sc3_citysim_acquire_layers`), which wires
33 layers into the city-sim by `(CLSID, IID, &field)`.

**3. `0x10014807` is not only a build dispatcher.** §12.2 describes it as slot `+0xec`, reached from
the six per-netType wrappers. The pre-existing C2 note reads it as `sc3_ntwrk_tool_reset_query`:
`switch(param_2)` mapping `1→ECX[0x78], 2→0x80, 3→0x8c, 4→0x7c, 5→0x88, 6→0x84, 8→0x90`, then
**filling 1280 triples with the `0x7fffffff` sentinel**. That sentinel is the same one
`FUN_100151f1` early-outs on (§1). Both readings can hold — a tool reset that then dispatches — but
the §12.2 label alone loses the sentinel fill, which is the part that connects to the `+0xb0` path.
`[UNCERTAIN]` which of the two is the function's primary role; **not** resolved here, and the row
keeps its original name.

> **Method note, and it is the general one.** The first promotion attempt was going to overwrite all
> eleven of those rows with freshly-written notes. Two of them would have *lost* measured detail and
> one would have introduced an outright error. **A tracker row at C2+ was written by someone who read
> the function; a fresh report is not automatically better than it.** The promotion pass was
> restricted to rows still at `C0` for exactly this reason, and the three conflicts above were
> written up instead of resolved by fiat.
>
> Also on record, because it reproduced the documented incident exactly: the first write parsed and
> re-serialised the whole CSV. Content was correct (`C0` −23, `C2` +23, row count identical) but
> `diff | grep -c '^<'` reported **50,668** changed lines instead of 23 — `csv.writer` re-quoted
> every field and flattened the 61 bare LFs inside quoted `notes` to zero. Restored from backup and
> redone by replacing only the 23 target records, which lands at **exactly 23**, with CRLF and bare-LF
> counts unchanged. `functions.csv` is fully quoted, so a writer must use `QUOTE_ALL`, and records
> must be matched on the **parsed** `(module, rva)` pair: `0x10002b48` exists in both `SIMADV.DLL`
> and `SIMCITY.DLL`, so this batch contained a live instance of the 9.9% collision hazard.
