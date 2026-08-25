# Making SimCity 3000 build cities larger than 256 tiles — the working procedure

**Status: a 512-tile city runs, plays to a 177-window tree, and saves — measured game-side
2026-08-20, re-measured 2026-08-22.** The shipped maximum is 256. **Four bytes are the whole fix**
for the crash; a second, separate patch is what makes the size *offerable* in the first place.

⚠️ **Read the limits section before shipping this to anyone.** Nobody has driven real gameplay
(zoning, building) in a 512 city, and no bound above 512 has been tried.

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

## ⚠️ Limits — read these before calling it shippable

- **Playability at 512 was never driven.** The city runs, renders, plays to a 177-window tree and
  saves. **Nobody has zoned, built, or run a full economy in one.** That is the single largest
  untested claim here.
- **No bound above 512 has been tried.** 512 is where the evidence stops, not where the format does.
- **The STRIDE (7) and CORNER (1) sites are correct by derivation and unvalidated by measurement.**
  They add nothing observable at 512. They are patched by default because the arithmetic says they
  should be; if you are debugging, `--groups SIZE` is the configuration with evidence behind it.
- **8-bit packing is unwitnessed** and there is a **cosmetic stride/corner defect** whose measurement
  is deferred (~8 runs, judged not worth the lease).
- `Apps\` is **game content.** Both tools back up before writing and both have `--restore`, but
  verify with `--check` rather than trusting that it worked.
- The N=512 city save is **game-derived data and must never be committed** to the public repo.
