# RESULTS — zoom-after-resize crash LOCALIZED by the VEH logger, 2026-08-30

The VEH crash logger worked. Reproduced: resize once (city rendered, all 11 steps), then zoom in ->
crash. Captured:

```
*** VEH FAULT *** code=0xC0000005 at GZGraphicD.dll+0x253E (base 0x026A0000)  (resize step at fault=11)
VEH access=WRITE addr=0x10DE9014
VEH regs eax=0FD4F9EA ecx=0FD4F9E0 edx=10DE8014 ebx=000041E7 esi=41E741E7 edi=00001000 ebp=001AFAF0 esp=001AFAB4
VEH [esp]=0x0F04B8D0 -> (heap, no module)
```
("resize step at fault=11" is just the leftover breadcrumb from the last resize; the fault is on the
game's zoom path, not in our routine. A first, separate `0xC0000096` privileged-instruction fault at
startup (`SC3U.exe+0x84122`, t=3ms) is a benign game probe it handles itself - the game ran 21 s after.)

## Where and what

- **`GZGraphicD.dll+0x253E`** is inside **`FUN_1000239d`** (`0x1000239d`, 982 bytes) - a **zoom-scaled
  16bpp sprite blitter**. It has an explicit **2x branch** (`dest_w == src_w*2`) and **4x branch**
  (`dest_w == src_w*4`), writing `CONCAT22(px,px)` (a 16-bit pixel doubled into a dword). No in-module
  caller -> a drawable vtable draw method, dispatched per tile.
- It gets the **destination pitch** from `param_1` vtable **`+0x1ac`** (`local_8 = ret >> 1`, pixels)
  and the **dest base** from vtable **`+0x1a8`**, then walks rows advancing `puVar11` by the stride.
- The fault is a **WRITE 0x1000 bytes past the destination buffer** (`edx=0x10DE8014` -> write
  `0x10DE9014`, `edi=0x1000`), fill value `0x41E7` (a 5-6-5 colour, doubled in `esi=0x41E741E7`). So the
  scaled-up output ran off the end of the dest surface by ~one row/page.

## Diagnosis

A **destination surface size/pitch mismatch** on the zoom path after a resize. When zoomed in, this
blitter scales each source tile up 2x/4x into the dest; if the dest surface's height/stride (from vtable
`+0x1a8`/`+0x1ac`) is inconsistent with what the scaled write needs at the resized window, it overruns.
This is **NOT** the §4 grid-B OOB class (that was SIMSPR bucket indices); it is a GZGraphicD raster-target
sizing problem, plausibly tied to the resize surface recreation (`FUN_10009efb` sets `iso+0x74` w/h at
`+0x24/+0x28`) and/or the `FIX16` 16bpp path - the pitch the blit reads may not match the recreated
buffer at the new zoom.

`[UNCERTAIN]` — the exact field that is stale (the dest surface object, its allocated size vs its
reported pitch `+0x1ac`) is not yet identified. Next: read `FUN_1000239d` + its dest-surface object
(what provides `+0x1a8`/`+0x1ac`, how its buffer is allocated and its pitch set, and whether the resize
recreates THAT surface or only `iso+0x74`/`iso+0x4ec`). The fix is likely to also recreate/resize the
zoom blit's destination surface, or to correct its reported pitch, on resize.

## Status

- `D-004` CONFIRMED; **render after resize FIXED** (step 11) - the milestones hold.
- Zoom-after-resize crash **localized** to `GZGraphicD FUN_1000239d+0x1a1` (RVA 0x253E), a zoom-scaled
  16bpp blit overrunning its dest surface. Fresh sub-investigation; not yet fixed.
- The VEH logger is a keeper - it captures faults the game swallows.
