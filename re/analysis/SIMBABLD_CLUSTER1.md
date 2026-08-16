## Module orientation (SIMBABLD.DLL @ base 0x12000000)

This module is the **Building Architect / BAT editor** — an interactive isometric tile-grid building editor plus its bitmap/sprite pipeline. 24 of the 25 functions in this slice belong to **one C++ class** (the editor document/view). That `this` struct is the load-bearing structure; the recurring offsets are consistent across every function:

| Offset | Meaning (mechanical) | Evidence |
|---|---|---|
| `this+0x8` | mode/type enum (FourCC-ish: `-0x3ce8d516`, `-0x7ce8d529`, `-0x7ce8d528`, `-0x3ce8d515`, `-0x3beb33a8/9`) | branched in `120251f9`, `12028239`, `12029936`, `1202a881` |
| `this+0x674` | tile-grid/layer object; `+0x8c`=cell array (0x20-byte cells, linked via `&0x1ffff`), `+0x94`=column ptr table, `+0x80`=fill id | every renderer |
| `this+0x690` | draw context (line/quad/sprite primitives) | `1202fcec`, `12031a7c` |
| `this+0x6ac` | active tool/mode (0..4) | `12035821`, `12036ae5`, `12034fe2`, `12031a7c` |
| `this+0x6c8..0x6dc` | selection box: origin(x,y,z)=`6c8/6cc/6d0`, size(w,h,d)=`6d4/6d8/6dc` | `1202fcec`, `12046aef` |
| `this+0x6f8` | zoom shift (`<< bVar`) | all renderers |
| `this+0x700/0x704/0x708` | current cursor tile (x,y,z) | `12034fe2`, `12035821` |
| `this+0x794 / 0x7af` | orientation flags: `0x10/0x20/0x40`=corners, `0x80`=single, `1/2/4`=edges | `1202fcec`, `12035821`, `12036ae5` |
| `this+0x7a3/0x7a7/0x7ab` | hovered/picked tile (x,y,z) | `1202fcec`, `12031a7c`, `12036ae5` |
| `this+0x81c / 0x820` | editor state / active sub-tool (switch keys 3..0xb) | `12035821`, `12034fe2`, `1202fcec` |

Recurring shared callees: `FUN_12038690` = tile(x,y,z)→screen(sx,sy) iso transform; `FUN_12038b00` = set cursor tile + recompute; `FUN_12034930` = mark-dirty/redraw; `FUN_12047f0a`+`FUN_1205aa12` = localized string load (string-table ids `0x63de4715`, `0x9a0884ad`); `FUN_12056614`/`FUN_1205666c` = event/service broker (event GUIDs `0x63cc69xx`); `PTR_FUN_12079078` = pixel-format writer fn-ptr (surface RGB packer); `FUN_1203c11a` = resampling kernel.

---

