# sc3ui3 results (round 2026-11-19b): game bitmaps for the small UI pieces, the game's font at run time

## Verdict

Done for the owner's six points, measured against a native 800x600 grab of Preferencias (stock game, my tree):

| owner point | what changed | proof (share of pixels identical to the game, replica_diff.py) |
|---|---|---|
| play / stop buttons | the game's own bitmaps, every state | play 10.2% -> **100%**, stop 10.0% -> **100%** |
| X button | the game's bitmap, every state | 1.9% -> **89.4%** (the other 51 px are drop shadow, within 4/255) |
| slider texture | the game's bitmap: track and knob | 60.2% -> **100%** (all three sliders) |
| dropdown arrow | the game's 16x16 button, outside the box like the game | 0.4% -> **100%** |
| dropdown text | the arrow no longer cuts it, navy as in the game. With the game folder: SYSTEM9 itself | game font: same ink as the game (1.000) |
| the game's font | importer only: built at run time from the player's own game folder, never published | 1-bit fonts: **0 pixels differ**. Anti-aliased: coverage within 0.012 |

Also the volume steps over the sliders are one game bitmap: 46.0% -> **100%**.

Second owner list (2026-11-19), same treatment:

| piece | main | sc3ui3 |
|---|---|---|
| check boxes (ticked / unticked / in the music list) | 49.7% / 65.7% / 8.9% | **100%** each |
| radio buttons (on / off) | 33.3% / 43.1% | **100%** each |
| scroll bar: up / thumb / down arrows | 10.2% / 4.7% / 2.0% | **100%** each |
| scroll bar track | 93.8% | **98.9%** (Chrome draws the thumb at least 17 px long, the game 16: one track row) |
| OK button | 26.4% | **100%** |

Every check box, radio button and scrolling box on every page now uses these (sc3ui.css styles the elements
themselves), and the importer carries them inline.

Importer tests: `run_all.sh` **14 of 14** on main **cf2b01b** (sc4diag merged) + this branch: the 13 existing steps,
SC4 included, plus the new `sc3font_check.py` (12 of 12). Log `webtest/run_all_final.log`. Then `sync_css.py --publish`
(docs/buildings/importer/, now with sc3font.js) and the guide rebuilt from the shared template (byte-identical to main's:
the guide links the stylesheet and holds no text of this round). classifier.html's SC4 note now says "One colour of each
straight design is on".

## 1. The bitmaps

Every UI record in `Apps\Res\UI\Shared\*.IXF` (710 images, QFS-packed RGB565) decoded and matched against the grab.

| piece | record | frames | published |
|---|---|---|---|
| close X | SYS.IXF `82b9b75b:453ba1f4`, 92x23 | 4 x 23x23 | `docs/assets/sc3ui/close.png` |
| play | SYS.IXF `82b9b75b:82fab6d2`, 96x25 | 4 x 24x25 | `play.png` |
| stop | SYS.IXF `82b9b75b:22fab6de`, 96x25 | 4 x 24x25 | `stop.png` |
| dropdown arrow | SYS.IXF `82b9b75b:62b99d31`, 64x16 | 4 x 16x16 | `combo_arrow.png`, `_disabled`, `_pressed`, `_hover` (one file per frame: a dropdown is wider than the arrow, so a strip would show the next frame beside it) |
| slider | SYS.IXF `82b9b75b:c2b99e09`, 80x20 | track = columns 0..59, knob = 60..79 | `slider_track.png`, `slider_knob.png` |
| volume steps | `22DEC92D_OtherCtrls.ixf` `22dec92d:1`, 68x10 | 1 | `volume.png` |
| check box | SYS.IXF `82b9b75b:c2d6e93a`, 104x13 | 8 x 13x13 | `checkbox.png` |
| radio button | SYS.IXF `82b9b75b:0000000a`, 96x12 | 8 x 12x12, magenta key | `radio.png` (the key is transparent) |
| OK button | SYS.IXF `82b9b75b:a2defd9a`, 168x32 | 4 x 42x32 | `ok.png` |
| scroll bar | SYS.IXF `82b9b75b:e2b99e01`, 192x16 | 12 x 16x16 | one file per frame: `scroll_up`, `_up_pressed`, `scroll_thumb`, `scroll_track`, `scroll_down`, `_down_pressed` and the horizontal set from the same record (`scroll_left`, `_right`, `_hthumb`, `_htrack`, pressed arrows) so horizontal scroll bars match |

