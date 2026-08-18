# CITY_SAVE.md — the SC3 city / terrain / scenario file family

Cracked at the **container level** 2026-08-16. This was the last outstanding P2 format.

## The headline: they are `.IXF` containers

Every shipped city-family file is a GZ `.IXF` indexed database segment — the **same container**
already fully parsed by `re/tools/ixf_parse.py` for localized text and sprite archives.

```
Cities\Berlin, Germany.sc3   ->  d7 81 c3 80 ...   = 0x80C381D7, the .IXF magic
```

| extension | what it is | files | records |
|---|---|---|---|
| `.sc3` | saved cities | 15 | 189 |
| `.sct` | terrains | 21 | 254 |
| `.snr` | scenarios | 13 | 459 |
| `.st3` | starter towns | 10 | 90 |
| **total** | | **59** | **992** |

**59 of 59 parse cleanly with the existing parser, no changes required.** The container needed no
new work at all — the 20-byte index `{group, instance, type, offset, size}` and the tombstone /
end-of-index rules documented in `formats/IXF_segment.md` all hold.

Example — `Berlin, Germany.sc3`, 781,807 bytes, 13 records:

| type | group | instance | size |
|---|---|---|---|
| `0x035f62a4` | `0x035f62a4` | 1 | **743,406** ← the city data blob |
| `0xe2f42628` | `0x62f42635` | 0 | 17,663 |
| `0x00000fa1` | `0x617e198d` | 0 | 94 |
| `0x035ad1cb` | `0x835ad1d1` | 0 | 24 |
| … | | | |

## What is NOT the SC3 save format `[FALSIFIED]`

`SIMINIT.DLL` contains an IFF-style chunk reader — `sc3_init_read_chunked_file` `0x10001ada`
`[CONFIRMED @0x10001ada]` — that loops `{u32 tag, u32 length, payload}` with **both dwords
byte-swapped** (`FUN_10025ef1`), reading through the GZCOM stream primitive `vt+0x38`. Its tag
table at `0x100371f0` holds, in order:

```
XZON  XBLD  XTER  ALTM  MISC  SCDH  FORM
```

Those are **SimCity 2000 `.sc2` chunk tags** (zones, buildings, terrain, altitude map). It is a
**legacy `.sc2` importer**, *not* the SC3 city format — the shipped `.sc3`/`.sct`/`.snr`/`.st3`
files are `.IXF` and contain no `FORM` header.

> This was very nearly recorded the wrong way round. The chunk table looked exactly like a save
> format, and only checking the first bytes of a real `.sc3` file showed the container was
> `.IXF`. **Read the shipped bytes before naming a format after the code that reads *a* format.**

## The payload is QFS-compressed `[CONFIRMED, 59/59]`

The bulk record (`type == group == 0x035f62a4`) is a **24-byte header + a QFS stream** — the same
QFS used for sprites, so `re/tools/qfs.py` decodes it **unchanged**.

```
+0x00  u32   0x67 (103)          constant in all 59 shipped files
+0x04  u32   4                   constant in all 59
+0x08  char4 "0.90"              ASCII version; "0.90" in all 59
+0x0c  u32   compressedLength    == len(record) - 20
+0x10  u32   uncompressedLength  == the QFS stream's own declared size
+0x14  u32   compressedLength    (repeated)
+0x18        QFS stream (magic 0x10FB)
```

What pins the layout: the QFS stream's 3-byte big-endian declared size **equals the u32 at
`+0x10`** in every file, and the stream consumes exactly to the end of the record.

> **59 of 59 city-family files decode. Zero failures.**
> 21,901,812 compressed → 92,718,078 decompressed (4.23x).
> Tool: `re/tools/city_parse.py`.

Example — `Berlin, Germany.sc3`: record 743,406 bytes → 743,382 compressed → **2,153,415** out.

## The decompressed body is a SECTION ARCHIVE `[CONFIRMED, 59/59]`

```
+0x00  u32   sectionCount
+0x04  u32   sectionTableOffset      == len(body) - sectionCount*16   (all 59 files)
+0x08  ...   section payloads, laid out contiguously; the FIRST section starts here
@table       sectionCount x 16-byte entries:
               +0  u32 type
               +4  u32 group      <- a GZCOM CLASS id
               +8  u32 instance   (small ints, 0..18)
               +12 u32 offset
```

`sectionCount*16 + sectionTableOffset == len(body)` holds in **all 59 files**;
**3,451 sections** total. Offsets are unique, strictly increasing when sorted, always below the
table, and the sections **tile contiguously** — e.g. Berlin section 0 is at offset 8 with the
next at 140,311, and `8 + 140,303 = 140,311` exactly. There is **no size field**: a section's
size is the delta to the next offset.

**The `group` column is a GZCOM class id**, which makes this the city's *saved-layer directory*.
Exact matches against the independently pinned GZCLSIDs:

| group | class | occurrences |
|---|---|---|
| `0x409ff3ba` | **SC3ZoneLayer** | 767 (13 per city) |
| `0xe11bddf6` | **SC3WorldLayer** | 59 (exactly one per file) |

Several other ids occur exactly 59 times — once per file — so they are per-city singletons:
types `0x406b1196`, `0xc2910e7d`, `0x20631788`, `0xe0faadc7`, `0xe11bcc69`.

### Group `0x21737de5` = the SIMDIRT terrain layer ("DirtBag") `[CONFIRMED]`

Found 2026-08-16 from the SIMDIRT C0 cluster and cross-checked against the bytes from both
directions.

`SIMDIRT.DLL FUN_10004d90` writes the section key literally `[CONFIRMED @0x10004d90]`:

```c
uStack_4c = 0x206c6e7c;      // the generic section TYPE
uStack_48 = 0x21737de5;      // group
... FUN_10010560(auStack_3c, s_DirtBag_Start_100240f4, ...);   // stream vt+0xa4 = write string
... FUN_10010560(auStack_3c, s_DirtBag_End_10024104,   ...);
```

That key is the **first section of every city file** — Berlin `206c6e7c:21737de5:0`, 140,303
bytes. Its loader is `FUN_10004a00`. Note the payload is delimited by the literal ASCII keys
`DirtBag_Start` / `DirtBag_End` (`0x100240f4` / `0x10024104`) rather than by counts, and it uses
stream slots `vt+0xa4` (write string) / `vt+0x64` (write row) — **not** the `vt+0x38`/`vt+0x88`
mirror pair. So section grammars are per-class, and the mirror-pair test does not find them all.

## Section GROUP → producing code: ALL 44 accounted for `[CONFIRMED]`

Tool: `re/scripts/find_section_producers.py` (added 2026-08-16). The section key is written as
two adjacent stack stores, so it is **greppable**:

```c
local_28 = 0x206c6e7c;      // the generic section TYPE
local_24 = 0x409ff3ba;      // group == the GZCOM class id
```

Sweeping every module's export and intersecting with the groups actually present in the 59
shipped files locates the **home module and the serialiser RVAs** for 41 of the 44 groups — the
decode route this document calls the practical key to the format. At the start of 2026-08-16
only **2** were known this way.

> ⚠️ **The sweep was wrong twice before it was right, and both bugs were silent.** Neither
> produced an error; each just reported fewer hits, with nothing to show the tool was the limit.
>
> 1. **Store order (found 16).** The first version matched a section TYPE assignment and took
>    the literal on the *next* line. `SIMNTWRK 0x10012dff` writes four keys at once and stores
>    **every group before any type**, so `0x2147c2dd` — the second-largest group in the save,
>    148 sections — was missed. Caught only because a worker reported it independently.
>    **Do not assume store order in decompiled output.**
> 2. **Leading zeros (found 30).** The literal pattern required 8 hex digits. **Ghidra prints
>    hex without leading zeros**, so `0x029ca804` appears as `0x29ca804` and `0x00abf2ec` as
>    `0xabf2ec`. That silently skipped **every group whose top nibble is zero — 9 of the 44**.
>    Caught only because the SimTransit worker reported `0x29ca804` and the sweep disagreed.
>
> Both were found by a *disagreement between two methods*, not by inspection. When a tool and a
> reader disagree, the tool is the thing to check first.

| group | sections | class | serialiser sites |
|---|---|---|---|
| `0x409ff3ba` | 767 | **SC3ZoneLayer** | SIMRCI `0x10031c85`, `0x100320e7` |
| `0x2147c2dd` | 148 | **SIMNTWRK network layer** | SIMNTWRK `0x10012dff` |
| `0xa0ab89f0` | 118 | SIMGEOM occupant collection | SIMGEOM `0x100032ca` |
| `0xc28d0b6e` | 118 | | SIMADV `0x100073b3` |
| `0x20a7ae7f` | 59 | | SIMSERV `0x100071d5`, `0x100073b0` |
| `0x20ec9849` | 59 | | SIMRCI `0x1000e9e4`, `0x1000ebca` |
| `0x21737de5` | 59 | SIMDIRT terrain ("DirtBag") | SIMDIRT `0x10004d90` |
| `0x21f6abca` | 59 | | SIMDSTR `0x100089c3`, `0x10008de8` |
| `0x4296380e` | 59 | | SIMDSTR `0x1000d777` |
| `0x61448030` | 59 | | SIMSERV `0x1000c7b3`, `0x1000c8be` |
| `0x621cda33` | 59 | | SIMDSTR `0x10005917` |
| `0x80ab8ab0` | 59 | SIMGEOM tile grid | SIMGEOM `0x1000beec` |
| `0x80f1e6d3` | 59 | | SIMRCI `0x1002eb82` |
| `0x82937b60` | 59 | | SIMMISC `0x10014ae3`, `0x10015378` |
| `0xa0f42214` | 59 | | SIMSERV `0x1000a479`, `0x1000a619` |
| `0xa106cf3d` | 59 | | SIMRCI `0x10015b1b`, `0x10015c80` |
| `0xa11bcc54` | 59 | SIMMISC budget layer | SIMMISC `0x10006fb0`, `0x10007519` |
| `0xc0a81498` | 59 | SIMECO pollution layer | SIMECO `0x100062b4`, `0x10006abb` |
| `0xc0ab8a88` | 59 | | SIMRCI `0x1001ce51`, `0x1001cfb8` |
| `0xc106c4f5` | 59 | SIMRCI demand layer | SIMRCI `0x10021cf3`, `0x10022169` |
| `0xc259c02d` | 59 | | SIMMISC `0x10002784`, `0x100028f1` |
| `0xc336f77c` | 59 | | SIMDSTR `0x10001dea` |
| `0xe0afdf68` | 59 | | SIMUTIL `0x10003f4d`, `0x100045ec` |
| `0xe1193c2a` | 59 | | SIMMISC `0x10019c53`, `0x10019d5a` |
| `0xe11bddf6` | 59 | **SC3WorldLayer** | SIMMISC `0x10027563`, `0x1002776c` |
| `0x22963800` | 49 | | SIMDSTR `0x10015403` |
| `0x24889f78` | 49 | | SIMDSTR `0x10011158` |
| `0x45326359` | 49 | | SIMDSTR `0x1000b4ed` |
| `0xc446f87c` | 49 | | SIMDSTR `0x1001c53f` |
| `0xc4c90997` | 49 | | SIMDSTR `0x1001f7e9`, `0x1002027f` |

**Independent corroboration of the frame class.** SIMGEOM `FUN_1001f360` is a second, unrelated
copy of the SIMCITY frame reader — three `vt+0x260` key reads, then `vt+0x28` u16, `vt+0x18` u8,
then the `0xDEADBEEF` check `[CONFIRMED @0x1001f360]`. Found by a worker with no knowledge of the
SIMCITY result. So the frame is a per-module copy of a shared helper, and the base-0 correction
rests on two independent witnesses.

### ⭐ ALL SEVEN previously unnamed persisted CLSIDs now have located serialisers

The section further down records a careful, failed attempt to name these seven by adjacency,
which correctly refused to guess. The sweep does not name them either — but it supplies the
thing that was actually missing, the code that reads and writes each one:

| CLSID | module (from registration) | serialiser sites (from the sweep) |
|---|---|---|
| `0x20a7ae7f` | SIMSERV | `0x100071d5`, `0x100073b0` |
| `0x00abf2ec` | SIMSERV | `0x1000e3e0`, `0x1000e581` |
| `0xa0f42214` | SIMSERV | `0x1000a479`, `0x1000a619` |
| `0x20ec9849` | SIMRCI | `0x1000e9e4`, `0x1000ebca` |
| `0xa106cf3d` | SIMRCI | `0x10015b1b`, `0x10015c80` |
| `0x02619041` | SIMADV | `0x1001e98d` |
| `0x422e28e8` | SIMADV | `0x10018560`, `0x1001862c` |

**The home modules match exactly** what was independently derived from the registration and
factory addresses — SIMSERV ×3, SIMRCI ×2, SIMADV ×2. Two unrelated methods agreeing on all
seven is a strong check on both. Their *human names* remain **not determined**; the route is
now open, the name is not.

### The `0x029ca804` near-miss is resolved: it is SimTransit `[CONFIRMED]`

This document has warned since the container was cracked that `0x029ca804` sits 2 below the
pinned `TrafficLayer` id `0x029ca806` and must not be treated as a typo. **That caution was
right.** It is SimTransit's own layer: `SIMTRANSIT 0x100048ee` (load) and `0x10004c8d` (save)
both hold the literal `0x29ca804` alongside the type `[CONFIRMED @0x10004c8d, 0x100048ee]`,
serialising the byte cost grids at `+0x60..+0x74` and the `0x14`-stride grids at `+0x7c/+0x80`.
Two distinct ids in the same family, exactly as suspected — and this is SimTransit's **first**
known save section.

### Save vs load, resolved for 15 of the pairs — `--direction` `[CONFIRMED]`

`find_section_producers.py --direction` counts pinned stream slots per site: writes
`vt+0x64/0x68/0x84/0x88`, reads `vt+0x14/0x18/0x34/0x38`. It reports the counts, not a bare
verdict, and only calls it when one side wins by more than 2x with at least 3 calls.

**The heuristic reproduces three independently-established ground truths**, which is why it is
trusted here:

| group | site | verdict | w/r | independently known from |
|---|---|---|---|---|
| `0x409ff3ba` | `0x100320e7` | SAVE | 21/0 | read by hand, this document |
| `0x409ff3ba` | `0x10031c85` | LOAD | 0/22 | read by hand, this document |
| `0xa11bcc54` | `0x10007519` | SAVE | 16/0 | SIMMISC cluster 2 |
| `0xa11bcc54` | `0x10006fb0` | LOAD | 1/20 | SIMMISC cluster 1 |
| `0xe11bddf6` | `0x1002776c` | SAVE | 6/0 | read by hand, this document |

**15 groups now have a fully directed pair:** `0x409ff3ba` `0x20a7ae7f` `0x20ec9849`
`0x21f6abca` `0x61448030` `0x82937b60` `0xa0f42214` `0xa106cf3d` `0xa11bcc54` `0xc0a81498`
`0xc0ab8a88` `0xc106c4f5` `0xc259c02d` `0xe1193c2a` `0xc4c90997`. Six more have a directed SAVE
with no located loader (`0x2147c2dd` `0xc28d0b6e` `0x4296380e` `0x621cda33` `0x80f1e6d3`
`0x22963800`).

Two honest limits:

- **`0x21737de5` (SIMDIRT) only resolves to `save?`**, on the inferred slots `vt+0xa0`/`vt+0xa4`
  rather than the pinned four. Its writes are strings (`DirtBag_Start`), which go through a slot
  that was never pinned from an implementation. Independently known to be the saver anyway.
- **Sites that delegate stay ambiguous, correctly.** `SIMGEOM 0x100032ca` scores 2/1 because it
  opens the section and then drives the pinned occupant saver `FUN_1001e226` per item — the
  writes are in the callee. Same for `SIMGEOM 0x1000beec`, `SIMUTIL 0x10003f4d`/`0x100045ec` and
  three SIMDSTR sites. A slot count cannot see through a call, and it should not pretend to.
- **`SIMMISC 0x10027563` scores 5/9 and stays `?`** — consistent with the note above that
  Ghidra's decompilation of that function is **degraded**, so the call sites are unreliable.
  That the heuristic fails exactly where the decompile is known bad is a good sign, not a bad one.

**Four groups still have no literal pair: `0x022e288e`, `0x828d04eb`, `0x828d0a2f`,
`0xc28d0f40`** (59 sections each).

**RESOLVED — all 44 are now accounted for.** `0x022e288e` was a self-inflicted miss: it is both
a section TYPE (for group `0x422e28e8`) and a GROUP in its own right, and the sweep was
subtracting the type set before matching. Fixed by filtering on "is a real group" alone.

### ⭐ The type-`0x013dee82` family: ONE writer for all seven `[CONFIRMED]`

The last three were not three separate mysteries. **Every section of type `0x013dee82` is
written by a single generic function**, SIMADV `FUN_1001d310` `[CONFIRMED @0x1001d310]`:

```c
local_20 = 0x13dee82;                                    // TYPE     -- a literal
local_1c = (**(code **)(*(int *)((int)this + -0x10) + 0x4c))();   // GROUP -- a VIRTUAL CALL
local_18 = 0xb;                                          // INSTANCE -- a literal, 11
FUN_10007584(auStack_60, &local_20);                     // open the section with that key
```

**The group is never a literal at the write site** — it is `vt+0x4c` on the base subobject,
i.e. "tell me my own class id". No literal sweep can attribute these, by construction. That is
a structural limit of the method, not a defect in it.

