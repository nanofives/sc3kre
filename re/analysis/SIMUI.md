# SIMUI.md — SIMUI.DLL, the game UI module

```
Apps\SIMUI.DLL   847,872 bytes   image base 0x10000000   6,057 functions
export: re\ghidra_export_simui\      anchored copy: original\modules\SIMUI.DLL
```

The **largest module in the game**. `SC3U.exe` is the shell (`S15_UI.md`), SIMUI is the actual
game UI, and `GZWIND.DLL` is the window-manager service underneath both.

```
SC3U.exe          UI shell: theme, splash, credits, resolution, updater
   │  GetService(0xa417445e, 0x5a4)
SIMUI.DLL         game screens: setup, catalog, terrain edit, advisors, graphs, chat
   │  GetService(0xa417445e, 0x5a4)   ← sc3ui_get_windowmgr_service 0x10012666
GZWIND.DLL        the dialog/window manager itself (ctor 0x1001fd88,
                  service-base init FUN_10023875(this, 0xa417445e, 0x1312d0))
```

**SIMUI has only 392 embedded strings** — all user-facing text lives in the `.IXF` tables
(`formats/IXF_segment.md`). String-anchoring, the technique that carried the whole `SC3U.exe`
S15 sweep, barely works here. The workable anchors are the **class registry**, **call topology**,
and **string-table group+instance ids resolved against `re/data/ixf_text.csv`**.

## Class hierarchy `[CONFIRMED]`

```
sc3ui_object_base_ctor        0x1006c2f7   ROOT, 0xa4 bytes, field [0x28]=0x903
   ├─ sc3ui_widget_base_ctor  0x1002c688   + secondary interface vtable at +0xa4
   │     └─ sc3ui_labeled_widget_base_ctor 0x10031dde   + std::string @+0xe4, [0x3e]=500
   └─ sc3ui_view_base_ctor    0x10082406   embeds the root at byte +4; 0xdeadbeef sentinels
```

> **Cross-binary link:** the root's `[0x28] = 0x903` and the view base's `0xdeadbeef` sentinels +
> resource ids `0x13`/`0x14`/`1` match the `SC3U.exe` widget base `FUN_00440296` and
> `FUN_0044d7ce` (`S15_UI.md`). Same class lineage compiled into both binaries.

## The registry — 40 classes `[CONFIRMED @0x1006a964]`

`GZDllGetGZCOMDirector` `0x100848a9` → singleton `0x1006a939` → ctor `0x1006a964` → 40 ×
`sc3ui_register_class` `0x10084c36`, which inserts `{GZCLSID, factory}` into a BST at
`director+0x14` (`0x10084eb2`).

**12 of the 40 were invisible.** Ghidra had left their factories as bare `LAB_*` — GZCOM factory
stubs are only reached through the registration table (a *data* reference), so auto-analysis never
promoted them to functions and the text export had no body for them. Recovered with the new
`re/scripts/MakeFunctions.java` + a re-export (6,045 → 6,057 functions).

| GZCLSID | factory | `new` | ctor | what it is |
|---|---|---:|---|---|
| `0x584` | `0x1006ad18` | 0x138 | `0x10063ff1` | **VIEW** — default name `*No View Name*`; factory returns the `+0x108` interface |
| `0x2f95d57` | `0x10024866` | **0x1d4** | `0x1002489b` | **largest object (468 B)**, fixed 6-entry table, `[0x73]`=3000 |
| `0x5a3` | `0x1006ad59` | 0xa0 | `0x10044021` | screen-anchored panel — the only class that adapts its rect to display mode |
| `0x57a` | `0x1006ace3` | 0x118 | `0x10061f53` | geometry object, rect 348×320 |
| `0x5a9` | `0x1006ad8e` | 0x110 | `0x10042866` | graphical control, area 0,0,0x40,0x40 |
| `0xa2a79fd0` | `0x1002c647` | 0xe4 | `0x1002c688` | the widget base, registered directly |
| `0xe2f95af5` | `0x1004f8ce` | 0x124 | `0x1004f90f` | bounded view, min/max `0xffffffff`/`0x7fffffff` |
| `0x82e968ee` | `0x10060b74` | 0x108 | `0x10060ba9` | colour/graph widget — instantiated by the terrain-edit window |
| `0x5a6`† | `0x1006ac73` | 0x14 | `0x1008665b` | small |
| `0x62be6ee2`† | `0x1001a021` | 0xfc | `0x1001a056` | |
| `0x230391b9`† | `0x1001a942` | 0x10c | `0x1001a983` | |
| `0x72e85997`† | `0x1005f242` | 0x28 | `0x1005f274` | |
| `0x30477a4`† | `0x100127c3` | 0x1c | `0x100127fe` | |
| `0x2f61b00`† | `0x1004e0ee` | 0x130 | `0x1004e123` | |
| `0x12faf305`† | `0x100649da` | 0xf4 | `0x10064a0f` | |
| `0x4324cc9b`† | `0x1004ed44` | 0x100 | `0x1004ed85` | |
| `0x756b5b54`† | `0x1006aedb` | — | `0x1006603a` | 5-byte thunk, no `new` of its own |

† recovered by `MakeFunctions.java`. Remaining ids: `0x3370d1a5`, `0xe3091435`, `0x62fa5742`,
`0xc2f14704`, `0xc2fa5860`, `0x4302b412`, `0x82f622c1`, `0x22be563e`, `0x454423ff`, `0x43164fb1`
and the `0xe42868xx` family below — all in `functions.csv`.

