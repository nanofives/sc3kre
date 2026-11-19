# sc3compat-b results (round 2026-11-19e): the pack reader

Verdict: steps 1 to 5 done, except the classifier.html hook (it waits for the orchestrator, gamefont). New
`re/tools/bldimport/sc3pack.js` (page) and `sc3pack.py` (Python twin) open a pack as downloaded, sort its files,
report every .bld's parts, and install / remove parts in Apps\BACustom. The page and Python write the same JSON, byte
for byte, on 6 packs. Tests: sc3pack_golden.mjs 21 of 21, sc3pack_pagetest.mjs (Chrome) 9 of 9, run_all.sh 18 of 18.

## 1. Open and sort

Input: a .zip (deflate or stored), a folder (a File list from a folder pick, or a folder handle), a .zip inside a
.zip (3 levels), a folder holding .zip files. Entry names: UTF-8 when flag 0x800 is set, else cp437, `\` read as
`/` (the Python zipfile rules). CRC and size are checked. A broken or encrypted entry, or an unsupported method,
becomes an "other" row with the reason. The pack is not unpacked to disk.

Every file gets one kind:

| kind | rule |
|---|---|
| building | IXF (magic 0x80C381D7) holding the BA model record (group 0xC3F8D4A9, type 0xE3F87B0C), any extension. Model version 8 (SC3U) and 7 (1999 BA) |
| part | .tga with a valid TGA header, .bmp with a valid BMP header, a .met whose first line is `x,y,z:` (prop). Kind: Paints / Details / Props folder, else a .met naming the image (prop), else the .bld's record 0xE3F87B0D (version 8 only), else "kind unknown" (the player picks one) |
| plugin | a .pin with [DBSegments] (the Maxis add-on ini) and the IXF .dat files it names. Identified only: segments found, each OccupantKeys key looked up in the .dat, SpriteSegments listed |
| readme | .txt .doc .rtf .htm .html .pdf .nfo .wri .md, or "readme" in the name |
| archive | a .zip that was opened (its files follow under `<name>.zip/`) |
| other | with a note: installer file, Windows program (not run), not a readable .zip, macOS metadata, not an IXF file, ... |

The 1999 files read with no format change beyond two (needed for the part list, measured on the 19 patch files):
- model record 0xE3F87B0C: byte 0 = 7 instead of 8, the rest of the layout the same (column table at 0x21,
  separators, QFS cell blob, texture list).
- part record 0xE3F87B0D: byte 0 = 7, same fields up to the name (u32 length at 57, name at 61), then the image key
  (type, group, instance) and NO kind u32 (85 bytes for a 12-character name, against 89 in version 8). So 1999 parts
  have no kind in the .bld.

`bldfile.custom_textures` (sc3compat-a's file) raises `struct.error` on these records (it reads the kind u32). Told
the orchestrator. sc3pack does not use bldfile: it has its own reader for the fields it needs.

## 2. Dependency report per .bld

Every texture name in the model's texture list (case-insensitive, first wins), in the order the BA renderer resolves
it (verify/bldbat/RESULTS.md step 3):

| status | meaning |
|---|---|
| color | `color ...`, no file |
| embedded | the .bld carries the image (0xE3F87B0D with its 0xE3F87B10 record present): the renderer uses it |
| stock | a file with that name under Apps\Res\BA |
| pack | a part in this pack. `pack_state`: new / installed (the same bytes already in Apps\BACustom) / conflict (a different file with that name there) / pack files differ (the pack has two different files with that name) |
| custom | only Apps\BACustom has it. The BA uses it only when its content is the one the .bld was made with, which cannot be checked here (the hash in the .bld is [UNCERTAIN], bldbat step 3) |
| missing | found nowhere: drawn flat, named in `missing` |

Same-named files are byte-compared (sha256): pack part against the Apps\BACustom file, pack part against pack part.
8.3 names (`bourbo~3.tga` in Kankakee) are flagged "8.3 short name".

Cross-check against `bldfile.parts` (task bldbat) on the 17 shipped .bld: 1,827 texture names, same status and same
file for every one.

Measured on the samples (game = dev tree):
- 17 shipped .bld: 0 missing apart from Kankakee's `bourbo~3.tga` (as bldbat found).
- 19 1999 .bld: all read (version 7); 0 missing; embedded parts in Castle 3, Knight's Hall 1, Licks 4, Maxis Plaza 2,
  Wayne's House 1, Wren's House 3; every other name is a colour or stock.
- Maxis add-on installers (folder of 3 unpacked installers, 50 files): LandmarkPack1 .pin + .dat (3 occupants, 3 in
  the .dat), LandmarkPack2 (2 of 2); the InstallShield files sorted as "installer file" / "Windows program".

## 3. Install and Remove

`install(game, entries, pack, overwrite, kinds)` writes each part to `Apps/BACustom/<Paints|Details|Props>/<name>`
(the existing file's case if one exists):
- same bytes already there: nothing written ("already installed");
- a different file with that name: NOT written ("conflict: a different X is in ..."), unless the player ticked that
  name (`overwrite`): then the game's copy is backed up first;
- unknown kind: skipped until the player picks a kind; two different pack files with one name: skipped; an identical
  duplicate: written once.
- a prop .met goes with its bmps into Props.

Backups and state: bldimport's scheme in its own folder, `mods/netmod/sc3pack/state.json`
(`{files: {rel: {existed, written sha256, pack, source}}}`) + `backup/<rel>`. A separate folder because bldimport's
apply() puts back every file of its last run, so sharing its state would undo the buildings. Writes are temp + rename
(link-safe on hard-linked trees). `remove(game, pack)` puts back the backup or deletes the file it created, and leaves
(and says so) a file changed since the install.

## 4. Test packs (local only, `stage\st_packs\testpacks\`, made by `webtest/sc3pack_testpacks.py`)

- `plain_bld.zip`: Dupont House, HiTech Lab, Longview Park (v8) + Castle, Licks (1999 v7), deflate.
- `bld_parts.zip`: "sc3pt Test Plant.bld" = Trash & Burn with 9 part names changed and their embedded images
  stripped; parts copied from the game's BACustom under new names (Details, Props, loose), one written from the
  .bld's own embedded image (32-bit TGA), `Mariners 04.tga` with one byte changed (conflict), an identical duplicate,
  one missing name, one loose image no .bld uses (kind unknown), a prop .met naming the renamed bmps, a readme.
  Report: 12 colour, 12 embedded, 106 stock, 8 pack, 1 missing (`sc3pt missing.tga`).
- `nested.zip`: readme, SETUP.INI, an unknown file, LandmarkPack2 .dat/.pin, a broken .zip, macOS metadata, inner.zip
  (2 .bld, one v7) holding more/deeper.zip (1 v7 .bld).
- plus `maxis_addons_2000\`, `maxis_batpatch_1999\` and the game's `Buildings\` opened as folders.

## 5. Tests

- `sc3pack_golden.py` (Python reports with and without a game, and the install run on a small copy of the game:
  install, install again with `Mariners 04.tga` overwritten and a kind picked for `sc3pt loose.tga`, remove;
  remove gives back Apps\BACustom byte for byte).
- `sc3pack_golden.mjs` 21 of 21: 6 packs x (with game, no game) reports = Python byte for byte; the install run on a
  listFS view (page with a file list) = Python at every step (log + sha256 of every file); the same on a real
  folder through handleFS (Chrome's folder access), Res\BA hard links intact; a folder handle gives the same report.
- `sc3pack_pagetest.mjs` 9 of 9 in headless Chrome (sc3pack_view.html, Chrome's own DecompressionStream): the 6
  reports = Python; the view draws the groups, the missing row, the overwrite box and the kind pick; the Install
  click passes `["Mariners 04.tga"]` and `{"sc3pt loose.tga": "detail"}`; no horizontal scroll at 412 px.
  Pictures: `owner_shots/sc3pack_view_phone.png`, `sc3pack_view_desktop.png`.
- `run_all.sh`: 4 new steps (test packs, Python golden, JS golden, Chrome). Samples from `SC3PACK_PACKS`
  (default `<repo>\stage\st_packs`). Result: **18 of 18** steps, SC4 included (14 existing + 4 new), on main 743d532 + this branch, game = dev\sc3compat-b\tree. Log `verify/sc3compat_b/run_all.log`.

## The classifier.html hook (waiting for the orchestrator)

```html
<script src="sc3pack.js"></script>            <!-- after bldweb.js; sync_css.py --publish must copy it too -->
<button id="packOpen">Open a building pack (.zip or folder)</button> <div id="packView"></div>
```
```js
const ents = await SC3PACK.openFiles(input.files);           // or SC3PACK.openHandle(await showDirectoryPicker())
const draw = async () => SC3PACK.view(document, packView, await SC3PACK.report(ents, gameFS), {
  onInstall: async (ow, kinds) => { await SC3PACK.install(gameFS, ents, packName, ow, kinds); await draw(); },
  onRemove: async () => { await SC3PACK.remove(gameFS); await draw(); } });
```
`gameFS` = the page's game folder view (handleFS, or listFS then `BLDWEB.zipOf(game.writes)` as the download, as the
importer does). The view uses sc3ui.css classes only (ui-group, ui-table, ui-note, ui-label, button.primary).

## Not done / limits
- The hook (above). The plugin .dat/.pin are identified, not installed (ploppables: a later round).
- Whether a BACustom file has the content a .bld was made with cannot be checked (hash [UNCERTAIN]); the report says
  "custom" and the pack's copy is byte-compared only against files.
- ZIP64 and encrypted .zip are not read (reported). Python's zipfile reads ZIP64; the page does not.
- Which of Res\BA and BACustom wins for the same name in the BA is not measured; the report follows bldfile.parts
  (stock first).
