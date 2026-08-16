# QFS.md — the QFS / RefPack compression used for sprite pixel data

Identified 2026-08-15 in `SIMSPR.DLL`, and **verified against shipped data**. This is the same
QFS/RefPack scheme used by SimCity 4 and The Sims, so it is publicly documented and independently
implementable — which makes it the most reusable finding in the project so far.

## Where it sits in the chain

```
Apps\Res\Sprites\*.DAT            .IXF container (formats/IXF_segment.md)
  └─ 20-byte index record {group, instance, type, offset, size}
       └─ type-0 record payload:
            +0x00  dword0   bits 8..15 = FORMAT CODE   (bits 0..7 passed to the pixel decoder)
            +0x04  dword1   flags; ALSO the pixel-format selector at FUN_1001e086
            +0x08  dword2   width   (equals the inner header's width; see below)
            +0x0c  dword3   height
            +0x10  dword4   length of the stream that follows
            +0x14  QFS stream (magic 0x10FB)
```

**The header is five dwords (0x14), not four.** Both dispatch paths pass `payload + 0x10` to the
wrapper, and the wrapper adds 4 before decompressing —
`FUN_10050d09((byte *)(param_1 + 4), ...)` `[CONFIRMED @0x1001ddb8:17]`, mirrored by
`FUN_1001de0c -> FUN_10050cdf(param_1 + 4)` `[CONFIRMED @0x1001de0c:16]`. So the stream begins at
`+0x14` **in every case** and `dword4` is a length the wrapper skips.
Verified on all 63,691 shipped type-0 records (see "Validation" below).

Decoder: `sc3spr_decode_record` `0x1001de49` — vtable `PTR_FUN_10063598` **slot 6 (+0x18)**,
reached from `sc3spr_provider_make_bitmap` `0x10012d91`. It reads the record into a 49,120-byte
stack buffer when `size < 0xc011`, else `operator_new(size)`, then dispatches:

| format code | path |
|---|---|
| `0` | `FUN_1001e086` — **a pixel-format dispatcher, NOT "uncompressed"** (corrected 2026-08-15) |
| `1` **and** `(flags & 0x8000) == 0` **and** `(flags & 0x80000) != 0` | `FUN_1001de0c` (get output size) → `FUN_1001ddb8` → **QFS** |

`FUN_1001e086` `[CONFIRMED @0x1001e086]` switches on `dword1` and calls a different decoder per
value — `1`→`FUN_1001e1b4`, `2`→`FUN_1001e258`, `4`→`FUN_1001e338`, `8`→`FUN_1001e41f`,
`0x10`→`FUN_1001e513`, `0x80`→`FUN_1001e615`, `0x100`→`FUN_1001e73d`, `0x8000`/`0xc000`→
`FUN_1004efdd`. Separately, `(dword1 & 0x10000000) != 0 && (dword1 & 0x8000) == 0 &&
(dword1 & 0x80000) != 0` → `FUN_1001e869`, **which is also QFS**: it decompresses via
`FUN_1001ddb8` and then `memcpy`s the result row by row into the surface (`vt+0x3c` rows of
`vt+0x38` bytes, destination stride `vt+0x1ac`) `[CONFIRMED @0x1001e869:31,50,56-60]`. That
output is therefore a **plain row-major bitmap with no inner header** — 1,139 shipped records
(`format 0`, `dword1 = 0x10080000`) take this path and are the simplest route to an image.

> The vtable slot was invisible to the text export (function pointers live in `.rdata`). The
> worker correctly refused to guess the decoder and named the exact blocker; it was resolved with
> `re/scripts/VtableDump.java`.

## The format `[CONFIRMED]`

**Header** — `sc3_qfs_get_uncompressed_size` `0x10050cdf`:
```
if (u16be at +0 == 0x10FB)  header is 2 bytes
else                        header is 5 bytes          # decompressor uses (*p & 1) to decide
then 3 bytes big-endian     = uncompressed size
```

