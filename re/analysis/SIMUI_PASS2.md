## 1. Promoted rows (C1 → C2)

All 13 bodies were read; each is described mechanically below with callees and constants. None reach C3 (no runtime/second witness), so all are capped at C2.

```csv
rva,subsystem,confidence,new_name,evidence
0x100127fe,ui/dispatch,C2,sc3ui_msghandler_map_ctor,"2 vtables [0]/[1]; FUN_10016e11 builds RB-tree node (alloc 0x18) at [+8]; then 14x FUN_10012a99(this,id,handler) inserting {id->fn} via FUN_10055917 map-insert (key @node+0x10); ids 0x75807646..0x75807652 + id 1; new size 0x1c"
0x1001a056,ui/widget,C2,sc3ui_object_ctor_acquire_res,"FUN_1006c2f7 root ctor; sub-obj ctor FUN_1008aa23(+0x37) sets 100/1000 and self-registers into global list &DAT_100bfba0 under crit-sect 0x100bfb78; FUN_10085065 service (GetService 0xc2c2eb0f/0x22c2eb1f) vtable+0x80(0x13)->[0x36], (0x14)->[0x35]; new 0xfc"
0x1001a983,ui/widget,C2,sc3ui_object_ctor_plain_230391b9,"FUN_1006c2f7 root ctor; zero-inits [0x2a..0x42] incl byte fields; sets primary vtable PTR_FUN_100a3d08 and secondary [0x29] PTR_LAB_100a3ce0; no resource/service calls; new 0x10c"
0x10030b8c,ui/widget,C2,sc3ui_widget_ctor_e4286882,"e42868xx family template: FUN_1002c688 widget base; derived iface pair [0x39]/[0x3a]=+0xe4/+0xe8; marker vtable PTR_LAB_100a2714; zero [0x3b..0x3f]; finalizer FUN_1002d287(this+0x29,...)"
0x100385c5,ui/widget,C2,sc3ui_widget_ctor_e4286890_2vec,"same family template as 0x10030b8c; adds 2 container members via FUN_10005eb6 at +0x3e and +0x43 (each reserves 8 via FUN_1000b6da); finalizer FUN_1002d287"
0x1003ccc0,ui/widget,C2,sc3ui_widget_ctor_e4286899_3vec,"same family template; 3 container members via FUN_10005eb6 at +0x3d,+0x42,+0x49; extra byte fields; finalizer FUN_1002d287"
0x1004e123,ui/tool-desc,C2,sc3ui_tooldesc_ctor_tag_287c760,"FUN_1004d9be base ctor (root + 12-byte circular-list node alloc, flag|8); [0x2e]=self; [0x2a]=(&~8)|1; writes type tag [0x2c]=0x287c760 (offset 0xb0) READ by factory FUN_1004dc89 to pick new(0xfc); tags 0x287c760/1/2 select 3 sub-classes; new 0x130"
0x1004ed85,ui/widget,C2,sc3ui_object_ctor_4324cc9b,"FUN_1006c2f7 root ctor; 2 container members via FUN_10005eb6 at +0x35 and +0x3a; vtables PTR_LAB_100a9f0c / [0x29] PTR_LAB_100a9ef4; new 0x100"
0x1005f274,ui/color-desc,C2,sc3ui_colordesc_ctor,"standalone (NO base ctor); zero-inits [2..9]; FUN_1005f2dc writes RGB bytes +0x12/+0x13/+0x14 = 0x80,0x80,0x80, dword +0xc=2, word +0x10=8; vtables PTR_FUN_100aaae0 / [1] PTR_LAB_100aaad0; new 0x28"
0x10064a0f,ui/widget,C2,sc3ui_object_ctor_plain_12faf305,"FUN_1006c2f7 root ctor; zero-inits [0x2a..0x3c] (19 dwords); vtables PTR_LAB_100ab274 / [0x29] PTR_LAB_100ab264; no service calls; new 0xf4"
0x10085091,ui/service,C2,sc3ui_get_windowmgr_singleton,"lazy cache DAT_100bfabc: if 0 -> FUN_10012666 (GetService 0xa417445e/0x5a4 = window-mgr, same pair as SC3U) then release temp FUN_10012687; returns cached ptr"
0x10085179,ui/service,C2,sc3ui_get_service_441e5070_singleton,"lazy cache DAT_100bfacc: if 0 -> FUN_10085353 (GetService CLSID 0x441e5070 / IID 0x54b7d5) then release FUN_10085374; returns cached ptr; role of 0x441e5070 not proven by any string"
0x1008665b,ui/widget,C2,sc3ui_smallobj_ctor_5a6,"trivial: zero [1..4]; set vtable [0]=PTR_LAB_100aeba0; no base ctor; new 0x14 (5 dwords)"
```

