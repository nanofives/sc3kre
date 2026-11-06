# CIVICDEALS: Civic Deals D9 / DA in Spanish, installed by a patcher (child/civicdeals, 2026-11-06)

Owner decision (re/analysis/COMMUNITY_MODS.md): D9 "Back Door Development Deal" and DA "WMT Redevelopment Offer" as
is, translated into Spanish, installed on the player's own files. Tool: `re/tools/civicdeals_patch.py`.

## What the author's package changes (measured against the stock files)

- `SYS.PAK`: two members only. `PetitionerExtraInfo.ini` + `0x000000D9=19,2`, `0x000000DA=19,2` after `0x000000D8`.
  `PetitionerManager.ini` `NumberOfPetitionerMessages` 210 -> 212.
- Six `Sc3StringsPetitioner*.IXF` (Advice, Button1, Button2, Heading, Reaction1, Reaction2): two new records each,
  instances 0xD9 / 0xDA, in the index's spare zero slots, payload at the end. Their `size` is the string length
  (prefix excluded), same as the stock files.
- `SC3KCivicDeals.dll` carries its own English for the petitioner name, the window title, the message body, the buttons,
  the reactions and every cheat notice (the game shows the DLL's copies of name, title, body and reactions).

## What the patcher does

- Same SYS.PAK and IXF additions on the player's files, any number of text folders. The `ENGLISH` folder gets Spanish
  when its 0xD7 heading differs from English-UK's (a Spanish install), every other folder gets the author's English.
- Copies the DLL into Apps and, for Spanish, rewrites 30 strings in place, each checked against the English original and
  inside its NUL-padded slot (the DA body was cut to fit 531 bytes).
- Backup `<file>.civicdeals-orig` once, writes through temp + rename (a hard-linked tree gets its own copy: SYS.PAK link
  count 13 -> 1 in the tree, `stage\release` hash unchanged). Second run: 43 "already" lines. `--restore` puts it back.
- Spanish follows the game's own words: "Alcalde", "arcas", "simlletes". WMT = "TMC (Tecnología de Modificación del Clima)".

## In game (dev/civicdeals tree, Craterville, 800x600, FRAMEDUMP, posted input)

| step | result |
|---|---|
| `corruptncrazy` (cheat box opened with a Frida GetKeyState hook, text posted) | notice "La primera propuesta de desarrollo le espera en Reunirse..." |
| Reunirse list | "Trato de desarrollo por la puerta de atrás" |
| open it (posted double click: two down/up pairs 30 ms apart; one click only selects) | title, name, body, buttons in Spanish |
| Análisis de impacto | Spanish, %YOURCITY% -> Craterville |
| Aprobar el acuerdo privado | notice "Acuerdo privado aprobado. Se ingresaron 100.000 simlletes.", reaction in Spanish, funds 47,180 -> 147,180 |
| next Reunirse | "Oferta de reurbanización TMC" in place of D9 |
| DA open + análisis | Spanish |
| Aprobar la prueba de TMC | "TMC activada. Se forma un tornado...", funds 147,180 -> 247,180, camera to a tornado, "¡¡TORNADO!!" ticker |

No VEH fault (only the start-up privileged-instruction one every tree logs). Picture: `owner_shots/1_d9_da_spanish.png`.

Not checked: the reject buttons, the English-UK / other-language folders in game, the petitioner portrait (blank on both
offers; the author's `19,2` portrait entry, not compared with the untranslated package), save/load with an offer pending.
The DLL's notices are Win32 message boxes, which take the foreground window (the cheat itself shows them).

## Extra Cheats (Null 45, MIT): shipped unchanged

`civicdeals_patch.py` also copies `SC3KExtraCheats.dll` unchanged into Apps (`--restore` removes it). Its three cheats,
per the upstream README (github.com/0xC0000054/sc3k-extra-cheats): `dotcom` +1,000,000, `moolah <n>` sets the funds,
`SimDate <m> <d> <y>` sets the date. No visible text of its own, so nothing to translate.

| cheat (dev tree, both DLLs loaded, then ExtraCheats alone) | result |
|---|---|
| `dotcom` | funds 10,933 -> 1,010,933 (both setups) |
| `moolah 500000` | funds 500,000 |
| `SimDate 1 1 1990`, `simdate 1 1 1990`, `SimDate 5 20 1900`, `SimDate 1 1 1840` (README example), sim running or paused | **date unchanged** (1933 kept), with and without SC3KCivicDeals.dll |

Cause found and fixed 2026-11-06 (verify/simdate/RESULTS.md): the stock "sim" cheat caught the text first. Old note:: the stock-tree control (`-Stock`) could not be read (the 16-bit DWM garbling,
`project-dwm16-mitigation-root-cause`), so whether our mods or the GOG 2.0.949 build stop it is not known yet.
