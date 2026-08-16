# S15_UI.md — the SC3U.exe UI subsystem

State after the 2026-08-14 S15 sweep. **47 rows in `functions.csv` carry `subsystem=S15`**;
34 of them are named. `SC3U.exe` is the GZCOM shell (`MODULE_MAP.md`), so S15 is the largest
genuinely-resident subsystem in this binary — this doc is close to a complete account of it.

## Architecture as the code shows it

```
framework singleton  DAT_004fab74   (thunk_FUN_0045d5ae)  — GZCOM, GetService at vtable+0x10
   ├─ string-table service   CLSID 0x801998e4  IID 0x1995e7  → DAT_004fae78  (sc3_gz_get_string_manager 0x0048440b)
   └─ dialog/window manager  CLSID 0xa417445e  IID 0x5a4     → DAT_004fac90  (sc3_ui_get_dialog_manager 0x004703a7)
```

Neither service is implemented in `SC3U.exe` — both live in the GZCOM DLLs. `SC3U.exe` only
holds the client side.

## Localized text path `[CONFIRMED]`

Corrects an earlier reading in `RESOURCE_KEYS.md`: `FUN_00484bef` does **not** resolve anything.

1. `sc3_gz_make_resource_key` `0x00484b6d` stores the triple `{0x2026960b, group, instance}` at `+8`.
2. The ctor tail calls **`sc3_gz_reskey_resolve` `0x004862e1`** — the actual resolver:
   `(*(*stringManager + 0x14))(this+8, 0x69, this+4)` @`0x004862f1`. Manager vtable **slot 0x14**,
   the triple, the constant **`0x69` (105, meaning unknown — `[UNCERTAIN]`)**, and an out-pointer.
   On failure `+4` is nulled.
3. `sc3_gz_reskey_copy_string` `0x00484bef` then just copies the cached string behind `+4`
   (or yields an empty `std::string` if unresolved).