Original pixels, lossless PNG (565 expanded the way the game's screen shows it). The bitmaps have no key colour: their
background is the blue the game draws them on. Tool: `re/tools/sc3ui/uiart.py --game <install> --out docs/assets/sc3ui`.

**States, observed in the game with posted input** (no real mouse): frame 0 disabled (unticking Musica greys play and
stop), 1 normal, 2 pressed, 3 hover. Every frame matched the grab with 0 differing pixels. The close X shows rows 2..22
of its frame. The dropdown arrow has no hover change in the game and shows frame 2 while pressed. sc3ui.css maps them
to `:disabled`, normal, `:active`, `:hover`.

Check boxes and radios, observed the same way (0 px differ each): 0 on, 1 off, 2 / 3 the same under the mouse, 4 / 5
pressed, 6 on + disabled (the music list's ticks once Musica is unticked), 7 off + disabled (by the pairing). The radio's
disabled frames are by the same layout only: Preferencias has no disabled radio. Scroll arrows: pressed frame while
held, no hover change, and a held arrow scrolls the list. OK: 1 normal, 2 pressed, 3 hover.

The second game session (PID 9600, started and stopped by this session) opened Preferencias with the resolution
dropdown empty and the song "Building" highlighted, unlike the first. That was so before any input. Holding the
scroll-down arrow scrolled the list, and one held press of the up arrow brought the dialog back to its opening pixels
(0 differ). No setting was changed.

Side effect found: pressing the dropdown arrow with posted input opens its list, and posted clicks do not reach the
open list. A posted Escape closes it. The dialog was back to the first grab (0 pixels differ) after each test, and
Musica was ticked again. The game (PID 14844, started and stopped by this session) ran windowed.

## 2. Dropdown text

The game draws it with SYSTEM9 in navy `#31347b`, 3 px inside the box, with the arrow button outside the box. The old
replica put the arrow inside the box and lost "RTX". Free face for that role, scored on the dropdown's own strings
(2,112 configurations): Istok Web stays the best free family (13.0 px 0.693, the current 11.5 px 0.673). The gain
comes from the digits and costs 1 px of spacing per letter, so the pages keep 11.5 px.

## 3. The game's font in the importer

`re/tools/bldimport/sc3font.js`: when the player chooses the game folder (either route, and the remembered folder if
the browser still has read permission), it reads `Apps\Res\Text\<language>\*.FBF`, builds six TrueType fonts in memory
(MAIN9, MAIN10, SYSTEM9, TITLE9, TITLE12, SERIF17) and points the page's type tokens at them. No game folder: the free
fonts stay. Nothing is saved or published.

Two findings made it exact:
- Chrome on Windows draws web fonts with DirectWrite, which spreads each pixel into its neighbours (ink 0.88, 0.10
  beside it). Each glyph is also a COLR v1 glyph in the text colour, which Chrome draws with its own FreeType path:
  exact coverage, and CSS `color` still works.
- On that path a small square does not draw its area as coverage (a curve with gaps). A full-height bar does, linearly.
  The page measures this once in a canvas at run time (`calibrate()`).

`webtest/sc3font_check.py`: 12 of 12 (fonts load, tokens switch, fallback without a folder, 8 strings compared with the
game's own rendering, navy colour exact). The importer hook is one helper in `classifier.html` (`gameFonts`).

## 4. Proof pictures (`owner_shots/`, local: they hold game pixels)

- `elements_1.jpg` .. `elements_7.jpg`: per element (both owner lists), game | before (main) | after with free fonts |
  after with the game fonts, zoomed, with the numbers.
- `replica_stacked_2x.jpg`: the whole dialog, game above the replica with the game fonts above the replica with free fonts.
- `before_*` / `after_*`: gallery, guide, importer, gallery dark, importer dark, `_desk.jpg` (1280 px window) and
  `_phone.jpg` (true 390 px).

Pages: in the importer the dropdowns, check boxes and scroll bars changed (pixel changes only there). The guide:
0 pixels differ (no control of the new set on it). The gallery and guide's thin tab strip sets `scrollbar-width: thin`,
which keeps the browser's own bar there.
The gallery page is byte-identical and uses none of the changed parts. Its shot differs only inside an animated GIF,
caught on another frame (two shots of the same page are identical, the extra stylesheet images move the headless clock).

## 5. Files

See `re/sessions/STATUS_sc3ui3.md`, "files owned".
