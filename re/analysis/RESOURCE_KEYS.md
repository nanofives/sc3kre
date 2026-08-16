# RESOURCE_KEYS.md — the GZCOM resource key and the localized string path (U-007, RESOLVED)

Resolved 2026-08-14. Started as the U-006 GZCLSID grind, which was falsified; the probe that
killed it exposed this instead.

## The object `[CONFIRMED]`

`sc3_gz_make_resource_key` @`0x00484b6d` (45 bytes) builds a 3-tuple key:

```c
this[0x00] = &PTR_FUN_004da53c;   // vtable
this[0x04] = 0;
this[0x08] = 0x2026960b;          // TYPE  — fixed for every call site in SC3U.exe
this[0x0c] = param_2;             // GROUP — string-table id
this[0x10] = param_1;             // INSTANCE — index within the table
FUN_004862e1(this);
```

`sc3_gz_get_resource_key` @`0x00484c7a` (25 bytes) reads it back as `{0x2026960b, +0x0c, +0x10}`.

This is the same **type / group / instance** shape as a `CitySim.ini [AgentTypes]` value
(`0x2026960B,0x41F56C4C,0x41F836xx`) — hence the earlier misreading of it as class registration.
It is not: in `SC3U.exe` the type is always `0x2026960b` and the payload is **localized text**.

## The family

| RVA | name | role | conf |
|---|---|---|---|
| `0x00484b6d` | `sc3_gz_make_resource_key` | ctor (group, instance) | C2 |
| `0x00484c7a` | `sc3_gz_get_resource_key` | getter → triple | C2 |
| `0x00484bef` | `sc3_gz_resolve_key_to_string` | key → `std::string` (then `FUN_0040262c`) | C1 |
| `0x00484b9a` | — | destructor/release (paired with every ctor) | C0 |
| `0x00484beb` / `0x00484c93` | — | validity tests | C0 |
| `0x00484d84` | — | extract into a caller object | C0 |
| `0x00484b0a` / `0x00484ba5` | — | key-set insert (used by `sc3_ui_init_theme`) | C0 |

## Group ids — RESOLVED 2026-08-14 (U-008 closed)

