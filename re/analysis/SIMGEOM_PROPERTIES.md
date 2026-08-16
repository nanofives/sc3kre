# SIMGEOM_PROPERTIES.md — semantic meaning of building-occupant property ids 0x65-0x7c

Produced 2026-08-15 by a delegated read-only analysis pass; written to disk by the orchestrator
(single-writer rule). Witnesses: loader `0x1002286f` (GetProperty vt+0x38/+0x4c/+0x30), saver
`0x10022c09` (SetProperty vt+0x58/+0x6c/+0x50), extended saver `0x1002321c`. Consumers grepped in
`re/ghidra_export_simgeom/functions`. NO-GUESSING: every row cites an RVA and the literal
operation. iOS labelled `[iOS-HINT]` only.

## Architecture found (the two idioms driving these fields)

1. **Lazy resource-key slots (registry type `0x6100`).** A slot = `{+0x00 u32 cachedResolvedId
   (0 until resolved), +0x04.. GZ key data}`. Resolver `FUN_10022e2d` `[CONFIRMED @0x10022e2d]`
   calls `FUN_1001be55()` then `vt+0x14(keyPtr, 0x6100, &out)`; on failure cache = 0. Proven
   slots: `+0x34` (key at `+0x38`), `+0x84` (`+0x88`), `+0x94` (`+0x98`); another at
   `+0x44`→`+0x50` in `FUN_1002396f` `[CONFIRMED @0x1002396f]`.
2. **Appearance resource keys (type `0x2026960b`).** The `+0xf0` and `+0x108` keys (ids `0x6d` /
   `0x7c`) are 3-dword GZ keys built by `FUN_1001fa0c`; a different resource class from idiom 1.

`FUN_10022749` `[CONFIRMED @0x10022749]` selects a resource-key slot by a **purpose bitmask**:
`param&1`→`+0x34`, `param&2`→`+0x84`, `param&4`→`+0x94`, else 0; and if `+0x120 != 0` it delegates
the whole call to `(*+0x120)->vt+0x34(param)`. This proves `+0x34`/`+0x84`/`+0x94` are alternate
resource variants of one building, chosen by a purpose flag.

## Property table (semantic)

| property id | struct offset | proposed meaning | confidence | evidence (RVA + what the code does) |
|---|---|---|---|---|
| `0x65` | `+0x04` | Primary building/type id; resolved to a handle stored at `+0x2c` | C2 | `0x1002286f` loads prop→`+0x04`, then `FUN_1001bead()` (manager via `FUN_1001bdb4` vt+0x40) `vt+0x1c(+0x04)`→`+0x2c` |
| `0x66` | `+0x20`/`+0x28`/`+0x24` | 3-int tuple (descriptor count 3); meaning of the triple undetermined | C1 | `0x1002286f`/`0x10022c09` move indices 0,1,2 only; no reader found |
| `0x67` | `+0x34` | Resource-key slot (type `0x6100`); primary model/appearance variant, purpose bit0 | C2 | `0x10022725` & `0x10022749(param&1)`: return `+0x34` or resolve `FUN_10022e2d(+0x38,+0x34)` |
| `0x6b` | `+0x48`/`+0x4c`/`+0x50` | 3-dword value, guard-saved only when any dword nonzero; resolve idiom (type `0x6100`) present nearby | C1 | `0x10022c09` lines 13-16 guard; `FUN_1002396f` resolves a `+0x44`→`+0x50` key (offset alignment `[UNCERTAIN]`) |
| `0x6c` | `+0x54` | single dword | C1 | load/save move only (`0x1002286f`, `0x10022c09`); no reader |
| `0x6d` | `+0xf0`/`+0xf4`/`+0xf8` | GZ resource key #1, type `0x2026960b`, default group `0xa1096a4f` / instance `0xffffffff` (S3D appearance) | C3 | `0x1002286f` default block lines 119-124; ctor `FUN_1001fa0c`; matches `SIMGEOM.md` |
| `0x6e` | `+0x60` (byte) | boolean flag | C2 | `0x1002286f` type-1 byte load, default 0; `0x10022c09` saves only if byte != 0 |
| `0x6f` | `+0x64` | single dword (default `+0x6c` = 0) | C1 | move only |
| `0x70` | `+0x70` | single dword (default `+0x78` = 0) | C1 | move only |
| `0x71` | `+0x120` | Override/delegate CLASS id; validated at load against GZCOM interface `0x579` (default `0x57a` = 1402); at runtime a refcounted delegate object that overrides resource resolution | C2 | `0x1002286f` validates via `FUN_1001958a` factory `vt+0xc(id,0x579,&out)` else sets `0x57a`; `FUN_10022ff1` setter AddRef/Release; `FUN_1002301d` delegates `vt+0x28`; `FUN_10022749` delegates `vt+0x34`; `FUN_10022fea` getter. `[UNCERTAIN]` the exact site replacing the loaded int id with the object pointer |
| `0x72` | `+0x114` | single dword, default `0x5bee0`; emitted as 3rd element of a `{+0x10c,+0x110,+0x114}` triple | C2 | `0x1002286f` default `0x5bee0` (lines 149-152); `FUN_10022fba` copies the triple |
| `0x74` | `+0x84` | Resource-key slot (type `0x6100`); variant selected by purpose bit1 | C2 | `FUN_10022749(param&2)`: `+0x84` or resolve `FUN_10022e2d(+0x88,+0x84)` |
| `0x75` | `+0x94` | Resource-key slot (type `0x6100`); variant selected by purpose bit2 | C2 | `FUN_10022749(param&4)`: `+0x94` or resolve `(+0x98,+0x94)` |
| `0x76` | `+0xa4` | Resource-key slot, same 16-byte record layout; specific variant undetermined | C1 | shares layout with `0x74`/`0x75`; no proven reader |
| `0x77` | `+0xb4` | Resource-key slot (same layout) | C1 | no proven reader |
| `0x78` | `+0xc4` | Resource-key slot (same layout) | C1 | no proven reader |
| `0x79` | `+0xd4` | Resource-key slot (same layout) | C1 | no proven reader |
| `0x7a` | `+0xe4` | Resource-key slot (same layout) | C1 | no proven reader |
| `0x7b` | `+0xfc` | single dword (default `+0x104` = 0) | C1 | move only |
| `0x7c` | `+0x108`/`+0x10c`/`+0x110` | GZ resource key #2, type `0x2026960b`, default group `0x62e69238` (building catalog string table) / instance `0xffffffff` | C3 | `0x1002286f` default block lines 143-148; matches `SIMGEOM.md` |

