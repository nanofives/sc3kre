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
| `-l<value>` | `0x004077b5` +77 | → svc `0x441E5070` `vf+0x44`/`vf+0x48` lookup, `vf+0x28`/`vf+0x24`, then `FUN_004845fe()->vf+0x78`. ⚠️ **Does not load a city in practice — measured 2026-08-21, see §"Loading a city at launch" below.** Use a bare path instead |
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
| **Language/country (locale)** — NOT city/region, see §31.5 | `FUN_0047048f` → `FUN_00470867` | `0x441E5070` | `0x0054B7D5` |
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
- ~~`-l<value>` / `-c<value>` — load a city/region directly at launch~~ → **corrected 2026-08-21:
  `-l` does NOT load a city. Pass a bare absolute `.sc3` path with no switch. See "Loading a city
  at launch" below.**

### Loading a city at launch — measured, not inferred (2026-08-21)

Three forms tried against this build, observed with the multi-module `-filetrace`
(`verify/tilingrules_read_test/RESULTS.md`):

| argument passed to `SC3U.exe` | observed |
|---|---|
| `-lFarmsville` | **no file access at all.** No `Cities` open, no `FindFirstFileA`, nothing. The `-l` path never reached a file. |
| `-lC:\…\Cities\Farmsville.sc3` | `CreateFileA "-lC:\…\Farmsville.sc3"` → **FAIL**. The `-l` prefix was **not stripped**; the whole token was used as the path. |
| `C:\…\Cities\Farmsville.sc3` (**bare absolute path, no switch**) | **`-> ok`, the city loads.** First open at 1,383 ms, reload at 2,533 ms. |

**Use the bare absolute path.** Reproducible; this is how `verify/tilingrules_read_test/` loads a
fixture.

`[UNCERTAIN]` why `-l` fails, given the handler at `0x004077b5` +77 demonstrably exists. The two
failing attempts carried a **leading space** in the argument (needed to stop PowerShell binding
`-lC:` as a parameter name), which may have shifted tokenisation in the game's
`GetCommandLineA()` re-parse. Not chased further, because the bare path works.

Two `capture.ps1` gotchas found alongside:

- The reconstructed shot fires at **~44 s**, so `-AtSec 40` kills the run before it lands. Use 60+.
- `-GameArgs "-lC:\…"` is rejected by PowerShell as a parameter (the colon). Use
  `-GameArgs:" <value>"` with a leading space.
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
read.** [FALSIFIED 2026-08-19 - see §32. There are TWO references and one is a WRITE:
`0x10010EF7` is the imm32 of `A2` (mov [imm32],al) inside the 12-byte setter `FUN_10010ef2`,
which occupies two vtable slots. And the game CALLS it with al=1 during startup, so the byte
is 1 at Init time with or without our poke.] The original text read: zero writers, zero-init
BSS, so the expression is
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
[FALSIFIED - see §32: two references, one of them a WRITE, and the game itself calls the
setter with al=1 before Init reads. This poke is REDUNDANT; the operative half of `-windowed`
is the `0x117D6` nop.] The original text read: exactly one reference in the DLL (the read),
zero writers, zero-init BSS - so the expression is
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

### Length decoder — 33/33 instrumented `[CONFIRMED]`

The first build used four hardcoded prologue patterns and skipped 14 of 33 entries. Inspecting
those showed the pattern approach could not work in general: `reskey_resolve_string`
@ `0x004862e1` begins `56 57 8B F1 E8 ...`, i.e. only **4** bytes before a **relative `call`**.
Any 5-byte steal necessarily captures a rel32, which is position-dependent.

Replaced with a small x86 length decoder (`insn_len` + `modrm_len`) that walks whole
instructions until at least 5 bytes are covered, and records the offset of any `E8`/`E9`
encountered. The trampoline builder then **rewrites those displacements**:

```c
DWORD abs_target = (DWORD)(t + o + 5) + *(DWORD *)(t + o + 1);
*(DWORD *)(tr + o + 1) = abs_target - (DWORD)(tr + o + 5);
```

Result:

```
FN  reskey_resolve_string: relocated rel32 at +4 -> 0x0048440B
--- FNLOG: 33/33 functions instrumented ---
```

Anything the decoder does not understand still returns 0 and the function is skipped and
reported, rather than guessed at.

**Non-destructive: verified the game still renders its main menu with all 33 detours active.**

### What the full table showed

| Function | Hits (20 s) | What it confirms |
|---|---|---|
| `load_gzcom_plugin_dll` | **34** | 34 GZCOM plugin DLLs loaded at startup — matches `MODULE_MAP.md` |
| `get_graphics_service` | 62 | graphics service is the hottest of the four |
| `get_music_service` / `get_city_region_service` / `get_audio_service` | 19 / 10 / 4 | |
| `reskey_resolve_string` / `reskey_ctor` / `reskey_get_triple` | 39 / 31 / 8 | localized-string traffic, consistent with `RESOURCE_KEYS.md` |
| `cmdline_find_char_switch` / `cmdline_find_named_switch` | 9 / 11 | matches the call-site counts of §3a / §3b exactly |
| `apply_cmdline_options` | 1 | independent runtime re-confirmation of U-013 |
| `crashlog_install` / `crashlog_setup_filter` | 1 / 1 | the crash logger is armed at startup (§7a) |
| `crashlog_printf` | **0** | and it is crash-only, as documented — never fires in a clean run |
| `get_debug_stream` | 1 | the Gonzo console object **is** constructed (§7b) |
| **`debug_window_create` / `debug_window_show` / `debug_console_dispatch`** | **0 / 0 / 0** | **the console window is never created and never shown during startup** — runtime support for U-015 |
| `app_dtor` | 0 | run was killed, never reached shutdown |

The `get_debug_stream = 1` with `debug_window_create = 0` pair is the useful one: it confirms
§7b's static reading that the stream is constructed unconditionally while its window is not,
and shows the show-setter is not called on any normal startup path.

---

## 10j. Windowed present pipeline built and proven — engine still not drawing `[2026-08-15]`

### Surface layouts, measured via `GetSurfaceDesc` (call-only, no patching)

| Slot | Fullscreen | Windowed |
|---|---|---|
| `+4` | 800x600, 16bpp, `FLIP\|COMPLEX\|VIDMEM`, backbuf=0 → **back buffer (render target)** | **2560x1440**, 32bpp, `PRIMARY\|COMPLEX\|VIDMEM` → the desktop primary |
| `+8` | 800x600, `PRIMARY\|FLIP\|COMPLEX\|VIDMEM`, backbuf=1 → **primary (front)** | **NULL** |

So fullscreen renders into `+4` and flips `+8`. **Windowed has the primary in the render-target
slot and no back buffer at all** — and my earlier Blt attempt (§10h, direction 0 = dest `+4`,
src `+8`) was therefore both sourceless *and* backwards.

### The present pipeline works — proven with a magenta test surface

Created an 800x600 offscreen surface, installed it at `+4`, moved the primary to `+8`, and
presented with the game's own `FUN_10019be8` (direction 1 = dest `+8`, src `+4`).

**Result: the window filled 99.9% with our test colour, at the correct position and size.**
A windowed present is therefore mechanically achievable — surface, clipper, rect and blit all
work end-to-end.

Two bugs found and fixed along the way, both worth recording:

- **`non-black` is not a content test.** A fresh VRAM surface is full of stale desktop imagery,
  which fooled an earlier check into "the engine is rendering". Pre-filling with magenta and
  measuring retention is the reliable test.
- **DPI double-scaling.** `ClientToScreen` inside this DPI-virtualised process returns logical
  coordinates, and the shimmed DirectDraw *already* maps them onto the physical primary.
  Scaling by 1.25 ourselves put the blit 25% too far right and down. Do not correct it.

### But the engine does not draw into it `[CONFIRMED]`

Magenta retention at present **#3** and **#60**: `57600/57600 STILL MAGENTA`. Installing a
surface at `+4` does not redirect the engine's rendering.

Nor is there any other candidate. `FUN_10019273` creates exactly one offscreen surface matching
the requested mode (800x600), and it is **`0/7500` non-black on every sample, for the whole
run**. Nothing anywhere holds a rendered frame.

**Conclusion: in windowed mode the engine's draw path is itself inactive, not merely its
present.** This strengthens §10h rather than replacing it: windowed mode is unfinished at more
than one layer. Completing it means finding and enabling the draw path too, which is engine
work of unknown depth.

### Bonus: the crash logger validated in anger

Two runs crashed, **both from my own probe code**, and `SC3U_stkdmp.txt` (§7a) diagnosed both:

```
Exception code: C0000005 ACCESS_VIOLATION
Fault address:  02809C0C  01:00018C0C  GZGraphicD.dll     -> VA 0x10019C0C, inside FUN_10019be8
EAX:00000000  EDX:00000000
```

That is `FUN_10019be8` dereferencing a NULL surface: **the game's Blt wrapper does not
null-check `this+4`/`this+8`** — useful to know for any future patching. The second crash was
in `sc3probe.dll` itself (the candidate-scanning lock loop). The always-armed crash logger
found both instantly, exactly as §7a predicted.

---

## 10k. ROOT CAUSE, FINAL — windowed mode needs a 16bpp display mode `[CONFIRMED 2026-08-15]`

### The measurement that cracked it

Same engine surface (`FUN_10019273`, matching the requested mode), sampled from the watcher
thread in both modes:

| | Fullscreen (renders) | Windowed (black) |
|---|---|---|
| engine frame buffer | 800x600 **16bpp** — **7500/7500 LIT** | 800x600 **32bpp** — **0/7500 LIT** |

Fully drawn in one mode, completely empty in the other, and the only difference is depth.

### Why the depth differs

`FUN_10019273` writes an explicit `DDPIXELFORMAT` **only for 32bpp and 8bpp** (§10h). At 16bpp
it writes none, so the surface **inherits the current display mode**:

- **Fullscreen** changes the display mode to 16bpp → surfaces are created 16bpp.
- **Windowed** never changes the display mode → on a 32bpp desktop, surfaces are 32bpp.

And `GZGraphicD`'s software blitter is **16bpp-first**: `FUN_1000ce4c` / `FUN_1000cf31` /
`FUN_1000d054` gate on `this+0x10 != 0x10`, and `FUN_10014c05` provides 8→16 and 32→16
converters but no 32bpp draw path. On a 32bpp surface the drawing simply does not happen.

So the `-bpp 32` workaround from §10c — which windowed *required* to survive Init — was itself
silently disabling all rendering. Two patches that each looked necessary were mutually exclusive.

### The confirming experiment

Neutralised the Init re-force (`0x100117d6  C6 43 48 01  mov byte [ebx+0x48],1` → 4×`nop`) so
16bpp could stay, then patched `FUN_10019273` to request an explicit 16bpp 5-6-5 format instead
of inheriting:

```
100192fb  74 4C  je 0x10019349        ->  74 1F  je 0x1001931c   (into the explicit branch)
1001931c  83 4E 58 41                 ->  83 4E 58 40            (DDPF_RGB, no alpha)
1001932a  31 bytes of 32bpp constants ->  RGBBitCount=0x10 + 5-6-5 masks + nops
```

**Result: the game aborts ~2.4 s in**, with no crash dump — i.e. the graceful
`cGZFrameWorkW95::AbortiveQuit(): Calling _exit()` path (string @ `0x100240bc`), not a fault.
DirectDraw will not give a 16bpp surface on a 32bpp display, so surface creation fails and the
engine gives up.

### Final verdict

```
windowed  =>  no display-mode change
          =>  desktop stays 32bpp
          =>  engine surfaces are 32bpp (they inherit the mode)
          =>  the 16bpp-only software blitter draws nothing
and forcing 16bpp surfaces directly  =>  DirectDraw refuses  =>  the game aborts
```

**Windowed mode is not achievable by patching on a 32bpp desktop.** It is not an unfinished
branch so much as an *obsolete* one: in 2000, 16bpp desktops were common, and on a 16bpp
desktop this path would have worked, because the inherited surface format would have matched.
The dependency is on an environment that no longer exists.

Making it work today requires a pixel-format conversion layer — render 16bpp offscreen, convert
to 32bpp, present — which is precisely what a DirectDraw wrapper (DDrawCompat, dgVoodoo2)
already implements. **That is the recommended route**, with the same fidelity caveat as U-020.

What is genuinely reusable from this line of work: the present pipeline (§10j) is proven — a
test surface reached the window at the correct position and size — so if the format problem is
solved by a wrapper, nothing else here is missing.

---

## 10l. RETRACTION — the draw path IS active in windowed mode `[CONFIRMED 2026-08-16]`

**§10j's conclusion ("in windowed mode the engine's draw path is itself inactive") is WRONG
and is retracted.** It rested on sampling one guessed surface. Instrumenting the actual draw
functions shows the renderer running at full rate.

Method: the per-function tracer extended to `GZGraphicD` (`sc3launch -gzlog`), 30 draw-path
functions, 20 s runs, fullscreen vs windowed:

| Function | Fullscreen | Windowed |
|---|---|---|
| `blt_disp_1` `FUN_10014894` | 14,697 | **34,764** |
| `getpixel_a` `FUN_100155b6` | 40,295 | **40,252** |
| `blt_convert` `FUN_10014c05` | 750 | 534 |
| `dev_init_w_h_mode_bpp` `FUN_10009efb` | 56 | 48 |
| `transparency_test` `FUN_10015785` | 43 | 0 |
| `restyle_fullscreen` `FUN_1001850e` | 1 | 0 |
| `window_create` / `window_style` / `window_center` | 1 / 1 / 1 | 1 / 1 / 1 |

Pixel traffic is essentially identical, and windowed actually blits **more**. The engine draws.

### What the blit destination actually is

`FUN_10014894`'s `this` (captured live) is **not** a surface wrapper — `+4` holds a vtable
(`GZGraphicD+0x1F314`, i.e. `.rdata`), not a surface. It is the **software render device**:

```
DRAW OBJ: 0x00588358   bpp(+0x10)=32   w(+0x24)=800   h(+0x28)=600
```

matching `FUN_10009efb`'s field map (`+0x10` bpp, `+0x24` width, `+0x28` height). Scanning its
first 48 fields for any pointer whose own vtable lives in `DDRAW.dll`/`apphelp.dll` found
**none** — the device holds no DirectDraw surface at all.

**So the engine renders into a plain memory buffer**, and the missing step in windowed mode is
whatever carries that buffer into a DirectDraw surface. That is consistent with everything
else: the `FUN_10019273` surface stays `0/7500` lit because the engine never renders *into*
it directly, and forcing a Blt from it presents an empty surface.

### Where this leaves the chase

Still unsolved, but the target is now specific and much narrower than before:

- The frame data exists, in a software buffer owned by device object `+0x10/+0x24/+0x28`.
- Find the pixel-buffer pointer in that object (offset unknown; not in the first 48 fields as
  a COM pointer, so it is likely a raw `void*` to locked surface bits or a private allocation).
- Find what normally moves it to DirectDraw in fullscreen, and why that step is skipped windowed.

Two earlier interventions also produced diagnostic errors worth keeping:
`DDERR_INVALIDRECT (0x88760096)` when blitting screen coordinates into an 800x600 surface, and
`DDERR_SURFACELOST (0x887601C2)` when blitting from a bogus pointer — the latter is the exact
code `FUN_10019a77`/`FUN_10019be8` retry on.

### Probe bug found and fixed

`GetEnvironmentVariableA` was being read into a `char[32]` while the value was 62 chars. On
overflow the API leaves the buffer **undefined** and returns the required size, so the table
loaded in one run and was silently skipped in the next — which produced an all-zero fullscreen
column and nearly caused a false conclusion. Now queried straight into `MAX_PATH`.

---

## 10m. The device object dissected — render/present raster aliasing `[CONFIRMED 2026-08-16]`

Following §10l (the draw path is active), the blit destination was dissected field by field.
All of this is in-process memory reading; no screen capture is involved, so window z-order and
focus cannot corrupt it.

### The hot blit, decompiled

`FUN_10014894` @ `0x10014894` (34,764 calls in a 20 s windowed run):

```c
iVar2 = (**(code **)(*param_1 + 0x50))(local_c);          // source format; [+4] = bpp
if (*(int *)((int)this + 0x10) == *(int *)(iVar2 + 4))    // device bpp == source bpp?
    (**(code **)(**(int **)((int)this + 0x44) + 0x2c))(param_1[0x11], &dst, &src);
else
    (**(code **)(*(int *)this + 0x1d4))(param_1, &dst, &src, 0);   // format-converting path
```

So **`device+0x44` is the render raster object** and its vtable slot `+0x2c` is the rasterizer;
`param_1[0x11]` is the source's raster at the same offset. `device+0x10` is the device bpp.

### The device object, side by side

| Field | Fullscreen | Windowed |
|---|---|---|
| `+0x0C` | `0x07` | `0x0E` |
| `+0x10` bpp | **`0x10` (16)** | **`0x20` (32)** |
| `+0x24/+0x28` w/h | `0x320`/`0x258` (800x600) | same |
| `+0x3C` | `1` | `3` |
| `+0x44` render raster | `005AEA18` | `0056BCE0` |
| `+0x64..+0x70` | zeros | `270,107,590,35F` = **624,263-1424,863**, the window rect |
| `+0x80`, `+0x8C` | `0x101` | `0x001` |
| `+0xAC` | **`0`** | `0056BBD8` |
| **`+0xB0`** | **`005AEA18` — aliased to `+0x44`** | `0056BBD8` — **not** `+0x44` |

### The decisive measurement

Sampling the pixel buffers inside those raster objects:

```
FULLSCREEN   RENDER(+0x44)  bits at raster+0x04 = 0x0BECA6A8 : 5270/7500 LIT
             PRESENT(+0xB0) bits at raster+0x04 = 0x0BECA6A8 : 5270/7500 LIT   (same buffer)

WINDOWED     RENDER(+0x44)  bits at raster+0x30 = 0x05C47000 : 0/7500 LIT
             PRESENT(+0xB0) : no pixel buffer found
             ALT(+0xAC)     : no pixel buffer found
```

**Fullscreen has one raster, holding the live frame, serving as both render target and present
source.** Windowed has a render raster of a *different class* (its bits live at a different
field offset), which is **empty**, and a present raster with **no pixel buffer at all**.

### Reading

The windowed device is constructed with raster objects that have no usable backing store, so
the 34,764 blits per run have nowhere to land. This is a deeper structural difference than the
present call (§10h) or the pixel format (§10k) — those were symptoms of the same thing:
`FUN_1001611b` builds a windowed device whose raster chain was never completed.

`[UNCERTAIN]` — why the windowed raster class differs and whether it can be substituted.
The device bpp difference (16 vs 32) is entangled with it, since `-bpp 32` is required for
windowed to survive Init (§10c) and the fullscreen device is 16bpp.

### Cost note

Windowed mode has now consumed the majority of this session across ~10 rounds, with four
falsified hypotheses (present gate, clipper, blit geometry, window origin) and three retracted
conclusions (§10d, §10j, plus the §10.1/§10.2 measurement errors). The knowledge gained is
real and documented; the feature is not delivered. Anyone resuming this should read §10h,
§10k, §10l and §10m together before touching code.

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

---

## 12. Windowed mode: the intro VIDEO renders; the game still does not (2026-08-16)

**AMENDED. The first version of this section claimed windowed mode worked and retracted the
§10h root cause. That was wrong and is withdrawn.** What renders in windowed mode is the
intro movie, which blits itself to the primary surface. The game's frame loop presents via
Flip on a device whose `this+8` (render target) is NULL, so after the video ends the client
area goes black and the menu never appears. Confirmed by the user: "video still half width,
video played, then black".

**The error, recorded because it is the reusable lesson:** I saw the video appear in the
client area and concluded the present path worked. Video rendering is not evidence that the
game renders - they are different paths. A correct conclusion (§10h, U-023/U-024) was
retracted on the strength of one screenshot. Before treating any visual as proof that a
subsystem works, establish WHICH path drew it.

What survives is the placement constraint in §12.2, which is independently established and
was measured across four placements.

### 12.1 Invocation that shows the video

```
re\harness\bin\sc3launch.exe -nocom -windowed -origin
```

Produces a real top-level window titled "SimCity 3000" with a normal caption and border, and
the intro video plays inside the client area. The GAME does not render - black after the
video. Useful as a test vehicle, not as working windowed mode.

`-nocom` remains mandatory (§10e): any IDirectDraw vtable patching breaks rendering, because
the `DWM8And16BitMitigation` shim owns that dispatch.

### 12.2 The constraint: the window must lie inside the PRIMARY display

Four placements tested, same build, same switches otherwise. Monitor layout as the game
process sees it (logged by `log_monitors()`, DPI-virtualised space):

```
MONITOR 1:     0,0     2048x1152   (primary)
MONITOR 2:  2560,155   1920x1080
MONITOR 3: -2560,-1    2048x1152
```

| Window pos | Inside primary? | Result |
|---|---|---|
| `0,0` (`-origin`) | yes | **video visible in the client** (game still black afterwards) |
| `-3,-26` (client aligned to 0,0) | no, negative | black, every run |
| `-2560,-1` (monitor 3) | no | black |
| `2560,155` (monitor 2) | no | black - sound plays, in-game cursor draws, zero pixels |

Positive coordinates are NOT sufficient: `2560,155` is positive and still black. The
discriminator is containment in the primary display. This is consistent with the destination
being the DirectDraw **primary surface**, which spans only the primary monitor; a destination
rect outside it is discarded rather than clipped.

`[CONFIRMED - empirical, 4 placements]`

Two corollaries, both counter-intuitive enough to be worth stating:

- The game's own `CreateWindowExA(pos=-3,-26)` puts its CLIENT at 0,0 - but "correcting" the
  placement to preserve that (window at `-3,-26`) renders black. The engine anchors to the
  WINDOW rect, not the client rect. Do not re-apply the client-alignment "fix"; there is a
  do-not-fix-again comment at `h_MoveWindow` in `sc3probe.c`.
- The game centres itself via `MoveWindow(621,237)` immediately after creation. That position
  is inside the primary, so the stock centring is fine; it was my repositioning that broke it.

### 12.3 Remaining defect: video draws at half width

The intro video occupies 320x480 logical of the client, right-hand half black, colours
otherwise correct. Half width with correct colour is the signature of a bytes-per-pixel
mismatch: a row's byte count computed at 16bpp (640 px x 2 = 1280 B) written into a 32bpp
surface fills only 320 px, leaving the rest untouched.

Measured since: device init `FUN_10009efb` receives `[800, 600, 4, 16]` - **bpp 16**
`[CONFIRMED @0x10009efb]` - and it is 16 in fullscreen too, so 16bpp is the game's normal
configuration, not a windowed anomaly.

**`-bpp 32` never reached this call.** The GZGraphicD call site at `0x1001626B` (inside
`FUN_1001611b`) receives 16 with and without the switch, because the value arrives via
`param_1[4]` rather than a literal. Every §10b conclusion drawn from `-bpp 32` was therefore
testing nothing. The causal link between bpp and the half width is NOT established. See
U-025-AMENDED; parked as cosmetic next to the missing render target.

### 12.4 Framebuffer memory-diff hunt: closed, negative

The §10-era hunt dumped changed regions at an ASSUMED pitch (800*bpp/8). A wrong stride makes
a real framebuffer look like horizontal-striped noise, so "noise" was not conclusive. Replaced
the assumption with measurement: `lag_mad()` scores mean |p[i]-p[i+lag]| over lags 512..6144,
and scanline data must produce a deep narrow minimum at the true pitch.

Result across every changed region: best candidate 53% of baseline, most 99%. No sharp
minimum anywhere. These regions are not scanline images. The hunt is closed with evidence
rather than with exhaustion, and `fb_scan()` remains as a reusable negative test.

### 12.5 New switches

| Switch | Effect |
|---|---|
| `-origin` | move the game WINDOW to 0,0 (window origin, deliberately not client origin) |
| `-at X,Y` | force the window to explicit coordinates, applied inside the centring `MoveWindow` |

`-at` replaced an earlier `-monitor N`: `EnumDisplayMonitors` index order need not match what
a user calls "monitor 2", and a wrong guess costs a full run. The probe now logs the monitor
layout on every start, so `-at` values can be read straight from the log.

---

## 13. The present function fully decoded; the guard is a lock (2026-08-16)

### 13.1 Instrument fixed first

`-winpresent` implies `-present`, and `install_tracer` had a guard on only one of its two
call sites, so it ran twice. The second pass re-scanned functions already carrying our own
5-byte JMP, reported every one as `UNRECOGNISED prologue E9 ...`, and printed
**`0/15 detours installed` for a run whose detours were in fact live**. Any conclusion drawn
from that log about call counts is void. `install_tracer` is now idempotent; the same run now
reports 13-14/15.

Also void: an earlier claim that the present "runs 3 times then stops". That was the probe's
own `n <= 3` log throttle, not the game.

### 13.2 The present, byte-exact

`0x10016BF1` has NO direct callers anywhere in GZGraphicD. It is reached only through a vtable
pointer at `0x1001F2C0` (sibling `0x10016BDE` at `0x1001F2C8`); those are the only two
references to that address range in the whole image `[CONFIRMED - byte scan of the DLL]`.

```
0x10016BF1  8B C1        mov  eax, ecx
0x10016BF3  56           push esi
0x10016BF4  33 C9        xor  ecx, ecx
0x10016BF6  39 48 1C     cmp  [eax+0x1C], ecx    ; GUARD
0x10016BF9  75 44        jne  +0x44              ; guard != 0 -> skip everything
0x10016BFB  38 48 15     cmp  [eax+0x15], cl     ; GATE
0x10016BFE  74 0C        je   +0x0C              ; gate == 0 -> skip present
0x10016C00  8B 40 44     mov  eax, [eax+0x44]
            ...          call [edx+0x38]         ; slot 14 = FUN_10018dd9
```

Prologue is exactly 5 bytes on an instruction boundary, so the detour placement was correct
all along.

**There are TWO gates, and `-present` only ever patched the second one.** The guard at
`+0x1C` is tested first, and the trace shows it becoming 1. That is why every `-present` run
turned the client white but produced no frame: it was clearing a branch the code never
reached.

### 13.3 The guard is a lock - bypassing it hangs the game

Patching `0x10016BF9 75 44 -> 90 90` as well: the game **hangs** at ~1.15 s. The probe log
stops dead at 1151 ms with no further periodic reports, and the on-screen image freezes while
sound keeps playing. `[CONFIRMED - empirical]`

So `this+0x1C` is a busy/re-entrancy lock, not a windowed-mode flag. Bypassing it re-enters
the present and deadlocks. **Do not patch it.** The patch remains in `patch_present_gate` but
this note is the reason it must not be treated as a fix.

### 13.4 The present's caller is the intro movie player

Trace: `PresentFn hit#1 ret=0x0042A207`, `hit#2 ret=0x0042A232` - **SC3U.exe addresses**, both
inside `FUN_00429f95`, which loads `Res/UI/Shared/Movies/Intro.tgq`. That function sets the
movie size explicitly:

```c
(**(code **)(**(int **)((int)param_1 + 0xa8) + 0x44))(0x280, 0x1e0);   // 640 x 480
```

`[CONFIRMED @0x00429f95]`

This is a hard anchor for U-025: the movie source is **640x480** and it displays **320** wide -
a factor of exactly 2, not an eyeballed estimate from a screenshot. It also explains why the
video appears while the game does not: both use the same device vtable, and the movie player
drives the present itself.