**Control-byte loop** — `sc3_qfs_decompress` `0x10050d09` (441 bytes). Canonical QFS:

> ⚠️ **Corrected 2026-08-15.** The earlier version of this table understated every back-reference
> length by 1 and left the 3- and 4-byte forms as "follows the standard layout". All four forms
> are in fact fully visible in the decomp and are transcribed exactly below. The off-by-one is
> real: the copy loops are `do { ... } while (n-- != 0)`, which executes **n+1** times
> `[CONFIRMED @0x10050d09:47-53]`. Likewise each offset is `+1`, because the source pointer is
> computed as `out + (-X) - 1`. The corrected values match canonical RefPack, so the old table
> was the error, not the binary.

| control byte | form | literals | back-ref length | back-ref offset |
|---|---|---|---|---|
| `0x00`–`0x7F` | 2 bytes | `c & 3` | `((c >> 2) & 7) + 3` | `((c & 0x60) << 3) + b1 + 1` |
| `0x80`–`0xBF` | 3 bytes | `b1 >> 6` | `(c & 0x3F) + 4` | `((b1 & 0x3F) << 8) + b2 + 1` |
| `0xC0`–`0xDF` | 4 bytes | `c & 3` | `((c & 0x0C) << 6) + b3 + 5` | `((c & 0x10) << 12) + (b1 << 8) + b2 + 1` |
| `0xE0`–`0xFB` | 1 byte | `(c & 0x1F) * 4 + 4` (a literal run, then continue) | — | — |
| `0xFC`–`0xFF` | 1 byte | `c & 3` then **stop** | — | — |

The run/terminator split is the test `if (0x70 < n) break;` `[CONFIRMED @0x10050d09:101]`, where
`n = (c & 0x1F) * 4 + 4`; `n` exceeds `0x70` exactly when `c >= 0xFC`.

Back-references copy **byte-by-byte from the output already written** (overlapping copies are
legal and intentional — a run of length > offset repeats).

## Verification against shipped data `[CONFIRMED]`

`Apps\Res\Sprites\00000002_Residential.DAT`, index record 0
(`group=0x00000002`, `instance=0x00900000`, `type=0`, `offset=575940`, `size=667`):

```
payload  07 01 00 00  00 00 08 00  10 00 00 00  16 00 00 00  8b 02 00 00  10 fb 00 02 ...
         └ dword0 = 0x00000107 -> format code 0x01  (compressed)
                      dword1 = 0x00080000 -> (&0x8000)==0 OK, (&0x80000)!=0 OK
                                                          └ +0x14: magic 10 FB
uncompressed size = 0x0002xx -> 758 bytes from a 667-byte payload
```

Every branch condition the decompiler shows is satisfied by the real bytes, and the magic lands
exactly where the code says it will.

## Validation — `re/tools/qfs.py` `[CONFIRMED, C4]`

Implemented 2026-08-15 and run over every shipped sprite archive:

| | |
|---|---|
| archives | **40** (36 `.DAT` + 4 `.IXF`, under `Apps\Res\Sprites`) |
| index records | **127,971** → 63,691 type-0, 62,387 type-1 |
| type-0 records decoded as QFS | **63,691 (100%)** |
| **size-check failures** | **0** |
| compressed → decompressed | 237,396,677 → 449,165,466 bytes (1.89x) |

Every stream's produced length equals the 3-byte big-endian size declared in its own header.
63,691 independent round-trips with zero failures meets the **C4** bar for the container +
compression layer. (The *pixel* encoding inside is a separate, still-open question — see Open.)

> ⚠️ **Corrected count.** `HANDOFF.md` claimed "72 sprite archives, 253,838 index records
> (127,382 type-0 + 124,774 type-1)". Those figures are **exactly double-counted**:
> 127,382 = 2 x 63,691, 124,774 = 2 x 62,387, and 72 = 2 x the 36 `.DAT` files. The earlier
> sweep walked the `.DAT` files twice and missed the 4 `.IXF` archives. Corrected figures above.

