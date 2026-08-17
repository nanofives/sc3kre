## Result — 9 functions, SIMGEOM toolkit-necessary set

All nine are **GZCOM COM-plumbing** for the SIMGEOM classes: `QueryInterface` bodies, their multiple-inheritance adjustor thunks, and `GetServiceID` getters. None are a tick/serialiser/message table — but the getters revealed three previously-unrecorded service IDs, corroborated by their request-descriptor call sites.

### 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x10004cb8,geom/gzcom,C2,sc3_geom_layermgr_query_interface,"QueryInterface for the 4-iface manager class (ctor 0x10004bda, GZCLSID 0xa0ab8c20). Matches riid in {0x1,0x58d,0x20631788,0x206c6e7c,0x215b29c5,0x81c0cb7c}; writes adjusted this to *ppv at +0/+4/+8; on hit calls AddRef via (*(*this+4))(); returns bool. [CONFIRMED @ 0x10004cb8]"
0x100069fd,geom/gzcom,C2,sc3_geom_layermgr_query_interface_adj04,"MI adjustor-thunk QI: this-=4 then runs the 0x10004cb8 dispatch (shares LAB_10004d07/cf1/d09). AddRef via (*(*this+4))(). [CONFIRMED @ 0x100069fd]"
0x10006a15,geom/gzcom,C2,sc3_geom_layermgr_query_interface_adj08,"MI adjustor-thunk QI: this-=8 into the 0x10004cb8 dispatch. [CONFIRMED @ 0x10006a15]"
0x10006a2d,geom/gzcom,C2,sc3_geom_layermgr_query_interface_adj0c,"MI adjustor-thunk QI: this-=0xc into the 0x10004cb8 dispatch. [CONFIRMED @ 0x10006a2d]"
0x10004c5e,geom/gzcom,C2,sc3_geom_layermgr_get_serviceid,"6-byte getter returning 0xa0ab89f0. Second witness FUN_100032ca pairs 0xa0ab89f0 as the serviceId dword of interface-request descriptors {iid,serviceId,flags} (with iids 0xe0faadc7 and 0x20631788). [CONFIRMED @ 0x10004c5e]"
0x1000c681,geom/gzcom,C2,sc3_geom_occupant_query_interface,"QueryInterface matching riid in {0x1,0x206c6e7c,0x406b1196}; writes this to *ppv (no adjust), AddRef via (*(*this+4))(), returns 1/0. Sits in the occupant range (near ctor 0x1000b8f1). [CONFIRMED @ 0x1000c681]"
0x1000ccbe,geom/gzcom,C2,sc3_geom_occupant_query_interface_adj04,"Sibling QI, same riid set {0x1,0x206c6e7c,0x406b1196}, this-=4 before write/AddRef. [CONFIRMED @ 0x1000ccbe]"
0x1000c17b,geom/gzcom,C2,sc3_geom_occupant_get_serviceid,"6-byte getter returning 0x80ab8ab0. Second witness FUN_1000beec pairs 0x80ab8ab0 with iid 0x406b1196 in a request descriptor {0x406b1196,0x80ab8ab0,0}. [CONFIRMED @ 0x1000c17b]"
0x10011561,geom/gzcom,C2,sc3_geom_citylayer_get_serviceid,"6-byte getter returning 0x1fd7a8c. Second witness FUN_100116e9 pairs 0x1fd7a8c with iid 0x206c6e7c (cISC3CityLayer) in descriptor {0x206c6e7c,0x1fd7a8c,0}. [CONFIRMED @ 0x10011561]"
```

### 2. Notable findings

**No tick/serialiser/message-dispatch in this slice.** These nine are pure GZCOM identity/lifetime boilerplate. The QI bodies contain no message ids — the values compared are interface ids (riid), not `kSC3Message*` constants.

**Three service IDs recovered (new), each proven by a request-descriptor call site.** The getters return a class's registered GZCOM service id, and each is confirmed by an independent function that builds a `{interfaceId, serviceId, flags}` request struct (fed to `FUN_10003529`/`FUN_1001f57c`/`FUN_1001f360`):

| getter | returns (serviceId) | paired IID | witness |
|---|---|---|---|
| `0x10004c5e` | `0xa0ab89f0` | `0x20631788` / `0xe0faadc7` | `FUN_100032ca` @ 0x100032f2, 0x1000338d [CONFIRMED] |
| `0x1000c17b` | `0x80ab8ab0` | `0x406b1196` | `FUN_1000beec` @ 0x1000bf9f [CONFIRMED] |
| `0x10011561` | `0x1fd7a8c` | `0x206c6e7c` (cISC3CityLayer) | `FUN_100116e9` @ 0x100116fc [CONFIRMED] |

Note `0xa0ab89f0` (serviceId) ≠ `0xa0ab8c20` (the manager's GZCLSID in the SIMGEOM.md table) — **serviceId and GZCLSID are distinct values** for the same class.

**Interface-id set expanded for `0x10004cb8`'s class.** The 4-interface manager's QI advertises six riids: `0x1` (cIGZUnknown), `0x58d`, `0x20631788`, `0x206c6e7c` (cISC3CityLayer, per commit `2c3a96d`), `0x215b29c5`, `0x81c0cb7c` (= `-0x7e3f3484` signed). They resolve to three subobject offsets: base (`0x1`, `0x20631788`), `+4` (`0x58d`, `0x206c6e7c`, `0x81c0cb7c`), `+8` (`0x215b29c5`).

**The three 8-byte functions are MI adjustor thunks, not standalone methods.** `0x100069fd`/`0x10006a15`/`0x10006a2d` do `this -= 4/8/0xc` and tail into `0x10004cb8`'s dispatch (they share its internal labels 0x10004d07/0x10004cf1/0x10004d09). Offsets −4/−8/−0xc exactly recover the primary object from subobjects 2/3/4 of the manager, whose ctor `0x10004bda` writes four vtable pointers at `+0/+4/+8/+0xc` (`PTR_FUN_100292c0`, `_10029278`, `_10029250`, `_1002923c`). Clean confirmation the manager is a 4-vtable MI object. For a source-port these four must be emitted as one QI plus three compiler-generated adjustor thunks.

**`cISC3CityLayer` (`0x206c6e7c`) is exposed by more than one SIMGEOM class** — it appears in both the manager QI (`0x10004cb8`) and the occupant QI (`0x1000c681`/`0x1000ccbe`), and as the paired IID for getter `0x10011561`.

### 3. Not determined

- **Exact owning class for `0x1000c681`/`0x1000ccbe`/`0x1000c17b`.** Named `occupant` from address locality (occupant ctors `0x1000b8f1`/`0x1002...` and shared service id `0x80ab8ab0`) — `[UNCERTAIN]`. Missing evidence: the `.rdata` vtable that lists these method addresses, to bind them to a specific ctor/GZCLSID. The vtable pointers are in `.rdata` (absent from the text export); needs `re/tools/pe_read.py` on the PTR tables or a live-Ghidra data xref.
- **Human-readable names for the raw IIDs** `0x58d`, `0x20631788`, `0x215b29c5`, `0x406b1196`, `0x81c0cb7c` (and serviceId semantics of `0xa0ab89f0`/`0x80ab8ab0`/`0x1fd7a8c`). Only `0x1` (cIGZUnknown) and `0x206c6e7c` (cISC3CityLayer) are named. Missing: an iOS-oracle `GZIID_*` cross-match or a string/registration xref. `[UNCERTAIN]`

All nine are C2 (body read, mechanics described, callees identified, named); getters additionally have a confirming second witness. No C3/C4 claimed.