### The `0xe42868xx` widget family (11 ids)
Every member is built from the same template `[CONFIRMED]`: base `0x1002c688` (directly, or via
`0x10031dde`) → primary vtable at `+0`, base secondary interface at `+0xa4`, a derived interface
pair at `+0xe4/+0xe8` (or `+0x128/+0x12c` for the labelled base) → the shared marker vtable
`PTR_LAB_100a2714` → finalizer `FUN_1002d287(this + 0x29, …)`. Sizes cluster by base: `0xec`–`0x12c`
direct, `0x130`–`0x140` labelled. `0xf23b1880/1881` and `0x454423ff` follow the **same** template
under different prefixes, so the family is wider than its id block.

## Named screens

Identified by resolving the group+instance pairs the code fetches against `re/data/ixf_text.csv`.

| rva | size | screen |
|---|---:|---|
| `0x100564d9` | 8,049 | game setup — 3 radio groups, option-service driven |
| `0x1005bbd5` | 7,641 | new game — currency 50000/20000/10000, difficulty |
| `0x1003409e` | 5,442 | multiplayer chat context menu |
| `0x10008d40` | 5,218 | mode-switched dialog (`*(this+8)` = 1/2/3) |
| `0x1000690a` | 4,738 | petition window (`Pet Hdr` format) |
| `0x1001f3df` | 4,248 | **utilities chart legend** — power + garbage |
| `0x100938c0` | 3,874 | **IRC protocol dispatcher** (channel modes, PONG) |
| `0x10067620` | 3,534 | **building catalog picker** |
| `0x10089c10` | 3,457 | image resampler (graphics library, not UI) |
| `0x1005f621` | 3,418 | **terrain edit** window |
| `0x10044257` | | Maps, Graphs and Charts window |
| `0x10005602` | | advisor window (`Christine McGavran`) |

### Three names were corrected by the parent
The worker marked these `[UNCERTAIN]` for lack of strings; resolving the `.IXF` tables settled them:

- `0x1001f3df` — proposed "dataview legend". Its 18 labels (group `0x29541f4`, instances
  `0x1e8`–`0x1f7`) are **Coal / Oil / Gas / Wind / Solar / Nuclear / Microwave / Fusion /
  Waste to Energy**, Neighbor Deals, `Total Electricity Produced Annually = %s W`, then the
  garbage split (Landfill / Incinerators / Recycling / Collecting in Streets). **The first nine
  are exactly the nine SIMUTIL power-plant classes** — an independent confirmation of that
  taxonomy from a different module.
- `0x10067620` — proposed "graph window". Group `0x62e69238` instances resolve to
  `Select a Power Plant` / `Select A Water Building` / `Select a Waste Management Building` /
  `Select a Landmark Building` / `Rewards & Opportunities`. It is the **catalog picker**;
  `*(this+0x24)` selects the mode.
- `0x1005f621` — proposed "region window". Strings: `Terrain Edit`, `Accept this Terrain`,
  `Re-Generate Terrain`, `Pick Features:`, `Adjust Parameters:` → the **terrain editor**.

## String-table usage
| group | table | SIMUI functions |
|---|---|---:|
| `0x29541f4` | Window | **43** — the dominant source of SIMUI screen text |
| `0x41f2625` | SE UI | 15 — a distinct Scenario-Editor screen family |
| `0x209e6378` | App | 4 |
| `0x225872fe` / `0x15e410c` | GUI / Message | 1 each (both in `0x10058f14`) |
| `0x830cdf29` / `0x42c1ed2d` | Credits / Newsticker | **0** — stay in `SC3U.exe` |
| `0x62e69238` | **catalog** (new) | the picker window |
| `0x3c09aff` | **`SC3_STRINGTABLE_MENU`** (new) | main menu |

## Historical statistics `[CONFIRMED @0x1000d7ad]`
Three vtable accessors on a provider object each return one flat `int32` array:
`+0x28` → **12 months** (48 B), `+0x34` → **10 years** (40 B), `+0x40` → **10 decades** (40 B).
One metric at three resolutions, 128 bytes total; exported as three CSV rows.

**This is NOT the `SC3PowerLayer +0xcc` table** (a hypothesis the parent raised and the worker
disproved): SIMUI reaches the data only through an interface, never a direct field load, and the
monthly row is 12 scalars rather than 12 × 10. `[UNCERTAIN]` which GZCOM class backs the provider
— candidates `0xe41d8fee` and `0xe404e938`, unconfirmed; `0x1000d7ad` has no static caller.

## Dialogs
`0x10058f14` raises a modal through the same dialog-manager `vtable+0xac(strA, strB, mode, 1, 0)`
signature as `SC3U.exe` and tests `== 0x5301814c` for OK — mechanism identical. But its
`mode = 0x30003` is **not** in `SC3U.exe`'s observed set `{2, 3, 0x10001, 0x10003, 0x10004}`, so the
mode bitfield remains `[UNCERTAIN]`. `0x5377be31` is used identically to `SC3U.exe`: a manager
`+0x8c` resource fetch spliced into text, not a button id.

## Open
- The concrete role of each registered class (`*No View Name*` `0x584`, the 468-byte `0x2f95d57`)
  — object size and vtable width only; no string or constant proves a role. Not asserted.
- Which class backs the statistics provider.
- The `mode` bitfield in the modal call.
