# Replacing SimCity 3000 sprite art — the working procedure

**Status: validated in the running game, 2026-08-19** (`verify/sprite_mod_test/RESULTS.md`, two
rungs: a flat recolour and an authored pattern imported from PNG files). This is a how-to, not a
format spec — the pixel format itself is in [QFS.md](QFS.md) and the container in
[IXF_segment.md](IXF_segment.md).

Tool: `re/tools/sprite_patch.py`.

## Where the art is

`Apps\Res\Sprites\` — 40 containers. The extension is `.DAT` but **they are `.IXF` containers**;
`ixf_parse` selects on magic `0x80C381D7`, not extension. Inside, each sprite is two records:

| type | contents |
|---|---|
| `0` | a 0x14-byte header + a **QFS-compressed** pixel block (63,691 records) |
| `1` | an 8-byte anchor / registration point (62,387 records) |

These are all **world** art — vehicles, roads, buildings, people, flora, disasters, city objects.
`GAME_UI.DAT` is the one apparent exception and is not general UI: per its shipped `GAME_UI.SII`
sidecar it holds only the New City scheme-picker backgrounds and flora thumbnails.

> **The UI chrome sprites are NOT here.** Where the toolbar, dialogs and status bar get their art
> is **unknown**. If you want to reskin the UI, that is unsolved.

## The three-command workflow

```
# 1. see what is in a container
py -3.12 re/tools/sprite_patch.py Apps/Res/Sprites/GAME_UI.DAT --info

# 2. export a record to PNG
py -3.12 re/tools/sprite_patch.py Apps/Res/Sprites/GAME_UI.DAT --export 21 --png mine.png

# 3. edit mine.png in anything, then import it
py -3.12 re/tools/sprite_patch.py Apps/Res/Sprites/GAME_UI.DAT \
        --import-png 21=mine.png --out GAME_UI.DAT.modded
