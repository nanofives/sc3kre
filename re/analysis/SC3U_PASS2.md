# SECOND-PASS RE — SC3U.exe (JOB 1 + JOB 2)

All facts below are read from `re/ghidra_export/functions/*.c` (SC3U text export). Image base `0x00400000`. Constants cited inline as `[CONFIRMED @ 0xADDR]`.

## DELIVER 1 — Promoted rows (CSV)

```csv
rva,subsystem,confidence,new_name,evidence
0x00402e74,S1-host,C2,sc3_app_ctor,"base ctor FUN_0045d44c; sets 7 vtables (004cf684/66c/630/59c/58c + transient 004cf6d8/6c8); stores singleton DAT_004fa86c=this; installs crash handler FUN_00401000; zero-inits app+0x3c..+0xf8, +0x168/169/16a (cheat flags), tier byte +0xe8; operator_new(0x54)->FUN_0046d0a6 at +0x4c"
0x00403019,S1-host,C2,sc3_app_dtor,"tears down members at +0x3d/+0x69/+0x6a/+0x12; crash-handler teardown FUN_00401039; if byte+0x166!=0 rebuilds argv from cmdline vtable (+0xc count,+0x3c get) and _spawnv(1,...) self-relaunch; destroys cmdline (FUN_00469229 @+0x5a) and string members"
0x00403565,S1-host,C2,sc3_app_init_services,"main service-init; copies cmdline (FUN_00468cb1); GetService 0x22b9da43/0xa2c72982 ->+0x3c; FUN_0040b6d1; sc3_ui_init_theme FUN_0040efd8; new(0x44)/FUN_00443688 ->+0x3d; new(0xf40)/FUN_0041311f ->+0x41; -sound:off/-music:off (FUN_00469755, off @0x4f4c34) -> audio vf+0x14(0x3e9,..); -intro:off -> app[0x11]->vf+0x14; registers sc3dbssprite (FUN_0040d592)/sc3imageinfo (FUN_0040d64a); returns success byte to param_1+0xe"
0x00404797,host-updater,C2,sc3_updater_query_check_results,"calls sc3_updater_load_settings FUN_00404052; reads keys UpdateName(0x4f4d34)/Settings(0x4f4d28) via FUN_00471f0d, then Check-Results(0x4f4d18) via FUN_0047152a into local_18; returns true only if both reads succeed and result!=0"
0x0040496d,S1-host,C2,sc3_app_start_singleinstance,"SetErrorMode(0x8003); creates 'SimCity 3000 Mutex' (FUN_0047ed35); if instance exists and -restart:on absent -> FindWindowExA(Gonzo/SimCity 3000)+SetForegroundWindow+ShowWindow(9); else UpdateMutexName wait loop (3x FUN_0047e203(1000000)); SetResolution vf+0xdc {0x280,0x1e0 | 800,600 by tier +0xe8}, bpp local_44=0x10; sets 'Apps\SC3U.exe'; new(0xb40)->FUN_00408a23; -sound:off -> audio vf+0x14(0)"
0x00405de7,S18-data,C2,sc3_text_scan_language_dirs,"loops i=1..0x2b (43); city/region svc FUN_0047048f vf+0x38(&buf,i) enumerates entry; builds '<entry>\\'+'SC3StringsApp.IXF' under 'Res\\Text\\' (PTR_004f4ae8/004f4aec); FUN_0047b98f file-exists; if present vf+0x14(i) selects it"
0x00408a23,S1-config,C2,sc3_config_ctor,"new(0xb40) object; vtable PTR_004cfe88 then 004cfdac/PTR_004cfd98; stores 'SC3.cfg' (PTR_004f4f1c) at +0x2c9; memset(+0x4a,-1,0x20) and memset(+0x2a,0,0x800); FUN_00484611 reads tier byte+4 -> sets +0x25/+0x26/+0x27 to (1,1,0)/(2,1,0)/(2,1,1)/(2,2,1)/(3,2,1) for <2/<3/<4/<5/>=5"
0x0040b6d1,S1-host,C2,sc3_app_register_core_factories,"via class-registry vf+0x1c registers 4 factories: 'cores'->FUN_0040c579, 'dbsegment'->FUN_0040c5cb, 'sysser'->FUN_0040c710, 'cogamecmd'->LAB_0040c75f; short-circuits on first failure; called by sc3_app_init_services"
0x0040cca0,S18-data,C2,sc3_plugin_scan_addons,"builds 'PlugIn\\' (0x4f5210) under FUN_00470463 vf+0x20 base path; dir listing FUN_0047fa0c/FUN_00480f4a('*.DAT' 0x4f51ac)/FUN_004810e4; per file reads 'addon-enabled' (0x4f5200) key; registers 'sc3dbssprite' (PTR_004cffa8) via registry vf+0x18"
0x0042054f,S14-governance,C2,sc3_game_register_commands_cheats,"via svc FUN_00484321 vf+0x2c: pre-registers 7 msg-type ids (0x82684130,0xa460ed02,0x82684131,0xa2fbe51a,0xe3865c7a,0xc3865c83,0x311fdae5) through FUN_00470247 vf+0x14; then maps 24 keyword strings->command ids (table below); calls sc3_ticker_load_newscast FUN_004229e0; sets param_1[0x54]=0; FUN_0044405e"
0x0042252d,S14-governance,C2,sc3_ticker_load_datafile,"per-file ticker loader; svc FUN_00484321 vf+0x50 base; sets file path '\\Sys\\'+name (FUN_004711f8) and archive '\\Sys\\SYS.PAK' (FUN_00486c43); iterates 'Sc3TickerData' (0x4f71cc) records via FUN_00486f55 with callback FUN_00422664"
0x004229e0,S14-governance,C2,sc3_ticker_load_newscast,"top-level ticker/newscast loader; sets '\\Sys\\SC3Newscast.INI' (0x4f720c) + '\\Sys\\SYS.PAK'; FUN_00422b36(param_1); iterates 'TickerData Files' (0x4f71f8) via FUN_00486f55 with callback sc3_ticker_load_datafile FUN_0042252d"
0x0043f1fd,S17-audio,C2,sc3_audio_open_track,"UV.dll track open; guarded by byte this+8; sets path this+0x50 (FUN_00402d6c) and FUN_0047b98f exists-check; sound desc this+0x4c; uV_Open(this+0x54,this+0x30,desc)->handle this+0x48; sets volumes this+0x18/+0x1c=100 (0x64) and desc+0x70/+0x74=100; marks this+8=1"
0x0043f834,S17-audio,C2,sc3_audio_update_track,"3-state playback FSM on this+4 (0 init/1 playing/2 stopped); state0: (vf+4) open then uV_Play_FromHandle(this+0x48)->state1, else state2; state2: if this+0x11 set, param_1 vf+0x1c(0x40)/vf+0x74/vf+0x20(0x40); default: uV_is_Playing(this+0x48), if idle ->state2"
0x004431e1,S15-ui,C2,sc3_text_truncate_to_width,"width-fit text via metrics obj param_3 (vf+0x6c measure, vf+0x78, +0x18/+0x1c on target); fallback ellipsis string resource 0x5377be31 from FUN_0047037b vf+0x8c (else literal DAT_004f7660); truncates cRZString param_1 (data+4,end+8) to fit param_2 px, appending ellipsis"
0x0045f994,S15-ui,C2,sc3_debug_window_create,"RegisterClassA('cGZDebugStreamW95' 0x4f7748, wndproc FUN_00460913) + CreateWindowExA('Gonzo Debug Window' 0x4f7734, style = (-(this+0x89!=0)&0x10000000)|0xef0000) -> param_1[0x23]; child edit window ->param_1[0x24]; SystemParametersInfoA(0x30); confirms LAUNCH_CONTROL §7b"
0x004711f8,S18-data,C2,sc3_dbfile_set_path,"setter: if owns-handle byte this+0x19 set, calls vf+0xc (close); then FUN_00402d6c(this+4,param_1) assigns filename string; used by updater + ticker loaders"
0x0048631a,S15-ui,C2,sc3_text_truncate_encoded_to_width,"like sc3_text_truncate_to_width but param_3 is an encoder/codec (vf+0x6c encode, vf+0x58 measure); ellipsis resource 0x5377be31 (FUN_0047037b vf+0x8c); rebuilds cRZString at param_1+4 to fit param_2, appending encoded ellipsis on overflow"
0x00486c43,S18-data,C2,sc3_dbfile_set_archive_path,"setter: this+0xb4=0 (reset cached handle), FUN_00402d6c(this+0x64,param_1) assigns archive path; paired with sc3_dbfile_set_path for SYS.PAK targets"
0x0049c1ec,network,C2,sc3_net_create_socket_window,"RegisterClassA('SocketWindowClass' 0x4f88d0, wndproc FUN_0049c0f5, cbWndExtra=4) if absent; CreateWindowExA('SocketWindow' 0x4f88c0, 16x16 hidden); SetWindowLongA(GWL_USERDATA) binds object; stores hwnd at obj+0x50; confirms LAUNCH_CONTROL §6 winsock window"
0x004a3f0c,S15-ui,C2,sc3_ui_init_html_window,"confirms existing name; 'HTML Window' (0x4f9468); bg color vf+0x184(0xc0,0xc0,0xc0)/vf+0x178; GetService 0x849b190a/0x449b1912 ->param_1[0xf1] (matches RESOURCE_KEYS); computes client rects +0x2b..+0x33; FUN_00495b45/FUN_004a43c1; FUN_0044211a"
0x004a7feb,S16-render,C2,sc3_ui_control_ctor,"UI control ctor; vtables PTR_004db64c then PTR_004db61c/004db60c; string members via FUN_004029d7; one-time init (DAT_004fb18c latch): graphics svc FUN_00470323 vf+0x84 palette-match caches DAT_004fb188=black(0,0,0), 004fb184=red(0xff,0,0), 004fb180=blue(0,0,0xff), 004fb17c=magenta(0xff,0,0xff), then FUN_004a89f6 (15KB) + FUN_004a7758; param_1[0x3f]=*(&DAT_004db5a8+param_1[0x43]*4), default [0x43]=3"
```