The shipped bytes confirm it exactly: **413 sections of type `0x013dee82` = 7 groups × 59 files,
and every one is instance 11**, matching the literal `0xb`. The seven are `0x022e288e`
`0x028d0fc5` `0x628d0c45` `0x828d04eb` `0x828d0a2f` `0xc28d0b6e` `0xc28d0f40` — one advisor/news
subclass each. `FUN_1001d401` is the type dispatcher (`if (param_1 == 0x13dee82)`).

`0xc28d0b6e` appears in both this family *and* the literal table because it has **two** sections
per file: `0x206c6e7c` instance 0 (SIMADV `0x100073b3`, a genuine literal write) and
`0x013dee82` instance 11 (this family). That is why its count is 118, not 59.

> ⚠️ **One known FALSE POSITIVE in the sweep output, left in deliberately.** SIMUI `0x1000690a`
> is an if/else-if **class-id selector** (tag 1 → `0x022e288e`, 2 → `0x628d0c45`, 3 →
> `0xc28d0b6e`), not a serialiser; it matches only because `0x022e288e` is itself a section type.
> A guard requiring "calls a pinned stream slot" removes it — but it also removes SIMGEOM
> `0x100116e9`/`0x1001176e`, which genuinely write `{0x206c6e7c, 0x01fd7a8c}` while reaching the
> stream through unpinned slots `0x24`/`0x28`. **A silent false negative is worse than a
> documented false positive**, because only the first one is invisible. So the hit stays in and
> is named here instead. Hand-check new hits.

One literal pair, `0xc3de4d66` (SCENARIO `0x10009c3d`), appears in **no** shipped file — a
section written only for scenario state that none of the 13 shipped `.snr` files exercises.

### SIMDSTR's eight sections — field-order layouts `[CONFIRMED]`

SIMDSTR owns more save sections than any other module. `re/analysis/SIMDSTR_CLUSTER2.md` gives
the field order for each; the shape is uniform. The `SC3DisasterLayer` manager (CLSID
`0x61f6abf5`, `[CONFIRMED @0x1002269e]`) owns a GZ persistent-object collection at `manager+0x10`;
every **list** section walks that collection keeping only nodes whose type-id equals the section's
own group, and the **fixed-array** sections stream an in-place vector.

Spot-checked against the binary: `0x10008de8` writes in the exact claimed slot order
(`vt+0x98`, then four `vt+0x88`) `[CONFIRMED @0x10008de8]`, and `0x10001dea` uses a `0x24`-byte
(36) element stride with a `0xc351` (50,001) bound — i.e. a cap of 50,000 — writing raw blocks
through `vt+0xac` `[CONFIRMED @0x10001dea]`.

> An anomaly the worker reported rather than smoothed over, and it is preserved here: in the
> master record `0x21f6abca`, **SAVE writes `this+0xa0` and `this+0xb4` but LOAD restores into
> `this+0xd0` and `this+0xd4`.** Not reconciled. Either the fields are aliased through a union
> or one side was misread; it needs a second look before anyone writes a parser against it.

Two stream slots turn up here that were not in the pinned set: **`vt+0x98`** (a write, seen in a
proven saver) and **`vt+0xac`**, which is the underlying `Write(ptr, len)` already pinned in the
primitives table. `vt+0xac` has been promoted into the direction test's confirmed write set;
`vt+0x98` sits in its inferred tier.

### Group `0xc106c4f5` = the SIMRCI demand layer `[CONFIRMED]`

Found 2026-08-16 from the SIMRCI C0 cluster. `SIMRCI.DLL` holds a full mirror pair keyed on it —
`FUN_10022169` (save) and `FUN_10021cf3` (load), both writing the literal
`{0x206c6e7c, 0xc106c4f5}` `[CONFIRMED @0x10022169, 0x10021cf3]`. Berlin's matching section is
`206c6e7c:c106c4f5:0`, 1,994 bytes.

The pair agrees on the field set, which is the on-disk shape of the RCI demand layer: bools at
`this+0x640/0x641/0x642`, four sub-objects at `this+0x74/0x1dc/0x344/0x4ac` (stride `0x168` =
360), accumulators `this+0x644..0x67c`, and the three demand gauges `this+0x680/0x684/0x688`.
Array writes go through `vt+0x8c` with capacity `0x5a` (90).

`[UNCERTAIN]` group `0x029ca804` occurs once per file and sits **2 below** the pinned
`TrafficLayer` id `0x029ca806`. It is *not* treated as a match — a near-miss id is a different
class, not a typo.

### ⚠️ SECTION OFFSET BASE = **0** `[CONFIRMED, 59/59]` — the `+0x0C` reading is **FALSIFIED**

Corrected 2026-08-16 (later). The `offset` field is **absolute in the body**; the body header is
**8 bytes**, not 20. What was read as header fields at `+0x08` / `+0x0c` / `+0x10` is the **first
section's own content**.

The earlier `+0x0C` proof was circular: it assumed a 20-byte header, then observed that
`12 + 8 = 20` reached its end. Both bases tile `[first, tableOffset)` exactly and produce
identical section *sizes*, so tiling cannot distinguish them — only content can. See the frame
test below, which does.

**Consequence: attempts 3, 4, 5 and 6 at the zone grammar all ran on a window shifted 12 bytes
too late.** Attempts 1-2 used base 0 but an incomplete grammar. Every recorded byte-level
observation taken at base 12 (notably the twelve 4-byte SC3ZoneLayer id values) is off by three
slots and has been re-measured below.

**Grid-size lead, now clean:** Berlin's section `406b1196:80ab8ab0:0` is **65,552 bytes**, and at
base 0 it opens with an 8-byte object frame, leaving `65,544 = 65,536 + 8` — a **256 x 256 byte
grid** plus 8 bytes. `[UNCERTAIN]` — no consuming code read.

## THE ARCHIVE DOES FRAME SECTIONS — the frame class `[CONFIRMED]`

The archive class was the untested assumption above the grammar, and reading it settled the
offset base. The frame is written by a small **SIMCITY.DLL** class, vtable `PTR_FUN_10013fc0`:

| function | role | evidence |
|---|---|---|
| `0x10010315` | **read** ctor (open-for-load, validates) | `[CONFIRMED @0x10010315]` |
| `0x10010531` | **write** ctor (open-for-save, emits) | `[CONFIRMED @0x10010531]` |
| `0x1001066c` | dtor | `[CONFIRMED @0x1001066c]` |
| `0x100106ab` | accessor: returns the framed stream, or NULL | used by every caller |

The read ctor's sequence `[CONFIRMED @0x10010315]`:

```c
uVar3 = (**(code **)(*param_1 + 0x260))();   x3   // three u32s -> this+0x14/0x18/0x1c
piVar5 = FUN_1000e9f4(this->sub);            // sub->member_0x10 == the stream
(**(code **)(*piVar5 + 0x28))();             // u16  -> this+0x04   version
(**(code **)(*piVar5 + 0x18))();             // u8   -> this+0x06   flags; bit0->+6, bit1->+7
  if (flags bit1)  (**(code **)(*piVar5 + 0x18))();   // u8   -> the extra byte
(**(code **)(*piVar5 + 0x38))();             // u32  -> this+0x08
*(bool *)((int)this + 0x10) = *(int *)((int)this + 8) == -0x21524111;   // == 0xDEADBEEF
```

`0x10010531` is its exact mirror on the write slots (`vt+0x78` twice, then `vt+0x88`), and takes
the version `u16` and the flags `u8` as arguments.

So the on-disk frame is:

```
+0x00  u16   version
+0x02  u8    flags
+0x03  u8    extra        <- present iff (flags & 2)
+0x04  u32   0xDEADBEEF   <- the ctor refuses the object if this does not match
```

### The test that pins base 0 `[CONFIRMED, 59/59]`

| base | sections whose first bytes are a valid frame |
|---|---|
| 12 (old) | 319 of 3,451 = 9.2% |
| **0** | **2,330 of 3,451 = 67.5%** |

And **2,330 is also the total number of `0xDEADBEEF` byte sequences in all 59 decompressed
bodies.** Every marker in every file is a section-start frame; none is left over; none lands
anywhere else. That is not reachable by coincidence, and base 12 cannot produce it.

Observed frame variants (all 8 bytes long, so `flags & 2` holds everywhere):

| version | flags | count |
|---|---|---|
| 1 | 2 | 1,341 |
| 2 | 2 | 362 |
| 4 | 2 | 207 |
| 3 | 2 | 170 |
| 3 | 3 | 66 |
| 505 | 2 | 59 |
| 9 | 2 | 59 |
| 2 | 3 | 44 |
| 1 | 3 | 22 |

The frame is **opt-in per class**, not imposed by the archive on every section: the other 1,121
sections start with payload. `SC3ZoneLayer` is one of the classes that does **not** use it —
all 767 of its sections are unframed.

### The city LOAD driver, and where the frame is used `[CONFIRMED @0x1000351e]`

`SIMCITY.DLL FUN_1000351e` (1,645 bytes) is the **city load driver**: `this` = the city
simulator, `param_1` = the archive.

```c
FUN_10010315(&local_100, this, param_1);        // open the framed city header
piVar6 = (int *)FUN_100106ab((int)&local_100);  // the stream, or NULL
...   vt+0x48 x4 -> this+0x180/0x184/0x188 ;  vt+0x38 x8 ;  vt+0x54 x4 (strings) ; vt+0x18 x3
FUN_1001066c(&local_100);                       // close the frame
...
(**(code **)(**(int **)(*(int *)((int)this + 0x94) + uVar7 * 4) + 0x1c))(this, param_1);
                                                // then EACH layer's load, (citySim, archive)
```

So the layer array lives at `citySim+0x94 .. +0x98` and each layer's **load is vtable slot
`+0x1c`**, taking `(citySim, archive)`. `FUN_10004b85` is the sibling that also opens a frame.

## Worked example: SC3ZoneLayer — the loop closed `[CONFIRMED]`

`SC3ZoneLayer` (GZCLSID `0x409ff3ba`, SIMRCI) is registered at `0x10036382` with factory
`FUN_10036660` — `operator_new(0x2d0)` (720 B), ctor `FUN_100310f5`, returns object+0x10.

Its **saver is `FUN_100320e7`** and its loader `FUN_10031c85` (both hold the literal
`0x409ff3ba`). The saver *writes the section-table key itself*, which closes the loop between
the file layout and the code `[CONFIRMED @0x100320e7:23-25]`:

```c
local_28 = 0x206c6e7c;                                  // section TYPE
local_24 = 0x409ff3ba;                                  // group = the CLASS id
uVar4 = (**(code **)(*param_2 + 0x30))(&local_28, &local_14);   // archive->OpenSection(key, &stream)
...
cVar2 = (**(code **)(*local_8 + 0x88))(*(undefined4 *)((int)this + 0x260));  // stream->Write(field)
```

So: **archive `vt+0x30` = open-section-by-{type,group}; stream `vt+0x88` = write a field.**
That is where the 16-byte section entries come from, and it confirms `type 0x206c6e7c` as the
generic "serialised object section" type — which is why it is the most common type in the table
(2,095 of 3,451 sections).

Field write order in the saver, i.e. the on-disk order: `this+0x10`, `this+0x14`, then
`+0x260`, `+0x264`, `+0x15c`, `+0x158`, `+0x154`, `+0x150`, then a **loop** writing
`this + i*8 + 0x18c` (a stride-8 array) in a second section opened the same way
`[CONFIRMED @0x100320e7:131-135]`.

### What the 13 SC3ZoneLayer sections are

Re-measured at **base 0** (the values previously recorded here were read 12 bytes late, i.e.
three slots off, and are withdrawn). Each value is identical in all 59 files:

| instance | size | content |
|---|---|---|
| 0 | 50,274–198,060 (varies per city) | the bulk zone data |
| 2, 3, 4 | 4 | `0x619BA64E` |
| 6, 7, 8 | 4 | `0x41A3ADC1` |
| 10, 11, 12 | 4 | `0xE1A53B30` |
| 15 | 4 | `0xC1F81E7E` |
| 16 | 4 | `0x82D2D72B` |
| 18 | 4 | `0x82348DE5` |

### The stride-8 loop explains the instances `[CONFIRMED @0x100320e7:120-148]`

```c
while (true) {
  if (0x16 < bVar1) break;                                    // 23 slots, index 0..0x16
  uVar5 = bVar1;
  if (*(int *)((int)this + uVar5*8 + 0x188) != 0) {           // skip NULL slots
    local_20 = uVar5 + 1;                                     // INSTANCE = index + 1
    (**(code **)(*param_2 + 0x30))(&local_28,&local_14);      // OpenSection(key)
    (**(code **)*local_14)(0x199627,&local_8);                // QueryInterface(IID 0x199627) -> stream
    (**(code **)(*local_8 + 0x88))(*(u32 *)((int)this + uVar5*8 + 0x18c));   // write the slot's id
    (**(code **)(**(int **)((int)this + uVar5*8 + 0x188) + 0x24))(...);      // sub-object writes itself
  }
  bVar1 = bVar1 + 1;
}
```

This resolves three things at once:

1. **`this+0x188` is a 23-slot table of 8-byte records** `{void* obj at +0x188+i*8, u32 id at
   +0x18c+i*8}` — the same **23-slot zone-developer table** already documented in `SIMRCI.md`,
   now tied to the save format.
2. **The section `instance` is the slot index + 1.** Observed instances 2,3,4,6,7,8,10,11,12,
   15,16,18 are slots 1,2,3,5,6,7,9,10,11,14,15,17 — and the previously unexplained **skips
   (1,5,9,13,14,17) are simply NULL slots** (indices 0,4,8,12,13,16). Mystery closed.
3. **Instance 0** is the main section written earlier in the function, not part of this loop.

Also pinned: **IID `0x199627` is the write-stream interface** — a section object is QI'd for it
to obtain the stream that `vt+0x88` writes to.

The twelve 4-byte sections are therefore each a slot's `u32 id` at `this + i*8 + 0x18c`. They are
**byte-identical across all 59 shipped files**, so they are **not city data** — they are ids
(note `0x619FF3CE` shares its middle digits with `SC3ZoneLayer` `0x409FF3BA`). The counts
`0x619FF3CE`×3, `0x41A00001`×3, `0xE1A00030`×3 form three groups of three; `[UNCERTAIN]` whether
that is R/C/I × three density tiers — the shape fits but nothing confirms it.
`[UNCERTAIN]` what they identify: none of the six values occurs
anywhere in any binary's decompiled text, which matches the U-006 pattern of ids that exist only
in data and are resolved at runtime. Only instance 0 varies per city.

~~`[UNCERTAIN]` the instance numbers skip 1, 5, 9, 13, 14 and 17.~~ **RESOLVED below** — they
are NULL slots in the 23-slot table.

### Instance 0 — the bulk zone data

198,000 bytes in Berlin. **It is not a fixed-dimension grid.** Sizes vary per city *within* a
size class (197,634 / 197,916 / 198,000 / 198,060 …), which rules out a plain `w*h` raster, and
they fall into two clusters — ~111,8xx and ~197,9xx — consistent with two city map sizes.

Content starts `00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 0f 0f 0f 00 0a 0a 0a …`: all 256
byte values occur, but the distribution is heavily skewed (0x00 ×42,470 of 198,000; then 0x02,
0x16, 0x03, 0x06, 0x09). Runs of a repeated small value are common.

`[UNCERTAIN]` the encoding. `198000` is not a clean multiple of 65,536 (×3.021) and
`sqrt(198000) = 445.0` is close to but not exactly 445² = 198,025, so neither a square grid nor a
simple power-of-two raster fits. **Do not assume a raster.**

### The saver's grammar for instance 0 — derived, and it does NOT fit the data

Reading `0x100320e7:25-104` gives the stream vtable and the write order
`[CONFIRMED @0x100320e7]`:

| stream slot | operation |
|---|---|
| `vt+0x88` | write u32 |
| `vt+0x68` | write u8 |
| `vt+0x84` | write raw block `(ptr, len)` |
| `vt+0x38` | read u32 (the loader's counterpart) |

```
(*(this-0x14))->vt+0x28(stream)        // base class writes FIRST, length unknown
u32 count1;  count1 x { u32 node+0x10, u32 node+0x14 }     // walks a list at *(this+0x2a4)
vt+0x84(this+0xf4, 0x17);  vt+0x84(this+0x98, 0x17)        // two raw blocks
u32 count2;  count2 x { u8 node+0x10, u8 node+0x14, u32 node+0x18 }   // list at *(this+0x160)
u32 count3;  count3 x { u8, u8, u32 }                                 // list at *(this+0x16c)
```

**Tested against Berlin's 198,000-byte section and it does not fit.** Scanning *every* possible
start offset (0 … N-60) and requiring the grammar to consume exactly to the end gives **zero**
exact fits; allowing ±64 bytes of slack over prefixes 0-199 also gives none.

So one of these is wrong, and this is the next thing to resolve:
- `vt+0x84(ptr, 0x17)` — `0x17` may be an **element count**, not a byte length;
- `vt+0x68` may not write exactly one byte;
- the base-class `vt+0x28` write may not be a simple opaque prefix;
- or the section's **end** is misplaced, since sizes are derived as offset deltas and the
  `offset` base is itself `[UNCERTAIN]` (see above).

Recording the failure explicitly so the next attempt starts from the grammar and the four
suspects rather than re-deriving them.

**Attempts 2 and 3 also failed, and the boundary excuse is now gone.**

- *Attempt 2*: `0x17` as an **element count**, sweeping element sizes 1/2/4/8 and `vt+0x68`
  widths 1/2/4 — 12 combinations, every start in the first 4 KB. **Zero fits.**
- *Attempt 3*: after the offset base was pinned to `+0x0C` (above), the section window shifted by
  12 bytes at **both** ends — the exact boundary error suspected. Re-ran the full sweep on the
  corrected window. **Still zero fits.**

So the boundary is now proven correct and the **grammar is what is wrong**. The corrected
section begins `00 00 00 0f 0f 0f 00 0a 0a 0a …` — byte data, not a `u32` count, which is
consistent with the saver's *first* call being the base class's `vt+0x28` write. That base-class
write is therefore not a small prefix but the **bulk of the section**, and it is opaque here:
`this-0x14` is the base subobject and its `vt+0x28` was never read.

### The base-class writer — found, and it is a row-pointer array `[CONFIRMED]`

Chased through three hops, each invisible to the text export:

1. The saver calls `(*(this-0x14))->vt+0x28`. `this` is object+0x14, so `this-0x14` is the base
   subobject at object+0, whose vtable is `PTR_FUN_1004d274` (installed by the SC3ZoneLayer ctor
   `FUN_100310f5`).
2. `VtableDump` slot 10 (`+0x28`) = `0x10030369`, which **Ghidra never carved** — force-created
   with `MakeFunctions.java` (15 bytes). It is a delegating stub `[CONFIRMED @0x10030369]`:
   ```
   PUSH dword ptr [ESP + 0x4]     ; the stream
   MOV  ECX, dword ptr [ECX+0xc]  ; this = this->member_0x0c
   CALL 0x1001b4e9
   RET  0x4
   ```
3. `FUN_1001b4e9` (53 bytes) is the real writer `[CONFIRMED @0x1001b4e9]`:
   ```c
   n = *(int *)(this + 4);                        // ROW COUNT
   while (--n >= 0)
       stream->vt[+0x64]( *(u32 *)(*(int *)(this + 0xc) + n*4),   // pointer to row n
                          *(u32 *)(this + 8) );                   // BYTES PER ROW
   ```

So the bulk of the section is a **2D array serialised as `rowCount` raw blocks of `rowBytes`
each**, through a *new* stream slot **`vt+0x64` = write-raw-block(ptr, len)** — and the rows are
written **in reverse order** (`n-1` down to `0`).

The owning struct is therefore `{ +0x04 rowCount, +0x08 rowBytes, +0x0c rowPointerArray }`,
reached from the layer via `member_0x0c`.

### The stream vtable — required signatures, and one candidate REJECTED

The zone save path pins the *arity* of four stream slots, which is enough to identify the right
vtable `[CONFIRMED from the call sites]`:

| slot | args | from |
|---|---|---|
| `+0x64` | **2** — `(ptr, len)` | the base writer `0x1001b4e9` |
| `+0x68` | **1** — a byte value | the saver's `{u8,u8,u32}` list loops |
| `+0x84` | **2** — `(ptr, 0x17)` | the two fixed blocks |
| `+0x88` | **1** — a u32 value | everywhere |

IID `0x199627` is the stream interface — QI'd for it in **18 of the 31 modules**, so it is the
universal GZCOM stream. Its implementation should be in `GZResourceD.dll`.

`FindVtables` there (>=35 slots, requiring `+0x64/+0x68/+0x84/+0x88` to resolve) gives one strong
candidate, `PTR 0x1001d5c8` (installed by `FUN_1000eb7e` / `FUN_1000ec31`), with
`+0x64 = FUN_1000b5b5`, `+0x68 = FUN_1000b614`, `+0x84 = FUN_1000f33a`.

> ⚠️ **REJECTED.** The arities are **inverted** versus the requirement: `FUN_1000b5b5` (`+0x64`)
> is `__thiscall(this, param_1)` — **one** argument, where the base writer passes **two**; and
> `FUN_1000b614` (`+0x68`) takes **two**, where the saver passes **one**. So this is either a
> different interface or the same one at a 4-byte slot shift. **Not the zone saver's stream**,
> and not usable to decode the grammar.

### The stream primitives — RESOLVED by construction `[CONFIRMED]`

Identifying by construction rather than by vtable search worked immediately:

1. `FUN_1000b88a` (GZResourceD) is the **QueryInterface that answers** the IID
   `[CONFIRMED @0x1000b88a]`: `if (param_1 == 0x199627) { *param_2 = this; AddRef; }`. The
   stream is returned as **`this` at offset 0**, so the stream vtable *is* that class's vtable.
2. `VtableProbe` on it gives **three** vtables holding it at slot 0 —
   `PTR_FUN_1001cb34`, `PTR_FUN_1001cef0`, `PTR_FUN_1001d130` (three stream flavours).
3. All three share the **same** functions at the four slots of interest, i.e. a common base.
   Three were uncarved; `MakeFunctions.java` created them.

Every one forwards to `vt+0xac`, the underlying `Write(ptr, len)` `[CONFIRMED]`:

| slot | implementation | code | meaning |
|---|---|---|---|
| `+0x64` | `0x1000c169` | `PUSH [ESP+8]; PUSH [ESP+8]` → `RET 8` | **Write(ptr, len)** — raw block |
| `+0x68` | `0x1000c157` | `LEA EDX,[ESP+4]; PUSH 1; PUSH EDX` → `RET 4` | **Write(&arg, 1)** — u8 |
| `+0x84` | `0x1000c1ad` | `MOV EDX,[ESP+8]; PUSH EDX; PUSH [ESP+8]` → `RET 8` | **Write(ptr, len)** — raw block |
| `+0x88` | `0x1000c1d6` | `PUSH 4; PUSH &local` → `RET 4` | **Write(&value, 4)** — u32 |

**This vindicates the original grammar assumptions**: `vt+0x84` *is* a raw `(ptr, len)` write, so
the two `0x17` blocks *are* 23 bytes each, and `vt+0x68` *is* one byte. Attempt 1 modelled all of
this correctly.

It also confirms the earlier candidate `PTR 0x1001d5c8` was rightly rejected — it is a different
class entirely.

**These four primitives apply to every GZCOM serialiser in the project**, not just the zone
layer, which makes them the most reusable part of this investigation.

### So why does the grid still not fit?

The primitives are no longer a suspect, and neither is the section boundary. Remaining
candidates, none tested:
- the `if (cVar != '\0')` guards threaded through the saver may skip writes in ways the flat
  grammar does not model;
- `FUN_10010ae4` is the list-node iterator — if those containers are maps rather than lists, the
  per-node field offsets (`+0x10`, `+0x14`, `+0x18`) would differ;
- the base-class row write has **no count and no dimensions** in the stream, so `rowCount` and
  `rowBytes` must come from elsewhere entirely (probably the world layer) — if a *reader* needs
  external dimensions, a self-describing parse of this section may simply not be possible.

That last point is the important one: it may be that this section **cannot** be parsed
standalone, and decoding it requires the city dimensions from `SC3WorldLayer` first.

### Dimensions are NOT in SC3WorldLayer `[FALSIFIED]`

Checked directly: the 725-byte `SC3WorldLayer` section's only u32 values in the 1..1024 range are
**150 (at +0x04) and 255 (at +0x18)**, and both are **identical across cities** — Berlin
(zone blob 198,000), Europolis (197,634) and Farmsville (111,726) carry the same two numbers.
Per-city grid dimensions are therefore **not** in the world layer section. Hypothesis dead.

What the blob sizes do show: two clusters, ~197.6-198.1 KB and ~111.7-111.9 KB, i.e. **two map
sizes**, with small within-cluster variation (a few hundred bytes) that must come from the
variable-length lists.

### Attempt 5: the missing trailing writes — also no fit

Re-reading the saver's tail exposed an omission in every earlier grammar: after the two
`{u8,u8,u32}` lists there are **six more u32 writes** (`this+0x260`, `+0x264`, `+0x15c`,
`+0x158`, `+0x154`, `+0x150`) `[CONFIRMED @0x100320e7:109-118]` that the grammar never included —
24 bytes. Re-swept with and without that 24-byte tail. **Still zero exact fits.**

### Stop sweeping the saver; read the LOADER

Five attempts have now failed, all built from the **saver**. That is the wrong source: the saver
is threaded with `if (cVar != '\0')` guards, writes through two different raw-block slots, and
delegates its bulk to a base class — so reconstructing a linear grammar from it is error-prone,
as five failures demonstrate.

**`sc3_zonelayer_load` `0x10031c85` is the authoritative parser** — and it was read. It confirms
the grammar exactly, gives the read primitives, and supplies validation bounds. It still does not
fit. See below.

### The loader, read in full `[CONFIRMED @0x10031c85]`

Read primitives, the exact mirror of the four write primitives:

| read slot | write slot | meaning |
|---|---|---|
| archive `vt+0x20` | archive `vt+0x30` | open section by `{type, group}` |
| `vt+0x14` | `vt+0x64` | read/write raw block `(ptr, len)` |
| `vt+0x18` | `vt+0x68` | read/write u8 |
| `vt+0x34` | `vt+0x84` | read/write raw block `(ptr, len)` |
| `vt+0x38` | `vt+0x88` | read/write u32 |
| base `vt+0x24` | base `vt+0x28` | the bulk row array |

Read order: base bulk → `u32 c1` → `c1 × {u32, u32}` (into the map at `this+0x2a4`) →
`raw(this+0xf4, 0x17)` → `raw(this+0x98, 0x17)` → `u32 c2` → `c2 × {u8, u8, u32}` →
`u32 c3` → `c3 × {u8, u8, u32}`. **Identical to the grammar derived from the saver.**

**The base reader `0x1001b4b4`** (reached via the carved thunk `0x1003035a`) is the mirror of the
writer and settles the dimensions question outright:

```c
n = *(int *)(this + 4);                                  // rowCount  — from the OBJECT
while (--n >= 0)
    stream->vt[+0x14]( *(u32*)(*(int*)(this+0xc) + n*4),
                       *(u32 *)(this + 8) );             // rowBytes  — from the OBJECT
```

**Neither dimension is ever in the stream.** The reader already knows them, so the section is
genuinely **not self-describing** — confirming the earlier suspicion as fact, not hypothesis.

**Validation bounds the loader enforces** (useful as parse filters): both list counts `< 0x1b6`
(438); each record's first `u8 < 0x13` (19) and second `u8 < 0x17` (23).

### Attempt 6 — with the loader's own bounds — also zero fits

Re-swept every start offset applying `c2, c3 < 438`, per-record `u8 < 19` and `u8 < 23`, with and
without the 24-byte trailing-u32 block. **Zero exact fits.**

### Attempt 7 — corrected window, forward AND backward — still zero fits

The archive class was read (above) and it **does** frame sections, so the one authorised re-test
was run. Two things changed versus attempts 3-6: the window moved back 12 bytes (base 0), and the
parse was also run **backwards** from the section end, which removes the unknown bulk length `G`
from the search entirely — the end is known exactly, and the tail grammar is rigid.

| run | result |
|---|---|
| forward, every start, ±24-byte tail, loader bounds | **0 fits, 59/59 files** |
| backward from the end, solving each count in turn | **0 fits, 59/59 files** |

The backward parse is the stronger of the two and it is conclusive: **the tail
`u32 c2 ; c2 x {u8,u8,u32} ; u32 c3 ; c3 x {u8,u8,u32}` is not present at the end of this
section**, with or without the six trailing `u32`s, under the loader's own bounds. Stop treating
the flat grammar as the description of instance 0.

### But the section's SHAPE is now measured `[CONFIRMED, 59/59]`

Two independent measurements agree on the layout, which is the first real progress here:

**1. The size formula.** For every one of the 59 files there is exactly one
`N ∈ {128, 192, 256}` with `size − 3·N² ∈ (0, 4096)`:

```
size(zone instance 0)  =  3·N²  +  tail        N = 128 | 192 | 256   (the three map sizes)
```

`tail` is **900 in 34 of the 59 files** — every unplayed terrain and starter town, at *both*
N=192 and N=256 — and larger only in played cities. **Every tail is a multiple of 6**
(900, 1026, 1086, 1122, 1134, 1200, 1206, 1236, … 1452). A constant 900-byte floor plus a
6-byte-per-element variable part is exactly the shape of a fixed header followed by the
`{u8, u8, u32}` records the loader reads.

**2. The first N² bytes are a low-entropy raster.** Measured per plane:

| file | N | plane 0 = `[0, N²)` | plane 1 | plane 2 |
|---|---|---|---|---|
| Berlin | 256 | **H = 2.13, 14 distinct byte values** | H = 7.95 | H = 7.98 |
| Farmsville | 192 | **H = 0.58, 9 distinct byte values** | H = 7.55 | H = 7.58 |

Exactly `N²` bytes containing only 9-14 distinct values, followed by a hard entropy jump. That is
a **one-byte-per-tile zone raster** at the head of the section, and it pins `N` independently of
the size arithmetic.

`[UNCERTAIN]` what the remaining `2·N²` bytes are. They are not uniform noise: the byte at `N²`
begins a structured `u32` run — Berlin `3, 3000, 1027, 5000`, Farmsville `3, 3000, -397, 5000`
(same first, second and fourth value, city-specific third) — after which entropy rises. No code
has been read for that region, and "2 bytes per tile" is arithmetic, not evidence.

The section's last bytes are a clean run of small `u32`s in every file (Berlin
`… 0, 1, 132, 74, 54, 58, 50, 82`; Farmsville `… 1, 90, 170, 0, 0, 0, 3`), consistent with the
saver's six trailing `u32` writes `[CONFIRMED @0x100320e7:109-118]` — but the records that should
precede them do not parse, so the six are not asserted as located.

### ⭐ Zone plane 0 decoded: each byte is a ZONE-DEVELOPER SLOT INDEX `[CONFIRMED, 59/59]`

Resolved 2026-08-16. The `N*N` raster at the head of the zone blob is **one byte per tile, and
that byte is an index into the 23-slot zone-developer table** — the same table whose non-NULL
slots each get a 4-byte id section.

**Evidence 1 — `0x00` is "unzoned".** All **21 `.sct` terrain files are 100% `0x00`**, with no
other value anywhere in them. Developed saves are 67.7% zero, starter towns 97.6%. Bare land
has exactly one value and it is zero.

**Evidence 2 — every other value is a declared slot, in all 59 files.** Each file states its own
occupied-slot set (one 4-byte section per non-NULL slot, `instance == slot + 1`). Comparing that
per file against the set of non-zero raster bytes:

| result | files |
|---|---|
| raster values are a strict **subset** of the declared slots | 22 |
| raster values ⊄ slots, and the **only** outlier is `0x16` | 37 |
| any other outlier | **0** |

A subset is expected — a city need not use every zone type. Across all 59 files **no value other
than `0x16` ever falls outside that file's own declared slot set.** The observed value set
`{1,2,3,5,6,7,9,10,11,14,15,17}` is exactly the set of occupied slots, and the gaps
(`0,4,8,12,13,16`) are exactly the NULL slots.

**Evidence 3 — the index is a byte in code.** The slot registrar `FUN_10032694` masks its index
argument to a byte before using it: `uVar2 = param_1 & 0xff;` then writes
`this + uVar2*8 + 0x18c` and `this + uVar2*8 + 400` `[CONFIRMED @0x10032694]`. A byte-wide slot
index is exactly what a one-byte-per-tile raster supplies.

This ties three previously separate things together: the raster, the twelve 4-byte sections, and
the 23-slot table are one mechanism. The three-groups-of-three id pattern (slots 1-3 →
`0x619ba64e`, 5-7 → `0x41a3adc1`, 9-11 → `0xe1a53b30`) is therefore three developer classes at
three density tiers, though **which class is R, C or I is still not determined**.

### ⭐ The developers are NAMED: R, C, I and Landfill `[CONFIRMED]`

All six slot ids are registered as GZCOM classes in the SIMRCI registration `FUN_10036382`
`[CONFIRMED @0x10036382]`, each with a factory, each factory with a constructor — and **each
constructor loads its own named `SC3Tune.INI` section**. That is the identification, from
literal strings in the code, not from address locality:

| slots | id | factory | ctor | `SC3Tune.INI` section in the ctor |
|---|---|---|---|---|
| 1, 2, 3 | `0x619ba64e` | `0x100367d9` | `0x10028198` | **`ResidentialZoneDeveloper`** |
| 5, 6, 7 | `0x41a3adc1` | `0x1003680e` | `0x1000f022` | **`CommercialZoneDeveloper`** |
| 9, 10, 11 | `0xe1a53b30` | `0x10036843` | `0x10016290` | **`IndustrialZoneDeveloper`** |
| 17 | `0x82348de5` | `0x100368dc` | `0x100194cf` | **`LandfillZoneDeveloper`** |
| 15 | `0x82d2d72b` | `0x10036878` | `0x1002c73f` | none — no strings in the ctor |
| 14 | `0xc1f81e7e` | `0x100368aa` | `0x10004447` | none — no strings in the ctor |

So the R/C/I × three-density-tier reading is **confirmed**: three slots per class, one shared
class id each, the density distinguishing the three instances. `[UNCERTAIN]` which of the three
slots in a group is low/medium/high — the counts are not monotonic (Berlin runs 2 > 3 > 1), so
do not assume slot order is density order.

> Address locality would have produced the same R/C/I answer here, and it is still not
> evidence — this document records a near-miss that punished exactly that reasoning. The INI
> section names are what settle it.
>
> Note also that this document previously stated the six ids "occur nowhere in any binary's
> decompiled text". That was true of the **base-12** values, which were wrong. All six correct
> values are in one function.

### `0x16` resolved: the raster reader classes it as COMMERCIAL `[CONFIRMED @0x1001deca]`

`FUN_1001deca` reads a raster value into `local_d` and partitions it three ways:

```c
if (((local_d == 1) || (local_d == 2)) || (local_d == 3))            { ... }   // Residential
else if (((local_d == 5) || (local_d == 6)) ||
         ((local_d == 7 || ((local_d == 0xe || (local_d == 0x16)))))) { ... }   // Commercial
else if ((((local_d == 9) || (local_d == 10)) || (local_d == 0xb)) ||
         (local_d == 0xf))                                           { ... }   // Industrial
```

