# sprite_mod_test — does a sprite edit made with these tools change what the game draws?

**Written before the run. Predictions are committed here and are not to be edited afterwards.**

## Why this test exists

`sprite_encode.py` proved the block encoder byte-identical on 62,552/62,552 shipped records and
`qfs_encode.py` proved the compressor on 63,931/63,931 streams. Both are offline results. **No
sprite this project wrote had ever been in front of the game**, and unlike the city-save and
`SYS.PAK` paths there was no writer joining the two encoders to a file on disk at all — three
links were missing (the 0x14 record header, `.IXF` record replacement with offset
recomputation, and a pixel edit that leaves the span structure alone). They are now
`re/tools/sprite_patch.py`.

So this test carries two claims, and they are separable:

1. the new `repack()` produces a sprite archive the game accepts, and
2. a pixel edit we make reaches the screen.

## The marker

`Apps\Res\Sprites\00000005_Roads.DAT` — 6,676 records, **all format 1, all QFS**, 14.8 MB of
payload. Every visible pixel of every record is repainted flat red `0xF800`; pixels equal to the
transparency key `0xF81F` are left as the key.

Roads were chosen for one reason: in the verified camera position of `verify/tunable_mod_test`
the road network covers a large fraction of the frame, so the observation is a read-off and not a
judgement. That is the same rule the credits failure taught (`U-051`) and the pollution test
applied: **never use a marker a human has to judge.**

**Why recolouring is the safe edit.** `recolor_record()` only rewrites non-key pixels, so every
row's lead / span / opaque flag is unchanged and `sprite_encode.encode()` returns a block of the
**same length** as the shipped one. Verified on record 1 (slot 1, `0x00000005:0x2bcc0011`,
128x64): block 8,976 bytes before and after, transparency mask identical, resulting palette
exactly `{0xF800, 0xF81F}`. So the only variable is colour.

**The payloads still change length, and that is wanted.** Flat colour compresses far better than
asphalt: record 1's payload drops 4,545 → 502 bytes. Every subsequent payload offset therefore
moves, which exercises `repack()`'s index recomputation across 6,676 records — a much harder
test of that code than `SYS.PAK`'s M2 rung, which shifted offsets by 4.

## Pre-flight, offline — all of these must hold before the game is launched

| check | bar |
|---|---|
| identity repack on the whole sprite corpus | `sprite_patch.py Apps/Res/Sprites --selftest` → **40/40 byte-identical** |
| the patched container re-parses | same record count, same group/instance/type for every slot |
| every patched record decodes again | `qfs.decode_record()` → `qfs`, no size mismatch |
| dimensions preserved | every record's `w`,`h`,`key` unchanged |
| `d4` correct | `d4 == len(stream) + 4` on every patched record |
| the shipped file is untouched | `00000005_Roads.DAT` still at its pre-run SHA-256 |

## Prediction

**The road network renders solid red.** Asphalt, lane markings and intersections all become one
flat red; the road *shapes* stay exactly as they are, because only colour changed and the
transparency mask is identical.

**Negative control, and it is a real one: vehicles, buildings, terrain and UI stay normal.**
Cars are in `00000006_Vehicles.DAT`, buildings in `00000002/3/4_*.DAT`, and none of those files is
touched. So the cars driving on the red roads should still be their normal colours. If everything
on screen turns red, or anything outside the road layer changes, the edit did not do what it says.

## What each outcome means, written down BEFORE running

- **Roads render red; vehicles/buildings/terrain unchanged → the sprite write path is validated
  game-side.** Art modding becomes an available capability, not a claim, and `sprite_patch.py`
  earns its place in the T2 table. This also validates `repack()` on 6,676 shifted offsets.
- **Roads render normally, and `FILETRACE` shows the game opened our file.** The writer is
  exonerated offline by the pre-flight, so the finding is about the consumer: either roads at this
  zoom are drawn from a different container, or the archive is shadowed by something we have not
  found. Re-diff the staged file against shipped before concluding anything — the
  `ARM3_RESULTS.md` method rule.
- **Roads render normally and `FILETRACE` shows no read of our file → staging failed.** Not a
  result. Note that `00000005_Roads.DAT` is a loose file, not a `SYS.PAK` member, so the
  `FUN_004872e8` archive-first resolver does not apply to it; that is itself worth confirming in
  the trace.
- **Roads render as garbage / wrong art in the wrong place → `repack()`'s index is wrong**, i.e.
  offsets or sizes disagree with the payloads. The most informative failure available, and it
  would matter beyond sprites, because that is the same recomputation any multi-record edit needs.
- **The game crashes or fails to load → a defect in the record header (`d4`) or the index.**
  Distinguish from the above by whether anything drew at all.

## What this cannot tell you

It settles whether a sprite edit reaches the screen. It says nothing about *authoring* new art:
there is still no RGB→RGB565 quantizer and no PNG import path in `re/tools/`, so "replace this
sprite with my PNG" needs that converter written (about five lines, plus mapping alpha-0 to the
colour key). It also says nothing about the 1,139 format-0 alpha-mask records, which this edit
skips, or about sprite *dimensions* changing — every record here keeps its width and height.

## Staging and undo

```
copy  "Apps\Res\Sprites\00000005_Roads.DAT" "verify\sprite_mod_test\Roads.DAT.original"
copy  "verify\sprite_mod_test\Roads.DAT.red" "Apps\Res\Sprites\00000005_Roads.DAT"
```

UNDO, to be run even if the game crashed, and verified by hash, not assumed:

```
copy  "verify\sprite_mod_test\Roads.DAT.original" "Apps\Res\Sprites\00000005_Roads.DAT"
```

`Cities\` is not touched by this test and no city is saved during it.