**Notes on the naming corrections:** `0x10085091` was `sc3ui_get_parent_registry` — the decomp shows it caches the **window-manager** service (`0xa417445e/0x5a4`), the same pair SIMUI.md already names `sc3ui_get_windowmgr_service`. `0x10085179` was `sc3ui_get_screen_info` — no evidence supports "screen info"; it caches `GetService(0x441e5070, 0x54b7d5)`, so the name now carries the raw ids.

**Two would-be-trivial ctors that still reach C2:** `0x1001a983` and `0x10064a0f` are pure zero-init + vtable ctors, but callees (`FUN_1006c2f7` root) and every offset/vtable are identified, so they clear the C2 bar.

---

## 2. OPEN-list resolutions

### (a) Role of each registered class — `*No View Name*` `0x584` and the 468-byte `0x2f95d57`
**PARTIALLY RESOLVED — still no role assertion, but more mechanical detail.**
- `0x584` ctor `0x10063ff1` `[CONFIRMED]`: derives the **view base** `FUN_10082406`; copies `"*No View Name*"` (`s__No_View_Name__100bf004`) into a `std::string` at `+0x46` via `FUN_10005f5e`; sets `[0x4c]=0xffffffff`, byte `[0x4d]=0`. It is the **default/placeholder view** carrying a name string; nothing beyond the name string proves a further role.
- `0x2f95d57` ctor `0x1002489b` `[CONFIRMED]`: root-derived; container member at `+0x6e`; constants `[0x73]=3000` (confirms SIMUI.md) and `[0x74]=1`; a fixed **6-iteration loop** zeroing a 6-entry table (per-entry stride: 4 dwords + 1 dword). Still no string/constant naming its purpose. **STILL OPEN as to role**; blocker is that role lives in the vtable slots (`PTR_LAB_100a40ec` / `PTR_LAB_100a42d4`), which are `.rdata` function pointers not present in the decompiled bodies — `VtableDump.java` on those two pointers would break it.

### (b) Which class backs the statistics provider
**RESOLVED (identity of the id pair) — one residual gap.**
The two candidates SIMUI.md flagged are **confirmed to be a CLSID/IID pair for the graph-data source**:
- `FUN_1000d52e` `[CONFIRMED @0x1000d5?? lines 106-109]`: sets `local_34=0xe41d8fee`, `local_30=0xe404e938`, then calls provider `vtable+0x1d4(&local_34, …)` — a QueryInterface/GetObject by `{CLSID 0xe41d8fee, IID 0xe404e938}`. This is the same function that emits `"Graph Data (12 months) (10 years) …"` (`s_Graph_Data__12_months__10_years__100be350`), the exact 12/10/10 resolution triple of the exporter `0x1000d7ad`.
- `FUN_1000e66c` `[CONFIRMED @0x1000e66c:232]`: `FUN_1008e933()` director `vtable+0xc(0xe404e938, 0x6856f7, &obj)` — a **GetClassObject** with `0xe404e938` as the **CLSID** and IID `0x6856f7`, then calls `obj vtable+0x2c()`. So `0xe404e938` is a live registered GZCOM class.

Verdict: the statistics/graph provider is reached through **CLSID `0xe41d8fee` / IID `0xe404e938`** (and `0xe404e938` is itself instantiable as a class with IID `0x6856f7`). **Residual gap:** the exporter `0x1000d7ad` still has **no static caller** in the export (grep confirms only its own file + `symbols.csv`), so the literal binding of *its* `param_1` to that class is inferred from the shared `"Graph Data (12 months)(10 years)"` string, not from a direct call edge — `[UNCERTAIN]` on that last hop. `VtableDump.java` on `0xe404e938`'s registered vtable (to confirm slots `+0x28/+0x34/+0x40` return the 12/10/10 arrays) would close it.

