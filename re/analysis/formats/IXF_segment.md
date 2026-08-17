# IXF_segment.md — the GZ database segment (`.IXF`), and the localized-text chain

**U-008 CLOSED 2026-08-14.** The full path from a `SC3U.exe` UI string to bytes on disk is now
known end to end, code *and* data.

## The chain

```
SC3U.exe                sc3_gz_make_resource_key  0x00484b6d   {type=0x2026960b, group, instance}
   ctor tail       →    sc3_gz_reskey_resolve     0x004862e1   (*(*mgr+0x14))(triple, 0x69, out)
   mgr = GZCOM service CLSID 0x801998e4 / IID 0x1995e7   (framework DAT_004fab74, @0x00406ec6)
        │  not implemented in SC3U.exe
        ▼
GZResourceD.dll         director 0x10002d89 registers 0x801998e4 → factory 0x100033b1
                        ctor 0x10011ea4 (operator_new(0x104)), returns object+0x18
                        vtable PTR_LAB_1001d92c slot 5 (+0x14) = sc3_gz_resolve_key_to_string 0x10012c48
                        → sc3_gz_open_indexed_db 0x1000ca78   (magic + 20-byte index)
        ▼
Apps\Res\Text\<LANGUAGE>\*.IXF        7 languages, verified on disk
```

## File format `[CONFIRMED]`

```
magic  u32  0x80C381D7      ; on disk: D7 81 C3 80  (verified on 4 files)
index  N × 20-byte records: { u32 type, u32 group, u32 instance, u32 offset, u32 size }
       read via (*+0x38)(&buf, 0x14) @0x1000ca78
       all-zero record  = end of index
       fields == -1      = skipped slot
```
This is a **DBPF-style type/group/instance indexed archive** — the same key shape the whole GZCOM
engine uses. Record fetch is `cGZDBSegmentIndexedFile::DoOpenRecord` (error string `0x10022214`:
`"…DoOpenRecord(): Record not found: %d"`).

## Discovery at runtime `[CONFIRMED @0x10009337]`
Paths are built from the directory service's `%DataDirectory%` (`0x100221f0`) and
`%PluginDirectory%` (`0x100221dc`) + `PlugIn\` (`0x100221d4`), with the **`%Language%`** token
(`0x100221b4`) substituted — localization is one segment file per language. Files are enumerated
by the literal **`dbdfseg`** via finder service CLSID `0x25076b9e` / IID `0xa237613c`.

## Verified on disk
```
Apps\Res\Text\{DUTCH, ENGLISH, English-UK, FRENCH, GERMAN, ITALIAN, SWEDISH}\*.IXF
  e.g. BAMBEStringsMain.IXF 22,122 B · BATStringsMain.IXF 25,812 B · Betterfeld.IXF 26,968 B