Runtime vtable dump confirms the dispatch: `obj(+0x44)` slot 14 (+0x38) = `GZGraphicD+0x18DD9`
= `FUN_10018dd9`.

### 13.5 Where U-024 now stands

Unchanged in substance: the windowed device still has no render target. What is new is that
the two gates are understood, one of them must not be touched, and the present's only driver
found so far is the movie player. The open question is what drives the present after the movie
ends - in fullscreen something calls it ~105x/s, and that caller has not been identified.

---

## 14. The renderer is SUSPENDED by the intro movie and never resumed (2026-08-16)

### 14.1 The suspend counter

`0x10016BDE`, the vtable slot next to the present (`0x1001F2C8` vs `0x1001F2C0`), decodes to:

```
8B 44 24 04    mov  eax, [esp+4]
01 41 1C       add  [ecx+0x1C], eax      ; delta
79 04          jns  +4
83 61 1C 00    and  [ecx+0x1C], 0        ; clamp at zero
8B 41 1C       mov  eax, [ecx+0x1C]
C2 04 00       ret  4
```

`this+0x1C` is a **suspend counter** - `Suspend(+1)` / `Resume(-1)` with a clamp - not a lock.
The present at `0x10016BF1` tests it FIRST (`jne` at `0x10016BF9`) and skips the whole frame
while it is non-zero.

This also explains §13.3: nopping that branch forces presents during a suspended state, which
is why the game hung. **The counter must be respected, not bypassed.**

### 14.2 One increment, zero decrements

Detoured at `0x10016BDE` (prologue is 4+3 = 7 bytes; a 5-byte steal splits the `add`, which is
why it was skipped as "UNRECOGNISED prologue" until `prologue_len` learned the pattern).

Whole 40 s windowed run:

```
SUSPEND #1  delta=+1  count(before)=0  this=0x00549D5C  ret=SC3U 0x2A298
SuspendCnt  sub_10016bde   total hits: 1
```

**Exactly one call. One increment. No decrement, ever.** `[CONFIRMED @0x10016BDE]`

`0x0042A298` is inside `FUN_00429f95`, the intro movie player, and matches:

```c
if (local_11 != '\0') {
    *(undefined4 *)((int)param_1 + 0xac) = 1;
    (**(code **)(**(int **)((int)param_1 + 0xb4) + 0x38))(1);   // Suspend(+1)
```

So the movie player suspends the renderer while the movie plays - correct behaviour - and the
matching `Resume(-1)` never runs. That accounts for every symptom: the video draws (the movie
player renders itself), then the client is black forever, sound keeps playing, game logic stays
alive, and the present is polled ~3M/s while exiting at the guard every time.

### 14.3 Status of the intervention: BUILT, NOT YET VERIFIED

`-resume` clears the counter from the watcher thread once past the intro. Writing 0 is a valid
resume because the field is a plain int clamped at zero, so no synthetic `__thiscall` is needed
and nothing is bypassed - the present still honours its gate.

**It has never actually run.** The `SC3PROBE_RESUME` / `SC3PROBE_GUARD` environment reads were
missing from the probe, so `g_resume` was 0 in every run so far; any run labelled `-resume`
before this fix was a plain windowed run. Do not read those runs as evidence either way.

### 14.4 Open: the second gate

Even with the suspend cleared, `gate(+0x15)` is independently 0 in windowed mode (§10h: no flip
chain -> flipping flag 0). Both blockers are real and may both need addressing. Whether clearing
the suspend alone is enough is exactly what the unverified `-resume` run would answer.

### 14.5 RETRACTION of 14.2 - the renderer IS resumed

**§14.2's claim "one increment, zero decrements, the renderer is never resumed" is WRONG.**

Re-run with the tracer AND the movie trace table loaded together:

```
SUSPEND #1  delta=+1  count(before)=0  this=0x00588DD4  ret=SC3U 0x2A298   (movie start)
SUSPEND #2  delta=-1  count(before)=1  this=0x00588DD4  ret=SC3U 0x2A35F   (movie stop)
```

`0x0042A35F` is inside `FUN_0042a31a`. The counter returns to 0. Suspend and resume are
correctly paired `[CONFIRMED @0x10016BDE]`.

The earlier "1 hit" reading came from a single run whose intro movie ended outside the window
I was looking at; I generalised one observation into a root cause. Same failure mode as the
§12 retraction: treating one run as proof.

**What the same log shows instead:** `gate(+0x15)=0` on every present sample, before and after
the movie. The persistent blocker is the flipping flag, exactly as §10h said - not the suspend
counter. `FUN_0042a31a` and the whole movie state machine are working correctly.

Still standing from §14: `this+0x1C` is genuinely a suspend counter and not a lock, so §13.3's
"do not nop that branch" holds - nopping it forces presents during a legitimately suspended
state, which is why it hung.

Also measured: `movie_tick` = **0 hits** while `movie_state_dispatch` = 11,468,424. The movie
goes start -> stop without a single tick, i.e. the first frame draw returns false and it takes
the failure path that posts message `(5, 0x1B)`. That is a real anomaly and is NOT explained.

---

## 15. Windowed present pipeline now WORKS; the source surface is empty (2026-08-16)

### 15.1 A harness bug invalidated §10i

`g_render_obj` - the variable `present_hook` reads to find its Blt source - was **declared and
read but NEVER ASSIGNED**. The entire "windowed present via Blt" path from §10i was dead code:
every frame fell straight through to the failing Flip. **§10i's failure verdict was never a
test of the idea.** Now populated from the first `FUN_10019273` surface matching the requested
mode.

Two further harness defects fixed in the same pass:
- the reshape block was left disabled (`if (0)`) after the §10i crash, and it was the only
  thing that set `g_primary_w`, so the DPI correction silently never applied;
- the `src` sampling dereferenced `this+8` which is NULL windowed.

### 15.2 The pipeline is now correct end to end

With the gate forced open (`-present`, implied by `-winpresent`):

```
Flip FUN_10018dd9                                    16208 hits   (present reaches slot 14)
WINPRESENT: primary is 2560 px wide (physical)
DPI scale 1.250 (primary 2560 / logical 2048)
engine-fb Blt: src=0x03B46050 -> dest 3,32-1003,782  hr=0x00000000 [DD_OK]
```

Destination `3,32-1003,782` = 1000x750 physical = exactly 800x600 logical, i.e. the client
rect. The Blt succeeds every frame. `[CONFIRMED - empirical]`

This is the first time the windowed present has had a valid source, a valid destination and a
succeeding blit simultaneously.

### 15.3 But the source has no content

```
BLT SOURCE #3:   800x600 32bpp pitch=3200   0/7500 lit
BLT SOURCE #200: 800x600 32bpp pitch=3200   0/7500 lit
```

Screen result: intro video plays, then black - unchanged.

So the remaining problem is NOT presentation. It is that **the engine does not draw into the
surface we adopted**. Candidate selection is a guess: we take the first `FUN_10019273` surface
whose dimensions match the requested mode, and a second 800x600 candidate appears later
(`0x0F1F4F90`), so dimension-matching does not identify the frame buffer.

This lands back on the same question §10-§11 failed to answer: WHERE does the engine draw?
The difference is that everything downstream of that surface is now known-good, so the
question is finally isolated - find the surface with content and the picture appears.

Next: sample every candidate's lit-pixel count and adopt whichever has content, rather than
adopting by dimensions. The blit dispatcher `FUN_10014894` runs ~34k times per windowed run,
so the engine IS drawing somewhere.

### 15.4 The render raster's backing surface is also empty

Pointed the present at the blit dispatcher's real destination: `device+0x44` (render raster),
whose `+0x04` is the backing surface.

```
DRAW OBJ 0x005486D8   bpp(+0x10)=32  w=800 h=600
  RENDER(+0x44)  obj=0x00568CB0  vt=GZGraphicD+0x1F0AC  bits=0x03B3C080  800x600 pitch=3200
  PRESENT(+0xB0) obj=0x00568BA8  vt=GZGraphicD+0x1F628  bits=0x03B3C060  0x0 pitch=0  EMPTY
```

Note `bpp(+0x10) = 32` on this device - NOT the 16 seen at `FUN_10009efb` init. Different
object; this is why the 16bpp theory never fitted.

No "switched" line was logged, i.e. the raster backing and the dimension-matched candidate are
the SAME surface. And it stays empty at every sample point:

```
BLT SOURCE #3 / #200 / #1000 / #3000 / #8000:  800x600 32bpp pitch=3200   0/7500 lit
```

while the engine is demonstrably blitting:

```
blt_disp_1    158931
blt_convert      882
setpixel_a         0
```

**158,931 blits and the destination surface reads all zeros.** So the engine's blits do not
land in the surface at `raster+0x04`, or a Lock on it does not observe what they write. That
is the single remaining unknown; everything downstream (gate, present, source selection,
destination rect, DPI, Blt) is now measured and correct.

`PRESENT(+0xB0)` being 0x0 with pitch 0 remains true and matches §10m: windowed builds two
rasters and leaves the present one unsized.

Next candidate lines of attack, in order of cost:
1. Determine which branch of `FUN_10014894` runs (hardware `raster->vt[0x2c]` vs converting
   `device->vt[0x1d4]`), and for the hardware branch dump what `raster->vt[0x2c]` does with
   `param_1[0x11]` - that is the actual pixel writer.
2. Log the `dst` rect and destination pointer passed to those calls; the engine may be
   drawing into a scratch surface that is later composited.
3. Compare all of the above against a fullscreen run, where the same dispatcher feeds a
   surface that demonstrably ends up on screen.

### 15.5 The pixel writer is a DirectDraw Blt - and its result is unmeasured

`FUN_10014894` takes the HARDWARE branch: `raster->vt[0x2c]` = `FUN_10018C58`, the same
function in BOTH raster classes (`0x1001F0AC` windowed and `0x1001F5C0` fullscreen share
slots `+0x2C/+0x30/+0x34`).

```
blt_disp_1        34223
raster_blit_hw    33342      <- the hardware path does the work
raster_slot30         0
raster_slot34         0
blt_convert         882
```

`FUN_10018C58` @`0x10018c58`:

```c
iVar1 = (**(code **)(**(int **)((int)this + 4) + 0x14))     // this+4 = dest surface, slot 5 = Blt
          (dstSurface, param_3 /*destRect*/, param_1[1] /*srcSurface*/,
           param_2 /*srcRect*/, param_1[0x37] /*flags*/, param_1 + 0x1e /*fx*/);
if (iVar1 == -0x7789fe3e) {          // 0x887601C2 = DDERR_SURFACELOST
    ... vt+0x60 (restore) then retry the same Blt once ...
}
if (iVar1 == 0) return 1;            // success
... failure path via PTR_FUN_1001f058 / PTR_FUN_1001f064 ...
```

So the engine blits sprite surfaces into `raster+0x04` - **exactly the surface we sample** -
33,342 times, and that surface reads `0/7500 lit`.

**Critical caveat on the evidence: the tracer counts CALLS, not successes.** 33,342 hits is
equally consistent with 33,342 failed Blts. The function has an explicit `DDERR_SURFACELOST`
branch, so wholesale failure is an anticipated state, and nothing measured so far distinguishes
"blits succeed but we sample the wrong buffer" from "blits all fail". Do not assume the former
as §10d once did.

Next step, and it is a single measurement: capture the Blt's HRESULT. The entry-only tracer
cannot do it, so either detour the return, or from the watcher call `IsLost` (surface vtable
slot 24, `+0x60`) on `raster+0x04` and log it. If the surface is lost, that is the whole
answer and it is also a plausible consequence of the windowed cooperative level.

### 15.6 Surfaces are healthy, the sampling is valid, the engine's blits produce nothing

Three measurements, in order, each closing a hypothesis:

**1. The surfaces are not lost.**
```
SURFACE STATE #3/#200/#1000/#3000/#8000:
    dest IsLost=0x00000000 [DD_OK]   primary IsLost=0x00000000 [DD_OK]
```
`IsLost` is surface vtable slot 24 (`+0x60`) - the same slot `FUN_10018C58` calls in its
`DDERR_SURFACELOST` retry, which confirms the index. DDERR_SURFACELOST is NOT the cause.

**2. It is not the wrong surface.** Census of every DISTINCT `this` at the blit dispatcher
(the first is not necessarily the frame buffer - the engine makes 49 offscreen surfaces):
```
DEST[0] dev=0x00589258 surf=0x03B54480  800x600 32bpp  0/7500 lit   <- presented
DEST[1] ...  147x29 32bpp  0/76 lit
DEST[2] ...  150x29 32bpp  0/76 lit
DEST[3] ...  146x29 32bpp  0/76 lit
DEST[4] ...  130x29 32bpp  0/68 lit
DEST[5] ...  160x29 32bpp  0/80 lit
DEST[6] ...  234x29 32bpp  0/120 lit
DEST[7] ...   49x29 32bpp  0/28 lit
```
The 29-pixel-tall surfaces are UI text/button targets. **Every** destination is empty, so this
is not a selection error.

**3. The sampling method is valid.** Colour-fill the destination ourselves via
`Blt(DDBLT_COLORFILL|DDBLT_WAIT)` and read it back:
```
ROUND-TRIP: our ColorFill hr=0x00000000 [DD_OK] -> 7500/7500 magenta read back
```
`Lock` DOES observe `Blt` writes. The surface is real, writable, and correctly sampled.

**Conclusion:** the engine calls `FUN_10018C58` 33,342 times, the surfaces are healthy, our own
blits to the same surface work - and the engine's blits deposit nothing. The tracer counts
calls, not results, so the outstanding measurement is the HRESULT the engine's `Blt` returns
(or whether its SOURCE surfaces are themselves empty, in which case the blits succeed and
faithfully copy black).

Two candidates, both cheap:
1. Sample the SOURCE surface of the engine's blits (`param_1[1]` in `FUN_10018C58`) the same
   way we sampled destinations. If sources are empty, the failure is upstream of blitting
   entirely and nothing about DirectDraw is at fault.
2. Capture the engine Blt's return value - needs a return-capturing detour, which the
   entry-only tracer cannot do.

Do (1) first: it reuses the census machinery and needs no new detour mechanics.

### 15.7 The SOURCES are empty too - the failure is upstream of presentation

Sampled the source surface of every engine blit (`param_1[1]` in `FUN_10018C58`):

```
SRC[0] surf=0x0C0288C0  147x29 32bpp  0/296 lit
SRC[1] surf=0x0C028960  150x29 32bpp  0/304 lit
SRC[2] surf=0x0C028A20  146x29 32bpp  0/296 lit
SRC[3] surf=0x0C028BA0  130x29 32bpp  0/264 lit
SRC[4] surf=0x0C028BC0  160x29 32bpp  0/320 lit
SRC[5] surf=0x0C028C00  234x29 32bpp  0/472 lit
SRC[6] surf=0x0C028C20   49x29 32bpp  0/104 lit
```

Their dimensions match the destinations exactly, and they are menu button captions.
**Every source is blank.** The engine is blitting empty surfaces onto empty surfaces.

So DirectDraw is behaving correctly throughout: healthy surfaces, working blits (our own
ColorFill round-trips), and faithful copying of nothing. **The windowed failure is upstream of
presentation entirely - whatever rasterises content into those surfaces produces no pixels.**
Note also that no 800x600 surface appears as a blit SOURCE, so the main frame buffer is never
a source; only UI element surfaces are.

This re-frames the whole of §10-§15. The chain gate -> present -> blit -> surface is now fully
measured and correct; the missing step is earlier, where glyphs/sprites should be drawn into
those small surfaces and never are.

Likely connection, NOT yet evidence: §10m established that fullscreen uses raster class
`0x1001F5C0` (memory-backed) and windowed uses `0x1001F0AC` (DirectDraw-surface-backed). If
the software drawing routines write through a memory pointer at `raster+0x04`, that field
holds a COM surface pointer in the windowed class, so drawing has nowhere valid to go.
`setpixel_a` trace = **0 hits** in windowed, which is consistent with the drawing routines
never running at all - but 0 hits is equally consistent with the game simply using a different
routine, so this must be tested, not assumed.

Next: trace the drawing entry points on both raster classes (`0x1001F0AC` vs `0x1001F5C0` slot
by slot) and compare hit counts windowed vs fullscreen. The fullscreen run is the control that
has been missing from every comparison in this section.

### 15.8 Fullscreen control: the traced path is WINDOWED-ONLY

Same instrumentation, fullscreen, 40 s:

```
blt_disp_1..8        0      blt_convert          0
raster_blit_hw       0      setpixel_a/b         0
getpixel_a           7      gate16_a/b/c         0
size_arith           0      vidmem_calc          0
window_create        1      restyle_fullscreen   1   restyle_windowed  0
```

Fullscreen renders perfectly while **every** drawing function in `gz_draw.txt` sits at zero.
So `FUN_10014894`'s dispatcher family and `FUN_10018C58` are a **windowed-only code path**;
fullscreen renders through a mechanism this table never touches. `size_arith` = 0 confirms it
(that is the windowed device builder).

Consequence for method: there is NO working baseline for these functions. They run only in the
mode that fails, so "compare windowed against fullscreen" - the approach assumed throughout
§10-§15 - cannot validate them. Every hit count collected for them is unopposed.

### 15.9 Where this actually lands

Measured and correct in windowed mode: window creation and style, placement (must be inside
the primary display), the suspend/resume pairing, the present gate, the present call reaching
slot 14, the render-target selection, the destination rect with DPI correction, and the final
Blt returning DD_OK. Our own ColorFill into the engine's own destination surface round-trips
perfectly.

Measured and empty: every blit destination, and every blit source. The engine runs a windowed
compositing path 33,342 times per run that moves blank surfaces onto blank surfaces.

Taken together this is renewed - and much better evidenced - support for the ORIGINAL §10f
verdict: **SC3U's windowed path exists, executes, and was never finished.** The difference is
that the earlier verdict rested on "the present is never called", which turned out to be a
half-patched gate; this one rests on the content pipeline itself producing no pixels while
every downstream stage is proven functional.

That is a claim about a shipped code path, so it should be held provisionally until someone
finds where those small UI surfaces are supposed to be filled and shows that it does not run.

### 15.10 The UI labels are not drawn with GDI

Traced windowed, 45 s:

```
text_TextOutA      0        (SC3U FUN_0045fcd4, the only TextOutA call site)
text_CreateFontA   0        (SC3U FUN_0045fb17, the only CreateFontA call site)
getdc_a/b/d        1 each
getdc_c           74        <- FUN_10017e2f
```

SC3U does contain a GDI text renderer (`FUN_0045fcd4` / `FUN_0045fb17`) but it **never runs**,
so it is not what fills the 29-pixel-tall label surfaces.

`FUN_10017e2f`, the only busy `GetDC` site, is the **window procedure** - it dispatches
`WM_CHAR` (0x102), `WM_LBUTTONUP` (0x202), `WM_MOUSEWHEEL` (0x20a) and uses `PAINTSTRUCT`. Its
74 hits are window messages, not drawing. None of the four `GetDC` sites render text.

So the UI labels must be filled by the engine's own glyph/sprite blitter (bitmap fonts from
`Res/`), which has not been located. That is the next thread: `SIMSPR`/`GZGraphicD` sprite
draw entry points, traced windowed, to find which one should be writing into a 147x29 surface
and is not.

### 15.11 Housekeeping still outstanding

`Apps\DDrawCompat.ini`, `Apps\DDrawCompat-SC3U.log` and `Apps\ddraw.dll.off` are left over from
the DDrawCompat experiment. `Apps\` is GAME content and must not hold RE artifacts (CLAUDE.md).
They are inert (`ddraw.dll` is renamed `.off`, so it does not load) but they should be removed.

### 15.12 The engine locks the label surfaces, writes, unlocks - and they stay empty

Full sweep of the windowed raster vtable `0x1001F0AC` (22 slots), traced windowed 45 s:

```
slot  1  0x10019470   13      slot  3  0x10018A82   39   <- Lock
slot  4  0x10018B53   39      <- Unlock                  slot  5  0x100194EC   52
slot  6  0x100197D9    4      slot 11  0x10018C58  33342 <- hardware Blt
slot 21  0x100195CC   23
slots 2, 7, 8, 9, 10, 17, 18, 19: 0 hits
```

`FUN_10018A82` locks with flags `0x801` (`DDLOCK_NOSYSLOCK|DDLOCK_WAIT`); `FUN_10018B53`
calls surface `vt+0x80` (index 32 = `Unlock`) and maintains a lock count at `+0xE4`. They are
an exactly matched Lock/Unlock pair, 39 and 39.

39 pairs in 45 s is not per-frame drawing - it is once per UI element at construction, which
fits 7+ label surfaces plus other elements.

**So the engine DOES lock each label surface, write through the returned pointer, and unlock -
and the surface still reads 0 lit afterwards.** Combined with §15.6 (our own ColorFill into the
same surface round-trips perfectly) this narrows the fault to the locked-pointer write path
specifically, not to DirectDraw generally.

One hypothesis this raises, explicitly NOT yet evidence: if `Lock` returns a system-memory
shadow for a video-memory surface and the contents are not propagated on `Unlock`, the engine's
writes would vanish exactly like this, and it would be a fault in the DirectDraw emulation
layer (the `DWM8And16BitMitigation` shim) rather than in SC3U. That would also explain why the
identical drawing code is untroubled in fullscreen, which §15.8 showed uses a different path
entirely.

Testing it is a single measurement and does not need the game: lock one of these surfaces
ourselves, write a known pattern through the returned pointer, unlock, then re-lock and read
back. If our own write survives, the shim is exonerated and the fault is in what the engine
writes. If it does not survive, the emulation layer is the answer and no amount of SC3U-side
work will fix windowed mode.

### 15.13 RECONCILIATION: the suspend/resume is NON-DETERMINISTIC

§14.2 measured `+1` with no `-1` ("never resumed"). §14.5 retracted it after measuring `+1`
then `-1`. **Both measurements were correct. The behaviour varies between runs of the same
build.**

Recent runs (`sanity2.log`): `SUSPEND #1 delta=+1` at 1143 ms, no matching `-1`, and
`blt_disp_1 = 0` for the whole session - the engine never draws anything.
Earlier run (`movie_win2.log`): `+1` at 1770 ms, `-1` at 3778 ms, counter back to 0, and
`blt_disp_1` in the tens of thousands.

So there are two distinct windowed outcomes:

| Outcome | Resume | blt_disp_1 | What is on screen |
|---|---|---|---|
| A | happens | ~34k-159k | video, then black (blits run, surfaces empty) |
| B | does NOT happen | 0 | video, then black (nothing draws at all) |

They look identical on screen, which is why they were never separated. **Every measurement in
sections 14 and 15 must be re-read with this in mind: a run showing 0 hits for a drawing
function may be outcome B, where nothing draws at all, rather than evidence about that
function.** In particular the fullscreen control (§15.8) and the raster slot sweep (§15.12)
were single runs and are not safe until repeated.

Methodological correction for this whole investigation: single-run measurements are not
evidence here. Anything load-bearing needs N runs with the outcome classified by whether the
resume fired.

This also makes `-resume` (§14.3) worth testing after all - it targets outcome B specifically,
and it has still never actually executed.

### 15.14 CORRECTION to 15.13: not non-determinism - THE PROBE PERTURBS THE GAME

§15.13 called the suspend/resume "non-deterministic". That is wrong. The outcome correlates
perfectly with whether the surface-sampling code was present in the build:

| run | +1 | -1 | blt_disp_1 | sampling code |
|---|---|---|---|---|
| `draw_dest.log`  | 1 | 1 | 16504  | no |
| `win_blt7.log`   | 1 | 1 | 158931 | no |
| `movie_win2.log` | 1 | 1 | -      | no |
| `wp1..3.log`     | 1 | 0 | 0      | YES |
| `rep1..6.log`    | 1 | 0 | 0      | YES |

9 of 9 runs WITH the sampling code: no resume, zero drawing. Every run WITHOUT it: resume
fires, tens of thousands of blits. The resume is the discriminator and the sampling is the
cause.

Mechanism: the probe calls `Lock` / `IsLost` on the engine's own surfaces from the watcher and
present threads while the engine locks them itself with `DDLOCK_NOSYSLOCK`. Contending for
those locks makes the engine's own operations fail, the intro movie never completes normally,
`Resume(-1)` never runs, and nothing draws.

**Consequences - these invalidate measurements in this document:**

1. Every `0/7500 lit` and `0/296 lit` reading in §15.3, §15.5, §15.7 was taken by code that
   also suppressed the drawing. **"The surfaces are empty" is not established.** They may be
   empty *because we were sampling them*.
2. The fullscreen control (§15.8) and the raster slot sweep (§15.12) ran with sampling active
   and must be repeated without it.
3. §15.9's conclusion - "the windowed path executes but was never finished" - loses its main
   support and is **withdrawn** pending re-measurement.

What survives, because it was measured before the sampling code existed: the placement
constraint (§12.2), the two present gates and the guard being a counter (§13), `-bpp 32` never
reaching GZGraphicD (§12.3), the framebuffer pitch scan (§12.4), and the present pipeline
reaching a succeeding Blt with correct geometry (§15.2).

**Method rule for anyone continuing: do not Lock or query engine-owned DirectDraw surfaces
from a probe thread while the game is running.** Read pixel data only from memory the engine
is not concurrently locking, or accept that the act of measuring changes the result.

### 15.15 §15.14 IS ALSO WRONG - cause unknown, baseline not reproducible

Gated every surface Lock/IsLost behind `-sample` (default off) and re-ran 4x:

```
run 1..4:  +1 = 1,  -1 = 0,  blt_disp_1 = 0
```

Identical to the runs WITH sampling. **So the sampling was not the cause either, and §15.14's
correlation was coincidence** - every "no sampling" run in that table predated a batch of other
probe changes, so the two variables were confounded and I attributed it to the wrong one.

Current state: the working baseline (resume fires, tens of thousands of blits) **cannot be
reproduced**. It was present in `draw_dest.log`, `win_blt7.log` and `movie_win2.log` earlier
today and has been absent in 13 consecutive runs since, across several probe builds and flag
combinations, including builds with the added code disabled.

Not yet checked, and the obvious next candidates:
- game state held OUTSIDE the repo (registry keys, `%USERPROFILE%`/AppData settings) written
  during a session where the game was terminated ~40 times with `TerminateProcess`;
- `Apps\SC3U_stkdmp.txt` (14:43) shows the game crashed at least once today - it may have
  persisted a "safe mode" or damaged setting;
- a probe change outside the sampling block that has not been isolated (the `g_drawobjs` /
  `g_srcsurf` collection in `fnlog_enter`, or the `GetSurfaceDesc` on the primary in
  `present_hook`).

**Status of section 15: unsafe.** Its measurements were taken in a state that cannot currently
be reproduced, and two successive explanations for that (§15.13 non-determinism, §15.14 probe
perturbation) have each been falsified by the next measurement. Treat everything from §15.3
onward as unverified until the baseline is recovered.

The reliable way to recover it: `git stash` the probe source, rebuild from the revision that
produced `win_blt7.log`, and confirm the resume fires. If it does NOT, the cause is external
game state, not the probe, and that is where to look.

## 16. U-032 does NOT reproduce, and no reboot was needed (2026-08-16, late)

### 16.1 The result

