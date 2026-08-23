# The Preferences window, its widget vocabulary, and a new control added to it

Status: the **Camera Scroll Speed slider works in-game** (`-pref`, 2026-08-20). Evidence below.

This started as "can a camera sensitivity option be added to the settings menu". Answering it
required decoding enough of the UI layer to *create* a widget, which is new ground for this
project: everything modded before this was a data file or a constant.

## 1. The window

| fact | value |
|---|---|
| window id | `0x02F95AD5` |
| class vtable | `SIMUI.DLL+0xA4D64` |
| rect (local) | `272,148,752,620` = **480 x 472** |
| builder | `FUN_100564d9` @ `SIMUI+0x564d9`, 8,049 bytes |
| opened by | MenuItem command `0x10009001` "Prefs" -> GZCOM guid `0xc3001401` |
| child id block | `0x02F95AD6 .. 0x02F95B11` (contiguous) |

480 x 472 matches the builder's closing `(**(*param_1+0xc0))(0x1e0,0x1d8)`, which is how the
window was identified rather than assumed.

> **Tracker correction.** `re/analysis/SIMUI.md:87` describes `FUN_100564d9` as
> "game setup — 3 radio groups, option-service driven". It is the **Preferences dialog**: it opens
> with `FUN_1008ebbd(&local_78, 0x14e, 0x29541f4)`, and instance `0x14e` of group `0x029541f4` is
> the string `Preferences`. The three radio groups are real but they are only part of it.

**The layout is CODE, not data.** Every control is placed with immediate operands
(`0x17a,0x43,0x56` …). There is no dialog/layout record type in IXF — over the 149k rows of
`re/data/ixf_text.csv` the types are `0x2026960b` (strings, 56,038), `0xc25c74f2` (6,356),
`0x625c6226` (6,034) and a sprite tail. So `ixf_parse.py` / `syspak_mod.py` **cannot** add a
control; only text and bitmaps are data-driven.

## 2. Widget class vocabulary — observed, not inferred

Recovered by firing `0x10009001` in a loaded city and dumping the window tree (214 windows).
This resolves the "which class is the slider" question that a static sweep could not:

| class vtable | what it is | witnesses |
|---|---|---|
| **`GZWIND.DLL+0x2AEB4`** | **slider / trackbar** | `0x02F95AFE/AFF/B00` (music, ambient, sfx) |
| `GZWIND.DLL+0x2A5EC` | option (radio) group container | `0x02F95AEB`, `AF0`, `AF4` |
| `GZWIND.DLL+0x2B190` | label / checkbox / button | `0x02F95AF1..AF8`, `AD8` (OK), `B10`, `B11` |
| `GZWIND.DLL+0x2AC1C` | list scrollbar | `0x02F95B0F` |
| `GZWIND.DLL+0x2B4AC` | group panel / frame | `0x02F95ADC` (the audio box, `372,46,468,156`) |
| `GZWIND.DLL+0x2D310` | (undecoded) | `0x02F95AFD` (`386,50,454,60`) |

**The sliders already in the dialog:** ids `0x02F95AFE / AFF / B00`, rects
`378,67,464,87` / `378,91,464,111` / `378,115,464,135` — width `0x56`, 24 px pitch. Exactly the
`(x=0x17a, y=0x43/0x5b/0x73, w=0x56)` immediates at `FUN_100564d9:627-629`. Range `0..0x400`.

Measured at runtime: all three read **1024** (max volume) on this install.

## 3. The API, read out of the game's own code and then exercised

Creation — `FUN_10058e75` @ `SIMUI+0x58e75` (159 bytes), verbatim:

```
factory = FUN_10085065()                               // SIMUI+0x85065, no args, cached service
slider  = factory->vt[0x50](id, 1, min, max, value)    // CreateSlider
w = slider->vt[0x0c]()                                 // the cIGZWin view of the widget
      w->vt[0x10c](captionStr)                         // caption   (SKIPPED - see below)
      w->vt[0x0b8](width)
      w->vt[0x0cc](x, y)
ok = parent->vt[0x34](w)                               // AddChild
if (!ok) w->vt[0x28]()                                 // destroy
slider->vt[0x08]()                                     // release our reference
```

