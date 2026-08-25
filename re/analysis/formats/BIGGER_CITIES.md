# Making SimCity 3000 build cities larger than 256 tiles — the working procedure

**Status: a 512-tile city runs, plays to a 177-window tree, and saves — measured game-side
2026-08-20, re-measured 2026-08-22.** The shipped maximum is 256. **Four bytes are the whole fix**
for the crash; a second, separate patch is what makes the size *offerable* in the first place.

⭐ **Updated 2026-08-25: the engine is now measured to read, render and re-serialise tiles at
coordinates up to 495, with no coordinate-dependent failure** — the far-corner block survived *better*
than the low-coordinate control. See the limits.

⚠️ **Read the limits section before shipping this to anyone.** What is still unmeasured is
**development** (the test city loaded paused, and bare zones have no road or power) and **authoring
in game** at 512. `U-081` is open: drag-scroll appeared dead on a 512 map. No bound above 512 has been
tried.

Tools: `re/tools/patch_citysize.py` and `re/tools/patch_dirtbuf.py`. Both are same-length,
`--check`-able and `--restore`-able. **Neither has a `--selftest`** — use `--check`.

## Why two patches, not one

They fix two unrelated things, and **both are required**. Patching only the first gives you a
512-tile option that crashes the renderer within seconds; patching only the second changes nothing
a player can reach.

| patch | module | what it does |
|---|---|---|
| `patch_citysize.py` | `Apps\SIMUI.DLL` | Retargets the New City dialog's **largest** size option from `0x100` (256) to N |
| `patch_dirtbuf.py` | `Apps\SIMDIRT.DLL` | Stops the terrain vertex buffer overrunning at N > 256 |

### The dialog site

`SIMUI FUN_1005eb40` maps the four size radio buttons to a tile count at `+0x174`, which is handed
to the terrain generator as a square `(N, N)`:

```
0x1005ecf8   mov [esi+0x174], 0x100     <- the "else" arm; ONLY this one is touched
0x1005ed04   mov [esi+0x174], 0xc0      (192)   control
0x1005ed10   mov [esi+0x174], 0x80      (128)   control
0x1005ed1c   mov [esi+0x174], 0x40      (64)    control
```

**The other three arms are deliberately left alone so they act as controls:** if a patched run breaks
in a way 64/128/192 also show, the cause is not N.

Downstream is size-agnostic, which is why this is the right site: the generator's `vt+0x0c`
(`SIMDIRT 0x1001742c`) stores `N+1` as the vertex count and heap-allocates four grids at
`(N+1)x(N+1)`; the city's dimensions land in `cSC3City +0x3c`/`+0x40` and every consumer reads them
through vtable slots `+0xcc`/`+0xd0`. No fixed-size buffer sits on that path.

### The defect that actually crashes

`SIMDIRT` keeps a lazily-created singleton (`DAT_10025bac`, built by `FUN_1001214d` →
`FUN_1001665c`) whose field `+0x2c` is a **ushort-per-vertex terrain buffer**. On an N-tile map the
vertex grid is `(N+1) x (N+1)`, so it needs `2*(N+1)^2` bytes with a row stride of `N+1`. **The
shipped binary hardcodes both for N=256** — so at N=512 it overruns by ~132 KB.

Three groups of sites, all length-preserving, all verified by disassembly:

| group | pattern | sites | what it is |
|---|---|---:|---|
| **SIZE** | `push 0x20402` (= 257·257·2 = 132,098) | **4** | the allocation (`0x100166e0`) plus three `memset`s (`0x100132c3`, `0x10014159`, `0x1001469f`) |
| STRIDE | `imul reg, reg, 0x101` (= 257) | 7 | the row stride; buffer is addressed `buf[(X*stride + Z)*2]` |
| CORNER | `mov word [edx+ecx*2+0x204], ax` | 1 | the `(X+1, Z+1)` corner displacement |

> ⭐ **The SIZE group alone is the entire fix, and that was measured rather than assumed.**
> Config C (SIZE only) survived **6/6**; the shipped binary survived **0/6**, dying at 4.5–6.8 s.
> Patching all 12 sites also survived 6/6, and the N=192 control survived 6/6.
>
> **The STRIDE hypothesis FAILED.** STRIDE and CORNER are correct by derivation and add nothing
> measurable — see the limits.

## The procedure

```powershell
# 0. see the shipped state first; both tools read the live install
py -3.12 re/tools/patch_citysize.py --check      # "largest option : 256 (0x100)" + 3 controls OK
py -3.12 re/tools/patch_dirtbuf.py  --check      # 12 sites at shipped values

# 1. patch both (each backs up first)
py -3.12 re/tools/patch_citysize.py --n 512
py -3.12 re/tools/patch_dirtbuf.py  --n 512

# 2. verify
py -3.12 re/tools/patch_citysize.py --check
py -3.12 re/tools/patch_dirtbuf.py  --check

# 3. undo, any time
py -3.12 re/tools/patch_citysize.py --restore
py -3.12 re/tools/patch_dirtbuf.py  --restore
```

