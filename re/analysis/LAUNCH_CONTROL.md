# Launch control — command line, display, audio, logging

Purpose: establish the foundation for **repeatable testing against the original**. Answers
what `SC3U.exe` already exposes for controlling resolution / fullscreen / sound / city load,
and exactly which of the desired test-harness controls do **not** exist and must be built.

Evidence tags: `[CONFIRMED @ 0xADDR]` = read from the SC3U decompilation export or from raw
bytes of the anchored `original\SC3U.exe`. `[UNCERTAIN]` = stated gap + missing evidence.
All addresses are Ghidra VAs; image base `0x00400000`, so RVA = VA − 0x400000.

---

## 0. Verdict

`SC3U.exe` **does** parse a real command line, and it already ships switches for resolution,
fullscreen/windowed, sound, music, intro, graphics device, direct city load, cheats, and
single-instance bypass. Three desired controls do **not** exist: desktop color depth
(bpp is a hardcoded literal), launch-minimized (`nCmdShow` is discarded), and per-function
logging (no general-purpose log writer exists).

**Phase 0 (§9) tested this on the real game.** `-r<W>x<H>` is confirmed live, which proves
the whole char-switch table is reached. Two corrections to the static reading came out of it:
the effective default is **800x600, not 640x480** (U-017), and **`-w` does not produce a
windowed game** despite being parsed and dispatched (U-016). The color-depth work item may be
moot on Windows 11 and must be measured before it is built (U-018). `-sound:off` is parsed
and dispatched but has **not** been verified audibly (U-019).

---

## 1. Where the command line enters

`entry` @ `0x004b4b54` — MSVC CRT boilerplate. Calls `__getmainargs`, then walks `_acmdln`
to skip argv[0] (handling the `0x22` quote case) and passes the remainder as `lpCmdLine`.
The `argc`/`argv` it obtained from `__getmainargs` are **never used afterwards**.
`[CONFIRMED @ 0x004b4b54]`

`GetStartupInfoA(&local_60)` is called here and `local_60` — which holds `wShowWindow` — is
**never read again**. `[CONFIRMED @ 0x004b4b54]` This is why launch-minimized is impossible
without intervention (see §6).

WinMain = `FUN_00402e31` @ `0x00402e31`. On the NT path (`GetVersion() < 0x80000000`) it
**re-reads the full line** via `GetCommandLineA()` and builds the command-line object:

```c
if (DVar1 < 0x80000000) { param_3 = GetCommandLineA(); }
piVar2 = FUN_00469023(local_40, param_3);   // tokenizer ctor
uVar3 = FUN_0045e68f(piVar2, uVar4);
```
`[CONFIRMED @ 0x00402e31]`

The object is stored on the framework singleton at `+0x34` by `FUN_0045d907` @ `0x0045d907`,
and retrieved everywhere else via framework vtable slot **`+0x48`**:

```c
piVar2 = (int *)thunk_FUN_0045d5ae();              // returns DAT_004fab74 (framework singleton)
piVar2 = (int *)(**(code **)(*piVar2 + 0x48))();   // -> the command-line object
```
`FUN_0045d5ae` @ `0x0045d5ae` is literally `return DAT_004fab74;` (6 bytes).
Framework singleton constructed in `FUN_0045e6b2` @ `0x0045e6b2` via `FUN_004610b5`
(`operator_new(0x104)`) + `FUN_004610fd`, vtable `PTR_LAB_004d6bf4`. `[CONFIRMED]`

---

## 2. The tokenizer and lookup class

Class is `cRZCmdLine`-shaped, primary vtable at `0x004d7750`, secondary at `0x004d7790`,
`QueryInterface` @ `0x00469e20` accepting **IID `0xA31E539C`** and `GZIID_cIGZUnknown = 1`.
`[CONFIRMED @ 0x00469e20]`

`FUN_00469023` @ `0x00469023` splits the raw line on space / tab / newline honoring `"`
quoting, strips surrounding quotes per token, and pushes each into a vector at `this+0x08`
(element stride `0x14`). Raw line kept at `this+0x18`. `[CONFIRMED @ 0x00469023]`

| vtable slot | RVA | signature / role |
|---|---|---|
| `+0x0c` | `0x004692f4` | arg count: `(*(p+0xc) - *(p+8)) / 0x14` |
| `+0x14` | `0x00469301` | exact token match → index, else `0xFFFFFFFF` |
| `+0x18` | `0x0046941b` | prefix/compare match → index |
| **`+0x1c`** | **`0x00469755`** | **named switch**: `(this, cIGZString* name, cIGZString* out, char bStripQuotes)` |
| **`+0x20`** | **`0x00469568`** | **char switch**: `(this, char c, cIGZString* out, char bStripQuotes)` |
| `+0x28` | `0x004699cb` | find index by switch char, from start index |
| `+0x2c` | `0x00469c9b` | insert argument at index |
| `+0x30` | `0x00469d7d` | remove argument at index |

Both lookups scan **only the tokenized process command line** — not the registry, not an
INI, not a property map. `[CONFIRMED @ 0x00469568, 0x00469755]`

### 2a. Syntax rules `[CONFIRMED]`

**Accepted prefix characters** are a set held at `DAT_004f79d0`. The export left this
undefined; raw bytes from the anchored binary are `2f 2d 5c 00` = **`"/-\"`**.
So `-r`, `/r` and `\r` are all accepted. `[CONFIRMED @ 0x004f79d0]`

**Char switches — value is glued on, no separator, no following token.** From
`FUN_00469568`: if token length is exactly 2 the switch matches with an empty value and
still returns true; otherwise the value is `token.substr(2)`, with surrounding `"` stripped
when `bStripQuotes` (always passed as `1` at every call site).
→ `-r1024x768`, `-d3dfx`, `-p"200 128 6 5"`. **Never** `-r 1024x768`. `[CONFIRMED @ 0x00469568]`

Switch char matching is case-insensitive (both upper→lower and lower→upper branches present,
digits `'0'..'9'` handled too). `[CONFIRMED @ 0x00469568]`

**Named switches require exactly `:`.** From `FUN_00469755`: `token[0]` ∈ prefix set,
`token[1..1+len(name)]` == lowercase(name) (via `FUN_00468748` = in-place `_strlwr`), and
`token[1+len(name)] == ':'`. Value = `substr(namelen+2)`, with `'` **or** `"` stripped from
both ends. **`=` is never accepted.** → `-sound:off`, `-station:'name'`.
`[CONFIRMED @ 0x00469755]`

`FUN_004686d5` @ `0x004686d5` is a first-N-bytes prefix compare used to test values.
The comparison target at `0x004f4c34` was undefined in the export; raw bytes are
`6f 66 66 00` = **`"off"`**. The PTR pair `0x004f4ea0`/`0x004f4ea4` resolve to
**`"on"`** (`0x004f4ec0`) and **`"off"`** (`0x004f4c34`). `[CONFIRMED @ 0x004f4c34]`

---

## 3. Complete switch inventory

### 3a. Char switches (slot `+0x20`) — all call sites are in `FUN_004077b5` @ `0x004077b5`

| Switch | Call site | Effect |
|---|---|---|
| `-r<W>x<H>` | `0x004077b5` +49 | `sscanf(value, "%ux%u")` (fmt @ `0x004f4f0c`) → gfx `vf+0xDC({w,h,0x10})`; also `app->[0x30]->vf[0x68](&w,&h)` |
| `-d<name>` | `0x004077b5` +58 | value truncated to 31 chars → gfx `vf+0xEC(name)` (device/driver) |
| `-f` | `0x004077b5` +69 | gfx `vf+0xE4(0)` = fullscreen. **Presence-only**, value discarded |
| `-w` | `0x004077b5` +73 | gfx `vf+0xE4(1)` = windowed. Presence-only |
| `-l<value>` | `0x004077b5` +77 | → svc `0x441E5070` `vf+0x44`/`vf+0x48` lookup, `vf+0x28`/`vf+0x24`, then `FUN_004845fe()->vf+0x78` |
| `-c<value>` | `0x004077b5` +94 | → svc `0x441E5070` `vf+0x8C`/`vf+0x90`, `vf+0x80`, `FUN_004845fe()->vf+0x80`, `vf+0x70` |
| `-x<value>` | `0x004077b5` +111 | value fetched, **return discarded** — no effect in this function |
| `-p<a b c d>` | `0x004077b5` +123 | `sscanf(value, "%u %u %u %u")` (fmt @ `0x004f4ef8`), clamped (100..1000, ≥0x10, 5..10, ≥4) → `app+0xfc/0xfe/0x100/0x101` |

No other `+0x20` call site exists in the binary. `[CONFIRMED]`

### 3b. Named switches (slot `+0x1c`)

| Switch | Call site | Effect |
|---|---|---|
| `-restart:on` | `0x004077b5` +47 | if present, the `-r`/`-d` block is **skipped** |
| `-restart:on` | `0x0040496d` +105 | → `app[400]->vf[4]()`, and **skips the `FindWindowExA` single-instance check** |
| `-sound:off` | `0x0040496d` +241 | audio svc `0x23CECBA0` → `vf+0x14(0)` = Enable(false) |
| `-sound:off` | `0x00403565` +130 | direct `FUN_00469755` → `vf+0x14(0x3e9,0,0,0,0)` |
| `-music:off` | `0x00403565` +138 | direct call; otherwise sets music path via svc `0x2073215D` `vf+0x1c()` |
| `-intro:off` | `0x00403565` +175 | if absent **or** value ≠ `"off"` → `app[0x11]->vf[0x14]()` plays the intro |
| `-cheats:<x>` | `0x004077b5` +118 | `app->[0x110]->vf[0x3c](0, value)`; sets `*(app+0x168) = 1` |
| `-station:<name>` | `0x00408052` +96 | if value length > 3 → radio `vf+0x2c(value)` |
| `-radio:on\|off` | `0x00408052` +106 | `"off"` → `vf+0x58()`; `"on"` → `vf+0x54()` |
| `-UpdaterApp:<path>` | `0x00404052`, `0x00404189` | launches `Updater.exe` with the `-Mode:` / `-UpdateRegistration*` args |