Three consecutive runs of the prescribed command recovered. Same probe build
(`sc3launch.exe` / `sc3probe.dll`, both 21:58), same switches, same machine, **same boot
session** as the 16+ failing runs (last boot `2026-08-15 12:59:43`, uptime 1 d 10 h at the
time of the test - **the reboot prescribed as the first step was never performed**).

| run | log | instrumented | SUSPEND | `blt_disp_1` | `raster_blit_hw` |
|-----|-----|--------------|---------|--------------|------------------|
| iso1 | 21:59:04 | 33/33 | `+1` only | **0** | - |
| iso2 | 21:59:44 | 33/33 | `+1` only | **0** | - |
| iso3 | 22:00:25 | 33/33 | `+1` only | **0** | - |
| A | 22:54:06 | 33/33 | `+1` then **`-1`** | **23,911** | 23,030 |
| B | 22:57 | 33/33 | `+1` then **`-1`** | **32,578** | 31,698 |
| C | 22:58 | 33/33 | `+1` then **`-1`** | **37,903** | 37,023 |

Resume is `ret=SC3U 0x2A35F`, `args=[FFFFFFFF ...]`, `count(before)=1` -> back to 0
`[CONFIRMED @0x10016bde]`. Rule 1 is satisfied in every row: `33/33 instrumented`, no
`UNDECODABLE`/`UNRECOGNISED` line for any counted function. Rule 2 is satisfied: 3 runs, all
the same class.

The probe banners of `iso3` and `recover_A` are line-for-line identical - same two WINDOWED
patches, same PRESENT-GATE nop, PRESENT-GUARD not patched, same WINPRESENT detour, same three
monitors, same `2560x1440 @ 32 bpp, freq=165`. **Nothing under our control differs between the
failing class and the recovered class.** What differs is ~55 minutes of wall clock.

### 16.2 What this settles and what it does not

- **Settles:** U-032 is not a repo-side regression, and it is not persistent. It cleared
  without a reboot, a rebuild, or a revert.
- **Settles:** the suspend/resume pair is correct in windowed mode (this re-confirms
  U-028-RETRACTED and closes the "never resumed" reading for good).
- **Does NOT settle:** what the transient variable was. Nothing here identifies it, and
  because it cleared on its own it cannot be bisected after the fact. A run that shows `+1`
  with no `-1` should now be classified as **this transient**, not as a new defect, and
  re-run before anything is concluded from it.
- **Does NOT settle:** whether the game is visually correct. `blt_disp_1` rising is drawing
  activity, not a picture. The probe still cannot see the screen (§12/§15 rule 5), and
  `WINDUMP` still reports `[UNIFORM - capture produced no content]`, which is expected and
  means nothing either way.

### 16.3 Harness defect found while testing: relative log paths silently do nothing

`sc3launch` passes `-log` / `-gzlog` **verbatim** into `SC3PROBE_LOG` / `SC3PROBE_GZLOG`
(`sc3launch.c:155`, `:80`), and launches the game with its working directory set to
`<root>\Apps` (`sc3launch.c:144`, `:167`). The probe runs in-process, so a relative path
resolves against `Apps\`, where `re\harness\` does not exist. The result:

- `-log re\harness\recover.log` writes **nothing**, and `sc3launch.c:214` still prints
  `[*] log written: ...` unconditionally, without checking.
- `-gzlog re\harness\gz_draw.txt` cannot be opened, the probe logs
  `--- FNLOG: cannot open ... (err 2) ---`, and **every fnlog counter is then absent from the
  log** - including `blt_disp_1`.

**The command written in `HANDOFF.md` and used in this section's test therefore cannot produce
a measurement.** Always pass absolute paths. This is also a rule-1 trap of a new kind: not a
detour that failed to install, but a whole counter table that never loaded, which reads as
"the line is missing" rather than as an error.

Note `-gzlog` is an **input** trace table, not an output log. Do not rename or delete
`re\harness\gz_draw.txt`.

## 17. The present is NOT the problem: it blits, it succeeds, the source is empty (2026-08-16, late)

### 17.1 The counters that were missing

`g_blt_ok` / `g_blt_fail` were incremented at `sc3probe.c:2321-2322` and **never printed**, and
the `engine-fb Blt:` log line is capped at `if (n <= 3)`. So every previous reading of "3 blits"
was a log cap, not a count, and the true number of windowed presents had never been measured.
A `WINPRESENT` line was added to the 5 s summary. Measured, windowed, movie skipped by hand:

| run | t | `present_calls` | `blt_ok` | `blt_fail` | `blt_disp_1` | `raster_blit_hw` |
|-----|---|-----------------|----------|------------|--------------|------------------|
| D | +5 s | 1263 | 1263 | **0** | - | - |
| E | +5 s | 474 | 474 | **0** | - | - |
| E | +10 s | 3193 | 3193 (+2719) | **0** | 23,163 | 22,283 |

`33/33 instrumented` in both, suspend `+1`/`-1` paired in both.

### 17.2 What this rules out

**The windowed present path works and is not the blocker.** It runs 250-550 times a second,
every call returns `DD_OK`, and not one fails. Destination is `dest 3,32-1003,782` on the
primary. Simultaneously the engine is drawing hard: `blt_disp_1` 23,163 with
`raster_blit_hw` 22,283 tracking it.

So the engine renders ~23,000 times and the present blits ~3,200 times successfully, and the
client area is black (confirmed visually by the user: intro video plays, black after skipping).

### 17.3 What that leaves

The blit source is empty. `CANDIDATES (t+6s)` in run D:
`#1 obj=0x005A7B50 surf=0x03B36110 800x600 32bpp **0/7500 LIT**`. §15 asserted this on a
baseline that could not be reproduced; it is now re-established on a clean one (U-032 cleared,
33/33 instrumented, repeated runs).

**The open question is therefore a memory-identity question, not a present question: does
`raster_blit_hw` write into the surface that the present reads?** 23,163 engine blits and a
0/7500-lit source surface cannot both describe the same buffer. Next measurement: capture the
destination pointer of `raster_blit_hw` (`FUN_10018c58`) and compare it against the present's
`src` (`0x03B64F60` in run A, `0x03B36110` in run D - it is re-allocated per run, so compare
within a single run, never across runs).

Note `FBHUNT` in run E finds changed regions with plausible lit ratios
(`2354/4100`, `3155/7500`) - the engine's output exists in memory somewhere. §12.4 closed the
pitch-scan hunt negatively; this is a different question (identity of a known pointer), not a
re-opening of that scan.

## 18. ROOT CAUSE: every engine blit is DDBLT_KEYSRCOVERRIDE and ddraw returns E_NOTIMPL (2026-08-16)

### 18.1 The measurement

```
raster_blit_hw       3935        FUN_10018c58 entered
rasthw_throw         3935        error path @0x10018CDD taken -> 100.0%
rasthw_surfacelost      0        not DDERR_SURFACELOST
hr                   0x80004001  E_NOTIMPL  (one distinct code, all runs)
dwFlags              0x01010000  DDBLT_KEYSRCOVERRIDE | DDBLT_WAIT
DDBLTFX              dwSize=100  dwDDFX=0  dwROP=0  destCK=0..0  srcCK=0..0
engine_dest = present_src = 0x009F4840      SAME SURFACE
dest vtable          DDRAW.dll+0x7D120, slot5(+0x14) = DDRAW.dll+0x49C80
```

`35/35 instrumented`, no `UNDECODABLE`/`UNRECOGNISED` for any counted function.

### 18.2 How it was established

The two probe addresses come from a **real disassembly** of `FUN_10018c58` (capstone, over
`original\modules\GZGraphicD.dll`), not from the decompiled C:

```
0x10018C86  call dword ptr [ecx+0x14]     IDirectDrawSurface::Blt (index 5), result in eax
0x10018C89  cmp eax, 0x887601C2           DDERR_SURFACELOST -> retry path at 0x10018C90
0x10018CD9  test eax, eax / je 0x10018D0A success, al=1
0x10018CDD  (fallthrough)                 error path
```

`0x10018C90` and `0x10018CDD` are fallthrough-only - every branch target in the function is
`0x10018CA8`, `0x10018CC0`, `0x10018CD9`, `0x10018D06`, `0x10018D0A`, `0x10018D0C` - and both
have >=5 stealable bytes (6 and 7). At `0x10018CDD` the Blt's HRESULT is still in `eax`, which
is `f[8]` in the probe's `pushad`+`pushfd` frame.

The argument layout is confirmed at `0x10018C74-0x10018C86`: `lea ebx,[esi+0x78]` gives
`lpDDBltFx = param_1 + 0x1E` and `push [esi+0xdc]` gives `dwFlags = param_1[0x37]`.

### 18.3 What it means

The chain is now fully accounted for, and every earlier suspect is cleared:

1. the renderer resumes correctly (§16);
2. the engine composites into a surface, ~4-23k blits per run;
3. **every one of those blits fails with `E_NOTIMPL`, so the surface stays empty**;
4. the windowed present reads *that same surface* (pointer-identical) and Blts it to the
   primary 250-550 times a second, `DD_OK` every time (§17);
5. the client is black.

`E_NOTIMPL` is a flags complaint, not a surface or resource one: modern Windows DDRAW does not
implement `DDBLT_KEYSRCOVERRIDE`. The engine passes it on every blit with an override key of
`0..0`, i.e. treat black as transparent.

**This also explains the earlier "0/7500 LIT" source-surface readings (§15, §17.3) without
needing any of §15's retracted machinery: the surface is empty because nothing ever
successfully wrote to it.**

### 18.4 What is NOT established

- **Why fullscreen works.** Not measured. `blt_disp_1` (`FUN_10014894`) branches on
  `this+0x10 == srcfmt+4`, so fullscreen may take the software path and never reach
  `FUN_10018c58` at all. That is a hypothesis; the same counters run fullscreen would settle it
  and that run has not been done.
- **Whether removing the flag fixes it.** Two candidate directions, both untested: drop
  `DDBLT_KEYSRCOVERRIDE` (changes transparency semantics - black would stop being transparent),
  or force the software blit path. Neither should be called a fix until measured.
- `[UNCERTAIN]` whether the colour key `0..0` is meaningful or a zero-initialised DDBLTFX that
  the engine never fills because it expects the override flag to be honoured.

## 19. The E_NOTIMPL fix is real, necessary, and NOT sufficient (2026-08-16)

### 19.1 `-nokeysrc` works, measurably

Clearing bit `0x00010000` (`DDBLT_KEYSRCOVERRIDE`) in `param_1[0x37]` on entry to
`FUN_10018c58`, opt-in via `-nokeysrc`:

| counter | without | with `-nokeysrc` |
|---|---|---|
| `raster_blit_hw` | 3,935 | **473,220** |
| `rasthw_throw` | 3,935 (**100%**) | **1** |
| present `blt_ok` / `blt_fail` | 72 / 0 | 203,306 / **0** |
| captured `dwFlags` | `0x01010000` | `0x01000000` (DDBLT_WAIT only) |

The flag is cleared only **7 times** in a 60 s run - it lives on the raster object, not on
each blit. §18's diagnosis is therefore confirmed: `DDBLT_KEYSRCOVERRIDE` was failing every
blit, and removing it makes them succeed.

### 19.2 And the client is still black

Confirmed visually by the user: black for the whole run. With `-sample`, after 59,003
successful blits:

```
#1 obj=0x005A7F98  surf=0x03B4B628  800x600 32bpp   0/7500 LIT     <- the render target
#2 obj=0x0F2BBB80  surf=0x0C015188  147x29  32bpp   0/76   LIT     <- a blit SOURCE
```

`surf=0x03B4B628` is pointer-identical to the captured `dest_surface`, so this is the right
surface, sampled after tens of thousands of successful writes into it. **The blits succeed and
copy nothing, because the sources are empty too.**

So the failure has moved one level upstream: whatever is supposed to fill those source rasters
(e.g. the 147x29 one, a UI-sized element) is not doing so. `blt_convert` runs 882 times in
every run, which is the only other populated path in the table.

Meanwhile `FBHUNT` in the same run reports changed regions that look like real raster content:
`2686/4100`, `1836/4100`, `2407/7500` lit interpreted as 800x600x32. So the process does
contain drawn pixels somewhere - they are just not in these DirectDraw surfaces.

### 19.3 Status and cautions

- §18's root cause **stands** and `-nokeysrc` should stay on for all further windowed work: it
  converts a 100% blit failure into ~0%.
- The black client is now a **separate, upstream** defect: empty source rasters.
- `[UNCERTAIN]` the `0/N LIT` readings are Lock-based samples of every 8th pixel, counting
  `px & 0x00FFFFFF`. They would also read 0 for genuinely black content. Given `#2` is a
  147x29 UI element, black-on-black is implausible, but it has not been excluded.
- Unexplained: two `-nokeysrc` runs exited cleanly on their own (`code = 0`) at ~10.5 s and
  ~12.7 s, while a third ran the full 60 s. Not diagnosed, and NOT established as caused by the
  flag clear. Treat an early clean exit as this, and re-run.

## 20. The empty sources are real, not a sampling artifact — and they are UI sprites (2026-08-16)

### 20.1 Game-thread measurement

`sample_candidates` locks surfaces on a SEPARATE thread at t+6s, so an empty reading could be
an inter-frame clear. `probe_count_lit` (new) locks on the CALLING thread, inside the
`FUN_10018c58` detour, synchronous with the blit. First 6 blits, `-nokeysrc` on:

```
blit#1: SRC 0x0C040C28 147x29 32bpp lit=0   DST 0x0386CE10 800x600 32bpp lit=0
blit#2: SRC 0x0C040B28 150x29 32bpp lit=0   DST 0x0386CE10 800x600 32bpp lit=0
blit#3: SRC 0x0C040A08 146x29 32bpp lit=0   DST 0x0386CE10 800x600 32bpp lit=0
blit#4: SRC 0x0C040C48 130x29 32bpp lit=0   DST 0x0386CE10 800x600 32bpp lit=0
blit#5: SRC 0x0C040AA8 160x29 32bpp lit=0   DST 0x0386CE10 800x600 32bpp lit=0
blit#6: SRC 0x0C040A48 234x29 32bpp lit=0   DST 0x0386CE10 800x600 32bpp lit=0
```

The `147x29` matches `sample_candidates`'s independent reading exactly, so `probe_count_lit` is
locking the right surface and reading real bits. **The sources are empty at the instant they
are blitted. The inter-frame-clear confound is eliminated.**

### 20.2 What the sources are

Every source is ~29 px tall, 130-234 wide, 32bpp - the shape of **UI text-label sprites**, a
menu's worth of small strips. The dest is the 800x600 render target, also empty. The chain is
empty end to end: empty label sprites -> empty composite -> black present.

Meanwhile FBHUNT still finds real content in unrelated system buffers (`0x0EF30000`:
5712/7500). So the engine draws SOMETHING, somewhere, but not into the DirectDraw surfaces this
blit path uses.

### 20.3 The open question, sharpened

**What should fill a 147x29 32bpp UI sprite surface, and is that fill windowed-only-broken?**
Two ways to attack it, in order of cost:

1. **Fullscreen contrast (U-035).** Run the same `probe_count_lit` on the blits in a fullscreen
   run. If fullscreen sources are lit and windowed are empty, the fill step is
   windowed-specific. If fullscreen sources are ALSO empty, this DirectDraw blit path is a
   red herring in both modes and the real present path is elsewhere (follow the FBHUNT
   regions / `blt_convert`, 882 hits, instead).
2. **Trace the sprite fill.** The 32bpp sprite is likely converted from an 8bpp resource by
   `blt_convert` (`FUN_10014c05`); instrument it and see whether its output surface is ever one
   of these `0x0C04xxxx` sources.

`[UNCERTAIN]` a pixel counted lit requires `px & 0x00FFFFFF != 0`; a sprite drawn entirely in
pure black would read 0. Implausible for text labels but not excluded.

## 21. ROOT CAUSE: windowed surfaces are 32bpp, the engine renders 16bpp (2026-08-16)

### 21.1 The fullscreen/windowed contrast

Same `probe_count_lit`, same blit function, first 6 blits:

| | fullscreen (`u035_fs.log`) | windowed (`u037_A.log`) |
|---|---|---|
| source dimensions | 640x480, 800x600, 1124x406 | 147x29, 150x29, 146x29 ... |
| source **bpp** | **16** | **32** |
| source lit | **19,185 / 30,000 / 28,662** | **0** |
| dest bpp | **16** | **32** |
| dest lit | 0 -> 19,196 -> **30,000** | **0** |

Fullscreen: `raster_blit_hw` blits full-frame 16bpp rasters full of content, and the dest
composites correctly - `0 -> 19,196 -> 30,000` lit, layer by layer. The blit mechanism is
sound and shared by both modes.

### 21.2 The root cause

The device renders at **16bpp** (`[CONFIRMED @0x10009efb]`, U-025). Fullscreen surfaces are
16bpp and carry content; the FBHUNT system rasters that hold real content are 16bpp too.
**Windowed surfaces come out 32bpp** - matching the desktop mode (2560x1440 @ 32bpp), NOT the
engine. Content rendered at 16bpp never lands in a 32bpp surface, so every windowed source and
the windowed dest are freshly-allocated and empty.

This is one defect, not several:
- U-024 (black windowed client): the presented 32bpp surfaces are empty because the 16bpp
  engine output never reaches them.
- U-025 (intro movie draws exactly half width): 16bpp row bytes (640 px x 2 = 1280 B) written
  into a 32bpp surface fill 320 px. Same bpp mismatch, on the movie path. The "factor of
  exactly 2" is now explained.
- U-037 (empty sources): the sources are 32bpp; the engine never renders 32bpp.

### 21.3 Why the surfaces are 32bpp - the next question

The WINDOWED patch already nops `GZGraphicD+0x117D6 'mov [ebx+0x48],1'` ("16bpp can stay"), so
the DEVICE keeps 16bpp. But surface CREATION in windowed mode still adopts 32bpp. DirectDraw
windowed surfaces on the primary inherit the desktop's pixel format unless an explicit
`ddpfPixelFormat` is supplied. The fix path is one of:

1. supply an explicit 16bpp `ddpfPixelFormat` when the windowed offscreen surfaces are created
   (find the `CreateSurface` call site in GZGraphicD and force `dwRGBBitCount=16` + the 5-6-5
   masks), or
2. run the whole windowed device at 32bpp (force the engine's render rasters to 32bpp - larger
   change, touches the 16bpp fast-path gates `gate16_a/b/c`), or
3. change the desktop to 16bpp before launch (test-only, confirms the diagnosis: if a 16bpp
   desktop makes windowed render, the mismatch is proven and option 1 is the real fix).

Option 3 is the cheapest confirmation and needs no code. Options 1/2 are the actual fix.

`[UNCERTAIN]` not yet read: the exact `CreateSurface`/`CreateSurface`-caller in GZGraphicD that
allocates these offscreen surfaces, and whether it passes a pixel format or inherits the
primary's. That call site is the fix location.

## 22. FIX LOCATION CONFIRMED: the missing 16bpp branch in FUN_10019273 (2026-08-16)

### 22.1 The call site

`FUN_10019273` @ `0x10019273` (our `OffscreenSurf`) is the ONLY color offscreen-surface
creator in GZGraphicD. It calls `IDirectDraw::CreateSurface` (interface via
`*DAT_1006ce28 -> +0x1c`, then vtable `+0x18` = index 6) twice - line 75 (video-memory
attempt) and line 88 (system-memory fallback) - both from a DDSURFACEDESC embedded at
`this+0xc`. The vtable is pinned by `FUN_1001250d` (SetCoopLevel) calling `+0x50`
(SetCooperativeLevel) with `8`=DDSCL_NORMAL windowed vs `0x11`=EXCLUSIVE|FULLSCREEN, which
fixes `+0x18`=CreateSurface. `[CONFIRMED @0x10019273, read directly]`

DDSURFACEDESC field map (desc base = `this+0xc`): `this+0x10`=dwFlags, `this+0x18`=dwWidth,
`this+0x14`=dwHeight, ppf at `this+0x54`: `+0x54`=ppf.dwSize, `+0x58`=ppf.dwFlags,
`+0x60`=dwRGBBitCount, `+0x64`=R mask, `+0x68`=G mask, `+0x6c`=B mask, `+0x70`=A mask.

### 22.2 The defect

```
line 40:  this+0x10 (dwFlags) = 7                      // CAPS|HEIGHT|WIDTH, no PIXELFORMAT
line 43:  if (*(param_3+4) == 0x20) {                  // 32bpp -> sets dwFlags=0x1007 + ARGB8888
line 53:  } else if (*(param_3+4) != 0x10) {           // 8bpp/other -> sets dwFlags=0x1007 + fmt
line 61:  }                                            // 16bpp (==0x10): NEITHER branch runs
```

For a 16bpp request `dwFlags` stays `7`, DDSD_PIXELFORMAT (`0x1000`) is never set, and no
`dwRGBBitCount`/masks are written. `CreateSurface` with no pixel format inherits the primary
surface's format. `param_3+4` is the requested source depth; the engine renders 16bpp, so this
is the path taken for every game surface. `[CONFIRMED @0x10019273]`

Fullscreen: primary is 16bpp (SetDisplayMode + DDSCL_EXCLUSIVE), so the inherited format is
16bpp and matches. Windowed (DDSCL_NORMAL): primary = 32bpp desktop, so the offscreen is 32bpp
and the 16bpp engine output never lands. This is the sole defect behind U-024/U-025/U-037/U-039.

### 22.3 The fix spec

Add the missing 16bpp arm (5-6-5), i.e. make the 16bpp case set the same fields the other two
arms set, with 16bpp values:

```
this+0x10 (dwFlags)        = 0x1007        // add DDSD_PIXELFORMAT
this+0x54 (ppf.dwSize)     = 0x20
this+0x58 (ppf.dwFlags)   |= 0x40          // DDPF_RGB
this+0x60 (dwRGBBitCount)  = 0x10          // 16
this+0x64 (R mask)         = 0xF800
this+0x68 (G mask)         = 0x07E0
this+0x6c (B mask)         = 0x001F
```

`[UNCERTAIN]` 5-6-5 vs 5-5-5: the engine's 16bpp getpixel/setpixel format has not been read;
if the software renderer packs 5-5-5, the masks must be `0x7C00/0x03E0/0x001F` and the primary
would need matching. Read `getpixel_a`/`setpixel_a` (`FUN_100155b6`/`0x10015614`) to confirm
the 16bpp bit layout before committing masks.

Two ways to apply it:
1. **Harness detour** (reversible, no binary edit): we already detour `FUN_10019273`
   (`OffscreenSurf`). A mid-function hook just before the CreateSurface call (or a re-write of
   the desc when `dwFlags==7` && depth==0x10) forces the 16bpp pixel format. Preferred for
   testing.
2. **Static byte patch** of the DLL: add the branch. Larger, and GZGraphicD is a game asset -
   out of scope for the public repo. Keep any patched DLL local.

## 23. WINDOWED MODE RENDERS — the 16bpp fix confirmed visually (2026-08-16)

### 23.1 The fix works

`-fix16` (patch_surfacefmt) injects the missing 16bpp branch into FUN_10019273 at 0x19349 via
a mid-function inline hook (steals `neg bl; sbb ebx,ebx; and ebx,0xfc0`, writes a 5-6-5
ddpfPixelFormat when `[esi+0x10]==7`, replays, returns). With it on, windowed reproduces the
fullscreen blit pattern exactly:

```
blit#1: SRC 640x480  16bpp lit=19185   DST 800x600 16bpp lit=0
blit#2: SRC 640x480  16bpp lit=19185   DST 800x600 16bpp lit=19185
blit#5: SRC 800x600  16bpp lit=30000   DST 800x600 16bpp lit=19185
blit#6: SRC 1124x406 16bpp lit=28662   DST 800x600 16bpp lit=30000
```

Sources are 16bpp (were 32bpp) and full; the dest composites 0 -> 19185 -> 30000. **Confirmed
visually by the user: the game renders in the window** - U-024/U-039 fixed. This is the first
time the windowed client has shown the game.

### 23.2 -nokeysrc is now obsolete (color keying works at 16bpp)

`-fix16` WITHOUT `-nokeysrc`: `raster_blit_hw` 289,451, `rasthw_throw` **0**, and the user
confirms transparency is correct (violet gone). So the DDBLT_KEYSRCOVERRIDE E_NOTIMPL of §18
was a SYMPTOM of the 32bpp mismatch, not an independent defect - a color-key blit against a
32bpp surface whose format the emulation could not key failed; against a proper 16bpp surface
it succeeds. **`-nokeysrc` is retired.** §18/§19's "100% blit failure" was real but its cause
was U-040 all along.

### 23.3 One secondary defect remains: the menu is clipped right and bottom

The render is 800x600 (device init `[800,600,...]`); the client is larger. `present_calls`
dropped to 2 with `-fix16` (was thousands), so the game's OWN present path is active now and
the forced `-winpresent` Blt is essentially unused - the clip comes from the game's own
windowed present sizing, not our hook. This is a window/client sizing issue, not a format one,
and is the only remaining windowed defect. `-winpresent` may itself now be removable; re-test.

### 23.4 The switch set that renders

`-nocom -windowed -origin -fix16` + `-gzlog <abs>`. `-fix16` is the one essential new switch.
`-nokeysrc` retired; `-winpresent` now likely redundant (re-test). This is the first fully
rendering windowed configuration.

## 24. WINDOWED MODE COMPLETE - clipping was -winpresent, fixed by dropping it (2026-08-16)

**Final working config, user-confirmed: `-nocom -windowed -origin -fix16 -fitclient`** (NO
`-winpresent`, NO `-nokeysrc`). Renders, correct transparency, no clipping.

The right/bottom clip (U-041) was NOT a window-size problem - `-fitclient` confirmed the client
was already exactly 800x600 (`AdjustWindowRectEx` agreed with the game's own 806x629/806x635
outer calc, GetClientRect = 800x600). Two things fixed it together:

1. **`-fitclient` -> `SetProcessDPIAware` in DllMain.** The game is DPI-unaware; on a 125%
   desktop (physical 2560x1440, logical 2048x1152) its windowed present blitted 800x600 logical
   into an 800x600 PHYSICAL region of a DWM-scaled client. Making the process DPI-aware
   (logical==physical) removed the scaling mismatch. Also fixes the caption-height metric so an
   800x600 client needs an 806x635 outer, which `-fitclient` now enforces.
2. **Dropping `-winpresent`.** With `-fix16`, the game's OWN windowed present works (the flip /
   present path was fine once the surfaces were valid 16bpp - the original §10h "NULL flip
   chain" was another symptom of the format defect). `-winpresent`'s hook fired only ~3x then
   the game's native present took over, and the two disagreed on the dest rect - the hook's
   DPI-corrected 1000x750 rect (pre-DPI-aware) or its screen-absolute 3,32 origin fought the
   game's own present. Removing the hook lets the game present natively and correctly.

So `-winpresent` and `-nokeysrc`, both built this session's-worth of effort to work around the
black screen, were BOTH symptoms of U-040. With the real fix they are obsolete. The minimal
render path is the game's own, plus one injected pixel-format branch and DPI awareness.

### 24.1 What windowed mode needs, minimal and final

| switch | why |
|---|---|
| `-nocom` | mandatory; apphelp shim owns the COM dispatch |
| `-windowed` | the two GZGraphicD windowed patches (0x6CDAC flag, 0x117D6 nop) |
| `-origin` | keep the window on the primary display (placement constraint, §12) |
| `-fix16` | inject the missing 16bpp pixel-format branch in FUN_10019273 (U-040) |
| `-fitclient` | SetProcessDPIAware + size the client to exactly 800x600 (U-041) |

