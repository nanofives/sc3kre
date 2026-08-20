# sprite_mod_test — RESULTS

Run date: `2026-08-19`  Run by: `harness session (headless §31 route)`

**Outcome: the first pre-registered one. The sprite write path is validated game-side.**
`README.md` was written before the run and has not been edited since.

---

## 1. Pre-flight, offline — every bar in `README.md` §"Pre-flight" met

| check | bar | got |
|---|---|---|
| identity repack, whole sprite corpus | 40/40 byte-identical | **40/40** (`sprite_patch.py Apps/Res/Sprites --selftest`), 15 non-container files skipped |
| patched container re-parses | same slot count, same keys/types | **13,353 → 13,353 slots**, 12,352 live → **13,352 live**, `[group,instance,type]` sequence **identical** |
| every patched record decodes | `qfs`, no size mismatch | **0 decode failures** across all 6,676 pixel records |
| dimensions preserved | `w`,`h`,`key` unchanged | **6,676 / 6,676** |
| `d4` correct | `d4 == len(stream) + 4` | **6,676 / 6,676** |
| shipped file untouched by the build | pre-run SHA-256 holds | `29b2d4dd…`, 15,172,185 bytes |

Container size **15,172,185 → 2,525,526 bytes** (flat colour compresses far better than asphalt).
Every payload after the first therefore sits at a new offset: this run exercised `repack()`'s index
recomputation on **6,676 shifted records**, against `SYS.PAK` M2's single 4-byte shift.

Patch run: **6,676 patched, 6,676 skipped.** The skips are exactly the 6,676 `type == 1` anchor
records (8 bytes each, no pixels) — the walker declines them rather than failing on them.

**One check was recorded as a fail and then withdrawn, and the reason is worth keeping.** "All
visible pixels red" first came back **6,626 / 6,676**. The 50 shortfalls were then checked against
the shipped file: all 50 are **4x4 records with zero visible pixels in the shipped archive**, so
there was nothing to paint and `set(surface) == {key}`. The assertion was too strict, not the
patcher. Corrected count: **6,626 recoloured + 50 legitimately empty = 6,676.**

---

## 2. Raw observations — written before §3

### 2a. Did the game read our file?

