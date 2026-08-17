## 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x10004559,rci-layer,C2,sc3_rcilayer_init_acquire_services,"Init: guards this[3] init-flag; stores framework param_2 at this[0xe]; FUN_1003d040->[0xf], FUN_1003d02d->[0x10]; acquires 8 sub-services via param_2 vtable +0x138/+0x150/+0x11c/+0x14c/+0x16c/+0x154/+0x144/+0x188; +0x1b8(0x1fd7a8c) then QI(0xc1fd7a96)->[0x18]; sets *(byte)(this+3)=1"
0x1002c849,rci-layer,C2,sc3_rcilayer_init_via_singleton,"Init variant: FUN_1003ceec() singleton vtable +0x44->[0xf] +0x40->[0x10]; param_2 (framework) vtable +0x138/+0x150/+0x11c/+0x14c then +0x1b8(0x1fd7a8c)+QI(0xc1fd7a96)->[0x17], +0x16c/+0x154/+0x144; sets init-flag; on fail calls own vtable+0x10"
0x1002cee4,rci-layer,C2,sc3_rcilayer_bind_services,"Init: param_2 vtable +0x11c->[0xd], +0x14c->[0xf], +0x1b8(0x1fd7a8c)+QI(0xc1fd7a96)->[0x10], +0x13c->[0xe]; on fail calls own vtable+0x10 (shutdown)"
0x1002bf6a,rci-layer,C2,sc3_rcilayer_bind_services2,"Init: param_2 vtable +0x138->[0xd], +0x14c->[0xe], +0x1b8(0x1fd7a8c)+QI(0xc1fd7a96)->[0xf]; on fail calls own vtable+0x10"
0x10006b05,serialization,C2,sc3_rci_save_record,"FUN_1003e47b(this,stream) base-write; then param_3(persist obj) vtable +0x84(0xa352d404,*(this+0x2c)), +0x9c(0xa352d405,*(this+0x34)), +0x84(0xa352d406,*(this+0x3c)), +0x84(0xa352d407,*(this+0x30))"
0x10007915,serialization,C2,sc3_rci_save_record_thunk,"Adjustor thunk of 0x10006b05: this=param_1-8; FUN_1003e47b then keyed writes 0xa352d404..07 from offsets 0x24/0x2c/0x34/0x28 (== base 0x2c/0x34/0x3c/0x30)"
0x10019ccb,gzcom-service,C2,sc3_rci_query_service_object,"this[0xc] vtable +0x1b8 (service lookup) with serviceID 0x80f1e6d3 -> obj; obj vtable+0 (0x40a42f1c,&local); local vtable+0x14 (0xa2c9e821, 0xf1ec30, this+0xf); local vtable+8 (Release); returns bool"
0x1000ee95,gzcom,C2,sc3_rci_query_interface_80ec9834,"QueryInterface: iid 1 (GZIID_cIGZUnknown)->*out=this; iid 0x206c6e7c->*out=this+0xc (secondary iface); class iid 0x80ec9834->*out=this; then vtable+4 (AddRef); else return 0"
0x10016109,gzcom,C2,sc3_rci_query_interface_a106cf30,"QueryInterface: iid 1->this; iid 0x206c6e7c->this+0xc; class iid 0xa106cf30->this; vtable+4 (AddRef)"
0x10024214,gzcom,C2,sc3_rci_query_interface_4106c508,"QueryInterface: iid 1->this; iid 0x206c6e7c->this+0x10 (int*+4); class iid 0x4106c508->this; vtable+4 (AddRef)"
0x10026604,gzcom,C2,sc3_rci_query_interface_4106c508_thunk_c,"Adjustor thunk (this=param_1-0xc) of the 0x4106c508 QueryInterface; shares LAB_10024246 (AddRef path)"
0x1002660c,gzcom,C2,sc3_rci_query_interface_4106c508_thunk_10,"Adjustor thunk (this=param_1-0x10) of the 0x4106c508 QueryInterface; shares LAB_10024246"
0x1001b3bf,gzcom,C2,sc3_rci_get_id_c0ab8a88,"Returns constant 0xc0ab8a88 (class/interface id getter)"
0x10020f90,gzcom,C2,sc3_rci_get_id_c106c4f5,"Returns constant 0xc106c4f5 (class/interface id getter)"
0x1002df6a,gzcom,C2,sc3_rci_get_serviceid_80f1e6d3,"Returns constant 0x80f1e6d3 -- the same serviceID consumed by 0x10019ccb's +0x1b8 lookup"
```

All 15 bodies were read and mechanically described; every one is **C2**. None reaches C3/C4 (no runtime/second witness available).

## 2. Notable findings

**Save/serialise pair — keyed persist writes** `[CONFIRMED @ 0x10006b05 / 0x10007915]`
The highest-value structural find in this slice. `sc3_rci_save_record` (0x10006b05) calls base writer `FUN_1003e47b(this, stream)` then writes four keyed fields to the persist object (`param_3`) through its vtable:

| persist key | source struct offset | vtable slot |
|---|---|---|
| `0xa352d404` | `*(this+0x2c)` | +0x84 |
| `0xa352d405` | `*(this+0x34)` | +0x9c |
| `0xa352d406` | `*(this+0x3c)` | +0x84 |
| `0xa352d407` | `*(this+0x30)` | +0x84 |

`0x10007915` is the adjustor-thunk entry (`this = param_1 - 8`) hitting the same four keys through a secondary subobject (offsets 0x24/0x2c/0x34/0x28 = base 0x2c/0x34/0x3c/0x30). The three fields written via +0x84 share one accessor type; the +0x9c field (key `0xa352d405`, off 0x34) is a different type/width. These four property ids are the save keys for this RCI record. `[UNCERTAIN]` write-vs-read direction of +0x84/+0x9c — the callee vtable is not in this slice; mechanically the current field value is passed as the second argument, consistent with a Set/Write.

**GZCOM `QueryInterface` family** `[CONFIRMED @ 0x1000ee95 / 0x10016109 / 0x10024214 / 0x10026604 / 0x1002660c]`
Five bodies are the standard GZCOM multiple-inheritance `QueryInterface`. All recognise the base IID **`0x00000001`** (returns primary `this`) and a secondary-interface IID **`0x206c6e7c`** (returns an adjusted subobject pointer: `this+0xc` in the 0x…ee95/16109 objects, `this+0x10` in the 0x…24214 family), plus one class-specific IID each — **`0x80ec9834`**, **`0xa106cf30`**, **`0x4106c508`** — before calling vtable `+4` (AddRef). `0x10026604` (this−0xc) and `0x1002660c` (this−0x10) are adjustor thunks of the `0x4106c508` variant and jump into its shared `LAB_10024246` AddRef path.

**Class / service-ID getters** `[CONFIRMED @ 0x1001b3bf / 0x10020f90 / 0x1002df6a]`
Three 1-instruction getters returning constants `0xc0ab8a88`, `0xc106c4f5`, `0x80f1e6d3`. The last, `0x80f1e6d3`, is the exact serviceID that `sc3_rci_query_service_object` (0x10019ccb) passes to the framework's `+0x1b8` service-lookup slot — so 0x1002df6a is that layer's GetServiceID and 0x10019ccb is its consumer.

**Service-lookup-then-query** `[CONFIRMED @ 0x10019ccb]`
`sc3_rci_query_service_object` resolves service `0x80f1e6d3` via `this[0xc]`→vtable `+0x1b8`, calls the result's vtable+0 with class id `0x40a42f1c`, then the returned object's vtable `+0x14` with `(0xa2c9e821, 0xf1ec30, this+0xf)`, and releases via vtable `+8`. A three-hop registry→class→interface acquisition.

**Init / service-binding cluster** `[CONFIRMED @ 0x10004559 / 0x1002c849 / 0x1002cee4 / 0x1002bf6a]`
Four layer `Init`/rebind methods. All guard an init-flag byte at `this+3` and, on failure, call their own vtable `+0x10` (shutdown/cleanup). They cache framework sub-service pointers from a fixed set of framework-vtable accessor slots (`+0x11c/+0x138/+0x13c/+0x144/+0x14c/+0x150/+0x154/+0x16c/+0x188`) into `this[0xd..0x1b]`, and every one performs the same `+0x1b8(0x1fd7a8c)` service lookup followed by `QueryInterface(0xc1fd7a96, …)` — a shared acquisition idiom across the RCI layers. 0x1002c849 additionally uses the `FUN_1003ceec()` framework singleton (the same singleton the module map records for all five layer config loads) for its first two pointers.

## 3. Not determined

- **Which specific RCI sub-layer** (Zone / Valve / Res / Com / Ind) each function belongs to. The four Init methods, the serialiser pair, and the QueryInterface/ID getters are reached only through vtable/data slots; the text export carries **no static caller edge** to bind them to a layer (the module map already records this limitation for the whole module). Missing evidence: a live-Ghidra data xref from each function to the vtable that installs it, then to the ctor/factory/GZCLSID. The class/interface id constants (`0xc0ab8a88`, `0xc106c4f5`, `0x80ec9834`, `0xa106cf30`, `0x4106c508`) are candidates to cross against the 37-entry registration table but none matches a table GZCLSID exactly, so they are interface/service ids, not the layer class ids.
- **No per-tick / Simulate entry point, no message-id dispatch table, and no named tunable table** appear in this 15-function slice. (The tunable tables and the `sc3_valve_apply_effects` periodic loop live at the other RVAs already catalogued in `SIMRCI.md`.)
- **Serialiser read/write direction** (0x10006b05 / 0x10007915): the persist object's `+0x84`/`+0x9c` callees are outside the slice, so Set-vs-Get is inferred from argument shape only, not confirmed.