## Open
- ~~The pixel encoding~~ — **BOTH CLASSES SOLVED 2026-08-15, C4.** See "Plain-bitmap class" and
  "Span-sprite class" below. The whole sprite pipeline now decodes to images.
- The `.SII` text mirrors beside each `.DAT` (10 files) may name the records; worth reading as a
  free cross-check.

## The plain-bitmap record class `[CONFIRMED, C4]`

`format code 0` **and** `dword1 == 0x10080000` — **1,139 records across 12 archives**
(`00000010_Smoke`, `EffectSprites`, `disaster_LOCUST/SPACEJUNK/TOXICCLOUD/WHIRLPOOL`,
`GAME_UI`, `1000484E_nu18510`, `1000484F_DS18511`, `10004850_DS18512`, `10004854_GY18516`,
`10004856_LO18518`).

Renderer: `re/tools/sprite_render.py`.

**Geometry** — `width = dword2`, `height = dword3`. The declared uncompressed size equals
`width * height` **exactly, for 1139/1139 records**, so `bytes_per_row == width` and the image is
**8 bits per pixel, one byte per pixel, row-major, top-down**. This agrees with `FUN_1001e869`,
which copies `vt+0x3c` rows of `vt+0x38` bytes `[CONFIRMED @0x1001e869:56-60]`.

**Pixel values** — every byte of every one of the 1,139 records lies in **0..31 inclusive**
(global min 0, max 31, 32 distinct values, contiguous; value 0 is ~71% of all bytes). The range
never reaches 32, so the stored quantity is **5-bit**, not an 8-bit palette index.

**It is a single-channel coverage/alpha mask, not colour.** Verified by rendering all 1,139 as
intensity and inspecting them: `00000010_Smoke` yields coherent rising-smoke animation sequences
at several zoom levels (smooth gradients, correct row order, no shearing or stride drift), and
`GAME_UI` yields clean hard-edged isometric building and tree silhouettes. A palette-index buffer
would not produce *both* correct smooth gradients and correct hard silhouettes when read as
intensity. That is behaviour reproduced from shipped data, i.e. **C4**.

**Confirmed as ALPHA by a second witness** — the shipped `.SII` text mirrors label exactly the
format-0 records `Alpha` (90 labelled `Alpha` ↔ format 0, 8,042 unlabelled ↔ format 1, zero
exceptions). See `formats/SPRITE_SII.md`. That is Maxis' own art-pipeline text, independent of
the decompilation and of the visual inference.

`[UNCERTAIN]` which colour the mask is modulated against, and whether the 5-bit range is enforced
by code or is merely a property of the shipped art. Also note the `.SII` evidence covers 90 of
the 1,139 format-0 records; nothing contradicts it on the rest, which share the same 0..31 range.

## The span-sprite record class `[CONFIRMED, C4]`

`format code 1` — **62,552 records**, i.e. the main art: buildings, flora, vehicles, UI.
Renderer: `re/tools/sprite_render.py`.

After QFS decompression the block is **self-describing**:

```
+0x00  u32  total size            == len(block)
+0x04  u16  width                 == record dword2
+0x06  u16  height                == record dword3
+0x08  u16  a                     (4 in every shipped record)
+0x0a  u16  b                     (7, or 5 for the 90 RGB555 records - see below)
+0x0c  u16  colour key            (0xF81F, or 0x7C1F for those 90)
+0x0e  u16  pad                   (0 in every shipped record)
+0x10       height x { u32 pixelOffset, u16 x, u16 flags }     <- one entry PER ROW
            span length n = flags & 0x7FFF
then        pixel data, ONE u16 PER PIXEL
```

