# SIMSPR.DLL — C0 cluster analysis: 25 largest functions

All 25 read in full and mechanically described. Every function reached **C2** (body read, callees identified, named). No C3/C4 claimed. Cross-references to the module map's confirmed record shapes are noted where the code consumes them.

Two opcode-string finds confirm structural pairs: the animation-script format strings at `0x10071634` (`"Script[%ld,%ld,%ld,%ld]:"`) + `0x1007158c`–`0x10071628` (`P/R/S/W/WL/WD/WR/L/CE/CB/D/DA/G/GL`) are **parsed** by `0x100030dc` and **executed** by `0x10014df9`. INI format strings `[%s]` / `%s = %s` (`0x100722d8/e4/f0`) confirm `0x10052010` is an INI writer.

## 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x10044471,view-ui,C2,sc3spr_view_register_cursors,"~60x operator_new(0x30)+FUN_10056b2a from PTR_s_*_CURSOR_cur_* under s_res_ui_shared_cursors_10072188; registers each via (piVar4+0x24)(obj,cursorID); IDs 0x43401c71,0xc16c4e1b,... ; also FUN_10047e61 (msg-subscribe) at 0x10044471:60"
0x1000961f,view-iso-draw,C2,sc3spr_view_build_drag_overlay,"walks cells between two world pts (FUN_1000a33a/a692); line-clip FUN_10050569(0,3,4)/FUN_10050635; per-cell resolves sprite (*local_14 vtable+0x58/+0xc/+0x30); builds 6-dword draw item via FUN_1000a27e, appends FUN_100105bf to vec local_68; iso shifts this+0x44/0x48/0x4c; default-layer sprites this+0x48c; finalize FUN_10010942 [UNCERTAIN which tool]"
0x10032305,sprite-entity-sim,C2,sc3spr_entity_step_scripted_state,"switch(*(**this+0xd0)+8) cases 1-10; float pos this+0x14/18/1c, vel +0xf4/f8/fc; operator_new(0xc8/0x168/0x178) sub-objects; sound via DAT_10072bc0(+0x14) ids 0x4d/0x4e/0x4f/0x4b; renderer DAT_10072b9c; _DAT_10062900 fixed-pt bias; queue pop FUN_1003b7fc(this+0xd0)"
0x1002b5e5,sprite-fx-tick,C2,sc3spr_effect_layer_tick,"per-tick: this+0x10 += param_1(dt); iterate vec this+0x38..0x3c (ptr array); advance pos piVar13+4 by vel [0x35]/[0x37]*dt*_DAT_1006406c; expire on [0x34]+[0x33]<clock; renderer DAT_10072b9c +0x50/+0x60/+0x68; RNG FUN_10050f05/f80(&DAT_10072ba8); tag this+0x44=='\x0f'"
0x100071a3,view-iso-invalidate,C2,sc3spr_view_propagate_layer_update,"grid this+0x14(w)xthis+0x18(h), rows this+0x24, cell stride 0x14, flags &0x40/&0x4000/&1; per-cell FUN_10006c67/FUN_10006efc; layer mask DAT_100624f0, DAT_100624dc; enqueues records to this+0x444 via FUN_100103a8 (type local_2c,layer local_24,seq this+0x440); zoom u16 at *(this+0x35c)+2 thresholds 0x14/0x1d/0x24/0x2d/0x2e; label 'VIEW-Iso-UpdateDirtyRects' 0x100716f4"
0x10052010,text-io,C2,sc3spr_ini_upsert_entry,"stream sub-obj this+0x28 (vtable +0x70 open,+0x10/+0x14 lock,+0x40 write,+0x18 tell,+0x1c size,+0x30 seek,+0x38 read); writes '[%s]' 0x100722f0 / '\n[%s]' 0x100722d8 / '%s = %s' 0x100722e4; parses lines skipping ';' comments and '[' sections; INI read-modify-write"
0x1000be25,view-iso-draw,C2,sc3spr_iso_build_drawlist_tiles,"CORE draw-list builder over tile rect; two aiStackY[16384] visited-lists; emits 0x2c(44)-byte records to vec this+0x500 (u16 type,+4 sprite ptr,+8.. screen xy,+0x14.. rect); consumes anchor u16 (unaff_EBX+9/10/0xb -> +0xe/0x10/0x12/0x14 *0x100); iso shifts this+0x44/48/4c, origin +0x54/58, zoom +0x28; magenta colorkey +-100 when flag&2; anim grid this+0x380(+0x38c shift); mask DAT_100624f0; submit FUN_1000c6f0"
0x10023532,sprite-fx-emit,C2,sc3spr_fx_emit_particles,"switch(*this) shapes 1/3/4/5; loop *(this+0x10) particles; float RNG FUN_10051033(0x10072920,min,max), int RNG FUN_10050f80; trig sin/cos; freelist alloc DAT_10072940 + FUN_10022ffb; template copy FUN_10023d88(this+0x14); pos this+4/8/0xc + offset, vel +0x24/28/2c; scale FUN_10023d3f; frame jitter +0xe; push FUN_1002cadb; type5 adds 10 preset-angle (_DAT_100645c0..10064600); many _DAT_1006xxxx float tunables"
0x100030dc,anim-script,C2,sc3spr_parse_anim_script,"PARSER: sscanf 'Script[%ld,%ld,%ld,%ld]:' 0x10071634 then per-line opcodes L(0xd)/CB/CE/CD/D(1)/DA(2)/G(5)/GL(0xe)/P/S(1+wait3)/R(6)/W(3)/WR(4)/WD(0xb)/WL(0xc); builds 12-byte opcode objs (operator_new(0xc), +0 type) into vec local_1c; stores to this+(idx)*0xc tables +0x42/+0x56; PAIRED with VM 0x10014df9"
0x10049a80,view-command,C2,sc3spr_view_dispatch_command,"switch(param_1) cmd ids 1-0x73; each broadcasts a GZ message (uVar2 id) via msg-server this+0x230(+0xc) building 3x FUN_100540dd(operator_new(0x28)) params, OR calls services FUN_1005a900/1005a8a5/1004fe8e/1004f6e0 with resource ids; tool/hotkey dispatch table"
0x1002fe84,sprite-entity-sim,C2,sc3spr_entity_tick_ground,"per-tick(dt); this+0xd0 state, +0xf0 clock, +0xcc/cd frame ctr/cnt; swaps frame tables this+0x128/0x12c/0x130 by state; pos this+0x10/14/18 += vel +0xe0/e8; bounds DAT_10072c54/c50; terrain DAT_10072c4c+0x48/+0x54, lookup FUN_10041226; render DAT_10072b9c+0x60; trailer this+0x120/0x124 state 5/6"
0x100289b0,sprite-entity-sim,C2,sc3spr_entity_tick_projectile,"per-tick(dt); this+0x11c clock; mode this+0xe4 (0 straight/1 decel/else seek target this+0xe8/ec/f0 via FUN_10023d3f); collision terrain DAT_10072c4c; spawns child operator_new(0xe4)/FUN_100273f1 (smoke) and 0xe0/FUN_10024f0b (impact); sound DAT_10072ba4 ids 0x425ec00b/0x525ec00b/0x625ec00b; alt cue _DAT_100729ec 0x2d490000/0x48640000"
0x10059a33,serialization,C2,sc3spr_deserialize_typed_value,"reads type tag via stream this vtable+0x38; alloc prop obj operator_new(0x28)/FUN_10053c7d; switch tags 1-0xc scalar (bool+0x18,u8+0x14,u16+0x24,u32+0x34,float+0x3c,8byte+0x5c,string) -> prop setters +0x24..+0x134; tags 0x8000-0x800b arrays (sized local_14 <<0/1/2/3); 0x800c string,0x800d vec3,0x800e vec2,0x800f 8byte; GZ variant read path"
0x10037395,sprite-entity-sim,C2,sc3spr_flock_update,"iterates list this+0x110; per-node seek/steer: node[2]=obj,[3]/[4]=refs,[5]=life,[6]=mode; vec math FUN_1003bc12(sub),FUN_10028427(len),FUN_1002c806(atan2),FUN_10023d3f(scale); tunables _DAT_10072a04/a08/a10/a14,_DAT_10071898; sin/cos heading; remove on bounds/expire FUN_1003b938 + DAT_10072b9c+0x54"
0x10047e6d,view-ui,C2,sc3spr_view_shutdown,"INVERSE of 0x10044471: RemoveNotification (FUN_1004fe8e +0x18) for ~25 msg ids; release this+0x110/0xbc/0xb8/0x228/0x22c/0xc0/0x1fc; free this+0x168; FUN_100440f4; unregister ALL ~80 cursors (piVar2+0x2c) ids 0x43401c71..0xc3655605"
0x1000d0f5,view-iso-draw,C2,sc3spr_iso_build_drawlist_screen,"draw-list builder variant over screen/anim grid this+0x380 (+0x38c shift); two aiStackY[16384]; same 0x2c records to this+0x500, same anchor-u16 consume and magenta +-100, mask DAT_100624f0; type-2 (anim sprite) + type-3 (tile) records; submit FUN_1000c6f0; (line 61 '/0' is decompiler artifact for /0x2c)"
0x1003f24e,detail-scatter,C2,sc3spr_scatter_reconcile_full,"this+0x12 enabled; rebuilds two grids this+0x90 & this+0xac from source layer this+0x40; count FUN_10040812, fill FUN_10040855, create FUN_1003e486, insert FUN_10040649; subsamples via float ratio when count>cap; region walk FUN_1003e079/e236, terrain FUN_1003d605, occupancy DAT_10072ba0+0x60; bounds cache this+0xd4..0xe0 [UNCERTAIN art category]"
0x10030970,anim-frames,C2,sc3spr_anim_load_direction_frames,"loads directional frames for index param_1 into frame sets this+0x128/0x12c/0x130/0x120/0x124; key = FUN_10031253(idx,this+0xce,base) bases -0x1b000..-0x1a700; fetch via provider DAT_10072bdc+0x38 -> rec local_8; stores sprite ptr(+0xc) to +0x24, ANCHOR u16s (+0x10/12/14/16) to +0x74/78/7c region; idx>3 doubles dims (<<1); confirms SIMSPR type-1 anchor consume"
0x1003ea15,detail-scatter,C2,sc3spr_scatter_reconcile_region,"region reconcile of detail sprites; 100x16-byte stack scratch (local_680/688); reuses off-screen items (FUN_1003cb8b transfer) for newly-visible cells; grids this+0x90/0xac; helpers FUN_10040812/40855/40649/3e486; terrain FUN_1003d605, occupancy DAT_10072ba0+0x60; same family as 0x1003f24e/0x1003db3d"
0x10031c4f,sprite-entity-sim,C2,sc3spr_entity_tick_main,"top-level per-tick(dt); this+0x100 clock; mode this+0xd0 (0 linear+arrival FUN_100321aa; else delegates to state-machine FUN_10032305); drives child list this+0xd4 (steer toward self, submit DAT_10072b9c+0x60); singleton guard DAT_10072ad0; shadow this+0x14c; frame ctr this+0xd8/d9/e0"
0x1003db3d,detail-scatter,C2,sc3spr_scatter_sync_from_layer,"rebuilds detail sprites from data layer param_1 (vtable +0xc w,+0x10 h,+0x34 sample); bitmask this+0x40(+0x10 rows); added/removed sets this+0x70 & this+0x64/0x68 via FUN_1003f89e; reconcile create FUN_1003e486/insert FUN_10040649/destroy FUN_1003c809; grids this+0x90/0xac; terrain FUN_1003d605, occupancy DAT_10072ba0+0x60"
0x10036496,sprite-entity-sim,C2,sc3spr_entity_tick_flock,"per-tick(dt) under critical section DAT_10072cc0 (FUN_10054b12 lock/FUN_10054b3b unlock); frame ctr this+0xca/cc/cd, dir this+0xd8/d4; swaps frame tables this+0x104/0x108; pos this+0x10, vel +0xec/f4; render DAT_10072b9c+0x60/+0x6c; drives flock FUN_10037395 at end"
0x100557e2,filesystem,C2,sc3spr_enum_directory_files,"FindFirstFileA/FindNextFileA/FindClose over path from this+0x8/this+0x1c; filters dir bit 0x10 and extension via FUN_10004ea0 vs PTR_DAT_10072320/24/28; pushes names to param_1 vector (FUN_10053385/FUN_10055e03); param_2 bit flags 1/2/4/8 select categories [UNCERTAIN exact extensions]"
0x10014df9,anim-script,C2,sc3spr_run_anim_script,"VM/INTERPRETER executing 0x100030dc opcodes; state this+0x10, rot/zoom idx +0x780/+0x784; script clock +0x794 += dt>>10; per-track opcode byte dispatch 1-0xe: 1/2 frame+coords, 3 timed adv, 4 rand delay(rand()%op8), 5 set ctr, 6 rand wait(rand()%op+1), 0xb/0xc loop flags, 0xd PC++, 0xe FUN_10015819; keyframe bounds test at LAB_1001525b; child tick vtable+0x44"
0x10006226,view-iso-scroll,C2,sc3spr_view_scroll_surface,"view pan(param_1=dx,param_2=dy); view rect this+0x54/58/5c/60 & +0x64..70; zoom this+0x28 (==4 rounds even); re-tessellate when scroll>=DAT_100624c8[zoom] (enqueue this+0x444, FUN_1001037c/100083bb/1000859f/100085da); blit-scroll surface this+0x74 (+0x1c/+0x120/+0x20) via vtable+0x134 for exposed strips; tess center this+0x3e0/3e4; shares view obj with 0x100071a3"
```

## 2. Notable findings (structural, high-value)

**Animation-script parser + VM pair (the `ScriptCountry` animation system).**
- **`0x100030dc` = parser.** Reads `"Script[%ld,%ld,%ld,%ld]:"` and a line-based opcode language. Confirmed opcode→type-byte map (all strings verified in `strings.csv`):

  | mnemonic | string | type byte | mnemonic | string | type byte |
  |---|---|---|---|---|---|
  | `L` | `L %ld` | `0x0d` | `WR` | `WR %ld %ld` | `0x04` |
  | `D` | `D %ld %ld %ld` | `0x01` | `WD` | `WD %ld %ld` | `0x0b` |
  | `DA` | `DA %ld %ld %ld` | `0x02` | `WL` | `WL %ld %ld` | `0x0c` |
  | `G` | `G %ld` | `0x05` | `W` | `W %ld` | `0x03` |
  | `GL` | `GL %ld` | `0x0e` | `R` | `R %ld` | `0x06` |
  | `P`/`S` | `P/S %ld %ld %ld` | `0x01`+`0x03` | `CB/CE/CD` | collision box | — |

- **`0x10014df9` = interpreter/VM** executing exactly those opcode bytes `1..0xe` per tick, keyed on rotation/zoom index (`this+0x10 +0x780/+0x784`) and script clock (`+0x794 += dt>>10`). This is the runtime that the parser feeds. **This pair is the single most valuable find in the slice.** Nearby strings `"DSprites:"`, `"Scripts:"`, `"ScriptCountry:%s"`, `":holidays"` (`0x10071654`–`0x100716b4`) tie it to the SIMSPR.md `+0x300 ScriptCountry` field.

**The two core draw-list builders (the draw-submission path).** `0x1000be25` (tile-region) and `0x1000d0f5` (screen/anim-grid region) both emit **44-byte (0x2c) draw records** into the vector at `view+0x500`, consume the **type-1 anchor u16 block** (`+0x10/+0x12/+0x14/+0x16`, scaled `*0x100`), apply the **magenta color-key ±100 adjustment** when sprite flag `&2` is set, gate on the per-zoom layer mask `DAT_100624f0`, and submit via `FUN_1000c6f0`. `0x10030970` is the **frame loader** that fills those anchor slots from provider `DAT_10072bdc(+0x38)` — a second independent witness for the type-1 record on the *consume* side.

**Per-tick "Simulate" entry points (moving-sprite entities).** A whole family sharing one entity struct (float pos `+0x10/14/18`, velocity, state `+0xd0/d4/d8`, frame counters, fixed-point bias `_DAT_10062900`, renderer `DAT_10072b9c` [+0x50 add-pt / +0x54 remove / +0x60 add-sprite / +0x68 / +0x6c], terrain `DAT_10072c4c` [+0x48 height], sound `DAT_10072ba4`/`DAT_10072bc0`, map dims `DAT_10072c54`/`DAT_10072c50`):
- `0x10031c4f` **top-level tick** (delegates to state-machine `0x10032305`, drives a child list),
- `0x10032305` **10-case scripted state machine**,
- `0x1002fe84` ground vehicle, `0x100289b0` projectile-with-impact, `0x10036496` flock (locked), `0x10037395` steering/seek sub-updater, `0x1002b5e5` effect-collection tick, `0x10023532` particle emitter.

**Message-id / command dispatch table:** `0x10049a80` — `switch(param_1)` over tool/command ids `1..0x73`, each broadcasting a distinct GZCOM message id or invoking a service. This is the view's tool/hotkey router.

**Init / shutdown pair:** `0x10044471` (register ~60 named cursors + notifications) and `0x10047e6d` (unsubscribe ~25 messages + unregister ~80 cursors, release view sub-objects) — mirror images sharing the same cursor-id set.

**Typed serializer:** `0x10059a33` — GZ variant/property **read** path with a full type-code table (scalars `1..0xc`, arrays `0x8001..0x800b`, string `0x800c`, vec3 `0x800d`, vec2 `0x800e`). This is save/load-adjacent.

**INI writer:** `0x10052010` — read-modify-write of `[section]` / `key = value` text via the stream sub-object at `view+0x28` (formats confirmed at `0x100722d8/e4/f0`).

**Detail-sprite scatter subsystem:** `0x1003f24e` / `0x1003ea15` / `0x1003db3d` — three functions managing two spatial grids (`this+0x90`, `this+0xac`) rebuilt/reconciled from a source data layer (`this+0x40`), sharing helpers `FUN_1003e486` (create), `FUN_10040649` (insert), `FUN_1003d605` (terrain test), `DAT_10072ba0(+0x60)` (occupancy).

**Tunable/table constants surfaced:** `DAT_100624f0` per-zoom layer-visibility mask; `DAT_100624dc` and `DAT_100624c8` per-zoom thresholds (scroll re-tessellation / neighbour-refresh); flock tunables `_DAT_10072a04/a08/a10/a14`; emitter float bank `_DAT_100645c0..10064630`; critical section `DAT_10072cc0`; particle freelist `DAT_10072940`; RNG state `DAT_10072ba8`/`DAT_10072920`.

## 3. Not determined / residual uncertainties

No function in the slice was left unclassified; all 25 are C2. Remaining evidence gaps (would need the noted extra witness, none producible read-only here):

- **`0x100557e2`** — the three filter extensions are `PTR_DAT_10072320/24/28`; those pointer targets are not present as literals in `strings.csv` at those addresses, so the exact extensions (likely city/sprite data suffixes) are **[UNCERTAIN]**. Needs the resolved pointer targets from `globals.csv`/data section.
- **`0x1003f24e` / `0x1003ea15` / `0x1003db3d`** — mechanics fully described, but the **art category** (street trees vs. animated network sprites vs. auto-props) is **[UNCERTAIN]**; distinguishing needs the resource-id constants passed into `FUN_1003e486`, which are supplied by callers outside the slice.
- **`0x1000961f`** — confirmed as an iso cell-walk that clips a line and emits draw items to a caller vector, but **which tool/overlay** it serves (road/power drag preview vs. query line) is **[UNCERTAIN]** without the caller.
- **`0x10032305` cases** — the 10 state indices are dispatched and each described mechanically; the **semantic name of each state** (which disaster/vehicle phase) is **[UNCERTAIN]** pending the producer that sets `*(**this+0xd0)+8`.

Cross-RE note: no iOS witness was needed — every claim above rests on SIMSPR-side decompilation, constants, and verified `strings.csv` literals.