### Left at C1 (too trivial to name meaningfully — one-line vtable forwarders)

| rva | body | why C1 |
|---|---|---|
| `0x0044211a` | `(**(code**)(**(int**)(param_1+4)+0x94))(param_1)` | fully understood mechanically (tail-dispatch to owner-object slot `+0x94`, passing self) but the target slot's meaning is not determined; naming it `sc3_*_verb_noun` would be inventing a verb. Called from `sc3_ui_init_html_window` `0x004a3f0c` line 65, so param_1+4 is that window's manager. |
| `0x0044215d` | `...+0x74)(param_1)` | same — forwarder to owner slot `+0x74`. |
| `0x004422d4` | `...+0x80)()` | same — forwarder to owner slot `+0x80` (tail-call, no args); Ghidra flagged the indirect jump. |

These three are a contiguous trio of thiscall→owner forwarders on the same object shape (`this+4` = owner/manager pointer); they are the UI-control equivalent of thunks. Honest verdict: understood, not C2-nameable.

---

## DELIVER 2 — OPEN-list resolutions (JOB 2)

The two items quoted in the prompt come from `§10d (retracted)` / the "What is now open" block. **Both were already resolved later in the same file (§10e–§10h, same date 2026-08-15).** Neither is answerable from the SC3U.exe text export — both are `GZGraphicD.dll` runtime questions — and neither needs to be, because the on-disk doc already closes them. Restating precisely:

### U-022 — "the game stalls after `CreateWindowExA`/`ShowWindow`, 89 s no graphics"
**RESOLVED (harness artifact, not the game).** §10e bisection: with COM vtable patching removed, the game renders at 99.7% in every configuration (tests A–E). The stall/black state that produced U-022 was caused by **patching the apphelp-owned `IDirectDraw` vtable at `DDRAW.dll+0x7D3C0` in place** (§10.1, §10e). The "no further graphics calls" reading in §10d was circular — the instrument (COM hooks) was the disease. **U-022 should be closed.** Not derivable from SC3U.exe (the renderer is entirely in `GZGraphicD.dll`).

### "Critical unknown: does SC3000 render normally on this machine, without the injector?"
**RESOLVED — YES.** §10e test A (`-noinject`): renders, 99.7%, main menu visible. So injection was suspect, and §10e localised it to the COM vtable patch specifically. This question is answered on disk.

### Downstream of those (already tracked, for completeness of the OPEN section)
- **U-023 / U-024 windowed-mode black window — RESOLVED as ROOT CAUSE (§10f–§10h):** the windowed device (`GZGraphicD` class `0x1001F628`) creates a **plain** primary via `FUN_100199c0` (`ddsCaps=0x2200`, no flip chain) and **never allocates `this+8`** (the render target). Present path `FUN_10018dd9` flips a chainless primary → silent fail; `this+8` measured NULL at runtime (§10h `WINPRESENT` log). Verdict: SC3U's windowed presentation was never finished. Fix = re-implement the device class (engine work) or drop in a DirectDraw wrapper. Not a SC3U.exe question.
- **U-016 / U-017 / U-018 / U-020** — already resolved or reframed in §5, §10a, §10b; no SC3U.exe static work outstanding.