Each row stores a **single horizontal span**: `x` is where it starts, `n` how many pixels it
holds, `pixelOffset` where those pixels sit in the data section (in u16 units, not bytes).
Pixels outside a row's span are simply **not stored** — that is a second layer of compression on
top of QFS, and it is why the data section is far smaller than `width * height`.

**Pixel layout — two variants, and the colour key identifies which:**

| key | header `b` | layout | records | note |
|---|---|---|---|---|
| `0xF81F` | 7 | **RGB565** | 62,462 | `0xF81F` is magenta in 565 |
| `0x7C1F` | 5 | **RGB555** | 90 | `0x7C1F` is magenta in 555 |

Both keys decode to the *same colour* (magenta) under their own layout — that is what ties the
layout to the key rather than to a guess. `b` correlates perfectly with the key across all
62,552 records.

### Round-trip: byte-identical re-encoding `[CONFIRMED, C4 — the strongest result here]`

`re/tools/sprite_encode.py` transcribes the shipped encoder `FUN_100017de` (16bpp branch). For
every shipped record it: decodes the block to a full pixel surface, re-runs the encoder over that
surface, and compares the output **byte for byte** against the original block.

> **62,552 of 62,552 format-1 records re-encode BYTE-IDENTICAL. Zero mismatches.**

This is much stronger than "the images look correct". Producing identical bytes requires every
one of the encoder's decisions to be reproduced exactly:

- the leading and trailing colour-key scan boundaries (so `x` and the span length match),
- the `0x8000` opaque flag on every single row,
- the empty-row case (`x = width`, span 0, flag set) — reached only when a row is entirely key,
- the running pixel-offset accumulation across all rows,
- every header field, including the literal `4` at `+0x08` and the pixel-format id at `+0x0a`.

A misunderstanding of any of them diverges the bytes. This meets the project's C4 bar
("a parser round-trips") in its literal sense.

### Independent second witness: SIMBABLD `[CONFIRMED @0x1204bcf7]`

The BAT authoring tool (`SIMBABLD.DLL`, image base `0x12000000`) consumes the **same** layout,
which corroborates it from a different module entirely. Its blitters
(`0x1204bcf7`, `0x1204d120`, `0x12049d83`, `0x1204a96c`) do:

```c
iVar10   = *(int *)((int)this + 4);                     // the block
local_2c = iVar10 + 0x10 + (u16 at iVar10+6) * 8;       // data start = +0x10 + height*8
local_10 = (int *)(iVar10 + 0x10 + uVar13 * 8);         // row entry, stride 8
uVar7    = (uint)*(ushort *)((int)local_10 + 6);        // flags at row+6
```

16-byte header, height at `+6`, row table at `+0x10` with stride 8, flags at row `+6` — the same
structure the round-trip proves. Transparent colour is held at the blitter object's `+0x1c`.

### Structural validation `[CONFIRMED, C4]`

Seven independent predictions were checked against **all 62,552** shipped format-1 records:
inner total == block length; inner `w,h` == record `dword2,dword3`; the row table fits; spans
**chain exactly** (`row[i].off + n == row[i+1].off`, no gaps and no overlap); the last span ends
precisely at the end of the data section; `x + n <= width` for every row; and the data section is
even-length.

**62,552 of 62,552 pass all seven. Zero failures.**

Confirmed further by rendering: `00000002_Residential.DAT` produces clean isometric apartment
blocks and high-rises in correct colour with correct transparency (trees, cars, rooftop pools all
legible). A wrong stride, wrong span chain or wrong channel order cannot produce coherent
isometric art.

### How the code reaches it

The consumer was invisible to the decompiler because it is a **QueryInterface + vtable call**.
Raw disassembly of `0x1001de49`'s tail (via the new `re/scripts/DumpDisasm.java`) shows:

```
1001df5d  PUSH 0x487534f          ; IID
1001df64  CALL [EAX]              ; param_1->vt[0](0x487534f, &iface)  = QueryInterface
1001df6d  PUSH 0x1
1001df6f  PUSH [EBP-0x1c]         ; the decompressed block
1001df74  CALL [EAX + 0xc]        ; iface->vtable slot 3 (block, 1)    = the consumer
```