That answers three things at once:

- **`0x16` (22) is handled as commercial by this reader.** It is not a developer slot — no file
  declares one — but the branch groups it with 5/6/7. `[UNCERTAIN]` what it actually is. Note
  the grouping is one reader's behaviour, not necessarily the tile's identity: counting `0x16`
  as commercial flips residential-above-commercial from 14 of 15 saved cities to 12 of 15,
  which is a hint that it is not simply another commercial zone. That is weak and nothing is
  concluded from it; it is recorded so the next reader does not treat "commercial" as settled.
- **Slot 14** (`0xc1f81e7e`, the ctor with no INI strings) is also **commercial-side**.
- **Slot 15** (`0x82d2d72b`, likewise no strings) is **industrial-side**.

The three groups the reader uses match the three INI-named developers exactly, which is an
independent confirmation of the naming above: the class names and the reader's partition were
derived from different evidence and agree.

> ⚠️ **The `+0x188` vs `+0x18c` offset discrepancy is NOT settled.** The saver reads the slot
> record at `this + i*8 + 0x188` (object) / `+0x18c` (id); the registrar `FUN_10032694` writes
> `+0x18c` (pointer) / `+0x190` (value). The two are perfectly consistent under a **4-byte
> difference in `this`**, which the class's layout makes plausible — the factory returns
> `object+0x10` while the saver's base-class call implies `object+0x14`. But `FUN_10032694` has
> **zero static callers** (it is vtable-dispatched), so the text export cannot say which `this`
> it receives. Resolution needs `VtableProbe.java` on live Ghidra. Until then, do not build a
> parser on either offset.

### ⭐ THE MAP DIMENSION IS IN THE FILE AFTER ALL `[CONFIRMED, 59/59]`

Found 2026-08-16 while building `re/tools/city_sections.py`. This document concluded that the
zone section "may simply not be parsable standalone" because its reader takes `rowCount` and
`rowBytes` from the object, and then **falsified** `SC3WorldLayer` as the source of the
dimensions. Both of those stand. The source is a **different section**:

```
{type 0x406b1196, group 0x80ab8ab0}   =   frame(8) + N*N bytes + 8-byte trailer
                                          so  N = isqrt(size - 16)
```

That is the SIMGEOM tile grid (saver `0x1000beec`). **N is 128, 192 or 256 — the three map
sizes — and it is readable directly from the section size in all 59 files.**

**Two independent derivations agree in 59 of 59 files**, neither built from the other:

| source | relation |
|---|---|
| the tile-grid section | `size - 16 == N*N` |
| the zone blob | `size == 3*N*N + tail`, `tail == 900 + 6k` |

So the grid section supplies the dimension the zone section lacks.

> ⚠️ **Correction (same day).** This paragraph first also claimed the agreement "corroborates
> the 3 planes of N*N reading". **It does not, and that reading is now FALSIFIED** — see
> attempt 8 below. What the two derivations agree on is **N**, and therefore the *arithmetic*
> decomposition `size = 3*N*N + tail`. Only the FIRST `N*N` is a plane. Agreeing on a size
> relation is not evidence about what fills it.

**A stride test confirms both are real rasters, independently of the arithmetic.** Vertical
coherence (fraction of vertically adjacent bytes that are equal) peaks exactly at `N`:

| file | section | N-2 | N-1 | **N** | N+1 | N+2 |
|---|---|---|---|---|---|---|
| Berlin (N=256) | zone plane 0 | .593 | .673 | **.796** | .673 | .596 |
| Berlin (N=256) | tile grid | .829 | .839 | **.859** | .843 | .832 |
| Farmsville (N=192) | zone plane 0 | .944 | .955 | **.973** | .955 | .944 |
| Farmsville (N=192) | tile grid | .817 | .823 | **.837** | .816 | .815 |

Read at a wrong stride a raster shears and coherence drops; it peaks at the claimed `N` in
every case. `[CONFIRMED]` the first `N*N` bytes of the zone blob are a **1-byte-per-tile
raster** and the grid section is an `N*N` byte raster.

`[UNCERTAIN]` what either raster's byte values mean. Berlin's zone plane has 14 distinct values
and its tile grid 18; no consuming code has been read for either.

### Attempt 8 — NOT a grammar sweep, and it falsifies the three-plane reading

Attempts 1-7 all searched for a grammar fit. Attempt 8 asked a **decidable** question instead,
using information those attempts did not have (N is now known per file, and plane 0 is a proven
raster): **is the middle `2*N*N` raster data at all?**

The instrument is the same stride-coherence test that confirmed plane 0. Result:

| region | coherence at N-1 / **N** / N+1 | distinct byte values |
|---|---|---|
| plane 0 (Berlin) | .673 / **.796** / .673 | 14 |
| plane 1 (Berlin) | .011 / **.013** / .012 | **256** |
| plane 2 (Berlin) | .004 / **.005** / .004 | **256** |
| middle as u16 (stride 2N) | .008 / .007 / .008 | — |

**No peak at any stride, and coherence two orders of magnitude below plane 0.** Farmsville and
Europolis behave identically. So:

> **`[FALSIFIED]` the zone blob is NOT three N*N planes.** Only the first `N*N` is a raster.
> The following `2*N*N` is not spatially coherent at stride `N`, `2N`, or anything near them.

Statistics of the middle (Berlin, 131,072 bytes): all 256 byte values present, chi-square
against uniform 1,781 on 255 df, byte-repeat rate ~0.009 at every lag tried (1, 2, 3, 4, N, 2N)
against 0.0039 for pure random. Only 1.1% zero bytes, where plane 0 is 62.5% zero. That is
high-entropy packed data — **not a map layer, not per-tile 16-bit fields with any regularity,
and not QFS** (a `0x10FB` byte pair does occur, but ~2 occurrences are expected by chance in
128 KB and it does not decode).

`[UNCERTAIN]` what the middle is. It is consistent with a densely packed or hashed structure;
nothing here identifies it.

**What this does NOT change:** `N`, plane 0, the slot-index meaning, and the developer names all
stand — they rest on separate evidence. What dies is the inference that the size arithmetic
implied three planes. **The size relation was never evidence about content**, and treating it as
such is the mistake this attempt caught.

### ⭐⭐ THE GRAMMAR IS FOUND. It starts at `N*N` and it fits `[CONFIRMED, 59/59]`

Reading the middle's *start* rather than sweeping for it found it immediately. At offset `N*N`
the bytes are not noise — they are the grammar's first list:

```
Berlin      3 | (3000, 1027) (5000, -1823) (8000, -2189)
Farmsville  3 | (3000, -397) (5000,    18) (8000,     0)
Europolis   3 | (3000,    0) (5000,  -158) (8000, -1040)
```

`u32 count` then `count x {u32, u32}` — exactly the c1 list the loader reads from the map at
`this+0x2a4`. **The keys are always 3000, 5000, 8000** and never anything else; only the values
vary per city.

Parsing the full grammar forward from `N*N` in every shipped file:

| result | files |
|---|---|
| parses cleanly (`c1` list, two 23-byte blocks, `c2` list, `c3` list) | **59 / 59** |
| `c1 = 3`, consumes **82** bytes | 25 |
| `c1 = 0`, consumes **58** bytes | 34 |
| `c2` and `c3` | **0 in every file** |

`82 = 4 + 3*8 + 23 + 23 + 4 + 4` and `58 = 4 + 0 + 23 + 23 + 4 + 4`. Both exact.

### Why eight attempts failed

**Every one of them required the grammar to consume exactly to the section end.** It never does.
The grammar occupies 58 or 82 bytes starting at `N*N`, and roughly `2*N*N` bytes follow it that
it does not describe. That single constraint rejected the correct parse at the correct offset in
all 59 files, in every sweep, forwards and backwards.

Two further consequences worth recording:

- **`c2` and `c3` are empty in all 59 shipped files.** The loader's per-record bounds
  (`u8 < 0x13`, `u8 < 0x17`) could therefore never be validated against bytes, because there
  are no records anywhere. Sweeps were filtering on constraints with nothing to constrain.
- The base row array is **one** `N*N` plane, not three. `rowCount * rowBytes == N*N`, which is
  consistent with the falsification above and with plane 0 being the only coherent raster.

`[UNCERTAIN]` what the keys 3000 / 5000 / 8000 index.

### ⭐ The `2*N*N` is a DELEGATED WRITE — the recorded grammar was incomplete `[CONFIRMED]`

Reading `FUN_100320e7` end to end, instead of trusting this document's summary of it, found
**two writes after the `c3` list that were never recorded** `[CONFIRMED @0x100320e7:107-108]`:

```c
vt+0x84((int)this + 0x3c, 0x17);                                    // a THIRD 23-byte block
(**(code **)(*(int *)((int)this + 0x268) + 4))(param_1, local_8);   // DELEGATED WRITE
```

then the six trailing `u32`s. So the true section layout is:

```
[ N*N raster ][ c1 list ][ 23 ][ 23 ][ c2 ][ c3 ][ 23 ][ sub-object at this+0x268 ][ 6 x u32 ]
```

**Verified against the bytes:** the last 24 bytes parse as six small `u32`s in **59 of 59**
files. Working inwards from there, the delegated write occupies `2*N*N + 795..1323` bytes — so
**the entire high-entropy region is one sub-object serialising itself**, roughly two bytes per
tile plus its own header. That is why it shows no raster coherence at stride `N`: it is not the
zone layer's data and is not laid out like it.

The sub-object sits at **object+0x27c**, vtable **`PTR_FUN_1004d2bc`**, installed by the
SC3ZoneLayer ctor (`param_1[0x9f]`), fields initialised by `FUN_10031267`
`[CONFIRMED @0x100310f5, 0x10031267]`. Its writer is **slot 1 (`vt+4`)** of that vtable.

### ⭐ Resolved on live Ghidra: the `2*N*N` is a `u16`-per-tile vector `[CONFIRMED, 59/59]`

`VtableDump` on `PTR_FUN_1004d2bc` gives **slot 1 = `FUN_1004361d`** (260 bytes), and confirms
the vtable is installed by the SC3ZoneLayer ctor `FUN_100310f5`. Reading it
`[CONFIRMED @0x1004361d]`:

```c
vt+0x70(u8  this+0x04);   vt+0x88(u32 this+0x08);   vt+0x68(bool this+0x0c);
vt+0x98(this+0x10); vt+0x98(this+0x18); vt+0x98(this+0x14);
vt+0x98(this+0x1c); vt+0x98(this+0x20);
count = (*(this+0x28) - *(this+0x24)) >> 1;          // a vector of 2-BYTE elements
vt+0x88(count);
while (count--) vt+0x78( *(u16 *)(*(this+0x24) + count*2) );   // each u16, in REVERSE
vt+0x98(this+0x30); vt+0x98(this+0x34); vt+0x98(this+0x38);
```

So the high-entropy region is **`N*N` 16-bit values, one per tile**, written individually and in
reverse order — a second per-tile plane at `u16` width, which is why it is `2*N*N` bytes and why
it never looked like a byte raster.

**Verified against the bytes at an exactly predicted position:** the writer emits, after the
vector, three `u32`s (`vt+0x98`) and then the saver's six trailing `u32`s — 36 bytes. So the
count must sit at `end - 36 - 2*N*N - 4`. **The `u32` there equals `N*N` in 59 of 59 files.**
That is a single predicted offset, not a search.

### ⭐ The `u16` plane is a PERMUTATION, not per-tile game data `[CONFIRMED]`

Extracting the vector and comparing it to the zone raster answers what it is:

- **In all 59 files the `N*N` values are pairwise DISTINCT** — no value repeats.
- In the 47 files with N=256 the vector is **exactly the permutation of `0 .. 65535`**, i.e.
  every 16-bit value once. (For N < 256 the values are still all distinct but are not the range
  `0 .. N*N-1`; `[UNCERTAIN]` what range they cover.)

A sequence of `N*N` distinct indices is a **traversal order**, not map content. That explains
every statistical property measured earlier at a stroke: perfectly uniform byte histogram, no
spatial coherence at any stride, ~1.1% zeros — all forced by it being a permutation.

It is consistent with the zone developers shuffling tile visit order to avoid directional bias
(they do carry RNG state), but **nothing here proves what consumes it**, so that is a lead and
not a finding.

The practical consequence for a toolkit: **this region is not worth decoding as content.** It is
2 bytes per tile of scheduling state.

`[UNCERTAIN]` the widths of `vt+0x70` and `vt+0x78` are still inferred from their arguments
(byte / `u16`) rather than pinned from a GZResourceD implementation. `vt+0x98` WAS pinned — see
the correction below.

### The gap before the `u16` vector — measured, and it points at `vt+0x98`

Between the grammar's end and the `u16` count there is a gap of **1,000–1,270 bytes**, and it is
**not constant**: Mount Herrang (N=128) 1,000, Farmsville (N=192) 1,012, Berlin (N=256) 1,270.
The saver's tail was re-read in full and contains no writes beyond the 23-byte block at
`this+0x3c`, the delegated call, and the six `u32`s — so the gap is **inside the sub-object's
own header**.

That header, as written by `FUN_1004361d`, is `u8 + u32 + bool + 5 x vt+0x98` — about **26
bytes** if `vt+0x98` is a scalar. It is not: something in there is writing ~1,000 bytes more.

> ~~**`vt+0x98` is therefore NOT a scalar write.**~~ **`[FALSIFIED]` — I pinned it and I was
> wrong.** `VtableDump` on the stream vtable `PTR_FUN_1001cb34` gives **slot 38 (`+0x98`) =
> `FUN_1000c1d6`, which is the SAME function as slot 34 (`+0x88`)** — the already-pinned
> `Write(&value, 4)`. So `vt+0x98` is a plain u32 write, the sub-object header really is ~26
> bytes, and my inference from "it must be the only thing big enough" was reasoning backwards
> from the gap to a cause instead of measuring the cause.
>
> **The gap was then closed by testing the remaining suspect — and the suspect was right.**

### ⭐ The saver and loader are NOT mirrors at the tail `[CONFIRMED]`

Listing both call sequences in order and comparing them head to tail — which had never been
done, despite both functions having been "read" several times — shows they agree exactly up to
the third 23-byte block and then **diverge**:

| | saver `0x100320e7` | loader `0x10031c85` |
|---|---|---|
| block C | `vt+0x84(this+0x3c, 0x17)` | `vt+0x34(this+0x3c, 0x17)` ✓ mirror |
| next | **`(*(this+0x268))->vt+4(param_1, stream)`** | **`(*(this-0x14))->vt+0xc()`** then `piVar1->vt+0x10()`, `piVar1->vt+0x34(local_18, local_14, &local_6)`, `vt+0x10()`, `vt+0xc()` |
| then | 6 × `vt+0x88` | 6 × `vt+0x38` ✓ mirror |

**The loader never calls the object at `this+0x268`.** It reaches the same region of the stream
through the *base* subobject (`this-0x14`) and an object `piVar1` obtained from it. So the two
sides are genuinely asymmetric exactly where the unexplained ~138 bytes and the `u16` region sit.

**This matters beyond the byte count.** The mirror-pair assumption is what this document has
leaned on throughout — "the grammar is confirmed from BOTH the saver and the loader" was the
headline claim that made eight failed sweeps so confusing. It is now clear the two functions
**do not describe the same byte sequence at the tail**, so cross-confirming them there proves
nothing. The agreement up to block C is real; past it, each must be read on its own terms.

#### `piVar1` is not a stream — the loader's divergent block is a POST-LOAD RECOUNT `[CONFIRMED @0x10031c85:144-163]`

```c
piVar1 = (int *)((int)this + -0x14);              // the BASE subobject, i.e. the grid itself
for (y = 0; y < piVar1->vt+0xc();  y++)           // vt+0xc  = row count
  for (x = 0; x < piVar1->vt+0x10(); x++) {       // vt+0x10 = column count
    piVar1->vt+0x34(y, x, &local_6);              // fetch the tile value at (y, x)
    if (local_6 < 0x17)                           // < 23 -- a zone-developer SLOT INDEX
      *(int *)((int)this + local_6 * 4 + 0x3c) += 1;   // histogram it
  }
```

**It reads nothing from the stream.** It walks the grid that was already loaded and rebuilds a
**23-entry `u32` histogram of zone-developer slot usage** at `this+0x3c` — derived state,
recomputed rather than trusted.

Three things follow:

1. **The saver's delegated write to `this+0x268` has no counterpart in the loader at all.** The
   `u16` permutation and its ~138-byte header are **written but never read back** by this
   loader. Consistent with the permutation being regenerable scheduling state — and it means a
   toolkit does not need them to reconstruct a city.
2. **Independent confirmation of the zone-raster decode.** The guard `local_6 < 0x17` says tile
   values are slot indices `0..22` — arrived at from the loader, entirely separately from the
   file-side evidence (terrains all-zero, values ⊆ declared slots). It also confirms `0x16` (22)
   is an in-range tile value, not corruption.
3. `this+0x3c` is a **23-entry `u32` array (92 bytes)**, yet the saver writes only `0x17` = 23
   **bytes** from it. `[UNCERTAIN]` — that mismatch is unexplained and may be the same thread as
   the missing ~138 bytes.

### ✅ CONTRADICTION RESOLVED — and it was my own reading error `[CONFIRMED @0x10031c85:166]`

The loader **does** read the sub-object. It is an `if/else`, and I only listed one arm:

```c
else {
  cVar4 = (*(code *)**(undefined4 **)((int)this + 0x268))(param_1, local_c);   // SLOT 0
  if (cVar4 != '\0') cVar3 = (**(code **)(*local_c + 0x38))((int)this + 0x260);
}
```

