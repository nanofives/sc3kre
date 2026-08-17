# city_load_test — does the game load a file our writer produced?

This is the one claim the city-save toolkit cannot make offline. `re/tools/city_roundtrip.py`
proves the pipeline reverses (59/59 byte-identical) and `re/tools/city_write.py` proves an edit
lands where intended, but **no file this project produced has ever been loaded by SimCity 3000.**
Every "solved" claim about writing rests on structural checks only.

These four files isolate one variable each, so a failure names its own cause instead of leaving
"the writer is broken" as the only conclusion. Built 2026-08-17 from `Cities\Mount Herrang.sc3`
(the smallest shipped `.sc3`, N=128, so it loads fast).

## The ladder

| file | what differs from the shipped original | what a FAILURE here would prove |
|---|---|---|
| **T0** `T0_original.sc3` | nothing, a plain copy | the harness, the path or the copy step is at fault, not the writer. This is the control |
| **T1** `T1_rewritten_identical.sc3` | nothing — our writer re-emitted it and the result is **byte-identical** (verified, same SHA-256 as T0) | nothing about the writer. T1 and T0 are the same bytes, so any difference in behaviour is environmental |
| **T2** `T2_recompressed_same_content.sc3` | **bytes differ, content does not.** Same decompressed body byte-for-byte (verified), re-encoded with our QFS compressor's `quick=0` mode, which no shipped file uses. 147,566 bytes vs 153,366 | **our QFS compressor emits a stream the game cannot read.** This is the sharpest test in the set: zero content change, so only the compression path is under test |
| **T3** `T3_one_tile_landfill.sc3` | **exactly one byte**, verified: body offset 114,715, inside the zone raster, tile **(28, 0)** changed from slot 1 (Residential) to **17 (Landfill)** | the game rejects an edited zone raster — e.g. an unknown checksum, or derived state that must agree with the raster |

SHA-256 of each file is in `MANIFEST.txt`, so whoever runs this can confirm what they actually
loaded rather than trusting the filename.

## How to run it

The game reads cities from the install's `Cities\` folder, and this project does not write there
(that folder is game content). So a human has to opt in:

1. Copy one file at a time into `Cities\`, under a distinct name.
2. Launch the game and load it.
3. Record: does it appear in the load list, does it load, does the city look right, and for T3 does
   tile (28, 0) show as Landfill in the zone overlay.
4. Remove it again before testing the next one.

Do not copy all four in at once. The point of a ladder is knowing which rung broke.

## What each outcome means, written down BEFORE running

Committing to the interpretation in advance is the whole point, otherwise any result can be
rationalised after the fact.

- **T0 and T1 load, T2 loads, T3 loads** — the writer is validated end to end and the toolkit's
  central claim is no longer structural-only. `city_write.py`'s docstring limit 1 can be lifted, and
  limits 2 (unknown checksum) and 3 (`u16` permutation) are shown not to bite for a single-tile
  raster edit.
- **T2 loads, T3 does not** — the container and our compressor are fine; something about edited
  *content* is rejected. That points at a validity check inside a section, or at the `u16`
  permutation / derived state needing to agree with the raster (`U-029`). This would be the most
  informative failure available.
- **T2 does not load, T3 does not** — our QFS compressor produces streams the game rejects even
  though the shipped decompressor's transcription round-trips them. That would be surprising, since
  `quick=1` reproduces all 59 shipped streams byte-identically, and it would mean `quick=0` exercises
  a corner the game dislikes. Retry T2 built with `quick=1` plus a trivial content change to separate
  "our compressor" from "any non-shipped byte sequence".
- **T1 does not load** — the file is byte-identical to T0, so nothing about the writer is implicated.
  Look at the harness, the copy, file permissions or the load path.

## What this cannot tell you

Loading is not the same as correct simulation. Even if T3 loads and shows Landfill at (28, 0), that
does not prove the sim treats the tile consistently, that saving from the game afterwards produces
a sane file, or that larger edits behave. It settles one binary question: **will the game accept a
file this project wrote.**
