## 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x1001669f,serialization,C2,sc3_pollution_obj_deserialize,"reads stream(param_2): +0x20->this+4, +0x38->this+8, +0x18 bool->this+0xc, +0x48 x5 nested->this+0x10/0x18/0x14/0x1c/0x20, +0x38 count then +0x28 loop into array this+0x24, +0x48 x3 ->this+0x30/0x34/0x38; mirror of 0x100167ae [CONFIRMED @ 0x1001669f]"
0x100167ae,serialization,C2,sc3_pollution_obj_serialize,"writes stream(param_2): +0x70 this+4, +0x88 this+8, +0x68 bool this+0xc, +0x98 x5 this+0x10/0x18/0x14/0x1c/0x20, +0x88 count=(this+0x28-this+0x24)>>1 then +0x78 loop from array this+0x24, +0x98 x3 this+0x30/0x34/0x38; exact write-mirror of 0x1001669f [CONFIRMED @ 0x100167ae]"
0x100180e6,serialization,C2,sc3_eco_graph_deserialize,"reads +0x38 int x4 ->this+0xc/0x10/0x14/0x18, +0x40 struct x2 ->this+0x34/0x38, +0x18 byte ->this+0x3c, +0x48 x2 ->this+0x1c/0x20; sets this+0x2c=stream,this+0x30=0; computes ratio (this+0x2c*+/-1000)/(this+0x24|0x28); posts float 0x426840a0 via FUN_100120e3 +0x10 [CONFIRMED @ 0x100180e6]"
0x10018208,serialization,C2,sc3_eco_graph_serialize,"writes +0x88 int x4 this+0xc/0x10/0x14/0x18, +0x90 struct x2 this+0x34/0x38, +0x68 byte this+0x3c, +0x88 this+0x2c, +0x98 x2 this+0x1c/0x20; write-mirror of 0x100180e6 [CONFIRMED @ 0x10018208]"
0x100171ec,serialization,C2,sc3_pollution_stats_deserialize,"reads via FUN_100174a3 indexer: 12 ints from this+0x78, 10 from this+0xa0, 10 from this+0xc8, +1 int this+0x60 (stream +0x38); then this+0x64==0 ? vtable+0x48() : FUN_10016be1; mirror of 0x100172b7 [CONFIRMED @ 0x100171ec]"
0x100172b7,serialization,C2,sc3_pollution_stats_serialize,"writes 12/10/10 int arrays (this+0x78/0xa0/0xc8 via FUN_100174a3) + this+0x60 via stream +0x88; write-mirror of 0x100171ec [CONFIRMED @ 0x100172b7]"
0x1001525f,serialization,C2,sc3_eco_occupant_deserialize,"reads stream +0x38 int/+0x18 byte/+0x28 short and drives this vtable setters +0x18/+0x104/+0xfc/+0x34/+0x70/+0x78/+0xec/+0x108; 3 ints <<8 (fixed-point coords) into +0xec; returns 1 [CONFIRMED @ 0x1001525f]"
0x10001511,serialization,C2,sc3_incinerator_serialize,"FUN_10013b71 base-serialize then keyed writes stream +0x84(id,val): 0xe352c57c<-this+0x30, 0xe352c57d<-this+0x3c, 0xe352c57e<-this+0x40, 0xe352c57f<-this+0x44(byte) [CONFIRMED @ 0x10001511]"
0x10003545,serialization,C2,sc3_recycling_serialize,"FUN_10013b71 base-serialize then keyed writes +0x84: 0x4352c330<-this+0x30, 0x4352c331<-this+0x34, 0x4352c332<-this+0x40(byte) [CONFIRMED @ 0x10003545]"
0x10001605,building-model,C2,sc3_incinerator_place_occupant,"QIs param_1 0xc14f8955; registry FUN_10016338 +0x138/+0x11c; looks up occupant by param_1[9] id 0xe0faadc7; sets pos param_1[6](x&0x7ff,y>>0xb); copies model values param_1[0xb]+0x10/+0x18 into occupant +0xc/+0x14; registers via +0x48/+0x58; subiface 0x43680ca9 [CONFIRMED @ 0x10001605]"
0x100035f7,building-model,C2,sc3_recycling_place_occupant,"byte-identical to 0x10001605 (recycling variant); same QI 0xc14f8955 / lookup 0xe0faadc7 / subiface 0x43680ca9, pos param_1[6], model values param_1[0xb]+0x10/+0x18 [CONFIRMED @ 0x100035f7]"
0x1000234d,building-model,C2,sc3_incinerator_update_effectiveness,"age uVar3=model+0x1c; age>=MaxLifespan DAT_100200a4 ->out=0 + demolish(+0x68); age<=DeclineAge DAT_100200a8 ->out=OptimalGarbageCap DAT_100200a0; else linear decay; gated by powered(+0x150 grid @coords param_1[6]) and built(+0x4c==1); writes param_1[0xc] [CONFIRMED @ 0x1000234d]"
0x1000414c,building-model,C2,sc3_recycling_update_effectiveness,"same shape as 0x1000234d w/ MaxLifespan DAT_100201fc, DeclineAge DAT_10020200, OptimalPctReduction DAT_100201f4, OptimalPopServed DAT_100201f8; writes two outputs param_1[0xc],[0xd] [CONFIRMED @ 0x1000414c]"
0x100093ec,pollution-grid,C2,sc3_pollution_mark_cell,"reads tile type via this+0x24 obj +0x34 @(param_1,param_2); if !param_3||type==0x11 tests predicate this+0x104; sets/clears bit 0x8000 in grid this+0x128 (+0x34 read/+0x3c write, mask &0x7fff | 0x8000) and inc/dec polluted counter this+0x468 [CONFIRMED @ 0x100093ec]"
0x10006147,pollution-grid,C2,sc3_pollution_seed_region_from_source,"gated by param_2 +0x14(0xa2); size from +0x24(0x80); nested x/y loop over 0x80-typed region, 2x2 subcells; converts source byte->(b*0x7fff)/0xff; writes pollution grids via inner iface this-4 +0x98/+0x9c/+0x94/+0x90; reads cell types 2 and 0x20 via param_2 +0x18 [CONFIRMED @ 0x10006147]"
0x10014b20,occupant-query,C2,sc3_eco_occupant_fill_descriptor,"fills param_2 record from this: +0x28<-this+4 obj+0x14, +0x2c<-this+0x88(), +0x30<-packed coords this+0x10(x&0x7ff,y>>0xb&0x7ff,z>>0x16&0xff), +0x34<-this+0xd4() twice, +0x38<-this+0x10>>0x1e, +0x3c<-this+0xc>>0x18/0x19 bits; returns this+4!=0 [CONFIRMED @ 0x10014b20]"
0x10007e6b,pollution-ui,C2,sc3_pollution_ui_update_readout,"formats 3 values from param_1+0x110 (+0x24/+0x30/+0x3c) via number-formatter FUN_10012167 +0x94, fetches text param_1+0x114 +0x14, builds GZ-string (PTR_LAB_1001b130) via FUN_1000ecdc, sets slots 0/1/2 via param_1+0x110 +0x50 [CONFIRMED @ 0x10007e6b]"
0x10013468,platform-fileio,C2,sc3_eco_move_file,"lazy-loads KERNEL32.DLL MoveFileExA (cached DAT_100208e4, guard DAT_100208e0); moves file param_1->param_2 (paths via +0x14); falls back to MoveFileA on null-proc or failure [CONFIRMED @ 0x10013468]"
```

All 19 read to body level, callees identified, named → **C2**. None left C1.

---

## 2. Notable findings

**A. This slice is a save/load serialization cluster — 9 of 19 are stream (de)serializers, in matched write/read pairs.** The archive object (`param_2`) exposes a fixed GZ-style stream vtable, consistent across every function:

| slot | read (deserialize) | slot | write (serialize) |
|---|---|---|---|
| `+0x18` | read byte/bool | `+0x68` | write bool |
| `+0x20` | read blob→obj | `+0x70` | write byte |
| `+0x28` | read 2-byte element | `+0x78` | write 2-byte element |
| `+0x38` | read uint32 (returns found-flag) | `+0x88` | write uint32 |
| `+0x40` | read struct/pair | `+0x90` | write struct/pair |
| `+0x48` | read nested object | `+0x98` | write nested object |
| — | — | `+0x84` | write **keyed** field `(id,value)` |

`[iOS-HINT]` this matches the GZ framework `cIGZIStream`/`cIGZOStream` Get*/Set* interface (algorithm shape only; offsets are SC3U-side confirmed above).

Confirmed serialize/deserialize **pairs** (same struct offsets, mirrored slots):
- `0x1001669f` (load) ↔ `0x100167ae` (save) — main object: byte + int + bool + 5 nested + a `>>1`-counted element array at `this+0x24` + 3 nested.
- `0x100180e6` (load) ↔ `0x10018208` (save) — a graph/chart data object (`this+0xc..0x18` ints, `+0x34/0x38` structs, `+0x1c/0x20` nested). The loader additionally posts float `0x426840a0` via `FUN_100120e3` (a redraw/notify).
- `0x100171ec` (load) ↔ `0x100172b7` (save) — a stats block of **three fixed-size arrays: 12 + 10 + 10 int32** (at `this+0x78 / +0xa0 / +0xc8`, indexed by `FUN_100174a3`) plus one int at `this+0x60`.

**B. Keyed-property serializers with named property IDs (highest-value find).** Two building models save via `+0x84(propertyID, value)` after a base call to `FUN_10013b71`:
- **Incinerator** `0x10001511`: `0xe352c57c`←`+0x30`, `0xe352c57d`←`+0x3c`, `0xe352c57e`←`+0x40`, `0xe352c57f`←`+0x44` (byte).
- **Recycling** `0x10003545`: `0x4352c330`←`+0x30`, `0x4352c331`←`+0x34`, `0x4352c332`←`+0x40` (byte).

These IDs are consecutive per model (`…c57c/d/e/f`, `…c330/1/2`) — a persisted property table keyed by GZ PropertyID. `FUN_10013b71` (not in slice) is the shared base-class serialize.

**C. The two building-model aging ticks — confirmed decline formula.** `0x1000234d` (incinerator) and `0x1000414c` (recycling) are near-twins computing effectiveness from building age:
```
age = model[0xb] +0x1c()
if age >= MaxLifespan:          out = 0 ; call demolish (+0x68)
elif age <= DeclineAge:         out = Optimal
else:  out = Optimal - ((age-DeclineAge)*Optimal)/(MaxLifespan-DeclineAge)   // linear decay
```
- Incinerator → `DAT_100200a4` (MaxLifespan), `DAT_100200a8` (DeclineAge), `DAT_100200a0` (OptimalGarbageCap), single output `param_1[0xc]`.
- Recycling → `DAT_100201fc`, `DAT_10020200`, `DAT_100201f4` (OptimalPctReduction), `DAT_100201f8` (OptimalPopServed), two outputs `param_1[0xc]`, `[0xd]`.

Both gate on **powered** (`FUN_10016338` singleton `+0x150` grid, method `+0x34` at packed coords `param_1[6]`) and **built** (`param_1 +0x4c()==1`). These consume the tunables the module map recorded in §4 — this closes the loop on how `MaxLifespan`/`DeclineAge`/`Optimal*` are actually applied.

**D. Building-occupant instantiation, `0x10001605` == `0x100035f7` (byte-identical).** Each model's "place occupant" method: QI self `0xc14f8955`, look up the sim occupant by `param_1[9]` under IID `0xe0faadc7`, set world position from packed coords `param_1[6]` (`x&0x7ff`, `y>>0xb&0x7ff`), copy the model's two effect values (`param_1[0xb] +0x10/+0x18`) into occupant `+0xc/+0x14`, register into two world lists (`+0x48`, `+0x58`); sub-interface `0x43680ca9`.

**E. Pollution-grid cell primitives.**
- `0x100093ec` `sc3_pollution_mark_cell` — toggles the `0x8000` "polluted" bit in grid `this+0x128` and maintains the polluted-cell counter at `this+0x468` (the counter neighbouring the `this+0x46c = (w*h)/(UpdatePeriod<<2)` value from `FUN_10005844` in the module map). Tile-type `0x11` is a special-case pass-through.
- `0x10006147` `sc3_pollution_seed_region_from_source` — writes pollution across a `0x80`-typed region in 2×2 sub-cells, converting a source byte to the 0..`0x7fff` grid scale via `(b*0x7fff)/0xff`; gated by data-query `0xa2`.

**F. Atomic save via MoveFileEx.** `0x10013468` `sc3_eco_move_file` lazy-binds `KERNEL32!MoveFileExA` (cached in `DAT_100208e4`, guard `DAT_100208e0`), with a `MoveFileA` fallback — the temp-file→final-file rename used to commit a save.

**G. UI readout.** `0x10007e6b` `sc3_pollution_ui_update_readout` formats three numbers (from `param_1+0x110` slots `+0x24/+0x30/+0x3c`) through the number-formatter singleton `FUN_10012167(+0x94)` and pushes them to display slots 0/1/2.

---

## 3. Not determined (mechanically described, semantic gaps)

None of the 19 was left unclassified; each is C2. Residual `[UNCERTAIN]` semantics, with the exact missing evidence:

- **Owning class of `0x1001669f`/`0x100167ae` and the stats object `0x100171ec`/`0x100172b7`.** The (de)serializers are confirmed mirror pairs, but which concrete SIMECO object each persists (main pollution layer vs a sub-layer) is not proven from the body alone. Missing: the ctor that installs `this`'s vtable and the caller that invokes these Read/Write slots. `0x1001669f`'s counted array at `this+0x24` and the 12/10/10 arrays in `0x100171ec` have no field names here.
- **Property IDs `0xe352c57c-f` / `0x4352c330-2` → human key names.** Confirmed as consecutive persisted PropertyIDs for the incinerator/recycling models; the name strings live in the IXF/property registry, not in these bodies. Missing: the property-name table (SYS.PAK / property-list resource).
- **`0x1001525f` (`sc3_eco_occupant_deserialize`) — identity of the object it fills.** It drives high virtual setters (`this +0xfc/+0x104/+0x108/+0xec`) rather than raw fields, so the target class is opaque here. The three `<<8` values are fixed-point coordinates mechanically, but the object type needs `this`'s vtable owner.
- **`0x100180e6` posted float `0x426840a0` (= 58.0629 as IEEE-754) and message target `FUN_100120e3`.** The constant is confirmed as the literal passed; its meaning (a scale/threshold for the graph redraw) is not determinable inside SIMECO. Missing: the subscriber of that notification.
- **`0x10006147` query ids `0xa2` (`+0x14`) and cell-type selectors `0x80` / `2` / `0x20`.** Confirmed as the literal layer/data ids used; their named data-layer meanings come from the owning data-manager module, not read here.
- **`0x10014b20` descriptor field semantics.** The packed-coord unpack (`x&0x7ff`,`y>>0xb`,`z>>0x16&0xff`) and bit-flags (`>>0x18/0x19`) are confirmed mechanically; the meaning of `this+0x88`/`this+0xd4` method returns (fed to record slots `+0x2c`/`+0x34`) needs those methods' bodies.

Cross-refs (`FUN_10013b71` base-serialize, `FUN_100174a3` array-indexer, `FUN_10016338` city/registry singleton, `FUN_100120e3`, `FUN_10012167` formatter) are outside the 19-function slice but are named callees worth pulling into the next slice — `FUN_10013b71` in particular anchors the base serialize contract for the whole module.