`(*(code *)**(undefined4 **)(this + 0x268))` is **slot 0** of the object at `this+0x268` — and
`VtableDump` on `PTR_FUN_1004d2bc` already showed **slot 0 = `FUN_1004350e` (271 bytes)**
alongside **slot 1 = `FUN_1004361d` (260 bytes)**. Slot 0 reads, slot 1 writes. They are a
mirror pair after all.

**Why I missed it:** my call-listing regex matched `(**(code **)(*x + 0xNN))(` — the form with an
explicit slot offset. A slot-0 call has no `+ 0xNN` and is written `(*(code *)**(...))(`, so it
never appeared in the list I compared against the saver. **The asymmetry I reported was an
artefact of how I extracted the calls, not a property of the code.**

Three claims made earlier today are therefore **withdrawn**:

- ~~"The saver and loader are NOT mirrors at the tail."~~ They are, via slot 0 / slot 1.
- ~~"The `u16` permutation is written but never read back."~~ It is read back.
- ~~"Regenerable scheduling state a toolkit does not need."~~ Unsupported — it is loaded.

The `u16` data being a permutation still stands; that came from the bytes, not from this.

#### What selects the two arms: it is a FAILURE FALLBACK, not a version flag `[CONFIRMED @0x10031c85:139-140]`

```c
if ((cVar4 == '\0') ||                                            // any earlier read failed
    (cVar3 = (**(code **)(*local_c + 0x34))((int)this + 0x3c, 0x17), cVar3 == '\0')) {
    ... recompute the 23-entry histogram by walking the loaded grid ...
} else {
    ... (*(code *)**(this + 0x268))(param_1, stream)   // read the sub-object
}
```

`cVar4` is the running success flag threaded through every preceding read, and the block C read
is performed **inside the condition itself**. So:

- **Normal path:** block C (23 bytes) is consumed, then the sub-object is read, then the six
  `u32`s — exactly the saver's order, fully mirrored.
- **Failure path:** if any earlier read failed, or block C fails, the loader **rebuilds the slot
  histogram from the already-loaded grid** rather than trusting the file.

So the recount is **graceful degradation**, not a format variant. The histogram at `this+0x3c`
is derived data the loader can always reconstruct, which is why it is safe to fall back on.

That closes the tail: the serialiser **is** a mirror pair on the normal path, and the earlier
"asymmetry" was entirely an artefact of my call extraction plus reading only the fallback arm.

### 🔴 The contradiction as it stood before the resolution above

The base reader `FUN_1001b4b4` consumes exactly `rowCount * rowBytes` `[CONFIRMED @0x1001b4b4]`
— `this+4` rows of `this+8` bytes, no more. Combined with everything else now pinned, the two
sides do not add up:

| | saver | loader |
|---|---|---|
| base | `N*N` | `N*N` |
| grammar | 58 / 82 | 58 / 82 |
| block C | 23 | 23 |
| sub-object | **~132,335 (Berlin)** | **nothing** |
| six `u32`s | 24 | 24 |
| **total** | **= section size** ✓ | **≈ `N*N` + 129** ✗ |

So the loader would read its six trailing `u32`s at `N*N + 105`, which lands **inside** the
sub-object region — the wrong bytes. The game loads cities correctly, so **at least one fact
recorded in this document is still wrong.**

Candidates, none tested:

1. The base read is **not** `N*N`. But it cannot be `3*N*N` either: the `u16` permutation sits at
   the *end* of the section, so `3*N*N` lands inside it.
2. The `c1` list at `N*N` is a coincidence. Against that: the keys are `3000/5000/8000` in all
   25 developed files and the parse is exact.
3. The loader's six `u32` reads are not the mirror of the saver's six `u32` writes — plausible,
   given the tail is already proven asymmetric.
4. The sub-object region *is* consumed, by something between block C and the `u32` reads that
   the decompilation does not show.

**Do not resolve this by arithmetic.** Four inference attempts at this gap have now failed
(`vt+0x98`, the block size, the mirror assumption, and this). The next step is to read the
loader's stream object across the whole function and track its position, or to breakpoint the
loader under a debugger — the byte-fitting approach is exhausted.

What is unaffected, because it rests on separate evidence: the `N*N` zone raster and its
slot-index meaning, the R/C/I/Landfill developer names, the `u16` permutation, the map dimension
`N`, and the section frame.

### ⚠️ The "23 elements of 4 bytes" reading is FALSIFIED — the blocks ARE 23 bytes

**Read this before the section below, which is left in place as the record of a wrong turn.**

`VtableDump` on the other two stream flavours shows **all three share `+0x84 = FUN_1000c1ad`**,
so "a different flavour scales the length" is dead. And the disassembly of the call site is
unambiguous `[CONFIRMED @0x100321bb]`:

```
100321b5  LEA  EDX,[ESI + 0xf4]
100321bb  PUSH 0x17                     ; length = 23, literally
100321bd  PUSH EDX
100321c0  CALL dword ptr [EAX + 0x84]   ; Write(ptr, len) in BYTES
```

**So each block is 23 bytes and the pair is 46.** What the `S=4` sweep below actually
established is narrower than what it was written up as: with **184** bytes attributed to the
"block" term the distance to the `u16` count is constant in all 59 files, whereas the true
blocks account for only 46. That is still a real result — **there are ~138 CONSTANT bytes
between the two blocks and the `c2` count that nothing in the decompiled saver accounts for** —
but attributing them to the block size was fitting a parameter, not identifying a structure.

This is the **second** wrong inference in a row on this same gap (the first was `vt+0x98`). Both
came from the same move: taking a number that made the arithmetic close and calling it a cause.
The gap remains open. What is now pinned about it: it is ~138 bytes, it is constant across all
59 files, and it sits between the two 23-byte blocks and the `c2` count.

The end-to-end layout below is therefore **not** confirmed as written; everything from the
blocks to the `u16` count needs re-deriving with 46-byte blocks.

---

### The `S=4` sweep — kept as the record, but see the falsification above

Solving for the block element size instead of assuming it: parse from `N*N` with the blocks at
`2 * 0x17 * S` bytes, for every `S`, and ask which `S` makes the distance from the grammar's end
to the (independently known) `u16` count **constant across files**.

| S | files parsing | distance to count | files agreeing |
|---|---|---|---|
| **4** | 59 | **118** | **59** |
| 3 | 59 | 710 | 34 |
| 2 | 59 | 756 | 34 |
| 1 (the old assumption) | 59 | 802 | 34 |

`S = 4` is unambiguous: **all 59 files**, one constant. And that constant decomposes exactly:

```
118  =  92  (block C at this+0x3c, also 23 x 4)  +  26  (the sub-object header)
 26  =  u8(1) + u32(4) + bool(1) + 5 x u32(20)              <- exactly as FUN_1004361d writes it
```

**The zone section is now accounted for end to end with no unexplained bytes:**

```
[ N*N u8 zone raster ]
[ u32 c1 ][ c1 x {u32,u32} ][ 92 ][ 92 ][ u32 c2 ][ c2 x 6 ][ u32 c3 ][ c3 x 6 ]
[ 92 ][ u8 u32 bool 5xu32 ][ u32 N*N ][ N*N x u16 permutation ][ 3 x u32 ][ 6 x u32 ]
```

`c2` and `c3` are **not** zero under the corrected block size — the earlier "always 0" reading
was an artefact of parsing 46 bytes where 184 belong, and their variation is what made the gap
scale with city size.

> ⚠️ **One code-side loose end.** `vt+0x84` is pinned as `FUN_1000c1ad` = `Write(ptr, len)` with
> `len` in **bytes**, yet these call sites pass `0x17` and the bytes say 92. So either the
> decompiler dropped a scale at this call site, or the zone saver holds a different one of the
> three stream flavours (`PTR_FUN_1001cb34` / `1001cef0` / `1001d130`) whose `+0x84` differs.
> The byte evidence is 59/59 and stands; the reconciliation does not, and is the next read.

One structural detail *is* readable at the end of that header. The bytes immediately before the
count contain **`N-1` twice** — `0xff` for N=256, `0xbf` for N=192, `0x7f` for N=128
`[CONFIRMED, 3 files]` — i.e. grid extents in the form `0 .. N-1`. So the sub-object is
grid-shaped and knows its own dimensions, which is consistent with it holding one `u16` per tile.

### ⭐ The `+0x188` vs `+0x18c` discrepancy is SETTLED `[CONFIRMED]`

`VtableProbe` on both functions shows they belong to the same class but **different subobjects**:

| function | vtable | slot | installed at |
|---|---|---|---|
| saver `FUN_100320e7` | `PTR_LAB_1004d198` | 10 (`+0x28`) | `param_1[5]` = **object+0x14** |
| registrar `FUN_10032694` | `PTR_LAB_1004d1e0` | 22 (`+0x58`) | `param_1[4]` = **object+0x10** |

Both installed by `FUN_100310f5` and `FUN_10031357` — multiple inheritance, two subobjects
**exactly 4 bytes apart**. So:

```
saver     this+0x188  =  object + 0x14 + 0x188  =  object+0x19c
registrar this+0x18c  =  object + 0x10 + 0x18c  =  object+0x19c    <- the same field
saver     this+0x18c  =  object+0x1a0  ==  registrar this+0x190    <- the same field
```

**Neither reading was wrong.** The slot record is
`{ void* developer at object+0x19c + i*8, u32 id at object+0x1a0 + i*8 }`, and the two functions
simply address it through `this` pointers 4 bytes apart. This also independently confirms the
saver's `this = object+0x14`, which had only been inferred from its `this-0x14` base call.
>
> The general lesson is worth more than the finding: this document's grammar was derived from
> the saver twice and the loader once, and was **still missing two writes**. Eight attempts
> trusted the summary instead of re-reading the function.

### Where that leaves it

The archive question is **answered**: sections are framed, the frame is `{u16 version, u8 flags,
u8 extra, u32 0xDEADBEEF}`, it is opt-in per class, and `SC3ZoneLayer` does not use it. The real
payoff was the offset base: 12 -> 0.

The zone grammar remains unsolved after seven attempts, but the failure has moved. It is no
longer "the bytes are opaque" — the section is `N²` raster + `2·N²` + a 900+6k tail, and the flat
`{u8,u8,u32}` list grammar provably is not at the end of it. **Do not sweep the grammar again.**
The next evidence has to come from the `if (cVar != '\0')` guards in the saver (which can skip
whole writes) or from a debugger, not from more byte fitting.

## Second worked example: SC3WorldLayer — the city header `[CONFIRMED]`

`SC3WorldLayer` (GZCLSID `0xe11bddf6`, **SIMMISC**) is registered at `0x1002a204` with factory
`FUN_1002a606`. Its serialiser pair is `FUN_1002776c` (**SAVE**, 6 × `vt+0x88`, 0 reads) and
`FUN_10027563` (**LOAD**, 4 × `vt+0x38`, 0 writes) — the mirror-pair test picks them out cleanly.

**The section-key pattern generalises** `[CONFIRMED @0x1002776c]`:

```c
local_20 = 0x206c6e7c;      // the same generic section TYPE
local_1c = 0xe11bddf6;      // group = SC3WorldLayer
FUN_10027897(auStack_60, &local_20);   // open the section with that key
```

So a second, unrelated class in a different module uses the identical `{0x206c6e7c, classId}`
convention. The saver then writes via sub-objects at `this+0x28`, `+0x58`, `+0x70`, `+0x88`,
`+0x40`. `[UNCERTAIN]` the exact field list — Ghidra's decompilation of this function is
**degraded** (call arguments dropped, visible as `uStack_58 = <return address>` assignments), so
only the sub-object offsets are legible, not what each writes.

### The section content

**725 bytes, instance 0, exactly one per city, in all 59 files.**

```
+0x00  u32  0x00020002        version/flags, identical in all 59
+0x04  u32  0xDEADBEEF        the marker again, per-section this time
+0x08  u32  varies per city   e.g. Berlin 514,166 · Europolis 1,422,548 · Farmsville 23,396
+0x0c  u32  varies per city   e.g. Berlin 425,561 · Europolis 1,231,165 · Farmsville 20,789
+0x10  u32  0x96 (150)        identical in all 59
+0x14  ...  zeros, then 0xfffff830-style negative-looking dwords
```

`[UNCERTAIN]` **the two varying u32s are probably population-like counters** — the magnitudes are
city-sized, they differ per city, `+0x0c` is consistently ~83-89% of `+0x08`, and both track the
size of that city's zone blob (Farmsville smallest on all three, Europolis largest). **This is
NOT confirmed**: no code that produces or consumes them has been read, and the in-game values
have not been checked. Treat as a lead, not a fact.

Only 23 of the 59 files have distinct leading-40-byte patterns, so many terrains/starter towns
share identical headers — consistent with unplayed maps.

## The layer roster: save sections ↔ city-sim fields `[CONFIRMED]`

`SIMCITY.DLL FUN_10005e3e` is the city simulator's **layer-acquisition function**. It makes 33
calls of the form `FUN_10006655(CLSID, &tmp, IID, &citySim->field)`, wiring every layer/service
into a fixed offset on the city-sim object `[CONFIRMED @0x10005e3e]`. (Arg 1 is the CLSID — it
matches the pinned class ids — and arg 3 is the sibling IID, e.g. `SC3WorldLayer` `0xe11bddf6`
with IID `0x811bdde9`, sharing the `1BDD` middle.)

**10 of those 33 CLSIDs appear as `group` in the save-file section table**, which maps saved data
straight onto the running sim's fields:

| CLSID | IID | city-sim field | sections | class |
|---|---|---|---|---|
| `0x409ff3ba` | `0x80902c70` | `+0xb4` | 767 | **SC3ZoneLayer** |
| `0xe11bddf6` | `0x811bdde9` | `+0xc8` | 59 | **SC3WorldLayer** |
| `0xc0a81498` | `0x80a814ac` | `+0xd4` | 59 | SIMECO pollution layer (factory `0x1000e5c8`) |
| `0x20a7ae7f` | `0x80a24318` | `+0xd8` | 59 | |
| `0x00abf2ec` | `0x00abf2d9` | `+0xdc` | 59 | |
| `0xa0f42214` | `0xa0f42240` | `+0xe0` | 59 | |
| `0x20ec9849` | `0x80ec9834` | `+0xe8` | 59 | |
| `0xa106cf3d` | `0xa106cf30` | `+0xec` | 59 | |
| `0x02619041` | `0x82619039` | `+0x120` | 59 | |
| `0x422e28e8` | `0x022e288e` | `+0x104` | 49 | |

### The 7 unnamed persisted CLSIDs — registrations found, names NOT determined

Each of the 7 unnamed entries occurs **exactly once in SIMCITY** (the roster) and **three times
in its home module** — register + save + load, the established shape. Home modules and factories
`[CONFIRMED]`:

| CLSID | module | registration | factory | alloc |
|---|---|---|---|---|
| `0x20a7ae7f` | SIMSERV | `0x10010426` | `FUN_100104e3` | `0xe0` (224 B) |
| `0x00abf2ec` | SIMSERV | `0x10010426` | `FUN_1001055c` | `0xf0` (240 B) |
| `0xa0f42214` | SIMSERV | `0x10010426` | `FUN_1001059a` | `0xe0` (224 B) |
| `0x20ec9849` | SIMRCI | `0x10036382` | `FUN_1003669e` | `0x20` (32 B) |
| `0xa106cf3d` | SIMRCI | `0x10036382` | `FUN_100366d0` | `0x24` (36 B) |
| `0x02619041` | SIMADV | `0x1000102b` | `FUN_100012ac` | `0x150` (336 B) |
| `0x422e28e8` | SIMADV | `0x1000126e`'s registrar | `FUN_1000126e` | `0x1f0` (496 B) |

**Their human names are NOT determined** — and this was attempted properly, not skipped.

What was tried for the two SIMRCI ids, and why each attempt failed to prove anything:

| attempt | result |
|---|---|
| name strings in the module | SIMRCI has 5 `SC3*Layer` INI names; none is tied to these ids |
| code locality | ctor `FUN_1000e772` (`0x20ec9849`) sits ~1.4 KB from the `SC3ComLayer.ini` loader `FUN_1000eccd`; ctor `FUN_100158d3` (`0xa106cf3d`) sits beside the `SC3IndLayer.ini` loader `FUN_10015dc0`. **Suggestive, not proof** |
| do the ctors call the INI loaders? | **No.** Both ctors are 65/68 bytes: they call `FUN_10036ee3` and install a vtable. They never touch the loaders |
| are the loaders in the ctors' vtables? | **No.** `VtableDump` on `PTR_FUN_1004c208` (210 slots) and `PTR_FUN_1004c4a4` (43 slots) does not contain `FUN_1000eccd` or `FUN_10015dc0` |

So `0x20ec9849`→SC3ComLayer and `0xa106cf3d`→SC3IndLayer is an **attractive mapping with zero
supporting evidence**, and the 32/36-byte allocations argue against it outright — far too small
for a layer that owns a tuning INI. Not asserted. The INI loaders are almost certainly methods of
the *layer* classes, and these small objects are something else that merely lives nearby.

### Following the INI loaders' callers — closer, still not proof

`XrefProbe` gives each loader **exactly one** reference, an `UNCONDITIONAL_CALL` from a region
Ghidra never carved into a function `[CONFIRMED]`:

| INI loader | its single caller | ctor of the unnamed CLSID | that ctor's extent |
|---|---|---|---|
| `SC3ComLayer.ini` `0x1000eccd` | `0x1000e837` | `0x20ec9849` → `FUN_1000e772`; same vtable also installed by `FUN_1000e7e4` | `0x1000e7e4`–`0x1000e833` |
| `SC3IndLayer.ini` `0x10015dc0` | `0x1001599d` | `0xa106cf3d` → `FUN_100158d3`; same vtable also installed by `FUN_1001594a` | `0x1001594a`–`0x10015999` |

