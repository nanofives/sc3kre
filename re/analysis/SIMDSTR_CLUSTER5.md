## Summary

The slice splits cleanly into two GZCOM-idiom families, both fully mechanical:

- **4x `QueryInterface`** (0x10008cd6 + three adjustor thunks) — the standard `cIGZUnknown::QueryInterface(this, iid, ppvOut)` for the disaster classes.
- **6x leaf "return a 32-bit id" accessors** — each returns one hard-coded GZ type/interface id, called through a vtable slot. The same id constants appear **inlined in the disaster classes' save/load serialization methods** (FUN_100089c3, FUN_1002027f, and ~27 others), which is the highest-value structural tie-in — see Notable findings.

All 10 are **C2** (body read, mechanically described, callee/leaf status established, named).

---

### 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x10008cd6,disaster-com,C2,sc3_dstr_query_interface,"QueryInterface(this,iid,ppvOut): *ppvOut=0; iid==1 or 0xe1f6abe2 -> this; iid in {0x58d,0x206c6e7c,0x81c0cb7c} -> this+4 (null-guarded); else return 0; on match calls AddRef via (*(*this+4))(); returns 1/0 [CONFIRMED @ 0x10008cd6]"
0x1000a08a,disaster-com,C2,sc3_dstr_query_interface_adj4,"adjustor-thunk QueryInterface: base=this-4; same iid set {1,0x58d,0x206c6e7c,0x81c0cb7c,0xe1f6abe2}; returns this for the +4 subobject; AddRef via *(*base+4); shares tail LAB_10008d1c [CONFIRMED @ 0x1000a08a]"
0x1000a0a2,disaster-com,C2,sc3_dstr_query_interface_adj8,"adjustor-thunk QueryInterface: base=this-8; special-iid result = base-4 (i.e. this-4), else base; same iid set; AddRef via *(*base+4) [CONFIRMED @ 0x1000a0a2]"
0x1000a0ba,disaster-com,C2,sc3_dstr_query_interface_adjc,"adjustor-thunk QueryInterface: base=this-0xc; special-iid result = base-8 (i.e. this-8), else base; same iid set; AddRef via *(*base+4) [CONFIRMED @ 0x1000a0ba]"
0x10006576,disaster-com,C2,sc3_dstr_get_typeid_621cda33,"leaf; returns constant 0x621cda33 (GZ type/interface id); no callees; reached via vtable slot [CONFIRMED @ 0x10006576]"
0x10007aed,disaster-com,C2,sc3_dstr_get_typeid_21f6abca,"leaf; returns 0x21f6abca; same 'f6ab' family as QI iid 0xe1f6abe2 and class#1 CLSID 0x61f6abf5; id is inlined into serializer FUN_100089c3 [CONFIRMED @ 0x10007aed,0x100089c3]"
0x1000e266,disaster-com,C2,sc3_dstr_get_typeid_4296380e,"leaf; returns 0x4296380e ('96380' family with 0x02963821/0x22963800); no callees [CONFIRMED @ 0x1000e266]"
0x10013b42,disaster-com,C2,sc3_dstr_get_typeid_02963821,"leaf; returns 0x02963821 ('96382' family); no callees [CONFIRMED @ 0x10013b42]"
0x10016de3,disaster-com,C2,sc3_dstr_get_typeid_22963800,"leaf; returns 0x22963800 ('963800' family); no callees [CONFIRMED @ 0x10016de3]"
0x1002136e,disaster-com,C2,sc3_dstr_get_typeid_c4c90997,"leaf; returns 0xc4c90997 ('4c9' family with class#7 CLSID 0x84c92cbe); id is inlined into serializer FUN_1002027f [CONFIRMED @ 0x1002136e,0x1002027f]"
```

---

### 2. Notable findings

**A. QueryInterface + multiple-inheritance adjustor thunks (the four QI functions).**
The four form one QI implementation replicated as `this`-adjusting thunks. Mechanically, each is `QueryInterface(this, iid, ppvOut)`:
- `*ppvOut = 0` first.
- Accepted IIDs: `1` (GZIID_cIGZUnknown), `0x58d`, `0x206c6e7c`, `0x81c0cb7c` (= `-0x7e3f3484`), `0xe1f6abe2` (= `-0x1e09541e`) [CONFIRMED @ 0x10008cd6].
- For `iid==1` or `iid==0xe1f6abe2` it returns the base pointer; for the other three it returns the `+4` sub-interface (null-guarded via the GZCOM idiom `-(uint)(p!=0) & (uint)(p+N)`).
- On any match it calls **AddRef** through vtable slot 1 (`(**(code**)(*base + 4))()`) and returns `1`; unmatched IIDs return `0`.
- The three thunks fix up `this` by `-4`, `-8`, `-0xc` respectively and jump to the shared tail `LAB_10008d1c` — i.e. they are the entry points for QI when called on sub-objects placed at +4/+8/+0xc in a multiply-inherited disaster-class layout. `0xe1f6abe2` is this module's own interface IID (matches the `f6ab` family of class #1's CLSID `0x61f6abf5`); `0x206c6e7c` is the serializable-sub-interface IID (see B).

**B. Save/load serialization is the consumer of these type-id constants — the highest-value tie-in.**
The six leaf accessors return the same 32-bit ids that appear **inlined as stream type tags inside the disaster classes' persistence (Load/Save) methods**:
- `FUN_100089c3` builds a typed reader with tag pair `{0x206c6e7c, 0x21f6abca}` (`FUN_1002a9ae` → `FUN_1002ad44`), then deserializes fields via `(*(*reader+0x38))()` into `this+0xb0/+0xa4/+0xd0/+0xd4/+0x54` [CONFIRMED @ 0x100089c3]. `0x21f6abca` is exactly the constant returned by 0x10007aed.
- `FUN_1002027f` builds a typed accessor with tag pair `{0xe1f6abe2, 0xc4c90997}` (`FUN_10004136`/`FUN_1002abca` → `FUN_1002ad44`), then reads fields via `(*(*acc+0x88))()`/`+0x68`/`+0x98` into `this+0x7d/+0x4c/+0x5c/+0x74/+0x78/+0x60/+0x64/+0x68/+0x6c/+0x80` [CONFIRMED @ 0x1002027f]. `0xc4c90997` is exactly the constant returned by 0x1002136e; `0xe1f6abe2` is the QI base IID from (A).

So the six 6-byte functions are `GetGZCLSID`/`GetPersistID`-style vtable accessors: each reports its class's persistence type id, and those same ids drive the DB-segment serialization of every disaster/event class. This is the save/load serialization surface the task flagged as high-value. The persistence type ids are **distinct from the COM registration CLSIDs** in SIMDSTR.md §2 (none of the six match the 12 registered CLSIDs) — normal GZCOM: separate factory CLSID vs. persist type id.

**Type-id families observed** (grouping only, not a proven class map): `f6ab` → {0x21f6abca, QI 0xe1f6abe2, cls#1 CLSID 0x61f6abf5}; `9638xx` → {0x4296380e, 0x02963821, 0x22963800}; `4c9` → {0xc4c90997, cls#7 CLSID 0x84c92cbe}; plus standalone 0x621cda33.

**No per-tick / Simulate entry point and no message-id dispatch table appear in this slice** — the 10 functions are COM plumbing (QI + type-id accessors), not simulation logic.

---

### 3. Not determined

- **Which numbered disaster class (SIMDSTR.md §2 #1–#12) each of the six type-id accessors belongs to.** The accessors are anonymous leaves; binding each to a class requires reading the class vtables (`PTR_LAB_*` targets) to see which vtable slot holds each accessor's address. The family-prefix groupings above are suggestive, not confirmed. Missing evidence: per-class vtable dumps (needs `symbols.csv`/`globals.csv` or live-Ghidra reference query, unavailable to a read-only grep of function bodies).
- **Semantic role of each accepted QI IID** (`0x58d`, `0x206c6e7c`, `0x81c0cb7c`). `0x206c6e7c` is confirmed as the serializable-sub-interface tag by its reuse in FUN_100089c3; the meaning of `0x58d` and `0x81c0cb7c` as named GZ interfaces is not determinable from this module (no name strings for them). Missing: a GZIID name table / SDK header.
- **The persist field layouts** (`this+0xb0`, `+0x7d`, etc.) belong to the class ctors/serializers outside this slice; only the tag ids are in-slice here.
