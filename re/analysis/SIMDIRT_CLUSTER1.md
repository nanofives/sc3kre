## Module verdict

SIMDIRT.DLL is the **relief / terrain-shading overlay renderer** internally named **"DirtBag"** (confirmed by the save-chunk strings `s_DirtBag_Start` / `s_DirtBag_End` at `0x100240f4` / `0x10024104` [CONFIRMED @ 0x10004d90]). It maintains a height grid + a hill-shade grid + several bit-plane layers, renders them as isometric diamond tiles into the world, produces a downscaled thumbnail, and serialises its state. It is not the gameplay terraform engine's data owner — it consumes a city/tile source and produces raster/shade output.

The whole slice classifies. Below, then the CSV, notable finds, and the honest uncertainties.

---

## 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x10004d90,dirt-serialize,C2,sc3_dirt_save_state,"SAVE side. FUN_1001d397 opens writer; writes marker strings s_DirtBag_Start(0x100240f4)/s_DirtBag_End(0x10024104) + tag words 0x206c6e7c/0x21737de5 via vt+0xa4(write-str); iterates *(this+0x30)[+4] rows writing via vt+0x64, then this+0x38; vt+0x88 finalize [CONFIRMED @ 0x10004d90]"
0x10004a00,dirt-serialize,C2,sc3_dirt_load_state,"LOAD counterpart. FUN_1001d17b opens reader; vt+0x40 begin; iterates *(this+0x30)[+4] rows via vt+0x14, this+0x38 via vt+0x18, bitfields via vt+0x38; vt+0x54 finalize; then FUN_10007010 recompute shade [CONFIRMED @ 0x10004a00]"
0x10003e50,dirt-init,C2,sc3_dirt_init_layers,"Ctor/init. operator_new the layer stack: height grid this+0x30, shade this+0x34, this+0x38, bitfields this+0x40/0x44/0x48, 4 bit-planes this+0x50/0x54/0x58/0x5c sized (w*h)>>5. Defaults 0xf6/DAT_100203f8. FUN_10007010 shade; FUN_10016798(DAT_10024a28); subscribes msg ids 0x2f2ee63 and 0x624a8220 via FUN_10019a8b vt+0x14 [CONFIRMED @ 0x10003e50]"
0x10007010,dirt-shading,C2,sc3_dirt_compute_hillshade,"Core relief algo. Per cell gathers 4-neighbor heights (edge-clamped via FUN_10010d40 + mirror-extrapolate), builds normal FUN_100073b0(16.0,scale), dots with light vectors DAT_10020400 & DAT_1002040c (FUN_1000fd10/FUN_1000fd40), max, quantize FUN_10016852, writes shade byte to this+0x34 grid [CONFIRMED @ 0x10007010]"
0x100148d7,dirt-raster,C2,sc3_dirt_render_gouraudpoly,"Gouraud iso-poly scanline fill with depth params. Strip table DAT_10024258[orient*0x13]; vtx-idx tables DAT_10024259/0x10024265/0x10024267; param_5 vtx array, param_6 RGB array; interpolates pos+RGB per scanline; DAT_10025bb0 setpixel / DAT_10025bb4 getpixel; texture branch (param_7 LUT + param_9), dither param_8; delegates to FUN_10013556 when param_13>=param_12 [CONFIRMED @ 0x100148d7]"
0x10013556,dirt-raster,C2,sc3_dirt_render_gouraudpoly_flat,"Sibling of 100148d7 without depth-cull params; same DAT_10024258 strip table + gouraud scanline fill, DAT_10025bb0/bb4 [CONFIRMED @ 0x10013556]"
0x10015f44,dirt-raster,C2,sc3_dirt_render_texturedspan,"Textured scanline rasterizer. DAT_10024258 strip table; param_5 vtx list; maps param_7 texture LUT (0x400 mask) across span; writes 16-bit px direct + DAT_10025bb0 [CONFIRMED @ 0x10015f44]"
0x10007dc0,dirt-raster,C2,sc3_dirt_tessellate_edgespans,"Edge/span-list builder. new(0x17f4) vtx list 0x1ff*3 ints init 0x7fffffff; pulls verts via source vt+4/+0x14/+0xc/+8; plots via target vt+0x4c/+0x13c; emits 6-byte records {short x,short y,byte val,flag} into two 0x1800 bufs at this[0]/this[4], count this+8 capped 0x400 [CONFIRMED @ 0x10007dc0]"
0x10008be0,dirt-raster,C2,sc3_dirt_tessellate_edgespans_hi,"Near-identical sibling of 10007dc0, 0x400-entry list / 0x3000 buffer; same 6-byte span records + vt+0x4c/+0x13c plot [CONFIRMED @ 0x10008be0]"
0x10017c2d,dirt-reliefmap,C2,sc3_dirt_build_reliefmap,"Builds palette-shaded relief map. Edge-shape masks DAT_10024858/0x10024878/0x10024898 (8 entries); 256-bin height histogram local_42c; percentile thresholds (uses (w*h*9)/10, /0x600); sqrt area scale; calls FUN_100187da/FUN_100185c8/FUN_100181d6 edge dirt, FUN_100177b7 [CONFIRMED @ 0x10017c2d]"
0x10004420,dirt-build,C2,sc3_dirt_build_from_tilemap,"Build height grid from source bitmap. Source vt+0x24 rows, vt+0x30 get-record, vt+0x18 flag; 12-way switch on nibble (uStack_38&0xf) decoding tile-corner heights into this+0x30 grid; 2nd pass builds this+0x48 bitfield from vt+0x18; FUN_10007010 shade [CONFIRMED @ 0x10004420]"
0x1000e520,dirt-edges,C2,sc3_dirt_apply_edgefalloff,"Border falloff. Per cell computes 4-edge neighbor-delta bitmask bStack_25 (thresholds *0x3c vs *100); for each flagged edge runs 5-step (>>2 quarter) gradient write via layer service vt+0x90 [CONFIRMED @ 0x1000e520]"
0x100076e0,dirt-contour,C2,sc3_dirt_trace_contour,"Region-boundary walk. 8-dir Moore chain (switch cases 0-7 dx/dy) building vtx list at this[4] via FUN_10009ac0/FUN_10009830/FUN_10009920; caps at 0x3fc; swaps double buffer this[0..0xc]<->this[4..0xc] [CONFIRMED @ 0x100076e0]"
0x10015acf,dirt-blit,C2,sc3_dirt_blit_reliefdiamond,"Iso diamond-tile blit. DAT_10024258/0x10024269 strip table; builds top+bottom triangle descriptors, calls FUN_10015f44 x2; height layers DAT_10025bac+0x18/+0x20; rebuilds 0x200-entry remap LUT DAT_10024ea4..0x100252a4 when mode DAT_10024780 changes [CONFIRMED @ 0x10015acf]"
0x1001461d,dirt-blit,C2,sc3_dirt_draw_tile,"Draws one relief tile for rotation param_4 / zoom param_3. Fetches 4 corner colors vt+0x6c, height FUN_10013208/FUN_10013503; calls FUN_100148d7 with strip idx DAT_10025bbc and tables DAT_1002570c/0x10025b58/0x100252d0/0x10025740; clears cache memset 0x20402 on mode change [CONFIRMED @ 0x1001461d]"
0x100163c7,dirt-project,C2,sc3_dirt_setup_tileproj,"Sets iso-projection globals for tile-shape param_1 / rotation param_2: DAT_1002570c/0x10025710/0x1002570e/0x10025712/0x100252a8/0x1002571a/0x10025714/0x10025718 from height layers DAT_10025bac+0x18/+0x20 and coord tables DAT_10025720/0x10025b64/0x10025b88; strip idx DAT_10025bbc=FUN_10016389 [CONFIRMED @ 0x100163c7]"
0x10018f79,dirt-thumbnail,C2,sc3_dirt_render_thumbnail,"256x256 beveled thumbnail. Samples source layer at /0x56(86) into renderer vt+0xb8; draws 4 corner bevel triangles gated by this+0xc..0xf; per-px palette remap FUN_1001932c; RNG DAT_10025bd8 [CONFIRMED @ 0x10018f79]"
0x1001945b,dirt-procgen,C2,sc3_dirt_fill_midpoint,"Recursive diamond-square height fill. Splits rect; unset (0xffff) edge/center midpoints = avg of corners (FUN_10019708 clamp) via renderer vt+0xb4 get/vt+0xb8 set + RNG jitter FUN_1001bba8(DAT_10025bd8); recurses 4 quadrants [CONFIRMED @ 0x1001945b]"
0x100187da,dirt-procgen,C2,sc3_dirt_scatter_edgenoise,"Random border roughness. param_1=edge flags(0x10/0x20/0x30); amplitude from sqrt(this+4 size) & this+0x10 max-h; RNG FUN_1001bc23(DAT_10025bc0,lo,hi); stamps via FUN_10018b57 in 4 dirs over 0x400 cells [CONFIRMED @ 0x100187da]"
0x10005230,dirt-publish,C2,sc3_dirt_publish_layers,"Publishes 2 derived layers to services then frees them. param_1[0x12] bitfield->grid service vt+0x16c (setpixel vt+0x90, 4-neighbor OR); param_1[0x11] height bytes->placement service vt+0x148 (vt+0x6c, >>5 quantize, thresh 0x1f); dtor+null both [CONFIRMED @ 0x10005230]"
0x10003220,dirt-worldrender,C2,sc3_dirt_draw_worldquad,"Draws relief quad into world via renderer objs this+0x11c/0x120/0x124/0x128. Builds 2 transformed quads (FUN_10003996/100039af/100039e2, 0x100 fixed-pt), vt+0x110/0x130 draw, posts msg 0xfa2 subcode 0x14 via FUN_1000397a [CONFIRMED @ 0x10003220]"
0x10001a5d,dirt-worldrender,C2,sc3_dirt_draw_tileupdate,"Sibling of 10003220 for one tile-coord (param_1>>8). Transformed quad via this+0x11c/0x120/0x124; posts msg 0xfa2 subcodes 0x12/0x1e/0x20 then 0x12 via FUN_1000397a vt+0x7c/+0x34/+0x14 [CONFIRMED @ 0x10001a5d]"
0x100114bc,dirt-query,C2,sc3_dirt_query_tileheightproj,"Projects a tile's height to a coordinate; branches on water test vt+0x54. Builds GZCOM property objects FUN_1001d7a5(class 0x82e0074c); uses source this+100 vt+0xfc(height scale)/vt+0x10c(project); ftol result to vt+0x40 [CONFIRMED @ 0x100114bc]"
0x10016cce,dirt-palette,C2,sc3_dirt_load_palette,"Palette loader. switch(id 0..8) FUN_100100f0 loads .bmp: palBasic/data1Pal/data2Pal/data3Pal/(case4 dynamic via FUN_1001cb0f COM)/palUnder/palWater/palEdgeL/palEdgeD (strings 0x10024814..0x100247a4); stores at this+0xc+id*8 [CONFIRMED @ 0x10016cce]"
0x10006a20,dirt-message,C2,sc3_dirt_handle_stringmsg,"Reads string msg (param_1 vt+0x1c len / vt+0x18 data) into a std::string; looks up service FUN_1001cb0f vt+0x5c, calls vt+0xc; maintains small-buffer free-list DAT_10024a2c/DAT_10024a70. Note: 19 unreachable blocks removed by decompiler [CONFIRMED @ 0x10006a20]"
```

---

## 2. Notable findings (highest value)

- **Serialiser pair — the save-section producer you asked for.**
  - **`0x10004d90` = SAVE** (`sc3_dirt_save_state`): writes a chunk delimited by the literal keys **`DirtBag_Start` / `DirtBag_End`** (`0x100240f4` / `0x10024104`) plus tag words **`0x206c6e7c`** and **`0x21737de5`**, streaming the `this+0x30` grid rows via a writer object (`FUN_1001d397`; write-string `vt+0xa4`, write-row `vt+0x64`, finalise `vt+0x88`).
  - **`0x10004a00` = LOAD** (`sc3_dirt_load_state`): the mirror, via reader `FUN_1001d17b` (begin `vt+0x40`, read `vt+0x14`/`vt+0x18`/`vt+0x38`, finalise `vt+0x54`), then recomputes shade.
  - Note: this is **not** the vt+0x38-read / vt+0x88-write mirror pattern named in the brief — the read/write selectors here are `vt+0x14`/`vt+0x64` on a dedicated stream object, not the GZCOM persist-mirror pair. So SIMDIRT's persistence is chunk-keyed ("DirtBag"), not the world-layer vt+0x38/+0x88 shape.

- **Init + message subscription — `0x10003e50`** (`sc3_dirt_init_layers`): allocates the entire layer stack and subscribes to message ids **`0x2f2ee63`** and **`0x624a8220`**. These two ids are the DirtBag's inbound event hooks (likely terrain-changed / redraw).

- **Message dispatch ids (post side):** `sc3_dirt_draw_worldquad`/`draw_tileupdate` post message **`0xfa2`** with subcodes **`0x12, 0x14, 0x1e, 0x20`** — a small redraw/notify vocabulary. GZCOM class id **`0x82e0074c`** is used for property objects in `0x100114bc`.

- **Tunable / named-resource tables:**
  - **`DAT_10024258`**: iso triangle-strip descriptor table, **19 bytes (`0x13`) per orientation**, sub-fields `DAT_10024259` (vtx-index pairs), `DAT_10024265`, `DAT_10024267`, `DAT_10024269`. Drives every rasterizer (`100148d7`, `10013556`, `10015f44`, `10015acf`).
  - **Palette resource names** (`0x10016cce`): `palBasic.bmp, data1Pal.bmp, data2Pal.bmp, data3Pal.bmp, palUnder.bmp, palWater.bmp, palEdgeL.bmp, palEdgeD.bmp`.
  - Edge-shape masks `DAT_10024858 / 0x10024878 / 0x10024898` (8 entries each); light vectors `DAT_10020400 / 0x1002040c`; RNG contexts `DAT_10025bc0` and `DAT_10025bd8`.

- **Core algorithms present:** hill-shade normal lighting (`0x10007010`), diamond-square procedural height fill (`0x1001945b`), boundary contour trace (`0x100076e0`), and Gouraud/textured iso-poly rasterisers (`100148d7`/`13556`/`15f44`).

- **No per-tick `Simulate` entry point** was found in this slice. The module is event/redraw-driven (message subscribe in `0x10003e50`, message post in the world-render pair), not tick-driven. `[UNCERTAIN]` — a Simulate hook could live outside the 25-function slice.

---

## 3. Not determined / residual uncertainty

- All 25 functions were read and mechanically classified (C2). None left unclassified.
- **`0x10006a20`** — the decompiler removed 19 unreachable blocks, so the exact branch taken by the string-message handler is not fully reconstructable from the export; the string-read + service-dispatch skeleton is confirmed but the per-message behaviour is not. Missing evidence: the raw disassembly of the removed blocks (needs live Ghidra, not the text export).
- **Meaning of the tag words `0x206c6e7c` / `0x21737de5`** (`0x10004d90`) is reported raw — not resolved to an ASCII/type meaning; they are not printable little-endian ASCII.
- **Struct offsets are SC3U-specific and confirmed from these bodies only** — I did not cross-map to the iOS `SimCity Deluxe` binary, so no `[iOS-HINT]` claims are made. Per the workspace rule (0/5 goPowerPlant offset match), offsets here should not be assumed to transfer.
- Confidence is capped at **C2** for the whole slice per instructions (no runtime/second-witness available in a read-only pass).