> ⚠️ **A wrong conclusion was nearly recorded here.** Both callers are `+0x53` from the second
> installer's start, which looked like "the call is inside the ctor that installs the vtable" —
> and that would have named both classes. **It is false.** Both installers are **80 bytes**, so
> they end at `0x1000e833` and `0x10015999`; the callers at `0x1000e837` and `0x1001599d` are
> **4 bytes past the end**. `VtableProbe` independently reports the loaders are *not* in any
> vtable slot at all.

What is true: each INI loader is called from **uncarved code immediately following** the second
ctor of the unnamed class, at an identical `+4`-past-the-end offset in both cases. That is strong
circumstantial linkage — but adjacency is not containment, and this file already records one
near-miss id (`0x029ca804` vs `0x029ca806`) that punished exactly that kind of reasoning.

**Names remain NOT determined**, and the carve was done — it did not close the gap:

`MakeFunctions.java` created all three callers (each **8 bytes**), and they are bare forwarding
stubs `[CONFIRMED]`:

```
1000e837  CALL 0x1000eccd   (SC3ComLayer.ini loader)   ;  1000e83c  RET 0x4
1001599d  CALL 0x10015dc0   (SC3IndLayer.ini loader)   ;  100159a2  RET 0x4
1002115d  CALL 0x10022ac6   (SC3ResLayer.ini loader)   ;  10021162  RET 0x4
```

8 bytes is the size of an MSVC adjustor thunk, so the obvious next guess was that a *secondary*
vtable holds the **stub** (which would explain why probing the *loader* found nothing). It does
not: `VtableProbe` on all three stubs returns **no vtable slot**, and `XrefProbe` on them returns
**zero references of any kind**.

So the chain is: INI loader ← exactly one stub ← *nothing statically reachable*. These stubs are
dispatched through a table Ghidra has not typed as data. **Read-only probing is exhausted here.**

A byte-scan of the whole module for the three stub addresses finds **zero occurrences** — they
are in no data table either.

> ⚠️ **Do not conclude "unreachable" from that scan.** An x86 `CALL rel32` encodes a
> *displacement*, not the target address, so a byte-scan for an absolute address **cannot find
> call sites by construction**. The scan only rules out *data* references. Combined with
> XrefProbe returning nothing, the real explanation is that the calling code **was never
> disassembled** — the same uncarved-region problem that hid the stubs themselves.

Remaining routes, in order of cost: (a) force-disassemble the whole region around
`0x1000e7e4`–`0x1000e900` (and the SIMRCI equivalents) so the callers become visible to
XrefProbe; (b) run the game under a debugger and breakpoint the loader. Until one lands,
`0x20ec9849` and `0xa106cf3d` stay unnamed.
SIMSERV's only class-name string is `\Sys\SC3FireLayer.INI`; SIMRCI has `SC3ComLayer.ini`,
`SC3IndLayer.ini`, `SC3ResLayer.ini`, `SC3ValveLayer.ini`, `\Sys\SC3ZoneLayer.INI`; SIMADV has
none at all. Adjacency to a string is not evidence of identity, so nothing is assigned here —
note in particular that the two SIMRCI ids allocate only **32 and 36 bytes**, which is far too
small for the Res/Com/Ind layers those INI names suggest, so the tempting mapping is very likely
wrong. Resolving these needs the INI-loading call sites (which file name each ctor opens).

The other 23 roster entries are layers/services that are **not persisted** (or are persisted
under a different id). Note `TrafficLayer` `0x029ca806` is in the roster at `+0xac` but the save
uses `0x029ca804` — which is why the near-miss was not treated as a match earlier; they are
distinct ids in the same family.

**This is the practical key to the format:** for any of the 10, the decode route is
CLSID → its module's serialiser (find via the `vt+0x38`/`vt+0x88` mirror-pair test) → its field
write order → that section's layout.

## What is still open

1. **Per-section record structure.** The archive is solved; what is inside each section is not.
2. Name the remaining `type`/`group` ids. Two are already pinned from the class list, and the
   once-per-file ids are the obvious next targets.
3. **The decoding route:** GZCOM serialisers are **mirror pairs** — a reader calling stream
   `vt+0x38` on field *addresses* and a writer calling `vt+0x88` on field *values*, same offsets,
   same order (first proven on the SIMGEOM pair `0x1001e516` / `0x1001e226`). **A serialiser's
   field order IS the on-disk layout.** Now that section groups are known to be **class ids**,
   the mapping is direct: find the class's serialiser, read its field order, decode its section.
   Note `0x035f62a4` itself appears in exactly one place in any binary
   (`GZResourceD.dll FUN_1000f5c4`), so go via the class ids, not that id.

## Tooling

```
py -3.12 re/tools/city_parse.py "Cities"                    # validate every city file
py -3.12 re/tools/city_parse.py "Cities\X.sc3" --extract out\   # dump decompressed payloads
```

---

# ⭐⭐ THE WRITER: a shipped `.sc3` round-trips BYTE-IDENTICALLY, 59/59

Landed 2026-08-17. This was the toolkit branch's first deliverable and the bar was deliberately
falsifiable: reading 59/59 is not writing, and the precedent to match was the sprite work
(62,552/62,552 byte-identical re-encode). **It passes at every layer.**

Tool: `re/tools/city_roundtrip.py`. Each layer is re-emitted **from parsed structure** — no layer
is allowed to copy its own input through — and diffed against the shipped bytes:

| layer | what is rebuilt | result |
|---|---|---|
| **L0** container | `.IXF` magic + every index slot + payloads at their offsets | **59/59** |
| **L1** record | the 24-byte payload header from its parsed fields | **59/59** |
| **L2** archive | the body from the section table: count, table offset, payloads, 16-byte entries | **59/59** |
| **L3** QFS | the compressed stream, re-encoded by the transcribed GZResourceD encoder | **59/59** |
| **L4** whole file | sections -> body -> QFS -> header -> record -> container, lengths **recomputed** | **59/59** |

```
py -3.12 re/tools/city_roundtrip.py "Cities"
L0 59/59  L1 59/59  L2 59/59  L3 59/59  L4 59/59   byte-identical
```

**L4 is the claim that matters.** It recomputes `compressedLength` (both copies of it) and
`uncompressedLength` from the bytes it actually emitted rather than echoing the parsed header, so
the header, the compressor and the archive layout are all being tested at once against 59 files.

## The QFS compressor was the expected blocker and it is not one

`re/tools/qfs.py` decompressed but no byte-identical compressor had ever been demonstrated, and
the expectation going in was that one might be unreachable. **It is in the game**: GZResourceD
`FUN_1001694d`, reached through `FUN_100168cb`, transcribed in `re/tools/qfs_encode.py`. Full
detail — the hash/chain structures, the net-gain selection rule and the `quick = 1` finding — is
in `formats/QFS.md`. The short version: the game writes `.sc3` files, so a compressor had to
exist, and finding it beat inferring it.

## Two container facts the writer needed, both measured

**1. Type `0x2026960B` payloads are `4 + size` bytes, not `size`** `[CONFIRMED, 59/59]`. For
localized-string records the index `size` field is the **string length**, and the payload on disk
is `u32 length + chars`. Measured on 110 such records across the 13 `.SNR` files: the `u32` at the
payload start equals `size` in every one, and `offset + 4 + size` is exactly the next record's
offset. Reading only `size` bytes truncates the last four characters of every string — `"Maxis"`
becomes `"M"`, `"Blazej Stompel"` becomes `"Blazej Stom"`. Every other type stores exactly `size`.

> This surfaced as 13 files failing L0 at a "4-byte gap between payloads", and the gap bytes were
> ASCII (`axis`, `mpel`) — the tails of the strings. Worth noting how it was nearly misread: the
> driver's output column was too narrow, so `FAIL @941` printed as `FAIL @94`, which pointed into
> the index instead of into the payload region. The column is now wide enough to never clip a
> verdict. **A truncated diagnostic is a wrong diagnostic.**

**2. Container slack, and unreferenced tail data** `[CONFIRMED, 59/59]`:

- **Reserved index slots**: 0 or 20,200–20,280 bytes of zeros, all-zero in all 59 files.
- **Mid-file slack**: one all-zero region per `.SNR` (20,200 bytes, after the `0x23dfae5f` record).
- **Unreferenced tail**: **7 of the 13 `.SNR` files carry 51–63,586 bytes past the last indexed
  payload, ~96–98% non-zero**, with **no** deleted (`0xFFFFFFFF`) slots pointing at it. The index
  does not reference it, so the game never reads it, but a byte-identical writer must preserve it.
  `[UNCERTAIN]` what it is — the shape fits stale bytes from an earlier, larger version of the
  file left behind by an in-place rewrite, but no code has been read for it. See `U-039`.

## The honest scope limit

`build_body` re-emits the section archive from the parsed table with **each section's payload bytes
verbatim**. It does not re-serialise a section's contents from decoded sim state, and it could not:
that would mean reimplementing the layer savers. So what is demonstrated is an
**edit-and-rewrite pipeline** — parse a city, change bytes at a decoded offset, emit a valid file —
in which everything untouched reproduces exactly. That is what a modding toolkit needs. It is not
a claim that a city can be authored from scratch.

---

## What SIMRCI cluster 4 added (2026-08-17) — the first gate-A slice