**The `-filetrace` gate is NOT AVAILABLE for sprites, and this is a finding about the instrument.**
The run logged **54 `FILETRACE` lines**, covering `.ini` (36), `.PAK` (12), `.sc3` (3) and `.html`
(2). It recorded **zero** paths under `Apps\Res\Sprites\` — a grep for `Sprites` in the log returns
**0 hits**. So `-filetrace` does not observe the sprite archives at all, and the §2a-style
machine-checkable proof used by `tunable_mod_test` could not be applied here.

What stands in its place is stronger for this particular edit, and it is stated rather than
assumed: **`0xF800` flat-red road pixels exist in no shipped file.** They exist only in the archive
this project wrote. Their appearance on screen is itself the evidence that the file was read, in a
way a colour matching the shipped art would not have been.

### 2b. The city

Berlin, Pob 794,278, §117,006, 2/9/2067 — the same save, same scripted camera position as
`verify/tunable_mod_test`, so the frame is directly comparable to the baseline shots from that run.

### 2c. What the screen showed

**The entire road network renders solid red.** Straight runs, curves, intersections and the road
edges are all one flat red. **The road geometry is unchanged** — every road occupies exactly the
tiles it occupied in the baseline shot, which is what the preserved transparency mask predicted.

### 2d. The negative control — HELD, on every element

Nothing outside the road layer changed. Checked against the baseline shot from `tunable_mod_test`:

| element | container | result |
|---|---|---|
| buildings (industrial, commercial, residential) | `00000002/3/4_*.DAT` | **unchanged** |
| terrain, grass, trees | `00000009_Landscape.DAT`, flora | **unchanged**, still green |
| **the elevated rail line** running diagonally across the frame | rail sprites, not `Roads.DAT` | **unchanged**, still grey — a sharp control, since it is a transport line adjacent to the roads and it did not move |
| vehicles | `00000006_Vehicles.DAT` | **unchanged** — the white trucks are still white, driving on red roads |
| smoke plumes | `00000010_Smoke.DAT` | **unchanged**, still white |
| UI: toolbar, status bar, minimap panel | not in these archives | **unchanged** |
| **the minimap's own road rendering** | — | **unchanged** — worth noting: the minimap does not draw from these sprites |

- Crashes, hangs, corruption: **none.** The game booted, loaded Berlin, dismissed the tip and ran.
  No garbage pixels, no art in the wrong place, no misaligned sprites — which is the specific
  failure mode a wrong index would have produced.

---

## 3. Which pre-registered outcome fired

| | outcome | what it settles |
|---|---|---|
| ☑ | Roads render red; vehicles/buildings/terrain unchanged | **The sprite write path is validated game-side.** Art modding is an available capability. `repack()` validated on 6,676 shifted offsets. |
| ☐ | Roads render normally, `FILETRACE` shows the game opened our file | — |
| ☐ | Roads render normally, no read of our file → staging failed | — |
| ☐ | Roads render as garbage / wrong art in the wrong place → `repack()` index wrong | — |
| ☐ | Game crashes or fails to load → header (`d4`) or index defect | — |

Selected: **the first row**, with the §2a qualification recorded above — the visual result is
unambiguous, but it was *not* corroborated by a file-access trace, because the instrument does not
cover sprite archives.

---

## 4. Verdict

**The sprite write path works end to end, in the running game.**

`sprite_patch.py` decoded 6,676 shipped sprite records, repainted every visible pixel, re-encoded
them with `sprite_encode.encode()`, recompressed them with `qfs_encode.compress_stream(quick=1)`,
packed the 0x14 record headers, recomputed the whole `.IXF` index for a container that shrank by
12.6 MB, and the game loaded the result and drew it. The claim holds at exactly that strength: a
**recolour** of existing sprites, at unchanged dimensions, is proven. Authoring *new* art is not
proven and is not claimed — see §5.

This is the second independent format whose writer is now confirmed game-side (after `SYS.PAK` in
`tunable_mod_test` and the city-save family in `city_load_test`), and the first one where the
edit was to *art* rather than to a number or a byte.

---

## 5. Settled vs not settled

- **SETTLED:**
  - `sprite_encode.encode()` is a **true encoder**, not a round-trip verifier: it accepted 6,676
    surfaces it had not decoded and the game rendered every one of them.
  - `repack()`'s index recomputation, on **6,676 records whose payloads all changed length**.
  - The `d4 = len(stream) + 4` rule for the 0x14 sprite record header, on 6,676 records the game
    accepted. (`qfs.decode_record`'s `d4_matches_stream` diagnostic is False on all of them, as
    documented — it is not the rule.)
  - `qfs_encode.compress_stream(quick=1)` output is accepted by the game for **sprite** streams.
    Previously confirmed game-side only for a city-save payload (`city_load_test` rung T2).
  - Sprites are direct-colour 16bpp with a per-record colour key; there is no palette to update,
    confirmed by the fact that a raw `0xF800` write rendered as red with no other change.
  - The minimap does not render roads from these sprites.

- **NOT SETTLED:**
  - **Authoring new art.** There is still **no RGB→RGB565 quantizer and no PNG import** in
    `re/tools/`. "Replace this sprite with my PNG" needs that converter written (about five lines:
    `((r>>3)<<11)|((g>>2)<<5)|(b>>3)`, mapping alpha-0 to the colour key). This run changed colours
    of existing pixels; it did not import an image.
  - **Changing a sprite's dimensions.** Every record kept its `w`/`h`. Whether the game tolerates a
    different size, and what else would have to change with it (the type-1 anchor record, the
    `.SII` span/registration values), is untested.
  - **The 1,139 format-0 alpha-mask records.** This edit skips them; `[UNCERTAIN]` which colour
    they modulate (`QFS.md:157-159`) is untouched.
  - **Whether `-filetrace` can be made to see sprite loads.** It saw none. Until that is fixed, any
    sprite experiment lacks the file-access gate that `tunable_mod_test` had, so a *negative*
    sprite result would be much weaker than a negative tunable result — you could not distinguish
    "the edit did not take effect" from "the file was never opened".
  - Sprites inside the other 39 containers, including the ones the UI chrome draws from, which are
    **not** in `Apps\Res\Sprites\` and have not been located.

---

## 6. Restore — confirmed, not assumed

| check | expected | got |
|---|---|---|
| `00000005_Roads.DAT` SHA-256 | `29b2d4dd…` | **`29B2D4DDDB5B2AB578B6D6CD9C49FABE6E2A683A6A933DE6C7A548E97F35E3EC`** — match |
| `00000005_Roads.DAT` length | 15,172,185 | **15,172,185** |
| `Apps\Sys\SYS.PAK` (untouched by this test) | `172c02d9…` | **`172C02D9…`** — match |

**The staged and backup archives were deleted after restoring**, deliberately:
`Roads.DAT.original` (15 MB) and `Roads.DAT.red` (2.5 MB) are game assets, and game assets do not
belong in the repo. `shipped.sha256` records the anchor and one command rebuilds the modified
archive:

```
py -3.12 re/tools/sprite_patch.py Apps/Res/Sprites/00000005_Roads.DAT --recolor F800 --out <path>
```

---

## 6b. ADDENDUM — rung 2: PNG import, run the same day

**Status of this rung's honesty: weaker pre-registration than rung 1, and that is stated rather
than hidden.** Rung 1's predictions were committed to `README.md` before the run. This rung was
built and run after rung 1 passed, and its prediction was *not* written to a file first. What
protects it is the nature of the observable: yellow/black hazard stripes appear **nowhere in the
shipped game**, so there is no result this could be rationalised into.

### What was added to the tool

`sprite_patch.py` gained the PNG path — `quantize565()` / `quantize555()`, `image_to_surface()`,
`export_png()`, `replace_from_png()`, `png_roundtrip()`, and the CLI verbs `--export`,
`--import-png`, `--pngtest`. That closes the gap §5 recorded as "authoring new art is still not
possible".

**The quantizer is the exact inverse of the decoder, and that is measured, not asserted.** For
**all 65,536** RGB565 values and **all 32,768** RGB555 values, `quantize(rgb565(v)) == v`. It holds
because `sprite_render`'s expansion `c * 255 // 31` (or `// 63`) equals `c << 3` (or `<< 2`) plus a
remainder strictly smaller than the shift, so shifting back recovers `c`. That exactness is what
lets the PNG round-trip be held to **byte-identical** instead of "visually close".

