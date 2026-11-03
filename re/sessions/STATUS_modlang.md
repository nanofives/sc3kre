# STATUS modlang (child of "SC3 graphs tabs + Vida util/restore/query UI round", 2026-11-02)

## goal
Owner: "todos los mods estan disponibles en todos los idiomas?" -> move the mod texts into tables and add the game's
languages. One string table per language, every mod reads from it, one shared language detection.

## verdict + deciding RVA
DONE, built and checked in game. Detection in the loader sc3mods.dll reads the game's Preferences title through SIMUI
FUN_1008ebbd(0x14e, 0x029541f4) / FUN_1008ebea (the probe ho_spanish already used) and maps the 7 shipped titles to
es en fr de it nl sv. 235 keys, 7 tables. Details: `verify/modlang/RESULTS.md`.

## built
- `dev\modlang\tree\Apps\sc3mods.dll` (exports sc3mods_lang @3, sc3mods_tr @4) + all 11 mods in `dev\modlang\inst`.
- Tables land in `<out>\sc3lang\` from build_mod.ps1 (inst and tree\Apps) and in `Apps\sc3lang\` from stage_lan_release.py.

## proven game-side vs static only
- Game side: es tables on = 0 px diff vs pre-change DLLs (Cuadros + Graficas). es `SC3MODS_LANGTABLES=0` = 0 px diff.
  fr via LANGSEL: Cuadros, Graficas, query dialog, mods page in French. de via LANGSEL: query dialog + mods page.
- Static only: it / nl / sv text (format check + width measure from the in-game glyph table). Native review of all 5
  machine translations.

## blocked on
Nothing.

## files owned (worktree dev\modlang\wt, branch child/modlang from be42ba9)
Modified (git add):
- re/harness/src/sc3mods.c, re/harness/src/sc3mods.def
- re/harness/src/sc3resize.c, sc3resize_restore.c, sc3resize_vdbars.c, sc3resize_graphs.c, sc3resize_rcibars.c,
  sc3resize_vdtabs.c (FONTDUMP diagnostic only)
- re/harness/src/sc3restore.c, sc3landfill.c, sc3undo.c, sc3dataview.c, sc3autosave.c, sc3bigcity.c
- re/scripts/build_mod.ps1, re/scripts/lan_release/stage_lan_release.py
New, ignored by the deny-by-default .gitignore (need `git add -f`):
- re/harness/src/sc3mods_lang.c, re/harness/src/sc3lang.h
- re/harness/lang/es.txt en.txt fr.txt de.txt it.txt nl.txt sv.txt
New, tracked pattern:
- re/tools/sc3lang.py
Verify (RESULTS is tracked, pictures are not to be staged):
- verify/modlang/RESULTS.md
- verify/modlang/owner_shots/*.png, verify/modlang/runs/ (do not stage)

## converting strings added by other children (after their merge) - mechanical
Run from the worktree (or main after the merge), `re/harness/src` is the default source:
```
py re/tools/sc3lang.py convert                 # dry run: every inline  es ? "..." : "..."  pair it would rewrite, with its key
py re/tools/sc3lang.py convert --apply         # rewrite them to SC3TR(es, "<mod>.<key>", "...", "...") (adds the #include
                                               #   "sc3lang.h" to a module root that lacks it)
py re/tools/sc3lang.py extract                 # regenerate es.txt + en.txt from the source (never hand-edit those two)
py re/tools/sc3lang.py check                   # lists the new keys "missing" in fr/de/it/nl/sv (they show English until added)
py re/tools/sc3lang.py merge fr new_fr.json    # append translations {key: text} to a table, keeps every existing line
py re/tools/sc3lang.py check --fonts dev\<child>\inst\fontwidths.txt   # widths (fontwidths.txt: run once with SC3RESIZE_FONTDUMP=1)
```
- Keys: `<mod prefix>.<first 4 words of the English>`. The prefix comes from the file (`PREFIX` in sc3lang.py: sc3resize.c
  resize, sc3resize_restore.c lifespan, sc3resize_vdbars.c cuadros, sc3resize_graphs.c graphs, sc3resize_rcibars.c
  rcibars, sc3restore.c restore, sc3dataview.c dataview, ...). The same (prefix, Spanish, English) reuses its key, and a
  new key never collides with one already in the source.
- Language tests it recognises: `es`, `ho_spanish()`, `g_lang_es`, `vb_es()`, `g_gn_es`, `g_req_es`, `is_es`, `spanish`
  (`LANG_CONDS`). A new test name: add it there. Pairs inside `logf(` are skipped.
- After the rewrite, `convert` prints a "by hand" list: if/else blocks on the language, `_es[]` / `_en[]` arrays and
  Spanish-only literals. Convert those like the ones already done (`SC3TXT` rows `{ SC3KEY("k"), "es", "en" }` +
  `sc3lang_txt(es, &row)`, or `SC3TR(1, "k", "Spanish", "English")` for Spanish-only text). Today the list holds only 4
  known non-UI lines (sc3perf byte pattern, LANGSEL markers, a log continuation, the font probe).
- Validated 2026-11-02: run on the be42ba9 source it rewrites the same 142 pairs with the same 132 keys as this branch,
  and its by-hand list names every site that was converted by hand here.

## merge notes
- Mechanical, line-local edits: each `es ? "A" : "B"` became `SC3TR(es, "key", "A", "B")`. A child that changes one of
  those strings after be42ba9 conflicts on that line only. Keep the key, take the new text, then run
  `py re/tools/sc3lang.py extract` and `check` (es/en must be regenerated, other tables report the key as unchanged).
- New UI text from now on: write `SC3TR(es, "<mod>.<name>", "Spanish", "English")`, run extract, add the key to
  fr/de/it/nl/sv (missing keys show English, `check` lists them).
- GitHub release zip: include `Apps\sc3lang\*.txt` (no tracked zip script found, the LAN stage already copies them).

## behaviour changes the owner did not ask for (needed by the shared detection)
- sc3undo tooltips follow the game language (before: `[undo] lang=` default es, so English games showed Spanish).
- sc3dataview captions, the autosave indicator and the "Enorme" option were Spanish only. They follow the game now,
  Spanish unchanged. `bigcity.ini caption=` still wins.

## game-harness need
None left running. `dev\modlang\inst\sc3resize.ini` removed after the LANGSEL runs. `inst\fontwidths.txt` stays
(input of `sc3lang.py check --fonts`).

## asks of other sessions
None.