The first cluster driven by the re-scoped P1 criterion 2 (`scope_toolkit.py --todo` →
`delegate_cluster.ps1 -RvaFile`, 25 of SIMRCI's 55 toolkit-set functions). All 25 rows were
checked against the binary with `re/scripts/verify_worker_rows.py` before merging. Three results
bear on this document.

### 1. `0x16` gets its first mechanical witness: something CLEARS it `[CONFIRMED @0x10032ca9]`

`SIMRCI FUN_10032ca9` (300 B) walks the tile grid and, for `param_1 == 1` only:

```c
(**(code **)(*(int *)this + 0x34))(x, y, &local_5);      // grid GET  (row, col, &value)
if (local_5 == '\x16') {                                  // the value 22
  local_6 = 0;
  (**(code **)(*(int *)this + 0x3c))(x, y, &local_6);     // grid SET  -> 0
}
```

So `0x16` is a tile value that a **normal code path resets to 0 (unzoned)**, over the whole grid,
under a mode flag. This document had `0x16` as `[UNCERTAIN]` — present in the raster, grouped with
commercial by the reader `0x1001deca`, but declared by no developer slot in any file. "A value
something sweeps away" is consistent with it being **transient/marker state rather than a zone
type**, which also fits the earlier observation that counting it as commercial makes
residential-above-commercial worse (14/15 → 12/15). **Still `[UNCERTAIN]` what it marks** — no
producer has been read, only this consumer. It is the first real handle on it.

> ⚠️ **My verifier nearly destroyed this finding.** It reported the row as citing `0x16` with the
> value "absent from the body", i.e. a fabricated constant. The value IS in the body — as a **C
> character escape, `'\x16'`** — which neither the hex nor the decimal pattern matched. That was
> the fourth silent zero-match regex of the session and the only one that would have thrown away
> correct evidence and blamed the reader for it. When a checker accuses a claim, check the checker.

### 2. A THIRD independent copy of the frame reader `[CONFIRMED @0x1003fb73]`

`SIMRCI FUN_1003fb73` has the SIMCITY frame read-ctor layout exactly: three `param_1 vt+0x260`
reads into `this+0x14/0x18/0x1c`, then `*(int *)(this + 8) == -0x21524111` (`0xDEADBEEF`) with the
result stored as the bool at `this+0x10` — plus a reset-and-retry-once around the sentinel.

The base-0 correction rested on two witnesses (SIMCITY `0x10010315`, SIMGEOM `0x1001f360`). This is
a **third, in a third module**, found by a worker with no knowledge of either. The frame really is a
per-module copy of a shared helper. Tracker name corrected to `sc3_zonedev_frame_read_ctor`; the
worker had it as a "cursor ctor", which understates what it is.

### 3. The `u16` permutation READER is confirmed field-for-field `[CONFIRMED @0x1004350e]`

`FUN_1004350e` is slot 0 of `PTR_FUN_1004d2bc`, the mirror of the writer `FUN_1004361d` this
document reads above. The worker's field list matches the writer's, slot for slot, and supplies the
**read-side slot mirrors** that were missing:

| write (`0x1004361d`) | read (`0x1004350e`) | field |
|---|---|---|
| `vt+0x70` u8 | `vt+0x20` | `this+0x04` |
| `vt+0x88` u32 | `vt+0x38` | `this+0x08` = the count |
| `vt+0x68` bool | `vt+0x18` | `this+0x0c` |
| `vt+0x98` ×5 | `vt+0x48` ×5 | `this+0x10 .. 0x20` |
| `vt+0x78` u16 ×count | `vt+0x28` ×count | the vector at `this+0x24` — read into a **short array**, matching the `>> 1` element stride on the write side |

Two things follow. The `u16` vector really is **2-byte elements** (a `short` array on the read
side, independently of the writer's `>> 1`), and the earlier withdrawn-then-reinstated claim that
the loader does read the sub-object is now confirmed from the sub-object's own side.

Also merged, and relevant to the section directory: `0x1003dd02` / `0x1003db69` are a
**save/load mirror pair** on stream slots `+0x88/+0x68/+0x78` against `+0x38/+0x18/+0x28`, and
`0x100194cf` is confirmed as the **LandfillZoneDeveloper ctor reading `\Sys\SC3Tune.INI`** — the
same identification this document derived from the registration table, reached independently.

---

# ⭐ THE EDITING API: `re/tools/city_write.py`

Added 2026-08-17, the layer above the writer. `city_roundtrip.py` proved the pipeline is
reversible; this turns that into an API that changes something decoded and emits a valid file.

```python
from city_write import City
c = City.load("Cities/Berlin, Germany.sc3")
c.n                     # 256 -- from the SIMGEOM tile-grid section, isqrt(size - 16)
c.declared_slots()      # {1,2,3,5,6,7,9,10,11,14,15,17} -- this city's own developer slots
c.zone_get(10, 20)      # the tile's zone-developer slot index
c.zone_set(10, 20, 17)  # Landfill
c.save("out.sc3")
```

## What it proves, measured

| check | result |
|---|---|
| `--selftest`: load → save with **no edits**, all 59 shipped files | **59/59 byte-identical** |
| offsets **recomputed** from scratch rather than reused | still 59/59 — the shipped sections really do tile contiguously from offset 8 |
| a two-tile edit on Berlin, re-read from the written file by a fresh parse | both tiles read back as set; **exactly 2 raster bytes differ**; **one section's bytes changed**, the zone layer |
| the edited file through the independent `city_roundtrip.py` | **L0–L4 all PASS** — it is well-formed by every offline check |

Offset recomputation is what makes editing possible: a section that changes length shifts every
later one, and the section table has to be rebuilt. That it still reproduces all 59 shipped files
exactly is the check on it, not an assumption. The edited Berlin came out 781,814 bytes against
781,807 — QFS compresses the changed body slightly differently, and both header length fields are
recomputed from what was actually emitted.

## Only the zone raster is editable, on purpose

`zone_set` refuses anything the evidence does not support:

- the loader's own bound, tile values `< 0x17` `[CONFIRMED @0x10031c85:144-163]`;
- **and** slots this city actually declares — each non-NULL slot of the 23-slot table has its own
  4-byte section with `instance == slot + 1`, so the file states its own occupied set. A raster
  byte is an index into that table, so an undeclared slot has no developer behind it.

Everything else is exposed as raw section bytes, because nothing else has a decoded per-field
meaning yet.

## The limits, stated because a working writer invites over-claiming

1. **No modified city file has ever been loaded by the game.** 59/59 byte-identical round-trip is
   a statement about the container, not about whether the sim accepts edited contents. Every claim
   above is an offline structural one.
2. **No checksum is known — which is not the same as there being none.** The 24-byte header holds
   two length fields and no checksum, and the archive has none. A validity check inside a section
   would be invisible to this tool.
3. **The `u16` permutation is left alone.** Editing the raster does not touch the `N*N` distinct
   `u16`s in the zone section's tail, and whether the two must agree is `[UNCERTAIN]` (`U-029`).
4. **Derived state is not recomputed.** The loader can rebuild the 23-entry slot histogram itself
   (that is its failure path), but RCI demand, land value and everything else downstream of zoning
   are untouched.

> Berlin's raster carries **4,921 tiles of value `0x16`** — the value no file declares as a slot
> and that `FUN_10032ca9` clears to 0. So it is not rare, which makes "transient marker state"
> more interesting rather than less. `zone_set` will not write it.

---

# ⭐ Chasing the `0x16` producer (2026-08-17): six new facts, and one reading FALSIFIED

`0x16` (22) has been the raster's open question since the layer was decoded: present in the
raster, grouped with commercial by the reader `0x1001deca`, declared as a slot by no shipped
file. It is not a rounding artefact — **Berlin carries 4,921 of them**, so it was worth chasing.

The producer was **not** found. What was found is a much tighter box around it, plus a
falsification.

## 1. Nothing in any shipped binary writes the literal 22 into the raster `[CONFIRMED, exhaustive]`

The cell-map setter's call shape is known from `FUN_10032ca9`: a local is assigned, then passed
**by address** as the third argument of vtable slot `+0x3c`:

```c
local_6 = 0;
(**(code **)(*(int *)this + 0x3c))(row, col, &local_6);
```

Sweeping **all 30 binaries** for a local assigned 22 — in all three spellings Ghidra uses,
`'\x16'` / `0x16` / decimal `22` — and then passed by address to a `+0x3c` call gives **zero
hits**. So the value is not written as a literal through that path anywhere. It is computed, or
it arrives by a route this shape does not cover (a bulk row write, or an authoring tool).

## 2. It exists only where there is zoning `[CONFIRMED, 59/59]`

| family | files | files with `0x16` | total `0x16` tiles |
|---|---|---|---|
| `.sct` terrain | 21 | **0** | **0** |
| `.sc3` saved city | 15 | 14 | 27,222 |
| `.snr` scenario | 13 | 13 | 20,498 |
| `.st3` starter town | 10 | 10 | 965 |

**Every one of the 21 bare terrains has none.** In developed cities it is **8–20% of all
non-zero raster tiles** (Berlin 4,921 of 24,555 = 20.0%). A useful consistency check fell out:
`Fall of the Wall.SNR` and `Berlin, Germany.sc3` report *identical* counts (4,921 / 24,555), as
do `Rags To Riches.SNR` and `Madrid, Spain.sc3` — the scenarios are built from those cities.

## 3. ⚠️ It is NOT another commercial zone — the spatial evidence contradicts that `[FALSIFIED]`

This document has carried the reader's grouping (`0x1001deca` puts `0x16` in the same branch as
5/6/7/0xe) with a warning that "the grouping is one reader's behaviour, not necessarily the
tile's identity". That caution was right. Neighbour analysis on Berlin, 19,668 neighbour samples:

| class | share of all tiles | share of `0x16`'s neighbours | enrichment |
|---|---|---|---|
| **`0x16`** | 7.51% | **64.34%** | **8.57x** |
| unzoned | 62.53% | 29.13% | 0.47x |
| Residential | 13.71% | 3.43% | 0.25x |
| Commercial | 8.10% | 1.95% | **0.24x** |
| Industrial | 6.11% | 0.97% | 0.16x |
| Landfill | 1.10% | 0.14% | 0.13x |

`0x16` is **8.57x enriched next to itself** and **depleted next to every declared zone class**,
commercial included. Horizontal runs: 1,746 of them, mean 2.82, **max 36**. So it forms its own
large contiguous regions bordered mostly by empty land — which is not how a commercial density
variant would be laid out (that would interleave with 5/6/7). **The "another commercial zone"
reading is dead**; what survives is only that one reader dispatches it down the commercial branch.

## 4. The slot table is SIX GROUPS OF FOUR, and `0x16` is in the one nobody registers

Laying the 23 slots out in fours explains the NULL pattern exactly:

| group | slots | declared |
|---|---|---|
| 0 | 0,1,2,3 | 1,2,3 = **Residential** ×3 densities |
| 4 | 4,5,6,7 | 5,6,7 = **Commercial** |
| 8 | 8,9,10,11 | 9,10,11 = **Industrial** |
| 12 | 12,13,14,15 | 14,15 (no INI name; commercial-side / industrial-side) |
| 16 | 16,17,18,19 | 17 = **Landfill** |
| **20** | 20,21,22,23 | **none, in any of the 59 files** |

Every group is one gap followed by up to three slots, and the observed NULL slots
(0,4,8,12,16 + 13) are exactly those gaps. **`0x16` = 22 sits in the sixth group, for which no
city registers a developer at all.** So the raster holds an index into an unpopulated group.

## 5. `0x16` is the hard ceiling of a tunable range `[CONFIRMED @0x10001020]`

`FUN_10001020` (`sc3_zone_ctor_load_devrules`) reads INI section **`ZoneDeveloperRules`** and
parses four integers with `sscanf("%d %d %d %d")`, then clamps:

```c
if (DAT_100571d0 < 4)              DAT_100571d0 = 4;       // floor 4
if (DAT_100571d4 < DAT_100571d0)   DAT_100571d4 = DAT_100571d0;
if (0x16 < DAT_100571d4)           DAT_100571d4 = 0x16;    // CEILING 22
if (0x16 < DAT_100571d0)           DAT_100571d0 = 0x16;    // CEILING 22
```

So a tunable min/max pair is bounded to **[4, 22]** — the range of slot indices excluding the
Residential group. The only other reader of those two globals is `FUN_100015ab`, which gates on
them and tests a tile byte against the set **{0, 1, 5, 9, 22}** `[CONFIRMED @0x100015ab]` —
zero plus the *first* slot of the R, C and I groups, with 22 alongside them.

## Where that leaves it

`[UNCERTAIN]` what `0x16` marks. But the box is much tighter, and two candidate readings are now
excluded rather than merely doubted:

- **not** a commercial zone variant (fact 3);
- **not** written as a literal by any shipped code (fact 1);
- it is runtime/authoring state that only exists once a map is zoned (fact 2), covering large
  contiguous regions (fact 3), indexing a developer group no city populates (fact 4), and sitting
  exactly on the ceiling of a tunable slot range (fact 5).

The next evidence has to come from the write side: either the `vt+0x38`-style bulk row writer on
the cell map, or a debugger breakpoint on the setter while zoning in-game. A literal sweep is
exhausted — that is now measured, not assumed.

> Instrument note, because it nearly cost the negative result in fact 1: the first version of that
> sweep matched `'&' + varname` as a **substring**, so `&local_84` satisfied a search for
> `&local_8` and it reported 6 hits. With a word boundary the honest answer is 0. A sweep that
> finds something is not automatically better than one that finds nothing.

## A worker attacked the same question independently — three additions, verified here

Delegated in parallel with the sweep above, with no knowledge of its results. It reached the
**same negative** (no literal 22 is written through the cell-map setter anywhere in SIMRCI) and
added three things. Each was re-checked against the binary before being recorded:

**1. `0x10` and `0x16` are a COLOUR-PAIRED set** `[CONFIRMED @0x1003547c, re-read here]`.
`FUN_1003547c` reads the tile through the cell-map getter (`(this-0x10) vt+0x34`) and maps it to a
display colour index:

```c
if (uVar1 != 0x10) {
    if (uVar1 == 0x11) { *param_4 = 0x20; goto done; }   // 17 Landfill -> colour 0x20
    if (uVar1 != 0x16) goto default;                     // not 22 -> default
}
*param_4 = 0x22;                                          // BOTH 16 and 22 -> colour 0x22
```

So tile values **16 and 22 render identically**, while Landfill (17) has its own colour. The rest
of the map: `10 -> 0x16`, `0xb -> 0x15`, `0xd -> 0x21`, `0xe -> 0x1e`, `0xf -> 0x1f`. Note 16 is
itself a **group-start gap** slot (group `{16,17,18,19}`) that no file declares — so the two
values sharing a colour are both undeclared ones.

**2. The clear path has two entry points, and they are a keep/clear pair**
`[CONFIRMED @0x10032dd5, 0x10032de6, re-read here]`:

```c
FUN_10032dd5(this, x, p)  ->  FUN_10032ca9(this - 0x38, 0, p)   // mode 0: keep
FUN_10032de6(this, x, p)  ->  FUN_10032ca9(this - 0x38, 1, p)   // mode 1: clear the 0x16 cells
```

and the same pass adjusts an accumulator on the object QI'd for `0xe0faadc7`, negating the
per-tile contribution when it clears. So `0x16` tiles carry an ongoing effect that a caller can
toggle off wholesale.

**3. `[iOS-HINT]` the sibling's `e_ZoneType` has non-RCI members, and one of them is pinned.**
The iOS oracle names `kMilitary`, `kAirport`, `kSeaport`, `kLandfill`, `kPloppedBuilding`, with
**`kLandfill` at `0x11` = 17 — exactly the x86 slot whose ctor loads `LandfillZoneDeveloper`**.
That is a real cross-check on the mapping's alignment. It does **not** name 22: the value↔name
table is a data-driven static initialiser present as readable code in neither export, and the x86
binary carries **no string** for Seaport / Airport / Military / Plopped (consistent with slot 22
having no INI name, unlike R/C/I/Landfill).

> **The tempting inference, and why it stays a lead.** Large contiguous blobs bordered by empty
> land, 8–20% of zoned tiles, commercial-grouped, no INI name, budget-linked, sharing a colour
> with another undeclared value — that shape fits `kSeaport` / `kAirport` / `kPloppedBuilding`
> from the iOS list. **Nothing binds 22 to any of those names**, and this document already
> records a near-miss (`0x029ca804` vs `0x029ca806`) that punished exactly this kind of
> reasoning. `[UNCERTAIN]`, and the missing evidence is named: the `e_ZoneType` value→name table.

One worker reading is recorded as theirs, not verified here: that the recurring
`local_8._0_1_ = 0x16` in the INI loaders is a **C++ exception-unwind scope byte**. It is
certainly not a grid write (those functions call no setter), which is the part that matters.

### A THIRD consumer of `0x16`, and it is outside SIMRCI `[CONFIRMED @0x10010220]`

Found while hand-reading the post-carve additions to the toolkit set. **SIMGEOM** `FUN_10010220`
reads a single grid cell through the cell-map getter and gates on it:

```c
(**(code **)(**(int **)(param_1 + 0x10) + 0x34))(x, y, apiStack_c);   // cell-map GET
if ((cVar1 != '\0') && (cVar1 != '\x16')) { ... }                      // {0, 22} treated alike
```

So a second module tests the raster value 22, and it pairs it with **0** rather than with the
commercial slots. That is now the third independent consumer and the pattern across all of them is
consistent:

| site | what it does with 22 |
|---|---|
| SIMRCI `0x10032ca9` | **clears** it to 0 over the whole grid, in mode 1 |
| SIMRCI `0x100015ab` | accepts it alongside `{0, 1, 5, 9}` — zero plus each class's first slot |
| SIMRCI `0x1003547c` | gives it the **same display colour** as 16, another undeclared value |
| SIMGEOM `0x10010220` | treats `{0, 22}` as the pair to skip |

**`22` keeps behaving like a second kind of "empty".** Normalised to 0 by one path, grouped with 0
by another, coloured like another undeclared value by a third, and covering large contiguous
regions bordered by unzoned land (the neighbour analysis above). That is a *better* fit for
"reserved / vacant / not-yet-developed" than for a seaport or airport, and it is now a competing
reading of the `[iOS-HINT]` name list rather than a confirmation of it.

`[UNCERTAIN]` still — no producer has been found, and nothing names it. Two limits on the above:
Ghidra lost register tracking inside `0x10010220` (`unaff_ESI` / `unaff_EDI`), so the coordinate
operands are not legible, and "behaves like empty" is an inference from four consumers rather than
a statement any single one of them makes.

---

## ⭐ The section TYPE column is NAMED: `0x206c6e7c` = `GZIID_cISC3CityLayer`

Found by the gzcom session (2026-08-17, `2c3a96d`), and **corroborated here from the shipped bytes
by a different method** before being adopted. Their evidence is structural: a class has a
`cISC3CityLayer` base subobject iff an adjustor thunk (`sub ecx,N ; jmp <primary QueryInterface>`)
is slot 0 of a second vtable whose slot 15 is `mov eax,imm32 ; ret` (`GetLayerType`). Across seven
classes plus a control, accepting IID `0x206c6e7c` correlates perfectly with having one.

**The independent check, from the section table rather than from vtables.** If the type column is
the IID of the *interface* a section is serialised through, then the groups paired with
`0x206c6e7c` should be exactly the classes we already believe are city layers, and things that are
not layers should use a different type. They do:

| group | what we already called it | uses type `0x206c6e7c`? |
|---|---|---|
| `0x409ff3ba` | SC3ZoneLayer | **yes** |
| `0xe11bddf6` | SC3WorldLayer | **yes** |
| `0xc0a81498` | SIMECO pollution layer | **yes** |
| `0xc106c4f5` | SIMRCI demand layer | **yes** |
| `0x2147c2dd` | SIMNTWRK network layer | **yes** |
| `0x21737de5` | SIMDIRT terrain layer | **yes** |
| `0x029ca804` | SimTransit layer | **yes** |
| `0x80ab8ab0` | SIMGEOM **tile grid** — a cell map, *not* a layer | **no**, uses `0x406b1196` |

**Seven of seven named layers use it, and the one named non-layer does not.** Two unrelated methods
agreeing, which is the standard this project holds itself to.

So the section key is now fully readable:

```
{ type, group, instance } = { the INTERFACE IID being serialised,
                              the CLASS id (CLSID) implementing it,
                              a per-class ordinal }
```

That explains the type distribution at a glance: `0x206c6e7c` covers 2,095 of 3,451 sections
because most saved objects are city layers, and each remaining type is a different interface.
`0x406b1196` is the tile grid's interface, and the once-per-file types (`0xc2910e7d`,
`0x20631788`, `0xe0faadc7`, `0xe11bcc69`, `0x41193c3a`) are five further interfaces with one
implementing class each.

`[UNCERTAIN]` the names of the other type ids. `0x81c0cb7c`, which the same investigation found
alongside, is implemented by 16 classes and is **not** in the SDK headers.

> **A counting scare, recorded because the resolution is the useful part.** An ad-hoc script here
> once reported 3,511 sections and 2,131 of type `0x206c6e7c`, against the 3,451 / 2,095 this
> document has always carried. A clean re-measurement reproduces **3,451 sections and 2,330
> `0xDEADBEEF` markers exactly**, matching the committed figures. I proposed a mechanism for the
> difference — that a test city had briefly been copied into `Cities\`, which would have added
> exactly 60 sections — and then **falsified it**: every file in `Cities\` still carries its
> original install timestamp. The discrepancy is unexplained and the ad-hoc script is not
> reproducible; the committed numbers stand because they are the ones that reproduce.

---

# 🔴 The `0x16` hunt, 2026-08-18: the QUESTION was malformed

The producer of `0x16` was **not** found. What was found is better than another lead: **two of the
five facts this document rested the mystery on do not survive checking**, and one of them was the
entire reason `0x16` looked special. Net result — `0x16` is *less* anomalous than recorded, the
remaining anomaly is sharply localised, and one project-wide instrument is proven to lie.

Tools added, both with `--selftest`: `re/scripts/find_zone_writes.py`, `re/tools/city_planes.py`.

## 1. ⚠️⚠️ THE HARNESS `Grep` TOOL SILENTLY RETURNS ZERO OVER THE WHOLE DECOMPILATION

**Read this before trusting any "0 hits" in any tracker in this project.** `CLAUDE.md` instructs
every session to "grep the export before ever opening live Ghidra". The default tool for doing
that **cannot see the export at all**, and it reports that as *no matches* rather than as an
error:

```
Grep  '\+ 0x3c\)\)\('   path = re                                 ->  0 matches, 0 files
Grep  '\+ 0x3c\)\)\('   path = re/ghidra_export_simrci/functions   ->  77 matches, 44 files
```

Same pattern, same corpus, two answers. The cause is this repo's own publication safety net:
`.gitignore` is deny-by-default, so `re/ghidra_export*/` is ignored (correctly — the
decompilation must never be published), and **ripgrep honours `.gitignore`**. Confirmed directly:

```
git check-ignore -q re                        -> not ignored
git check-ignore -q re/ghidra_export_simrci   -> IGNORED
```

Searching *at or above* `re/` makes ripgrep skip the ignored subtree. Searching with the path
*inside* the ignored subtree works, because the search root itself is never re-tested against the
ignore rules. So whether the primary RE instrument works depends on how deep you point it, and
the failure mode is a clean, confident zero.

**Consequences.** Any exhaustive-negative claim in this project produced with that tool at or
above `re/` is a **false negative and must be re-run**. Use raw `grep`/`os.walk`, or pass a
specific module's `functions/` directory. This is the fifth silent zero-match recorded here and
the first that is a property of the *harness* rather than of a regex.

## 2. `[FALSIFIED]` "No literal 22 is written anywhere" — TRUE, AND IT MEANS NOTHING

This document's fact 1 (2026-08-17) reported, as an exhaustive confirmed negative, that no shipped
binary writes the literal 22 into the raster, and drew the inference that the value must therefore
be "computed, derived, or copied". **The negative reproduces. The inference does not.**

`find_zone_writes.py` re-runs it with three corrections: a gitignore-blind file walk (§1), all
**three** cell-map write slots instead of only one, and a `--selftest` (11 checks) that covers the
two traps this document already paid for. The write interface is pinned by a contiguous block of
8-byte adjustor thunks in SIMRCI at a uniform 8-byte stride, and **both previously-known anchors
fall out of it**, which is what makes the other two derived rather than guessed
`[CONFIRMED, read here]`:

| thunk | slot | target | shape |
|---|---|---|---|
| `0x10034332` | `vt+0x34` | inline | `GET(row, col, &u8)` — the known anchor |
| `0x1003433a` | `vt+0x38` | `FUN_10032afa` | `SET_RECT(x1, z1, x2, z2, &u8)`, per-row `memset` |
| `0x10034342` | `vt+0x3c` | inline | `SET(row, col, &u8)` — the known anchor |
| `0x1003434a` | `vt+0x40` | `FUN_10032be0` | `SET_ALL(&u8)` |

Then the sweep is run **per zone value**, which nobody had done. That is the whole result:

| zone value | what it is | strong hits |
|---|---|---|
| 3 | Residential HD | **0** |
| 5, 6, 7 | **Commercial ×3** | **0** |
| 9, 10, 11 | Industrial ×3 | **0** |
| 14, 15 | the two unnamed | **0** |
| 17 | **Landfill** | 1, hand-checked → **false positive** |
| **22** | the mystery | **0** |
| 0, 1, 2 | — | 237 / 16 / 4, all on unrelated classes' `+0x38/0x3c/0x40` slots |

**Commercial 6 is a zone the player creates with a mouse drag, and it has exactly as many literal
producers as 22: none.** So does every other real zone type. The literal sweep was never capable
of finding a producer for *any* zone value, because the zone type is passed as a **variable** from
UI state, not baked in at a call site.

> **`0x16` was never special in this respect.** "No literal 22 anywhere in 30 binaries" is a true
> statement about the *method*, not about the *value*. The 2026-08-17 write-up promoted it to the
> shape of the problem — "a value that is spatially clustered, common, and never written as a
> literal" — and half of that shape was an artefact. The sweep should have been run against a
> known-good control on day one; it takes one command.

The single value-17 hit (`scenario 0x100044c7`) is a false positive **of my own tool**, hand-checked
and reported rather than quietly dropped: `local_7c` is declared `undefined4` (4 bytes, not a tile
byte), is assigned `0x11` at line 296, and is **reassigned to 0 at line 372** before the
`vt+0x40` call at line 386. `find_zone_writes.py` is not flow-sensitive. That is the right way
round for this use — its **zeros** are sound (no such assignment-and-pass pair exists in the text
at all), its **hits** are an over-count needing a hand-check. Its docstring says so.

## 3. `[FALSIFIED]` "`0x16` is the hard ceiling of a tunable range" — it is a ROW STRIDE

Fact 5 of the 2026-08-17 write-up read `FUN_10001020`'s clamp of `DAT_100571d0`/`DAT_100571d4` to
`[4, 22]` as "the range of slot indices excluding the Residential group", and listed it as one of
the five things boxing `0x16` in. **The consumer says otherwise** `[CONFIRMED @0x100015ab]`:

```c
char local_23c [484];                                    // 484 == 22 * 22
...
param_2 = param_2 + 0x16;                                // walking rows of it
local_10 = local_8 + (int)(local_23c +
           (((int)local_c - (int)local_28) * 0x16 - (int)local_24));   // and indexing it
