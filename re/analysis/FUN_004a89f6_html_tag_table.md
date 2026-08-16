# FUN_004a89f6 — HTML parser keyword-table initializer  [C2]

`0x004a89f6` · 15,247 bytes (the single largest `FUN_*` in SC3U.exe) · proposed name
**`sc3_html_init_tag_table`** · subsystem **S15 (UI/HTML infra)**.

## Mechanical description (from the decompilation) `[CONFIRMED @ 0x004a89f6]`
The whole function is one uniform idiom repeated ~155 times (a per-entry state counter
`local_8` climbs 0…0x137). Each repetition:
1. `FUN_00401e6f`/`FUN_00402a40(tmp, s_<LITERAL>)` — construct a std::string from an HTML
   keyword literal (vtable `PTR_LAB_004cf4c4`).
2. `FUN_00472aec`/`FUN_0047296a(...)` — build a keyword-table entry from that string.
3. `FUN_00472a16`/`FUN_004b0dd7(&DAT_004fb170, slot, entry)` — insert the entry into the
   global container at **`DAT_004fb170`**.
4. `FUN_00402a96`/`FUN_00471ef9(tmp)` — destroy the temporary string (SEH-guarded via the
   `local_8` unwind index + `ExceptionList`).

The literals registered are the complete **HTML vocabulary**: document tags
(`!DOCTYPE HTML HEAD BODY TITLE /TITLE /BODY /HEAD /HTML`), form input types
(`IMAGE HIDDEN RESET SUBMIT RADIO CHECKBOX PASSWORD`), alignment enums
(`RIGHT MIDDLE BOTTOM`), shape enums (`CIRCLE SQUARE`), `NOBR`, and a `ParseA` entry
(string addresses `0x004f9904`–`0x004f99ec`+).

## Interpretation
`DAT_004fb170` is the recognized-keyword dictionary of an **embedded HTML parser/renderer**.
This function populates it once at startup. Consistent with SC3's HTML-driven UI surfaces:
`TickerAdvertisements.html` / `MajorAdvertisements.html` (S14 news ticker), the `news://`
CityExchange content, and the About/Legal window (`AboutLegalWindow`, iOS taxonomy).

## Callees identified
- `FUN_00401e6f` / `FUN_00402a40` = std::string ctor(from C-literal); `FUN_00402a96` /
  `FUN_00471ef9` = std::string dtor.
- `FUN_00472aec` / `FUN_0047296a` = construct a keyword entry.
- `FUN_00472a16` / `FUN_004b0dd7` = insert entry into `DAT_004fb170`.

## Callers
- `FUN_004a7feb` (sole caller) — the HTML subsystem init (seeded S15/C1).

## Open items
- `[UNCERTAIN]` exact rendering consumer (which window class draws the parsed HTML) — needs
  an xref chain from `DAT_004fb170` readers. Logged in UNCERTAINTIES.md.
- Promote to C3 by matching against the iOS HTML/RichText class if one exists
  (grep `ghidra_export_ios` for a tag-table with the same keyword set).