`-gzlog <abs>` only needed for measurement. `-winpresent`, `-nokeysrc`, `-present`, `-guard`,
`-sample`, `-resume` are all obsolete for a normal windowed run.

## 25. Intro movie half-width: structurally different from U-040, not the same fix (2026-08-16)

### 25.1 Where the movie draws

The intro player (SC3U `FUN_00429f95`) draws frames via the codec's `vt+0x10`
(`FUN_0043f834`) into the surface at `movie+0x5c`. That surface is resolved by
`FUN_004414c9` (player slot 0x15c) from the **cIGZWinMgr** window manager
(`FUN_004703a7` -> service `0xa417445e` = `GZSERVID_cIGZWinMgr`, `vt+0x18` active window,
`vt+0x4c` its surface). It is the **PRIMARY** surface, created by GZGraphicD
**`FUN_100199c0`** with `dwFlags=1` (DDSD_CAPS only) and caps `0x2200`
(DDSCAPS_PRIMARYSURFACE|LOCALVIDMEM), **no DDSD_PIXELFORMAT** `[CONFIRMED @0x100199c0, read]`.
So it inherits the display-mode format: 16bpp fullscreen, 32bpp windowed.

The codec's draw-frame does NO stride math itself (`FUN_0043f834`): state 2 Locks the dest
(`vt+0x1c`), copies the uV frame buffer via `vt+0x74`, Unlocks (`vt+0x20`). The 16bpp row
width lives in the **external `uV` video DLL** (`uV_Play_FromHandle`/`uV_Open` thunks at
`0x0043f93e` / `FUN_0043f1fd`), which is NOT in any Ghidra export.

### 25.2 Why -fix16 does not and cannot fix it

`-fix16` forces 16bpp on the OFFSCREEN surfaces (`FUN_10019273`), which are format-free to
create. The movie uses the PRIMARY (`FUN_100199c0`). **A windowed DirectDraw primary must
match the desktop pixel format**; forcing DDSD_PIXELFORMAT=16bpp on a PRIMARYSURFACE while the
desktop is 32bpp is rejected by DDraw (DDERR_INVALIDPIXELFORMAT). So the U-040 patch is not
applicable - it would fail CreateSurface. The uV codec emits 16bpp to match a 16bpp fullscreen
primary; windowed's 32bpp primary is the mismatch, and the codec is external and fixed.

### 25.3 The tractable fix, if pursued

The only in-our-control conversion point is the copy `dest->vt[0x74](uvBuffer, 0)` inside
`FUN_0043f834` state 2. `vt+0x74` is a method on the cIGZWinMgr window-surface class (vtable
not yet identified). If it is a GZGraphicD blit that reads the uV 16bpp buffer and writes the
locked primary WITHOUT format conversion, making it convert 16->32 would fix the movie. That
needs: identify the cIGZWinMgr surface class vtable, read `vt+0x74`, and confirm whether it is
format-aware. Alternative (larger): redirect `movie+0x5c` to a 16bpp offscreen and blit-convert
to the primary each frame.

### 25.4 Recommendation

The intro is cosmetic and skippable, and the game itself renders fully. This is understood, not
mysterious. Either interpose a converting copy at `vt+0x74` (a real piece of work on the movie
path) or leave it documented. Not worth blocking on.

## 26. Intro skipped via the game's own advance path (-nointro) (2026-08-16)

Rather than fix the 16bpp-on-a-32bpp-primary movie (§25, structurally hard), skip it. The boot
state machine SC3U `FUN_00429f54` already has the exit: for movie-state 0 it calls the start
`FUN_00429f95`, and **if that returns al==0 (movie did not start) it posts message (5,0x1b)**
= "movie done, advance to menu". So neutralising the start call makes the game boot straight to
the menu using its own logic.

`-nointro` (patch_nointro) replaces the 5-byte `call FUN_00429f95` at SC3U `0x429F78`
(`E8 18 00 00 00`) with `xor al,al` + 3 nops (`32 C0 90 90 90`). In-memory patch of SC3U
(base 0x400000), verified against the original bytes first. Result, user-confirmed: **boots
straight to the menu, no intro, menu correct, and NO renderer SUSPEND at all** (the movie never
runs, so the +0x1C suspend/resume of §13/§14/U-028 never happens). This sidesteps U-025 and
U-032's whole surface entirely.

### 26.1 The complete windowed command

```
sc3launch.exe -nocom -windowed -origin -fix16 -fitclient -nointro
```

Renders, correct transparency, correct client size, no intro. This is the finished windowed
mode. `-gzlog <abs>` only for measurement; all of `-winpresent -nokeysrc -present -guard
-sample -resume -bpp` are obsolete.

## 27. Launch-harness test suite (2026-08-17)

Built after this session showed that nearly every dead end was a broken MEASUREMENT
reading as a real result, not the game misbehaving. Three committed scripts in `re/scripts/`
(the probe source stays gitignored; these are tracked tools):

- **`harness_patches.py`** - a versioned manifest of every in-memory patch the probe applies
  (RVA + expected pre-patch bytes + which switch) and a DRY-RUN verifier that checks each site
  against the on-disk Apps\ binaries WITHOUT launching the game, plus the SC3U anchor SHA. Exit
  non-zero on any drift. This is the committed baseline the gitignored probe source lacked.
- **`harness_check.py`** - turns one run log into a single verdict with three distinct exit
  codes: `PASS` (rendered + integrity held), `FAIL` (trustworthy measurement, game did not
  render), `HARNESS-FAIL` (the measurement itself is broken - a zero here means nothing). The
  FAIL vs HARNESS-FAIL split is the whole point: a trace table that never opened, a detour that
  never installed, a missing log all become HARNESS-FAIL instead of a false "drew nothing".
  Auto-detects fix16/fitclient/nointro/windowed from the probe banners so one grader fits every
  scenario.
- **`harness_run.ps1`** - runs a scenario K times at a FIXED duration (never waiting on a human
  to close the window), grades each with harness_check.py, classifies the batch. Pre-flights
  harness_patches.py so a drifted binary aborts before any run is spent. `-List` shows scenarios.

### 27.1 What the suite taught while being built

- **The plain windowed path is not automatable.** Without `-nointro` the intro movie plays and
  suspends the renderer, and unattended nobody skips it, so `blt_disp_1` stays 0 for the whole
  run (the primary shows the movie, not the menu). The automatable render scenario is
  `windowed-nointro`; `windowed-movie` is kept opt-in and INTERACTIVE.
- **A surface signature for golden pixel comparison (item 5) was tried and REMOVED.** Sampling
  the render target with a Lock on the watcher thread returns a stale/shadow buffer (rule 5):
  the signature was identical (`all-4`) for a rendered menu AND a black no-fix16 run, so it
  could not tell pass from fail. Shipping it would have been false confidence - the exact
  failure the suite exists to prevent. The reliable pixel witness is the GAME-THREAD lit-count
  in `fnlog_enter` (U-037), which discriminates 0 vs ~30000 and is already a render check in
  harness_check.py. A finer content signature needs a game-thread present-time hook; deferred.

### 27.2 Usage

```
py -3 re/scripts/harness_patches.py            # verify patch sites (no game run)
py -3 re/scripts/harness_check.py <run.log>    # grade one log
pwsh re/scripts/harness_run.ps1                # windowed-nointro, 3x, graded
pwsh re/scripts/harness_run.ps1 -List
```

Validated: `harness_check.py` grades `recover_run18_nogztable.log` HARNESS-FAIL (trace table
never opened), `iso3.log` FAIL (integrity fine, blt_disp_1=0 black run), rendering runs PASS;
`harness_run.ps1` windowed-nointro 3/3 PASS.

## 28. Standalone portable build: version.dll proxy, no injector (2026-08-17)

The windowed fixes previously needed `sc3launch` to inject `sc3probe.dll`. They now run from a
**proxy DLL the game auto-loads**, so the user just runs `SC3U.exe` from the folder - no
launcher, no injection.

**Vehicle:** SC3U.exe statically imports `VERSION.dll` (only `VerQueryValueA`,
`GetFileVersionInfoA`, `GetFileVersionInfoSizeA`). VERSION.dll is not a KnownDLL, so a copy in
the game folder loads in preference to the system one, and its `DllMain` runs at process init -
before the exe entry, the window, and any registry read `[CONFIRMED by live run]`.

**`re/harness/src/proxy_version.c` -> `version.dll`** does two things:
1. reads `[Launch]` toggles from `<exedir>\SC3Portable.ini` (each defaulting to the proven
   windowed set - `NoCom, Windowed, Origin, Fix16, FitClient, NoIntro, NoReg`), publishes them
   as the `SC3PROBE_*` env vars the probe already reads, and `LoadLibrary`s `sc3probe.dll`. The
   probe then applies exactly the same patches it applies under injection - zero probe changes.
2. forwards its three exports to the real `%WINDIR%\System32\version.dll` (loaded by full path,
   no recursion) so SC3U's imports resolve.

**The whole standalone build is two files next to SC3U.exe: `version.dll` + `sc3probe.dll`.**
No trace table is needed (that is measurement only); the shim does not set `SC3PROBE_GZLOG`, and
logs to `<exedir>\SC3Portable.log`.

**Verified 2026-08-17:** launching `Apps\SC3U.exe` directly (no sc3launch) brought up NOINTRO,
NOREG (4/4 advapi32 redirected), SetProcessDPIAware, the GZGraphicD windowed + FIX16 patches,
FITCLIENT (client forced to 800x600), and registry served from the INI. Graded PASS by
`harness_check.py` (fix16 dest lit 230400, source lit 19185, no renderer suspend, 35/35
instrumented).

### 28.1 Caveats

- Dropping `version.dll` in the folder makes EVERY launch of SC3U.exe windowed+patched (delete
  `version.dll` to revert to stock). `[Launch] <key>=0` in `SC3Portable.ini` disables any one
  fix (e.g. `Windowed=0` for stock fullscreen).
- Still two DLLs, not a single patched exe. A truly single-file exe would need the fixes baked
  into SC3U.exe / GZGraphicD.dll as static byte patches plus an embedded DPI manifest, and the
  runtime-set windowed flag and fitclient window-resize (both currently runtime code) reworked
  as code patches. Not done - the proxy is simpler, reversible, and touches no game binary.
- `version.dll` + `sc3probe.dll` are our own code (publishable as tools); the probe SOURCE is
  gitignored. The build is `re/harness/build.ps1`.

## 29. Corrections + new harness flags + the -l city-load mechanism (2026-08-17)

> ⚠️ **§29.3 IS FALSIFIED — see §31.5.** `-l` is `-language`, not load-city: service
> `0x441E5070` is the locale manager and `FUN_004845fe()->vf+0x78(id)` is `SetLanguageId`.
> Read §31 for the mechanism that actually loads a city.

### 29.1 fitclient: DPI-aware only, NO window resize (corrects §24)

§24 said `-fitclient` recomputes the window's outer size to force an 800x600 client. That
resize is WRONG and was harmful. Because `SetProcessDPIAware` runs in DllMain BEFORE the game
sizes its window, the game's OWN `AdjustWindowRect` already produces the correct outer for its
intended client at true DPI (e.g. 1030x803 for a 1024x768 client). Forcing the client to a
hardcoded 800x600 SHRANK the window and clipped the game's larger view - the "clip is back"
regression. **`-fitclient` now does `SetProcessDPIAware` only and leaves the game's own sizing
alone.** The game runs at whatever resolution it is configured for (1024x768 was the observed
default), unclipped. `[CONFIRMED - user-verified unclipped at 1024x768]`

Also: forcing resolution with `-r800x600` (game char switch, §3a) CRASHED the game
(`0xC0000409`). Do not force a resolution to work around sizing; fix DPI instead.

### 29.2 New flags: -quiet, -filetrace

- **`-quiet`** skips the probe's framebuffer sampling (`snap_regions`/`diff_regions`/
  `sample_candidates`/`dump_window_bmp`). Those lock and dump DirectDraw surfaces and are a
  plausible source of instability during a play/verify session - a T3 city-load run hard-crashed
  at ~35 s during a `WINDUMP` at tick 350, and `-quiet` made the same run stable. Use `-quiet`
  for any interactive/verify run; leave it off only when you need the FBHUNT data.
- **`-filetrace`** IAT-hooks `CreateFileA` + `GetFileAttributesA` on SC3U.exe and logs opens of
  `SC3Tune` / `.PAK` / `\Sys\` paths with a sequence number. Answers "loose file vs archive, and
  in what order" with zero interpretation. Confirmed empirically: with `SYS.PAK` present the game
  checks a loose `\Sys\<name>` (GetFileAttributes MISSING) then reads the PAK; with `SYS.PAK`
  renamed away it opens the loose files instead. PAK-first, loose-fallback.

### 29.3 The -l city-load switch: a catalog lookup, NOT a path (for "launch into a city")

`-l<value>` (char switch, handler `FUN_004077b5` +77, §3) does NOT take a file path. It resolves
`<value>` through a service (`FUN_0047048f`): `vf+0x44(value,&id)` then a `vf+0x48` fallback, and
only on a hit does it `FUN_004845fe()->vf+0x78(id)` to load. A full absolute path fails both
lookups and pops "el archivo especificado en la linea de ordenes no es valido o no se ha
encontrado", then the game continues to the menu. So a working `-l` needs the catalog KEY the
service recognises (a city name/id), not `Cities\<name>.sc3`. `[CONFIRMED @0x004077b5, dialog
observed]` The catalog key format is the open question for launching directly into a city.

**Menu-driven load works** and is how the cross-session `.sc3` tests were run: place ONE file in
`Cities\` (a duplicate INTERNAL city name crashes the loader - use a unique name or replace the
target), boot with `-nointro`, load via the in-game menu.

### 29.4 Standalone caveat: version.dll loader is flaky

The `version.dll` proxy (§28) intermittently white-screens (loads the probe via LoadLibrary under
loader lock in DllMain - worked once, failed once). For reliable interactive runs use
`sc3launch` injection instead (a `PlayWindowed.bat` wrapper, no `-kill`, lets a human drive). The
loader-lock LoadLibrary should be reworked (defer to a thread, or merge the probe into version.dll)
before the standalone is dependable.

## 30. Headless screenshots + the menu-click investigation (2026-08-18)

> ⚠️ **§30.2 IS PARTLY RETRACTED and §30.3 item 1 IS CLOSED — see §31.** Headless clicking and
> auto-load into a city now WORK. Retracted from §30.2: `FUN_1006df81` is `ReleaseCapture`, not
> the command; there is no `+0xac` armed flag (armed = winmgr capture, taken by the *mousemove*
> handler); `FUN_10020f9a` is not what blocked the injected click; and the menu tiles are
> SC3U.exe classes, not SIMUI button classes. The "open-ended widget-tree RE" it deferred was
> unnecessary — the engine exposes its event dispatch as public `cIGZWinMgr` vtable slots.

Built so the game can be observed remotely, with no physical display and no un-occluding the
window. All of this is probe/harness code in gitignored `re/harness/`; this section is the
committed record.

### 30.1 Headless screenshots WORK - composite reconstruction (`-shot`, `capture.ps1`)

The obstacle (HANDOFF rule 5): this DirectDraw game composites the frame in a video-memory
surface whose Lock returns a magenta color-key shadow, and the on-screen window is occluded /
the remote machine has only a tiny virtual display - so screen BitBlt, PrintWindow, and locking
the render target ALL come back blank/wrong.

The fix, and it is fully reliable: every sprite blit's SOURCE surface is SYSTEM memory and locks
fine (U-037: 19,185 lit). So the probe MIRRORS each frame-buffer-targeted `raster_blit_hw`
(`FUN_10018c58`) source into its OWN system-memory buffer at the same dest rect, colour-keying
magenta - reconstructing the exact composite in a buffer it can always read
(`sc3probe.c` `fb_mirror`/`fb_dump`, `-shot`). `re/harness/capture.ps1` launches, lets it
reconstruct, dumps to BMP, converts to PNG in the Happy share, and auto-closes:

```
pwsh re/harness/capture.ps1 -Name menu
pwsh re/harness/capture.ps1 -Name x -GameArgs "-lFarmsville" -AtSec 10
```

Verified: pixel-exact 1024x768 main-menu capture, headless. This is the way to see the game.

### 30.2 The menu-click model - mapped, NOT yet drivable headlessly

The game IGNORES posted `WM_LBUTTON` for the action (a GZWinD coalescer `FUN_10020f9a` strips
posted button-downs; the button is not read via GetAsyncKeyState/GetKeyState either - those are
Shift/Ctrl/Alt only). Mouse POSITION comes from `WM_MOUSEMOVE` (so a posted move DOES drive the
hover/highlight, confirmed by screenshot). The click path, fully traced:

- Gonzo WndProc = GZGraphicD `FUN_10017e2f`; pre-filter `FUN_10018871` does NOT swallow mouse.
  It builds a GZ event (`FUN_100178a6`: type 7=Ldown, 9=Lup, 0xb=move; coords from the message
  lParam) and dispatches to the UI sink `*(gfxwin+0x30)` slot 0x64.
- Sink routes down the window tree (`FUN_10020818` / `FUN_1001ec22`), hit-testing the event's
  lParam coords. The menu screen is a SIMUI resizable FRAME (vtable `SIMUI.DLL+0xA4D64`); its
  tiles are CHILD widgets (a separate subclass, ~5-7 sharing one vtable).
- A tile arms on DOWN and fires on UP via a flag: SIMUI `FUN_1002cf27` (arm, sets `this+0xac` if
  the tile's hit-test passes, takes SIMUI-level capture `FUN_1006df61`) and `FUN_1002cf67`
  (fire: if `this+0xac`, clear it and call `FUN_1006df81` = the command). `FUN_1006cf15`
  switch: down->`vt+0x1bc`, up->`vt+0x1c4`.

**Status:** `SendMessage(WM_MOUSEMOVE, WM_LBUTTONDOWN[MK_LBUTTON], held-move, WM_LBUTTONUP)` with
correct 1024x768 client coords reaches the frame but does NOT fire the command. The remaining
unknown is the TILE subclass's own arm/fire (`this+0xac` is on the tile's class, not the frame's
`FUN_1002cf27`/`FUN_1002d6f2`, which are a resize-border hit-test). Cracking it needs identifying
the tile child class, its `vt+0x1bc/0x1c4`, and its armed-flag offset - an open-ended widget-tree
RE. Deferred as beyond its value; hover + screenshots already give remote observation.

`-clicks "x,y@sec;..."` (client coords) is the driver; it correctly sets hover but not the click.

### 30.3 Session open items (handoff)

1. Headless CLICK / auto-load into a city - blocked as above (30.2). The `-l` switch cannot do
   it cold: the city catalog is empty at command-line time (no `Cities\` scan at boot), so `-l`
   silently no-ops regardless of key (`-filetrace` confirmed). Direct-load-function-call from the
   probe is the untried alternative.
2. `version.dll` standalone loader is FLAKY (intermittent white-screen: loader-lock LoadLibrary
   in DllMain). Use `sc3launch` injection for reliable runs. Rework: defer the probe load to a
   thread or merge the probe into version.dll.
3. Intermittent early clean-exit (~7-15 s, code 0) - not diagnosed; re-run past it.
4. Intro movie half-width (U-025): the movie draws to the 32bpp windowed PRIMARY (can't be forced
   16bpp), so `-fix16` can't reach it; skip it with `-nointro`. A converting copy at the codec's
   `vt+0x74` is the deferred real fix.

## 31. HEADLESS CLICK + AUTO-LOAD INTO A CITY - WORKING (2026-08-18)

**The §30.3 item 1 blocker is closed.** The harness can now boot the game, open Load City,
pick a city and land in a rendered, running city view - with **no Win32 input at all**: no
`SendMessage`, no `SendInput`, no cursor, no window focus, no interactive session. One command:

```powershell
pwsh re/harness/capture.ps1 -Name city -GzSeq "0x712BF5BF@9;0x02DFDD6A@14" -AtSec 32
```

Verified visually: `Berlin, Pob: 794,278, $117,006, 2/9/2067`, full city view with toolbar,
RCI indicator and minimap.

### 31.1 The mechanism - drive the engine's OWN event API, not the message queue

§30.2 tried to reach the UI through Win32 messages. The right entry point is one level in:
`cIGZWinMgr` exposes the event dispatch as public vtable slots, so an injected probe can post
GZ events directly.

| what | where | note |
|---|---|---|
| `cIGZWinMgr*` | `SC3U.exe FUN_004703a7()` | no args, returns the cached pointer (`DAT_004FAC90`) |
| `GetRootWin()` | winmgr `vt+0x0c` | |
| `ProcessMouseEvent(GZEvent*)` | winmgr `vt+0x64` | resolves live to `GZWIND+0x20818` `[CONFIRMED]` |
| `GetCaptureWin()` | winmgr `vt+0x70` | the pass/fail oracle for a click |
| `cGZWin::DoEvent(GZEvent*)` | window `vt+0x0c` | what `FUN_1006e18b` dispatches |

`GZEvent` is a plain 16-byte POD `{u32 type; i32 d1; i32 d2; u32 d3}`; `7` = Lbutton down,
`9` = Lbutton up, `0xb` = move, `d3` bit `0x10` = left button held.

**MSVC has no `__thiscall` in C**, only in C++. `__fastcall` with an explicit second (EDX)
parameter is a byte-identical ABI: arg1 to ECX, arg2 to EDX, the rest on the stack, callee
cleans. That is how the probe declares every engine method.

### 31.2 Window tree walking - the child list is at `+0x34` `[CONFIRMED @0x1006c2f7]`

`FUN_1006c2f7` (cGZWin base ctor) allocates 0xC bytes at `param_1[0xd]` (= `+0x34`) and
self-links both pointers: it is an MSVC `std::list` sentinel. Node layout `+0x00 next`,
`+0x04 prev`, `+0x08 child*`. Walk until `node == sentinel`.

The same ctor does `FUN_10001b80(this, FUN_10085091())`, so **`win+0x04` is the window manager**
on every window. Other proven fields: `+0x10` id, `+0x80..0x8c` rect L,T,R,B.

**A window's rect is in its PARENT's coordinate space.** Absolute position is the running sum of
the ancestors' rect origins. Verified end to end: root `0,0,1024,768` -> menu screen
`192,144,832,624` -> Load City tile `333,156,606,374` => centre `(661,409)`, and a move event
there took capture on exactly `id=0x712BF5BF`.

### 31.3 The main-menu window ids (they ARE the menu switch codes)

The tile ids match the `FUN_0043e9d8` menu-result switch one for one, so no pixel hunting is
needed - address a tile by id and let the probe resolve its centre from the live tree.

| id | tile | id | tile |
|---|---|---|---|
| `0x712BF5BE` | New City | `0x712BF5C4` | Exit |
| `0x712BF5BF` | **Load City** | `0x712BF5C5` | Load Scenario |
| `0x712BF5C0` | Load Terrain | `0x712BF5C1` | Load Starter Town |

Load City dialog (frame `0x02DFDD67`, vtable `SIMUI+0xA4D64` - the §30.2 frame):
city list `0x02DFDD6F`, **confirm checkmark `0x02DFDD6A`** (local `425,310,467,342`),
title bar `0x42B7C351`, close box `0x42B7C353`.

The menu tiles are **NOT** SIMUI button classes - their vtables `0x004D2A20` / `0x004D2824` are
in **SC3U.exe**. Their button-up handler `FUN_00439f5a` is literally `mov al,1; ret 0xC`; the
action is on **DOWN**, `FUN_00439ed1` (`ret 0xC`, `__thiscall(this,x,y,flags)`), which notifies
the parent via `FUN_004423e4(this, parent, 3, 1|0x11, cmdid, 0)`. Its two gates, both measured
open on the live Load City tile: `FUN_0043a029(this,1)` = `(this+0xd0 & 1)` (observed `0x14`,
so 0 -> else-branch) and `vf+0xf0(0x10000000)` (observed 0).

### 31.4 THE TRAP THAT COST THIS SESSION - a stale screenshot reads as "nothing happened"

`-shot` arms the composite mirror for a fixed number of blits and only writes the BMP when that
count drains. At the static main menu that took ~6 s, so `capture.ps1`'s "newest `shot_*.bmp`"
was dumped at **t=6400 ms** while the click fired at **t=8990 ms**. Three consecutive
experiments were scored as failures against an image taken 2.6 s BEFORE the action. The click
had been working the whole time.

**Rule: never score a UI action against a shot you have not proved is newer than the action.**
The probe now re-arms a short (400-blit) shot immediately after every `-gz*` action, and the
log prints `SHOT #n` with its timestamp so the ordering is checkable in one grep.

### 31.5 Corrections and retractions to §29/§30

1. **`-l` is `-language`, NOT load-city.** Service `0x441E5070` is the locale manager (name
   tables in `GZSERVICED.DLL`: `"english-us"`, `"french"`, `"german"`, ...), `-c` is country,
   and `FUN_004845fe()->vf+0x78(id)` is **SetLanguageId**. §29.3 is falsified in full, and the
   `0x441E5070` = "City/region" row earlier in this file is wrong. The "empty catalog at boot"
   explanation was never needed: the key simply was not a language name.
2. **`FUN_1006df81` is not the command.** It is `mgr->ReleaseCapture(this)`; `FUN_1006df61` is
   `SetCapture`. §30.2's "`FUN_1006df81` = the command" is retracted.
3. **There is no `+0xac` armed flag** on the clickable classes. "Armed" is window-manager capture
   ownership, and it is taken by the **mousemove** handler (`vt+0x1cc`), never by button-down.
4. **`FUN_10020f9a` is not what broke the injected click.** It is a `PeekMessageA(PM_REMOVE)`
   drain over 0x100-0x108 / 0x200-0x209 / 0x20a that discards `WM_LBUTTONDOWN` unconditionally,
   discards `WM_LBUTTONUP` if a down was in the same batch, discards `WM_MOUSEMOVE`, re-posts the
   survivors and returns the discarded count. It has no callers inside GZWinD and `GZWIND.DLL`
   exports exactly **1** symbol, so it is a vtable method; and since it would eat real clicks
   identically while the game is playable, it cannot be the per-frame input path. Shape fits an
   any-input-to-abort/skip flush. `SendMessage` never went through it anyway.
5. **DirectInput is not an input path.** `GZGraphicD.dll` imports `DirectInputCreateA`, but its
   only xref `FUN_10012bd6` is a DirectX **version probe**: LoadLibrary DINPUT.DLL,
   GetProcAddress, FreeLibrary, create-and-release, writing a capability level
   (`0x100`/`0x200`/`0x300`/`0x500`/`0x600`/`0x601`). No device retained, no state polled.
6. `GZWinD FUN_10020260` reads the **real cursor**: `GetCursorPos` -> service `0xe46397db` ->
   `ScreenToClient`. `FUN_10025790` is a thin `GetAsyncKeyState(vk) >> 15`.

### 31.6 New harness switches (probe/harness code stays gitignored)

