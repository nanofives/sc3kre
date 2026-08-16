# SPRITE_SII.md — the `.SII` text mirrors, and what they confirm

Cracked 2026-08-15. `Apps\Res\Sprites\*.SII` are **plain-text sidecars shipped beside the sprite
`.DAT` archives** — 10 files, 8,132 records. They are a *second, human-authored witness* for the
binary sprite format, and they close two things the decompilation could not.

## The format, documented by the files themselves

Every `.SII` carries its own schema in a header comment:

```
;  SimCity3000 Image Info
;  This file should be formatted as follows:
;     Version:      [Version]
;     Record Count: [Record Count]
;     [ImageGroup], [ImageInst], [Span L (reg pt x)], [Span T (reg pt y)], [Span R], [Span B]
;  Comments can only be used at the top of the file. Do not leave blank lines anywhere
```

Body lines are CSV with an optional trailing `;` comment:

```
10004856, 48561000,  18,  23,  18,   0 ; Alpha
```

`ImageGroup`/`ImageInst` are **hex**; the four span values are **decimal**. Not every file has a
`Version:`/`Record Count:` preamble — the ones with a long comment banner omit `Version:`.

## Result 1 — the type-1 "anchor" record is decoded `[CONFIRMED, C4]`

The `.IXF` type-1 records (62,387 of them) had never been decoded. Joining `.SII` to `.IXF` on
`(group, instance)` gives **8,132 joined records**, and every type-1 payload is **8 bytes**:

```
type-1 record = 4 x SIGNED i16 { spanL, spanT, spanR, spanB }
                spanL/spanT = the REGISTRATION POINT (reg pt x, reg pt y)
```

**8,132 of 8,132 match, zero mismatches.** The fields must be read **signed**: 138 records have a
negative `spanT`, 30 a negative `spanB`, 10 a negative `spanL`, 8 a negative `spanR` — which is
exactly what a registration point relative to a tile anchor does. Reading them unsigned works for
7,964 records and silently corrupts the other 168.

Decoder: `parse_anchor()` in `re/tools/sprite_render.py`.

## Result 2 — the plain-bitmap class really is ALPHA `[CONFIRMED, C4]`

`QFS.md` recorded the format-0 / `dword1 == 0x10080000` class as an 8bpp 5-bit single channel and
marked its *meaning* `[UNCERTAIN]` — coverage/alpha was inferred only from rendering it.

The `.SII` comments settle it. Cross-tabulating the trailing comment against the record's format
code over all joined records:

| comment contains `Alpha` | format code | records |
|---|---|---|
| yes | **0** | 90 |
| no | **1** | 8,042 |

**Zero exceptions.** Maxis' own art-pipeline text labels exactly the format-0 records `Alpha`.
That is an independent second witness, so the plain-bitmap class is confirmed as an alpha mask
rather than a palette-indexed image.

## Result 3 — a third check on width/height

7,952 records carry a `W x H` dimension comment (e.g. `24 x 16`). Every one of them matches the
record's `dword2`/`dword3`: **7,952 match, 0 mismatch.** This independently re-confirms the
width/height fields of the record header.

## Coverage caveat

The 10 `.SII` files cover **8,132 of 63,691** records (12.8%) — they exist for only some archives
(`10004856_LO18518`, `54AACF44_Holiday`, `54DA2E59_HolidayF`, `5544F8BD_Roads_2`,
`654FCB99_CityObjects_2`, `disaster_LOCUST`, `Disaster_SPACEJUNK`, `disaster_TOXICCLOUD`,
`EffectSprites`, `GAME_UI`). The conclusions above are therefore proven on that subset and
consistent with, but not independently witnessed across, the other 87%. The binary-side
validations in `QFS.md` (63,691/63,691 and 62,552/62,552) do cover everything.

`[UNCERTAIN]` the `Alpha` correlation is proven only where `.SII` exists — 90 of the 1,139
format-0 records. Nothing contradicts it on the other 1,049, and all 1,139 share the identical
0..31 value range, but no shipped text labels them.

## Reproduce

`re/tools/sprite_render.py` decodes anchors; the join itself is a short script over
`ixf_parse.parse()` plus the CSV above.
