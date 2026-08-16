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
+0x08  u32   0x00020003 (.sc3/.snr)  |  0x00030003 (.sct/.st3)
+0x0c  u32   0xDEADBEEF               literal marker, all 59
+0x10  u32   0x40510625 (.sc3/.snr)  |  0x0000000d (.sct/.st3)
+0x14  ...   section payloads, laid out contiguously
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

`[UNCERTAIN]` group `0x029ca804` occurs once per file and sits **2 below** the pinned
`TrafficLayer` id `0x029ca806`. It is *not* treated as a match — a near-miss id is a different
class, not a typo.

`[UNCERTAIN]` what the `offset` field is relative to. The smallest observed is 8, which falls
inside the 0x14 header if the base is 0, so it may be relative to `+0x14` or the first entry may
be a sentinel. Unresolved, and it does not affect section sizing (derived from deltas).

**Grid-size lead:** Berlin's section `406b1196:80ab8ab0:0` is **65,552 bytes = 65,536 + 16**,
i.e. a **256 x 256 byte grid** plus a 16-byte header. `[UNCERTAIN]` — one section, not yet
generalised across files, and no consuming code read.

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

| instance | size | content |
|---|---|---|
| 0 | 50,274–198,060 (varies per city) | the bulk zone data |
| 2, 3, 4 | 4 | `0x619FF3CE` |
| 6, 7, 8 | 4 | `0x41A00001` |
| 10, 11, 12 | 4 | `0xE1A00030` |
| 15 | 4 | `0xC1F5C0BE` |
| 16 | 4 | `0x82D4A0EB` |
| 18 | 4 | `0x82361BE5` |

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

**Second attempt also failed.** Re-ran with `0x17` treated as an **element count** rather than a
byte length, sweeping element sizes 1/2/4/8 bytes and `vt+0x68` widths of 1/2/4 bytes — 12
parameter combinations, every start offset in the first 4 KB, requiring exact consumption to the
section end. **Zero fits.** Combined with the first attempt's full-range scan, that makes the
most likely culprit the **section boundary**, not the grammar: section sizes here are derived
from offset deltas because the table has no size field, and the `offset` field's base is still
`[UNCERTAIN]`. Pin the offset base first; re-testing the grammar before that is wasted effort.

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

**Names remain NOT determined.** Next step, and it is a small one: force-carve functions at
`0x1000e837`, `0x1001599d` and `0x1002115d` with `re/scripts/MakeFunctions.java`, then read them.
If those turn out to be methods of the same class, the mapping is proven.
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