`-gzdump` walk the window tree; `-gzclick "x,y"` GZ-event click at client coords;
`-gzclickid <id>` resolve the centre from the live tree then click; `-gzdirect <id>` call the
window's `vt+0x1bc` directly (bypasses routing, for isolating handler vs routing);
`-gzfire <cmdid>` call SIMUI `FUN_1004c209` on a SIMUI button (unused by the menu, which is
exe-side); `-gzseq "<id|dump>@sec;..."` scripted multi-step driving; `-gzat <sec>`.
`capture.ps1` exposes these as `-GzDump/-GzClick/-GzClickId/-GzDirect/-GzFire/-GzSeq/-GzAtSec`
and now takes `-Share` (the Happy share folder was hardcoded to a dead session id).

### 31.7 The IN-CITY UI tree, and driving gameplay (2026-08-18)

With a city loaded the tree is **165 windows, 109 of them buttons carrying a command id**. Dump it
with a sequence that loads first, then walks:

```powershell
pwsh re/harness/capture.ps1 -Name incity -GzSeq "0x712BF5BF@9;0x02DFDD6A@14;dump@28" -AtSec 34
```

**Two ways to drive, and which one applies is decided by the widget's rect.**

1. **Visible widgets -> click by id.** Confirmed in-city: the startup tip dialog is frame
   `0xC2FA5860` (`SIMUI+0xA4D64`) with `0xE2FA5BC2` = the confirm checkmark and `0xE2FBA4B4` =
   "next tip". Clicking `0xE2FA5BC2` dismisses it and the city runs on (verified visually: the
   dialog is gone, smoke plumes and traffic animate).
2. **Hidden widgets -> fire the command.** The twelve build palettes are `SIMUI+0xA9CC8`
   containers at `0,0,96,610` whose buttons all have rect **`0,0,0,0`** — a collapsed palette.
   They cannot be reached by any coordinate, by real mouse or synthetic. But they are SIMUI
   button classes, so `FUN_1004c209` takes them directly. **Verified:** `fire:0x10006602`
   selected a tool and the `$1,000` cost readout appeared in the status bar. Nothing was placed —
   selecting a tool does not apply it, that needs a separate map click.

**Do NOT compute the command id from the window id — read it** from the live button's
`vt+0x214`, which is what the dump prints. `cmdID = 0x10000000 | winID` looks like a rule and is
not: it breaks on 20 of the 109 live buttons. Detail and counter-examples in §31.8.3.

Button-class census in-city (the three clickable SIMUI classes of §31.3):
`cls 0` (`SIMUI+0xA8F60`) x9, `cls 1` (`+0xA917C`) x54, `cls 2` (`+0xA9398`) x46 — the palettes
are all cls 2.

**`-gzseq` grammar is now three verbs**, each `@<sec>`:
`<winid>` click it, `dump` walk the tree, `fire:<cmdid>` post the command. Example that boots,
loads Berlin, dismisses the tip and selects a tool:

```
-GzSeq "0x712BF5BF@9;0x02DFDD6A@14;0xE2FA5BC2@27;fire:0x10006602@31"
```

**The dump now prints `MODULE+RVA`, not raw pointers.** Vtable addresses are ASLR-varying and
were useless across runs; `MODULE+RVA` is stable and is what these docs cite. It also prints
`abs_centre`, the root-space centre (the running sum of ancestor rect origins, §31.2), which is
what `-gzclick` wants. Walk caps raised to 3000 windows / depth 16 / 500 siblings for the
in-city tree, which overflowed the previous 400/12/200.

**The command ids are now all named** — see `re/analysis/formats/MENUITEM_INI.md`. They did not
need any RE: `MenuItem.INI`, a member of `Apps/Sys/SYS.PAK`, is the shipped command table and
carries the developers' own English name for each id as a trailing comment:

```
0x10006602=1,0x225872FE,0x00000034,0x225872FE,0x00000034,COMM,0x22ff0548,0,0,0,END  ; Big Park
```

`re/tools/menuitem_parse.py` (built on the validated `syspak_parse.py`, `--selftest` green)
extracts 90 command records. **All 89 distinct ids seen on live in-city buttons are in it —
100%.** So the window walk plus this table gives a fully named, machine-readable command surface:
zones (`Res/Com/Ind Low/Medium/High Density`), transport (`Roads`, `Lay Rail`, `Highway`,
`Onramps`, `Bus Stop`, `Subway Station`), utilities (`Wires`, `Pipes`, `Power Plants`), civic
(`Police Station`, `Hospital`, `School`, `Library`), parks (`Small Park`, `Big Park`, `Zoo`,
`Marina`), views (`Budget`, `Ordinances`, `Map View`), file (`Save`, `Save As ...`, `Quit`,
`Load Saved City`), and the disaster set (`Fire`, `Tornado`, `Earthquake`, `Riot`, `UFO`,
`Toxic cloud`, `Whirlpool`, `Locusts`, `SpaceDebris`).

**Independent corroboration of the whole chain:** `fire:0x10006602` was fired blind into a loaded
city and produced a `$1,000` cost readout *before* the table was parsed; the table then named
that id `Big Park`, which costs $1,000. Two unrelated routes agreeing on one id.

83 records are `COMM` (dispatch a command) and 7 are `PMSG` (post a message) — a driver must not
assume `COMM`. The `SC3MII` / `SC3MDESC` / `SC3MSET` / `SC3MBTNDEFS` resource types registered by
`SIMUI FUN_10014db6` were NOT needed for this and remain unexamined.

### 31.8 Driving the MAP: the harness can build (2026-08-18)

Selecting a tool is not building. Building needs a second event stream aimed at the city view,
which is `id=0x6104489A` (`SC3U.exe+0xD32D0`, `0,0,1024,768`) - a full-screen window present in
both the menu and in-city trees. Two new `-gzseq` verbs aim there:

| verb | form | what it is for |
|---|---|---|
| `at:` | `at:x,y@sec` | click at raw root coords - plops (parks, buildings) |
| `drag:` | `drag:x1,y1,x2,y2@sec` | press, sweep, release - zoning rectangles and road/rail runs |

A drag is `move-to-start -> down -> 6 interpolated moves with the button HELD (`d3 |= 0x10`) ->
up`, one event per frame. **The intermediate moves are not decoration:** the tool tracks its
current end-point from them, so a press/release with nothing between draws only the start tile.

### 31.8.1 Verified end to end, with a numeric oracle

The city funds readout is the check that beats "the screenshot looks different": the sim is
PAUSED and the date never advances (`2/9/2067`), so nothing except a placement can move it.
Baseline in every run below is Berlin at **$117,006**.

| what | sequence | result |
|---|---|---|
| plop a park | `fire:0x10006601` then `at:300,200` | **-$105**, `$100` cost readout at the click point |
| lay road | `fire:0x10004001` then `drag:180,120,330,120` | **-$50** |
| zone residential | `fire:0x10003101` then `drag:280,170,360,215` | **-$30**, zoned rectangle visible in the open field |

Full working example (boot -> load Berlin -> dismiss the tip -> select -> build -> screenshot):

```powershell
pwsh re/harness/capture.ps1 -Name build `
  -GzSeq "0x712BF5BF;0x02DFDD6A;0xE2FA5BC2;fire:0x10003101;drag:280,170,360,215"
```

### 31.8.2 Two negatives worth keeping

Both were real experiments that placed nothing, and both are about the TARGET, not the mechanism:

- `drag:120,430,260,500` (zone) left funds **exactly unchanged** - that area is already built up,
  so zoning it is a no-op. A zero-delta is the signature of "the ground refused", not "the events
  did not arrive".
- `drag:180,120,330,120` (road) charged $50 but tinted a large existing building **red** - the
  game's cannot-build-here overlay, because the run crossed existing structures.

So a driver must pick open ground, and should treat the funds delta as its success signal.
**A screenshot alone cannot distinguish "placed nothing" from "placed something invisible at this
zoom".**

### 31.8.3 CORRECTION: `cmdID = 0x10000000 | winID` is a pattern, not a rule

Stated as a rule in an earlier draft of §31.7 and **wrong**. Measured over the 109 live buttons:
holds for **89**, breaks for **20**, in two ways - palette-owning buttons carry their FIRST
CHILD's command (`0x00004002 -> 0x10004301`, `0x00006002 -> 0x10006201`,
`0x00009003 -> 0x10009301`, `0x0000A005 -> 0x1000A101`, the three zone roots
`0x00003001/2/3 -> 0x10003101/201/301`, ...), and the nine top-level menu buttons
`0x00001003`..`0x00001009` have **`cmdID = 0`** and no SC3MII record at all (their caption comes
from the SC3MDESC group name). The authority is the `[SC3MenuBtnDefs]` table, or simply the live
button's `vt+0x214`. Never compute it.

### 31.8.4 A cheaper naming route exists, and is not yet used

Independently of `MenuItem.INI`, **every button carries its display text live**: `win+0x44` is a
`cRZString` caption (also reachable as `vt+0x108` `GetCaption`, `FUN_1006dfc9`, literally
`return this+0x44`) and `win+0xC0` is the tooltip/description. Both are filled at button init by
`FUN_1004b5bf` from the SC3MII record, and `win+0xB0` is that `SC3MII*` with its command id at
`+0x04`. `cRZString` is `{vtable, begin, end, cap, n}` and is **not NUL-terminated** - use
`end - begin`. Reading those two fields would give LOCALIZED names (Spanish in this install)
with zero calls and no INI parsing. Not implemented; `MenuItem.INI` already answered the question
in English, which is the better annotation language.

### 31.8.5 The scheduler WAITS FOR ITS TARGET, it does not wait on the clock

Earlier sequences carried wall-clock step times (`@9`, `@14`, `@27`, ...). Those were guesses at
how long a load takes, and guessing is the wrong mechanism in both directions: too short and the
step fires before its target exists and **silently does nothing** (which is indistinguishable
from a broken click - see §31.4 for how expensive that confusion already was), too long and every
run burns seconds it did not need.

Each step now blocks until **its own target is present in the live window tree**, polled from the
game-thread hook at 50 ms:

| step | ready when |
|---|---|
| `<winid>` | that window exists in the tree (and its centre is taken from the tree at that moment) |
| `fire:<cmdid>` | a button carrying that command exists - which is *also* the natural "the city has finished loading" signal, since the build palettes only exist in-city |
| `at:` / `drag:` / `dump` | no target to wait for: a 400 ms settle after the previous step |

**`@N` changed meaning: it is now an optional TIMEOUT in seconds, not a start time.** If a target
never appears the step is skipped with a loud log line instead of the run hanging or, worse,
firing into nothing. Default timeout 90 s.

Measured on the same build sequence, same machine:

```
-GzSeq "0x712BF5BF;0x02DFDD6A;0xE2FA5BC2;fire:0x10003101;drag:280,170,360,215"
```

| step | waited |
|---|---|
| 0 Load City tile | 1,031 ms (menu still coming up) |
| 1 dialog confirm | **0 ms** |
| 2 dismiss the tip | 3,281 ms (the city load) |
| 3 select the zone tool | **0 ms** |
| 4 the drag | 453 ms settle |

Sequence complete at **t+10.0 s**; whole run **11.5 s wall clock, against 46 s** for the
hardcoded-time version, with an identical result (-$30 and the zoned rectangle). The waits are
now where the work actually is, and the same script is correct on a slower machine.

`capture.ps1` follows the same principle: it polls for the probe's `### GZSEQ: COMPLETE` marker
instead of sleeping, and `-AtSec` became a timeout (auto: 90 s with `-GzSeq`, else 10 s).

**Two stale-artifact traps had to be closed to make that safe**, both the same shape as §31.4:

1. The log is reused across runs, so a leftover `GZSEQ: COMPLETE` from the *previous* run would
   satisfy the wait instantly and capture the wrong frame. `capture.ps1` now **deletes the log**
   before launching rather than trusting its contents.
2. Waiting for the shot *file* to appear races the writer and yields a truncated BMP (observed:
   `Image.FromFile` threw "invalid input"). The probe emits its `### SHOT #n` log line only
   **after** `CloseHandle`, so that line - not the file timestamp - is the completion signal.

### 31.9 Runtime verification of the zone write path (handoff from the U-063 session)

Two runtime checks the static session could not run. **Both scored on the SAVED FILE, never on
pixels** - deliberately, to sidestep U-062 entirely. Screenshots were used only to read the funds
counter, and `capture.ps1` now waits for `GZSEQ: COMPLETE` and then a `SHOT #n` line after it, so
every image used is provably post-action by construction.

**Install integrity: `Cities\` was SHA-256 baselined (59 files) before the first run and verified
byte-identical after every single run.** The method: back up the target `.sc3`, let the game's own
Save overwrite it, copy the result to scratch, restore the backup and its original mtime, then
re-hash all 59. No harness artifact was left in the game install at any point.

#### Cross-check that fell out for free: the 13 zone tools, confirmed from a second source

Every one of the 13 zone-tool CLSIDs in the U-063 factory table is the `guid` field of a
`MenuItem.INI` command record (§31.7), **13 of 13**, and the zone byte lines up with the command's
own name in every case:

| cmd | name | guid (= factory CLSID) | zone byte |
|---|---|---|---|
| `0x10003007` | DeZone | `0x82e88c9c` | 0 |
| `0x10003101/2/3` | Res Low / Medium / High | `0x42e88586` / `0x02e88915` / `0xa2e8893b` | 1 / 2 / 3 |
| `0x10003201/2/3` | Com Low / Medium / High | `0x02e88949` / `0xa2e8895a` / `0x02e88968` | 5 / 6 / 7 |
| `0x10003301/2/3` | Ind Low / Medium / High | `0xc2e8898f` / `0xa2e8899d` / `0x02e889aa` | 9 / 10 / 11 |
| `0x10003006` / `0x10003005` / `0x10003004` | Airport / Seaport / Landfill | `0xe2e889d4` / `0x02e889c4` / `0xc2e889b6` | 14 / 15 / 17 |

Note zone byte **6 is Com MEDIUM Density**, not "Commercial" generically.

#### TEST 1 - the zone chain is now C4. PREDICTION CONFIRMED.

Berlin (256x256), baseline histogram `{0:40981, 1:64, 2:5246, 3:3672, 5:1538, 6:2392, 7:1381,
9:2210, 10:1243, 11:550, 14:453, 15:166, 17:719, 22:4921}`.

Drag-zoned with **Com Medium Density (`0x10003202`, zone byte 6)**, saved, reloaded with
`re/tools/city_write.City`:

| run | changed tiles | transition | bbox | other values |
|---|---|---|---|---|
| small drag | 2 | all `0 -> 6` | 2x1 | none |
| larger drag | **10** | **all `0 -> 6`** | 5x2 | **none, and 22 unchanged at 4921** |

Histogram delta was exactly `{0: -10, 6: +10}`. Every legally-zoned tile reads exactly the tool's
byte and nothing else in the raster moved. **The chain `0x1000bb73 -> 0x1000ba68 -> 0x1000b7d0 ->
0x1003591f -> 0x10032a96` is now C4 for zone byte 6, observed end to end.**

#### TEST 2 - **OUTCOME A**, and it is a RECT FILL.

Plopping a **Hospital (`0x10006401`)** into open ground writes **22 over its whole footprint**:

```
deltas: {0: -9, 22: +9}          22: 4921 -> 4930
9 changed tiles, all 0 -> 22
bbox x 99..101, y 180..182  =  3x3 CONTIGUOUS
cost readout $500, funds -$515
```

Reproduced twice: once inside a three-plop run and once as a **single-plop run with no other
action**, both giving the identical bbox and delta. The write is a **contiguous 3x3 rect, not a
point write**, which is exactly the shape of the rect writer `0x10032afa` (vt+0x38) and matches
the iOS sibling's `goBuildingLayer::PlaceBuilding` stamping 22 over a footprint.

**So the retail x86 producer of 22 EXISTS and is reached from a call site not yet located.** The
problem is now "producer exists, call site unlocated", not "no producer in the binary", and the
rect writer is live - the 49 candidate call sites are worth hunting.

#### Negative controls, and why they matter

Two plops placed nothing, and both are recorded because they are what makes the positive result
trustworthy:

- **Police Station (`0x10006201`) at (300,200)**: funds unchanged at $117,006, zero raster change.
- **Big Park (`0x10006602`) at (300,200)**: funds unchanged, zero raster change.

The first TEST 2 attempt was exactly this case and I nearly reported it as OUTCOME B. **It was not
evidence of anything** - the building was never placed. Zero-delta and zero-funds-change co-occur
perfectly across all runs, so the funds counter is the gate: *do not read a raster delta from a
run whose funds did not move.* A re-save alone changes the file (`test1b` shrank by 316 bytes
while adding 10 tiles), so file size and hash are useless as placement evidence.

**Not established:** why those two plops were refused at a coordinate where a Small Park succeeded
earlier. Footprint fit and terrain slope are candidates; nothing was read to decide it.

#### 31.9.1 THE 22 PRODUCER IS FOUND: `SIMGEOM.DLL` `FUN_10007760+0x5BB`

U-057's last open item ("no shipped x86 code writes 22") is **closed, positively**. The producer
was located by hooking the rect writer at runtime and reading back its caller, then confirming in
the instruction bytes.

**The call site.** `SIMGEOM.DLL 0x10007D1B`, inside `FUN_10007760`
(`__thiscall(this, int *param_1, int *param_2)`, 1531 B, starts `0x10007760`):

```
10007CF3  8D 55 23        lea  edx,[ebp+0x23]        ; &value  (pushed first => last arg)
10007CF6  8B 4B 24        mov  ecx,[ebx+0x24]        ; this+0x24 -> holds the zone layer
10007CF9  52              push edx
10007CFA  8B 57 10 C1 FA 08 52   push param_1[4] >> 8
10007D01  8B 57 0C C1 FA 08 52   push param_1[3] >> 8
10007D08  8B 57 04 C1 FA 08 52   push param_1[1] >> 8
10007D11  C6 45 23 16     mov  byte ptr [ebp+0x23],0x16    ; <<<< THE LITERAL 22
10007D15  8B 01           mov  eax,[ecx]
10007D17  C1 FA 08 52            push param_1[0] >> 8
10007D1B  FF 50 38        call dword ptr [eax+0x38]        ; <<<< SIMRCI FUN_10032afa, the rect writer
10007D1E                  (return address; this is what the runtime hook reported)
```

So the call is
`zoneLayer->vt[0x38](param_1[0]>>8, param_1[1]>>8, param_1[3]>>8, param_1[4]>>8, &(byte)0x16)`.
`param_1` is a rect in the **8.8 fixed-point city-coordinate convention** (the `sar edx,8`).

**Three independent confirmations that this is the producer:**

1. **Runtime.** With `SIMRCI+0x32afa` hooked (`-modlog`), plopping a Hospital produced 30 rect
   writes in the whole run. 29 came from `SIMUTIL.DLL+0x42C1`, all during city LOAD. Exactly
   **one** came from `SIMGEOM.DLL+0x7D1E`, at t+10,971 ms - the plop click was t+10,464 ms.
2. **The rect matches the file.** That single call passed `a1=0x49, a2=0x63, a3=0x4B, a4=0x65`
   = rows 73..75, cols 99..101. The saved city showed the 9 new 22s at x 99..101, y 180..182.
   `255-75 = 180` and `255-73 = 182`: the same 3x3, under the known row-reversal of the zone
   plane. The measured write and the measured file agree tile for tile.
3. **The bytes.** `mov byte ptr [ebp+0x23],0x16` sits 10 bytes before the call, and `[ebp+0x23]`
   is the address `lea`'d as the writer's 5th argument. The literal is there in the shipped DLL.

**Why five sweeps missed it, and it is not anyone's fault.** Ghidra renders this call with **zero
arguments**:

```c
(**(code **)(**(int **)((int)this + 0x24) + 0x38))();      /* line 245 of FUN_10007760 */
```

The surrounding decompilation is full of `in_stack_0000001c` / `puStack00000014` - the stack model
is lost, so neither the arguments nor the `0x16` appear in the C at all. This is exactly the trap
`re/scripts/find_vslot_calls.py` documents in its own docstring ("an arity-filtered sweep is a
LOWER BOUND, never an exhaustive negative"). An `0x38:5` sweep returned 49 hits and **could not**
contain this one.

**A byte sweep alone would also have failed.** Searching for `mov byte [ebp+d8],0x16` near a
`call [reg+0x38]` gives 3 hits across all modules, and 2 of the 3 are false positives: in
`SIMBABLD FUN_1202e2fa` and `SIMUI FUN_1004a9ca` the `0x16` is the **MSVC SEH try-level**
(`local_8 = 0xffffffff` at entry, then `local_8._0_1_ = 1,2,...,0x18`). I initially dismissed all
three on that basis and was wrong about the third. Only the runtime hook separated them.

#### 31.9.2 `FUN_10007760` named: `cISC3BuildingLayer::commit_placement`

The 22-writer is the building layer's placement-commit. Signature recovered from bytes
(Ghidra's decompile is wrong here - it lost the stack model and shows a 3-arg call with zero args
at the write site):

```c
// SIMGEOM 0x10007760, __thiscall, ret 0x1C (7 stack args), bool in al
bool commit_placement(cISC3BuildingLayer *this,
                      Box6  *region,        // [ebp+08] {x0,y0,z0,x1,y1,z1}, 8.8 fixed city coords
                      Vec   *occupants,     // [ebp+0C] std::vector<cISC3Occupant*>
                      u32    a2,            // [ebp+10] forwarded to terrain vt+0x120, then scratch
                      i32    cost,          // [ebp+14] withdrawn unless freeOfCharge
                      u32    a4,            // [ebp+18] in/out of the terrain feasibility call
                      bool   freeOfCharge,  // [ebp+1C] Ghidra's in_stack_00000018
                      i32    mode);         // [ebp+20] Ghidra's in_stack_0000001c, 0/1/2/3