### Record shape of the `+0x84`..`+0xe4` array

They are **7 slots** (ids `0x74`-`0x7a`), **not 13** — `(0xe4-0x84)/0x10 + 1 = 7`. `SIMGEOM.md`
says "13 others spaced 16 bytes apart"; that figure is **wrong** and should be corrected there.

Each slot is 16 bytes = a lazy resource-key record `{+0x00 u32 cachedResolvedId, +0x04.. GZ key
data resolved with registry type 0x6100}` (proven for `+0x84`/`+0x94` in `FUN_10022749`; `+0x34`
is the same record shape at a lower offset). They are **not walked by a numeric index** —
`FUN_10022749` selects among `+0x34`/`+0x84`/`+0x94` with a discrete purpose bitmask (bit0/1/2),
so they are named resource-variant slots, not an indexed array.

> **UPDATE 2026-08-16 — `+0xa4`..`+0xe4` now HAVE a proven consumer `[CONFIRMED @0x100224ed]`.**
> The occupant **destructor** `FUN_100224ed` (329 bytes) is the reader. It makes exactly **11**
> `vt+8` (Release) calls, on `param_1[0x12] 0x16 0x17 0x26 0x2a 0x2e 0x32 0x36 0x3a 0x3e 0x4d`
> — verified by direct count, not inference. Destructor indices are on the **full** object and
> the occupant base is full+0x14, so `base offset = index*4 − 0x14`:
>
> | dtor index | base offset | property |
> |---|---|---|
> | `[0x12]` | `+0x34` | `0x67` |
> | `[0x16]` | `+0x44` | (the `0x6b` resolve key) |
> | `[0x17]` | `+0x48` | `0x6b` |
> | `[0x26]` | `+0x84` | `0x74` |
> | `[0x2a]` | `+0x94` | `0x75` |
> | `[0x2e]` | `+0xa4` | **`0x76`** |
> | `[0x32]` | `+0xb4` | **`0x77`** |
> | `[0x36]` | `+0xc4` | **`0x78`** |
> | `[0x3a]` | `+0xd4` | **`0x79`** |
> | `[0x3e]` | `+0xe4` | **`0x7a`** |
> | `[0x4d]` | `+0x120` | `0x71` delegate |
>
> **What this closes:** the `+0x00` word of every one of those slots is a **refcounted COM
> interface pointer** — the resolved resource object — not a plain cached id. All seven
> `+0x84`..`+0xe4` slots are now proven to be the same kind of thing by a *reader*, not by
> layout. It also proves `+0x48` (`0x6b`) and `+0x120` (`0x71`) hold COM objects.
>
> **What it does NOT close:** which visual/model purpose each of `0x76`–`0x7a` selects.
> `FUN_10022749` still maps purpose bits 1/2/4 only to `+0x34`/`+0x84`/`+0x94`, and no code
> found so far reads `+0xa4`..`+0xe4` via a purpose bit. **Missing evidence is unchanged: an
> external caller passing a purpose bit ≥ 8.** The occupant vtable is `PTR_FUN_1002b658`.

## Functions classified — for the `functions.csv` merge