Name literals: `"restart"` `0x004f4d50`, `"sound"` `0x004f4c38`, `"music"` `0x004f4c2c`,
`"intro"` `0x004f4c24`, `"cheats"` `0x004f4f04`, `"station"` `0x004f4ec4`,
`"radio"` `0x004f4ecc`, `"UpdaterApp"` `0x004f4c40`. All `[CONFIRMED]` from raw bytes.

### 3c. Other consumers of the same object

| What | RVA | Detail |
|---|---|---|
| `-Install` | `0x0045d907` | `vf+0x14(&"-Install", 1)` exact-token find; sets `*(framework+0x31)`. Consumed at `0x0045e6b2`, which runs an install path and **exits** instead of entering the game loop. Literal @ `0x004f76c4` |
| relaunch | `0x00406173` | loops `vf+0x28('r',0)` → `vf+0x30(idx)` removing every `-r*`, then `vf+0x2c(" -restart:on", argc-1)`. Literal @ `0x004f4e00` |
| plugin scan | `0x00405092` +85 | copies the cmdline (`FUN_00468cb1`), gets arg count, iterates all args |

### 3d. Reachability of `FUN_004077b5` — **RESOLVED empirically 2026-08-15**

**`FUN_004077b5` IS invoked at startup. The char switches are live.** Proof by controlled
experiment (§9.1): with no `-r`, the display mode goes to 800x600; with `-r640x480`, it goes
to 640x480. A switch that changes observable behaviour is a switch that is read.

Historical note on why this was ever in doubt:

`grep` over all 9,727 decompiled bodies + `globals.csv` + `symbols.csv` returns **zero**
references to `0x004077b5` other than its own definition. This is **not** evidence of dead
code: `FUN_0040496d` and `FUN_00403565`, which are definitely live startup code, likewise
have zero textual callers because they are vtable-dispatched.

Established: `FUN_004077b5` is a `__thiscall` method of the app class whose ctor is
`FUN_00402e74` @ `0x00402e74` — it touches `this+0x30`, `+0xfc/0xfe/0x100/0x101`, `+0x110`,
`+0x168`, all initialized in that ctor.

The vtable contents at `0x004cf684` / `0x004cf66c` / `0x004cf630` / `0x004cf59c` /
`0x004cf58c` (app), `0x004d6bf4+0x48` (framework) and `0x004d7750` (cmdline) are still not
dumped by our export — that gap is real (§11) and is why static reachability was
undecidable. It no longer blocks this subsystem.

---

## 4. Where the renderer and audio actually live

`SC3U.exe` is a **GZCOM framework host**. Its entire Win32 graphics import surface is 7 GDI
calls, all font/text related, plus `timeGetTime` from WINMM. There is **no** `DirectDrawCreate`,
`SetDisplayMode`, `CreateDIBSection`, `StretchDIBits`, `BitBlt`, `DirectSoundCreate`,
`waveOut*` or `midiOut*` anywhere in the binary. `[CONFIRMED]`

The only `GetDeviceCaps` call is `FUN_0045fb17` @ `0x0045fb17` with index `0x5a` =
**LOGPIXELSY**, for DPI font scaling — *not* BITSPIXEL. `[CONFIRMED @ 0x0045fb17]`