```

The `mov byte [ebp+0x23],0x16` at `0x10007D11` writes into **byte 3 of the `mode` argument slot**,
reused as dead scratch after `mode`'s last compare - which is why 22 never appears as a named
local. The stamp is `this->zoneLayer(+0x24)->vt[0x38](x0>>8, y0>>8, x1>>8, y1>>8, &22)`.

**`this` is `cISC3BuildingLayer`** (SIMGEOM), ctor `0x10004BDA`, size 0x84, four vtables; primary
`0x100292C0`. `QueryInterface 0x10004CB8` maps IID `0x20631788`
(`GZIID_cISC3BuildingLayer`, `GZCOM_INTERFACE_CATALOGUE.md:2403`) to offset 0. Its fields are bound
in `Init 0x100023E8` from the `cISC3City` at `this+0x38`:

| field | from city slot | used as |
|---|---|---|
| +0x18 / +0x1C / +0x20 | city vt+0x120 / +0x124 / +0x14C | three occupant managers (surface / L1 / L2) |
| **+0x24** | city vt+0x13C | **the zone raster layer** - its vt+0x38 is the 22 stamp |
| +0x28 | city vt+0x140 | terrain layer (altitude/IsWater/tile-type) |
| +0x2C | city vt+0x15C | region change/redraw sink |
| +0x30 | city vt+0x194 | budget layer (vt+0x10 funds, vt+0x14 withdraw, vt+0x58 cost) |
| +0x34 | city vt+0x18C | neighbors layer |
| +0x38 | Init arg | the `cISC3City` |

The **modes**: mode 1 is the on-water variant (per-tile `terrain->vt[0x15C]`; the feasibility
sibling `FUN_100072F6` requires tile-type 4 and level corners for mode 1, IsWater==false for the
others); modes 2 and 3 do an extra demolish-sweep over the L1 / L2 occupant managers respectively.
All modes: demolish conflicting occupants, insert the new ones via own `vt+0x58` with reverse
rollback via `vt+0x5C`, stamp 22, then withdraw `cost` unless `freeOfCharge`.

**The call chain.** `FUN_10007760` is in **no vtable**; it is reached by direct call from two
functions, each the tail of a family of ten consecutive vtable slots (`0x100292C0` +0x24..+0x48):

| function | proposed name | conf | role |
|---|---|---|---|
| `0x10006BA6` | `sc3_bldglayer_place_building` | C2 | resolve one exemplar (IID `0xE075EF51`), build footprint, run feasibility, check funds, create occupant (own `vt+0x20`), commit |
| `0x10006DF6` | `sc3_bldglayer_place_building_composite` | C2 | same, but four exemplar ids combined into one footprint |
| `0x10007760` | `sc3_bldglayer_commit_placement` | C2 | the body above |
| `0x10008599` | `sc3_geom_post_newsticker_for_building` | C2 | called for occupant[0] only; maps type id -> news headline (group `0x42C1ED2D` = `SC3StringsNewstickerTriggered.IXF`) |

The ten wrappers are a 2x(4+1) matrix: `commit=0` slots are dry-run "can-place" queries (the
`FUN_10007760` block is skipped), `commit=1` slots actually place; four `mode` values plus one
composite. So placing a building is a virtual call `buildinglayer->vt[9..18](...)`, and the visible
side effect on the zone raster - a footprint of 22 - is one instruction inside it.

**`[UNCERTAIN]`, do not propagate.** The agent's field map implies city vtable
slot +0x13C = zone layer, +0x140 = terrain, +0x15C = change-sink, +0x194 = budget. That
**conflicts** with `GZCOM_INTERFACE_CATALOGUE.md:1240/1249` (which has +0x15C = BudgetLayer,
+0x194 = DemolitionLayer, +0x13C = DirtBag). SIMGEOM's bytes and the catalogue disagree on these
slots; resolving it needs the `cISC3City` vtable read directly from SIMCITY.DLL. No catalogue slot
was renamed on the strength of SIMGEOM alone.

#### 31.9.3 The other caller of the rect writer, and the one that is NOT it

- **`SIMUTIL.DLL+0x42C1`** = `FUN_100041ce`, 29 of the 30 observed calls, all during city load.
  It gets an occupant's bounding rect (`param_2->vt[0xd0](&local_34)`) and stamps it, but the
  value is forced to **zero** first: `param_2 = (int *)((uint)param_2 & 0xffffff);` then
  `&param_2 + 3`. This is the "networks dezone on occupant insert" path the iOS sibling shows,
  not a 22 producer.
- **`SIMRCI FUN_1001cd8f`** matched the arity-5 filter and is the **SC2 importer**: it reads a
  source grid via `piVar2->vt[0x18](0x100, ...)` and writes **2x2 blocks**
  (`iVar1*2, local_c, iVar1*2+1, local_c+1`) with a `*1000/2500` value rescale - the 128->256
  upscale. It independently corroborates the standing finding that the SC2 importer cannot emit
  22.

#### 31.9.4 New harness capability: `-modlog MODULE:VA[,VA...]`

The `-gzlog`/`-fnlog` tables are bound to one module at DllMain, so they cannot reach the sim DLLs
(SIMRCI, SIMGEOM, SIMBABLD) which load much later. `-modlog` registers the requests, the watcher
polls for the module, and installs the existing fnlog trampoline on arrival.

Each `-modlog` hook logs **its caller**: in the fnlog stub frame (`pushad` 32 + `pushfd` 4), the
entry `esp` sits at `f[9]`, which holds the return address, and `gz_modstr` resolves it to
`MODULE+RVA`. It also prints `ecx` and the first five stack args. That turns "who dispatches into
this slot" from an unbounded static sweep into one observation:

```powershell
$sw = '-nocom -windowed -origin -fix16 -fitclient -nointro -quiet -modlog SIMRCI.DLL:0x10032afa'
& re/harness/capture.ps1 -Name trace -Switches $sw -GzSeq '...;fire:0x10006401;at:360,150;wait:3000'
```

Note `pwsh -File` mis-parses a parameter value that begins with `-`; invoke `capture.ps1` with `&`
in the current session instead.

**Still open:** what `FUN_10007760` is. It is reached via `FUN_10006ba6` / `FUN_10006df6`, each
fronted by a family of small wrappers (`0x10006a65`, `0x10006a82`, `0x10006aa0`, `0x10006abe`,
`0x10006b02`, `0x10006b21`, `0x10006b40`, `0x10006b5f`, `0x10006adc`, `0x10006b7e`) that look like
per-variant thunks. Its `this` holds the zone layer at `+0x24` and three more subsystems at
`+0x28` (`vt+0x15c`), `+0x2c` (`vt+0xb0`) and `+0x30` (`vt+0x14`), and it switches on a mode value
of 1/2/3. Naming it is the natural next step and is left to the U-063 session.

#### 31.9.5 The special zone bytes 14 / 15 / 17 all take the ORDINARY zone path

Airport (14), Seaport (15) and Landfill (17) look special in the raster and in the query tool, but
mechanically they are plain zone tools. Each was selected by command and dragged, with
`SIMRCI 0x1003591f` (PlaceZone) and `0x10032afa` (the rect writer) hooked via `-modlog`, then the
city was saved and the raster diffed.

| tool | command | `PlaceZone` arg 1 | raster result | rect writer |
|---|---|---|---|---|
| Landfill | `0x10003004` | **`0x11` = 17** | 2 tiles, all `0 -> 17` | not called |
| Airport | `0x10003006` | **`0x0E` = 14** | 3 tiles, all `0 -> 14` | not called |
| Seaport | `0x10003005` | **`0x0F` = 15** | 8 tiles, all `0 -> 15` | not called |
| Com Medium (§31.9) | `0x10003202` | `0x06` = 6 | 10 tiles, all `0 -> 6` | not called |

**All four dispatch from the same site**, `SIMRCI.DLL+0xB8D2` - inside `FUN_1000b7d0`, the
tool-apply the U-063 chain names - and none of them touches the rect writer `vt+0x38`. So the
per-cell `vt+0x3c` path is the whole story for player zoning, and the rect writer is used only by
the two callers in §31.9.1/.3 (the building stamp of 22, and the SIMUTIL dezone-on-insert).

The chain is now observed end to end for **four** of the 13 zone bytes (6, 14, 15, 17), and the
tool-apply's own caller is `SIMRCI.DLL+0x3F8D1`.

**A refusal happens before `PlaceZone`, not inside it.** Two seaport drags at other coordinates
produced **no `PlaceZone` call at all** and zero raster change, while `FUN_1000b7d0` still ran -
so the tool fired and the `CanZone` gate (layer `+0x84`) rejected the site. `PlaceZone` is never
reached on a refused placement, which makes "was `0x1003591f` called?" a clean yes/no test for
site validity, independent of the funds counter.

**A caution about my own first two seaport attempts.** I concluded "seaports need water adjacency"
after two failures, then the *same* drag rectangle succeeded in a later run with no water nearby.
The failures were location-specific, not a property of the tool. `[UNCERTAIN]` what actually
distinguishes the accepted site from the rejected ones - slope, existing occupancy and adjacency
are all untested. Nothing was read to decide it, and the earlier guess is withdrawn.

Byproduct: the terrain tool **Place Water** (`0x10002002`) works from the harness (funds -$350, a
visible water body) and, as expected, changes **no** zone-raster byte.

#### 31.9.6 ALL 13 ZONE BYTES OBSERVED - the write path is closed at C4

Every zone tool was selected by command and dragged, with `SIMRCI 0x1003591f` (PlaceZone) and
`0x10032afa` (the rect writer) hooked via `-modlog`; the city was then saved and the raster
diffed against pristine Berlin. **All 13 zone types in the U-063 factory table are now observed
end to end**, and every one of them behaves identically.

| zone byte | tool | command | `PlaceZone` arg 1 | raster confirmation |
|---|---|---|---|---|
| 0 | DeZone | `0x10003007` | `0x00000000` | reverted a freshly-zoned patch back to 0 |
| 1 | Res Low | `0x10003101` | `0x00000001` | 2 tiles `0 -> 1` |
| 2 | Res Medium | `0x10003102` | `0x00000002` | 2 tiles `0 -> 2` |
| 3 | Res High | `0x10003103` | `0x00000003` | 2 tiles `0 -> 3` |
| 5 | Com Low | `0x10003201` | `0x00000005` | 2 tiles `0 -> 5` |
| 6 | Com Medium | `0x10003202` | `0x00000006` | 10 tiles `0 -> 6` (§31.9) |
| 7 | Com High | `0x10003203` | `0x00000007` | 2 tiles `0 -> 7` |
| 9 | Ind Low | `0x10003301` | `0x00000009` | 2 tiles `0 -> 9` |
| 10 | Ind Medium | `0x10003302` | `0x0000000A` | 2 tiles `0 -> 10` |
| 11 | Ind High | `0x10003303` | `0x0000000B` | 3 tiles `0 -> 11` |
| 14 | Airport | `0x10003006` | `0x0000000E` | 3 tiles `0 -> 14` |
| 15 | Seaport | `0x10003005` | `0x0000000F` | 8 tiles `0 -> 15` |
| 17 | Landfill | `0x10003004` | `0x00000011` | 2 tiles `0 -> 17` |

**Uniform findings across all 13:**

- Every call dispatches from **`SIMRCI.DLL+0xB8D2`**, inside `FUN_1000b7d0` (the tool-apply), whose
  own caller is `SIMRCI.DLL+0x3F8D1`.
- `PlaceZone`'s first argument is the zone byte itself, matching the CLSID baked into the tool at
  construction (`0x1000bb73` factory -> `0x1000ba68` ctor `this+0x124`).
- **The rect writer `vt+0x38` is never called by any of them.** Player zoning is exclusively the
  per-cell `vt+0x3c` path. The rect writer has exactly two observed callers, both in §31.9.1/.3:
  the building stamp of 22 (SIMGEOM) and the SIMUTIL dezone-on-insert of 0.
- 22 (`kPloppedBuilding`) is therefore the **only** raster value with a non-`PlaceZone` producer,
  which is consistent with it having no tool, no `MenuItem.INI` command and no factory arm.

**Method note on byte 0.** A `-> 0` transition cannot be shown against pristine Berlin by dezoning
virgin land, because those tiles are already 0. It was shown instead by zoning a patch Ind High
and then dezoning a sub-rect of it in the same run: `PlaceZone(0x0B)` then `PlaceZone(0x00)`, with
the file showing the un-dezoned remainder at 11 and the dezoned part back at 0.

**DeZone is refused on developed land**: a dezone drag over built-up Berlin produced no
`PlaceZone` call at all, the same `CanZone` (+0x84) gate as §31.9.5. `[UNCERTAIN]` whether the
blocker is the buildings, the zone type or something else - not investigated.

#### 31.9.7 `CanZone` decoded: what actually rejects a placement, and where the price comes from

`CanZone` is the zone layer's **`vt+0x84` = SIMRCI `FUN_1003559f`** (896 B), sitting directly above
`PlaceZone` at `vt+0x88`. Slot numbers verified with `re/scripts/read_vtables.py`: `PlaceZone`
`0x1003591f` lives at `.rdata 0x1004d268`, and `--starts` proves the vtable begins at `0x1004d1e0`
(loaded as an immediate from constructors `0x100311bf` / `0x10031376`), so
`0x1004d268 - 0x1004d1e0 = 0x88` and `CanZone` is the dword at `0x1004d264` = `0x1003559f`.

**Signature:** `bool __thiscall CanZone(uint zoneType, cSC3Rect *area, uint *outCost)`.
It is not just a predicate - **it prices the operation and returns the total in `outCost`.**

**Per-tile rejection, in evaluation order:**

| # | test | effect |
|---|---|---|
| 1 | `(this-0x10)->vt[0x34](x,z,&cur)`; `cur == zoneType` | tile **skipped** - not counted, not charged. Re-zoning to the same type is a no-op, not a failure |
| 2 | `occupantMgr->vt[0x7c](x,z,&occ)` finds an occupant, then `occ->vt[0x74]()` is false | tile **rejected** |
| 3 | occupant flags via `occ->vt[0x3c](f)`: `0x400000` **and** `0x800` both set | tile allowed, and a **demolition surcharge** is added (`local_20 += local_28`) |
| 4 | else `0x400` set | tile allowed, no surcharge |
| 5 | else | tile **rejected** |
| 6 | `layer2->vt[0x54](x,z)` returns true (`layer2` = `this+0x34 vt+0x13c`) | tile **rejected** |
| 7 | **1x1 placements only:** the four corner altitudes at (x,z), (x+1,z), (x+1,z+1), (x,z+1) via `vt[0x4c]` must be **ALL EQUAL** | otherwise **rejected** |

**Test 7 is the notable one: the flatness requirement is applied ONLY to a single-tile placement.**
The multi-tile branch (`else`, the row/column loop) never performs the corner-altitude comparison
at all. So a 1x1 zone demands level ground and a dragged rectangle does not. `[UNCERTAIN]` whether
slope is enforced elsewhere for rectangles - nothing was read to decide it.

**Pricing.** `zoneType` maps to a price CATEGORY, then `budget->vt[0x58](category)` gives the unit
price (`budget` = `this+0x34 vt+0x15c`):

| category | zone types |
|---|---|
| 0 | 1, 5, 9 (all LOW density) |
| 1 | 2, 6, 10 (all MEDIUM) |
| 2 | 3, 7, 11 (all HIGH) |
| 3 | 17 Landfill |
| 4 | 14 Airport |
| 5 | 15 Seaport |
| 6 | 0 DeZone |
| - | anything else -> unit price 0 |

`*outCost = unitPrice * zonableTileCount + demolitionSurcharge`.

**Whole-call rejection** (the `bool` return) is then just two conditions:

1. `zonableTileCount == 0` - every tile in the rect was skipped or rejected, **or**
2. `cost != 0` and `funds < cost`, where funds is `budget->vt[0x10]()` returned as a **longlong**.

That is the complete answer to "what does `+0x84` reject": no zonable tile, or not affordable.

**Which branch caused THIS session's refusals is not isolated.** The seaport and dezone failures
(§31.9.5/.6) each produced a `FUN_1000b7d0` call with no following `PlaceZone`, so `CanZone`
returned false, but the hook logs entry arguments only and cannot see the return or the written
`outCost`. Affordability is implausible on its face - Berlin held $117,006 and the successful
seaport covered 8 tiles - which points at tests 2/5/6 (occupant present and not demolishable),
consistent with the red cannot-build overlay observed over existing buildings. **That is reasoning,
not measurement**; isolating it needs a hook that reads `outCost` and the return value after the
call, which was not built.

### 31.10 Still open

- **Route alpha, not yet built:** `SIMINIT.DLL+0x8bf8` is
  `__thiscall bool(cIGZString* path, cISC3NewCityInfo*)` (`ret 8`, bool in **AL only**) - a
  direct path->load that skips the picker entirely. `cRZString` ctor-from-`char*` is
  `SIMINIT+0x1284` (`__thiscall`, `ret 4`, object 0x14 bytes, vtable `SIMINIT+0x2F230`), dtor
  `SIMINIT+0x21757`. The only virtuals the loader calls on the string are `vt+0x1c` (length) and
  `vt+0x18` (data). Must run on the game thread; fails **modal** if the sim manager
  (`app_iface+0x18`) is NULL, so pre-check it. Now redundant for "get into a city" but still the
  cheapest way to load an ARBITRARY path.
- `version.dll` standalone loader flakiness (§30.3 item 2) - unchanged.
- Intermittent early clean-exit (§30.3 item 3) - unchanged.
- Intro movie half-width, U-025 (§30.3 item 4) - unchanged.

## 32. The `-windowed` flag warrant was FALSE - the game writes it itself (2026-08-19)

Handed off from the zone-raster session, verified here. The long-standing claim that the
windowed-mode byte `GZGraphicD.dll+0x6CDAC` (`DAT_1006cdac`) has "exactly one reference in the
whole DLL, zero writers" is **falsified**, and the runtime consequence is bigger than the
bookkeeping error: the game sets that byte to 1 by itself during startup, so the probe's poke of
it is **redundant**.

### 32.1 The static facts, verified in the image bytes

`DAT_1006cdac` has exactly **two** references in `GZGraphicD.dll`, and one is a **write**:

```
0x10010EF6  A2 AC CD 06 10        mov  byte ptr [0x1006CDAC], al     <-- WRITER
0x10011537  80 3D AC CD 06 10 00  cmp  byte ptr [0x1006CDAC], 0      <-- the known read
```

Independently confirmed by scanning the whole image for the literal address `0x1006CDAC`: two
hits, at `0x10010EF7` (the imm32 of the `A2` store) and `0x10011539` (the imm32 of the `80 3D`
compare), and nothing else. The write sits in a 12-byte `__stdcall` setter:

```
0x10010EF2  8A 44 24 04   mov al,[esp+4] / A2 AC CD 06 10  mov [0x1006CDAC],al / C2 04 00  ret 4
```

and that setter is **dispatchable** - `0x10010EF2` occupies two aligned `.rdata` vtable slots,
`0x1001EDC4` and `0x1001EFA0`. So it is a normal `Set<flag>(bool)` reachable through a vtable,
which is exactly why an xref/grep over the decompilation export missed it (the same U-057/U-063
lesson: vtable dispatch is invisible to a static caller search). The original "zero writers" came
from grepping the export, which does not carry the write.

### 32.2 The runtime measurement, and why the first attempt was worthless

Hooking the setter `0x10010EF2` and the Init reader `0x100114B8` with `-modlog`, run into a city
windowed:

- **First attempt: the detour did not install.** The log said
  `UNDECODABLE prologue 8A 44 24 04 A2 - skipped`. The probe's length-disassembler was missing the
  `A0..A3` opcode class (`mov AL/eAX <-> moffs32`, 5 bytes, absolute operand). A "0 hits" reading
  from that run would have been a pure U-033 artifact - absent, not zero. **Fixed** by adding the
  class; those instructions are position-independent so they copy into the trampoline verbatim.
- **Second attempt: still 0 hits, but for a different reason.** The `-modlog` install ran on the
  100 ms watcher tick, and GZGraphicD Init had already executed at ~t+33 ms. The hook was simply
  too late. **Fixed** by installing `-modlog` detours at the module-ready point (where the
  GZGraphicD patches already go in) instead of on the tick.
- **Third attempt, valid:** setter **1 hit**, reader **1 hit**, ordering:

  ```
  t+22.0 ms  our patch writes 0x6CDAC = 1
  t+40.8 ms  SC3U.exe+0x5D32 calls the setter with al=1
  t+40.9 ms  FUN_100114b8 (Init) reads it -> windowed
  ```

The setter's `al` is the low byte of arg1: `a1=0x00562F01` -> `al=1`.

### 32.3 The control run, and the conclusion

**With no `-windowed` patch at all**, the game *still* calls the setter with `al=1` from the same
`SC3U.exe+0x5D32` (`a1=0x005A4401`) at t+44 ms, and Init reads it 0.1 ms later. So the byte is 1
at Init time in both configurations - **the game writes it itself.**

Directly tested with a new `-nowinflag` switch (apply only the `0x117D6` nop, skip the `0x6CDAC`
poke): **windowed mode works, full city load and render, reproduced twice.** A `wflag_check`
heartbeat confirms the byte, left at 0 by us, reads **1** through the whole run - the game set it.

**Consequence.** The operative half of `-windowed` is the `0x117D6` nop (which stops Init line 146
re-forcing fullscreen on the `bpp != desktop` clause). The `0x6CDAC` poke is redundant on this
build: it writes a value the game writes anyway, ~19 ms later. The patch was never *broken* - it
works - but its stated warrant ("nothing writes this byte, so poking it is safe and necessary")
was false on both counts. The honest statement is: **one writer exists and is called every
startup with al=1; our poke duplicates its effect and could be dropped.**

`[UNCERTAIN]` what `SC3U.exe+0x5D32`'s enclosing function decides the flag *from* - it is passed
`al` from arg1, so some caller computes windowed-vs-fullscreen and this is just the store. Whether
a configuration exists where it passes `al=0` after Init (which would matter for a build that
relied on the poke) was not traced. The `wflag_check` monitor now catches any such late write for
free on any run.

### 32.4 New harness switches

- `-modlog MODULE:VA[,VA...]` now installs at module-ready, not on the watcher tick, so a hook on
  an early-Init function is not missed. It also logs `MODLOG[i]: will hook...` at parse time and
  `MODLOG: <mod> loaded... -> hooking...` at install, so "did the detour install" is answerable
  before trusting any hit count (U-033).
- `-nowinflag`: apply the `0x117D6` nop but skip the `0x6CDAC` poke. Built to run the isolation
  above; keep it as the reproducer.
- The probe's length-disassembler now decodes `A0..A3`. Any earlier `-modlog`/`-fnlog` target
  whose prologue began with one of those (a `mov al,[moffs32]` accessor) would have been silently
  skipped before this fix.

## 33. RESIZABLE WINDOW: menu path working, in-city six defects deep (2026-08-21/22)

Goal: a user-resizable game window. Verdict: **the menu path works and is verified on a stock
install; in-city, six defects were found, five fixed and verified, the sixth diagnosed.** All
in-city measurements were taken on Berlin, with `map(+0xec,+0xf0)=256x256` logged every run.

> ⚠️ **Provenance caveat.** This work ran on a shared install alongside three other sessions.
> Anything here NOT explicitly marked re-verified was captured inside a window (2026-08-20 10:43
> onward) when `Apps\SIMUI.DLL` / `SIMINIT.DLL` / `SIMDIRT.DLL` were intermittently patched by the
> bigger-cities session. mtime checks CANNOT detect this (`shutil.copy2` preserves mtime on
> restore). The honest method is a runtime hash recorded with the result: `game_lock.ps1`.
> The in-city results are argued clean because the SIMDIRT **stride was never patched**, so all
> three states that existed on disk are behaviourally identical at N=256 (see 33.7).

### 33.1 What works: the menu path [CONFIRMED, re-verified on a stock install 2026-08-22]

`sc3launch -nocom -windowed -origin -fix16 -fitclient -nointro -resizeto <W>x<H>`

1. **Sizing border.** `FUN_100181d0` @ `0x100181d0` builds the style from the flag word at
   `window+0x10`, which `FUN_10017c83` hardcodes to `0x1b` giving `0x80CA0000`. **No bit in that
   decode can produce `WS_THICKFRAME`**, so it is added from outside with `SetWindowLongA`. Observed
   style is `0x94CA0000`, i.e. USER32 adds `WS_VISIBLE|WS_CLIPSIBLINGS` - this closes the
   long-standing `[UNCERTAIN]` about where `WS_CLIPSIBLINGS` came from.
2. **Device rebuild.** `FUN_1001673b` @ `0x1001673b` (device vt `+0x20c`) releases every surface,
   then `FUN_10015e3d` @ `0x10015e3d` (sub-object vt `0x1001f290` slot 4) rewrites the device rect
   and rebuilds. **1.8 ms, no crash.** Do NOT use `FUN_100169d3` (vt `+0x10`): it also releases
   `device+0xa8`, the GZ DirectDraw wrapper the rebuild needs. Call `+0x20c` directly and zero
   `device+0x08` and `device+0x80` by hand. `device+0x88` is the present re-entrancy lock - read
   only, never force it (section 13.3 hangs the game).
3. **Window rect.** `FUN_10018691` @ `0x10018691` (window vt `+0x1c`) is the only writer of
   `+0x38..+0x44`, and **it propagates into the GZ widget tree by itself** via `sink->vt+0xc` then
   `vt+0xC8`: the root cGZWin already read `0,0,1280,1024` before any explicit call. That is the
   confirmed link between the Win32 window and the widget tree.
4. **UI reflow.** The root resize does NOT resize its children (GZWinD has no anchor system).
   Applied externally: children exactly the old screen size are stretched, others keep their size
   and shift by half the delta. Menu panel `192,144,832,624` becomes `320,272,960,752`, i.e.
   `abs_centre=640,512`, the exact centre of 1280x1024.
5. **Backdrop.** Geometry is CACHED at `this+0xc8..+0xd4` behind a load-once guard
   (`0x0043e071 cmp [esi+0x10],0 / jne`). Re-derive it with the game's own pair on the second base
   at `backdrop+0xa4`: `+0x20` = `FUN_0043e48e` (release raster, clears the guard) then `+0x24` =
   `FUN_0043e9b4` (re-prepare + invalidate). Measured `dst` `112,84,912,684` becomes
   `240,212,1040,812`, which is 800x600 art centred in 1280x1024, exactly as predicted.

Art note: the menu backdrop is a **fixed 800x600** asset (`Apps\Res\UI\Shared\MAIN.IXF`,
`{T=0x62b9da24, G=0x82b9b75c, I=0x22729921}`, header `w=0x320 h=0x258`), and the four rects at
`this+0xd8/+0xe8/+0xf8/+0x108` are **colour fills** (device `+0x7c`, colour 0) forming a deliberate
black frame. So the game already letterboxed it at 1024x768. Registry override for a replacement:
`HKLM\...\SimCity 3000 Unlimited\SKU\WINSC3BMP = "<group>,<instance>"`.

**Bonus finding: the game accepts FIVE resolutions, not three.** `FUN_00407684` @ `0x00407684`
snaps to 640x480, 800x600, 1024x768, **1152x864, 1280x1024**; anything else snaps by area, and
`-r1600x1200` lands on 800x600. Ghidra reports zero xrefs; resolved by byte scan to vtable
`0x004cf59c + 0x68`, called from `FUN_004077b5:52` (the `-r` path) and `FUN_0040586a:207`. Above
width 800 `FUN_100270e5` reuses the 1024x768 widget table, so 1152x864 and 1280x1024 run with
1024x768 widget coordinates.

### 33.2 In-city: the six defects

Re-entering the SIMSPR iso view's Init (`FUN_10005b42` @ `0x10005b42`, vt `+0xc`) at a new pixel
size hits six stale-state problems. Every one is the same shape: **Init reallocates or resets
something a sibling subsystem still references.**

| # | Defect | Fix | Status |
|---|---|---|---|
| 1 | tile cache `iso+0x24` reallocated **empty** (old one leaked) | refill via `FUN_10018cdf` @ `0x10018cdf` on the occupant bridge | **verified**, row 0 54/64 to 0/64 to 54/64 |
| 2 | camera origin reset to world `0,0` | save `+0x54..+0x60`, restore after Init keeping the NEW span | **verified**, `512,2352,1792,3376` |
| 3 | zoom/rotation are Init's `param_7`/`param_8` | pass the CURRENT values so both setters early-out | **verified**, zoom 3 / tilew 64 (was collapsing to 0 / 8) |
| 4 | stale flag-change queue at `iso+0x448`/`+0x44c` drained against the zeroed cache | discard the vector (`end = begin`) | **verified**, 20 stale entries |
| 5 | `FUN_1000dc17` called with **no args** so `param_1` (surface lock flag) = 0 | drop it, use vt `+0x14c` = `FUN_1000b4b3` | **verified**, crash gone |
| 6 | `dev->vf0c(w,h)` **fails** and Init ignores the return, so the render target has no backing store | not fixed | **diagnosed** |

**Defect 5 was OUR bug, not the engine's.** `FUN_1000dc17` is `__thiscall(this, param_1, param_2)`
and `param_1` is the surface lock flag: `0x1000dd2f cmp byte [ebp+8],0 / je` skips
`device->vf1c(0x40)`, `0x1000dfd4` skips the matching `vf20(0x40)`. With the lock skipped,
`device->vf1a8()` (valid only while locked) returns null and SIMDIRT's span rasterizer
`FUN_10013556` stores at `0x10013A8F` (`mov word ptr [ecx],ax`) with **ECX = 0xBC** = 94 px times 2.
Every game call site passes `1`. Use `+0x14c` instead, which runs `FUN_1000e248` (clears the
dirty-rect queue at `+0x4b8`/`+0x4bc`, clears all three display lists, memsets the grid at the NEW
dims), clears `+0x32c`, enqueues 64 rects tiling the visible rect, then calls `vf148(1,1)`.

**Defect 6, the open one.** With the lock correctly taken:

```
device probe: dev=0x14C724A0 vt=GZGraphicD+0x1E894  lock(0x40)=1
  vf1a8(bits)=0x00000028  vf1ac(pitch)=0  vf38(w)=0  vf3c(h)=0
surface was 0x0 - dev->vf0c(1280,1024) -> 0
  after vf0c: lock=1 bits=0x28 pitch=0 w=0 h=0
