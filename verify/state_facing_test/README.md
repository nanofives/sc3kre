# verify/state_facing_test — U-078, the `state` byte's rotation sense and compass zero

Settles the half of `U-078` that `NETWORK_RULE_ENGINE.md` §11.4 left open: `state N` = `N × 90°`
was already C3, but **which** 90° step, in **which** sense, was not.

## What is here

| file | what it is |
|---|---|
| `re/tools/state_facing.py` | the whole investigation, re-runnable, read-only. **Lives in `re/tools/`, not here** — `verify/` publishes protocols and outcomes only. |
| `RESULTS.md` | the captured output, 2026-08-24, verdict up front. |

```
python re/tools/state_facing.py
```

Reads only: `original\modules\SIMNTWRK.DLL`, `Apps\Res\TilingRules\*.txt`,
`Apps\Res\SSimData\English-UK\TrBlkAtt.IXF`. Writes nothing outside this folder.

## The two hypotheses it scores

World directions are the SIMNTWRK 5×5 offset table at `0x10032134`
(`NETWORK_RULE_ENGINE.md` §4.1): `dir 0 = (-1, 0)`, `dir 1 = (0, -1)`, `dir 2 = (+1, 0)`,
`dir 3 = (0, +1)`, labelled W/N/E/S there.

- **H+** — a piece's canonical direction `c` presents at world dir `(c + state) mod 4`.
- **H-** — ................................................ `(c - state) mod 4`.

`state 0` and `state 2` cannot tell the two apart (a half turn is its own inverse), so the script
counts **discriminating** evidence separately from total evidence. That distinction is the point;
a raw "80/80 agree" would be misleading on its own.

## Section by section

**WITNESS 1 — code.** `SIMNTWRK FUN_1000d73d` @ `0x1000d73d` is vtable slot `+0xb0` of the class
at vtable `0x1002bd04`, and every one of the 22 network-piece kinds reaches it through primary
slot `+0x4c` (`FUN_1000cd35` @ `0x1000cd35`), which forwards `state = *(u32*)(this+0x14) >> 0x1e`.
It indexes `DAT_1003123c` at `(dir + state*4)*4` — a 16-row × 4-byte table of bit indices into a
16-bit connection field. The script dumps all 16 rows and scores them. **16/16 fit H+, 8/16 fit
H-** (the 8 being exactly the `state 0` / `state 2` rows, which fit both).

**WITNESS 2 — data.** The `*_final.txt` stage runs at mode 4, so its selector is an exact 4-bit
orthogonal-occupancy mask and all its results sit at `dir 255`. Each rule is therefore literally
`(occupied orthogonal set) -> (pieceId, state)`. 95 rules over six networks, collapsing to **80
distinct `(file, id, state)` observations** across 40 families.

The 15 collapsed rules are all degree-4 pieces placed for many different masks — `HWAY 15149 s0`
alone is the result of 11 rules covering every mask of degree 1, 2 and 4, because a highway never
tapers. Those rules carry **no** facing information and are not counted twice.

**H+ explains 80 of 80 and contradicts 0. H- explains 70 and contradicts 10.** 5 families are
sign-discriminating (`ROAD 39 / 11203 / 11225`, `RAIL 54 / 16036`), covering 20 of the 80
observations, and **all 20 pick H+**. `HWAY` contributes 4 non-discriminating observations only.

**WIDENED SAMPLE.** Stage 1 (`*SIMPLERULES*`, mode 8) has 1,660 centre results. There the selector
means "a neighbour is present", not "the piece connects there", so the honest invariant is a
subset relation, not equality. **506 results have a known shape: 26 are satisfied by H+ only,
0 by H- only, 0 by neither.**

**CROSS-CHECK.** The 249 `*_Convert.txt` id-pairs with ≥2 states are **249/249 state-equivariant**.
Sign-blind, but it proves `state` is the same rotation index on both sides of a substitution.

**NOT EVIDENCE-GRADE PROBE.** `FUN_1000d1cf` @ `0x1000d1cf` builds the key
`{0x625c6226, 0x825c6289, id*0x100 + state}`, and that key resolves to
`Apps\Res\SSimData\<lang>\TrBlkAtt.IXF` — variable-length `BIN\r` **property blobs**, 161–463
bytes, **not bitmaps**. Probing them for a byte that steps by a constant multiple of 8 mod 32
(8/32 of a turn = 90°) finds 25 hits at `+8` and 2 at `-8`. **This proves nothing**: the blob
format is not parsed, so a fixed byte offset is not known to name the same field in records of
different length, and the two `-8` hits are at offset `0x64` in 281/322-byte records while the
`+8` hits at `0x64` are in 179-byte records. Reported so nobody re-derives it and mistakes it
for a witness.

## No PNGs, and why

Route A (render the four `pieceId*0x100 + 0..3` instances and look at them) was attempted and
**does not exist as described**. The `{0x625c6226, 0x825c6289}` space is not in
`Apps\Res\Sprites\*.DAT` at all — 573 containers under `Apps\Res` were enumerated and the 6,034
records carrying those two ids all live in the `SSimData\*\TrBlkAtt.IXF` family. The key is an
**exemplar/attribute key, not a graphic key**; the exemplar is what in turn names the art. So
there was nothing to render, and §11.4's phrase "builds the graphic key" is a wording that should
be corrected.

That is not a loss. Route A was only ever corroboration, because an isometric render cannot
anchor a world compass without first stating the screen→world mapping, and that mapping was never
established here.

## How to falsify the conclusion

The conclusion is `state s` presents canonical direction `c` at world dir `(c + s) mod 4`.

1. **Cheapest, no run needed.** Change one `*_final.txt` rule's state by +1 and place the matching
   neighbourhood in game. Under H+ the piece must appear rotated one step in the
   `(-1,0) -> (0,-1) -> (+1,0) -> (0,+1)` order. Under H- it goes the other way. The two
   predictions differ visibly for any state-1 or state-3 case.
2. **Purely static.** Decode the `BIN\r` property blob and read the 16-bit connection field that
   `FUN_1000d73d` probes. It must equal the `*_final.txt`-derived state-0 connection set for the
   same piece id, per the `4*edge + lane` layout. A mismatch on any single piece kills it.
3. Find any shipped rule whose result contradicts the equivariance fit. The script already looks;
   there are none in 95 final-stage rules, 1,660 stage-1 results, or 249 convert pairs.
