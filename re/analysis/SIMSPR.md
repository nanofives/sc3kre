# SIMSPR.md — SIMSPR.DLL, the sprite pipeline

```
Apps\SIMSPR.DLL   512,000 bytes   image base 0x10000000   3,265 functions
export: re\ghidra_export_simspr\
```

Director `GZDllGetGZCOMDirector` `0x1004f6ec` → ctor `0x1004c611` → **40** registrations via
`0x1004fa72`. 23 of those factories were label-only and were recovered with
`re/scripts/MakeFunctions.java`.

The manager is registered as **GZCLSID `0xa411112f`** and is a *thunk* returning the static
`&DAT_100726d8`, not an `operator_new` factory. Service handle: `GetService(CLSID 0x64111139,
IID 0x24111122)` (`FUN_1005ab10`).

Largest registered class: `0xe223be6c`, `operator_new(0xc84)` = 3,204 bytes. Per-class purpose
beyond the manager is `[UNCERTAIN]` — the methods are reached only through vtable data slots.

## Asset loading

`sc3spr_load_all_sprites` `0x10012e2b` is the **VIEW-Iso-LoadAllSprites** body: it builds
`%DataDirectory%\Res\Sprites` (falling back to `%PluginDirectory%\PlugIn\`, then `%Language%`) and
enumerates **`*.SII` then `*.DAT`**.

Each `.DAT` is an `.IXF` container (`formats/IXF_segment.md`) and each has a **`.SII` text mirror**
of its index (`sc3spr_import_index_text` `0x1001ea1d`):
```
Version: %ld            (0 or 1)
Record Count: %ld
v0 record:  "%08lX, %ld, %ld, %ld, %ld"
v1 record:  "%08lX, %08lX, %ld, %ld, %ld, %ld"
```
parsed into `+0x04 id1`, `+0x08 id2`, `+0x10/+0x12/+0x14/+0x16` = four `u16`s.

SIMSPR embeds its **own copy** of the `cGZDBSegmentIndexedFile` reader
(`sc3spr_dbseg_open_read_index` `0x10057826`) — magic `0x80C381D7`, 20-byte index records,
end-of-index = first 12 bytes zero, tombstone = `offset` or `size` == `-1`. Identical to the
GZResourceD reader and the SIMBABLD writer. It also has a **writer** (`0x100583cf`) — the second
independent `.IXF` producer found.

**Measured across the shipped data** (parent, with `re/tools/ixf_parse.py` unchanged):
72/72 archives parse, **253,838 records**, type 0 = 127,382 and type 1 = 124,774 — a near-exact
pairing, i.e. each sprite is a (pixels, anchor) pair. In `00000002_Residential.DAT` the archive
group is `2`, matching the `00000002` in the filename.

`[UNCERTAIN]` ~1,600 records carry type values outside {0,1} (`25344`, `545184782`, …). Either
there are record kinds not yet accounted for, or the index walk runs past the true end in some
files. Not yet resolved.

## Record formats

### Type 1 — 8 bytes, the anchor block `[CONFIRMED shape]`
Four little-endian `u16`. Two independent witnesses fix the slots: the text importer
`0x1001ea1d` writes four shorts to `+0x10/+0x12/+0x14/+0x16`, and `0x10012b98` fills the *same*
four slots from the bitmap when no stored data exists:
```
+0x10 = width / 2            (anchor X)
+0x12 = height - 1
+0x14 = width - (width / 2)
+0x16 = 1                    (flag)
```
`[UNCERTAIN]` the on-disk semantics beyond "4 × u16 anchor block": a real sample reads
`{0, 17, 16, 5}`, whose 4th short is 5 rather than the fallback's 1.

### Type 0 — pixel data, **QFS/RefPack compressed**
Full detail in **`formats/QFS.md`**. Header at the record start: `dword0` bits 8–15 = format code
(0 = raw → `FUN_1001e086`; 1 = compressed), `dword1` = flags, data at `+0x10`, QFS magic `0x10FB`
at `+0x14`. Decoder `sc3spr_decode_record` `0x1001de49` (vtable `PTR_FUN_10063598` slot 6);
decompressor `sc3_qfs_decompress` `0x10050d09`. **Verified against shipped bytes.**

### Instance → sprite
The manager keys the cache and provider lookup on the **pair (group, instance)**;
**no masking or shifting** of the instance id occurs anywhere on the read path (`0x10012b98`,
`0x10012d91`, `0x10057826`). Instances like `0x00900000` are literal index keys, not bit-packed.

## Field maps

**Sprite-definition object** (`sc3spr_parse_sprite_def_text` `0x10001909`):
`+0x18` frame array ptr (u32 count at `[-4]`, then N × 12-byte frames) · `+0x1c` `SprInstCLSID` ·
`+0x20` u16 `Frames` · `+0x22` u8 `AnimFrames` · `+0x23` u8 `AnimSetCount` · `+0x24` u8 `ZoomCount` ·
`+0x25` u8 `RotCount` · `+0x26` u8 `ZoomSetCount` · `+0x27` u8 `RegRects` · `+0x28` u32 `LayerFlags` ·
`+0x300` vector of `ScriptCountry` strings · `+0x30c` vector of script counts.

**Frame record** — 12 bytes, from `"Frame: %ld, %08lx, %08lx, %ld, %ld, %ld"`:
the two `%08lx` are the resource key (group, instance); `+0x01` u8, `+0x02` u16, `+0x04` u16,
`+0x08` u32 = the resolved sprite-cache pointer from `(mgr+0x34)(keyB, keyA)`; `+0x00` cleared.

**Sprite-instance record** — 20 bytes, from `"Sprite[%ld,%ld,%08lx,%ld,%ld,%ld]"`:
`+0x00` u32 sprite id, `+0x04` = 0, `+0x08`, `+0x0c`, `+0x10`. Pushed into a vector at
`this + (indexB + 0x6a + indexA*4) * 0xc`. `[UNCERTAIN]` whether A/B are zoom/rotation.

**Sprite-cache record** — 24 bytes (`0x10012b98`): `+0x00` refcount, `+0x04` group, `+0x08`
instance, `+0x0c` bitmap ptr, `+0x10`…`+0x16` the four anchor `u16`s.

**Archive object** — 408 bytes (`0x1001d8f7`): `+0x00` vtable `PTR_FUN_1006359c`, `+0x04`
stream sub-object, `+0x08` provider vtable `PTR_FUN_10063598` (**slot `+0x18` = the decoder**),
`+0x38` open vtable `PTR_LAB_10063578`, `+0x44` path (dedup key), `+0x94` record count,
`+0x98` record list, `+0xf4` colour key `(0xff, 0, 0xff)` — magenta.

Globals: `DAT_100726d8` manager singleton · `DAT_100726d0` record cache ·
`DAT_100726c8` archive-provider list.

## Open
1. **Pixel encoding after decompression** — bit depth, palette vs RGB, row order. In
   `FUN_1001e086` and the bitmap `+0xc8` colour-key call. Not read.
2. `VIEW-Iso-Anim` / `VIEW-Iso-Blt` / `VIEW-Iso-UpdateCitySurface` — profiling-label strings with
   no static body xref; the animation driver walks the frame array but is not pinned.
3. Per-class purpose for the 38 non-manager GZCLSIDs.
4. The ~1,600 out-of-range record types noted above.