`patch_dirtbuf.py --groups SIZE` applies only the group proven necessary. Groups not listed are left
at shipped values, which is what made the 6/6-vs-0/6 comparison possible.

Then start a **New City** and pick the largest size option.

## What was measured, and what was not

**Measured game-side** (24 runs, one lease, one probe):

| configuration | outcome at N=512 |
|---|---|
| shipped `SIMDIRT` | **0/6 survive**, deaths at 4.5–6.8 s |
| SIZE group only | **6/6 survive** |
| all 12 sites | 6/6 survive |
| N=192 control | 6/6 survive |

The saved city round-trips: a **920,753-byte `.sc3`** re-parses as a genuine 512×512 tile grid and
zone plane through `re/tools/city_parse.py`.

## The shipped cities are NOT all 256 — pick fixtures deliberately

Measured over the whole corpus 2026-08-25, because a test was run against "the 256 case" that was
actually a 192 map:

| N | cities |
|---:|---|
| 128 | Mount Herrang |
| **192** | **Farmsville** (the project's default fixture), Liverpool, Roadless Paradise, TUTORIAL |
| 256 | Berlin, Craterville, Europolis, Frankfurt, London, Madison, Madrid, Moscow, Sacramento, Seoul |

⚠️ **`Farmsville.sc3` is 192.** It is the fixture most of this project's runs reach for, and reading it
as the 256 case is wrong by 64 tiles. The recorded `-6848` camera baseline is **Berlin/256**.

**Every path-loaded city loads PAUSED** (`Simulación en pausa`) — measured on both a 192 and a 512
fixture. There is **no unpause command** among the 90 shipped menu commands. Any test whose observable
depends on the simulation advancing has to solve that first.

Also confirmed at two independent N: the camera's world extent is **`(N-1) x 0x100`** — `48896` at 192,
`130816` at 512.

## ⚠️ Limits — read these before calling it shippable

- ⭐ **The engine handles high coordinates end to end — measured 2026-08-25.** Four 32x32 zone blocks
  were planted offline at `(16,16)`, `(464,16)`, `(16,464)`, `(464,464)` and the game **read them,
  rendered them (main view and minimap) and re-serialised them on save**. The saved file re-parses at
  `N = 512` and `city_roundtrip.py` passes L0–L4. Coordinate extremes of every change:
  **x 16..495, y 16..495**, with **216 of 308 changes above 256** and **zero changes outside the four
  blocks**.

  **Crucially there is no coordinate threshold in the data.** Per-block survival was
  `(16,16)` 932/1024, `(464,16)` 957/1024, `(16,464)` 893/1024, **`(464,464)` 1006/1024** — the
  **far corner survived best and the low-coordinate control lost more than it did.** A lingering
  256-assumption would have damaged the high blocks preferentially; it did the opposite. The 308
  losses are **unattributed** — not terrain (flat 7.3% against grid value 0 over 3,991 tiles) and not
  coordinates; the candidate that cannot be excluded is uncontrolled human input during the run.

- **Development at 512 is still unmeasured, and for reasons unrelated to N.** `Pob: 0`, nothing grew
  anywhere **including the low-coordinate control**. Three causes, all independent of map size: the
  city loaded **paused**, no unpause command exists among the 90 shipped menu commands, and bare zones
  have neither road nor power. **This is inconclusive about 512, not evidence against it.**
- **Authoring at 512 has never been attempted.** Placing a zone or road *in game* on a 512 map
  (`fire:<toolcmd>` + `drag:`/`at:` with a funds oracle) is established at 256 and untried at 512.
- ⚠️ **`U-081`: right-click drag-scroll appeared DEAD on a 512 map**, observed live by the owner, and
  **unmeasured** — the run ended before the `cam` witness could be taken, and `cam` then declined to
  read. If you ship this, expect a camera-clamp question at 512. Arrow keys versus drag would localise
  it in one run.
- **No bound above 512 has been tried.** 512 is where the evidence stops, not where the format does.
- **The STRIDE (7) and CORNER (1) sites are correct by derivation and unvalidated by measurement.**
  They add nothing observable at 512. They are patched by default because the arithmetic says they
  should be; if you are debugging, `--groups SIZE` is the configuration with evidence behind it.
- **8-bit packing is unwitnessed** and there is a **cosmetic stride/corner defect** whose measurement
  is deferred (~8 runs, judged not worth the lease).
- `Apps\` is **game content.** Both tools back up before writing and both have `--restore`, but
  verify with `--check` rather than trusting that it worked.
- The N=512 city save is **game-derived data and must never be committed** to the public repo.