Apps\Res\{AIRTRMGR, BUILDFAM, SIMSCRPT, TRNPROD}.IXF   ← same container, non-text payloads
```
All checked files start `d7 81 c3 80`. **They are NOT inside `SYS.PAK`** — a separate archive
family from the one `syspak_parse.py` handles.

## Group ids — DONE
All 8 group ids from `RESOURCE_KEYS.md` are resolved; see the table there. Each is the `group`
field of an index record, and each maps to one `.IXF` file (`SC3StringsApp`, `SC3StringsWindow`,
`SC3StringsGUI`, `SC3StringsMessage`, `SC3StringsCredits`, `SC3StringsNewstickerTriggered`,
`SEStringsUI`, `BATStringsMain`). Round-trip verified: group `0x29541f4` instance `0x2a6` =
`"System Info"`, exactly as `sc3_ui_create_sysinfo_window` `0x00436a94` predicted.

## Deleted/free index slots `[CONFIRMED — from BOTH the reader and the writer]`
Records whose `offset` or `size` is `0xFFFFFFFF` are free slots. They are **not** end-of-index:
the reader `0x1000ca78` (GZResourceD) skips them and continues. 58 of 537 files contain them — a
parser that stops there silently truncates those files (caught and fixed in `ixf_parse.py`).

**The writer proves where they come from.** `sc3_ixf_delete_or_compact` `0x1204f38e`
(SIMBABLD, base `0x12000000`) deletes a record by `memset(&rec, -1, 0x14)` — filling the whole
20-byte slot with `0xFF` — then seeking back 20 bytes (`(*+0x2c)(0xffffffec)`) and rewriting it
in place. So `0xFFFFFFFF` slots are tombstones from in-place deletion, exactly as the reader's
skip logic implies. Two independent witnesses, read and write sides.

## End of index: the KEY TRIPLE, not the whole record `[CONFIRMED]`
`0x1204f38e:68` terminates the index walk when the first **12 bytes** are zero
(`group == instance == type == 0`), ignoring `offset`/`size`. `ixf_parse.py` originally required
all five fields to be zero; corrected to match the game.

## The writer `[CONFIRMED]` — SIMBABLD.DLL is the first known .IXF producer
| function | role |
|---|---|
| `sc3_ixf_segment_ctor` `0x1200c5f5` | segment object, `operator_new(0x1a8)` = 424 B; `+0x54` stream, `+0x90` counter, `+0x94` record count, `+0x98` record list |
| `sc3_ixf_open_or_create` `0x1204f2e7` | on create: `(*+0xc)(3,3,1)`, truncate, then **write the 4-byte magic** `0x80c381d7` |
| `sc3_ixf_delete_or_compact` `0x1204f38e` | delete-in-place (tombstone) or full compaction, re-emitting the magic and recomputing every record offset via `FUN_1205c64e` |
| `sc3_bat_export_rendered_buildings_ixf` `0x12001faf` | the entry point: opens two segments (one read, one write) and exports buildings to `Res\BA\RenderedBuildingsBackup.IXF` |

The writer reads the index through the **same vtable slot `+0x38` with length `0x14`** as the
GZResourceD reader — independent confirmation of the 20-byte index record.

`[UNCERTAIN]` the on-disk field ORDER as written here. Our reader treats the triple as
`{group, instance, type}` (validated by the round-trip on real files), while the writer's
in-memory list node uses `+0x04/+0x08/+0x0c` for the triple and `+0x10` for the offset. Pinning
the writer's emission order needs a live-Ghidra look at `FUN_1205c64e`.

## Still open
- **The selector `0x69` (105)** passed as the second argument. It is hardcoded at
  `0x1000eab3:13` and `0x1000eafb:13`, both gated on `key.type == 0x2026960b`, then
  `record->vtbl[0](0x69, &out)`. Mechanically it selects which property of the record to emit;
  the record class's slot-0 implementation has not been read. `[UNCERTAIN]`
- **`1000000`** stored at service `+0x10` by `0x10017cf9`, and **`70000`** at manager `+0xf8` —
  both only *stored* in the code read; their readers are behind vtables. Do not assume "capacity".

## Parser — BUILT
`re/tools/ixf_parse.py` (mirrors `syspak_parse.py`).

```
py -3.12 re/tools/ixf_parse.py <file.IXF>                     # list + validate
py -3.12 re/tools/ixf_parse.py <file.IXF> --dump              # print every string
py -3.12 re/tools/ixf_parse.py Apps/Res --csv re/data/ixf_text.csv
py -3.12 re/tools/ixf_parse.py Apps/Res --find 0x029541f4:0x2a6
```

Full extraction: **537 files, 71,924 records, 0 unreadable** -> `re/data/ixf_text.csv`
(columns: file, language, group, instance, type, offset, size, text, note).

## Payload encoding `[CONFIRMED]`
Each record payload is `u32 length` followed by `length` bytes, NOT NUL-terminated. The bytes are
8-bit (cp1252 round-trips the accented Latin languages cleanly); no BOM, no UTF-16.

> **Localisation quirk (observed, not inferred):** the directory named `ENGLISH` contains
> **Spanish** text; the actual English strings live in `English-UK`. Verified on
> `BAMBEStringsMain.IXF` across ENGLISH / English-UK / GERMAN / FRENCH.

---

# ⭐ THE WRITER (roadmap gate T2, 2026-08-17): 657/657 containers rebuild byte-identically

`re/tools/ixf_parse.py` now reads **and writes**. `layout()` describes a container completely
enough to rebuild it, `build()` re-emits it, `roundtrip()` checks the result against the original,
and `--selftest` runs that over a tree.

```
py -3.12 re/tools/ixf_parse.py . --selftest
IXF container round-trip: 657/657 byte-identical
```

**The corpus is the whole install, selected by MAGIC rather than by extension** — which matters,
because the same container ships under eight different names:

| extension | files | bytes | what |
|---|---|---|---|
| `.IXF` | 537 | 30,933,438 | localized text |
| `.DAT` | 37 | 243,704,818 | sprite archives |
| `.SCT` `.SC3` `.SNR` `.ST3` | 64 | 26,247,307 | the city save family |
| **`.BLD`** | 17 | 1,681,087 | **also IXF containers** — not previously recorded here |
| `.CFG` | 2 | 44,339 | also IXF containers |

An extension filter would have tested a fraction of that and reported a clean `N/N`.

## Two findings that only appeared because the corpus was widened

### 1. String records use TWO size conventions `[CONFIRMED]`

A string record (type `0x2026960B`) is `u32 length + chars`, and **`size` does not always count
the same thing**:

| family | `size` means | payload occupies | how to tell |
|---|---|---|---|
| city `.SNR` | the string length, prefix **excluded** | `4 + size` | the `u32` at the payload start `== size` |
| localized `Apps\Res\Text\**` | the whole payload, prefix **included** | `size` | that `u32 == size - 4` |

So the extent cannot be decided from the record type. `payload_extent()` reads the length prefix
and lets the data say which convention the file uses.

> This started as an unconditional `size + 4`, generalised from 110 records across the 13 city
> `.SNR` files, and it round-tripped **59/59** of them. Against the localized-text corpus it failed
> **472 of 478**, every one off by exactly four bytes. **A rule confirmed on one family is not a
> rule about the format** — and 59/59 was a real number that licensed a wrong generalisation.

### 2. Orphaned payloads: data no index slot points at `[CONFIRMED]`

**58 of the 478 localized-text containers carry an orphaned string payload mid-file.** In
`SWEDISH\TransportationTutorial.IXF` it is 159 bytes at offset 22,589 that decode as a perfectly
normal record (`u32 155` then `"Vilken typ a…"`), with no slot referencing it. This is the same
phenomenon as `U-039`'s unreferenced `.SNR` tails, but in the middle of the file rather than after
the last payload.

The writer therefore preserves the **bytes** of every region between payloads instead of
zero-filling. Both cases look like in-place editing by Maxis' own tools that left the previous
payload behind.

## Consequence for the toolkit

The container writer no longer lives inside `city_roundtrip.py`, a test harness — that file now
delegates to this library, so there is one implementation rather than two that can drift. The
promotion paid for itself immediately: the harness copy carried the `size + 4` bug and would have
destroyed a string payload in 472 containers the first time anyone wrote one.