**Net:** there is nothing in the SC3U.exe text export that bears on the quoted OPEN items — they are all `GZGraphicD.dll` runtime, and they are already closed in the doc. The only tool that could add anything (and only to the windowed-fix engineering, not to the questions above) is a runtime vtable dump of `GZGraphicD` `this+0x44`/`this+8`, which §10h already ran.

---

## DELIVER 3 — New findings (with RVAs)

**1. Full cheat / keyword → command-id table** `[CONFIRMED @ 0x0042054f]`. `sc3_game_register_commands_cheats` maps keyword strings (verified against `strings.csv`) to 32-bit command ids via service `FUN_00484321` vf+0x2c → vf+0xc:

| keyword | string @ | command id |
|---|---|---|
| *(id-only)* `&DAT_004f71a0` | 0x4f71a0 | `0xc352e7ae` |
| `advisor` | 0x4f7198 | `0x352e7c2` |
| `moremoney` | 0x4f718c | `0x352e7cc` |
| `maxis` | 0x4f7184 | `0x8352e7d6` |
| *(unlabeled)* `DAT_004f717c` | 0x4f717c | `0x4352e7e1` |
| *(unlabeled)* `DAT_004f7174` | 0x4f7174 | `0x4352e7ed` |
| `mayor` | 0x4f716c | `0x4352e7f6` |
| `hello` | 0x4f7164 | `0xa352e800` |
| `simon says` | 0x4f7158 | `0x3546e10` |
| `simcity` | 0x4f7150 | `0xe352e809` |
| `money` | 0x4f7148 | `0xa352e814` |
| `ticker` | 0x4f7140 | `0xe352e822` |
| `electronic arts` | 0x4f7130 | `0x4352e828` |
| *(unlabeled)* `DAT_004f7128` | 0x4f7128 | `0x352e873` |
| `will wright` | 0x4f711c | `0x352e87c` |
| *(unlabeled)* `DAT_004f6590` | 0x4f6590 | `0x352e885` |
| *(unlabeled)* `DAT_004f7118` | 0x4f7118 | `0xe352e88f` |
| `easter egg` | 0x4f710c | `0x4352e897` |
| `llama` | 0x4f7104 | `0xc352e8a2` |
| `scurk` | 0x4f70fc | `0xc352e8ac` |
| *(unlabeled)* `DAT_004f70f8` | 0x4f70f8 | `0xc352e8b4` |
| `porntipsguzzardo` | 0x4f70e4 | `0x8352e8bd` |
| `broccoli` | 0x4f70d8 | `0x2352e8c7` |
| *(unlabeled)* `DAT_004f70d4` | 0x4f70d4 | `0xe37fb7b8` |