Accessors: `…_get_string_ptr` `0x00484beb` · `…_is_resolved` `0x00484c93` ·
`…_write_to_sink` `0x00484d84` (pushes `(ptr,len)` into a sink's vtable+0xc) ·
`…_init_empty` `0x00484b0a` · `…_assign` `0x00484ba5` (re-resolves) · `…_dtor` `0x00484b9a`.

## Widget object model `[CONFIRMED]`

Base ctor `FUN_00440296` installs vtable `&PTR_FUN_004d3838`, allocates a 0xc-byte self-linked
list node at `+0x34`, sets flag `+0x60`=1 and `[0x28]`=0x903. Object is ~0x120+ bytes.
Subclass fields: `+0xa4` type/id tag (`0x25e74ba1` at `0x0043d328`, settable via `0x0043d672`),
`+0xc0`, child-slot array at `+0xb0` with a parallel id array at `+0xb8` (`0x0043d6f7`).

### Widget vtable slot map

| slot | behaviour | proven at |
|---|---|---|
| `+0x04` | AddRef | `0x00443d0d`, `0x0043e4a3`, `0x0043d6f7` |
| `+0x08` | Release | `0x0042a53f`, `0x0042a5ed`, `0x0043d6f7` |
| `+0x0c` | → sub-object (drawing/child accessor) | `0x0042a53f` |
| `+0x1c` | → sub-object | `0x0042a5ed` |
| `+0x24` | set attribute (color; also `(4,0)`) | `0x0042a53f`, `0x0042a5ed` |
| `+0x28` | no-arg call during show/finalize | `0x0043e4a3` |
| `+0x34` | add child to parent | `0x0042a53f`, `0x0042a5ed` |
| `+0x40` | set attribute from singleton id 0xf | `0x0042a53f` |
| `+0x44` | create/lookup child by id | `0x0042a53f` |
| `+0x78` | find child by id → widget-or-null | `0x0042a796`, `0x0043d6f7` |
| `+0x8c` | set text | `0x0042be5a` |
| `+0xa0` | add to display/child list | `0x0043e4a3` |
| `+0xc8` | set bounds (4 args) | `0x0042a53f` |
| `+0xcc` | set position (2 args) | `0x0042a5ed` |
| `+0xec` | called with an id on the `+0xc` sub-object | `0x0042a53f` |
| `+0xf4` | set state/flag on child | `0x0042a796` |
| `+0x10c` | notify/attach child | `0x0043d6f7` |

Owner vtable (object at widget `+0x4`): `+0x74` bool-returning, `+0x80` object-returning,
`+0x94` passes the widget. All three reached only through the forwarder thunks
`0x0044215d` / `0x004422d4` / `0x0044211a` — **`[UNCERTAIN]`**, the class that installs the
owner vtable was not found in `SC3U.exe`.

## Dialog system `[CONFIRMED]`

Modal call = dialog-manager **vtable `+0xac`**, five args: `(strA, strB, mode, 1, 0)`. `strA`/`strB`
are `std::string`s built from resource keys; `mode` observed as `2`, `3`, `0x10001`, `0x10003`,
`0x10004` — **`[UNCERTAIN]` bitfield**. Returns an int compared against these ids:

| id | role as the code uses it | proven at |
|---|---|---|
| `0x53018146` | registered only (`+0x90`), never compared | `0x0040efd8` |
| `0x53018147` | → framework `+0x40`(0), abort loop, return false | `0x004064ee` |
| `0x53018148` | registered only | `0x0040efd8` |
| `0x53018149` | cancel/no branch | `0x004108f3` |
| `0x5301814a` | sets the boolean result true | `0x004108f3` |
| `0x5301814b` | registered only | `0x0040efd8` |
| `0x5301814c` | OK/affirmative branch | `0x004108f3` |
| `0x5377be31` | not a button — a resource fetched via manager `+0x8c` and substituted into text | `0x004431e1`, `0x0048631a` |

`sc3_ui_init_theme` `0x0040efd8` is what *binds* each id to a localized string (manager `+0x90`),
alongside the 21-entry palette, the `.fon`/`.fbf` fonts and the six `res\ui\shared\cursors\*.cur`.

## Screens / clusters

| cluster | entry point | note |
|---|---|---|
| Theme + dialog-id registration | `sc3_ui_init_theme` `0x0040efd8` | the UI bootstrap |
| Main menu | `sc3_ui_build_mainmenu_buttons` `0x0043a31e` | parses `MAINMENUBMP`, `'< > = ,'` records, instances `0x22729930`–`0x22729938` |
| Splash | `sc3_ui_setup_splash_screen` `0x0043e4a3` + `sc3_ui_read_splashbmp_regkey` `0x0043e28b` | key comes from **registry** `HKLM\…\Maxis\SimCity 3000 Unlimited\SKU\SPLASHBMP` |
| Intro movie | `sc3_ui_play_intro_movie` `0x00429f95` | `Res\UI\Shared\Movies\Intro.tgq`, 640×480 |
| Credits | `sc3_ui_init_credits_screen` `0x00428801` | group `0x830cdf29`, lines 2..0xbc |
| Music/albums | `sc3_ui_build_music_window` `0x0042affa` | `Albums` |
| Resolution menu | `sc3_ui_build_resolution_menu` `0x00430e6b` | 320×240…1024×768, gated on display width |
| System info | `sc3_ui_create_sysinfo_window` `0x00436a94` → `…_populate_sysinfo_text` `0x00436f31` | 44 string keys, CPUID, memory |
| Updater | `sc3_ui_run_updatecheck` `0x004108f3` + `0x00404052` + `0x00404797` | `Updater\UpdateSettings.ini` |
| HTML window | `sc3_ui_init_html_window` `0x004a3f0c` | title `HTML Window`; **lead for U-001** |
| Menu-data resources | `sc3_boot_register_all_factories` `0x0040b761` | also registers `SC3MBTNDEFS`/`SC3MSET`/`SC3MDESC`/`SC3MII` + `Sys\MenuItem.ini` |

Widget construction helpers: `0x0042a53f` `0x0042a5ed` `0x0042a796` `0x00443d0d` `0x004395dd`
`0x0044d7ce` `0x0043d328` `0x0043d672` `0x0043d6f7` `0x0043b436` `0x0042be5a`.

## Reclassified OUT of S15
`0x0049c1ec` WinSock message window → NET · `0x0045f994` `Gonzo Debug Window` → S1 ·
`0x0040496d` mutex/single-instance app boot → S1.

## Open
- Owner-vtable slots `+0x74`/`+0x80`/`+0x94` — needs the class that installs it (likely a DLL).
- Dialog `mode` bitfield and the resolver constant `0x69`.
- **U-008**: the string tables themselves are behind GZCOM class `0x801998e4`, not in this binary.
- **U-001**: `0x004a3f0c` is the `HTML Window` initialiser; not yet tied to `DAT_004fb170`.
