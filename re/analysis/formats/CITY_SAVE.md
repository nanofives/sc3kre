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