## 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x1202f346,bat-editor/tick,C2,sc3_bat_tick_update,"PER-TICK ENTRY: timeGetTime() @0x1202f353; elapsed clamp 1000ms; drives FUN_1202fcec/FUN_12031a1d renderers; guard this[0x19e]; dt accumulator DAT_1207a17c threshold 0x87; calls FUN_12035821/FUN_1203957f/FUN_12034930"
0x1202fcec,bat-editor/render,C2,sc3_bat_render_footprint_overlay,"orientation jumptable (&UNK_12031a11)[0..4] keyed on +0x794/+0x7af (0x10/0x20/0x40/2/4/1) and +0x81c==6||7; walks +0x674 grid via +0x94 col-table/+0x8c cells; draws via FUN_1201fa65/FUN_1201fbb0/FUN_1202005b/FUN_12020140; edge colors 0xffa4b7c1/0xff546a84/0xffd2939d etc"
0x120251f9,bat-editor/ui-dispatch,C2,sc3_bat_build_editor_dialog,"message-id chain param_2==0x83172ad7/0x83172ad8/0xc3172aea/0xc3172aeb/0xc414cc57/0xc414cc58; builds dialog controls 0x2dfdd6a..0x2dfdd80 via FUN_120275be/FUN_12026fce/FUN_12026e69/FUN_120270bf; string-table 0x63de4715/0x9a0884ad; calls thumbnail FUN_1203b71d"
0x12035821,bat-editor/tile-op,C2,sc3_bat_apply_tile_op,"switch(this+0x820) cases 3..0xb; per-tile op on drag; reads cell +0x8c[+id*0x20]; masks 0x3c000000, 0x1ff<<0x11; calls FUN_12038b00/FUN_120347ef/FUN_1200ef03/FUN_1201b11d; event GUIDs 0x63cc69ad/0x63cc69b6/0x63cc69b4"
0x12028239,bat-editor/ui-dispatch,C2,sc3_bat_cmd_commit_dialog,"param_2==0x2dfdd6a/0x2dfdd7a else (param_2+0xbd483cad==0 -> 0x42b7c353); reads name field this+0xa0, strpbrk against s_<>______12078f50; writes this+0x88/0x9c/0xb0; calls FUN_1202508d/FUN_1201891c; string ids 700/0x2ce/0x2bd/0x2cc/0x2cb"
0x12028239,,,,
0x1200975b,bat-gfx/loader,C2,sc3_bat_deserialize_bitmap_resource,"reads resource via vtable stream (0x18=u8,0x28=u16,0x38=u32,0x5c=bytes,0x54=str); format byte local_47 in {4,5,6,7,8}; width<=0x20(or0x30), height<=0x200; allocs 0x1a0190 doc; per-frame FUN_12024a13; sscanf ""%08lx"" (s__08lx_12077a54); palette names PTR_s_brick_01_tga"
0x1203f7cd,bat-editor/ui,C2,sc3_bat_build_toolset_icons,"switch on this+0xc in {-0x5bd60446..-0x5bd60443}; new FUN_12044beb widgets, sets bitmap id via vtbl 0xec (0x644bb2b1..0x644bb2c3), 0x210/0xc0(0xaa,0x10); string ids 0x17c..0x189 & 0x26..0x32"
0x12036ae5,bat-editor/drag,C2,sc3_bat_drag_paint_line,"line-walk between last(this+0x7e0/7e4) and cur; sqrt/ftol step count >> (zoom+6); per-mode (+0x6ac 0/1/2) & orientation (+0x794); calls FUN_12036ad5/FUN_120388c9/FUN_12035821/FUN_12038b00; static DAT_1207a190/94/98 last-pos, DAT_12078f98 axis-lock"
0x12029936,bat-io/serialize,C2,sc3_bat_serialize_building_manifest,"writes building def list to stream this+0xe4; ext tags PTR_s___bld/_bst/_scs (1206a608/614/620) keyed on this+8 mode; enumerates families via FUN_1205e164/FUN_1205e226; delimiter s__12078f58; calls FUN_120297cd/FUN_1202b544"
0x1203c161,bat-gfx/scale,C2,sc3_batgfx_scale_rgba_bicubic,"2-pass separable resampler; ceil/floor/ftol; kernel FUN_1203c11a; per-axis weight tables (operator_new); RGBA channel accumulate w/ clamp _DAT_1206a5d8.._1206a5dc; transparent-key skip local_6/local_3c"
0x1203d486,bat-editor/ui-dispatch,C2,sc3_bat_toolbar_cmd_dispatch,"command dispatch param_2 in 0xe4161b03..0xe4161b39, 0x75b3d3c1/bf,0x55b3d3bc,0x65b3d3bb,0x65b3d4c8,0x45c78d0a; sets radio/tool state via FUN_1203d3cc/FUN_1203d400/FUN_1203d41d; event id 0x63cc69b7/0x63cc69a6/a7; new placement objs FUN_12058d61/9b"
0x1203b71d,bat-gfx/scale,C2,sc3_batgfx_scale_paletted_bicubic,"like 1203c161 but pixel fetch via fn-ptrs local_48/local_54 chosen by src fmt iVar14 in {5,7,10} (FUN_1203cbbe/ea, FUN_1203cc13); 2-pass bicubic kernel FUN_1203c11a; returns scaled surface local_24"
0x12056e1a,bat-io/config,C2,sc3_bat_ini_upsert_section,"text config read/modify/write; scans for '[' section headers, ';' comments; formats s___s__(%s), s__s____s_(%s = %s) 12079130/12079124; stream vtbl 0x28/0x40/0x48; string builders FUN_1205659a/FUN_1205774e"
0x1204bcf7,bat-gfx/blit,C2,sc3_batgfx_blit_sprite_scaled2x,"RLE sprite blit @2x/4x; frame hdr this+4 (+6 row count, +0x10 row table 8B each: off/len/flags bit0x80,bit0x8000); writes via PTR_FUN_12079078; color scale (*px*param_3+_DAT_1206be48); transparent short==this+0x1c; clip param_5 rect"
0x1204d120,bat-gfx/blit,C2,sc3_batgfx_blit_sprite_masked,"as 1204bcf7 plus second source param_5 (shadow/alpha): pixel = (*mask * *src)>>5; two RLE sources param_2/param_3; PTR_FUN_12079078 packer; 2x/4x paths"
0x12034fe2,bat-editor/cmd,C2,sc3_bat_command_dispatch,"numeric accel/menu dispatch switch(param_1) codes 1,2,5,6,0x19..0x2a,0x30,0x32,0x34..0x37,0x3d,0x3e,0x3f,0x48,0x49,0x4b,0x57..0x5b,0x65,0x66,0x6a,0x6b,0x72,0x73,0x75; cursor moves via FUN_1203957f, rotate FUN_12038f87/FUN_12039318, save/mirror; event ids 0x63cc6993/95/96"
0x12046aef,bat-editor/geom,C2,sc3_bat_compute_gizmo_bounds,"computes 3D selection-box / resize-handle screen quad; reads this+0xe8..0xf0 (dims), +0xd0..d8, +0x11c/0x120 offsets, zoom<<0xc8; state this+0x124 in {1,2,3,4}; clamps 3..0xa8; draws 12 edges via vtbl 0xf0 colors this+0x19c/0x1a0; writes this+0x14c..0x168,0x18c,0x190"
0x1202e2fa,bat-editor/preview,C2,sc3_bat_build_preview_scene,"builds 3D preview: FUN_1202e04a scene, model tags 0x62e56a2c/2d/2e, mesh part ids 0x75c408c9..0xcd via vtbl 0x38; material 0x45ee564e/0x15ee566f/0x45b12598; string ids 400/0x191/0x192/0x193/0x1e0; camera 1000,1000"
0x12049d83,bat-gfx/blit,C2,sc3_batgfx_blit_sprite_scaled,"RLE sprite scaled blit, single source; same frame layout (+6 rows,+0x10 8B table,flag 0x80); 2x path (interleave param_4) and 4x path; PTR_FUN_12079078; transparent key this+0x1c"
0x1202a881,bat-io/import,C2,sc3_bat_import_building_entry,"reads clipboard/registry doc via cmd 0x2dfdd6f/0x2dfdd6e, iface 0x4132242b/0x21335c59; type byte cVar1 in {6,0xc,0x12..0x1e}; splits path (0x5c) into this+0x20/0x38/0x60; calls FUN_12029936 serialize; mode this+8 branch; commit FUN_1202b077(0x2dfdd6a)"
0x1204a96c,bat-gfx/blit,C2,sc3_batgfx_blit_sprite_scaled_alt,"RLE scaled sprite blit variant (transparent key read as short this+0x1c into local_28); 2x & 4x paths; frame hdr +6/+0x10; PTR_FUN_12079078 packer; flag bit 0x80 run type"
0x1203e064,bat-editor/window,C2,sc3_bat_build_main_window,"constructs editor window+toolbars; service 0x63cc69b6/b9; new FUN_120432eb/FUN_12041a16 panels; render targets 0x45b12598/0x55b2c0ec; 4 toolbars this+0x30/0x50/0x70/0x90 populated w/ cmd rows (0x75b3d3c1/0x55b3d3bc/0x65b3d3bb/0x75b3d3bf -> accel 0x19..0x24) via FUN_1203f02f"
0x12031a7c,bat-editor/render,C2,sc3_bat_render_tile_column,"renders one grid cell's linked z-stack at (param_1,param_2); cell chain +0x8c[id*0x20] via &0x1ffff, height field >>0x11&0x1ff; tool +0x6ac==3 special (rubble/demolish DAT_120794e4); direction arrows FUN_1203a77a; draw FUN_1201f718/FUN_1201f51c/FUN_1201fbb0"
0x12013d94,bat-io/props,C2,sc3_bat_enum_family_key_values,"iterates a keyed collection (FUN_1205d2dc/FUN_1205e14e); for each entry compares key vs 0x120781fc/0x120781ec (4-char), builds ""name"".DAT_120781f8 joined pairs (sep DAT_120781f4/f8); emits via FUN_12015db7/FUN_1201450e"
0x1202f346,,,,
```

(Note: `0x1202f346` and `0x12028239` appear once each — the duplicate blank rows above are stray; the authoritative single rows are the first occurrences.)

---

## 2. Notable / high-value findings

**★ PER-TICK / ANIMATION ENTRY — `sc3_bat_tick_update` @ 0x1202f346** `[CONFIRMED @ 0x1202f353]`
Calls `timeGetTime()`, stores it at `param_1[0x1f6]`, computes `dt = now - param_1[0x1f7]` clamped to `[0,1000]ms`. It is the editor's frame driver: selects a render path (`local_c` 1/2/3/5) from `param_1[0x1ab]`, blits the four viewport buffers via vtbl `+0x118`, and calls the footprint renderer `FUN_1202fcec` (`sc3_bat_render_footprint_overlay`) and stack renderer `FUN_12031a1d`. Global animation accumulator `DAT_1207a17c += dt`; when `> 0x87` (135) it advances a drag step (`FUN_1203957f` + `FUN_12034930`) and resets. This is the closest thing to a Simulate/OnIdle in the module. **This is the single highest-value structural find in the slice.**

**★ THREE message-id / command dispatch tables** (the module's command surface):
- `0x120251f9` — dialog-build dispatch on command ids `0x83172ad7/ad8`, `0xc3172aea/aeb`, `0xc414cc57/58` `[CONFIRMED @ 0x1202520a-0x120252a0]`, populating dialog controls `0x2dfdd6a … 0x2dfdd80`.
- `0x1203d486` — toolbar/tool-select dispatch, contiguous id block `0xe4161b03 … 0xe4161b39` plus `0x75b3d3c1/bf`, `0x55b3d3bc`, `0x65b3d3bb`, `0x65b3d4c8`, `0x45c78d0a` `[CONFIRMED @ 0x1203d4a0+]`.
- `0x12034fe2` — numeric accelerator/keystroke table (cursor nudges, rotate, mirror, save) with dense integer cases `[CONFIRMED @ 0x12034ff4+]`.

**★ Serialization / persistence (the export path family — the requested high-value target):**
- `0x12029936` `sc3_bat_serialize_building_manifest` — writes a building-definition manifest to stream `this+0xe4`, choosing extension tags `.bld` / `.bst` / `.scs` (`PTR_s___bld_1206a608`, `PTR_s___bst_1206a614`, `PTR_s___scs_1206a620`) by document mode `this+8` `[CONFIRMED @ 0x1202a1af/0x1202a15a]`. This is the driver that feeds the IXF writer at `0x1204f2e7` (out of slice) — it is the building-definition **save/export** assembler.
- `0x1202a881` `sc3_bat_import_building_entry` — inverse: pulls an entry (iface `0x4132242b`/`0x21335c59`, cmd ids `0x2dfdd6f`/`0x2dfdd6e`), splits its path on `\` (0x5c) into `this+0x20/0x38/0x60`, then calls the serializer.
- `0x12056e1a` `sc3_bat_ini_upsert_section` — a general INI/text-section reader-writer (`[section]` headers, `;` comments, `%s = %s` lines). A tunable/config persistence primitive.
- `0x12013d94` `sc3_bat_enum_family_key_values` — enumerates a keyed collection and emits `name.<value>` pairs, comparing 4-char keys `0x120781fc`/`0x120781ec`.

**★ Bitmap/sprite pipeline (format knowledge):**
- `0x1200975b` `sc3_bat_deserialize_bitmap_resource` — reads a bitmap resource with a **version byte in {4,5,6,7,8}** `[CONFIRMED @ 0x120097e6]`, then per-version reads: flags(u8), width(u8, capped 0x20 or 0x30), depth(u8), height(u16, capped 0x200), plus five u32 header dwords; allocates a `0x1a0190`-byte document; frames parsed 0x4c/0x20 bytes each; hex ids parsed with `"%08lx"`. This is the on-disk bitmap/FSH format decoder.
- Sprite frame layout (shared by all blitters `1204bcf7`/`1204d120`/`12049d83`/`1204a96c`): the
  block pointer is at `obj+4`, height at block `+6`, row table at block `+0x10`, 8 bytes/row.
  Transparent colour = short at `this+0x1c`. All emit through packer `PTR_FUN_12079078`.

  > ⚠️ **CORRECTED BY THE ORCHESTRATOR.** The worker described the 8-byte row record as
  > `{offset(u16), len(u16), y(u16), flags(u16)}`. That field split is **wrong**. The record is
  > `{u32 pixelOffset, u16 x, u16 flags}` — as proven in `formats/QFS.md`, where the format
  > **round-trips byte-identically over all 62,552 shipped records** (C4). The blitter agrees
  > with the C4 layout, not the worker's split `[CONFIRMED @0x1204bcf7]`:
  > ```c
  > iVar10   = *(int *)((int)this + 4);                     // the block
  > local_2c = iVar10 + 0x10 + (u16 at iVar10+6) * 8;       // data start = +0x10 + height*8
  > local_10 = (int *)(iVar10 + 0x10 + uVar13 * 8);         // row entry, stride 8
  > uVar7    = (uint)*(ushort *)((int)local_10 + 6);        // flags at row+6
  > ```
  > There is no `y` field — rows are implicit in table order — and `len` lives in the low 15 bits
  > of `flags`, not in its own u16.
  >
  > **The genuinely new finding here is that SIMBABLD consumes the SAME format.** The span-sprite
  > layout is therefore shared between the runtime sprite pipeline (SIMSPR → GZGraphicD) and the
  > BAT authoring tool — an independent second witness for `formats/QFS.md`, from a different
  > module at a different image base.
- Bicubic resamplers `0x1203c161` (RGBA) and `0x1203b71d` (paletted, format-dispatched pixel fetch) — 2-pass separable, kernel `FUN_1203c11a`, clamp bounds `_DAT_1206a5d8`/`_DAT_1206a5dc`. `0x1205b440` is a near-identical RGBA bicubic scaler that additionally does color-key masking via broker callbacks `DAT_120c366c/68`.

**Selection-box gizmo geometry:** `0x12046aef` computes the 12-edge screen quad for the 3D bounding box / resize handles, with drag state `this+0x124` in {1..4} and screen clamp `[3, 0xa8]`.

---

## 3. Not determined / caveats

- **`0x1205b440`** `[UNCERTAIN]` — the two-callback color-conversion path (`DAT_120c366c` = vtbl+0x1a4 result, `DAT_120c3668` = vtbl+0x1a0) is only mechanically clear; whether it is anti-aliased downscale vs. a palette-remap depends on what those two device callbacks do (not in slice). Classified C2 as "RGBA bicubic scaler with color-key" on the ceil/floor/kernel/clamp structure alone; its exact filtering intent is not confirmed. Missing evidence: bodies of the `+0x1a0`/`+0x1a4` device methods.
- **Sub-tool enum `this+0x820` (values 3..0xb) and `this+0x81c`** — the numeric switch keys in `12035821`/`1202fcec` are confirmed, but the human meaning of each tool index (which is "wall", "roof", "prop", etc.) is **not determined** from this slice. Missing evidence: the tool-button setup that assigns those ids (partly `1203d486`, but the id→label mapping needs the string-table entries behind `FUN_12047f0a`).
- **FourCC-style ids at `this+8`** (`-0x3ce8d516` = `0xc3172aea`, etc.) — confirmed as a mode discriminator branched everywhere, but the semantic label of each mode (new/edit/save-as/template) is inferred-only and left unnamed. Missing evidence: the constructor/`FUN_1202508d` that sets `this+8`.
- **`&UNK_12031a11`** (the jumptable base in `1202fcec`) — Ghidra flags "could not find normalized switch variable"; the 5 cases are read correctly but the raw table bytes were not dumped. Not required for the C2 description.
- No genuine per-*simulation* tick (city sim) exists here — as expected, SIMBABLD is an editor/authoring module; `1202f346` is a UI/animation tick, not a `goCitySimulator` step. No `[iOS-HINT]` cross-refs were needed or asserted (this authoring UI has no clean iOS twin).

All 25 functions were read in full and are rated **C2** (body read, callees identified, struct offsets/constants cited, named). None are claimed C3/C4.
(raw JSON: C:\Users\maria\AppData\Local\Temp\fleet-delegate-3a4e34afde1a479d9d9205437ce7d8f0.json)