```

Every one of the nine uses of `0x16` in that function is a **row pitch into a fixed 484-byte
scratch bitmap** (lines 231, 246, 355-359, 396-400, 418, 428, 440, 466). `DAT_100571d0`/`d4` are
used exclusively as **rectangle extents** — the width/height gate at line 62 and the clamp at
lines 198-216 — so they are a min/max **lot edge length in tiles**, and the ceiling is 22 because
that is what fits the buffer. The INI section is `ZoneDeveloperRules`; a lot dimension is exactly
what belongs there.

> **Two unrelated meanings of the number 22 in one function were read as one.** A `[4,22]` clamp
> and a set of slot indices ending at 22 are a coincidence of value, and this document turned the
> coincidence into evidence. Sign-sensitive values get reported both ways here as a matter of
> policy; *dimension-versus-index* deserves the same suspicion.

**What survives from that function, and it is unchanged:** the `{0, 1, 5, 9, 22}` test is real. It
appears four times (lines 68, 80, 93, 105), once per side, and each loop walks the **perimeter ring
one tile outside** the candidate rect (`local_24 - 1` above, `local_28 - 1` left, `local_20 + 1`
right, `local_1c + 1` below). If any bordering tile is outside that set the function bails. So it
is a **"this border tile is acceptable to build against" whitelist** — unzoned, plus the first slot
of each of R/C/I, plus 22 — and it is a read-side predicate that writes nothing.

## 4. `[NEGATIVE, 59/59]` `0x16` is not identifiable from the second per-tile plane

Every previous attempt asked the code where 22 comes from. This asks the corpus what a 22 tile
*is*. Two `N*N` one-byte-per-tile planes sit in every shipped file and had never been compared —
the zone raster, and the SIMGEOM tile grid, whose 65,536 payload bytes `City.n` reads the *length*
of and then discards.

`city_planes.py` cross-tabulates them. It does not assume the two planes agree on row order (the
zone plane's base writer emits rows in reverse, `0x1001b4e9`; the tile grid is written by unrelated
code in another module), so it reports all four orientations. It does not assume the grid's payload
offset either: the 8-byte section frame's `0xDEADBEEF` marker is **validated** before the plane is
read, so a wrong offset fails loudly instead of shifting the whole table.

| filter | files | with 22 | 22 tiles | 22 / zoned |
|---|---|---|---|---|
| `Cities\*.sc3` | 15 | 14 | 27,222 | 0.1030 |
| `Cities\Terrains\*.sct` | 21 | **0** | **0** | — |
| `Cities\Scenarios\*.SNR` | 13 | 13 | 20,498 | 0.1123 |
| `Cities\StarterTowns\*.st3` | 10 | 10 | 965 | 0.0669 |

**All four totals reproduce the figures this document recorded on 2026-08-17 exactly** (27,222 / 0
/ 20,498 / 965), by a different tool on a different code path — the second-method check, passed.

The cross-tab itself is a clean negative. `conc` = `max_g P(grid = g | zone = 22)`; `ctrl-max` = the
same statistic for the sharpest *other* zone value in that file, which is the control that stops a
grid dominated by one value (Berlin's is 87.7% zero) from manufacturing a result:

| family | orientation spread of `conc` | mean `conc` | mean `ctrl-max` |
|---|---|---|---|
| `.sc3` (15) | 0.831 – 0.844 | 0.837 | **0.985** |
| `.snr` (13) | 0.894 – 0.923 | 0.905 | **0.986** |
| `.st3` (10) | 0.930 – 0.966 | 0.943 | **0.990** |

**In every family and every orientation `0x16` is LESS tightly tied to the tile grid than the
sharpest other zone value is.** Berlin's per-value enrichments are all within noise of 1.0 (grid
`0x00` 0.95, `0x26` 1.42, `0x21` 0.99, `0x22` 1.38). And the four orientations agree to within
±0.02, which is itself informative: a real alignment would make one orientation stand out.

> **`[FALSIFIED]` `0x16` is water, terrain class, or anything else the SIMGEOM tile grid records.**
> Both candidate identities that motivated the test — undevelopable terrain, and plopped-building
> footprints if the grid marks occupancy — are excluded by this, in 59 of 59 files. What the test
> cannot exclude is an identity recorded in a plane nobody has decoded, the SIMDIRT terrain
> section (`{0x206c6e7c, 0x21737de5}`, 140,303 bytes in Berlin) being the obvious one.

## Where the producer actually is, and why five sweeps could not reach it

The three functions that write the zone raster while maintaining its invariants are named. Read
here rather than inferred `[CONFIRMED @0x10034342]`:

```c
bVar2 = *(byte *)(*(int *)(*(int *)(*(int *)(param_1 + -4) + 0xc) + param_2 * 4) + param_3);
if (bVar2 != *param_4) {                                  // NO-OP if unchanged
  if (bVar2 < 0x17)      { ... param_1 + 0x40 + bVar2*4   -= 1; }   // 23-entry u32 count array
  if (*param_4 < 0x17)   { ... param_1 + 0x40 + *param_4*4 += 1; }
  *(byte *)(...) = *param_4;                                        // the raster store
  (**(code **)(*(int *)(param_1 + 8) + 0x2c))(param_2,param_3);     // post a cell-changed notify
}
```

| RVA | role |
|---|---|
| `0x10032a96` / `0x10034342` | `SetValue(row, col, &u8)` on the two subobjects |
| `0x10032afa` | `SetValue` over a rect, per-row `memset` + rect notify `vt+0x28` |
| `0x10032be0` | `SetAllCells`, zeroes all 23 counts then sets one to `rows*cols` |
| `0x1003270a` | `GetZoneDeveloper` — `*(param_1 + 0x18c + param_2 * 8)`, **the raw byte, no arithmetic** |

**And none of them has a caller in the export.** Measured: `FUN_10032afa` and `FUN_10032be0` are
referenced only by their own thunks `0x1003433a` / `0x1003434a`; `FUN_10032a96`, `FUN_10034342`
and both thunks have **zero** references of any kind. That is expected for vtable dispatch — and
`re/ghidra_export_simrci/globals.csv` contains exactly **one** `vftable` line, i.e. **the export
holds no vtable contents**, so the text export structurally cannot show who dispatches into them.

> **This is the real answer to "why has the `0x16` producer never been found".** It is not that
> `0x16` is elusive. **No zone value's producer is visible in this export** — not Commercial, not
> Residential, not Landfill. The zoning write path is reached through vtables the text export does
> not carry, from callers in regions Ghidra never carved: the same uncarved-code problem that hid
> the three INI-loader stubs and that a 2026-08-17 re-carve fixed for 12,529 other bodies.
>
> So the next step is **not** another sweep, and not a debugger either. It is `VtableProbe` /
> `XrefProbe` on live Ghidra against `0x10032a96`, `0x10032afa` and `0x10032be0` to find which
> vtable slots hold them and who dispatches through those slots — the route that has already
> worked three times in this document (`0x10030369`, `PTR_FUN_1004d2bc` slot 1, the `+0x188`
> vs `+0x18c` settlement).

## What `0x16` still is, after all this

Unchanged and still `[UNCERTAIN]`: it is an in-range slot index (`< 0x17`) that **no shipped file
declares a developer for**, occupying 6.7-11.2% of zoned tiles, absent from all 21 bare terrains,
clustered 8.57x next to itself, and treated as a second kind of "empty" by four independent
consumers. Excluded now: another commercial zone (2026-08-17), a tunable-range ceiling (§3), and
anything the tile grid records (§4).

The missing evidence, named: **which vtable slot dispatches to `0x10032afa`, and from where.**

---

# ⭐⭐ `0x16` IS NAMED, FROM THE X86 BINARY: it is a PLOPPED BUILDING

Landed later on 2026-08-18, and it resolves the section above. The name comes from the iOS oracle,
but **the enum is named by SC3U's own code** and that is what settles it — every binding below was
re-read here before being adopted.

## The x86 binary names the zone enum: SIMRCI `0x10034716` `[CONFIRMED @0x10034716]`

The query tool's zone-name switch dispatches on the raster byte and looks up a localized string in
LTEXT group `0x82e0074c`, or emits a hardcoded `*BUG*` string for a zone type the game refuses:

```c
switch((uint)param_5 >> 0x18) {
case 1:    FUN_1003f052(local_27c,0xf, 0x82e0074c);      // instance 15
...
case 0xd:  FUN_1000628b(local_14c,s__BUG__No_military_zones_allowed__100581dc);
case 0xe:  FUN_1003f052(local_2f4,0x19,0x82e0074c);      // instance 25
case 0xf:  FUN_1003f052(local_31c,0x18,0x82e0074c);      // instance 24
case 0x10: FUN_1000628b(local_110,s__BUG__No_spaceport_zones_allowed_100581b8);
case 0x11: FUN_1003f052(local_344,0x1a,0x82e0074c);      // instance 26
default:   FUN_1003f052(local_36c,0x195,0x82e0074c);     // instance 405
```

Resolving those instances in `re/data/ixf_text.csv` (`SC3StringsQuery.IXF`):

| raster value | case | LTEXT | string | name |
|---|---|---|---|---|
| 1, 2, 3 | 1, 2, 3 | 15, 16, 17 | `Residencial` / ` Media` / ` densa` | **Residential** ×3 |
| 5, 6, 7 | 5, 6, 7 | 18, 19, 20 | `Comercial` / ` Media` / ` densa` | **Commercial** ×3 |
| 9, 10, 11 | 9, 10, 0xb | 21, 22, 23 | `Industrial` / ` Media` / ` densa` | **Industrial** ×3 |
| **13** | 0xd | — | `*BUG* No military zones allowed!` | **Military** (refused) |
| **14** | 0xe | 25 | `Aeropuerto` | **Airport** |
| **15** | 0xf | 24 | `Puerto` | **Seaport** |
| **16** | 0x10 | — | `*BUG* No spaceport zones allowed` | **Spaceport** (refused) |
| 17 | 0x11 | 26 | `Vertedero` | **Landfill** |
| **22** | *no case* | 405 | `Zona no delimitada` | falls through → **reported as "Unzoned"** |

> Curiosity, recorded because it could mislead the next reader: the language column labelled
> `ENGLISH` in this install carries **Spanish** text (`English-UK` is the English one). It does not
> affect the mapping, and arguably strengthens it: the meaning survives translation.

## Independently corroborated by unrelated x86 code: the SC2 importer `[CONFIRMED @0x10031bcc]`

`SIMRCI FUN_10031bcc` is the zone layer's SimCity 2000 import method. It builds a 10-entry
translation table from SC2 `XZON` nibbles to SC3 raster values and writes each cell through the
cell-map setter with the table entry passed **by address**:

```c
local_1c[0] = 0;    local_1c[1] = 1;  local_1c[2] = 3;   local_1c[3] = 5;   local_1c[4] = 7;
local_1c[5] = 9;    local_1c[6] = 0xb; local_1c[7] = 0;  local_1c[8] = 0xe; local_1c[9] = 0xf;
...
if (9 < param_2._3_1_) { param_2 = (int *)((uint)param_2 & 0xffffff); }        // >9 -> 0
iVar6 = (**(code **)(*piVar7 + 0x3c))(iVar5,local_8,local_1c + ((uint)param_2 >> 0x18));
```

SC2's documented `XZON` low nibble is `1` light-res, `2` dense-res, `3` light-com, `4` dense-com,
`5` light-ind, `6` dense-ind, `7` military, `8` airport, `9` seaport. Against the table:

| SC2 nibble | 1 | 2 | 3 | 4 | 5 | 6 | **7** | **8** | **9** |
|---|---|---|---|---|---|---|---|---|---|
| → SC3 | 1 | 3 | 5 | 7 | 9 | 11 | **0** | **14** | **15** |
| meaning | R-lo | R-hi | C-lo | C-hi | I-lo | I-hi | military **dropped** | **airport** | **seaport** |

**Airport → 14 and seaport → 15 in exactly the positions the query switch names them, and military
is dropped to 0 in exactly the position that emits `*BUG* No military zones allowed!`.** That is an
order-preserving agreement at ten points between two functions with nothing to do with each other.

**Hypothesis "the SC2 importer produced the 22s" is `[FALSIFIED]` by the same code**: the table's
maximum output is `0xf` = 15, and out-of-range nibbles are forced to 0. It arithmetically cannot
emit 22. (Note in passing that this IS a genuine table-driven producer of zone values through
`vt+0x3c` — the "written through a table" framing was correct in general and wrong for 22.)

## Three corrections to this document

| this document said | it is actually |
|---|---|
| slot 14 = "(commercial-side, unnamed)" | **Airport** |
| slot 15 = "(industrial-side, unnamed)" | **Seaport** |
| slots 13 and 16 unremarked | **Military** and **Spaceport**, both refused with `*BUG*` strings |

The commercial/industrial-side grouping in the reader `0x1001deca` was **right and is now
explained**: Airport (14) dispatches commercial-side, Seaport (15) industrial-side. And the long
-standing oddity that **`0x10` and `0x16` share display colour `0x22`** `[@0x1003547c]` resolves at
a stroke — Spaceport and PloppedBuilding are the two values that are *not* developer-built zones.

## `[iOS-HINT]` the name, and `[CONFIRMED]` the x86 negative

The iOS sibling's `e_ZoneType` name block is 16 contiguous strings ending
`kLandfill` (`0x004af148`), `kPloppedBuilding` (`0x004af154`), and its `GetZoneColor`
(`0x00264768`) is a jump table over `0` to `0x16` whose populated-case set and colour values are
**byte-for-byte identical to x86 `0x1003547c`**, `{0x10, 0x16} → 0x22` pair included. With 11
x86-side positions independently pinned above, `kPloppedBuilding = 22` is the only remaining
assignment.

**And the iOS build contains the producer this document has hunted for four sessions**
`[iOS-HINT @0x001fe2a8:608]` — `SimCity::goBuildingLayer::PlaceBuilding`:

```c
local_21 = 0x16;
(**(code **)(**(int **)(*(int *)(this + 0x7c) + 0x274) + 0x11c))
          (..., iVar10 >> 8, iVar8 >> 8, iVar9 >> 8, iVar12 >> 8, &local_21);
```

`city+0x274` is the zone layer (typed call sites in the same export), and `+0x11c` is its
**SetCellRect** — the same slot as x86 `vt+0x38`. So **placing a building stamps its whole
footprint rect with 22.** Two sibling writers use the identical shape with value `0`:
`goPowerLayer::onOccupantInserted` (`0x00259b50`) and `goTransitLayer::ForcePlaceTile`
(`0x00294a6c`) — networks *dezone* the tiles they take, buildings *mark* them.

**The x86 side of that is the measured negative from §"Where the producer actually is":
`FUN_10032afa`, the rect fill, has zero callers in all 30 modules.** So SC3U reads, counts, saves,
loads and colours a mark that no shipped x86 code produces. `[UNCERTAIN]` whether the retail x86
writer was removed or merely lives in uncarved code — the vtable-contents gap makes the export
unable to answer, and the honest reading is that this is not yet decided.

## Why this reconciles every earlier observation

| observation | under `kPloppedBuilding` |
|---|---|
| absent from all 21 bare terrains | no buildings have been placed |
| large contiguous blobs, runs to 36, 8.57x self-adjacent | building footprints, stamped as rects |
| depleted next to every declared zone class | a footprint's interior neighbours are its own tiles |
| no file declares slot 22 | correct: **no developer builds it**, the player places it |
| four consumers treat it as a second kind of "empty" | the query tool literally reports it as **"Unzoned"** (LTEXT 405, the default arm) |
| `0x10032ca9` clears it to 0 when an occupant's rect is processed | the building was removed, so the mark goes |
| shares colour `0x22` with `0x10` | both are non-developer marks (Spaceport, PloppedBuilding) |
| **not** correlated with the SIMGEOM tile grid (§4 above) | consistent: that grid is not an occupancy map |

Confidence: **C3** — behaviour confirmed against a second witness (the iOS sibling) with the x86
naming pinned at eleven independent points by two unrelated x86 functions. Not C4: no runtime
observation, and the x86 producer's absence is measured but not explained.
