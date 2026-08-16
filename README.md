# sc3kre — SimCity 3000 Unlimited reverse-engineering

Static reverse-engineering of **SimCity 3000 Unlimited** (Maxis / Electronic Arts, 2000),
a 32-bit x86 Windows game. The goal for this phase is **understand and annotate first**:
produce a full annotated map of the engine plus documented, round-tripping file-format and
modding knowledge. The decision about whether to build a source port or a modding toolkit is
deferred until the surface is mapped.

This repository contains **only original work**: our own tools and our own analysis notes.
It contains **no game assets, no binaries, and no decompiled EA/Maxis code**. See
[What is NOT in this repo](#what-is-not-in-this-repo-and-why). You need your own legally
obtained copy of the game to use any of it.

## Headline findings

- **The simulation is not in `SC3U.exe`.** That executable is a GZCOM shell. The actual game
  logic lives in **29 GZCOM director DLLs** shipped in the game's `Apps\` folder (6.2 MB of
  code). Every module follows one registration recipe (a director registers N classes by
  GZCLSID, each behind a `operator new` + constructor factory). See
  [`re/analysis/MODULE_MAP.md`](re/analysis/MODULE_MAP.md) and
  [`MODULE_INVENTORY.md`](re/analysis/MODULE_INVENTORY.md).

- **QFS / RefPack decompressor fully recovered** ([`re/tools/qfs.py`](re/tools/qfs.py)),
  transcribed from the shipped decompressor. **63,691 of 63,691** sprite streams decompress
  to their declared uncompressed size (a C4 round-trip result).

- **Sprite format fully decoded** ([`re/tools/sprite_render.py`](re/tools/sprite_render.py)):
  per-row span encoding with RGB565 / RGB555, plus an 8bpp 5-bit coverage-mask class, plus
  4-by-int16 anchor records. **62,552 of 62,552** records pass 7 independent structural
  predictions.

- **An independent second witness.** The `.SII` text mirrors that ship beside the sprite
  archives corroborate the decoded records: **8,132 joins, 0 mismatches**.

- **`.IXF` container cracked.** Magic `0x80C381D7`, a 20-byte index record
  `{group, instance, type, offset, size}`. One reader and two writers in the binaries all
  agree on the layout. Parser: [`re/tools/ixf_parse.py`](re/tools/ixf_parse.py).

- **Sim models read out of the decompilation.** Power is a masked bitmap dilation flood-fill
  (32 tiles per dword, capacity constant `600` at a cited address). Traffic is a trip and
  cell-cost commute model. Budget, ordinances, aura, and neighbor deals are mapped to their
  record structures. See the per-subsystem docs under `re/analysis/`.

## Tracker status

The single source of truth for per-function status is [`functions.csv`](functions.csv), one
row per address. Current standing:

| Confidence | Count |
|---|---|
| C0 unreviewed | 4,843 |
| C1 triaged | 108 |
| C2 decompilation read + named | 543 |
| C3 behavior confirmed | 10 |
| C4 fully verified | 5 |
| **Named** | **635** |

## Confidence ladder

Every claim in this project is tagged with a confidence level. Nothing above C0 is asserted
without cited evidence from the decompilation.

- **C0** unreviewed. Auto-analysis output only, an unnamed function.
- **C1** triaged. Subsystem-classified with a one-line purpose from strings or cross-references.
- **C2** decompilation read. Mechanically described, callees identified, named.
- **C3** behavior confirmed. Cross-checked against a second witness (runtime observation, a
  second binary, or a data-file validation).
- **C4** fully verified. A parser round-trips, or the behavior is reproduced. This is the bar
  for "done" in an annotate-first project.

## Method: NO-GUESSING

The notes report only what the decompilation literally shows. No "probably", "likely",
"seems", or "appears". Every constant, offset, and formula cites its exact address. Unknown
meaning is reported as raw hex or decimal. Unknown purpose is described mechanically (reads X,
calls Y, writes Z). Uncertain items are marked and logged in
[`UNCERTAINTIES.md`](UNCERTAINTIES.md).

A named sibling binary, the iOS build of the same engine, is used as a **hint oracle** only.
Its algorithms and magic constants transfer. Its struct layouts do not (proven: 0 of 5 probed
field offsets matched the PC build). iOS-derived guesses are labeled and never presented as PC
facts. See [`re/analysis/CROSS_RE_iOS.md`](re/analysis/CROSS_RE_iOS.md).

## Layout

```
re/tools/      # format parsers and decoders (Python)
re/scripts/    # RE tooling: Ghidra headless drivers, export queries, Java analysis scripts
re/analysis/   # per-subsystem RE notes (cite addresses), incl. formats/ specs
functions.csv  # the per-address status tracker (single source of truth)
HANDOFF.md     # project state snapshot
ROADMAP.md     # phase gates and Definitions of Done
UNCERTAINTIES.md STUBS.md DEFERRED.md   # open holes and deferrals
```

## Running the tools

The tools are self-contained and read files you supply from your own game install. They do not
bundle any game data.

```bash
# Decompress a QFS / RefPack stream
python re/tools/qfs.py <path-to-compressed-stream>

# Parse an .IXF / .DAT container index and extract records
python re/tools/ixf_parse.py <path-to.dat>

# Decode sprite records to images (feeds on decompressed pixel data)
python re/tools/sprite_render.py <args>

# Read .rdata constants straight out of a PE, no Ghidra needed
python re/tools/pe_read.py <path-to.exe-or.dll>

# Parse SYS.PAK (51 ini files)
python re/tools/syspak_parse.py <path-to SYS.PAK>
```

The `re/scripts/` drivers wrap [Ghidra](https://ghidra-sre.org/) headless analysis and require
a local Ghidra install and JDK 21. They import a binary you provide and export a greppable text
decompilation for your own private analysis. The `.java` files are Ghidra scripts.

`delegate_module.ps1` wraps an external read-only delegation helper that is not part of this
repo. Point `REPO_FLEET_DELEGATE` at your own runner if you want to use it, otherwise ignore it.

## What is NOT in this repo (and why)

This working tree was a live retail game install with RE work layered on top. Publishing it
naively would have leaked copyrighted material. The following are deliberately excluded and can
never be added (the repository uses a deny-by-default `.gitignore` allowlist to enforce this):

- **The retail game.** No `SC3U.exe`, no game DLLs, no `Apps\` `Cities\` `Buildings\` `Scripts\`
  content, no installer binaries.
- **A decrypted iOS build** of the engine, used only as a naming reference during analysis.
- **The full Ghidra decompilation** of EA/Maxis code (tens of thousands of function bodies).
- **Extracted game data:** 63,691 rendered sprite PNGs, the sprite record tables, and 71,924
  extracted in-game text strings.

All of the above is the property of Electronic Arts / Maxis. **To use these tools you must
supply your own legally obtained copy of SimCity 3000 Unlimited.** Nothing here redistributes
any part of the game.

## License

Our tools and notes are licensed **MIT** (see [`LICENSE`](LICENSE)). That license covers only
the original work in this repository. SimCity 3000 Unlimited is the property of Electronic Arts
/ Maxis, and no game code, game data, or decompiled output is included or redistributed here.
This is an independent reverse-engineering and interoperability project, not affiliated with or
endorsed by Electronic Arts or Maxis.