### The class behind IID `0x0487534f` — RESOLVED `[CONFIRMED]`

Found by byte-scanning the module binaries for the IID immediate (the decompiler drops these
pushes, and Ghidra never carved the relevant functions, so grep over the text export finds
nothing — including the decimal form).

`FUN_1001daf5` (SIMSPR slot 7, `0x1001dc67`-`0x1001dc7e`) shows the creation, not just a QI:

```
1001dc67  CALL 0x1004f6e0        ; get the GZCOM class factory
1001dc71  PUSH ECX               ; &out
1001dc72  PUSH 0x487534f         ; IID
1001dc77  PUSH 0xa487535d        ; CLSID
1001dc7e  CALL [EDX + 0xc]       ; factory->CreateInstance(clsid, iid, &out)
```

So `0x0487534f` is an **IID** and the implementing class is **GZCLSID `0xa487535d`**, which lives
in **`GZGraphicD.dll`**, not SIMSPR:

| | |
|---|---|
| registered by | `FUN_100011ef` (GZGraphicD director) `[CONFIRMED @0x100011ef]` |
| factory | `FUN_100012b5` — `operator_new(0x38)` (56 B), returns **object+4** |
| ctor | `FUN_10001484` — installs `PTR_LAB_1001e3c8` at +0, **`PTR_LAB_1001e328` at +4** |
| the IID-`0x0487534f` vtable | **`PTR_LAB_1001e328`** (because the factory returns +4) |
| slot 3 (`+0xc`) = the consumer | `FUN_10001700` — adopt/copy the block |
| slot 5 (`+0x14`) = the **encoder** | `FUN_100017de` — builds the block from a 16bpp surface |

`FUN_10001700` `[CONFIRMED @0x10001700]` independently confirms the header from *code*: it does
`operator_new(*block)` + `memcpy(_Dst, block, *block)` when the second arg is 0 (so `+0x00` is the
total size; SIMSPR passes 1, meaning adopt-without-copy), then calls the owner's `vt+0xc8` with
the **u16 at `block+0x0c`**, and reads width from `+0x04` and height from `+0x06`.

> **`vt+0xc8` IS the colour-key setter after all.** An earlier note here doubted that because the
> `+0xc8` call at SIMSPR `0x10012e20` passes `DAT_1007276c`, a global with zero writers. That is a
> different (default/reset) call site. The real per-sprite key is set here from `block+0x0c`.
> U-024 is resolved as "the original premise was right".

### `a`, `b` and flags bit `0x8000` — RESOLVED `[CONFIRMED @0x100017de]`

The encoder `FUN_100017de` writes every header field, which names them:

| field | encoder line | meaning |
|---|---|---|
| `+0x08` (`a`) | `*(u16*)(buf+8) = 4` | a **hardcoded literal 4**. Not derived from anything — a format/version tag. That is why it never varies. |
| `+0x0a` (`b`) | `*(u16*)(buf+10) = *(u16*)vt0x50_result` | the **pixel-format id**, read from the surface's pixel-format descriptor (`vt+0x50`). The same descriptor's `+4` is the bit depth, tested `== 0x10` (16bpp) at the top of the encoder. Hence 7 = RGB565, 5 = RGB555. |
| flags bit `0x8000` | `*(u16*)(rec+6) = -(u16)bVar1 & 0x8000 \| (u16)len` | **"this span is fully opaque"**. The encoder scans the span and clears `bVar1` the moment any pixel equals the colour key. Set = no key pixels inside = the blit fast path. |

The encoder also re-confirms the geometry independently: it allocates
`(width+1)*height*2 + 0x10` (16-byte header, 2 bytes per pixel) and walks the row table with
`local_2c = 0x10` incremented by `8` per row.