```

The lock **succeeds** and the surface is still dead, and driving the device's own in-place resize
(`dev->vf0c`, the call Init makes at about `0x10005b7c`) returns **0**. So it FAILS and Init ignores
the return - it does not "silently no-op". Consequence: `iso+0x524` (display-list item count) stays
0, and `FUN_1000dc17` does nothing when that is 0, so nothing draws. Next step is the DirectDraw
teardown/rebuild ordering, not SIMSPR.

### 33.3 Two bugs in shipped SC3K code

1. **`FUN_10005fd0` (iso teardown, vt `+0x10`) has a self-inflicted NULL dereference.** Its first
   block frees and NULLs the five sprite caches at `iso+0x490`; its second tile loop then
   dispatches `this->vt+0x68`, whose callee reads those very slots at `0x10007ea9`
   (`mov ecx,[esi+eax*4+0x48c]`) and faults at `0x10007eb3`. Reproduced twice, byte-identical,
   with and without a prior DirectDraw teardown. Workaround: clear the `iso+4` guard so Init skips
   its teardown (the teardown itself ends with `*(byte*)(param_1+1) = 0`).
2. **`iso+0x3c8` is never cleared by anything.** It means "the five caches have been constructed",
   Init sets it, and the teardown frees the caches **without** clearing it - so one teardown
   permanently falsifies the invariant.

### 33.4 iso+0x3c8 vs iso+0x3c9, and the sprite caches

- `+0x3c9` = **async/deferred sprite loading enabled**. Sole writer `FUN_10008203` @ `0x10008203`
  (vt `+0x160`), getter `+0x15c`. Refuses to enable when `+0x3c8 == 0`; clearing it only writes the
  byte when its drain argument is non-zero.
- **DO NOT clear `+0x3c8` to force a cache rebuild.** Measured: Init then builds five fresh caches
  with all refcounts 0 and all per-zoom surfaces NULL (`0000C8CE` to 0, `128AE5C8` to NULL), and the
  display-list builders (`FUN_1000be25:147`, `FUN_1000d0f5:244`, `FUN_1000b352:35`) read those slots
  **ungated**, giving an instant `0xC0000409`.
- The caches are keyed by **(footprint size 1..5, zoom 0..4)**, resource id
  `0x1b870000 + (slot*0x4000 + min(zoom,3))*4`, sized from resource headers. **Resolution-
  independent and size-independent** - no map-dimension term anywhere. They need no rebuild on a
  resize. Confirmed jointly with the bigger-cities session for its N=512 case too.

### 33.5 Corrections to committed analysis

- **The flip-chain fields were recorded backwards.** `FUN_10019cc7` puts the *primary* in `this+8`
  and the *back buffer* in `this+4`; windowed `FUN_100199c0` puts its plain primary in `this+4`. So
  `this+4` is always "the surface everything uses". Section 10h's statement is true but means
  something different than recorded. `this+8` has **no Release site anywhere** in 1093 functions.
- **`FUN_0044160a` (`+0x168`) is NOT a cascaded repaint.** It is RecomputeAbsoluteRectTree - pure
  translation, no clamp. The real paint is `+0x148` = `FUN_004413ef` @ `0x004413ef`.
- **`FUN_100059fb` returns block COUNTS, not sizes.** Pixel size is `span/count` in `FUN_1000e2c0`.
  1280 gives 40; 1024 as a *height* gives 64 but as a *width* gives 32.
- **`FUN_10006226` is vt `+0x2c`, not `+0x98`** (`+0x98` is `FUN_10008eee`).
- **The root cGZWin's SetArea is `GZWIND+0x1F603`, not `SC3U+0x41d4c`.** The root is a plain
  GZWinD cGZWin; `FUN_00441d4c` is a different SC3U-side class's copy.
- **`iso+0x54..+0x60` is a full `{l,t,r,b}` rect in WORLD PIXEL space**, not a screen viewport and
  not just an origin. Init writes it as `(param_5, param_6, param_3, param_4)`, i.e. it assumes an
  origin of 0,0 - which is also why `param_3`/`param_4` double as the pixel size feeding
  `FUN_100059fb`. So the real origin cannot be passed as `param_5`/`param_6` without corrupting the
  grid lookup; restore it after Init instead.
- **`iso+0x1c`/`+0x20` are NOT the stored window size.** Measured `0,0` while the rect read
  `0,0,1024,768`; they are last-mouse-x/y. Window `vt+0x30` is `FUN_100185f5`, confirmed at runtime.
- **`-l` is `-language`, not load-city** (already flagged in 29.3 by 31.5; re-confirmed the hard
  way - two runs sat at the menu). The working auto-load is
  `-gzseq "0x712BF5BF@12;0x02DFDD6A@28"`.

### 33.6 Two queues, not one

Do not conflate them:

- `iso+0x448`/`+0x44c` - **flag-change** queue, 4-byte records `{opcode, x, y, zoomIdx}`, drained by
  `FUN_10008dd4` @ `0x10008dd4`. This is the resize landmine (defect 4): Init reallocates the tile
  cache **zeroed**, so every record's footprint byte at `+0x0a` reads 0 and `FUN_100080a9` computes
  `this + 0*4 + 0x48c` - one slot BEFORE the cache array at `+0x490` - and dereferences it.
- `iso+0x4b8`/`+0x4bc` - **dirty-rect** queue, `0x14`-byte records, drained by `FUN_1000dc17` and
  cleared by `FUN_1000e248`.

The landmine is specific to **re-entering Init on a live view**. On a fresh city the view is newly
constructed (`FUN_1001c4a1` @ `0x1001c4a1`: `operator_new(0x528)` then `vt+0xc`), so the vectors are
empty - confirmed jointly with the bigger-cities session from its crash stack.

### 33.7 Multi-session hazards, measured

Four sessions shared one install, one `sc3probe.dll` and one process namespace. Each of these cost
hours and all are now covered by `re/harness/GAME_PROTOCOL.md` plus `game_lock.ps1`:

- **Cross-session process kills.** `Stop-Process -Force` matched on process NAME kills other
  sessions' live runs. Match on your own `sc3launch` PID and the `SC3U` whose parent it is.
- **The single-instance handoff is silent.** With an SC3U already running, a new launch takes
  `FUN_0040496d` (mutex plus `FindWindowExA "Gonzo"/"SimCity 3000"`), exits `0xFFFFFFFF` at about
  840 ms and writes **no crash dump**. An early exit with no dump usually means this, not a crash.
- **mtime cannot detect historical patching.** `shutil.copy2` preserves mtime on restore, so a
  patched-then-restored install looks pristine. Hash at run time and record it with the result.
- **`find_game_window` must filter by PID.** Unfiltered it can return a FOREIGN process's `Gonzo`
  window; subclassing that would drive a device teardown against a game you do not own. Fixed by
  the queue session.
- **Harness bug worth remembering:** subclassing before the graphics window object exists makes
  `SetWindowLongA(GWL_WNDPROC)` return 0, after which `CallWindowProcA(NULL, ...)` swallows every
  message and startup dies at about 840 ms with no dump. Gate on `GZGraphicD+0x6CDB8` being
  non-NULL.

### 33.8 Testing gaps

- **Downward resize is completely unexercised.** Every run grew 1024x768 to 1280x1024. The
  bigger-cities session confirmed a stale-bounds hazard for exactly this case: `iso+0x420`/`+0x424`
  (mirrored at `+0x3f8..+0x404`) are set once, inside the `+0x3c9 != 0 && +0x3c8 == 0` block, to
  `cols-1`/`rows-1`, and **never refreshed**. Harmless growing, dangerous shrinking. So read 33.1
  and 33.2 as "resize UPWARD works".
- Only 1280x1024 was tested. 1152x864 and non-snapped sizes are untried.
- The tile-cache realloc **leaks**: `cols*4 + cols*(rows*0x14)` per Init, about 1.31 MB at N=256 and
  about 5.24 MB at N=512, in a 32-bit process.

### 33.9 New harness switches

`-resize` (sizing border plus rebuild on `WM_EXITSIZEMOVE`), `-resizeto <W>x<H>`, `-resizeat <sec>`,
and `SC3PROBE_RESIZE_NOPAINT=1` (skip our paint, leave it to the game's frame loop). The auto-resize
holds until the occupant bridge exists with a 20 s fallback, so **`-kill` must be at least
`resizeat` + 22** or the run is cut off mid-gate.

---

## §31.10 — U-068 fix attempt: the pre-registered negative, and grid B's two node classes (2026-08-24)

> ⚠️⚠️ **THIS SECTION'S VERDICT IS WITHDRAWN — read §31.11 first.** The negative below was
> adjudicated with `iso+0x524`, which §31.11 shows is a **drained** reading and not a symptom
> indicator. **"Grid B is ruled out as the blocker" is NOT established.** The node-class split and
> the post-Init census survive, because those were read off the structure; the verdict does not.

**The fix was applied, it worked mechanically, and it did not fix the symptom. That is the
outcome the diagnosis session pre-registered, and it is recorded as such rather than retried
until it looked positive.**

### What was run

Candidate (b), re-drive registration — and **not** a reimplementation. The engine has its own
bulk re-registration, `FUN_1000fa36` @ `0x1000fa36` (SIMSPR), which walks the object collection at
`iso+0x3a4` with the same iterator pair `FUN_10013592`/`FUN_10010c4b` that the shipped
`FUN_1000fb29` uses, doing `FUN_1000e4ce` + `FUN_1000effc` → `FUN_1000ef50` per object. It is
shipped code on the scroll route (`FUN_1000c9bd:109`). Prologue verified at runtime before calling
and re-verified here against the anchored DLL: `55 8b ec 83 ec 10 80 7d 0c 00`
`[CONFIRMED @ 0x1000fa36, SIMSPR.DLL]`.

Called after the Init replay, the camera restore and the tile refill, because `FUN_1000effc` maps
cells through `iso+0x54`/`+0x58` and `+0x39c`/`+0x3a0`. Gated behind `SC3PROBE_U068FIX=1`.

### The measurement

| point | type-1 (drawable) | type-2 | non-null cells | `FUN_1000ef50` |
|---|---|---|---|---|
| immediately after Init | **0** | **0** | 0/64 | 1286 |
| after camera restore | 0 | 0 | 0/64 | 1286 |
| after `FUN_10018cdf` refill | **0** | **1537** | 64/64 | 1286 |
| after the fix | **213 in 37 cells** | 1537 | 64/64 | **1499** |
| after the redraw | 213 | 1537 | 64/64 | 1499 |

Grid B repopulated (+213 inserts, counter 1286 → 1499), `builder_hi` was reached **+64** times over
the now-populated grid, and **`iso+0x524` is still 0** with `bg=0 sprites=0`.

> That is **falsifier 3 of the pre-registered set, hit exactly**: *"if grid B is repopulated and
> `iso+0x524` is still 0, grid B was contributing and not the blocker — my fix failing rather than a
> new defect."* Grid B was contributing **at most**. The blocker is elsewhere.

### ⭐ The finding that outruns the root cause: grid B holds TWO node classes

`[CONFIRMED]`, re-verified in the export:

| function | writes | meaning |
|---|---|---|
| `FUN_1000ef50` @ `0x1000ef50` | `*(undefined1 *)(puVar2 + 2) = 1` | **type 1** |
| `FUN_1000cedb` @ `0x1000cedb` | `*(undefined1 *)(piVar6 + 2) = 2` | **type 2** — a second, inlined inserter |

And **both** builders gate on type 1:

- `FUN_1000d0f5:111` — `if ((char)local_30[2] == '\x01')`
- `FUN_1000be25:282` — `if (((*(byte *)((int)puVar16 + 0x29) & 0x80) == 0) && ((char)piVar17[2] == '\x01'))`

Consequences, and they resolve an apparent contradiction in the earlier notes:

1. The census immediately after Init (0 nodes, 0 cells) **confirms the root cause by reading the
   structure**, not by counting calls. That half of `U-068` stands.
2. The tile refill puts **1537 nodes back into all 64 cells — every one type 2**, invisible to every
   builder. So *"nothing re-registers"* and *"the grid is not empty"* are **both true, about
   different node classes.**
3. ⚠️ **An undifferentiated node count of grid B measures nothing.** The first census in this run
   made exactly that mistake and read a 100%-type-2 grid as "populated". It cost a run to catch.
   Any future instrument on grid B must split by the type byte at `node[2]`.

### Next lead — NOT measured, do not cite as a result

The rejection is **downstream of the type-1 test, inside the builder**: `FUN_1000a62c`, then
`FUN_10008528(...)`, whose non-zero return is what increments `+0x524`. A call-site counter on that
`E8` — the same mechanism that worked here, chosen because entry detours on per-tile functions killed
the load at 6.7 s — is **one run**.

`[UNCERTAIN]` **213 type-1 nodes after the fix versus 1286 inserts at load.** That gap is not
explained. It may be the difference between per-object and per-object-cell insertion, or the
collection at `iso+0x3a4` not holding everything a load registers — neither was measured.

### Run hygiene

4 launches, **one void**: the driving shell mangled a log path via a `\u` escape so that run wrote no
log. **No run crashed or exited early**; all ran the full 50 s to `-kill`. Install verified stock
afterwards; harness claim and game lease both released. The resizable-window session's
`find_game_window` / `rz_*` code was checked intact before and after.

Session write-up: `re/sessions/STATUS_u068-fix.md` (untracked by design, like the other
`re/sessions/*` checkpoints). Logs: `re/harness/u068fix3.log` is the type-split one.

## §31.11 — ⚠️ `iso+0x524` IS NOT A SYMPTOM INDICATOR. §31.10's verdict is withdrawn. (2026-08-24)

**One run, outcome 4 of a pre-registered four, and the agent's own prediction (outcome 3) was
falsified and reported as such.** Call-site counters, no entry detours.

### The readings

| site | before | after | delta |
|---|---|---|---|
| `+0xD313` → `FUN_1000a62c` | 0 | **0** | +0 |
| `+0xD33A` → `FUN_10008528` calls | 285 | 501 | **+216** |
| `+0xD33A` **non-zero returns** | 214 | 430 | **+216** |
| `+0xD355` → `FUN_10010896` append | 214 | 430 | **+216** |
| `+0xD568` / non-zero / `+0xD581` (2nd path) | 2770 / 2441 / 2441 | 4307 / 3978 / 3978 | **+1537 each** |

Grid B at that moment: **216 type-1** in 39 cells, **1537 type-2**, `items(+0x524)` = **0**.

Both call sites verified against the anchored DLL: `0x1000d313` and `0x1000d33a` are `E8`s resolving
to `0x1000a62c` and `0x10008528` `[CONFIRMED]`.

### `FUN_10008528` rejects nothing, and the instrument calibrates itself

216 calls, 216 non-zero returns, 216 appends. **+216 = +216 = +216** matches the 216 re-registered
type-1 nodes exactly, and **+1537 = +1537 = +1537** matches the type-2 count. Every grid-B node of
both classes reached the overlap test, passed it, and was appended. **Nothing is filtered anywhere.**

`FUN_1000a62c` reads 0 — but it also reads 0 during normal pre-resize gameplay, so it is simply not
on the live path (`param_2 == 0` always). That ambiguity was **pre-registered as a caveat before the
run**, and is not claimed as a finding either way.

### ⚠️ What this overturns

**The builder appends, and `+0x524` then reads 0. So `+0x524` is a DRAINED reading taken after the
paint consumed the lists — not evidence that the builder produced nothing.**

Corroboration from inside the same run: at t+13.8 s, **pre-resize, with the city rendering
normally**, the counters already stood at 285/214/214 and 2770/2441/2441. Normal rendering produces
the same shape of traffic, and the post-resize delta (+216) is the same order as normal gameplay's
214.

> ### `iso+0x524 == 0`, sampled after a redraw, never meant "the display lists are empty".
> **Every conclusion resting on that reading needs re-reading**, including §31.10's and including the
> `U-068` framing that predates it.

**§31.10's verdict is WITHDRAWN.** Its falsifier 3 was *"grid B repopulated AND `iso+0x524` still 0 ⇒
grid B was contributing, not the blocker"* — and the negative half of that test is now known not to
discriminate. **"Grid B is ruled out as the blocker" is NOT established.** The re-registration fix may
have worked; nobody looked at pixels.

### What survives, and why

| claim | status | because |
|---|---|---|
| type-1 / type-2 node split | **stands** | read off the structure and re-verified in the export |
| census A: 0 drawable nodes immediately after Init | **stands** | read off the structure, not off `+0x524` |
| 1285 inserts on load vs 0 after a resize Init | **stands** | insert counters, not `+0x524` |
| "grid B ruled out as the blocker" (§31.10) | **withdrawn** | adjudicated with an instrument now known to be invalid |
| "display lists stay empty after a resize Init" (`U-068` as originally framed) | **`[UNCERTAIN]`** | the phrase encodes the `+0x524` reading |

### The honest next instrument is pixels, not another counter

`[UNCERTAIN]` **whether the city actually renders after the resize. Nothing measured so far looks at
pixels.** `WINDUMP` reporting `[UNIFORM - capture produced no content]` is a headless
window-capture artifact and is **not evidence either way**. The next step is a frame capture through
the probe's blit mirror (`-shot`), which is the observable this whole chain has been proxying for.

### Mechanism note worth keeping

Counting a *return value* needs a stub that outlives the callee. A bare `call orig` would have shifted
every argument by 4; the stub re-pushes both args and does the `ret 8` cleanup itself. Callee cleanup
confirmed from the shipped tail `32 c0 5f 5e 5b c2 08 00` at `0x10008597` `[CONFIRMED]`, consistent
with `FUN_10008528`'s `mov edx,[esp+8]` entry. No entry detours were used.

## §31.12 — ⭐ U-068 MEASURED IN PIXELS AT LAST: the fix is genuinely insufficient (2026-08-24)

**One run, three shots, a within-run A/B with the fix applied mid-process so city, camera, lighting
and window state are identical across the comparison.** Outcomes pre-registered before launch.

| shot | when | result |
|---|---|---|
| **A** pre-resize, in city — **the instrument control** | t+19.797 s | **Europolis fully rendered**, `Pob: 2,069,432  §364,671  3/22/2088` |
| **B** post-resize, fix withheld | t+24.620 s | **iso viewport BLACK**; toolbar, status bar and minimap fine, minimap showing a populated city |
| **C** post-fix (`FUN_1000fa36` re-registration) | t+26.357 s | **still BLACK.** Only difference: the tip dialog finished compositing |

**Verdict: row 3 of the pre-registered table — A good, B black, C black. The fix is genuinely
insufficient. Repopulating grid B is not sufficient for the iso view.**

Both A and C were viewed directly by the orchestrator before promotion, not accepted on report.

Provenance is clean and was designed to be: exactly three dumps (the 3 s auto-shot suppressed), each
written after its request, and phase C did not begin until `g_shot_seq` passed B's — the log records
`PHASE C … shot B is written (seq now 2, B was requested at seq 1)` one millisecond after `SHOT #2`.
**So B cannot have captured the fixed state.** This is the `U-070` lesson applied in advance rather
than regretted afterwards.

### It is not a null instrument — the fix ran, and the builder consumed its output

In the same process, one millisecond apart: grid B **0 → 208 type-1 nodes in 39 cells**, insert
counter **1290 → 1498 (+208)**, `FUN_1000b4b3 redraw → 246`, `FUN_1000e206 present → 1`, and
`clip_8528` **+208 calls, +208 non-zero, +208 appends**.

> **+208 in, +208 accepted, +208 appended, screen still black.**
>
> **The defect is downstream of the display list entirely** — in the rasterisation or blit of the iso
> view's render target, not in grid B and not in the builder. Every stage this project has
> instrumented for two days is working.

### ⭐ A separate defect, now on record: the in-city UI does not reflow

Visible in B and C. The window is 1280x1024 but the UI is still laid out for **1024x768**, with
~256 px black margins right and below: tool palette at x≈930..1023, status bar stopping at 1023,
minimap at the old corner, and a stray magenta 24x16 widget stranded at ~(1126, 875).

**This contradicts the menu path**, where the resizable-window session measured exact re-centring
(`192,144,832,624` → `320,272,960,752`). **In-city, that reflow does not happen.** Two different
behaviours on the same resize, and only the menu one was ever verified.

### Cross-session corroboration

The symptom is stable and reproducible across sessions and cities: the resizable-window session's
earlier `resize_G_incity_FIXED_1280x1024.png` shows the same black viewport with working UI and
minimap on **Berlin**, and this run reproduces it on **Europolis**. (That file's `FIXED` refers to
defect G of their ladder, not to `U-068`.)

### Limits, stated

`[UNCERTAIN]` **The region is black, not garbage.** It is not established whether the iso render
target holds an image that fails to blit, or holds nothing at all — **those are different defects.**
Next instrument: a lock-and-dump of `iso+0x74`'s surface against `iso+0x4ec`, the blit destination.
A read, one run.

### The correction that should survive this section

The 2026-08-24 negative on the grid-B fix **stands** — but its original justification did not. It was
first adjudicated on `iso+0x524 == 0`, which §31.11 showed is a *drained* value; the pixels now reach
the same verdict by a sound route. **A right answer reached through a broken instrument is not
evidence, and it was worth three runs to learn that here rather than in something shipped.**

Images: `re/harness/u068_shots/` (gitignored — they are game screenshots and are **game content**,
never to be published).

## §31.13 — the surface dump CRASHED THE GAME. Black-vs-garbage is not settled. (2026-08-24)

**Verdict: row 1 of the pre-registered table — control dump unresolvable, ABORT, nothing
interpretable.** The control did not merely fail; it took the process with it.

The game **exited on its own at t+19.595 s with `0xC0000005`**. It was not killed (`-kill 50` never
fired). The last log lines are the control dump starting, pre-resize:

```
U068SURF> ===== SURFACE DUMP: A_pre_resize_CONTROL =====  iso=0x0EA8EA30
          render(+0x74)=0x1231BF60 dest(+0x4ec)=0x0058A470
U068SURF>   wrapper 0x1231BF60 raw: created(+0x08)=1 fmt(+0x0c)=7 bpp(+0x10)=16
            w(+0x24)=1024 h(+0x28)=768 sub(+0x44)=0x0F1117D0
```

The next statement — the first candidate probe — never logged. **No BMP written, no post-resize
dump. `[UNCERTAIN]` black vs garbage remains completely open.**

### The design error, named plainly

The instrument guarded a pointer with `IsBadReadPtr` and then **called vtable slot 22**.

> **`IsBadReadPtr` proves a pointer is READABLE. It does not prove the object is a COM interface.**
> Both guards passed and the call went through a dword that is not a `GetSurfaceDesc` pointer.

"Let `GetSurfaceDesc` adjudicate" is not adjudication — it is an **unguarded indirect call through
unknown data inside a live game**. This is the same family as the prologue-stealing hazard that
killed the load at 6.7 s (§31.10): **an instrument that can destroy the thing it measures.** The
notes describing it as "self-verifying" were wrong.

The underlying assumption was also wrong: **`iso+0x74` is not a DirectDraw wrapper.** SIMDIRT
rasterises into bits obtained from the object's **own** vtable (`vf1c` / `vf1a8` / `vf1ac` / `vf20`),
a path `rz_iso_resize` already uses. The `*(this+4)` convention belongs to the **blit destination**
(`FUN_10018c58`) and was over-generalised.

### What survived the run

1. **Pre-resize, `iso+0x74` = `0x1231BF60`: `w=1024 h=768 bpp=16 fmt(+0x0c)=7 created=1`.** One
   dimensions set of the four requested. Pitch and channel masks were to come from the surface
   descriptor and were never obtained. Note this is the **pre-resize control**, where 1024x768 is the
   expected value and therefore **not yet diagnostic** — the interesting number, the post-resize one,
   was not reached.
2. `iso+0x4ec` = `0x0058A470`, the blit destination.

> ⚠️ **Corroboration downgraded.** The run report called `0x0058A470` "exactly the `draw_obj` the
> U-034 line reports", framed as two unrelated routes agreeing. It is not: both readings come from
> **the probe's own instrumentation in the same process**, so it is within-process agreement.
> `UNCERTAINTIES.md`'s `U-034-RESOLVED` row records a different address entirely
> (`engine_dest = present_src = 0x009F4840`), from a different run. Heap addresses vary per process,
> so there is no contradiction — but there is no independent confirmation either.

### A lead, and the reason it is probably NOT the answer

`U-034-RESOLVED` found the black **windowed client** was caused by **100% of engine blits failing**
(`raster_blit_hw` 3935 / `rasthw_throw` 3935, `hr = 0x80004001` = `E_NOTIMPL`), and `U-035` asks why
fullscreen works anyway. A blit-failure family is the obvious neighbour of "black region below the
display list".

**But it probably does not fit this defect, and the reason is in the pixels:** in §31.12's shots the
**UI, status bar and minimap all draw correctly** and only the iso viewport is black. A global blit
failure would take the UI with it. So whatever is wrong is **specific to the iso path**, not the
device's blit capability. Recorded so the next person does not spend a lease re-testing `U-034`.

### Safe redesign, for whoever takes this next

**Never call an unknown vtable slot to identify an object.** Either:

- (a) verify the wrapper's vtable pointer equals a known `MODULE+RVA` **first** — the discipline the
  existing probe code already applies to `vt+0x0c` / `vt+0x14c` / `vt+0x158` — and only then call
  `vf1c` / `vf1a8` / `vf1ac` / `vf20`; or
- (b) use a surface the probe has already seen the engine use (`g_rasthw_dest`, captured from the
  dispatcher's own arguments).

Either way, wrap the first call per object in `__try/__except`. That was missing from everything
written for this instrument and is the cheap part.

### Safety state

`SC3PROBE_U068SURF` is **off by default and inert without it**, so the crashing path cannot fire in
another session's run. ⚠️ **It must not be enabled again as written.** Locks released, install
verified stock, nothing committed.

## §31.14 — ⭐⭐ THE INPUT-FREE CAMERA MOVER FOUND: a FOLLOW/TRACK re-centre (2026-08-25)

Two results landed together: a `cam` enumeration run that **falsified** the instrument hypothesis, and
a call-site hunt that **found the mechanism**. Both are below, and the second explains what four runs
of camera measurement had been chasing.

### 31.14.1 My instrument fix's premise was falsified — `N == 1`

`cam` was rebuilt to enumerate every object matching iso vtable `SIMSPR+0x6250c` rather than stopping
at the first, on the theory that the **minimap** is also a city view and would own a cell map, making
the measured object depend on allocation order.

**It does not. `N == 1` on all seven reads**, same address (`0x0EEBCD68`), same offset
(`cityViewIso+0x158`), and the `!! N objects` warning never fired. **The first-match theory is dead.**

The enumeration is kept anyway, for two reasons that are not rationalisation: it now *proves*
uniqueness per read instead of assuming it, and it caught the object's **creation** — the count goes
`0 → 1` between t+5.27 s and t+6.64 s. The old code would also have found nothing at t+5.27 s, but
nothing in the log would have said why.

### 31.14.2 `span` never varies — so this is a rigid translation, not corruption

`1024x768` on **14/14** rect prints here, and `rectB == rectA` on all 7 reads. With the earlier 30/30
that is **44 consecutive rect prints at exactly `1024x768`** across thousands of pixels of excursion.

That is the signature of `FUN_10006226` adding `param_1` to both lefts and rights and `param_2` to both
tops and bottoms `[CONFIRMED @ 0x10006226]`. **The origin is being translated by something, not
corrupted** — which redirects the question from *what is `cam` pointing at* to **who is calling the
translate with no input.**

### 31.14.3 There is no call site to instrument — there is one vtable dword

Scanned every byte of all five sections of the anchored `SIMSPR.DLL`, **verified independently**:

- **Zero `E8` calls and zero `E9` tail-jumps** target `FUN_10006226`.
- **Exactly one** dword in the module equals it: **`.rdata 0x10062538`**, which is iso vtable
  `0x1006250c` **+ 0x2c**.

So the function is reached **only by virtual dispatch**, a call-site counter is impossible — and the
converse is better than what was planned: **swapping that single dword catches 100% of calls with no
entry detour and no ambiguity.** Entry detours on per-tile functions are what killed a load at 6.7 s
(§31.10), so this is strictly the safer instrument as well.

### 31.14.4 The caller tree, and the one path with no input

```
FUN_10006226  (cell-map vt+0x2c, the translate)
├─ A  FUN_1001d503        cSC3CityViewIso::Translate   (isoVt 0x10063390 +0x78)
│     └─ FUN_1004327d       cityView vt 0x10067894 +0x34
│           └─ FUN_10043daf   arrow keys / edge scroll / right-drag
│                 └─ FUN_10042a95  window tick
└─ B  FUN_10006736        cell-map vt+0x30, ScrollTo(absolute)
      ├─ FUN_1001d039       CenterOn (isoVt +0x54) ← window message handler
      └─ FUN_1000ec0b       FOLLOW / TRACK re-centre        ◀── NO INPUT ON THIS PATH
            └─ FUN_1000dc17    cell-map vt+0x148, the flush/paint tick
```

**Branch A is already known to be silent when idle:** `FUN_10043daf` took **0 hits in 16 s of idle
city** (`verify/scroll_patch_test/RESULTS.md`, recorded at `sc3probe.c:1266`). So A cannot explain
input-free motion, and `FUN_1000ec0b` is the only remaining path that can.

### 31.14.5 ⚠️ The arming gate, CORRECTED

The hunt reported the follow as armed iff `+0x354 != 0 && +0x358 == 0`. **The second offset is wrong.**
Read from the decompilation `[CONFIRMED @ 0x1000ec0b]`:

```c
if ((param_1[0xd5] != 0) && (param_1[0x149] == 0)) {        /* 0xd5*4 = +0x354, 0x149*4 = +0x524 */
    ...
    if ((iVar5 != param_1[0x15]) || (iVar4 != param_1[0x16])) {   /* differs from origin +0x54/+0x58 */
        *(undefined1 *)(param_1 + 0xd6) = 1;                      /* 0xd6*4 = +0x358, guard ON */
        (**(code **)(*param_1 + 0x30))(iVar5, iVar4, 1);          /* vt+0x30 = ScrollTo */
        *(undefined1 *)(param_1 + 0xd6) = 0;                      /* guard OFF */
    }
}
```

So:

| field | role |
|---|---|
| `+0x354` | the **follow target** — non-zero arms the follow |
| **`+0x524`** | **the second gate: the follow runs only while this is ZERO** |
| `+0x358` | a **re-entrancy guard**, set around the call — *not* a gate |

`+0x358` is what the *cancel* side tests, and that is where the hunt's offset came from
`[CONFIRMED @ 0x10006226:58-59]`:

```c
if ((*(int *)((int)this + 0x354) != 0) && (*(char *)((int)this + 0x358) == '\0'))
    *(int *)((int)this + 0x354) = 0;
