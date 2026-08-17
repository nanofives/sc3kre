# SIMSERV.DLL — toolkit-necessary slice (6 functions, save/load + QI)

All six are **GZCOM object-plumbing methods** reached only through `PTR_FUN_*` vtables (no direct-call xref inside the module — confirmed: `Grep` for each RVA returns only its own body + `symbols.csv`, consistent with the module map's vtable-dispatch note). Two persistence mechanisms and one QueryInterface are present. I read each body plus its base helper and, where relevant, its read/write counterpart.

## The two persistence idioms (established from the callees)

**Keyed DB-record persistence** — the stream/record object's vtable:
- `+0x84(id, value)` = **write** a keyed field (value by value) `[CONFIRMED @ 0x10001633:13]`
- `+0x80(id, addr)` = **read** a keyed field into an address `[CONFIRMED @ 0x100015c2:14]`
- base serializer = `FUN_10015ee9` (writes parent fields via this-vtable `+0x38/+0x3c/+0x40`, emits `this+0x1c` through param `+0x6c`) `[CONFIRMED @ 0x10015ee9]`

**Sequential stream persistence** — the stream object's vtable:
- `+0x68(byteval)` = write byte, `+0x88(dwordval)` = write dword `[CONFIRMED @ 0x10001706:10,16]`
- `+0x18(addr)` = read byte into addr, `+0x38(addr)` = read dword into addr `[CONFIRMED @ 0x100016a4:11,17]`
- base save `FUN_1001690b` (emits `this+0x14` via `+0x98`) / base load `FUN_100168c4` (reads via `+0x48`, `+0x50`) `[CONFIRMED @ 0x1001690b, 0x100168c4]`

---

## 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x10009abf,fire-layer,C2,sc3_fire_layer_query_cell_effect,"reads cell(p1,p2) from *(this+0x40) then *(this+0x3c) via grid vtable +0x34; scales by sub-object (this-vtable +0x1c) result*cell/0x100 @0x10009abf; fire region (adjacent to fire-layer ctor 0x10009b53)"
0x10001633,fire-station,C2,sc3_fire_station_save_dbrecord,"base FUN_10015ee9 then writes keyed fields 0x2352c88d/e/f (this+0x2c[3-byte],+0x30,+0x34) via record +0x84; read pair FUN_100015c2 uses +0x80; fire-station region @0x10001633"
0x10004aad,police-station,C2,sc3_police_station_save_dbrecord,"base FUN_10015ee9 then writes keyed fields 0xa352c8e8/9/a (this+0x2c[3-byte],+0x30,+0x34) via record +0x84; read pair FUN_10004a3c uses +0x80; police-station region @0x10004aad"
0x10001706,fire-station,C2,sc3_fire_station_save_stream,"base FUN_1001690b then writes bytes this+0x24/0x25/0x26 via stream +0x68, dwords this+0x28/0x2c via +0x88 @0x10001706"
0x100016a4,fire-station,C2,sc3_fire_station_load_stream,"base FUN_100168c4 then reads bytes into this+0x24/0x25/0x26 via stream +0x18, dwords into this+0x28/0x2c via +0x38; load counterpart of 0x10001706 @0x100016a4"
0x1000ef24,police-layer,C2,sc3_police_layer_queryinterface,"QI dispatch: iid 1/0xabf2d9->this+0x1c, 0x206c6e7c->+0x20, 0x215b29c5->+0x24, 0x81c0cb7b->+0x28; else base QI FUN_10006251; AddRef via +4 @0x1000ef24"
```

---

## 2. Notable findings (structural)

**Save/load serialisers — matched pairs (the highest-value finds in this slice).** This slice is almost entirely persistence code — exactly the "save/load serialisation" target:

- **Keyed DB-record SAVE**: `0x10001633` (fire station) and `0x10004aad` (police station). Each writes **three consecutive property ids** into a record via vtable `+0x84`:
  - Fire station: `0x2352c88d`, `0x2352c88e`, `0x2352c88f` `[CONFIRMED @ 0x10001633:13,15,17]`
  - Police station: `0xa352c8e8`, `0xa352c8e9`, `0xa352c8ea` `[CONFIRMED @ 0x10004aad:13,15,17]`
  - Fields serialised: `this+0x2c` (**3-byte** value, read as `uint3` — packed/RGB-shaped), `this+0x30` (dword), `this+0x34` (dword) `[CONFIRMED @ 0x10001633:11,15,17]`.
  - Their **LOAD counterparts** exist and were confirmed by grep: `FUN_100015c2` (fire, same ids via `+0x80`) and `FUN_10004a3c` (police, ids `0xa352c8e8/9/a` via `+0x80`) `[CONFIRMED @ 0x100015c2:14-21, 0x10004a3c:14-21]`. These are **not in the assigned slice** but are the direct read pairs — flag for a follow-up row.

- **Sequential-stream SAVE/LOAD pair** on the fire-station object: `0x10001706` (save) ↔ `0x100016a4` (load). Both touch the **same field layout**: bytes `this+0x24/0x25/0x26` + dwords `this+0x28/0x2c` `[CONFIRMED @ 0x10001706:10-18, 0x100016a4:11-19]`. So the fire-station exemplar implements **two** persistence surfaces (keyed record *and* raw stream) over different field ranges (`0x24–0x2c` stream vs `0x2c–0x34` record).

**QueryInterface dispatch table** — `0x1000ef24` is a hand-rolled multi-interface `QueryInterface`. IID → embedded sub-interface offset `[CONFIRMED @ 0x1000ef24:9-24]`:

| IID (raw) | returns |
|---|---|
| `0x1` (IGZUnknown) / `0x00abf2d9` | `this+0x1c` |
| `0x206c6e7c` | `this+0x20` |
| `0x215b29c5` | `this+0x24` |
| `0x81c0cb7b` (`-0x7e3f3485`) | `this+0x28` |
| (else) | tail-calls base QI `FUN_10006251` |

Sets `*param_2 = (this!=0) ? this+off : 0`, then AddRef via this-vtable `+0x4`, returns `true` `[CONFIRMED @ 0x1000ef24:25-27]`. The `this+0x1c` sub-interface return matches the layer factories' "returns obj+0x1c" convention (fire/police/crime layers). The primary IID `0x00abf2d9` shares the `0x00abf2` prefix with the **police-layer GZCLSID `0x00abf2ec`** from the module map — the strongest single witness for owning class, hence `police-layer`. The base QI `FUN_10006251` handles IIDs `0x1`, `0x817ab319` (`-0x7e854ce7`), `0xa0ace10a` (`-0x5f531ef6`) and returns `this` `[CONFIRMED @ 0x10006251:10-13]`.

**Cell-effect query** — `0x10009abf` is a fire-layer per-coordinate sampler, not a serialiser. Mechanically `[CONFIRMED @ 0x10009abf]`:
1. If `*(this+0x40) != 0`: read cell `(param_1,param_2)` via that grid's vtable `+0x34` into a byte `b2`; if `b2 == 0` → return false (`uVar2 & 0xffffff00`).
2. Read cell `(param_1,param_2)` from grid `*(this+0x3c)` via vtable `+0x34` into byte `b3`.
3. If `b3 != 0`: obtain sub-object `O = (this-vtable +0x1c)()`; if non-null, `r = (O-vtable +0x14)(param_3)`; return `(O-vtable +0x1c)( (int)(r * b3) / 0x100 )`.

Grid access `+0x34 = read cell` matches the module map's grid vtable. Constant: divide by `0x100` (256) `[CONFIRMED @ 0x10009abf:24]`. It gates a masked read (`+0x40` mask grid must be nonzero) then scales a second grid's value (`+0x3c`) by a `param_3`-derived factor.

---

## 3. Not fully determined (missing evidence)

- **Exact owning class of `0x10001633` / `0x10004aad` / `0x10001706` / `0x100016a4`** is by **address co-location** with the string-confirmed ctors (fire-station ctor `0x10001020` reads `[FireStation]`; police-station ctor `0x10004426` reads `[PoliceStation]`) plus the id-block split (`0x2352…` in the fire region, `0xa352…` in the police region). No name string is embedded in these serialisers themselves. **Missing witness:** the vtable dump (`PTR_FUN_*`) proving which class vtable holds each method. Marked `[UNCERTAIN]` on class, confident on region.
- **Meaning of property ids `0x2352c88d/e/f` and `0xa352c8e8/9/a`, and of `this+0x2c` (3-byte), `+0x30`, `+0x34`** — these are opaque persistence field ids and raw offsets; no label source in-module. **Missing:** the property-name registry (candidate `re/data/ixf_text.csv`) or a consumer that reads these fields for a purpose.
- **`0x1000ef24` owning class** — the `0x00abf2` IID-prefix match to the police-layer clsid is strong but is a family-prefix inference, not a proven binding. **Missing:** the police-layer vtable dump showing slot 0 (QI) → `0x1000ef24`. The four IIDs `0x00abf2d9 / 0x206c6e7c / 0x215b29c5 / 0x81c0cb7b` are unlabeled interface ids (reported raw).
- **`0x10009abf` sub-object semantics** — the object returned by this-vtable `+0x1c` and its `+0x14`/`+0x1c` methods were not read; described mechanically only. `param_1/param_2` are the cell coordinates, `param_3` is the factor input to `+0x14`.

**All six read to C2** (body read, mechanically described, callees identified, named). None claimed C3/C4 — no runtime or second witness produced.
