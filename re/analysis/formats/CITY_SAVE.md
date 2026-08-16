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

## Inside the decompressed body

```
+0x00  u32   e.g. 0x3d
+0x04  u32   e.g. 0x20d7f7      slightly less than the total — a section length?
+0x08  u32   e.g. 0x00020003
+0x0c  u32   0xDEADBEEF          [CONFIRMED] present in ALL 59 files
+0x10  u32   e.g. 0x40510625
+0x14  ...   byte data in the 0x16..0x20 range
```

`[UNCERTAIN]` the byte run at `+0x14` is *consistent with* a terrain height map (values 22–32,
smoothly varying), but **no code that consumes it has been read**, so that is not asserted. Note
the `.sct` terrain files all decompress to ~1,521,4xx bytes — near-identical sizes across
different terrains, which is what a fixed-dimension grid would do.

## What is still open

1. **The decompressed body layout.** The container and compression are solved; the record
   structure inside is not.
2. Map the other `type`/`group` ids (the 24–94 byte records) to meaning. They repeat across
   files, so a cross-file diff against known city properties should name several cheaply.
3. **The decoding route is already identified:** GZCOM serialisers are **mirror pairs** — a
   reader calling stream `vt+0x38` on field *addresses* and a writer calling `vt+0x88` on field
   *values*, over the same offsets in the same order (first proven on the SIMGEOM pair
   `0x1001e516` / `0x1001e226`). **A serialiser's field order IS the on-disk layout.**
   Note the type id `0x035f62a4` appears in exactly one place in any binary —
   `GZResourceD.dll FUN_1000f5c4` — so the *sim-side* serialisers are keyed by something else and
   must be found via the `vt+0x38`/`vt+0x88` pairing test, not by grepping the id.

## Tooling

```
py -3.12 re/tools/city_parse.py "Cities"                    # validate every city file
py -3.12 re/tools/city_parse.py "Cities\X.sc3" --extract out\   # dump decompressed payloads
```