Every group id is the `group` field of an index record in an `.IXF` GZ database segment under
`Apps\Res\Text\<LANGUAGE>\` (format: `re/analysis/formats/IXF_segment.md`; parser:
`re/tools/ixf_parse.py`). Extracted with `ixf_parse.py Apps/Res --csv re/data/ixf_text.csv`
— **537 files, 71,924 records, 0 unreadable**. Counts below are for `English-UK`.

| group | .IXF file | records | the game's own placeholder string |
|---|---|---:|---|
| `0x209e6378` | `SC3StringsApp.IXF` | 91 | `NEED SC3_STRINGTABLE_APP STRING` |
| `0x41f2625` | `SEStringsUI.IXF` | 137 | `NO SE UI STRING AVAILABLE` |
| `0x29541f4` | `SC3StringsWindow.IXF` | 462 | `NEED SC3_STRINGTABLE_WINDOW STRING HERE` |
| `0x830cdf29` | `SC3StringsCredits.IXF` | 378 | (empty) |
| `0x225872fe` | `SC3StringsGUI.IXF` | 135 | `NEED SC3_STRINGTABLE_GUI STRING HERE` |
| `0x63de4715` | `BATStringsMain.IXF` | 174 | `NO BAT STRING AVAILABLE` |
| `0x15e410c` | `SC3StringsMessage.IXF` | 47 | `NEED SC3_STRINGTABLE_MESSAGE STRING HERE` |
| `0x42c1ed2d` | `SC3StringsNewstickerTriggered.IXF` | 337 | *(news ticker headlines)* |

The placeholder text at instance 0 of each table names the table itself — `SC3_STRINGTABLE_APP`,
`_WINDOW`, `_GUI`, `_MESSAGE`. That is the shipping build telling us the group semantics directly.

### Round-trip verification `[C4]`
`sc3_ui_create_sysinfo_window` `0x00436a94` builds its title from group `0x29541f4`,
instance `0x2a6` (678). Resolving that key against the data:

```
Apps\Res\Text\English-UK\SC3StringsWindow.IXF   029541f4:678   "System Info"
Apps\Res\Text\GERMAN\...                                        "Systeminfo"
Apps\Res\Text\FRENCH\...                                        "Infos système"
```
Code prediction → data confirmation, so `0x00436a94` is verified behaviour, not just a read.

> **Localisation quirk (observed):** the directory named `ENGLISH` contains **Spanish** text; the
> English strings are in `English-UK`. Verified on `BAMBEStringsMain.IXF` across four languages.

`0x449b1912` (from `sc3_ui_init_html_window` `0x004a3f0c`) does **not** appear in any text
segment — it is paired with type `0x849b190a`, not `0x2026960b`, so it is a different resource
kind. Relevant to U-001.

## Group ids as originally observed (superseded by the table above)

`0x209e6378` · `0x41f2625` · `0x29541f4` · `0x830cdf29` · `0x225872fe` · `0x63de4715` ·
`0x15e410c` · `0x42c1ed2d`. None occurs in `SYS.PAK`/`CitySim.ini`; they also appear in
`SIMUI.DLL`, `SIMMISC.DLL`, `SIMADV.DLL`, `SIMINIT.DLL`, `SCENARIO.DLL` — i.e. global,
cross-module string-table ids. The tables themselves are not in `SC3U.exe`.

Useful known instances for pinning a table:
- grp `0x29541f4` inst `0x2a6` = system-info window title (`0x00436a94`); inst `0x2a7`–`0x2b7` = its field labels.
- grp `0x209e6378` inst `0x6a4`–`0x6d6` = system-info values (CPU/sound/memory strings, `0x00436f31`).
- grp `0x41f2625` inst `0x1f4`–`0x1f7` = update-check dialog text (`0x004108f3`).
- grp `0x830cdf29` inst `2`–`0xbc` and `+199` = credits lines (`0x00428801`).

## The 20 call-site functions (all merged into `functions.csv` at C2)

Named: `sc3_ui_init_theme` `0x0040efd8` · `sc3_ui_run_updatecheck` `0x004108f3` ·
`sc3_ui_init_credits_screen` `0x00428801` · `sc3_ui_build_music_window` `0x0042affa` ·
`sc3_ui_set_widget_text_from_resource` `0x0042be5a` · `sc3_data_read_file_to_buffer` `0x004304f5` ·
`sc3_ui_build_resolution_menu` `0x00430e6b` · `sc3_ui_create_sysinfo_window` `0x00436a94` ·
`sc3_ui_populate_sysinfo_text` `0x00436f31` · `sc3_ui_make_object_from_key` `0x0043b436` ·
`sc3_ui_setup_splash_screen` `0x0043e4a3` · `sc3_text_expand_token_by_type` `0x004853e8` ·
`sc3_text_expand_token_by_keyword` `0x004856b2`.

Left unnamed (mechanically described, `[UNCERTAIN]` purpose): `0x00405092` `0x004064ee`
`0x0040ed1c` `0x004218b0` `0x00422c4e` `0x0042e409` `0x0042f629`.

## What this says about SC3U.exe

Every one of the 20 is **S15 (UI) / S18 (data-IO) / S14 (text substitution)** — shell code.
`0x00436f31`, the #2 entry on the P1 size list (9.4 KB), turned out to be the *system-info
dialog text builder*. Combined with `MODULE_MAP.md`: `SC3U.exe` contains the shell, and
grinding its size list will keep yielding UI, not simulation.

## Notable individual findings
- `sc3_ui_init_theme` `0x0040efd8` maps 8 resource keys to dialog ids `0x5301814c`…`0x5377be31`
  via `vtable+0x90`, and registers the 21-entry palette, the `.fon`/`.fbf` fonts and the six
  `res\ui\shared\cursors\*.cur` cursors — a good entry point for the whole UI theme system.
- `sc3_text_expand_token_by_keyword` `0x004856b2` is the `%MAYOR%` / `%ANYNEIGHBOR%` token
  expander (token region `&DAT_004f80b4`, adjacent to the token strings at `0x004f804c`–`0x004f80a0`)
  — the ticker/newspaper text pipeline (S14).