The seven ids pre-registered through `FUN_00470247` vf+0x14 (`0x82684130`, `0xa460ed02`, `0x82684131`, `0xa2fbe51a`, `0xe3865c7a`, `0xc3865c83`, `0x311fdae5`) are the message/command **types** the keyword ids resolve into. `[UNCERTAIN]` the six unlabeled `DAT_*` addresses are short strings the exporter did not carve — raw bytes needed to read them (orchestrator: `pe_read.py` at those VAs).

**2. `SC3.cfg` IS referenced** — corrects LAUNCH_CONTROL §5 ("no code xref"). `sc3_config_ctor` `0x00408a23` stores the literal `"SC3.cfg"` (via `PTR_s_SC3_cfg_004f4f1c` → string `0x004f4f20`) into the config object at `+0x2c9` `[CONFIRMED @ 0x00408a23]`. The §5 statement was that the *string* `0x004f4f20` has no direct xref; the reference is through the `.rdata` pointer `0x004f4f1c`. Whether the file is ever opened is still `[UNCERTAIN]` (this ctor only stores the name).

**3. `0x5377be31` is the ellipsis/truncation string resource** `[CONFIRMED @ 0x004431e1, 0x0048631a]`. Both text-fit helpers fetch resource id `0x5377be31` (via `FUN_0047037b` vf+0x8c) to append when a string overflows its pixel width. This is one of the 8 theme keys `sc3_ui_init_theme` (`0x0040efd8`) maps (RESOURCE_KEYS §Notable: keys `0x5301814c…0x5377be31`) — it identifies that specific key as the truncation glyph.

**4. The 15 KB dominant function `FUN_004a89f6` is UI/render, invoked from a widget ctor's one-time init** `[CONFIRMED @ 0x004a7feb]`. `sc3_ui_control_ctor` calls `FUN_004a89f6` + `FUN_004a7758` exactly once (latched by `DAT_004fb18c`), immediately after caching 4 palette color indices via graphics-service vf+0x84. This ties the #1 RE target (SUBSYSTEMS §3) to **S15/S16 UI/render**, not simulation — consistent with RESOURCE_KEYS' conclusion that the SC3U size list yields UI, not sim. The cached palette globals: `DAT_004fb188`=black, `004fb184`=red, `004fb180`=blue, `004fb17c`=magenta.

**5. Self-relaunch on shutdown** `[CONFIRMED @ 0x00403019]`. `sc3_app_dtor` conditionally re-spawns the process: if byte `this+0x166 != 0` it rebuilds argv from the cmdline object (vtable `+0xc` count, `+0x3c` get-arg), compares/edits with `DAT_004f4c1c`/`DAT_004f4c18`, and calls `_spawnv(1, path, argv)`. This is the restart mechanism paired with the `-restart:on` / relaunch logic in LAUNCH_CONTROL §3c. `[UNCERTAIN]` contents of `DAT_004f4c18`/`004f4c1c` (not in `strings.csv`; raw-byte read needed).

**6. Cross-module edge: ticker/newscast pipeline is fully mapped** `[CONFIRMED]`. `sc3_game_register_commands_cheats 0x0042054f` → `sc3_ticker_load_newscast 0x004229e0` (`\Sys\SC3Newscast.INI` + `TickerData Files`) → `sc3_ticker_load_datafile 0x0042252d` (per-file `Sc3TickerData` records, callback `FUN_00422664`) → uses shared `sc3_dbfile_set_path 0x004711f8` / `sc3_dbfile_set_archive_path 0x00486c43` (`\Sys\SYS.PAK`). This is a complete S14 read chain from command-registration into the newscast data files.

**7. Config capability-tier table** `[CONFIRMED @ 0x00408a23]`. `FUN_00484611`→byte`+4` drives `{+0x25,+0x26,+0x27}` = `(1,1,0)`/`(2,1,0)`/`(2,1,1)`/`(2,2,1)`/`(3,2,1)` for tiers `<2/<3/<4/<5/>=5`. This is the same capability-tier idea as the resolution table (`FUN_00430e6b`, LAUNCH_CONTROL §5) but a distinct 3-value tuple — likely texture/detail tiers. `[UNCERTAIN]` semantic of the three values.