```

`--import-png` takes a comma-separated `slot=file.png` list, so several records go in one pass.
Then back up the shipped file and copy yours over it. **There is no loose-file fallback for these
containers** — you are replacing the archive in place, so keep the original.

Export uses `sprite_render.span_to_image()`, the decoder already validated against the whole
corpus, so what you edit is by construction what the game reads.

## The four rules you cannot ignore

### 1. The size must match exactly

`image_to_surface()` refuses a mismatch and tells you the expected dimensions. Changing a sprite's
size is **untested**: the type-1 anchor record and the `.SII` span/registration values would have
to move with it. Resize your image instead.

### 2. There is no alpha channel — only a colour key

The format stores one 16-bit value per pixel and a per-record **colour key** meaning
"transparent". So alpha is a threshold, not a channel: `--alpha-threshold` (default 128) decides
where the cut falls. **Soft edges will harden.** Anti-aliased art will show a hard boundary.

### 3. You cannot draw opaque magenta

Both shipped colour keys decode to `(255, 0, 255)`:

| key | header `+0x0a` | layout | records |
|---|---|---|---|
| `0xF81F` | 7 | RGB565 | 62,462 |
| `0x7C1F` | 5 | RGB555 | 90 |

An opaque magenta pixel quantizes straight onto the key and would silently turn into a hole. The
tool moves those pixels one step in blue and **reports the count**, so read that line.

### 4. Colour depth is 16-bit, and the conversion is exact

`quantize565(r,g,b) = ((r>>3)<<11) | ((g>>2)<<5) | (b>>3)` is the **exact inverse** of the
decoder's expansion, verified over all 65,536 values (and all 32,768 for RGB555). So an
export → import round-trip is **byte-identical**, which is the bar `--pngtest` enforces.

What that does *not* mean: your 24-bit source art still loses depth going in. 5/6/5 bits gives 32
red levels, 64 green, 32 blue. Gradients will band.

## Verifying before you ship

```
py -3.12 re/tools/sprite_patch.py Apps/Res/Sprites --selftest   # identity repack, byte-identical
py -3.12 re/tools/sprite_patch.py Apps/Res/Sprites --pngtest    # PNG round-trip, byte-identical
```

Measured 2026-08-19: identity repack **40/40 containers**, PNG round-trip **62,552/62,552 records**
byte-identical. Both are N/N bars over the shipped corpus. If either regresses, the writer is
wrong, not the game.

## What the write path actually does

The three links that did not exist before `sprite_patch.py`, in case they need re-deriving:

1. **the 0x14 record header** — `qfs.record_header()` only unpacks. `pack_payload()` writes it,
   carrying `d0..d3` through unchanged and recomputing **`d4 = len(stream) + 4`**. Measured on the
   corpus (e.g. `00000005_Roads.DAT` rec 1: size 4545, stream 4525, d4 4529). Note
   `qfs.decode_record`'s `d4_matches_stream` diagnostic is **False on every shipped record** — it
   is not the rule.
2. **index recomputation** — `ixf_parse.build()` writes payloads at their recorded absolute
   offsets and raises on overlap. `repack()` re-emits payloads in offset order from the original
   first-payload offset and rewrites every slot's offset/size. It **refuses non-contiguous
   containers** rather than guessing what unreferenced bytes mean (`ixf_parse.layout()` documents
   two real cases in this corpus).
3. **compression** — `qfs_encode.compress_stream(block, quick=1)`; `quick=1` is the shipped mode.

## Finding WHICH records a given thing uses

This was the hard gap: nothing shipped maps "the building I can see" to a slot number. There are
now two answers, one structural and one empirical.

### Ask the game's own table — do NOT compute the instance

**The mapping is data, not arithmetic, and the code proves it.** `SIMSPR FUN_100155bf`
@ `0x100155bf` builds the key `{type 0x6301, group 0x6400, instance = occupantId}` and hands it to
the resource manager. **There is no shift and no OR anywhere on that path.** The `objectId << 16`
pattern is an authoring convention baked into a shipped table, not something the engine derives.

The chain is three data hops:

```
OccupantAttribs*.IXF  TKB1 record   prop 0x64 = name,  prop 0x67 = {type, group, instance}
<attrib table>        (group, instance) from prop 0x67  ->  frame table of (group, instance)
Apps\Res\Sprites\*.DAT              those (group, instance) pairs  ->  pixels + anchor
```

### The name source

`Apps\Res\Occupant\OccupantAttribs*.IXF` records are `TKB1` blobs of
`[u32 propId][u16 type][u16 count][payload]`, where type `7` = `u32 len` + chars, `3` = u32 array,
`8` = `count` x 3-dword GZ key. **1,108 of 1,108** records carry both properties below
[CONFIRMED, read byte by byte on the Coal Power Plant]:

| prop | type | meaning | coal plant |
|---|---|---|---|
| `0x64` | 7 | authored name | `"Coal Power Plant"` |
| `0x65` | 3 | building type id | `0x00002F4F` |
| `0x66` | 3 x3 | footprint in tiles | `(4, 5, 4)` |
| `0x67` | 8 | **the attrib-table key** | `{0x6301, 0x6400, 0x000000CF}` |
| `0x7c` | 8 | localized catalog string | `{0x2026960b, 0x62e69238, 5}` |

> **Key on property 0x67's full `(group, instance)`, not on the instance alone.** The building and
> flora **set** archives (`Sprites\BuildingSets\*\BST_*.dat`, `MBE_*.dat`,
> `Sprites\FloraSets\*\Flora_*.dat`) are self-contained: each carries its **own** `BIN\r` attrib
> tables *and* its own `TKB1` occupant records at its own group id, so instance numbers collide
> across sets. Detect both record kinds by **magic**, not by filename or group — `BST_0004.dat`
> alone holds 144 attrib tables at group `0x5432D60F`.

Measured coverage of the whole shipped corpus:

| | count | share |
|---|---|---|
| `BIN\r` attrib tables found | 1,471 | — |
| of those, with a name | **1,465** | **99.6%** |
| sprite objects named | **1,358 / 1,433** | **94.8%** |
| pixel records covered by a name | **60,056 / 65,584** | **91.6%** |

The unnamed remainder is `GAME_UI.DAT`, the four `disaster_*` archives and `EffectSprites.dat` —
exactly the containers with no attrib table at all.

`CSATTRIB.IXF` record layout [CONFIRMED by reading the Coal Power Plant's record]:

| offset | field |
|---|---|
| `+0x00` | magic `BIN\r` |
| `+0x04` | u32 version (1) |
| `+0x08` | u32 SprInstCLSID |
| `+0x0c` | u8 ZoomCount (5 for buildings) |
| `+0x0d` | u8 RotCount (4) |
| `+0x0e` | u8 ZoomSetCount |
| `+0x10` | u32 LayerFlags |
| `+0x16` | u16 Frames (20 for buildings) |
| `+0x18` | `Frames` x 15 bytes: `u16 frameIndex, u32 group, u32 instance, u8 flag, u16, u16` |

`ZoomCount 5 x RotCount 4 = 20` frames, but buildings ship only **4** zoom levels of art: frames
16-19 **re-reference** the zoom-3 records with trailer `flag = 2`. That is why a simple building has
16 distinct pixel records, not 20.

So the one command you actually want:

```
py -3.12 re/tools/sprite_patch.py Apps/Res/Sprites --find-art "Coal Power Plant"
```

which prints every distinct record that draws it. And the whole index, with names attached:

```
py -3.12 re/tools/sprite_patch.py Apps/Res/Sprites --objects --csv re/data/sprite_objects.csv
py -3.12 re/tools/sprite_patch.py Apps/Res/Sprites/0000000B_Utilities.DAT --objects --object 0x00CF
```

`re/data/sprite_objects.csv`: **1,433 objects, 1,358 named (94.8%)**, covering **91.6% of pixel
records**. Names come from `OccupantAttribs*.IXF` property `0x64` (see above), with
`re/data/syspak/Occupant.ini` merged in as a fallback for group `0x6400` only — the one group its
flat `instance = name` form can be trusted to mean.

### The instance's internal layout — an authoring convention, only partly reliable

`objectId = instance >> 16` is **[CONFIRMED]** and is what groups the 1,433 objects.

The low word is documented in the authoring format as
`(animPage << 12) | (animFrame * 20) | (zoom * 4 + rotation)`, with `zoom` 0..4 and `rotation` 0..3,
matching `ZoomCount`/`RotCount` above. **Treat this as a convention, not a rule.** Two independent
checks against actual sprite dimensions:

- For the 596 objects whose low words are exactly `0x0000..0x000F`, it holds well: **585 of 596**
  have a width constant within each zoom and strictly increasing across zooms, and object `0x00CF`
  renders as a clean 4x4 sheet (32/64/128/256 px x 4 rotations).
- Corpus-wide it does **not** hold as geometry: only **41.1%** of static-art groups have a width
  constant per zoom. An earlier, tidier guess of
  `[15:12] kind / [11:4] frame / [3:2] zoom / [1:0] rotation` was **falsified outright** (1,022 of
  4,720 groups non-monotonic, every supposed zoom bucket with the same width range) — the real
  animation-frame stride is **20 decimal, not 16**, which is what broke it.

**Which is exactly why you read the frame table instead.** `--find-art` and `--objects` never touch
these bits.

> **The consequence you cannot skip: one building is up to 16 records, and for an animated one,
> hundreds.** Editing a single record changes the art at one zoom and one rotation only. That is
> why the whole-layer edits in `verify/sprite_mod_test/` looked complete and a single-record edit
> will look broken.

### The colour-index probe — ask the game which record it is drawing

When you can see a thing but do not know its record, make the art carry its own identity:

```
py -3.12 re/tools/sprite_patch.py "<f1.DAT>,<f2.DAT>" --index-probe \
        --out-dir probe/ --csv probe_map.csv
