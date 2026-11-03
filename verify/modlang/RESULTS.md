# modlang results (2026-11-02)

Verdict: built and checked in game. Every mod's UI text now comes from one table per language, picked by the
language of the game's own text. The game ships 7 text languages and all 7 tables exist: es, en (generated from
the source, unchanged text), fr, de, it, nl, sv (machine translations, header "MACHINE TRANSLATION, NEEDS NATIVE
REVIEW"). Spanish is unchanged: 0 differing pixels against the pre-change build, with the tables on and with them off.

## How it works
- **Detection: in the loader `sc3mods.dll`** (`re/harness/src/sc3mods_lang.c`, exports `sc3mods_lang`, `sc3mods_tr`).
  Every mod needs the loader (a mod stays inert without it), so this works with or without sc3resize. Same probe as
  the old `ho_spanish`: SIMUI resource key FUN_1008ebbd(0x14e, group 0x029541f4) loads the Preferences title, and
  the title names the language. Titles read from every shipped `Res\Text` folder: ENGLISH "Preferencias" (Spanish
  text), English-UK "Preferences", FRENCH "Préférences", GERMAN "Einstellungen", ITALIAN "Preferenze",
  DUTCH "Instellingen", SWEDISH "Egenskaper". Override kept: `sc3resize.ini [hud] lang=<code>` (any code now), or env
  `SC3MODS_LANG`.
- **Tables**: `<mods dir>\sc3lang\<code>.txt`, UTF-8 `key=value`, converted to code page 1252 at load. The game's own
  IXF text is 1252 and the FBF fonts are byte-identical in all 7 folders, so accented letters draw (pictures 2-5).
  Lookup: the language's table, then en.txt, then the mod's inline text.
- **Format check at load**: each table value's printf conversions must match the mod's own English (same
  conversions, same order, `%%` ignored). A mismatch is logged once in `sc3mods.log` and English is used.
- **Source**: the 142 inline `es ? "..." : "..."` pairs became `SC3TR(es, "mod.key", "...", "...")`
  (`re/harness/src/sc3lang.h`). Caption tables became `{ SC3KEY("mod.key"), "es", "en" }` rows. The inline pairs stay
  in the source: `re/tools/sc3lang.py extract` builds es.txt and en.txt from them, and they are what shows with the
  switch off.
- **Off switch**: `SC3MODS_LANGTABLES=0` = every mod shows its old inline text, decided by its old test.

## Inventory (235 keys)
| module | keys | language test before | note |
|---|---|---|---|
| sc3resize (mods page, Preferences rows, query buttons, picker toasts, LANGSEL caption) | 43 | ho_spanish | |
| sc3resize_restore (Vida util list, query rows) | 32 | ho_spanish | |
| sc3resize_vdbars (Cuadros tabs and bars) | 58 | ho_spanish, cached | number separators now from the table (`cuadros.decimal_sep`, `thousands_sep`) |
| sc3resize_graphs (Graficas lines, groups, tabs) | 50 | ho_spanish | |
| sc3resize_rcibars (A/P tooltip) | 1 | ho_spanish (if/else) | |
| sc3restore | 9 | `es` from the caller | |
| sc3landfill | 13 | `es` from the caller | |
| sc3undo | 2 | own `[undo] lang=` ini key, default es | now follows the game (see behaviour changes) |
| sc3dataview (map captions, old Cuadros column) | 23 | **Spanish only** | English added |
| sc3autosave (corner indicator) | 3 | **Spanish only** | English added |
| sc3bigcity ("Enorme" size option) | 1 | **Spanish only**, ini `caption=` | ini still overrides |

Not text of ours: netmod piece names and the highway ask dialog already come from per-folder IXF (netpack
`variants[].name`). Log lines stay English.

## Checks in game (Berlin, 2560x1351, HUD 2.25x, posted input only)
| run | result | picture |
|---|---|---|
| es, tables on, vs the pre-change DLLs | Cuadros (Educacion) + Graficas: 0 differing pixels. `LANG> game text language: "Preferencias" -> es` | `owner_shots/1_es_cuadros_graficas_igual_que_antes.png` |
| es, `SC3MODS_LANGTABLES=0` | 0 differing pixels against the pre-change DLLs | (same picture) |
| fr via LANGSEL (`[language] folder=FRENCH`) | game and mods in French: "Préférences" -> fr, Cuadros bars, tabs, Graficas, query rows, "Restaurer §620", "Copier l'ID", mods page. French numbers (4 600, 500,2K) | `2_fr_cuadros_graficas.png`, `3_fr_opciones_mods_antes_de_acortar.png`, `4_fr_consulta_central.png` |
| de via LANGSEL | "Einstellungen" -> de, query dialog + mods page in German, after the width fixes | `5_de_consulta_y_opciones_mods.png` |

## Text width
Widths measured from the game's own glyph advance table (fonts 0xf and 0x11, dumped in game with
`SC3RESIZE_FONTDUMP=1`), calibrated on the French pictures. Picture 3 showed two clipped captions, "Tous les :" (Every)
and "Sans limite" (FPS radio at the dialog edge), and "Coût de construction :" touching the value column. Those
and 8 more that the measure put over their room were shortened in fr/it/nl/sv/de. Remaining flags, none clipped:

| item | room px | es | en | fr | de | it | nl | sv |
|---|---|---|---|---|---|---|---|---|
| Graficas tabs, 5, min padding | 352 | 273 | 278 | 303 | 285 | 233 | 236 | 247 |
| Cuadros tabs, 7, min padding | 370 | 309 | 313 | 302 | 316 | 305 | 284 | 295 |
| "Undo buttons" checkbox | 140 | 144 | 97 | 141 | 132 | 111 | 129 | 103 |
| "Vida util" text button (only with `SC3RESIZE_RSICON=0`, the icon is the default) | 84 | 60 | 61 | 86 | 85 | 65 | 79 | 66 |

Spanish is already 4 px over on "Botones de deshacer" and reads fine at the dialog edge (picture 3 shows French at 141).
Full table for every measured caption: `py re/tools/sc3lang.py check --fonts <inst>\fontwidths.txt`.

## Behaviour changes (all needed for "one shared detection")
- sc3undo button tooltips follow the game language. Before, `undo.ini [undo] lang=` defaulted to Spanish, so an
  English game showed "Deshacer". The key is still read when the tables are off.
- sc3dataview captions, the autosave indicator and the "Enorme" option were Spanish in every language. They now
  follow the game. Spanish text is unchanged. `bigcity.ini [city] caption=` still wins when set.

## Not covered
- Native review of fr/de/it/nl/sv (all machine translated). Dutch and Swedish keep the R/C/I letters (no acronym found
  in their stock text). German uses W/G/I, as its stock text does.
- Only fr and de were seen in game. it/nl/sv are checked by the measure only.
- The Vida util list rows and the picker toasts were not opened in another language.

## Round 2 (merged build, main d087f9e + modlang2)
- 277 keys in all 7 tables after the merge of vdcolors, hudpos, placehints, transitmap and restorefix: 68 inline pairs
  converted by the orchestrator with `sc3lang.py convert`, the placehints and transit if/else blocks by hand, 42 new
  keys machine translated into fr/de/it/nl/sv.
- Spanish unchanged: Cuadros Educacion, Vida util list, transit map, 0 differing pixels between tables on and
  `SC3MODS_LANGTABLES=0`.
- French: the same three in French (picture 6).
- Widths: the transit caption lines, legend labels and the placement tooltip were shortened in the languages that
  measured longer than their room (tooltip: font 0x11, compared with the Spanish line that fits 768 px in game).