**And it passes at corpus scale: `--pngtest` over `Apps\Res\Sprites\` is 62,552/62,552 records
byte-identical** (65,419 non-format-1 records skipped). That figure is the same 62,552 that
`sprite_encode.roundtrip()` meets, which is the expected coincidence — it is the count of format-1
records — and it means the PNG detour costs nothing: export to PNG, re-import, and you get the
shipped bytes back.

### The run

All 6,676 pixel records of `00000005_Roads.DAT` were re-authored, and the pixels made a **full trip
through real `.png` files on disk**: the shipped silhouette was exported with
`sprite_render.span_to_image()`, an authored yellow/black diagonal stripe pattern was drawn into it
with PIL, the result was **saved as a PNG**, and that file was read back through
`sprite_patch.replace_from_png()`. Nothing was passed in memory.

Pre-flight, all met before launching:

| check | got |
|---|---|
| slot keys/types identical | **True** |
| decode + `d4` failures | **0** |
| dims + colour key preserved | **6,676 / 6,676** |
| **silhouette (transparency mask) preserved** | **6,676 / 6,676** |
| distinct colours in the whole container | exactly `0xFEA0` (yellow), `0x10A2` (black), `0xF81F` (key) |
| opaque-magenta key collisions | **0** nudges needed |

Container **15,172,185 → 3,560,391 bytes**.

### Observed

**Every road in the city renders as yellow/black hazard stripes.** The stripe pattern is the
authored one, running on the isometric diagonal as drawn. Road geometry is unchanged, which the
preserved silhouettes predicted. The negative control held again on every element: buildings,
terrain, trees, vehicles, smoke plumes, the adjacent elevated rail line and the whole UI are
untouched. No crash, no corruption, no misplaced art.

### What rung 2 settles beyond rung 1

- **Authoring new art works.** Rung 1 recoloured existing pixels; this rung drew a pattern that is
  not in the game and imported it from a PNG file. The `[NOT SETTLED]` item "no RGB→RGB565
  quantizer and no PNG import" in §5 is **closed**.
- `export_png` → edit → `--import-png` is a usable workflow for a modder, not just an internal API.
- The colour-key collision hazard is handled and counted (0 here, because neither yellow nor black
  quantizes to magenta) rather than silently producing holes.

### What rung 2 does NOT settle

- **Dimensions still cannot change.** `image_to_surface()` refuses a size mismatch on purpose; the
  type-1 anchor record and the `.SII` span/registration values would have to move with it, and none
  of that is tested.
- **Alpha is still a threshold, not a channel** (default 128). Semi-transparent art cannot be
  represented by this format at all, so soft edges will harden.
- The 1,139 format-0 alpha-mask records are still skipped.
- Nothing here validates *which* sprite a given building uses. Locating a specific on-screen
  building by sprite record was attempted during this session and **failed** — a search of
  `0000000B_Utilities.DAT` and `00000004_Industrial.DAT` by on-screen size returned two chemical
  plants, not the building in frame, because the building was clipped at the frame edge and the
  size estimate was wrong. **There is no record → on-screen-object index**, and that is the next
  real gap for anyone wanting to retexture one specific thing rather than a whole layer.

### Restore

`00000005_Roads.DAT` back at `29b2d4dd…`, 15,172,185 bytes, 0 stray `.original` files under
`Apps\`. Verified by hash, not assumed.

---

## 7. Follow-ups this run created

- **`re/tools/sprite_patch.py` belongs in the T2 table** with `--selftest` **40/40** — it is the
  missing writer for the sprite containers, and it is now the only writer in that table validated
  game-side on *art*.
- **`-filetrace` does not cover `Apps\Res\Sprites\`** (§2a). Worth either extending the hook or
  documenting the blind spot in `LAUNCH_CONTROL.md` §29.2, because it silently removes a gate that
  other experiments rely on.
- **The UI chrome sprites are not in `Apps\Res\Sprites\`.** All 40 containers there are world art
  (vehicles, roads, buildings, people, flora, disasters, city objects) plus `GAME_UI.DAT`, which
  holds only the New City scheme-picker backgrounds and flora thumbnails, per `GAME_UI.SII`. Where
  the toolbar, dialog and status-bar art lives is **unknown** and is a real gap for UI modding.
- **Next cheap win, if art modding is to be usable:** the RGB565 quantizer + PNG import, which
  turns `sprite_patch.py` from a recolour instrument into a replace-this-sprite tool. It is the
  smallest remaining piece of the art path.
- Trackers to update: `ROADMAP.md` (T2 table + the sprite row's game-side status),
  `HANDOFF.md`, `.happy/project-info.json`.