# stage probe/*.DAT over the originals, run the game, screenshot, restore, then:
py -3.12 re/tools/sprite_patch.py shot.png --decode-shot --csv probe_map.csv --box 0,0,1024,700
py -3.12 re/tools/sprite_patch.py shot.png --decode-shot --csv probe_map.csv --at 290,110
```

Every format-1 record is repainted a **unique flat 16-bit colour**, so one screenshot identifies
every visible record at once. Measured on 2 containers: **5,064 records probed, 438 identified as
visible in a single frame.**

**Why it is exact.** A sprite's 16-bit value reaches the framebuffer with **no shading, blending or
dithering** — measured as 99,802 screen pixels of one flat value with zero variation. So the pixel
can be quantized straight back to the record id.

> **One trap, and it will bite you if you compare colours by eye.** The FRAMEBUFFER expands 5/6/5
> to 8/8/8 by **shifting** (`0xF800` → `(248,0,0)`), while `sprite_render`'s PNG export expands by
> **scaling** (`0xF800` → `(255,0,0)`). Different numbers, same 5/6/5 bits, because `>>3` / `>>2`
> inverts either. An exported PNG is therefore very slightly darker-at-the-top-end than what the
> game displays; that is expected and does not affect round-trip fidelity.

### Worked example — the coal power plant

Wanted: the big shed with the rust-red roof and tall chimneys visible in Berlin.

1. Probed `0000000B_Utilities.DAT` + `00000004_Industrial.DAT` (5,064 records), ran, screenshotted.
2. Decoded the building's screen region: **19,844 px of one colour**, resolving to a single record.
3. Result: **`0000000B_Utilities.DAT` slot 2378, group `0x0000000B`, instance `0x00CF000C`,
   256x216** — object **`0x00CF`**. The probe silhouette matched the building outline exactly,
   including its chimney.
4. `--objects --object 0x00CF` then gave the full set: **16 pixel + 16 anchor records**, widths
   32/64/128/256. Rendering all 16 showed a four-chimney Battersea-style coal plant (the in-frame
   one was clipped, which is why only two chimneys were visible and why an earlier size-based
   search had failed).

**Then the static chain confirmed it independently, which is the part worth trusting.**
`Occupant.ini:158` reads `0x207EDC0E,0x0000057E,0x000000CF=(207) Coal Power Plant`, and
`CSATTRIB.IXF` instance `0xCF` is a `BIN\r` v1 record — ZoomCount 5, RotCount 4, Frames 20 — whose
frames 0-15 reference group `0x0000000B` instances `0x00CF0000..0x00CF000F` and whose frames 16-19
re-reference `0x00CF000C..F` with `flag = 2`.

> **Two unrelated methods agreed on `0x00CF`**: a colour probe that reads pixels off the screen, and
> a shipped name table read off disk. Neither used the other's assumptions. That is the strongest
> form of evidence available here, and it is why the identification is stated without hedging.

So in practice you do not need the probe for anything the occupant tables already name — use
`--find-art`. The probe earns its place for art the tables do **not** cover (see the gaps): terrain,
UI, and the archives with no attrib table.

An earlier attempt to find this same building by matching its **on-screen size** against record
dimensions returned two chemical plants — wrong, because the building was clipped at the frame
edge. The probe does not care about size, position, clipping or zoom.

## Known gaps

- ~~**No record → on-screen-object index.**~~ **CLOSED 2026-08-19.** `--find-art` resolves a
  building name to its records via the shipped `CSATTRIB.IXF` tables; `re/data/sprite_objects.csv`
  indexes all 1,433 objects; the colour-index probe covers anything the tables do not name.
- **Name coverage is 94.8% of objects / 91.6% of pixel records.** The remainder has no attrib table
  at all: `GAME_UI.DAT`, the four `disaster_*` archives and `EffectSprites.dat`. How the engine
  reaches those sprites is `[UNCERTAIN]`; the colour-index probe is the route for them.
- `[UNCERTAIN]` the CSAttrib header byte at `+0x0e` (`ZoomSetCount`?) and `+0x0f`, and the exact
  meaning of each frame entry's trailer `u8 flag / u16 / u16`. `flag = 2` reliably marks the
  zoom-4 frames that reuse zoom-3 art; the two u16s are 0 in every record read.
- **The instance's low word is a convention, not a decodable rule** (see above). Enumerate via
  `--objects` / `--find-art`; do not compute "zoom 2, rotation 1, frame 5".
- `[UNCERTAIN]` why occupant property `0x67` uses resource type `0x6300` for most occupants and
  `0x6301` for a few; both are registered as factories at `SIMSPR 0x1004c611`.
- **The 1,139 format-0 records are alpha masks** (5-bit, 0..31) and are skipped by this tool.
  `[UNCERTAIN]` which colour they modulate ([QFS.md](QFS.md)). Many building thumbnails ship as a
  format-1 colour record paired with a format-0 alpha record (`...0000` / `...0001`); if you edit
  one of those pairs, the mask is **not** updated with it.
- **`-filetrace` does not observe `Apps\Res\Sprites\`.** The harness cannot confirm the game opened
  your archive, so a sprite change that fails to appear is ambiguous between "no effect" and "never
  read". Pick a marker that could not come from shipped art (the validating runs used flat red and
  hazard stripes for exactly this reason).
- **Dimensions and the anchor record** — see rule 1.