### (c) The `mode` bitfield in the modal call
**STILL OPEN.** `FUN_10058f14:71` `[CONFIRMED]`: `dialogmgr vtable+0xac(&strA, &strB, 0x30003, 1, 0)`. The value `0x30003` is confirmed present, but the field is *consumed* inside the dialog manager, which lives in **GZWIND.DLL** — not in `re/ghidra_export_simui`. Blocker: no GZWIND text export loaded here; running the headless export on GZWIND (or reading `vtable+0xac`'s target there) is required. Read-only, this cannot be decoded.

---

## 3. New findings (material, with RVAs)

- **Message/command-id table for `0x30477a4` (`0x100127fe`)** `[CONFIRMED]` — 14 `{id → handler}` map entries:

  | id | handler |
  |---|---|
  | `0x75807646` | `FUN_10012b94` |
  | `0x75807650` | `FUN_10013481` |
  | `0x7580764b` | `FUN_10012cbc` |
  | `0x75807647` | `FUN_10012e16` |
  | `0x75807649` | `FUN_10012ebc` |
  | `1` | `FUN_10012ebc` (same handler as `0x75807649`) |
  | `0x75807651` | `FUN_10012ffa` |
  | `0x75807652` | `FUN_10013129` |
  | `0x7580764e` | `FUN_1001328d` |
  | `0x7580764f` | `FUN_100133fd` |
  | `0x7580764d` | `FUN_100131ed` |
  | `0x75807648` | `FUN_10013505` |
  | `0x7580764a` | `FUN_1001360f` |
  | `0x7580764c` | `FUN_100136f7` |

  Ids `0x75807646..0x75807652` also appear in `FUN_10066989`, `FUN_10041ab1`, `FUN_1002ae96`, `FUN_1001c95c` — i.e. these command ids are dispatched/emitted across several other SIMUI screens, so this class is a shared **command router**, not screen-local.

- **Type-tag factory `FUN_1004dc89`** `[CONFIRMED @0x1004dc89:28-57]`: reads a tag at `this+0xb0` and branches — `0x287c760 → new(0xfc)` `FUN_1004bdbc`; `0x287c761 → new(0xdc)` `FUN_1004c96a`; `0x287c762 → new(0x104)` `FUN_1004d409`. The `0x2f61b00` object (`FUN_1004e123`) writes tag `0x287c760` at its `+0xb0` (`[0x2c]`), so it is the **prototype whose tag selects the 0xfc-byte sub-class**. Three-member family `0x287c760/1/2`.

- **Resource/image service pair** `[CONFIRMED @0x10013880]`: `GetService(0xc2c2eb0f, 0x22c2eb1f)` is the service `0x1001a056` uses to fetch resources `0x13` and `0x14` (via `vtable+0x80`). New cross-module edge for SIMUI's resource acquisition.

- **Global self-registration list** `[CONFIRMED @0x1008aa23]`: `FUN_1008aa23` inserts the constructed sub-object into `&DAT_100bfba0` under critical section `0x100bfb78` (`FUN_1008e4c4`/`FUN_1008e594`), seeding fields `[4]=100`, `[5]=1000`.

- **Service singletons cache block** `[CONFIRMED]`: `DAT_100bfab8` (image svc, `0x10085065`), `DAT_100bfabc` (window-mgr, `0x10085091`), `DAT_100bfacc` (`0x441e5070` svc, `0x10085179`) — three adjacent lazy-init service caches, all routed through the GZCOM director `FUN_10011556 → 0x1006a939 vtable+0x2c`.

---

## 4. Revised OPEN (replaces the doc's OPEN section wholesale)

```
## Open
- Concrete ROLE of `0x584` (default view, holds `*No View Name*` string, `[0x4c]=0xffffffff`)
  and `0x2f95d57` (468 B, `[0x73]=3000`, `[0x74]=1`, fixed 6-entry table). Structure/constants
  are mapped; role is not asserted. Blocker: purpose lives in the .rdata vtable slots
  (`0x584`: PTR_FUN_100ab14c / PTR_LAB_100aaf14; `0x2f95d57`: PTR_LAB_100a40ec / PTR_LAB_100a42d4),
  not in the decompiled bodies. Tool: VtableDump.java on those pointers.
- Statistics provider: the id pair is CONFIRMED a CLSID/IID — CLSID `0xe41d8fee` / IID `0xe404e938`
  (acquired via provider vtable+0x1d4 in `0x1000d52e`; `0xe404e938` is itself GetClassObject-able with
  IID `0x6856f7` in `0x1000e66c`). REMAINING: the exporter `0x1000d7ad` has no static caller, so the
  binding of ITS param_1 to that class rests on the shared "Graph Data (12 months)(10 years)" string,
  not a call edge. Tool: VtableDump.java on `0xe404e938`'s vtable to confirm slots +0x28/+0x34/+0x40
  return the 12/10/10 arrays.
- The `mode` bitfield `0x30003` in the modal call `0x10058f14:71` (dialogmgr vtable+0xac). Value
  confirmed; decode requires the consumer, which is in GZWIND.DLL. Tool: headless export of GZWIND
  and read of its dialogmgr vtable+0xac target.
- Meaning of GZCOM service CLSID `0x441e5070` / IID `0x54b7d5` cached by `0x10085179` — no string
  or constant names it. Tool: cross-module grep once GZWIND/other module exports exist.
```

Note on iOS oracle: I did not lean on `ghidra_export_ios` for these — every claim above is SC3U/SIMUI-side decompilation, so no `[iOS-HINT]` tags were needed. The struct offsets here (e.g. `[0x73]=3000`, tag at `+0xb0`) are SIMUI-native and would not transfer to the ARM build per the established offset-divergence rule.
