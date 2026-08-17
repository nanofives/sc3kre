## Result — SimTransit slice (1 function)

The single function is a 6-byte constant getter. Both facts about the constant it returns are already CONFIRMED elsewhere in the module notes, so this closes cleanly.

### FUN_100015a7 — the whole body

```c
undefined4 FUN_100015a7(void)
{
  return 0x29ca804;
}
```

Mechanically [CONFIRMED @ 0x100015a7]:
- **Arguments:** none (`void`).
- **Reads:** nothing (no globals, no `this`, no struct offsets).
- **Writes:** nothing.
- **Calls:** nothing.
- **Returns:** the literal constant `0x029ca804` (dec 43,821,572), as `undefined4`.

**What the constant is.** `0x29ca804` is the **group id of SimTransit's save/serialisation section**, the second word of the section's `{type, group, instance}` persist key `{0x206c6e7c, 0x29ca804, 0}`. That pairing is not inferred here — it is written verbatim by the two serialisers and already CONFIRMED in the module notes:
- Load side `FUN_100048ee` (`sc3_transit_load_state`): `local_60 = 0x206c6e7c; local_5c = 0x29ca804` [CONFIRMED @ 0x100048ee, line 32-33].
- Save side `FUN_10004c8d` (`sc3_transit_save_state`): `local_20 = 0x206c6e7c; local_1c = 0x29ca804; local_18 = 0` → `FUN_10004e7f` builds the key [CONFIRMED @ 0x10004c8d, line 27-29].
- `SIMTRANSIT_CLUSTER2.md:50`: "SimTransit **does own a save section — type `0x206c6e7c`, group id `0x29ca804`**". `0x206c6e7c = GZIID_cISC3CityLayer` per the current HEAD commit.

So `FUN_100015a7` is a getter that hands back that group id (a `GetGroupID`/`GetPersistGroup`-style accessor for the transit layer's save section). It is these two files (`10004c8d`, `100048ee`) plus itself that are the only three bodies in the export containing the literal — no *caller* of `FUN_100015a7` exists in the SimTransit export (grep for `100015a7` returns only its own file), so its call sites are outside this module or reached indirectly (e.g. via vtable); that is the one piece of evidence not present here.

### 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x100015a7,transit-serialization,C2,sc3_transit_get_save_group_id,"6-byte getter: no args/reads/writes/calls; returns constant 0x029ca804. That value is the SimTransit save-section GROUP id, paired with type 0x206c6e7c (GZIID_cISC3CityLayer) in serialisers FUN_100048ee/FUN_10004c8d. [CONFIRMED @ 0x100015a7]; corroborated [CONFIRMED @ 0x100048ee], [CONFIRMED @ 0x10004c8d], SIMTRANSIT_CLUSTER2.md:50"
```

### 2. Notable findings

- **Serialisation-key accessor.** `FUN_100015a7` is a leaf constant-getter returning the **transit save-section group id `0x29ca804`** — part of the persist key `{type 0x206c6e7c, group 0x29ca804, instance 0}` that the confirmed load/save serialisers (`FUN_100048ee` / `FUN_10004c8d`) stamp into the record stream (header magic `0xDEADBEEF` at `+0x8`, per `FUN_10014318`). This is high-value for the file-format map: it names the module's persistence tag as a callable getter rather than an inline literal.
- No iOS corroboration: neither `0x29ca804` nor `0x206c6e7c` appears in `re/ghidra_export_ios/functions` (grep returned nothing), so no `[iOS-HINT]` is available for the constant's symbolic name. It is anchored entirely on the x86 side.

### 3. Not determined

- **Nothing left unclassified in the slice.** The one function is fully read and mechanically described.
- **One residual gap (does not block classification):** the exact *symbolic* GZ name of group id `0x29ca804` (analogous to how `0x206c6e7c` resolved to `GZIID_cISC3CityLayer`). Missing evidence: a string-xref or a named iOS/GZ symbol table entry mapping `0x29ca804` to a class/group name — absent from both the SimTransit and iOS exports.
