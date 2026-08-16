## Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x1000fec5,text-edit-multiline,C2,sc3_wtextarea_dispatch_editcmd,"command/message dispatch on param_1; cases 8,0x1b,0x21-0x28,0x2d,0x2e,0x59,0x5a; edits gap-buffer at this+0xac/0xb0/0xcc/0xd0/200; selection at +0xd4/+0xd8; vtable ops at *(this+0xa4)+0xa8/0xb4/0xc0/0xfc; calls FUN_10011b9f,FUN_1001298e,FUN_10012cac,FUN_1000fa6d [CONFIRMED @ 0x1000fec5]"
0x10014572,messagebox,C2,sc3_msgbox_build_dialog,"builds message-box dialog; local_28=param_1[0x30]&0xffff selects button set 0-5; per-set calls FUN_100150aa with button ids 0x53018146..0x5301814c; dialog width table 100/0xd0/0x13c/200 keyed on button count (param_1[0x30]&0xffff <4 <6); icon param_1[0x31]; colors via +0x184 (0x7c/0x90/0xff),(0xff,0xff,0xff),(0x80,0x80,0x80) [CONFIRMED @ 0x10014572]"
0x100182a2,list-textwrap,C2,sc3_wlist_layout_wrapitems,"word-wrap/measure loop over item list at param_1[0x32]; measures with vtable +0x68/+0x70 on param_1[0x34],param_1[0x35]; line height param_1[0x39]=+0x60 call; rows param_1[0x37]=(p[0xd]-p[0xb])/height; heavy std::string temp churn (PTR_LAB_1002ab40) [CONFIRMED @ 0x100182a2]"
0x10015db7,edit-render,C2,sc3_wtextedit_paint_content,"paints text edit; reads rect p[9..0xc]; color parse via sscanf(local_48,s___02x_02x_02x_10032174,...) -> +0x184; draw glyph run via *(p[0x2e])+0x6c/+0x88/+0x90; selection fill +0x7c/+0x17c; border draw 4x +0xf0; scroll node list at p[0x2a] [CONFIRMED @ 0x10015db7]"
0x10010a19,text-edit-multiline,C2,sc3_wtextarea_paint_lines,"per-line paint loop; line index local_18<local_24; FUN_10011891/FUN_10012e62 line-extent; selection region math p[0x35]/p[0x36]; draw run via *(p[0x53])+0x8c; caret via +0xf4 with p[0x7a]; calls FUN_1001f9f4 focus check [CONFIRMED @ 0x10010a19]"
0x1000a0b8,button-draw,C2,sc3_wshape_fill_polygon,"draws filled/edged polygon; vertex list at param_1+0xb4 count +0xb0; edge flags +0xa4 bits 2/4/0x10/0x20; color via FUN_10022d54()->+0x84 (RGB from +0xa8/+0xac); scanline fill FUN_1000a7bd + FUN_1001fcb7 edge insert; line draw +0xf0 [CONFIRMED @ 0x1000a0b8]"
0x10004dde,edit-control,C2,sc3_wedit_dispatch_editcmd,"single-line edit command dispatch on param_1; cases 8(bksp),9/0x1b(tab/esc->FUN_1001fc4b),0xd,0x23,0x24,0x25,0x27,0x2e; cursor p+0xac, sel p+0xb0/0xb4, anchor +0xb8; DBCS-aware delete via FUN_10005342 (returns 1/2 byte width); repaint FUN_10004c24; calls FUN_10004d9e [CONFIRMED @ 0x10004dde]"
0x1000416b,edit-render,C2,sc3_wedit_paint_content,"single-line edit paint; measures text FUN_100045df, draws via *(p[0x37])+0x90/+0x6c; selection region p[0x2c]/p[0x2d]; fill +0x7c/+0x17c with p[0x42]/p[0x43]; calls FUN_1000463c (draw run) and FUN_100046ec (border) [CONFIRMED @ 0x1000416b]"
0x100094ab,tooltip-position,C2,sc3_whint_compute_placement,"computes hint/tooltip placement; mode this+0xf8 (1..5); anchor rects this+0xfc/0x100/0x104/0x108; flags this+0xa8 bits 1/4/0x1000/0x2000; writes pos this+0x10c/0x110/0x114; calls FUN_1000932a, FUN_10009914 [CONFIRMED @ 0x100094ab]"
0x1001d306,list-render,C2,sc3_wlist_paint_row_dbcs,"paints one list/menu text row; fills bg +0x118, draws string run *(p[0x40])+0x84 with color p[0x41]/p[0x42]; DBCS/multibyte lead-byte classification p[0x3b] cases 0xf,0x11,0x12,0x13,0x14 (ranges 0x81-0x9f,0xe0-0xfc,0xa1,0x81-0xfe,0xb0-0xc8); advances p[0x3d] by 1 or 2 bytes; calls FUN_1001d70c,FUN_1001da6f,FUN_1001db1f [CONFIRMED @ 0x1001d306]"
0x100150aa,messagebox,C2,sc3_msgbox_make_button,"message-box button factory: maps id->label; 0x53018146=s_Abort_10032148,0x53018147=s_Cancel_10032150,0x53018148=s_Ignore_10032158,0x53018149=&DAT_10032160,0x5301814a=&DAT_10032164,0x5301814b=s_Retry_10032168,0x5301814c=&DAT_10032170; localized override via FUN_10022d80()->+0x8c(id); creates button FUN_1000810d, sets colors +0x184 (0xc0,0,0)/(0,0xc0,0)/(0xc0,0xc0,0), width +0xb8=100 [CONFIRMED @ 0x100150aa]"
0x10018d1d,list-render,C2,sc3_wlist_paint_columns,"two-column list row paint; item list p[0x32]; per-item draw name run *(p[0x33])+0x88 at local_3c and value run *(p[0x34])+0x88 at local_1c; right-align variant via +0x78 width; selection fill p[0x35] with +0x7c/+0x17c; sentinel color -0x21524111 -> p[0x2c]; border 4x +0xf0 [CONFIRMED @ 0x10018d1d]"
0x1002401f,property-dispatch,C2,sc3_variant_copy_bytype,"typed value copy dispatch: reads type tag via *(param_1)+0xc; switch 0(release),1-0xc scalar getters(u8/u16/u32/2int/...) each copied into this via FUN_10024b20..FUN_10024dde; 0x7fff array via +0x14c->FUN_10024e74; 0x8000-0x800f object refs (getter *(src)+0x94..+0x138, setter *(this)+0x13c..+0x134) [CONFIRMED @ 0x1002401f]"
0x1000fb3b,text-edit-multiline,C2,sc3_wtextarea_insert_char,"inserts typed char (param_1) into multiline edit; IME/composition path this+0xe8/0xe9; DBCS lead-byte accumulation this+0xf0/0xf4 with FUN_1000f28a/ranges 0x11(<0xfc)/0x14(<200,<0xff); replaces selection via *(this+0xa4)+0xb4/0xc0/0xa8/0xa4; FUN_10013851 append, FUN_10012883 notify [CONFIRMED @ 0x1000fb3b]"
0x10001ba4,static-label,C2,sc3_wlabel_paint,"paints static label/box; mode p[0x2b]==1/2 (left/right align); bevel border 4 edges via +0xf0 with edge colors *(p+0x12a),(short)p[0x4b],*(p+0x12e),(short)p[0x4c]; fill +0x7c; draws text via FUN_10001f10/FUN_10001fd3; icon draw p[0x41]; blink counter p[0x3a] with 0x32 decrement [CONFIRMED @ 0x10001ba4]"
0x1001a420,window-titlebar,C2,sc3_wframe_layout_tabs,"lays out/draws a tab or child-button strip; iterates child list p[0x29]; per child hit-test against y=iVar2; icon draw via child[2] +0x44/+0x118; label draw via p[0x2a] +0xac/+0xb0; queries gz object 0x450ebfeb/0x61325a2d via +0x80; border 4x +0xf0 [CONFIRMED @ 0x1001a420]"
0x1001be85,window-frame,C2,sc3_wframe_render_titlebar,"builds a temp title/caption widget (FUN_10015554, size 0x104); sets text class 0x53430d99 via +0xec, style +0xf4(0x10000,1); geometry from p[5],p[8],p[7]; colors p[0x2d..0x30] (sentinel -0x21524111 skip) via +0x84/+0x88; adds child strings from list p[0x2a]; blits to parent via +0xa0/+0x4c [CONFIRMED @ 0x1001be85]"
0x1000685b,button-draw,C2,sc3_wbutton_draw_bevel,"draws raised/sunk 3D bevel via polygon fill +0x118 and gradient +0x150; state this+0xa8(1) and this+0x138(1/2) select light/dark offsets (local_8 = width, *3,*4,*5 shifts); rect this+0xe0..0xec; helpers FUN_10007599,FUN_10007572 [CONFIRMED @ 0x1000685b]"
0x10020f9a,input-message-pump,C2,sc3_input_coalesce_pump,"Win32 input pump: PeekMessageA ranges 0x100-0x108(key),0x200-0x209(mouse),0x20a(wheel); coalesces repeated key-up/downs into buffer local_1c34[1792] (stride 7 = MSG); re-emits via PostMessageA; returns count of dropped/handled msgs iVar12 [CONFIRMED @ 0x10020f9a]"
0x10025a92,cursor-loader,C2,sc3_cursor_load_bmp,"loads cursor image; if this+4==0 reads embedded 'BMP' resource (writes 'bmp' ext at buf-3), parses via FUN_10027061 stream: magic 'BM', size dword, hotspot shorts at this+0x24/0x26 clamped to bitmap w/h (+0x38/+0x3c); else LoadCursorFromFileA(this+0x10); returns HCURSOR!=0 [CONFIRMED @ 0x10025a92]"
0x1001c7dd,stl-container,C2,sc3_rbtree_erase_rebalance,"std::_Tree (map/set) erase+rebalance; node layout color@0,parent@+4,left@+8,right@+0xc; finds successor, splices, recolors, rotates via FUN_1001c75d/FUN_1001c79d; updates head/first/last (param_2/3/4) [CONFIRMED @ 0x1001c7dd]"
0x1000ae26,widget-teardown,C2,sc3_widget_release_lists,"destructor/cleanup: walks 6 intrusive lists at param_1+0x2c/0x40/0x54/0x68/0x7c/0x90 (FUN_1000ca20 snapshot, FUN_1000df54 iter, FUN_1000dc23 clear); releases each held ref via vtable +8 / +0x1c / +0x30 / +100; clears rbtree at +0xa4 via FUN_1001c126; sets +0x1c=0 [CONFIRMED @ 0x1000ae26]"
0x10006ada,button-draw,C2,sc3_wbutton_draw_frame,"draws button outer frame lines; orientation p[0x2a]==1 (horizontal) vs else; thickness iVar2=+0x1f4, local_8=+0x1f8; draws 4-5 XORed(~) edge lines via +0x180 point-transform then +0x7c; final +0x20(0x10) commit [CONFIRMED @ 0x10006ada]"
0x100046ec,edit-render,C2,sc3_wedit_draw_border,"draws edit-control border by style *(param_1+0xf4): 1=focus rect +0x94; 2=2-line sunk bevel; 3=double-inset bevel (7 edges) using colors +0xf8/+0xfc/+0x100/+0x104; all via *(param_1+0x5c)+0xf0 line draw, +0x1c/+0x20 clip [CONFIRMED @ 0x100046ec]"
0x1000c546,widget-message-dispatch,C2,sc3_widget_dispatch_event,"widget event dispatch: first forwards to child handler list at this+0x8c (each +0x18); then param_1 (event id) 1..8 routes to factory/handler methods *(this)+0x2c/0x30/0x34/0x44/0x54/0x5c and invokes returned object's op[0]; returns handled bool [CONFIRMED @ 0x1000c546]"
```

## Notable findings

**Message-box button-ID table (highest value)** — `FUN_100150aa` @ `0x100150aa` is a factory that maps a fixed block of GZ command IDs to button labels. This is a named tunable table:

| ID | Label string | RVA of string |
|----|-------------|---------------|
| `0x53018146` | "Abort" | `s_Abort_10032148` |
| `0x53018147` | "Cancel" | `s_Cancel_10032150` |
| `0x53018148` | "Ignore" | `s_Ignore_10032158` |
| `0x53018149` | `&DAT_10032160` | (label) |
| `0x5301814a` | `&DAT_10032164` | (label) |
| `0x5301814b` | "Retry" | `s_Retry_10032168` |
| `0x5301814c` | `&DAT_10032170` | (label) |

Each ID is first looked up for a localized override via `FUN_10022d80()->vtable+0x8c(id)` (a string-table service); only the hardcoded English above is used as fallback. Button colors are set via `+0x184`: `(0xC0,0,0)` red, `(0,0xC0,0)` green, `(0xC0,0xC0,0)` yellow, default gray. [CONFIRMED @ 0x100150aa]

**Message-box dialog builder** — `FUN_10014572` @ `0x10014572` consumes `param_1[0x30] & 0xffff` (0–5) as a button-set selector and calls `FUN_100150aa` with the IDs above to assemble each layout (single button → three-button Abort/Retry/Ignore). Dialog width is chosen from `{100, 0xD0, 0x13C, 200}` by button count, icon is `param_1[0x31]`. Together these two are the message-box subsystem. [CONFIRMED @ 0x10014572]

**Property/variant type dispatch** — `FUN_1002401f` @ `0x1002401f` is a type-tag `switch` (tag from `*(src)+0xc`): tags `1..0xc` copy scalar values (u8/u16/u32/two-int pairs), `0x7fff` copies an array, `0x8000..0x800f` copy 16 object-reference slots (getter `*(src)+0x94..+0x138` → setter `*(this)+0x13c..+0x134`). This is a GZ variant/property copy dispatch table. [CONFIRMED @ 0x1002401f]

**Win32 input-coalescing message pump** — `FUN_10020f9a` @ `0x10020f9a` drains keyboard (`0x100–0x108`), mouse (`0x200–0x209`) and wheel (`0x20a`) messages with `PeekMessageA`, deduplicates auto-repeat key/mouse runs into a 1792-word `MSG` buffer (stride 7), then re-posts survivors with `PostMessageA`. This is the module's raw-input entry stage feeding the widget dispatch. [CONFIRMED @ 0x10020f9a]

**Two per-widget event dispatchers** (message-id dispatch tables, as the task flagged):
- `FUN_1000c546` @ `0x1000c546`: forwards to a child-handler list (`this+0x8c`, each `+0x18`), then routes event ids `1..8` to factory/handler vtable slots. [CONFIRMED @ 0x1000c546]
- `FUN_10004dde` @ `0x10004dde` and `FUN_1000fec5` @ `0x1000fec5`: keystroke/command dispatchers for the single-line and multi-line text-edit controls respectively (cases `8,0xd,0x1b,0x21–0x28,0x2d,0x2e,0x59,0x5a`), both DBCS-aware. [CONFIRMED]

**STL red-black tree** — `FUN_1001c7dd` @ `0x1001c7dd` is `std::_Tree::erase` with full recolor/rotate (node color@0, parent@+4, left@+8, right@+0xc). Library code, not game logic, but confirms the container layout used by `FUN_1000ae26`'s `+0xa4` tree. [CONFIRMED @ 0x1001c7dd]

**No per-tick / Simulate entry point and no save/load serializer** were found in this slice — consistent with GZWinD being the windowing/widget framework, not the simulation. The closest to serialization is the cursor `.bmp` stream reader `FUN_10025a92`.

## Not determined

Nothing in the slice was left unclassified. Residual uncertainties (mechanically described but purpose-inference incomplete):

- `&DAT_10032160` / `&DAT_10032164` / `&DAT_10032170` (the three non-symbolized message-box labels at IDs `0x53018149/0x5301814a/0x5301814c`) — the decompilation shows them used as button captions but their literal text is not in the function body. **Missing evidence:** the string bytes at those RVAs (read `re/ghidra_export_gzwind/strings.csv` or the data segment; likely "No", "OK"/"Yes", "Yes"). [UNCERTAIN]
- `FUN_1001a420` @ `0x1001a420` queries a GZCOM object by class/iid `0x450ebfeb` / `0x61325a2d` — I classified it as tab/child-strip layout from the draw calls, but the identity of that queried service is **missing** (needs the class-id registry / a second xref to `0x450ebfeb`). [UNCERTAIN]
- The `iVar4`/`iVar3` orientation constants `this+0x138 == 1/2` in `FUN_1000685b` select bevel light-source offsets; the enum meaning (raised vs sunk vs flat) is inferred from the shift pattern, not named. [UNCERTAIN]

All 25 functions in the slice were read and mechanically described; every one is rated **C2**.