```
rva,subsystem,confidence,new_name,evidence
0x1002286f,simgeom-occupant,C2,sc3_bldocc_load_properties,"GetProperty loader over key table DAT_1002b4e8..DAT_1002b580; ids 0x65-0x7c"
0x10022c09,simgeom-occupant,C2,sc3_bldocc_save_properties,"SetProperty saver; mirrors loader; guard-saves 0x6b/0x6d/0x7c/0x72"
0x1002321c,simgeom-occupant,C2,sc3_bldocc_save_extended,"calls base save then writes placement flags +0x130/+0x131 (props DAT_1002b780/788) and class tag +0x128 (prop DAT_1002b770) vs 0x62b9da80; strings 'Debug Placement Info Only'"
0x10022749,simgeom-occupant,C2,sc3_bldocc_get_resource_by_purpose,"returns resource id for purpose bitmask 1/2/4 (+0x34/+0x84/+0x94); delegates to +0x120 object vt+0x34"
0x1002349f,simgeom-occupant,C2,sc3_bldocc_get_resource_thunk,"wraps FUN_10022749"
0x10022725,simgeom-occupant,C2,sc3_bldocc_get_primary_resource,"resolves +0x34 key via FUN_10022e2d(+0x38,+0x34)"
0x10022e2d,simgeom-occupant,C2,sc3_bldocc_resolve_reskey,"FUN_1001be55() vt+0x14(key,0x6100,&out); cache=0 on fail"
0x1002396f,simgeom-occupant,C2,sc3_bldocc_resolve_reskey_slot,"lazy resolve +0x44 key -> +0x50 cache, type 0x6100"
0x10022fba,simgeom-occupant,C2,sc3_bldocc_get_key2_triple,"copies {+0x10c,+0x110,+0x114} out"
0x10022fea,simgeom-occupant,C2,sc3_bldocc_get_delegate,"returns +0x120"
0x10022ff1,simgeom-occupant,C2,sc3_bldocc_set_delegate,"refcounted set of +0x120 (Release old vt+8, store, AddRef vt+4)"
0x1002301d,simgeom-occupant,C2,sc3_bldocc_delegate_or_default,"if +0x120 delegate vt+0x28 else default path"
0x10023568,simgeom-occupant,C2,sc3_bldocc_vt_get_key2_triple,"thunk->FUN_10022fba"
0x10023580,simgeom-occupant,C2,sc3_bldocc_vt_set_delegate,"thunk->FUN_10022ff1"
0x10023591,simgeom-occupant,C2,sc3_bldocc_vt_delegate_or_default,"thunk->FUN_1002301d"
0x1001d907,simgeom-occupant,C2,sc3_bldocc_resolve_class_579,"resolves (this+4)->vt+0x8c id to GZCOM iface 0x579 via factory"
0x1001958a,simgeom,C2,sc3_geom_get_class_factory,"FUN_10012880 vt+0x30 -> GZCOM class factory (vt+0xc = create/lookup by id,iid,&out)"
0x1001bead,simgeom,C2,sc3_geom_get_id_manager,"FUN_1001bdb4 vt+0x40 -> manager used to resolve +0x04 id into +0x2c"
```

## OPEN — not determined, and the exact missing evidence

- **`0x66` (`+0x20`/`+0x24`/`+0x28`)**: meaning of the 3-int tuple. Missing: any function reading
  these three dwords (none in SIMGEOM). Next: grep other modules for a matching 3-tuple copy.
- **`0x6b` (`+0x48`/`+0x4c`/`+0x50`)**: confirmed 3-dword guarded value, but the resolve-slot
  alignment to `FUN_1002396f` (`+0x44`/`+0x50`) is off by 4; the base-object offset (factory
  returns `+0x14`) may explain it. Missing: proof of which base pointer `FUN_1002396f` receives.
- **`0x6c` (`+0x54`), `0x6f` (`+0x64`), `0x70` (`+0x70`), `0x7b` (`+0xfc`)**: single dwords,
  load/save only. Missing: any reader.
- **`0x6e` (`+0x60` byte)**: confirmed boolean, but the branch that tests it is not found.
  Missing: a reader of `*(this+0x60)`.
- **`0x71` (`+0x120`)**: dual representation (persisted int class id vs runtime refcounted
  iface-`0x579` object). Missing: the exact code replacing the loaded id with the object pointer.
- **`0x72` (`+0x114`)**: default `0x5bee0`; emitted with `+0x10c`/`+0x110` as a triple by
  `FUN_10022fba`. Missing: the consumer of that triple (a lookup keyed by group/instance).
- **`0x76`-`0x7a` (`+0xa4`..`+0xe4`)**: share the resource-key record layout but no consumer reads
  them and no purpose-bit mapping is proven. Missing: a caller of `FUN_10022749` (or a sibling)
  referencing these offsets / passing purpose bits >= 8.
- **`FUN_10022749` purpose flags (1/2/4)**: the semantic name of each variant (e.g. normal vs
  night vs under-construction model) is undetermined. Missing: an external (non-SIMGEOM) caller
  passing a concrete flag constant.
- **iOS cross-check**: `[iOS-HINT]` `Occupant` names in `re/ghidra_export_ios` are all
  disaster/health (`NumberOfOccupantsDamaged`, `AfflictedOccupant`, `AbandonOrDestroyBuildings`)
  — the *population* occupant, not the building-model occupant; no named building-model
  resource-key accessor matched. **No transferable evidence; do not use.**
- **`ixf_text.csv`**: no building-stat vocabulary maps to these ids (they are numeric GZ property
  keys, not localized). Not a naming source here.