Import evidence from the shipped plugin DLLs (`Apps\`):

| DLL | Decisive imports |
|---|---|
| `GZGraphicD.dll` | **`DirectDrawCreate`, `DirectDrawEnumerateA`**, `CreateWindowExA`, `ShowWindow`, `SetWindowPos`, `AdjustWindowRect`, `GetSystemMetrics`, `CreatePalette`, `RealizePalette`, `SelectPalette`, `GetSystemPaletteEntries`, `GetDeviceCaps`, `ShowCursor` |
| `GZSOUNDD.DLL` | `DSOUND.dll` #1/#2 (by ordinal), 13 × `mmio*` / `time*` |
| `UV.DLL` | `DirectSoundCreate`, `mmio*` |
| `GZWIND.DLL` | message pump: `PeekMessageA`, `DispatchMessageA`, cursor/key state |

**Implication for the harness:** the controls we must build belong at the *import* level of
`GZGraphicD.dll`, not as RVA patches in `SC3U.exe`. IAT hooking there is independent of our
RVA map and survives changes to it.

### 4a. GZCOM service IDs used by the startup path `[CONFIRMED]`

| Service | Accessor | CLSID | IID |
|---|---|---|---|
| Graphics | `FUN_00470323` → `FUN_0047060d` | `0xC416025C` | `0x0073283C` |
| Audio | `FUN_004703d3` → `FUN_0047070f` | `0x23CECBA0` | `0x106077D2` |
| City/region | `FUN_0047048f` → `FUN_00470867` | `0x441E5070` | `0x0054B7D5` |
| Music/path | `FUN_00470463` → `FUN_00470811` | `0x2073215D` | `0xE0203660` |
| Debug stream | `FUN_00405f1f` | `0xC07320D3` | `0xC51B11CB` |

Graphics service vtable slots in use: `+0xDC` SetResolution(w,h,bpp), `+0xE0`, `+0xE4`
fullscreen flag (0 = full, 1 = windowed), `+0xEC` device name.

---

## 5. Resolution and color depth defaults

**Startup default is 640x480 @ 16bpp.** `FUN_0040496d` @ `0x0040496d`:

```c
if (*(char *)(param_1 + 0xe8) < '\x04') { local_4c = 0x280; local_48 = 0x1e0; }  // 640x480
else                                    { local_4c = 800;   local_48 = 600;   }
local_44 = 0x10;                                   // bpp
(**(code **)(iVar3 + 0xdc))(&local_4c);            // gfx->SetResolution
```

The tier byte at `app+0xE8` is set to `0` in the ctor `FUN_00402e74` @ `0x00402e74` and
**no write to it exists anywhere in the binary** — so within this binary `0 < 4` always holds.
`[CONFIRMED @ 0x0040496d, 0x00402e74]`

> **Empirically falsified as the effective default (2026-08-15).** With no switches the game
> actually comes up at **800x600**, not 640x480 (§9.1), and no registry key or settings file
> exists on the test machine to supply it. Therefore either a plugin DLL writes `app+0xE8`,
> or the `FUN_0040586a` settings blob is sourced from `SYS.PAK`/`.IXF` data rather than a
> user-writable store. Tracked as **U-017**. The static reading of this branch is correct;
> the inference "shipped default = 640x480" was not.

**bpp is a hardcoded `0x10` at all three `SetResolution` call sites** — `0x0040496d` +208,
`0x0040586a` +209, `0x004077b5` +56. No 8/24/32 bpp path exists in this binary.
`[CONFIRMED]` This is why "same color depth as desktop" cannot be reached by a switch.

Persisted settings path: `FUN_0040586a` @ `0x0040586a` reads a settings blob `{w, h, byte,
byte, ...}` via `vf+0x28`, applies w/h from it but **still forces bpp = `0x10`**.

Mode enumeration table: `FUN_00430e6b` @ `0x00430e6b` builds the selectable list into
`DAT_004fa958`, tiered by a capability value (default `0x280` when the caps object is null):

| Tier | Offered modes |
|---|---|
| `< 0x2bd` | 320x240, 480x360, 512x384 |
| `< 0x3e9` | 480x360, 512x384, 640x480 |
| `< 0x4b1` | 480x360, 640x480, 800x600 |
| `≥ 0x4b1` | 640x480, 800x600, 1024x768 |

Registry reads at startup exist (`FUN_0040586a` +65, +92) but are **language/country only**:
`HKLM\Software\Electronic Arts\Maxis\SimCity 3000 Unlimited\Language` (`0x004f4dac`) and
`...\Country` (`0x004f4d58`). No display or audio setting is read from the registry.
`GetPrivateProfileString` and family are **absent** from the binary; `SC3.cfg` (`0x004f4f20`)
has **no code xref** in the export. `[CONFIRMED]`

---

## 6. Window creation and nCmdShow

The **main game window is not created in `SC3U.exe`** (it is created in `GZGraphicD.dll`).
All three `CreateWindowExA` sites in the EXE are: the debug window frame (`0x0045f9b4`),
its child edit control (`0x0045f9f0`), and a winsock message window (`0x0049c1ec`).
`WS_POPUP` appears at none of them. `[CONFIRMED]`

All three `ShowWindow` sites use **constants, never a forwarded `nCmdShow`**:

| RVA | Function | Value |
|---|---|---|
| `0x00404a4b` | in `FUN_0040496d`, already-running-instance handoff | `SW_RESTORE (9)`, after `FindWindowExA(0,0,"Gonzo","SimCity 3000")` + `SetForegroundWindow` |
| `0x0045fbcb` | show debug window | `SW_SHOW (5)` |
| `0x0045fbff` | hide debug window | `SW_HIDE (0)` |

`SW_MINIMIZE (6)` / `SW_SHOWMINNOACTIVE (7)`: **NOT FOUND**. Combined with `nCmdShow` being
discarded at `entry` (§1), **launch-minimized is impossible without intervention.**

---

## 7. Logging surfaces already in the binary

### 7a. Crash logger — always armed `[CONFIRMED]`

A Pietrek-style CrashHandler compiled in verbatim. Installed **unconditionally, straight-line**
from the app ctor `FUN_00402e74` +65 → `FUN_00401000` @ `0x00401000`; torn down at
`FUN_00403019` +100.

- `FUN_0040105b` @ `0x0040105b`: `SetUnhandledExceptionFilter(&LAB_004010c6)`, then
  `GetModuleFileNameA`, strip after last `.`, `strcat("_stkdmp.txt")` (literal @ `0x004f4260`).
  → **`SC3U_stkdmp.txt`** next to the exe. Path buffer `DAT_004fa4e8`, handle `DAT_004fa4e0`.
- `FUN_00401707` @ `0x00401707`: core log printf — `wvsprintfA(buf1024, fmt, va)` + `WriteFile`.
- `FUN_0040111a` @ `0x0040111a`: exception code, thread id, timestamp, fault address, **all registers**.
- `FUN_004015a5` @ `0x004015a5`: `StackWalk` + `SymGetSymFromAddr` call stack;
  `FUN_0040149a` @ `0x0040149a`: manual EBP-chain walk fallback; `FUN_00401746` binds IMAGEHLP.

**Free crash triage for every test run.** The `CreateFileA` that fills `DAT_004fa4e0` lives
inside `LAB_004010c6`, which Ghidra did not carve into a function — `[UNCERTAIN]`, not
verifiable from the text export.

### 7b. The "Gonzo Debug Window" — a full interactive console, shipped but hidden `[CONFIRMED]`

Constructed **unconditionally** by `FUN_00405f1f` @ `0x00405f1f` (tries `GetService(0xC07320D3,
0xC51B11CB)`; if absent, `operator_new(200)` + ctor `FUN_0045f79d`). There is no `if(g_debug)` guard.

Created by `FUN_0045f994` @ `0x0045f994`: `RegisterClassA("cGZDebugStreamW95")` (`0x004f7748`),
`CreateWindowExA(..., "Gonzo Debug Window" @ 0x004f7734, style)` where the style is

```c
-(uint)(*(char *)((int)param_1 + 0x89) != '\0') & 0x10000000 | 0xef0000
```

i.e. `WS_VISIBLE (0x10000000)` is OR-ed in **only if the byte at `this+0x89` is nonzero**, and
the ctor `FUN_0045f79d` @ `0x0045f79d` zeroes both `this+0x88` and `this+0x89`.
→ **the window is created hidden, not absent.**

- Singleton pointer: **`DAT_004fabd0`** (set in ctor, cleared in dtor `FUN_0045f92c`).
- `hInstance` global: `DAT_004fabd4` = `GetModuleHandleA(NULL)`, written at `FUN_004610fd` +25.
- Show: `FUN_0045fbcb` @ `0x0045fbcb` — sets `+0x88 = 1`, `+0x89 = 1`, `ShowWindow(SW_SHOW)`,
  emits `"Debug Window Shown.\n"` (`0x004f775c`).
- Hide: `FUN_0045fbff` @ `0x0045fbff` — both bytes 0, `ShowWindow(SW_HIDE)`, `"Debug Window Hidden.\n"` (`0x004f7774`).
- Text sink: vtable call `(**(code **)(*(int *)(this + 0x18) + 0x10))(msg)`.

It is a **command console**, not just a log pane: window proc `FUN_00460913` @ `0x00460913`
handles `WM_COMMAND`/notify `0x300` → `FUN_0046036f` @ `0x0046036f`, which reads the edit text
(`WM_GETTEXT`) and linear-searches a registered command vector at `this[0x1f]..this[0x20]`.
Help listing `FUN_00489a1f` @ `0x00489a1f` prints `"Current Commands:\n"` (`0x004f80d8`) and
`"%s - usage: %s"` (`0x004f80c8`) per entry. Registration helper `FUN_0045f829` @ `0x0045f829`.

`[UNCERTAIN]` — whether the show setter is reachable *from inside the game*. `FUN_0045fbcb`,
`FUN_0045fbff` and `FUN_0045f994` have **zero direct callers** in the export; they are
vtable-dispatched and the vtable data (`PTR_LAB_004d6b6c`, `004d6b54`, `004d6b28`, `004d6b10`,
`004d6a90`, `004d6a8c`, assigned in `FUN_0045f79d`) is not dumped by our text export.
No `RegisterHotKey` and no accelerator table exist. Irrelevant if we call the setter
ourselves from an injector.

### 7c. No general-purpose logger `[CONFIRMED]`

`fopen` / `fprintf`: **NOT FOUND**. `CreateFileA` appears only in generic file wrappers
`FUN_0047b437` and `FUN_0047b928`, with no `.log`/`.txt` literal at either site.
`OutputDebugStringA` has exactly 2 call sites, both in exception funclets of the console
command dispatcher (`Catch@0x0046065f`, `Catch@0x004607b5`).

Formatting helpers available for reuse: `FUN_00468809` @ `0x00468809` (`cRZString::Sprintf`),
`FUN_00468b7a` @ `0x00468b7a` (`_vsnprintf` 0x8000 → cRZString), plus duplicates at
`0x0048b780`, `0x004b8c12`, `0x004bc3a8`.

### 7d. Stripped trace macros `[CONFIRMED]`

The assert macro survives with **all call sites stripped**: `FUN_004838b5` @ `0x004838b5` —
`_snprintf(buf, 200, "Module: %s\nLine: %d")` (`0x004f7fa8`) + `MessageBoxA(0, buf,
"Exception about to be thrown, accept?" @ 0x004f7f80, 0x34)`. **Zero callers.**

Same pattern elsewhere: `FUN_0048a575` @ `0x0048a575` formats
`"Failed to load the requested dll '%s'\n"` (`0x004f8124`) into a 512-byte stack buffer and
**discards it** (`uVar3 & 0xffffff00`, buffer never used). Hexdump `FUN_0047937b` @ `0x0047937b`
(`"\nHEXDUMP:\n"` @ `0x004f7bd8`) has no callers.

Orphan literals with no xref — the signature of an inlined trace macro whose emit call was
removed, and a useful list of what the engine *used* to report:
`"cGZFrameWorkW95::AbortiveQuit(): Calling _exit().\n"` (`0x004f7860`),
`"cGZDBSegmentIndexedFile::DoOpenRecord(): Record not found: %d\n"` (`0x004f7990`),
`"OccManAnim::InsertOccupant: Failed. Occupant already in container.\n"` (`0x004f7254`),
`"OccManAnim::MoveOccupant: Failed. Occupant not found.\n"` (×2, `0x004f7298`, `0x004f72d0`),
`"OccManAnim::RefreshOccupant: Failed. Occupant not found.\n"` (×2, `0x004f7308`, `0x004f7344`),
`"OccManAnim::IsOccupantVisible: Failed. Occupant not found.\n"` (×3, `0x004f7380`, `0x004f73bc`, `0x004f73f8`).

Note: `"Debug Version"` @ `0x004f7cc4` is **not** a build flag — it is a version-resource field
name queried by `FUN_0047a858` via `VerQueryValueA`. `"TRACE"` @ `0x004f8638` is an **IRC verb**
(neighbours: `WHOIS`, `SQUIT`, `REHASH`, `WALLOPS`), not a trace macro.

---

## 8. Harness requirements vs. what exists

| Requirement | Status | Mechanism |
|---|---|---|
| Select output resolution | **ships, verified** | `-r640x480` (glued, no space) — §9.1 |
| Launch fullscreen | **ships (default)** | fullscreen is what you get |
| Launch without sound | **ships, not yet verified audibly** | `-sound:off`, `-music:off`, `-intro:off` — U-019 |
| Same color depth as desktop | **NO WORK NEEDED** | the `DWM8And16BitMitigation` shim already keeps the real desktop at 32bpp; the game's hardcoded 16 never reaches hardware — §10b, U-018 |
| Windowed (no mode change) | **NOT ACHIEVABLE by patching** | window + desktop-mode preservation work, but the windowed device **never allocates a render target** (`this+8 == NULL`) — §10h, U-024. Use a DirectDraw wrapper if needed |
| **Launch minimized** | **WORKING** | `sc3launch -minimized` — `ShowWindow` IAT hook forces `SW_SHOWMINNOACTIVE`; verified `IsIconic == True` — §10i |
| **Per-function logging** | **WORKING** | `sc3launch -fnlog re\harness\trace.txt` — data-driven runtime detours, 19/33 of the starter table instrumented — §10i |

Bonus controls useful for a test harness, all already shipping:

- `-restart:on` — bypasses the `FindWindowExA` single-instance check → concurrent instances
- `-l<value>` / `-c<value>` — load a city/region directly at launch → reproducible fixtures
- `-cheats:<x>`, `-d<device>`, `-p<a b c d>`

**Design consequence:** the two display gaps live in `GZGraphicD.dll`, so the harness should
be a **launcher + injected DLL**, hooking at the IAT level. `original\SC3U.exe` is never
modified, the SHA-256 anchor stays valid, and every RVA in `functions.csv` stays authoritative.

---

## 9. Phase 0 — empirical verification (2026-08-15)

Method: launch `Apps\SC3U.exe` with cwd `Apps\`, enumerate the process's top-level windows
(class, title, style, rect, visible/iconic), sample the primary display mode while running,
list loaded graphics/audio modules, then kill. Host desktop: 2048x1152 @ 32bpp, Windows 11.

Loaded modules confirmed on every run — `GZGraphicD.dll`, `DDRAW.dll`, `GZSOUNDD.DLL`,
`UV.dll`, `DSOUND.dll`, `GZWIND.DLL` — corroborating §4: the renderer is DirectDraw inside
`GZGraphicD.dll`, and `SC3U.exe` itself imports none of it.

### 9.1 `-r<W>x<H>` is live `[CONFIRMED]`

| Run | Args | Resulting primary display |
|---|---|---|
| 1 | `-w -r800x600 -sound:off -intro:off` | 800x600 |
| 2 | `-w -sound:off -intro:off` (no `-r`) | 800x600 |
| 3 | `-r640x480 -sound:off -intro:off` | **640x480** |

Run 1 alone proves nothing — it matches the no-switch baseline established by run 2. Run 3
is the decisive one: a value different from the baseline is honoured. **Therefore
`FUN_004077b5` executes at startup and the char-switch table of §3a is live.** Closes U-013.

The display mode is restored correctly to 2048x1152 @ 32bpp when the process is killed, so
the mode change does not persist past a crashed test run. Relevant to harness ergonomics.

### 9.2 `-w` did not produce a window `[CONFIRMED observation, cause UNCERTAIN]`

In runs 1 and 2 the game's top-level window was:

```
Class: Gonzo   Title: (empty)   Rect: 2048x1152   Client: 2048x1152
Style: 0x94000000 = WS_POPUP | WS_VISIBLE | WS_CLIPSIBLINGS
Visible: True   Minimized: False
```

i.e. a borderless popup at full desktop size, together with a display-mode change — the
signature of DirectDraw exclusive fullscreen, not windowed output. Window class `Gonzo`
matches the `FindWindowExA(0,0,"Gonzo","SimCity 3000")` single-instance probe at `0x00404a4b`.

`-w` is parsed (§3a) and calls gfx `vf+0xE4(1)`, so the switch reaches the graphics service.
Why the service does not honour it is **[UNCERTAIN]** — candidate causes, none yet tested:
`FUN_0040586a` re-applying a persisted fullscreen flag via `vf+0xE4` *after* `FUN_004077b5`;
or windowed output being unimplemented in this `GZGraphicD.dll` build. Tracked as **U-016**.
Resolving it needs `GZGraphicD.dll` imported into Ghidra, which has not been done.

### 9.3 No user-writable settings store exists `[CONFIRMED]`

After three runs: **zero** keys under `HKLM`/`HKCU` `...\Electronic Arts` (checked both
native and `WOW6432Node` views), and **no file in `Apps\` modified**. `Apps\SC3.cfg` is
untouched, consistent with §5's finding that its string `0x004f4f20` has no code xref.

Consequence: the 800x600 baseline is produced by code or by read-only packaged data, not by
saved user preferences — see the falsification note in §5 and **U-017**.

### 9.4 Color depth — the requirement may be moot on Windows 11 `[UNCERTAIN]`

The primary display reported **32bpp in all three runs**, including run 3, while §5 shows the
game requesting `bpp = 0x10` (16) at every `SetResolution` site. On WDDM the 16bpp request is
virtualized rather than applied to the desktop.

**Not yet established** whether the game's own back buffer is 16bpp (with the compositor
converting) or whether the request is ignored end-to-end. `Screen.BitsPerPixel` is a weak
witness. Settle it by hooking `IDirectDraw::SetDisplayMode` and logging the actual arguments
and HRESULT before deciding whether the color-depth work item is needed at all. Tracked as
**U-018**.

### 9.5 Not yet verified

`-sound:off` / `-music:off` were passed on every run but **audio output was never measured** —
`DSOUND.dll` and `GZSOUNDD.DLL` load regardless, and module presence is not evidence of
playback. Needs a per-process audio-session peak-meter check or a listening test.

---

## 10. Phase 1 — instrumented measurement (2026-08-15)

Tool: `re/harness/` — `sc3launch.exe` (CreateProcess suspended, cwd `Apps\`, inject, resume)
plus `sc3probe.dll` (IAT hooks on `GZGraphicD.dll` + COM vtable hooks on IDirectDraw).
Both x86 MSVC. **`SC3U.exe` is not modified on disk; the SHA-256 anchor is untouched.**
This build measures only, it changes no behaviour. Logs: `re/harness/run_w*.log`.

Hooked: `DirectDrawCreate`, `ShowWindow`, `CreateWindowExA`, `SetWindowPos`, `MoveWindow`,
`SetWindowLongA`, `GetDeviceCaps`, `ChangeDisplaySettings{A,ExA}` (reported *not imported*),
and IDirectDraw slots 0/6/20/21 with per-interface-version typed hooks so HRESULTs are
captured and interface upgrades are followed. Plus a 100 ms `EnumDisplaySettingsA` watcher.

### 10.1 A Windows compatibility shim is intercepting DirectDraw `[CONFIRMED]`

The decisive line. The IDirectDraw vtable lives in `DDRAW.dll+0x7D3C0`, but **every method in
it points into `apphelp.dll`** — the Windows Application Compatibility shim engine:

```
hooking IDirectDraw1 vtable at 0x6CD3D3C0 (from DirectDrawCreate)
  vtable        @ DDRAW.dll+0x7D3C0
  QI             = 0x73FD3E00  apphelp.dll+0x83E00
  CreateSurface  = 0x73FC5210  apphelp.dll+0x75210
  SetCoopLevel   = 0x73FC5580  apphelp.dll+0x75580
  SetDisplayMode = 0x73FC5600  apphelp.dll+0x75600
```
(`apphelp.dll` loaded at `0x73F50000`-`0x73FFE000`, confirmed in the module snapshot.)

> **CORRECTION 2026-08-15.** An earlier revision of this section claimed the observed
> `SetCooperativeLevel(hwnd=NULL, flags=0x8)` was `DDSCL_FULLSCREEN` and that its `DD_OK`
> return proved the shim was rewriting semantics. **That inference was wrong** — the probe's
> `decode_ddscl` had the constants inverted. Per `ddraw.h`, `DDSCL_FULLSCREEN = 0x01` and
> `DDSCL_NORMAL = 0x08`. The observed call is `SetCooperativeLevel(NULL, DDSCL_NORMAL)`,
> which is entirely legal, and §11 of `re/ghidra_export_gzgraphicd` analysis identifies it as
> the DirectX capability probe in `FUN_10012BD6` @ `0x10012bd6` line 83:
> `(**(code **)(*local_18 + 0x50))(local_18,0,8)`. The probe source has been fixed.
>
> **What survives the correction:** the vtable interception by `apphelp.dll` is directly
> observed and stands. The claim that the shim alters DirectDraw *semantics* is now
> unsupported by this evidence and is withdrawn.

**Consequence for the whole project, beyond this subsystem:** behavioural testing on this
machine currently measures *SC3U + Microsoft's compatibility shim*, not SC3U. Any C3/C4
confirmation that rests on observed runtime behaviour must state whether the shim was active.
Tracked as **U-020**.

### 10.2 The display mode really does change, and 16bpp really is applied `[CONFIRMED]`

Measured in-process with `EnumDisplaySettingsA(ENUM_CURRENT_SETTINGS)`, which is
DPI-independent (unlike `Screen.PrimaryScreen`, which misreported the desktop in §9):

```
[   0.623 ms] ### DISPLAY MODE AT START:  2560x1440 @ 32 bpp, freq=165
[1187.161 ms] ### DISPLAY MODE CHANGED:   800x600  @ 32 bpp
[1728.974 ms] ### DISPLAY MODE CHANGED:   800x600  @ 16 bpp
```

> **CORRECTION 2026-08-15 (§10b).** The conclusion originally drawn here — "the real display
> mode ends at 16 bits, so the colour-depth work item is real" — is **WRONG**, and was an
> artefact of measuring from *inside* the shimmed process. Sampling the display from an
> external, un-shimmed process (`Win32_VideoController`) during the same run gives:
>
> ```
>  1s  EXTERNAL: 2560x1440 @ 32bpp
>  3s  EXTERNAL:  800x600  @ 32bpp     <- resolution changes, depth does NOT
> 28s  EXTERNAL: 2560x1440 @ 32bpp     <- restored on exit
> ```
>
> **The real desktop never leaves 32bpp.** The 16bpp is the `DWM8And16BitMitigation` shim's
> emulated view, visible only to the game process. See §10b.

So the game does drive the desktop **resolution** to 800x600. The depth reading of 16 is
in-process only.

Note the correction this forces on §9: the host desktop is **2560x1440**, not 2048x1152.
`GetDisplayMode` reported `2560x1440, pitch=10240, RGBBitCount=32, Rmask=0x00FF0000,
Gmask=0x0000FF00, Bmask=0x000000FF` (32-bit XRGB). The Phase 0 figures were DPI-scaled by
1.25 by the .NET API. The *relative* Phase 0 result (`-r640x480` differs from baseline) stands.

### 10.3 `SetDisplayMode` is never called on any interface the game holds `[CONFIRMED]`

Across four runs, with both the IDirectDraw1 vtable (`DDRAW.dll+0x7D3C0`) and the
IDirectDraw2 vtable (`DDRAW.dll+0x7D420`, obtained via a logged
`QueryInterface(IID_IDirectDraw2)`) hooked at slot 21: **zero `SetDisplayMode` calls**, while
the mode demonstrably changes. Verified negatives:

- All four `DirectDrawCreate` calls return objects sharing the one hooked vtable (a second
  distinct vtable would have emitted another "hooking" line; none did).
- `ChangeDisplaySettingsA` / `ChangeDisplaySettingsExA` are **not imported** by `GZGraphicD.dll`.
- Byte-level import scan: **no** game module imports `ChangeDisplaySettings*` or
  `EnumDisplaySettings*` — checked `SC3U.exe`, `GZGraphicD.dll`, `GZWIND.DLL`, `GZSOUNDD.DLL`,
  `SIMUI.DLL`, `SIMINIT.DLL`, `GZResourceD.dll`, `GZServiceD.dll`, `GZTOOLSD.DLL`.
- `GZGraphicD.dll` imports exactly two DDRAW functions: `DirectDrawCreate`, `DirectDrawEnumerateA`.

`[UNCERTAIN]` — the mode-setting agent. Remaining candidates, none yet tested: the `apphelp`
shim performing the mode change itself; or a `GetProcAddress`-resolved DirectDraw entry point
that bypasses the IAT hook. **The cleanest next experiment is to disable the compatibility
shim and re-measure** — if `SetDisplayMode` then appears on our hooks, the shim was swallowing
it, and both U-016 and U-018 collapse into "measure again without the shim". Tracked as U-020.

### 10.4 What the windowed run actually produces `[CONFIRMED]`

With `-w`, in call order: `CreateWindowExA(class='Gonzo', title=NULL, style=0x90000000
[WS_POPUP|WS_VISIBLE], pos=0,0, size=800x600)` at ~770 ms, then
`SetWindowLongA(GWL_STYLE, 0x90000000)` re-asserting the same popup style, then
`SetWindowPos(0,0, 800x600, flags=0x37)`, then `ShowWindow(SW_SHOWNORMAL)`.

So under `-w` the window is created **at the game resolution (800x600), borderless, at the
desktop origin, and the display mode is still changed**. There is no titlebar, no
desktop-composited window. Whatever `-w` does reach, it does not produce windowed output here.
This sharpens U-016 without closing it: the deciding code is not in the window-creation path
we can see, since the style is popup from the very first `CreateWindowExA`.

### 10.5 Harness ergonomics note

PowerShell mangles `-sound:off` into `-sound: off` when splatting native arguments. The
stop-parsing token `--%` is required: `sc3launch.exe --% -kill 30 -- -w -sound:off`.
A named switch that arrives split is silently ignored by `0x00469755` (it requires
`token[1+len(name)] == ':'`), so this fails quietly rather than loudly.

---

## 10a. U-016 RESOLVED — why `-w` cannot work (GZGraphicD.dll, 2026-08-15)

Source: `re/ghidra_export_gzgraphicd/` (image base `0x10000000`, 767 functions). The graphics
service (CLSID `0xC416025C`) is registered by base ctor `FUN_1001588E` @ `0x1001588e`
(`FUN_1001a952(param_1, 0xc416025c, 1500000)`), derived ctor `FUN_10010C96` @ `0x10010c96`;
`GZDllGetGZCOMDirector` @ `0x10019de7`. SC3U's interface is the sub-object at `+0x18`,
vtable `0x1001ECE0`.

### The windowed flag is destroyed at Init `[CONFIRMED]`

The fullscreen/windowed state is **one byte at object offset `+0x48`** (`param_1[0x12]`).
Every writer, in order:

| Where | Write |
|---|---|
| ctor `0x10010c96` (early) | `= 0` |
| ctor `0x10010c96` (end) | **`= 1`** (default fullscreen) |
| Init `0x100114b8` **line 62** | **`*(bool *)(param_1 + 0x12) = DAT_1006cdac == '\0';`** |
| Init `0x100114b8` line 146 | **`= 1`** (force fullscreen) |
| Init `0x100114b8` line 157 | `= 0` (mode not in enumerated list) |
| Init `0x100114b8` line 235 | `= 0`, then virtual `(*(*param_1 + 0x34))()` |
| `FUN_10011F73` @ `0x10011f73` line 55 | `= (char)param_1` (the transition method) |

**Line 62 is the killer.** `DAT_1006cdac` has **exactly one reference in the entire DLL — that
read.** Verified independently by grep: zero writers. It is zero-init BSS, so the expression is
`0 == 0` → **fullscreen is unconditionally re-asserted at Init**, discarding whatever `-w` set.

Line 146 then re-forces fullscreen whenever the requested mode does not already match the
desktop — and a 16bpp request against a 32bpp desktop trips it on its own:

```c
if ((char)iVar1 == '\0') {                     // if currently windowed
  iVar4 = memcmp(param_1 + 0x40,&DAT_1006cd58,0x10);
  if ((((iVar4 != 0) || ((undefined **)param_1[0x1c] != DAT_1006cd98)) ||
      ((uint)param_1[0x1a] < DAT_1006cd90)) || ((uint)param_1[0x1b] < DAT_1006cd94)) {
    *(undefined1 *)(param_1 + 0x12) = 1;       // force FULLSCREEN
```

### There is no non-popup window style anywhere `[CONFIRMED]`

One `CreateWindowExA` site: `FUN_10018228` @ `0x10018228` line 64, class `"Gonzo"`. Style comes
from `FUN_100181D0` @ `0x100181d0`:

```c
cVar1 = (**(code **)(*piVar2 + 0x34))();          // IsFullScreen()
if (cVar1 == '\0') {
  uVar3 = (-(uint)((param_1 & 4) != 0) & 0x80800000) + 0x80000000;
  if ((param_1 & 2) != 0) uVar3 = uVar3 | 0xc00000;
  ...
} else { uVar3 = 0x90000000; }
```

The flags word is set to `0x1B` by `FUN_10017C83` @ `0x10017c83` and to `0` by the ctors —
**bit `0x4` is never set by any path**. So the only two reachable outcomes are:

- `IsFullScreen()` true → `0x90000000` = `WS_POPUP|WS_VISIBLE` (matches the measured trace exactly)
- `IsFullScreen()` false → `0x80CA0000` = **still `WS_POPUP`**, plus caption/sysmenu/minimizebox

`WS_OVERLAPPEDWINDOW` (`0x00CF0000`) is never produced. **Popup is unconditional.**

### Verdict

`-w` cannot produce a desktop-composited window in this build, for two independent reasons:
the flag is overwritten at Init from a global nothing ever writes, and even the "windowed"
style branch is still `WS_POPUP`. **U-016 resolved.** Making windowed mode work is therefore a
patch/hook job (force `+0x48` after Init and supply a real overlapped style), not a switch.

### Where `SetDisplayMode` actually lives — and why the probe never saw it `[CONFIRMED]`

Exactly one call site in the DLL, verified by direct grep:
`FUN_10011F73` @ `0x10011f73` line 51, `(**(code **)(*piVar3 + 0x54))(piVar3,w,h,bpp)`, on the
**fullscreen branch only**; the windowed branch calls `RestoreDisplayMode` (slot `0x4c`) at
line 37. `FUN_10011f73` is guarded by `if ((char)param_1 == cVar2) return;` — it runs only on
an actual state *transition*.

Cooperative level is set by `FUN_1001250D` @ `0x1001250d`: windowed → `0x08` (`DDSCL_NORMAL`),
fullscreen → `0x11` (`DDSCL_EXCLUSIVE|DDSCL_FULLSCREEN`).

This explains §10.3: our 30 s runs only ever observed `SetCooperativeLevel(NULL, 0x08)`, which
is the capability probe in `FUN_10012BD6` @ `0x10012bd6` line 83 — **the game never reached
real graphics init**, so neither the real `SetCooperativeLevel` nor `SetDisplayMode` ran.
The instrumentation was correct; the run was too short / the game was still loading.

`[UNCERTAIN]` — what changed the display mode at t+1187 ms and t+1729 ms then remains open.
The `apphelp` `DWM8And16BitMitigation` shim is the leading candidate. Note a methodological
trap: our mode watcher runs *inside* the shimmed process, so `EnumDisplaySettingsA` there may
report the shim's emulated mode rather than the true desktop mode. Any future measurement must
sample from an un-shimmed external process. Folded into U-020.

### Export gap that blocked full resolution

Slots `+0xDC` / `+0xE4` / `+0xEC` **cannot** be mapped to functions: `globals.csv` for this
module has 2 rows and no vtable arrays. Needed: pointer dumps of `0x1001ECE0`, `0x1001EE0C`,
`0x1001EC6C`, `0x1001EDF4`, `0x1001EEBC`. Slot `+0xDC` would be the dword at `0x1001EDBC`.
Same class of gap as §11.

---

## 10b. The 32bpp experiment — hypothesis FALSIFIED, requirement dissolved (2026-08-15)

### The hypothesis

From §10a and the GZGraphicD analysis: Init `FUN_100114b8` demands a display-mode change only
when the requested bpp differs from the **current** desktop bpp, and `FUN_10019273` has a full
explicit 32-bit ARGB path (`DDPF_RGB|DDPF_ALPHAPIXELS`, `dwRGBBitCount=32`, masks
`FF000000/FF0000/FF00/FF`) whereas the 16bpp case requests **no** pixel format at all.
Predicted: requesting 32 on a 32-bit desktop removes the mode change entirely.

### The intervention

`sc3probe.dll` gained an opt-in in-memory patch (`SC3PROBE_FORCE_BPP`, `sc3launch -bpp 32`).
It rewrites the `bpp` immediate at the four encodings of `mov dword ptr [ebp+disp], 10h` that
feed the three `SetResolution` call sites, after verifying the exact byte pattern
`C7 45 <disp> 10 00 00 00` at each address:

| RVA | VA | Function | Result |
|---|---|---|---|
| `0x4D27` | `0x00404d27` | `FUN_0040496d` (tier branch A) | PATCHED |
| `0x4D43` | `0x00404d43` | `FUN_0040496d` (tier branch B) | PATCHED |
| `0x5CF1` | `0x00405cf1` | `FUN_0040586a` (settings path) | PATCHED |
| `0x787B` | `0x0040787b` | `FUN_004077b5` (the `-r` path) | PATCHED |

4/4 applied, in memory only. **`original\SC3U.exe` on disk is untouched; the anchor holds.**

### The result: no observable change `[CONFIRMED]`

With `-bpp 32 -r800x600`, the in-process log is identical to the unpatched run: mode still
reported as `800x600 @ 32` then `800x600 @ 16`, same `WS_POPUP|WS_VISIBLE` window, same
absence of any `SetDisplayMode` call. **Hypothesis falsified for the observable.**

### Why — and the requirement dissolves

The external sampler settles it. During the same run, measured from an un-shimmed process:

```
 1s  EXTERNAL: 2560x1440 @ 32bpp
 3s  EXTERNAL:  800x600  @ 32bpp
28s  EXTERNAL: 2560x1440 @ 32bpp   (restored cleanly on exit)
```

**The real desktop never leaves 32bpp, patched or not.** The `DWM8And16BitMitigation` shim
already presents an emulated 16bpp surface to the game while keeping the true display at the
desktop's depth. The game's hardcoded `bpp = 0x10` therefore never reaches hardware.

**Consequence for the harness: "launch at the same colour depth as the desktop" is already
satisfied on this machine, and needs no code.** The work item is withdrawn while the shim is
active. If the shim is ever disabled, it returns — and §10b's patch is the ready-made fix,
since the renderer's 32bpp path is fully implemented.

**What actually disrupts the workflow is the resolution change, not the depth**: the desktop
really does drop to 800x600, which rearranges windows. The fix for that is windowed mode
(U-016), not colour depth.

### Methodological rule this establishes

Two conclusions in this document were wrong because they rested on in-process measurement
(the §10.2 depth claim, and the §10.1 shim-semantics claim from an inverted flag decode).
**Any runtime claim about display state must be measured from outside the shimmed process.**
Recorded so it is not re-learned a third time.

---

## 10c. Windowed mode — WORKING (2026-08-15)

**Result: the game runs in a captioned desktop window and the display mode is never changed.**
This is the fix that removes the actual workflow disruption (§10b: the resolution change, not
the colour depth).

### The recipe

```
sc3launch.exe -windowed -bpp 32 -- -r800x600 -sound:off -intro:off
```

Two in-memory patches, both required. Neither works alone.

**1. Defeat the Init override** — `GZGraphicD.dll + 0x6CDAC` (VA `0x1006cdac`), `0 -> 1`.

`FUN_100114b8` line 62 is `*(bool *)(param_1 + 0x12) = DAT_1006cdac == '\0';`. That global has
exactly one reference in the DLL (the read), zero writers, zero-init BSS — so the expression is
always true and fullscreen is unconditionally re-asserted, discarding `-w` (§10a). Writing 1
inverts it. Applied by the probe as soon as `GZGraphicD.dll` appears (~27 ms), well before Init
(~250 ms).

**2. Stop line 146 re-forcing fullscreen** — the four bpp immediates, `16 -> 32` (§10b).

Line 146 re-forces fullscreen when
`current_w < requested_w || current_h < requested_h || current_bpp != requested_bpp`.
Requesting 16bpp against a 32bpp desktop trips the third clause on its own. This is why the
§10b patch, which appeared to do nothing in isolation, is a **precondition** for windowed mode.
The requested resolution must also fit within the desktop.

### Measured result `[CONFIRMED]`

External sampler (`Win32_VideoController`, un-shimmed) across the whole 28 s run:

```
1s  EXTERNAL: 2560x1440 @ 32bpp     ... unchanged for the entire run ...
```

**The display mode is never touched.** Compare §10b, where the same run without `-windowed`
dropped the desktop to 800x600.

In-process trace:

```
--- WINDOWED: GZGraphicD+0x6CDAC (VA 0x1006CDAC) = 0 -> 1 ---
*** SetCooperativeLevel(this=..., hwnd=0x00000000, flags=0x00000008 [NORMAL]) -> DD_OK
CreateWindowExA(class='Gonzo', style=0x80CA0000
    [WS_POPUP|WS_CAPTION|WS_BORDER|WS_DLGFRAME|WS_SYSMENU|WS_MINIMIZEBOX],
    pos=-3,-26 size=806x629) -> hwnd=000A041C
MoveWindow(hwnd=000A041C, pos=621,237 size=806x629)
ShowWindow(hwnd=000A041C, SW_SHOWNORMAL(1))
```

Confirmations in that trace:
- Style is the windowed branch of `FUN_100181D0` (`0x80CA0000`), not the fullscreen `0x90000000`.
- 806x629 = 800x600 client plus border and caption, i.e. `AdjustWindowRectEx` ran.
- The initial rect is at `-3,-26` (client origin aligned to 0,0), then `MoveWindow` places it
  on the desktop instead of the origin.
- **No `SetDisplayMode` call**, and cooperative level is `DDSCL_NORMAL` — exactly the windowed
  path of `FUN_1001250D` predicted in §10a.

Visually verified: a window titled **"SimCity 3000"** with a standard caption bar and
minimize/maximize/close, composited on the desktop.

### RENDERING IS BROKEN in this mode `[CONFIRMED 2026-08-15]`

**The window is black. Not a capture artefact — confirmed by direct observation on the machine.**

Evidence: `PrintWindow(PW_RENDERFULLCONTENT)` on the `Gonzo` window at t+30 s and t+55 s of a
90 s run returns identical images, 4.4% non-black sampled pixels both times — and that 4.4% is
the caption bar. The client area is solid black and static.

**So windowed mode is NOT usable yet.** Placement and mode-preservation work; presentation does
not. This section previously read "rendering not yet confirmed"; that is upgraded to
"confirmed broken".

> **RESOLVED 2026-08-15 — the windowed patch is INNOCENT. See §10d.** The game never
> initialises its renderer in *any* configuration, patched or stock. The candidate causes
> listed below were separated by re-reading logs already captured, not by new experiments.

Two candidate causes, since separated (see §10d):

1. **The patch broke presentation.** The windowed path (`DDSCL_NORMAL`) needs things the
   fullscreen path does not — most likely an `IDirectDrawClipper` attached to the primary
   surface with `SetHWnd`, and a screen-relative destination rect for the blit. `GZGraphicD`
   does call `CreateClipper` (`FUN_10019877` @ `0x10019877`, IDirectDraw slot `+0x10`).
   A further specific risk: `FUN_10019cc7` @ `0x10019cc7` requests a **flip chain**
   (`ddsCaps = 0x2218` = `PRIMARYSURFACE|FLIP|COMPLEX`, backbuffer 1), which DirectDraw
   rejects with `DDERR_NOEXCLUSIVEMODE` outside exclusive fullscreen.
2. **The game never rendered at all**, in any configuration, and the patch is innocent.

**Note the gap in our evidence: rendering has never been confirmed in ANY configuration,
including stock fullscreen.** Every run was killed during startup, and the Phase 0 fullscreen
capture showed only the desktop, never game content. The control experiment (stock fullscreen +
`Blt`/`Flip`/`Lock` counters, now implemented in the probe) has not been run.

### Style note

`WS_OVERLAPPEDWINDOW` is never produced by this DLL (§10a), but it turns out not to matter:
`0x80CA0000` is `WS_POPUP` *plus* caption, border, sysmenu and minimize box, which behaves as a
normal window. No style patch was needed — only the two flag/bpp patches.

---

## 10d. RETRACTED — "the renderer never initialises"

> **This section's conclusion is WRONG and is retracted (2026-08-15). See §10e.**
>
> The `CreateSurface` counts below were collected in runs whose **COM vtable hooks were
> themselves preventing the game from rendering**. The instrument was the disease. Counting
> surface creations through a hook that breaks surface creation is circular, and I did not
> notice because every configuration I compared shared the same broken hooks.
>
> Ground truth, established afterwards by bisection (§10e): the game renders fine with no
> injector, fine with a passive DLL, and fine with IAT hooks only. It renders **black** as soon
> as the IDirectDraw vtable is patched in place.
>
> What survives: the raw observation that only one `CreateSurface` appeared *in those runs*.
> What does not survive: the inference that the renderer never initialises in general, and the
> consequent absolution of the windowed patch (U-021). The data below is kept for the record.

## 10d (retracted). The renderer never initialises — in ANY configuration

The probe logs every `CreateSurface` on every hooked IDirectDraw vtable, with `ddsCaps` and
HRESULT. Comparing four runs — three stock/partially-patched, one fully windowed-patched:

| Log | Configuration | `CreateSurface` calls | The one call |
|---|---|---|---|
| `run_w3.log` | stock (`-w` only, which is inert) | **1** | `ddsCaps=0x200`, `hwnd=NULL`, `DDSCL_NORMAL` @ 220 ms |
| `run_w4.log` | stock | **1** | same, @ 209 ms |
| `run_bpp32.log` | `-bpp 32` | **1** | same, @ 214 ms |
| `run_win.log` / `run_render.log` (90 s) | `-windowed -bpp 32` | **1** | same, @ 249 ms / 243 ms |

That single call is the **DirectX capability probe** in `FUN_10012BD6` @ `0x10012bd6`
(`SetCooperativeLevel(NULL, DDSCL_NORMAL)` then a throwaway `CreateSurface`, both released).

**No primary surface is ever created.** `FUN_100199c0` (`ddsCaps=0x2200`) and `FUN_10019cc7`
(`0x2218`) never run. `FUN_1001250D`'s real cooperative-level call (`0x08` windowed / `0x11`
fullscreen) never runs. `FUN_10011F73` — and therefore `SetDisplayMode` — never runs.

### What this settles

1. **The windowed patch (§10c) did not break rendering.** Rendering was never happening.
   U-021's candidate causes — missing clipper, flip chain rejected outside exclusive mode,
   absent screen-relative blit rect — are all **moot**: execution never reaches any of them.
2. It retroactively explains §10.3 (no `SetDisplayMode` observed), §10a's note that only the
   probe's `SetCooperativeLevel` ever appeared, and the black client area in §10c.
3. It explains why the Phase 0 fullscreen screen-capture showed only the desktop: there was
   no game content to capture.
4. The display-mode change at t+1187 ms is therefore **certainly not** the game's doing —
   nothing in the game's graphics path executes. It is the `DWM8And16BitMitigation` shim.

### Method note

This control existed in data already captured. It was resolved by re-reading four logs, not by
new experiments, and it overturned an in-flight hypothesis (the clipper/flip-chain theory) that
a static sweep had already been dispatched to investigate. **Check the logs you have before
commissioning analysis of a mechanism that may never execute.**

### What is now open

The game creates its window (`CreateWindowExA` ~770-980 ms), calls `ShowWindow`, and then makes
no further graphics calls for the remaining 89 seconds. Where it stalls is **`[UNCERTAIN]`** —
tracked as **U-022**. Note the four `DirectDrawCreate` calls (enumeration via `FUN_100120F9` /
`FUN_100121C4`, plus the live object from `FUN_100125C8`) *do* happen, so driver enumeration
completes; the stall is after that and before primary-surface creation.

**Critical unknown before spending more effort: whether SimCity 3000 renders on this machine at
all when launched normally, without the injector.** If it does not, the fault is environmental
(data files, GZCOM plugin load, the shim) and nothing in the harness is implicated. If it does,
then injection itself is suspect. That question is cheap to answer and has not been asked.

---

## 10e. Bisection — the COM vtable hooks were breaking the game `[CONFIRMED 2026-08-15]`

Trigger: the user reported that **SimCity 3000 renders fine when launched normally**. That
falsified the §10d premise immediately and forced a bisection of the harness itself.

Capture method note: `PrintWindow(PW_RENDERFULLCONTENT)` never captures this game's output.
`Graphics.CopyFromScreen` does. Percentages below are non-black sampled pixels of the screen.

| Test | Configuration | Result |
|---|---|---|
| A | `-noinject` (launcher only, no DLL) | **renders** — 99.7%, main menu visible |
| B | inject while suspended, `-passive` (no hooks, no patches) | **renders** — 99.7% |
| C | inject 4 s *after* resume, full hooks | **renders** — 99.7% (hooks land after graphics init) |
| D | inject at suspend, IAT hooks incl. `DirectDrawCreate`, **`-nocom`** | **renders** — 99.7% |
| E | inject at suspend, `-nodd` (so COM hooks never install) | **renders** — 99.7% |
| — | inject at suspend, **full hooks incl. COM vtable patching** | **BLACK** |

**Conclusion: patching the IDirectDraw vtable in place kills rendering.** Everything else in
the harness is safe — the suspended-process injection, the DLL itself, and all IAT hooks
(`DirectDrawCreate`, `ShowWindow`, `CreateWindowExA`, `SetWindowPos`, `MoveWindow`,
`SetWindowLongA`, `GetDeviceCaps`) are innocent.

Likely mechanism `[UNCERTAIN]`: the vtable at `DDRAW.dll+0x7D3C0` is not DirectDraw's own — its
slots point into `apphelp.dll` (§10.1), i.e. the `DWM8And16BitMitigation` shim owns that
dispatch. Overwriting those slots in place evidently breaks the shim's internal contract.
Not investigated further; the practical fix is simply not to do it.

**Harness rule adopted: run with `-nocom`. IAT hooks only.** COM-level observation of this
game's DirectDraw needs a non-invasive technique (e.g. wrapping the returned interface pointer
rather than patching shared vtable memory), which has not been built.

### Consequence: the windowed patch is NOT exonerated

With the harness in its known-good configuration (`-windowed -bpp 32 -nocom`):

- Desktop stays **2560x1440 @ 32bpp** for the whole run — the mode-preservation goal holds.
- A `SimCity 3000` captioned window appears at 806x629.
- **The client area is still black.** Fullscreen with the same hook set (test D) renders fine,
  so the difference is the windowed patch itself.

So U-021's original hypotheses are live again, and the §10c clipper analysis is relevant after
all. Leading candidates, in order:

1. **No clipper on the primary surface.** `FUN_10019877` @ `0x10019877` is the only code that
   calls `CreateClipper` + `SetHWnd` (clipper vtable `+0x20`, index 8) + `SetClipper` (surface
   `+0x70`), and **neither primary-surface creator calls it**. DirectDraw refuses a windowed
   blit to the primary without a clipper.
2. **No screen-relative destination rect.** `FUN_10019be8` @ `0x10019be8` (the only `Blt`)
   uses the caller's rect verbatim, with no `ClientToScreen`/`GetWindowRect` offsetting. The
   one `ClientToScreen` site, `FUN_100185f5` @ `0x100185f5` (correctly gated on
   `!IsFullScreen()`), feeds a different, unresolved consumer.
3. Silent failure everywhere: `GZGraphicD` discards every DirectDraw HRESULT, so any of this
   fails invisibly.

Plausible overall reading, not yet proven: **SC3U's windowed path was never finished or
shipped** — the game always ran fullscreen, so the windowed presentation plumbing is present
but incomplete. Tracked as U-023.

### 10e.1 Vtables resolved from `.rdata` `[CONFIRMED 2026-08-15]`

The export's missing vtable data was recovered by reading `Apps\GZGraphicD.dll` directly
(image base `0x10000000`; `.rdata` at `0x1001e000`). Closes the §10a/§10c gaps:

| Vtable | Slot | Function | Meaning |
|---|---|---|---|
| `0x1001ECE0` | 55 / **`+0xDC`** | `FUN_10010ED1` | **SetResolution — confirms SC3U's `+0xDC`** |
| `0x1001ECB4`, `0x1001EE90` | 66 / `+0x108` | `FUN_10010ED1` | same method, sibling interfaces |
| `0x1001EC6C` | 9 / `+0x24` | `FUN_1001250D` | SetCooperativeLevel wrapper |
| `0x1001EE0C` | 8 / `+0x20` | `FUN_100114B8` | Init |
| `0x1001EE0C` | 13 / `+0x34` | `FUN_10011F73` | fullscreen transition / IsFullScreen sibling |
| `0x1001F0AC` | 20 / `+0x50` | `FUN_10019877` | clipper create+SetHWnd+SetClipper |
| `0x1001F0AC` | 22 / `+0x58` | `FUN_10014286` | (not a primary creator) |
| **`0x1001F628`** | 20 / `+0x50` | `FUN_10019877` | clipper |
| **`0x1001F628`** | **22 / `+0x58`** | **`FUN_100199C0`** | **primary surface, `ddsCaps=0x2200`** |

`0x1001F628` is a **derived class**: its vtable ends immediately after slot 22 (slot 23 is not
code). It overrides slot 22 with the plain-primary creator — i.e. it is the non-flip-chain
device class. **`FUN_10019CC7` (the `0x2218` flip chain) appears in NO vtable**, so the
"flip chain rejected outside exclusive mode" hypothesis is dead.

### 10e.2 Two interventions tried, both FAILED `[CONFIRMED]`

**Attaching a clipper — succeeded mechanically, changed nothing.** Implemented as
`sc3launch -clipper`: read the live `IDirectDraw` from `GZGraphicD+0x6CD54` (RVA of
`DAT_1006cd54`, written by `FUN_100125C8`), then, **by calling COM methods only, never
patching a vtable** (per §10e):

```
CLIPPER: IDirectDraw=0x03B7BBE0 hwnd=0x002F08CA (after 1100 ms)
    GetGDISurface        -> hr=0x00000000 [DD_OK], primary=...
    CreateClipper        -> hr=0x00000000 [DD_OK], clipper=0x03BB1270
    Clipper::SetHWnd     -> hr=0x00000000 [DD_OK]
    Surface::SetClipper  -> hr=0x00000000 [DD_OK]
--- CLIPPER: attached to the primary surface ---
```

All four calls succeed. **The window is still black** (verified with a DPI-aware
`CopyFromScreen` of the exact window rect: 6.0% non-black = the caption bar only).

**The "no screen-relative rect" prediction — falsified.** If `FUN_10019be8` blitted with a
client-relative rect and no offset, the frame would land at the *screen's* top-left. A
DPI-aware full-desktop capture during a windowed run shows the top-left 800x600 region is
**plain desktop wallpaper**. The frame is not landing there, or anywhere.

Conclusion: the game is not presenting at all when forced windowed. The failure is upstream of
both the clipper and the blit geometry.

### 10e.3 Capture methodology (learned the hard way)

- `PrintWindow(PW_RENDERFULLCONTENT)` **never** captures this game's output. Do not use it.
- `Graphics.CopyFromScreen` **does**.
- PowerShell is DPI-virtualized: without `SetProcessDPIAware()`, `GetWindowRect` values and
  capture coordinates disagree by the desktop scale factor (1.25 here), producing captures
  that look black because they are aimed at the wrong pixels. Two captures in this document
  were misread for exactly that reason. **Always call `SetProcessDPIAware()` first.**

---

## 10f. U-023 ROOT CAUSE — the windowed path has no presentation mechanism `[CONFIRMED 2026-08-15]`

Method: an inline detour tracer (`sc3launch -trace`) on 13 `GZGraphicD` functions. This
patches **game code**, not the apphelp-owned COM vtable, so it does not reproduce the §10e
fault. Prologues are verified before patching: pattern A `B8 <imm32>` (`mov eax, imm32`, the
MSVC SEH idiom `mov eax,<handler>; call __EH_prolog`) → steal exactly 5 bytes, fully
position-independent; pattern B `55 8B EC 83 EC ??` → steal 6. Trampoline is
`[stolen][jmp target+stolen]`.

Two 20 s runs, identical except for the windowed patch:

| Traced function | Fullscreen (**renders**) | Windowed (**black**) |
|---|---|---|
| `Init            FUN_100114b8` | 1 | 1 |
| `SetCoopLevel    FUN_1001250d` | 2 | 1 |
| `PrimaryCreate   FUN_100199c0` (plain, `0x2200`) | **0** | **1** |
| `PrimaryFlipChn  FUN_10019cc7` (flip chain, `0x2218`) | **1** | **0** |
| `Transition      FUN_10011f73` | 1 | 0 |
| `Clipper         FUN_10019877` | 0 | **1** |
| `OffscreenSurf   FUN_10019273` | 48 | 48 |
| `CreateWindowFn  FUN_10018228` | 1 | 1 |
| `Flip            FUN_10018dd9` | 0 | 0 |
| `FlipOverride    FUN_10018e32` | 0 | 0 |
| **`FlipPlus8       FUN_10019a77`** | **1050** | **0** |
| `Blt             FUN_10019be8` | 0 | 0 |
| `FSslot22        FUN_10014286` | 0 | 0 |

### The answer

**The engine's only present path is `FUN_10019a77` @ `0x10019a77` — a `Flip` on the surface at
`this+8` — and `Flip` requires a flip chain.** At ~105 calls/second it is plainly the
per-frame present.

- Fullscreen creates its primary through `FUN_10019cc7` (`ddsCaps=0x2218` =
  `PRIMARYSURFACE|FLIP|COMPLEX`, 1 back buffer) and then flips 1050 times. It renders.
- Windowed creates a **plain** primary through `FUN_100199c0` (`ddsCaps=0x2200`, no back
  buffer). `FUN_10019a77` is then **never called**, and `FUN_10019be8` (the only `Blt`) is
  never called either. Nothing ever reaches the screen.

Everything else about the windowed path works correctly: it selects the windowed device class
(`0x1001F628`), creates the plain primary, sets `DDSCL_NORMAL`, **calls its own clipper**
(`FUN_10019877`, 1 hit — so the manual `-clipper` attach of §10e.2 was redundant), and builds
the same 48 offscreen surfaces as fullscreen. It renders frames into offscreen memory and then
has nowhere to put them.

### Corrections this forces

- **`FUN_10019cc7` IS used** — it is the fullscreen primary creator. §10e.1 called that
  hypothesis "dead" because the function appears in no vtable; it is evidently called directly.
  What was wrong was the *reason* it mattered, not its existence.
- The `-clipper` intervention (§10e.2) failed because it was **unnecessary**, not because the
  clipper was wrong: the game already attaches one in windowed mode.
- `FSslot22 FUN_10014286` is never called in either mode — not the fullscreen primary creator.

### Verdict on windowed mode

**SC3U's windowed presentation was never finished.** The plumbing exists — a windowed device
class, a clipper, `DDSCL_NORMAL`, and a general `Blt` wrapper (`FUN_10019be8`, which even has
a src/dest direction selector) — but nothing wires `Blt` into the frame loop. The game shipped
fullscreen-only and the windowed branch was left non-presenting.

A fix is possible but is real engineering, not a flag: detour `FUN_10019a77` (or its caller)
so that, when windowed, it blits `this+8` → `this+4` with a `ClientToScreen`-offset
destination rect instead of flipping. `FUN_10019be8` already implements exactly that blit
shape (`dest=+4, src=+8` when its `param_3 == 0`). Tracked as U-024.

---

## 10g. The present gate located and forced — partial result `[2026-08-15]`

### Correcting §10f's identification

§10f said the steady-state present caller was `FUN_10016ba4`. **Wrong.** That came from
"nearest preceding function start", but `FUN_10016ba4` is only 58 bytes and ends at
`0x10016bde`, while the captured return address is `0x10016c0a`. Tracing `FUN_10016ba4`
directly gives **0 hits in both fullscreen and windowed**, while `FUN_10019a77` still fires
968 times in fullscreen — proving it is not on the present path.

The real caller sits in a region **Ghidra never carved into a function** (`0x10016bde` →
`0x10016c9f` is a gap in the export). That is why no static sweep could find it.

### The present path, hand-disassembled from `Apps\GZGraphicD.dll`

Function starts at **`0x10016bf1`**:

```
10016bf1  8b c1        mov  eax, ecx
10016bf3  56           push esi
10016bf4  33 c9        xor  ecx, ecx
10016bf6  39 48 1c     cmp  [eax+0x1c], ecx
10016bf9  75 44        jne  0x10016c3f
10016bfb  38 48 15     cmp  byte ptr [eax+0x15], cl   ; THE PRESENT GATE
10016bfe  74 0c        je   0x10016c0c                ; skip presenting
10016c00  8b 40 44     mov  eax, [eax+0x44]
10016c03  8b c8        mov  ecx, eax
10016c05  8b 10        mov  edx, [eax]
10016c07  ff 52 38     call [edx+0x38]                ; PRESENT
10016c0a  5e           pop  esi                       ; <- captured return address
10016c0b  c3           ret
```

`this+0x15` is written by `FUN_10015e3d` from the flipping flag (`param_3` → `this+0x21` →
`this+0x15`), and the windowed path forces flipping to 0 (`FUN_100114b8` zeroes
`DAT_100241ed`). **So in windowed mode the gate is closed and the present call is skipped
every frame.** That is the precise mechanism behind the black window.

### Intervention: `sc3launch -present`

Patches `GZGraphicD+0x16BFE` from `74 0C` (`je`) to `90 90` (`nop nop`), after verifying the
bytes, making the present call unconditional.

**Result: the client area changes from black to WHITE. Still no game content.**

So the gate is real and controls presentation, but opening it is not sufficient. The present
target `[edx+0x38]` on the object at `this+0x44` evidently presents an empty/uninitialised
surface in windowed mode. Note `Blt FUN_10019be8` and `FlipPlus8 FUN_10019a77` both remain at
**0 hits**, so the windowed `+0x38` resolves to yet another present implementation that is not
among the 14 traced functions.

### Status

**Windowed rendering is still NOT working.** Progress is real but partial:

| Step | State |
|---|---|
| Windowed device class selected, clipper attached, `DDSCL_NORMAL` | working |
| Desktop display mode preserved (2560x1440 @ 32bpp) | working |
| Captioned window, correct client size | working |
| Present gate located and forced open | working — black to white |
| Actual game frames reaching the window | **not working** |

Next concrete step: identify what `[edx+0x38]` resolves to in windowed mode (dump the vtable
of the object at `this+0x44` at runtime, which the probe can do without patching anything),
then determine why it presents blank. Tracked in U-024.

---

## 10h. FINAL ANSWER — the windowed device has no render target `[CONFIRMED 2026-08-15]`

Runtime vtable dump of the object at `this+0x44` (read-only, no patching) settles which
present implementation each mode uses:

| Mode | present object vtable | slot 14 (`+0x38`) | gate `this+0x15` |
|---|---|---|---|
| Fullscreen | `GZGraphicD+0x1F5C0` | `FUN_10019a77` @ `0x10019a77` | **1** |
| Windowed | `GZGraphicD+0x1F628` | **`FUN_10018dd9`** @ `0x10018dd9` | **0** |

`FUN_10018dd9` is, in full:

```c
iVar1 = (**(code **)(**(int **)(param_1 + 4) + 0x2c))(*(int **)(param_1 + 4),0,1);
if (iVar1 == 0) { uVar2 = 1; } else { /* swallow, return false */ }
```

i.e. `this[1]->Flip(NULL, DDFLIP_WAIT)` on the **primary**, with the failure discarded.

### The decisive measurement

Detoured `FUN_10018dd9` to substitute the game's own blit wrapper `FUN_10019be8`
(`direction 0` → `dest = this+4`, `src = this+8`) with a `ClientToScreen` destination rect.
The hook logged its inputs before acting:

```
WINPRESENT #1: this=0x005AB5A8  primary(+4)=0x03B61450  src(+8)=0x00000000
WINPRESENT #2: this=0x005AB5A8  primary(+4)=0x03B61450  src(+8)=0x00000000
WINPRESENT #3: this=0x005AB5A8  primary(+4)=0x03B61450  src(+8)=0x00000000
```

**`this+8` is NULL.** There is no back buffer, no render target, nothing to present.

- Fullscreen: `FUN_10019cc7` creates a primary **with a flip chain** (`ddsCaps=0x2218`,
  1 back buffer) and then `GetAttachedSurface` populates `this+8`. Present = flip that chain.
- Windowed: `FUN_100199c0` creates a **plain** primary (`ddsCaps=0x2200`) and **never creates
  or attaches anything at `this+8`**. Present = flip a surface that has no flip chain, which
  always fails, silently.

So the chain is complete and every link is now evidence-backed:

1. Windowed forces the flipping flag off → `this+0x15` gate closed → present skipped (§10g).
2. Force the gate open → present runs → but it is a `Flip` on a plain primary → fails silently.
3. Substitute a `Blt` → **there is no source surface to blit from**.

### Verdict

**SC3U's windowed mode is not merely unfinished at the presentation call — the windowed device
never allocates a render target.** Completing it means constructing an offscreen surface,
wiring it into `this+8`, and ensuring the engine's draw path targets it: re-implementing part
of the device class, not patching a branch. That is engine work well beyond a launch flag.

**Recommendation for the test harness:** use a DirectDraw wrapper (DDrawCompat, dgVoodoo2)
dropped into `Apps\` if windowed output is wanted. It solves this whole class of problem
without modifying the game, at some cost to RE fidelity — which must then be stated whenever
runtime behaviour is cited as evidence, exactly as with the `apphelp` shim (U-020).

### What the harness gained regardless

`sc3probe.dll` now has, all validated: IAT hooking, an inline detour engine with verified
prologue patterns (`B8 imm32` / `55 8B EC 83 EC` / `56 8B F1 33 C0` / `8B C1 56 33 C9`),
runtime vtable dumping, byte-patching with pattern verification, a display-mode watcher, and
COM interface calling. That is the instrumentation toolkit the rest of the RE work needs.

---

## 10i. Launch-minimised and per-function logging — BOTH WORKING `[CONFIRMED 2026-08-15]`

### Launch minimised — `sc3launch -minimized`

`SC3U.exe` discards `nCmdShow` (`entry` @ `0x004b4b54` calls `GetStartupInfoA` and never reads
`wShowWindow`), and every `ShowWindow` call site uses a constant (§6), so this can only be done
by interception. The probe's existing `ShowWindow` IAT hook on `GZGraphicD.dll` substitutes
`SW_SHOWMINNOACTIVE (7)` for any non-`SW_HIDE` value:

```
ShowWindow(hwnd=007608F2, SW_SHOWNORMAL(1)) -> forced SW_SHOWMINNOACTIVE(7)
```

Verified by window state, not just by the intercepted call:

```
Gonzo hwnd=0x370840  Iconic=True  Visible=True
```

**Works.** Combines with `-windowed -bpp 32` so the desktop mode is left alone as well.

### Per-function logging — `sc3launch -fnlog <table>`

Data-driven detour tracing of arbitrary SC3U functions. The table is plain text
(`re/harness/trace.txt`), so the instrumented set changes without a rebuild and can be
maintained straight from `functions.csv`:

```
0x004077b5 apply_cmdline_options
0x00469568 cmdline_find_char_switch
```

Addresses are SC3U VAs, rebased at runtime. Stubs are **emitted at runtime** (not compile-time
macros) so the table size is not fixed; each is
`pushad / pushfd / mov eax,esp / push frame / push idx / call fnlog_enter / popfd / popad /
jmp trampoline`. Entry logging gives `ecx` (this), the return address, and the first four stack
arguments, throttled to 5 hits per function then counted.

**First run validated the static analysis directly.** 19 of 33 table entries instrumented,
20 s run:

| Function | Hits | Significance |
|---|---|---|
| `winmain` | 1 | |
| `cmdline_tokenizer_ctor` | 1 | |
| **`cmdline_find_char_switch`** | **9** | matches the 8 char switches of §3a |
| **`cmdline_find_named_switch`** | **11** | matches the named-switch call sites of §3b |
| **`apply_cmdline_options`** (`FUN_004077b5`) | **1** | **independent runtime re-confirmation of U-013** |
| `app_init_resolution_sound` | 1 | |
| `app_init_sound_music_intro` | 1 | |
| `app_apply_settings_blob` | 1 | |
| `check_install_switch` | 1 | |
| `app_ctor`, `framework_alloc`, `framework_init` | 1 each | |
| **`get_debug_stream`** | **1** | the Gonzo console really is constructed (§7b) |
| **`crashlog_install`** | **1** | the crash logger really is armed (§7a) |
| `scan_cmdline_plugins` | 1 | |

**Known limitation: 14 of 33 entries were skipped** with `UNRECOGNISED prologue`. Only four
patterns are currently accepted, each verified before patching:

| Pattern | Bytes | Steal |
|---|---|---|
| A | `B8 <imm32>` (`mov eax, imm32`, MSVC SEH idiom) | 5 |
| B | `55 8B EC 83 EC ??` (`push ebp; mov ebp,esp; sub esp,imm8`) | 6 |
| C | `56 8B F1 33 C0` (`push esi; mov esi,ecx; xor eax,eax`) | 5 |
| D | `8B C1 56 33 C9` (`mov eax,ecx; push esi; xor ecx,ecx`) | 5 |

Skipped functions are reported by name with their first five bytes, so extending coverage is
mechanical: add the pattern to `prologue_len()`. A proper length-disassembler would remove the
limit entirely and is the obvious upgrade if the table grows.

---

## 11. Gaps in the export tooling this work exposed

`ExportAllDecomp.java` emits function bodies and symbol/string/global CSVs, but **not**:

1. **Vtable / pointer-array contents.** This blocked §3d and §7b reachability. Needed:
   raw pointer dumps of `0x004cf580-0x004cf700` (app), `0x004d6bf4+` (framework),
   `0x004d7750+` (cmdline), `0x004d6a80-0x004d6b80` (debug stream).
2. **Undefined data bytes.** `0x004f4c34` (`"off"`) and `0x004f79d0` (`"/-\"`) were both
   invisible in `strings.csv` because Ghidra never created data there; both were resolved by
   reading `original\SC3U.exe` directly. A raw-bytes fallback for `DAT_`/`PTR_DAT_` targets
   referenced by decompiled code would close this class of gap.