---

## DELIVER 4 — Revised OPEN (replaces the doc's OPEN section)

The prompt's quoted OPEN block is stale; here is the wholesale replacement reflecting §10e–§10j:

```
OPEN (as of 2026-08-15, second pass)

CLOSED since the quoted block was written:
- U-022 (89 s stall / no graphics)        RESOLVED — harness artifact: COM vtable
                                            patching killed rendering (§10e). Game renders
                                            99.7% with -nocom. Close.
- "Does SC3000 render normally?"           RESOLVED — YES, test A -noinject (§10e).
- U-016 (-w does nothing)                  RESOLVED — Init re-forces fullscreen from a
                                            never-written global; style is always WS_POPUP (§10a).
- U-018 (color depth)                      DISSOLVED — DWM8And16BitMitigation keeps desktop
                                            at 32bpp; 16bpp request never reaches HW (§10b).
- U-023 (windowed black — cause)           RESOLVED root cause -> U-024.

STILL OPEN:
- U-024  Windowed mode presents nothing because the windowed device class (GZGraphicD
         0x1001F628) creates a plain primary (FUN_100199c0, ddsCaps=0x2200) and never
         allocates this+8 (render target measured NULL, §10h). Fix = re-implement the
         device class or use a DDraw wrapper (DDrawCompat/dgVoodoo2). Engine work, not a
         flag. Blocker: not a SC3U.exe question; needs GZGraphicD engineering.
- U-020  All runtime display claims are made inside the apphelp/DWM shim; any C3/C4 that
         rests on observed display state must record shim presence. Standing caveat.
- U-019  -sound:off / -music:off dispatched (FUN_00403565, FUN_0040496d) but never verified
         audibly. Blocker: per-process audio peak-meter or listening test.
- U-017  Effective default is 800x600 not 640x480, with no user-writable settings store on
         the test machine. Source of the 800x600 baseline unconfirmed (plugin DLL writing
         app+0xE8, or SYS.PAK/.IXF settings blob via FUN_0040586a). Blocker: instrument
         app+0xE8 writers in GZ* DLLs, or dump the FUN_0040586a settings source.
- U-015  Gonzo debug console: constructed unconditionally (get_debug_stream=1) but window
         never created/shown at startup (debug_window_create/show = 0, §10i). Show-setter
         FUN_0045fbcb reachability from in-game still unproven (vtable-dispatched).
- U-001  Resource key 0x449b1912 (type 0x849b190a, from sc3_ui_init_html_window 0x004a3f0c)
         is a non-text resource kind absent from all .IXF text segments (RESOURCE_KEYS).
         Blocker: identify the 0x849b190a resource family (likely HTML/layout asset).

NEW, opened by this pass:
- U-025  Six cheat-keyword strings at 0x4f70d4/0x4f70f8/0x4f7118/0x4f7128/0x4f7174/0x4f717c
         and 0x4f71a0 are not carved by the exporter. Blocker: raw-byte read (pe_read.py).
- U-026  Whether SC3.cfg (stored at config+0x2c9 by 0x00408a23) is ever opened/read/written,
         or only named. Blocker: xref the config object's file-IO methods (this+0x2c8 group)
         and/or a runtime CreateFileA watch.
- U-027  Meaning of the config capability-tier tuple {+0x25,+0x26,+0x27} set by 0x00408a23
         from FUN_00484611 byte+4. Blocker: find the consumers of app-config +0x25..+0x27.
```

**Notes for the merge step:** every promoted row is C2 (behaviour read + callees + name); none is C3/C4 (no runtime/second witness produced here). `sc3_debug_window_create 0x0045f994`, `sc3_net_create_socket_window 0x0049c1ec`, and `sc3_ui_init_html_window 0x004a3f0c` are static confirmations of facts LAUNCH_CONTROL/RESOURCE_KEYS already asserted, so they may already sit in `functions.csv` — reconcile rather than duplicate.