The factory service is `GetService(CLSID 0xc2c2eb0f, IID 0x22c2eb1f)` via `FUN_10013880`.
Other factory slots seen in the builder: `+0x3c` CreateCheckBox, `+0x44` CreateLabel,
`+0x48` CreateOptionGroup, `+0x4c` CreateFromResource, **`+0x50` CreateSlider**, `+0x80` GetImage.

Reading a value — `FUN_100593ac` (the OK handler), verbatim:

```
parent->vt[0x80](id, 0x21325207, &out)   // GetChildAs, returns bool
value = out->vt[0x10]()                  // get value
out->vt[0x08]()                           // release
```

Sibling IIDs in the same dialog: `0x8810` checkbox (`+0x38` get state), `0xa1336cc0` option group
(`+0x30` get selected child id), `0x61325a2d` list, `0x212cdc1f` label (`+0x10` setText).

**Why the caption is skipped.** `FUN_100564d9:627-629` passes the *same* scratch string
`local_ac` to all three sliders (constructed at `:86` by `FUN_10005eb6`, destroyed at `:1055`),
so the shipped sliders' captions are leftover text. What labels a slider in this dialog is a
separate widget. Skipping `vt+0x10c` therefore loses nothing and avoids constructing a GZ string.

## 4. The feature: `-pref`

`re/harness/src/sc3probe.c`, gated on `SC3PROBE_PREF` (launcher flag `-pref`).

**It patches no code.** No detour, no `.text` edit. The obvious approach — detouring
`FUN_100564d9` to add a widget during construction — was rejected: it is 8,049 bytes with an EH
prologue and a per-object unwind counter. Instead the probe waits for the dialog to appear in the
window tree and calls the same factory the game calls. Every operation above is an ordinary
vtable call.

- **Where:** id `0x02F95B12`, at local `(18, 404)`, width 86, range `0..1024`.
  - `0x02F95B12` is free — the block ends at `0x02F95B11` and a grep for `0x2f95b12` across every
    module's decomp export returns zero hits.
  - `y=404..424` is free — the last checkbox ends at `y=398`, the OK button starts at `y=434`.
- **Mapping:** `speed = value / 8.0`, so the shipped `32.0f` is slider **256** and the range is
  `0..128`. Chosen so the default lands on a round position and `0` is reachable, `0` being the
  S1 rung's "arrow keys do nothing", which makes the control self-evidently live.
- **Applied to both:** the live view's `+0x1c8` (active) and `+0x1cc..+0x1dc` (per-zoom bank) for
  immediate effect, and SIMSPR's `.rdata` `+0x67690..+0x676a0` under `VirtualProtect` so any view
  built later inherits it (`FUN_100440b1` copies `.rdata` into the object at construction).
- **Lifecycle:** polled at 10 Hz. The slider is a child, so it dies with the dialog; the poll
  notices the window is gone and re-adds on reopen.

### Evidence it works

```
### PREF: Preferences window found; shipped sliders music=1024(1) ambient=1024(1) sfx=1024(1)
### PREF: slider id=0x02F95B12 at (18,404) w=86 range 0..1024 -> add OK
### PREF: label  id=0x02F95B13 "Camera Scroll Speed" at (110,406) w=180 -> add OK
### GZWIN  id=0x02F95B12 vt=GZWIND.DLL+0x2AEB4 local=18,404,104,424 abs_centre=333,562
### PREF: scroll speed <- 32.000 (slider 256)  rdata=ok live=ok
```

The read path was validated on the three widgets we did **not** create before being trusted on
one we did — all three returned success. The tree dump then shows our slider carrying the *same
class vtable as the shipped sliders* at exactly the requested geometry.

Dragging it (`drag:311,562,372,562`) tracked continuously and monotonically:

```
21.250 (170) -> 40.625 (325) -> 60.000 (480) -> 79.500 (636)
             -> 98.875 (791) -> 118.250 (946) -> 128.000 (1024)
```

Rendering confirmed visually in `pref1_202726.png`: the slider is drawn under
"Opciones generales:" in the same style as the audio sliders, thumb at ~25% for value 256.

### Reproduce

```powershell
$sw = '-nocom -windowed -origin -fix16 -fitclient -nointro -quiet -pref'
& re/harness/capture.ps1 -Name pref -Switches $sw `
    -GzSeq '0x712BF5BF;0x02DFDD6A;0xE2FA5BC2;fire:0x10009001;wait:1500;drag:311,562,372,562;wait:1500'
```

## 5. The label — "Camera Scroll Speed"

Added and **rendering in-game** (`pref3_005306.png`: the text sits beside the slider in the same
grey-blue as the dialog's other section labels). Id `0x02F95B13`, at local `(110, 406)`, width 180.
`0x02F95B12` and `0x02F95B13` are both confirmed unused — zero referencing files across SIMUI,
GZWIND and SC3U.

**No game file was modified to get text on screen**, which was the open question. Two things made
that possible.

### The string class

Widgets take a GZ string object, not a `char *`. The class is the one behind `PTR_FUN_100a2410`
(SIMUI `.rdata` `0x100a2410`): 5 dwords, vtable at `+0`, constructed by `FUN_10005eb6` @
`SIMUI+0x5eb6`, destroyed by `FUN_10006057` @ `SIMUI+0x6057`. Its vtable ends at `+0x30` (slot
`+0x34` reads `0xffffffff`). The slot that matters:

| slot | function | what it is |
|---|---|---|
| **`+0x10`** | `FUN_10006182` | **`operator=(const char *)`** — builds a temp via `FUN_10005f5e`, assigns |
| `+0x28` | `FUN_100844ce` | plainer `strlen` + assign-range; would also work |
| `+0x0c` | `FUN_100061d7` | assign from (ptr, length) |

`+0x10` was chosen because it is the one the game itself uses for `char *` assignment. So arbitrary
runtime text needs no string resource at all.

### The label recipe, and the one call that must be skipped

Mirrored from `FUN_1005844a` @ `SIMUI+0x5844a`, which builds every static label in this dialog:

```
label = factory->vt[0x44](id, strObj)                      // CreateLabel
label->vt[0x0c]()->vt[0xec](id)                            // <-- DELIBERATELY SKIPPED
label->vt[0x40]( factory->vt[0x14](0xf) )                  // font 0xf
label->vt[0x24]( FUN_10085039()->vt[0x84](0x79,0x7d,0xb5) )// the section-label grey-blue
label->vt[0x0c]()->vt[0x10c](strObj)                       // caption = our text
label->vt[0x0c]()->vt[0x0b8](width)
label->vt[0x44](1)
label->vt[0x0c]()->vt[0x0cc](x, y)
parent->vt[0x34]( label->vt[0x0c]() )
label->vt[0x08]()
```

**`vt[0xec](id)` is the trap.** In `FUN_1005844a` the string passed in is `local_ac`, which
`FUN_100564d9` constructs at `:86` and **never fills** — so the shipped labels' text does *not*
come from that string, it comes from this id-keyed resource lookup. Calling it with a new id would
look up a resource that does not exist and blank the caption. Skipping it and setting the caption
explicitly via `+0x10c` (the same slot `FUN_10058e75` uses for slider captions) is what lets a
custom label carry custom text with no IXF edit.

## 6. Known gaps
- **Not persisted by the dialog.** The slider's value is applied live but the OK button does not
  save it. The dialog's own settings land in a struct behind `FUN_1008e77f()->vt+0x60`; the
  serializer was not found, and `SC3U.ini` is write-only (proved in
  `verify/scroll_patch_test/RESULTS.md`). **A config-file store now exists instead** — see below.

### Persistence and standalone delivery — plumbing done, vehicle broken

`proxy_version.c` now reads a `[Camera]` section from `<gamedir>\SC3Portable.ini`:

```ini
[Camera]
ScrollSpeed = 96     ; 0..128, shipped value is 32. Applied to SIMSPR at load.
Slider      = 1      ; add the Camera Scroll Speed slider to Preferences
```

`ScrollSpeed` is published as `SC3PROBE_SCROLLSPEED`; the probe applies it to SIMSPR's `.rdata`
bank the moment SIMSPR loads, and the slider's thumb starts at that value so the file and the
control agree. **Verified working through the launcher** (`SC3PROBE_SCROLLSPEED=96`):

```
### PREF: armed - scroll speed 96.000, slider id 0x02F95B12 ...
### PREF: applying configured scroll speed 96.000 to SIMSPR .rdata: ok     <- t+105 ms, no dialog
### PREF: slider id=0x02F95B12 ... -> add OK
### PREF: scroll speed <- 96.000 (slider 768)  rdata=ok live=ok            <- 768 = 96 x 8
```

Note the `.rdata` apply lands at t+105 ms, before any dialog is opened, so the INI alone is a
complete setting — the slider is optional live tuning on top.

**But the standalone vehicle does not work, measured 2026-08-21.** With `version.dll`,
`sc3probe.dll` and `SC3Portable.ini` beside `SC3U.exe` and the game started directly:

- `SC3U.exe` **does** import `VERSION.dll` (verified in its import table — 13 DLLs) and
  `VERSION.dll` is **not** a KnownDLL (38 entries, none matching), so the folder copy should win.
- The folder copy **is** mapped: the module list shows `VERSION.dll <- <gamedir>\VERSION.dll`, and
  the on-disk file is byte-identical to the build (sha `ced64dc8…`).
- **`DllMain` is never invoked and the exported wrappers are never called.** Proved with two
  independent beacons writing to fixed writable paths — one at the top of `DLL_PROCESS_ATTACH`,
  one in the export path. Neither file was ever created, across repeated runs. The PE has a valid
  `AddressOfEntryPoint` (`0x186e`) and `IMAGE_FILE_DLL` set, and both beacons' code is present in
  the binary.

So the module is mapped but inert. This is **not** the loader-lock `LoadLibrary` problem: that was
also real and is now fixed (the load is deferred to a thread created in `DllMain`, with the first
forwarded export call as a fallback), but it sits downstream of something that fails earlier. This
sharpens the standing "version.dll standalone loader flaky" item — on this install it does not run
at all.

Not ruled out: mapped as a data file / image-resource rather than an executable image; import
binding resolving to the system copy while this copy is mapped for another reason; or a loader
policy on this machine. Diagnosing it needs a loader trace (ProcMon, or `gflags` loader snaps),
which was not run. **Working delivery meanwhile: `sc3launch.exe -pref`.**

#### Second attempt: a `winmm.dll` proxy — same result

`winmm.dll` looked strictly better than `version.dll` and the reasoning still holds:

- SC3U.exe imports **exactly one** function from it, `timeGetTime` (per-DLL import counts:
  UV.dll 7, WINMM.dll 1, VERSION.dll 3, IMM32.dll 5) — one forward, no guesswork.
- `timeGetTime` is a frame-timing call, so it is invoked constantly and early. That makes the
  "bring the probe up from an exported function" fallback a certainty rather than a hope, and it
  does not depend on `DllMain` at all — which is precisely what failed for `version.dll`.
- `winmm.dll` is **not** a KnownDLL (38 entries; `IMM32.dll` *is*, so an IMM32 proxy could never
  have worked).

Built as `re/harness/src/proxy_winmm.c` + `winmm.def`, with every piece of setup in an idempotent
`bootstrap()` called from both `DllMain` and the first `timeGetTime`. Verified structurally sound:
it exports `timeGetTime` (1 function, 1 name) and imports only KERNEL32 — **no self-import**, so
the C4273 "inconsistent DLL linkage" warning (`windows.h` declares `timeGetTime` as `dllimport`)
is cosmetic and there is no recursion.

**Result: identical failure.** `Apps\WINMM.dll` is mapped into the live process (module list
confirms our path) and the game runs normally, but no boot log is ever written — so neither
`DllMain` nor `timeGetTime` reaches our code. Two independent proxy DLLs, two different export
surfaces, same inert outcome. This is therefore a property of the install/loader, not of
`proxy_version.c`.

#### A genuinely useful discovery along the way

**The real game executable is `Apps\SC3U.exe`, not the install-root `SC3U.exe`.** Both are
1,155,072 bytes and both hash to the anchor `49dd55e1…` — they are the same binary — but
`sc3launch.exe` runs the `Apps\` copy, and `Apps\` is where every game DLL lives, so `Apps\` is
the directory the loader searches for an import. Any future proxy-DLL experiment must stage there,
and must be launched with the **install root as the working directory** (launching with `Apps\` as
CWD makes the game exit immediately — its `Cities\`, `Buildings\` data paths are root-relative).

#### Loader trace — what it settled, and what it did not

Run on an **isolated copy** of `Apps\` in the scratchpad (552 MB, deleted afterwards), never on the
live install. DLL init happens before the entry point, so no game data was needed.
`cdb.exe`/`gflags.exe` (32-bit, matching the game) are present under
`C:\Program Files (x86)\Windows Kits\10\Debuggers\x86`.

**Settled — and it overturns the "mapped but inert" framing above:**

| finding | evidence |
|---|---|
| The import **is** bound to our proxy | `x WINMM*!timeGetTime` -> `73d814a0`, inside our module |
| Ours is the **only** winmm loaded | `lm f m WINMM*` lists only `<scratch>\WINMM.dll`; `SysWOW64\winmm.dll` is **not loaded at all** (only `winmmbase.dll`, pulled in by DSOUND) |
| **AppCompat shims are active** on this exe | `apphelp.dll` is in the module list |
| Our proxy was mapped **twice** in one non-debugger run | two `ModLoad` lines for the same path at `629e0000` and `00750000` — consistent with an extra datafile/resource mapping alongside the image load |

So the earlier conclusion that the loader binds to the system copy is **wrong**: binding and module
identity are both correct. The open question is narrower than it looked — whether our code is
*entered*.

**Not settled.** No boot log is produced even in the clean copy, and a `bp WINMM!timeGetTime`
breakpoint did not visibly hit in a 30 s debugger window. True loader snaps were **not** obtained:
`gflags /i SC3U.exe +sls` requires elevation, which was not available non-interactively (both the
enable and disable calls failed, so nothing was left set). Empty `Image File Execution Options`
keys for `SC3U.exe` exist under both the native and WOW6432Node hives — **no values**, so they do
not affect the loader; they were not created by this session's failed `gflags` calls.

**Next step if resumed:** an elevated `gflags /i SC3U.exe +sls` run under `cdb` for real loader
snaps, or a patient interactive breakpoint session on the proxy's entry point. One more thing
worth checking cheaply first: whether `bootstrap()` is in fact running and only its `CreateFileA`
is failing — the current diagnostic cannot distinguish "never entered" from "entered, could not
write", because the log path is itself derived inside `bootstrap()`.

> **Process note / self-correction.** Earlier attempts placed `winmm.dll`,
> `sc3probe.dll` and `SC3Portable.ini` into `Apps\`, which `CLAUDE.md` explicitly forbids —
> `Apps\` is game content and must not hold RE artifacts. All five files were removed afterwards
> and the install re-verified (`Apps\` clean, `SIMSPR.DLL` at `eec71500…`). A proper standalone
> test needs a **copy** of the install, not the live one.

### Other gaps
- **OK/Cancel is not honoured.** The value applies on drag and is never reverted, so the OK button
  has no relationship to it.
- `GZWIND.DLL+0x2D310` (`0x02F95AFD`) is undecoded.
- Whether the slider interface has a **set**-value method is still unknown; only `+0x10` (get),
  `+0x08` (release) and `+0x0c` (get window) are witnessed. The initial value is passed to the
  factory instead, which is why this was never needed.
