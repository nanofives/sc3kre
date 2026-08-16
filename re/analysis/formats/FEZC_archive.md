# FEZC archive (`data.fez`) — iOS FusionEngine container

`Payload/SimCity DLX.app/data.fez` — 76,237,772 bytes. The iOS game's virtual filesystem.
NOTE: this is the **iOS** asset pack (FusionEngine), not the desktop SC3U data — but the
`.gvf` string blobs (`sc3strings…`) are SC3-derived, so it's a lead for SC3 text/data layout.

## Header (little-endian) — partially decoded
```
00: 46 45 5A 43            "FEZC" magic
04: 00 00 01 00            version? (0x00010000)
08: 55 13 00 00            0x1355 = 4949   (entry count?)
0C: 28 00 00 00            0x28            (offset to TOC / header size?)
10: AE 2D 04 00            0x042DAE                 (?)
14: 4E 98 06 00            0x06984E                 (?)
18: A4 0D 0F 31 AD 58 86 89 0E 44 38 AA A9 37 B8 C3   16-byte hash/GUID/key
28: <TOC begins>
```

## FORMAT — FULLY DECODED (parser: `re/tools/fez_extract.py`, 4949/4949 extracted, validated)
Header fields are pointers: `h0c=0x28` = path-table start, `h10` = meta-table start
(= end of path table), `h14` = data start.

- **Path table** @ `h0c`: `fileCount × [u32 len][len bytes incl trailing NUL]`.
- **Meta table** @ `h10`: `fileCount × 32-byte records`, SAME order as the path table:
  - `+0x00` u32 `field0` — per-entry, **NOT the size** (role `[UNCERTAIN]`; ~0x106 on early entries).
  - `+0x04` u32 `dataOffset` (absolute). Entries **tile the data region contiguously**.
  - `+0x08` 16-byte per-entry hash.
- **File size** = next entry's `dataOffset − thisOffset` (last = EOF − offset). Verified:
  `offs[0]==dataStart`, chain contiguous, last ends exactly at EOF, sum = data-region size.

## Payload encoding — SOLVED
- Already-compressed formats stored **raw**: `.png` (89504e47), `.caf` audio (RIFF 52494646).
- All other entries are a **single zlib stream** (`78 da`). Inflate with
  `zlib.decompressobj().decompress(blob)` — **not** `zlib.decompress()` (intolerant; raises
  -5/-3 on these). Verified **4321/4321 zlib entries inflate cleanly, 628 stored raw**.
  `fez_extract.py <fez> <out> --inflate` writes decompressed files.
- Record `field0` is **not** the uncompressed length (matched only 2/4321) — role open (U-002).

## Inner format: `.gvf` = `FE_GVF_BIN_0001`
Decompressed `.gvf` files start with ASCII magic **`FE_GVF_BIN_0001`** (FusionEngine GVF
binary) — a **keyed string/data table**. `strings.gvf` (8,210 B inflated) holds SC3 query/UI
keys: `QI_LABEL_TRAFFIC`, `QI_GRADE_D/F`, `QI_CRIME_HIGH/LOW`, `QI_FIRE_FAIR`,
`LC_CITY_SIZE_HISTORY`, `QI_LABEL_PERFORMANCE`, … Parsing the GVF key/value index = next P2 step.

## Asset tree revealed by the TOC (file types)
- `data/*.gvf` — packed string/data blobs (`package`, `app`, `strings`; the SC3 `sc3strings*`).
- `data/interface/*.ui`, `*.sm` — UI layout / state machines; `hierarchy_pc.ui` (a "pc" variant!).
- `data/game/effects/seasons/*.spr` + `*.pvr` — sprites + **PowerVR-compressed** textures.
- `data/interface/**/*.png` — UI PNGs incl. `.../rci/background*.png` (the RCI meter chrome).

## Value to the project
- Confirms the SC3 asset taxonomy (RCI, seasons/disasters like `plague`/`blizzard`, interface).
- `.gvf` blobs are the string/data container to reverse for P2; the `sc3strings` names map 1:1
  to the `data/sc3strings/*.gvf` paths embedded in the iOS binary (advisor/petitioner/newsticker).
- TODO (P2): decode the FEZC offset table → extract `.gvf`/`.pvr`; compare `.gvf` layout against
  SC3U's on-disk data files to bridge desktop ↔ iOS data formats.
