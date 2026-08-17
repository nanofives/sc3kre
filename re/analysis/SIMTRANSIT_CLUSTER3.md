## 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x10013b6a,transit-serialize,C2,sc3_transit_visit_arrays_dispatch38,"__thiscall(this,param_1,param_2); iterates 3 arrays via FUN_10013e21 over 16-byte headers at this+0x78 (12 elts), this+0xa0 (10), this+0xc8 (10), short-circuits on char return; calls param_2 vtbl+0x38 per element passing *piVar3; then single this+0x60; finalizes via this vtbl+0x48 (if this+0x64==0) or FUN_1001355f(this-8) [CONFIRMED @ 0x10013b6a]"
0x10012003,io-util,C2,sc3_io_move_file,"__cdecl(int*,int*); lazily LoadLibraryA(KERNEL32.DLL)+GetProcAddress(MoveFileExA) cached in DAT_1001fe8c (init flag DAT_1001fe88); path via param vtbl+0x14; MoveFileExA(flags=2) else MoveFileA fallback [CONFIRMED @ 0x10012003]"
0x10015da8,transit-serialize,C2,sc3_transit_write_record,"__thiscall; guards *(this+4)!=0; writes fields to param_2 stream via vtbl 0x28/0x2c/0x30/0x34/0x38/0x3c; unpacks packed dword this+0x10 into bitfields &0x7ff,>>0xb&0x7ff,>>0x16&0xff,>>0x1e; reads this+0xc bytes [CONFIRMED @ 0x10015da8]"
0x10013c35,transit-serialize,C2,sc3_transit_visit_arrays_dispatch88,"__thiscall; same 3-array iteration as 0x10013b6a (this+0x78/0xa0/0xc8, counts 12/10/10) but calls param_2 vtbl+0x88 passing *(undefined4*)*piVar2; single this+0x60 tail; no finalizer [CONFIRMED @ 0x10013c35]"
0x100051fc,gzcom,C2,sc3_gzcom_query_interface,"__thiscall(this,int iid,void** out); if iid in {1,0x58d,0x29ca805,0x206c6e7c,0x81c0cb7c} writes this to *param_2, calls this vtbl+0x4 (AddRef), returns 1 in low byte; else returns iid&0xffffff00 (0) [CONFIRMED @ 0x100051fc]"
```

## 2. Notable findings

**GZCOM interface-cast / message-id dispatch — `0x100051fc`** (highest value).
This is a GZCOM `QueryInterface`/`Cast` implementation. It tests `param_1` (an interface/message id) against a literal set and, on a hit, stores `this` into `*param_2` and calls the AddRef slot (vtbl+0x4), returning `1`:
- `1` = `GZIID_cIGZUnknown` [CONFIRMED @ 0x100051fc:9]
- `0x58d`, `0x29ca805`, `0x206c6e7c`, and `-0x7e3f3484` = `0x81C0CB7C` are the four additional GZ interface IDs this class answers to [CONFIRMED @ 0x100051fc:9-10].
The miss path returns `param_1 & 0xffffff00` (low byte 0 = false) [CONFIRMED @ 0x100051fc:16]. This is the canonical GZCOM `QueryInterface` id-table; the four non-`cIGZUnknown` constants are directly usable as interface-id keys for this SimTransit class.

**Serialization write path — `0x10015da8`.**
A record writer: it pushes fields into `param_2` (a stream/writer) through a contiguous vtable band `0x28,0x2c,0x30,0x34,0x38,0x3c` [CONFIRMED @ 0x10015da8:16-29]. The dword at `this+0x10` is a packed record: `x = v & 0x7ff`, `y = (v>>0xb)&0x7ff`, `z = (v>>0x16)&0xff`, plus `(v>>0x1e)` (top 2 bits) [CONFIRMED @ 0x10015da8:21,26] — an 11/11/8/2 bit packing (a tile coordinate + flags packing). Two bytes are unpacked from `this+0xc` via `>>0x18&1` and `>>0x19&1` and passed to vtbl+0x3c [CONFIRMED @ 0x10015da8:27-29]. Returns whether `*(this+4)` was non-null.

**Matched array-iterator pair — `0x10013b6a` / `0x10013c35`.**
Both walk the same three fixed-size arrays through the element accessor `FUN_10013e21` (which copies a 16-byte header from `this+off` then indexes via `FUN_10013e68`): header at **`this+0x78` (12 elements)**, **`this+0xa0` (10)**, **`this+0xc8` (10)**, then a single item at `this+0x60` [CONFIRMED @ 0x10013b6a:19,28,36,42 / 0x10013c35:18,27,36,41]. Each element is fed to a callback slot on `param_2`: **vtbl+0x38** in `0x10013b6a`, **vtbl+0x88** in `0x10013c35`. Both short-circuit the moment the callback returns 0 (the `cVar1` guard). `0x10013b6a` additionally finalizes: if `this+0x64 == 0` it calls `this` vtbl+0x48, else `FUN_1001355f(this-8)` [CONFIRMED @ 0x10013b6a:45-50]. The same 12/10/10 array triplet is aggregated numerically in `FUN_1001355f` (max-reduce → `* *(this+0x74)` float → clamp to `_DAT_1001b584` → `+ _DAT_1001a930` → write `this+0x68`) — context, outside the slice.

**File-move utility — `0x10012003`.**
Runtime-resolves `MoveFileExA` from `KERNEL32.DLL` once (cached in `DAT_1001fe8c`, guard `DAT_1001fe88`), calling it with flags `2` (`MOVEFILE_COPY_ALLOWED`); on absence or failure it falls back to `MoveFileA` [CONFIRMED @ 0x10012003:15-40]. Both `param_1` and `param_2` are path-provider objects (source, destination) queried through vtbl+0x14. A generic filesystem helper reused by SimTransit's save/load, not transit-specific.

## 3. Not determined

- **Semantic meaning of the 12/10/10 array triplet** (`this+0x78/0xa0/0xc8`) in `0x10013b6a`/`0x10013c35`/`0x1001355f`: the code mechanically reads 16-byte headers and indexes elements, but the domain meaning (lanes, directions, route slots) is not shown. Missing evidence: the type/constructor of the owning class (a caller/xref that populates these arrays) and the identity of the `param_2` vtbl+0x38 / vtbl+0x88 callbacks.
- **Which of `0x10013b6a` vs `0x10013c35` is the write vs the size/measure pass**: both are visitor loops over identical data with different callback slots (0x38 vs 0x88) and `0x10013b6a` dereferences one level less than `0x10013c35`. Distinguishing them requires the vtable definition of `param_2` (the stream/visitor class), which is not in this slice.
- **The four non-`cIGZUnknown` interface IDs in `0x100051fc`** (`0x58d`, `0x29ca805`, `0x206c6e7c`, `0x81c0cb7c`): confirmed as the id keys this class answers to, but their symbolic interface names are not determinable from this body. Missing evidence: a GZCOM IID→name registry or a matching `QueryInterface` in the unstripped iOS export.

All five are **C2** (bodies read, callees identified, mechanically described, named). No C3/C4 claimed — no runtime or second witness produced.