```

**A user-initiated scroll cancels the follow; the follow's own scroll does not cancel itself.** Elegant,
and it means the two mechanisms are designed to interact rather than merely coexisting.

> ### ⭐ `+0x524` is the `U-068` field
> The same `iso+0x524` that the entire resizable-window investigation turned on — the one §31.11 showed
> is a *drained* reading rather than a symptom. **It gates the camera follow.** So `U-068` and the
> camera thread touch the same field from opposite directions, and a reading of `+0x524 == 0` (which is
> what it reads most of the time) means **the follow is armed** whenever `+0x354` is set.

### 31.14.6 The test needs no counter and no patch

Read **`iso+0x354`** (follow target), **`iso+0x524`** (gate) and **`iso+0x358`** (guard) in `cam`.

- `+0x354 != 0` and `+0x524 == 0` on an idle city → **the follow is armed, and predicts drift.**
- `+0x354 == 0` → follow disarmed, predicts no drift.

That is a falsifiable prediction from a pure read, on a mechanism whose gate is known. It also explains
the shape of what was seen: deltas of `target − current` are **arbitrary, not step multiples** (matching
every non-32-multiple delta observed), the motion is a **rigid translation** (§31.14.2), and it would
**oscillate** if the tracked rect itself moves.

`[UNCERTAIN]` what writes `+0x354`. Not chased rather than guessed — and that is the next question, not
this one.

### 31.14.7 A yardstick correction that invalidates a comparison used all day

All 14 rect values lie inside **`0..6144` by `0..3072`**, where `6144 = 192 × 32 = N × tilepx` at
`zoom=2` — the iso diamond's extent at that zoom. **The `0..48896` this project has been testing camera
values against is SIMGEOM's `(N-1) × 0x100`** `[CONFIRMED @ 0x100023e8]`, **8× larger and
zoom-independent.**

`[UNCERTAIN]` which is the field's actual bound. It does **not** rescue the `-2396` reading (negative
under either), but **"far outside `0..48896`" is the wrong scale and must not be reused.**

### 31.14.8 What was NOT measured

- **The churn window was never entered.** Every stable read here is at **t < 13.5 s**; every churning
  read in the earlier series is at **t > 16.6 s**. This run ended at t+14.6 s. One run, spent on the
  enumeration question.
- The load origin `-160,1604` **reproduced byte-identically** from the earlier series' first read, so
  the "load-camera non-determinism" claim is **not supported by this run** — though it is not refuted
  either, since three different values were seen across earlier runs.
- `MAP dimensions UNAVAILABLE` on every read: N was **not** confirmed from memory. The fixture rests on
  329 filetrace lines opening `Farmsville.sc3` and the status bar in the frame.
- One jump did occur, at t+14.59 s: `dx=+1936, dy=-395`, neither a multiple of 32. `SHOT #1` completed
  at t+14.03 s, between the last stable read and the jumped one — **correlation only, no causal claim.**

### §31.14.9 — follow/track falsified, and the quantisation lead (second run, 2026-08-25)

**`FUN_1000ec0b` is not the mover.** `followTarget(+0x354)` read `0x00000000` on **all 16 reads**
(t+4.3 s to t+32.0 s) while the churn reproduced hard — 13 of 15 transitions moved, mean |dx| 1,317 px.
Its gate requires `+0x354 != 0` `[CONFIRMED @ 0x1000ec0b]`, so it cannot have moved this camera. The
tracked-rect check — the one called strongest going in — was **not evaluable**, because its print is
conditional on the field that stayed zero, and no proxy was substituted for it.

**The timing prediction that justified the run is also dead.** Churn onset was **t+8.0 s** (reads 2–3
byte-identical, read 4 moved), 6–9 s earlier than predicted and earlier than the previous run's
stability window, which held to t+13.5 s — same fixture, same switches, same probe path.
**So whatever selects between the frozen and churning regimes is not elapsed time.**

#### The lead nobody predicted: a fixed sub-tile phase lock

The mover becomes **exactly tile-quantised partway through and stays that way.**

| reads | x deltas that are multiples of 32 | x phase (mod 32) |
|---|---|---|
| 2–11 | **0 of 10** | varies: 0, 0, 0, 1, 11, 7, 26, 11, 21 |
| **11 onward** | — | **x = 9 on 6/6 reads** |
| **12 onward** | — | **y = 28 on 5/5 reads** |

**The two axes lock one read apart** — x at t+18.9 s, y at t+21.5 s. That detail was verified here from
the raw values; the run report had them as simultaneous. So the quantisation split first seen *across
two runs* also happens **twice inside one process with zero input**, and input cannot be what
distinguishes the two modes. `[UNCERTAIN]` what changes at t ~ 19–21 s; nothing else in the log
transitions there.

#### Two facts that got stronger

- **`span` = `1024x768` on 76/76 rect prints across three series, `rectB == rectA` throughout.**
  Rigid translation is now the most robust fact about this field.
- **The load origin is deterministic:** `-160,1604` reproduced a **third** time. The earlier
  "load-camera non-determinism" claim is **retracted** — those readings were samples taken inside the
  churning regime, not different load positions.

#### Method point, and it is the reason to stop guessing one gate at a time

**Five mechanisms have now been killed, each on its own gate:** off-map-kills-view, soft clamp /
pull-back, minimap cell map (first-match), repaint-driven tick count, and follow/track. Each cost a
run. Each was a plausible reading of real data.

The call-site hunt proved `FUN_10006226` has one vtable pointer and no direct call sites. **It did not
prove `FUN_10006226` is the only code that writes `iso+0x54..+0x70`.** A **write watchpoint on
`iso+0x54`** names the writer directly instead of eliminating candidates — and candidate elimination
has now lost five times in a row here.

### §31.14.10 — the watchpoint works, the phenomenon did not show up, and non-reproducibility is now the blocker (2026-08-25)

**No pre-registered row fired.** The watchpoint armed cleanly on the correct thread, survived 38 s and
reported **0 hits** — but the camera was **byte-identical on all 15 reads across 27.7 s**. With no
motion, zero hits is the trivially consistent case, not evidence about a cross-thread writer.
**Who writes `iso+0x54` is still unmeasured, because on this run nobody did.**

```
### CAMW: ARMED 4-byte WRITE watch on iso+0x54 = 0x0EEC597C, thread 29684 ...
### CAMW: 0 hit(s), 0 unique writer(s) of iso+0x54 (0x0EEC597C)
```

`tid 73f4` = 29684, so it armed exactly the thread `cam` runs on — verified, not assumed.

#### The null is load-bearing, because the game was demonstrably alive

`raster_blit_hw` climbed monotonically 3,063 → 13,395 at ~2,050 blits per interval, 7 heartbeats, no
exception, no dump, and the frame is a normal dense farmland view. **The engine drew 13,400 blits while
the camera sat still.** Also: where a frame exists the ticker reads paused, so sim-driven camera motion
is out on those runs.

#### Two things this run does establish

1. **Hardware-verified: zero writes to `iso+0x54` from the game thread across 27.7 s of a live,
   rendering, static-camera city.** No continuous same-value writer exists — which **closes off** "the
   field is constantly rewritten and `cam` catches it mid-write", one of the two survivors from the
   `U-082` null.
2. **The instrument is fit for use.** It arms, costs nothing observable, does not crash the process.
   It has simply never been pointed at a moving camera.

#### ⚠️ The blocker is now non-reproducibility, and it is not a small problem

Four runs. Same fixture, same switches, same probe path, zero input in all four:

| run | window | behaviour |
|---|---|---|
| A | t+16.6 → 32.4 s | churn throughout, mean \|dx\| 1,080 px |
| B (enumeration) | t+6.6 → 14.6 s | stable 6 reads, one jump at t+14.6 s |
| C (follow gate) | t+4.3 → 32.0 s | churn from t+8.0 s, 13/15 moved |
| **D (watchpoint)** | t+5.0 → 32.7 s | **frozen: 0 of 14 transitions moved** |

Onset has been **t+16.6 s, t+14.6 s, t+8.0 s, and never** — a **3-of-4 churn rate**. Not elapsed time
(killed in §31.14.9), not the fixture (all four Farmsville, and the two quiet windows are on the
fixture called unstable), not input, not the sim. **Nothing identified so far sorts these four runs.**
The load origin `-160,1604` is now reproduced a **fourth** time.

#### The confound on my own instrument, which the run agent raised rather than buried

**Run D is the only run with `SC3PROBE_CAMWATCH=1`, and run D is the only fully frozen run.** Against
it: the VEH recorded 0 hits so it never executed, and an armed-but-unhit debug register has no runtime
cost — there is no mechanism I can name. But "new instrument arrives, phenomenon vanishes" is not
something to leave unexamined off one run. `[UNCERTAIN]`.

**The test is the cheapest run on the list: identical to D with the env var unset.** If that churns,
the watchpoint is the suppressor and must be withdrawn. If it is also frozen, non-reproducibility is
real and D is the fourth sample of a coin flip.

#### Two method requirements for any future run in this thread

1. **A live churn-detection gate.** Only trust a writer census from a run where consecutive reads
   actually differ. Otherwise a null is indistinguishable from a real negative — exactly the trap this
   run fell into.
2. **A base rate, not another single run.** At a 3-of-4 churn rate, one run cannot distinguish "my
   change suppressed it" from "this one was quiet". That is a sample-size problem, and single runs
   against a scarce game lease are the wrong instrument for it. Several short runs, or an in-process
   detector that reports whether churn occurred, would settle more per lease than another full
   measurement.

### §31.14.11 — the watchpoint is exonerated, and the wall turns out to be surmountable (2026-08-25)

Three control launches in one lease, `SC3PROBE_CAMWATCH` **unset**, everything else identical.

**`E2` froze: 15 consecutive reads at `-160,1604` over 27.9 s with the variable unset.** That is the
single freeze the design was bought for. **The suppression hypothesis is dead, the watchpoint is
exonerated, and nothing built on run D needs withdrawing.**

#### The pre-registered criterion was defective, and the run agent fixed it in the open

The criterion — *"any consecutive pair differing ⇒ churn"* — fires on the **city-load transition**
(`zoom=0 tilepx=8` at `-508,-73` becoming `zoom=2 tilepx=32` at `-160,1604`). That is loading, not
churn, and it is **not comparable across runs**: whether a run's first read lands pre- or post-load is
timing jitter. D and E1 never sampled the pre-city state; E2 and E3 did. **Corrected criterion, applied
uniformly: count only from the first post-load `zoom=2` read.**

| run | deciding pair | verdict | onset bracket |
|---|---|---|---|
| E1 | read 2→3, `-160,1604` → `-362,1346` | **churn** | t+6.26 – 7.42 s |
| E2 | none | **FROZEN**, 15 reads / 27.9 s | never |
| E3 | read 9→10, `-160,1604` → `-465,861` | **churn** | t+13.51 – 16.15 s |

#### ⭐ Churn stops by itself — so every run-level verdict in this file is really about sampling

`E1` churned for 7 transitions and then **froze at `-1466,114` for reads 9–15, six consecutive zero
transitions over 15.8 s.** So **churning and frozen are properties of a WINDOW, not of a run.** A run
that started at t+18 s would have called E1 frozen.

That reframes the whole non-reproducibility problem, **including my own verdict on D**: those were
statements about *when each run sampled*, not about what the game was doing.

#### ⭐ The zoom also changes with no input

`E3` went `zoom=2 tilepx=32` → **`zoom=4 tilepx=128`** between t+24.03 s and t+26.65 s, **zero keys**.
`SetZoom` is a **different vtable slot** (`+0x38` → `0x10006752`) from the translate (`+0x2c` →
`0x10006226`), so whatever drives this reaches **more than one entry point.** A writer hunt aimed only
at the translate could therefore miss the cause even when it fires.

#### The out-of-bounds yardstick is zoom-dependent, and that settles the earlier flag

The bound is `N × tilepx` by `N × tilepx / 2`, which moves with zoom — verified: at N=192,
`zoom 2 → 6144 × 3072`, `zoom 4 → 24576 × 12288`. E3's read 14 has `y = 7426`, **outside** the zoom-2
bound and **inside** the zoom-4 one. **Every out-of-bounds claim in this thread must be re-checked
against the zoom on the same read.**

#### Tally across all seven runs, corrected criterion

| run | CAMWATCH | verdict | first motion |
|---|---|---|---|
| A | unset | churn | not bracketed |
| B | unset | churn | t+13.46 – 14.59 |
| C | unset | churn | t+6.80 – 8.00 |
| **D** | **SET** | frozen | never |
| E1 | unset | churn, **then froze from t+15.7 s** | t+6.26 – 7.42 |
| **E2** | **unset** | **FROZEN** | never |
| E3 | unset | churn | t+13.51 – 16.15 |

Without the watchpoint: **5 churn, 1 frozen of 6.** D is no longer exceptional. (Row AR, not a
base-rate argument — one freeze without the variable was the pre-registered killer, and E2 delivered
it.)

**Onset brackets, four:** 6.26–7.42, 6.80–8.00, 13.46–14.59, 13.51–16.15. **Two near t+7 s, two near
t+14 s, nothing between.** `[UNCERTAIN]` — n = 4, so an observation, not a distribution. If it survives
more samples, **bimodal onset would mean two triggers rather than one noisy one**, and counting costs
nothing.

#### Reconfirmed

`followTarget(+0x354) = 0` on all 47 control reads — **63 consecutive** with C and D. `N == 1` on 47/47.
`span = 1024x768` on 47/47 for both rects, **cumulative 170/170** across six series.

#### ⭐ The method fix that un-parks this thread

**The churn gate must be a WINDOW gate, not a run gate — E1 is the proof.** Have `cam` report the
watchpoint census **per interval**, alongside that interval's `dx, dy`. Then **each interval is its own
experiment**: the intervals that moved are the ones whose EIPs matter, and a run like E1 yields **both
a moving sample and a frozen control inside one launch.**

That removes the reason this was parked. The blocker was "we cannot reliably get a moving camera in a
run"; the answer is that we do not need to — we need to *label* the intervals we already get.

### §31.14.12 — ⭐⭐ THE WRITER IS NAMED, and the question moves one level up (2026-08-25)

**`SIMSPR + 0x62AF` = `FUN_10006226 + 0x89`** — 137 bytes into **the translate itself**
`[CONFIRMED @ 0x100062af]`. Verified independently: the function spans `0x10006226`–`0x10006735` (the
next export is `0x10006736`), and iso vt `+0x2c` → `0x10006226`. The reported EIP is the instruction
*after* the store, so the store to `iso+0x54` sits at or immediately before `+0x89`.

**And a second writer: `SIMSPR + 0x68C9` = `FUN_10006752 + 0x177`** `[CONFIRMED @ 0x100068c9]`, which
is **`SetZoom`, iso vt `+0x38`** — verified as a different slot. It fired **once**, at the city-load
transition where zoom went `0 → 2`. **That is the mechanism behind E3's unprompted zoom change**, and
it confirms that a translate-only hunt would have missed this entry point.

#### The separation is perfect

| | writes > 0 | writes = 0 |
|---|---:|---:|
| **MOVED** | **12** | **0** |
| **still** | **0** | **17** |

**29 of 29 intervals.** Stores to `iso+0x54` occur **if and only if** the origin moved. No still
interval had any writes, so there is no background set to subtract.

**Row AV did not fire, and that is a second answer: the writer is on the GAME THREAD.** Zero moving
intervals had zero writes, so **the cross-thread hypothesis is retired** and run D's null was
ambiguity alone, not a hidden thread.

#### The cleanest data point in the thread

**Interval 11: `writes=1, dx=0, dy=-32`.** One call, one tile. `dx = 0` *with a write recorded* proves
the counter registers a store **even when the stored value is unchanged** — so the 17 `still` intervals
at `writes=0` had **no store at all**, not merely no net displacement. **The separation is real, not a
differencing artefact.**

`[UNCERTAIN]` and explicitly not claimed: that one write equals one 32 px step. It holds for interval 11
and interval 12 (`dx = -672 = -21 × 32`, 21 writes) but **not** interval 4 (104 writes,
`dx = -1512`, not a multiple of 32).

#### The per-interval design did exactly what it was built for

**F2 contributed one moving interval and then 15 consecutive `still` intervals over 22.8 s.** Under
run-level scoring that launch was a wasted lease. Under interval scoring it supplied **the 15 controls
that make the 29/29 separation meaningful.** The experiment and its control came from the same session.

Also: **F1 churned with the watchpoint armed** — independent confirmation of E2 that the instrument
neither suppresses churn nor is required for it.

#### ⭐ The number that reframes the question

**66–150 stores per ~0.9 s interval — roughly 75–165 calls per second into the translate, with zero
input.** Net displacement is far smaller than path length, so it oscillates hard.

But `FUN_10006226` has **zero direct call sites** and **one vtable pointer**, and its only *known*
input-free dispatch path (`vt+0x148` → `FUN_1000ec0b` → `vt+0x30`) is **gated closed** — `+0x354 == 0`
on 63+ consecutive reads and throughout F1/F2.

> **So something is entering iso vt `+0x2c` a hundred-plus times a second through a path nobody has
> identified. The question is no longer what writes the field — it is WHO CALLS `vt+0x2c`.**

**The same technique answers it:** hook `FUN_10006226` at entry, record the **return address**, and
difference per interval exactly as the writer census did. That names the caller the way this run named
the writer.

#### Tally, nine runs

Six churn, three frozen. Onset brackets now five: 6.26–7.42, 6.80–8.00, **7.82–8.73**, 13.46–14.59,
13.51–16.15 — **three in a ~t+7–8.7 s cluster, two in a ~t+13.5–16.2 s cluster, still nothing between.**
n = 5, so worth counting, not yet a distribution.

`span = 1024x768` on 31/31 reads, **cumulative 232/232**. `N == 1` on 31/31.

### §31.14.13 — the caller census armed, the phenomenon did not show, and the null narrows the driver anyway (2026-08-25)

Two launches, `SC3PROBE_CAMWATCH=1` and `SC3PROBE_CAMCALLER=1`. **28 intervals, every one `still`,
`calls=0`, `writes=0`.** No MOVED interval, so **no return address was recorded and the caller is not
named.**

#### The one clean positive: expect-or-refuse PASSED at runtime

```
### CAMC: ARMED caller census - iso vt+0x2c at 0x034F2538 swapped 0x03496226 -> thunk ...
### CAMC: ARMED caller census - iso vt+0x2c at 0x034D2538 swapped 0x03476226 -> thunk ...
```

The slot held exactly `SIMSPR + 0x6226` in **two independent processes**. Until now *"iso vt `+0x2c`
holds `FUN_10006226`"* was a **static** claim from the `.rdata` scan. **It is now confirmed at runtime**,
by an instrument that would have refused and printed the contents had it been anything else. The
refuse-row not firing **is** the evidence.

#### ⭐ What the null establishes: the driver STARTS AND STOPS

**In a frozen window, `vt+0x2c` is called ZERO times** — not "called with a zero delta", not called at
all, across 28 intervals and 44 s of live city in two processes. Against F1, where every moving
interval carried **66–150 stores in ~0.9 s**:

> **The driver is not a continuously-running loop whose delta is sometimes zero. It starts and stops.**
> Something begins calling `vt+0x2c` at ~100 Hz and later ceases — which is exactly what E1 showed from
> the outside when it churned for 7 transitions and then froze for 6 in one launch.

So **frozen windows are the gate closed, not the driver idling.** Nothing about the method needs
changing; it will name the caller the moment a launch churns.

**The two-instrument self-check passed:** `calls=0`, `writes=0`, `dx=dy=0` agree on 28/28. They were run
together so that one could catch the other lying; in this regime they corroborate exactly.

#### Base rate revised, and the design consequence is sharp

**Eleven runs: 6 churn, 5 frozen.** Previously reported as 6-and-3 of 9. Verified arithmetic at
`P(frozen) = 5/11 = 0.4545`:

| | |
|---|---|
| two consecutive freezes | **0.207** — ordinary, not suspicious |
| at least one churn in 2 loads | 0.793 |
| at least one churn in 3 loads | 0.906 |
| **at least one churn in 4 loads** | **0.957** |

*(The run report quoted ~94% for four loads; the precise figure is 95.7%. Same conclusion.)*

**At ~45% frozen, a fixed two-launch design fails to observe the phenomenon about one time in five.**
That is exactly what happened here.

#### Two method points, both raised by the run agent against itself

1. **It did not pre-register a "no MOVED intervals" row — for the second time**, having previously
   written in this same file that one should have existed. Recorded rather than quietly scored against
   a row from a different pre-registration.
2. **It declined to run a third launch after seeing the result.** The pre-registration committed to
   two, and adding a third post hoc is precisely the undisclosed flexibility that made E2 worth
   something. **That is the right call**, and the fix belongs in the next design rather than in this
   one.

#### The adaptive stopping rule, to be declared BEFORE the next caller run

> **Launch until one launch yields at least one MOVED interval, maximum four launches; report every
> launch including frozen ones.**

Honest because it is declared in advance, ~96% likely to reach a churning launch inside four loads at
the measured base rate, and the frozen launches serve as `still` controls rather than waste. **It must
also pre-register the all-frozen row.**

#### Confound on `CAMCALLER`'s first outing, stated rather than dismissed

Both its launches froze. Against reading into it: the thunk **never executed** (`calls=0`), so it had no
runtime cost; `writes=0` as well, so this is not "the swap broke dispatch" — the watchpoint observes the
store independently of the vtable and was equally silent; and the game was alive
(`raster_blit_hw` 897 → 7,323 and 897 → 12,720, monotonic). `[UNCERTAIN]` on one pair. **The clean test
is a churning launch with `CAMCALLER` armed** — the same shape F1 used to exonerate `CAMWATCH`.

Reconfirmed: `+0x354 = 0` on 30/30 (closed on every read since run C), `N == 1` on 30/30,
`span = 1024x768` on 30/30, **cumulative 292/292**. The vtable swap is memory-only, so the on-disk
install stayed stock by hash throughout.

### §31.14.14 — a caller named, and a suppression signal that outranks it (2026-08-25)

Four launches, the pre-registered ceiling. **All four frozen post-load** (`p = 0.043` at the measured
base rate) — the all-frozen row, pre-registered this time after being omitted twice.

#### The load-time caller: `SIMSPR + 0x674F` = `FUN_10006736 + 0x19`

Identical in **three independent processes** (H2, H3, H4). `FUN_10006736` is **28 bytes**
(`0x10006736`–`0x10006751`, verified), so `+0x19` is the instruction after its single `call`. The whole
body is:

```c
(**(code **)(*param_1 + 0x2c))(param_2 - param_1[0x15], param_3 - param_1[0x16], param_4);
```

`param_1[0x15]` = `+0x54` and `param_1[0x16]` = `+0x58` — **exactly the origin fields the watchpoint
watches.** So it takes an **absolute** target, subtracts the current origin, and dispatches to
`vt+0x2c`: **`ScrollTo(absolute)` implemented on top of `Scroll(relative)`**
`[CONFIRMED @ 0x10006736]`.

> **The run report left the slot `[UNCERTAIN]`. It is resolved here from the anchored binary:
> iso vt `+0x30` → `0x10006736`.** ScrollTo *is* `vt+0x30`, so this is one of the two **mapped**
> dispatch sites — **not** the unmapped path the ~100 Hz rate implied, and not `FUN_1000ec0b`.

**Why that matters rather than merely tidying a footnote:** load-time motion runs through the *same
final dispatch the follow path uses* (`vt+0x30` → `vt+0x2c`), while `+0x354 == 0` on 63/63 rules
`FUN_1000ec0b` out. **So something other than the follow calls ScrollTo.** The next instrument is a
single expect-or-refuse swap on `.rdata SIMSPR+0x6253c` (= vt `+0x30`, verified), which names that
caller the same way this run named ScrollTo.

**Instruments corroborated at single-event resolution:** `calls=1` with exactly one store at `+0x62AF`,
plus one at `+0x68C9` (SetZoom, which does not route through `vt+0x2c`). One call in, one translate
store out — three times.

**The CHURN caller is still unnamed.** No post-load MOVED interval occurred in any launch.

#### ⚠️ The signal that outranks the caller

| | launches | churn | frozen |
|---|---:|---:|---:|
| before `CAMCALLER` existed | 11 | 6 | 5 |
| **with `CAMCALLER` armed** | **6** | **0** | **6** |

**Six consecutive frozen launches with the caller census armed: `p = 0.4545⁶ = 0.0088`** — verified.
The same concern was raised about `CAMWATCH` on *one* sample and dismissed; this is six, an order of
magnitude stronger.

**Against a mechanism:** the thunk is correct (`[esp+36]`, `pushad`/`popad` preserving `ecx` for
`__thiscall`, the `__cdecl` `add esp,4`, the `jmp` leaving the return address in place) and it
demonstrably *works* — it recorded the load call in three processes.

**But there is a competing explanation and it is not the instrument.** Load times drifted shorter as
the file cache warmed: **t+5.0–5.8 s** in the F/G launches, **t+3.79–4.27 s** in H2–H4. If the churn is
a load-related transient, faster loads leave less of it inside the observation window. **`CAMCALLER`
and the warm cache are confounded** — every `CAMCALLER` launch came later in the day than every
non-`CAMCALLER` launch.

#### The clean test is INTERLEAVED, not another batch

A batch of unset launches **repeats the confound with time.** The design that separates them is
**alternation within one session** — set / unset / set / unset — with the alternation and count
pre-registered, so instrument and session-time are **crossed rather than confounded**.

**That should run before any further caller work.** At `p = 0.0088` this is the largest uncontrolled
variable in the thread, and a churn caller named while it stands is a result nobody could trust.

#### The stopping rule was defective — a third instance of the same class

H2 tripped the rule on **interval 1, the city-load transition** (`zoom 0→2`), which the **corrected
churn criterion published in this file after the E runs** explicitly excludes. The rule was written in
terms of "MOVED interval" and never had that fix carried over.

Disclosed and corrected mid-run: the detector became *a MOVED interval whose preceding read was already
post-load (`zoom == 2`)*, and the run continued to the pre-registered ceiling. **The ceiling was not
raised, no row was changed, the fixture was untouched, and the criterion applied had been published
before the run began.** H3 and H4 ran under the corrected detector; both frozen.

The pattern worth naming: **three separate criteria in this thread have been written without carrying
over a fix already made elsewhere in the same document.** The churn criterion, the stopping rule, and
the all-frozen row. Each was caught by the person who wrote it, which is the good half.

Validity: 0 keys, 25 filetrace hits per launch, **0 exceptions in any launch**, 4/4 COMPLETE,
expect-or-refuse passed in all four — `SIMSPR + 0x6226` now runtime-confirmed in **six** processes.
`followTarget = 0` on 63/63. `N == 1` on 63/63. `span = 1024x768` **cumulative 418/418**.
