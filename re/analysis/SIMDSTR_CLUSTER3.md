## Summary

The 25-function slice is the **runtime backbone of SIMDSTR**: the module map (§3) already documented the *tunable loaders*; this slice is the layer, so what I read is the other half of every disaster's life cycle — **layer init/shutdown, instance init/tick state machines, save/load serialisers, and the message subscribe/dispatch plumbing**. All 25 were read and mechanically described (C2).

Shared idioms confirmed across the slice:
- **`FUN_10022eeb`** = the notification/message service. `vtable+0x14` = **subscribe**, `vtable+0x18` = **unsubscribe**, called with `(this+8, msgId)`.
- **`0x220fbd5b`** = the per-tick / Simulate pulse. **Every layer Init subscribes to it** — this is the single highest-value find: it is how the disaster subsystem is driven each frame.
- **`FUN_1002a89d` / `FUN_1002a7b8`** = shared service getters (property collection; resource service whose `vtable+0x34` yields the stream registry, `+0x2c` yields the COM class registry).
- Save/load section framing: **`0xe1f6abe2`** is the SIMDSTR record magic (paired with the layer GZCLSID `0x61f6abf5`). `FUN_1002abca`/`FUN_1002a9ae` open a section, `FUN_1002ad44` fetches the stream, `FUN_1002ad05` closes.

## 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x100193bf,disaster-serialize,C2,sc3_dstr_save_records_30,"save: section tags {0xe1f6abe2,0x0336f76a} then {..,0xa303b249}; writes vector this+0x60..0x64 elem-size 0x30 (count capped 50000) via stream vtable+0x88(count)/+0xac(buf); 2nd section enumerates list this+0x14 filtering type -0x1d69c7d8(0xe2963828), writes 0x30-byte recs"
0x1002e80e,disaster-serialize,C2,sc3_dstr_instance_serialize,"writer: sub-obj via FUN_1002e1f0 queried id 0x80199683, writes its +0x14/+0x1c/+0x24; then ~12 fields from this via getters to stream vtable+0x88(int)/+0x68/+0x78(float); writes 3-int(+0xb8) as >>8 and 3-float(+0xb0). Inverse of FUN_1002e675"
0x1001c53f,disaster-serialize,C2,sc3_dstr_save_records_20b,"save: tags {0xe1f6abe2,0xc446f87c}/{..,0xe311c076}; vector this+0x64..0x68 elem 0x20 (cap 50000); 2nd list this+0x10 filter type 0x13873254 -> read via elem vtable+0x18, write 0x20-byte recs"
0x1000f8ef,disaster-serialize,C2,sc3_dstr_save_records_20c,"save: tags {0xe1f6abe2,0xe4889ef6}/{..,0xe4889ef7}; vector this+0x64..0x68 elem 0x20 (cap 50000); 2nd list this+0x10 filter type 0x13873257 -> write 0x20-byte recs. Structural twin of 0x1001c53f"
0x1002e675,disaster-serialize,C2,sc3_dstr_instance_deserialize,"reader: from stream vtable+0x38(int)/+0x18(byte)/+0x28(float) into this via setters +0x18/+0x104/+0xfc/+0x34/+0x70/+0x78/+0xec/+0x108; height fields recovered as val<<8. Inverse of FUN_1002e80e"
0x10019aed,disaster-ufo,C2,sc3_dstr_ufo_instance_tick,"per-tick state machine states 0..5 at this+0x74, counter this+0x78++, timers 0x28/0x2c/0x30/0x34/0x38; sends msg id 0x4a via (this+0x10)+100 vtable+0x14 (1,0x4a,0,0,0)&(5,0x4a,0,1,0); calls FUN_1001ae5b/FUN_1001ab55/FUN_1001adc8/FUN_1001ae17/FUN_10018221. Pairs with init FUN_100196d1"
0x10028c84,disaster-io,C2,sc3_dstr_read_text_line,"getline over stream this+0x28 (vtable+0x18 tell/+0x1c size/+0x38 read/+0x30,+0x2c seek); reads 0x28-byte chunks, scans for CR/LF, appends into std::string at param_1+4 via FUN_10004acb"
0x100130e8,disaster-serialize,C2,sc3_dstr_load_records_58,"load: clears vector this+0x58..0x5c (FUN_1001449d), opens section 0xe1f6abe2, reads count local_14, per rec reads fields via stream vtable +0x48/+0x38/+0x40/+0x20 then appends via FUN_10014475"
0x1001146a,disaster-instance,C2,sc3_dstr_instance_init_a,"instance init (guard this+0xc): loads tunables DAT_1003a9c4/DAT_10039aa0/aa4/aa8/aac into timers this+0x10..0x24 (+0x24=+0x20+10), state this+0x78=1(or 4 if !param_3), counter 0x7c; subscribes msgs 0x625ec00b/0x425ec00b/0x525ec00b; loads sound via FUN_10024e7b(0x650496cd/cc)+DAT_10039ab0. Pairs with tick FUN_10011847"
0x10011847,disaster-instance,C2,sc3_dstr_instance_tick_a,"per-tick state machine states 1..6 at this+0x78, counter this+0x7c++, timers 0x10/0x14/0x18/0x1c/0x20; on 4->5 sends msg id 0xed via (this+0x60)+0x44 vtable+0x14 (1,0xed,0,0,0)&(5,0xed,0,0x4b,0); calls FUN_100119e9/FUN_10024067/FUN_100119a5/FUN_10010c19. Pairs with init FUN_1001146a"
0x100151f0,disaster-toxiccloud,C2,sc3_dstr_load_records_5c,"load: clears vector this+0x5c..0x60 (FUN_100176e0), section 0xe1f6abe2, count local_14, per rec reads +0x38/+0x38/+0x48/+0x40/+0x40/+0x40/+0x38/+0x38 then appends FUN_10017687"
0x100150a9,disaster-toxiccloud,C2,sc3_dstr_toxic_layer_init,"layer init: addref param_2(app), grabs sim services via app vtable 0xd8/0xdc/0x13c/0xcc(w-1)/0xd0(h-1)/0x11c/0x158/0x16c/0x138/0x14c into this+0x84/0x88/0x14/0x50/0x54/0x20/0x70/0x6c/0x74/0x78; stream reg FUN_1002a7b8+0x34->this+0x58; subscribes 0x220fbd5b; calls FUN_10014e93; sets this+0xc=1"
0x10017dcd,disaster-ufo,C2,sc3_dstr_ufo_layer_init,"layer init: string ""UFO_Swarm"" (PTR_s_UFO_Swarm_10039f10); grabs app services 0x13c/0x194/0x164/0x11c; registers COM class 0x6303efa6 in registry (FUN_1002a7b8+0x2c, reg vtable+0xc); subscribes 0x220fbd5b; sets this+0xc=1"
0x1000a466,disaster-locust,C2,sc3_dstr_locust_layer_init,"layer init: string ""Locust_Swarm"" (PTR_s_Locust_Swarm_1003980c); app services 0x13c/0x194/0x164/0x11c; registers COM class 0xc5326321; subscribes 0x220fbd5b; sets this+0xc=1. Structural twin of 0x10017dcd"
0x1000d42f,disaster-riot,C2,sc3_dstr_riot_layer_init,"layer init: app services 0xcc/0xd0/0x164/0x160/0x174/0x11c; provider 0x1b8(0x259c03f)->0x4259c018 into this+0x18; QI 0x621cda33 (result-0xc)->this+0x64; subscribes 0x220fbd5b; sets this+0xc=1. In riot 0x1000d block"
0x1001f6c6,disaster-parade,C2,sc3_dstr_parade_layer_init,"layer init: app services 0xcc/0xd0/0x164/0x1b8(0x259c03f->0x4259c018)/0x11c; sets this+0x70=1 + zeros many; subscribes 0x220fbd5b, 0x011fdae5, 0x211fdae5; sets this+0xc=1. Pairs with shutdown FUN_10020455"
0x1000d566,disaster-serialize,C2,sc3_dstr_load_records_70,"load: clears vector this+0x70..0x74 (FUN_1000eac9), section 0xe1f6abe2, count local_14, per rec reads +0x38/+0x38/+0x48/+0x38/+0x38 then appends FUN_1000ea0b"
0x10010848,disaster-tornado,C2,sc3_dstr_tornado_layer_init2,"layer init: app services 0x13c/0x194/0x14c/0x164/0x11c/0x120/0x124 into this+0x18/0x14/0x1c/0x20/0x2c/0x30/0x34; stream reg FUN_1002a7b8+0x34->this+0x38; subscribes 0x220fbd5b; sets this+0xc=1. In tornado 0x10010/0x10011 block"
0x100196d1,disaster-ufo,C2,sc3_dstr_ufo_instance_init,"instance init: loads UFO tunables DAT_1003aafc/DAT_10039ea0/ea4/ea8/eac into timers this+0x28/0x2c/0x30/0x34/0x38, state this+0x74=0(or 3 if !param_4), counter 0x78; subscribes 0x03092d3c/0x33092d3c/0x43092d3c/0x53092d3c/0x625ec00b. Pairs with tick FUN_10019aed"
0x100056e0,disaster-serialize,C2,sc3_dstr_load_records_6c,"load: clears vector this+0x6c..0x70 (FUN_10006c17), section 0xe1f6abe2, count local_14, per rec reads +0x38/+0x38/+0x48 then appends FUN_10006b8e"
0x10012ffc,disaster-tornado,C2,sc3_dstr_tornado_layer_init,"layer init: app services 0x13c/0xcc(w-1 this+0x48)/0xd0(h-1 this+0x4c)/0x11c; stream reg FUN_1002a7b8+0x34->this+0x50; subscribes 0x220fbd5b; picks random this+0x68=FUN_10022c1c(DAT_10039ad0,DAT_10039ad4); sets this+0xc=1"
0x1000ba19,disaster-locust,C2,sc3_dstr_locust_instance_init,"instance init: loads locust tunables DAT_1003a88c/DAT_100397e4/DAT_100397ec into timers this+0x2c/0x30/0x34, state this+0x58=0(or 2 if !param_3); subscribes 6 msgs 0xe5351201/0x854f737f/0x6535120a/0x45356db9/0xe546a035/0xc546b412; calls FUN_1000bde7. Pairs with shutdown FUN_1000bb8b"
0x10020455,disaster-parade,C2,sc3_dstr_parade_layer_shutdown,"shutdown (guard this+0xc): unsubscribes 0x220fbd5b/0x011fdae5/0x211fdae5; releases services this+0x10/0x1c/0x2c/0x58/0x14/0x18/0x20 via vtable+8; clears this+0xc. Inverse of FUN_1001f6c6"
0x1000bb8b,disaster-locust,C2,sc3_dstr_locust_instance_shutdown,"instance shutdown: clears this+0xc, FUN_1000a8dd/FUN_1000c6f9/FUN_1000a91f, decrements (this+0x10)+0x58 active count; unsubscribes same 6 msgs as FUN_1000ba19 (0xe5351201..0xc546b412). Inverse of FUN_1000ba19"
0x1000bca3,disaster-locust,C2,sc3_dstr_next_instance_coord,"round-robin iterator over collection this+0x14: if vtable+0x1c count==0 fills up-to-0x32(50) ptr array via +0x34, else indexes via +0x24; advances index this+0x24 mod count; returns two coords in param_1/param_2 (>>8) from chosen elem vtable+0x18; returns -1/-1 if empty"
```

## 2. Notable findings (structural)

- **Per-tick pulse `0x220fbd5b`** — subscribed by **every layer Init** in the slice (`0x100150a9`, `0x10017dcd`, `0x1000a466`, `0x1000d42f`, `0x1001f6c6`, `0x10010848`, `0x10012ffc`). This is the message that drives the whole disaster subsystem each simulation step. `FUN_10022eeb` `vtable+0x14`=subscribe / `+0x18`=unsubscribe. **This resolves module-map §7 open item "who invokes the loaders / how disasters are ticked" for the layer-tick half.**

- **Two complete instance state machines** (init + tick pairs, the actual disaster life cycle):
  - **UFO**: init `0x100196d1` → tick `0x10019aed` (state at `+0x74`, timers `0x28/0x2c/0x30/0x34/0x38`). Tick **dispatches message id `0x4a`** at the destruction stage `(1,0x4a,0,0,0)` and `(5,0x4a,0,1,0)`.
  - **"Instance A"** (tornado or riot — see §3): init `0x1001146a` → tick `0x10011847` (state at `+0x78`, timers `0x10..0x20`). Tick **dispatches message id `0xed` (237)** at the 4→5 stage `(1,0xed,0,0,0)` and `(5,0xed,0,0x4b,0)`.
  - These **`(1,id,…)` / `(5,id,…)` calls are the outbound message dispatch** the module map (§7) reported as "not determined." The `1`/`5` first argument is a message-verb selector; `id` is the event id.

- **Save/load serialiser family**, all framed by SIMDSTR magic **`0xe1f6abe2`**:
  - Writers: `0x1002e80e` (single instance, field-by-field) / `0x100193bf`, `0x1001c53f`, `0x1000f8ef` (bulk vector + filtered-list, fixed record sizes **0x30 / 0x20 / 0x20**, both capped at **50000** records).
  - Readers: `0x1002e675` (single instance, exact inverse of `0x1002e80e`, incl. `<<8` height decode) / `0x100130e8`, `0x100151f0`, `0x1000d566`, `0x100056e0` (count-prefixed record loops into distinct vectors `this+0x58/0x5c/0x70/0x6c`). **These are the disaster-instance persistence used by the city-save writer.**

- **COM class self-registration**: UFO layer registers `0x6303efa6` (name "UFO_Swarm"), Locust layer registers `0xc5326321` (name "Locust_Swarm") into the resource-service registry — new GZCLSIDs not in the module-map §2 table (those are per-disaster *swarm-item* classes, registered dynamically at layer init rather than at director ctor).

- **Per-instance message subscriptions** (the ids each disaster instance listens on):
  - UFO instance: `0x03092d3c`, `0x33092d3c`, `0x43092d3c`, `0x53092d3c`, `0x625ec00b`
  - Instance A: `0x625ec00b`, `0x425ec00b`, `0x525ec00b`
  - Locust instance: `0xe5351201`, `0x854f737f`, `0x6535120a`, `0x45356db9`, `0xe546a035`, `0xc546b412`
  - Parade layer: `0x011fdae5`, `0x211fdae5` (plus the tick pulse)

- **`0x1000bca3`** — round-robin position iterator over active instances (bounded at **50** entries), returns a display tile coordinate; how the UI/news locates active disasters.

## 3. Not determined / uncertain

- **Exact disaster type of `0x1001146a`/`0x10011847` and `0x1000d42f`/`0x10010848`.** The tunable DAT ranges narrow it but don't pin it: `0x1001146a` reads `DAT_10039aa0..aac` (between the riot block `DAT_10039a00..a24` and the tornado group `0x10039b0c`), and its init/tick sit in the `0x10011xxx` block alongside the tornado layer init `0x10010848`/`0x10012ffc`. **[UNCERTAIN]** — missing: which `PTR_LAB_*` vtable slot (class #2–#12, module-map §2) holds `0x1001146a`/`0x10011847`, i.e. a data xref from a class vtable to these addresses (needs `symbols.csv`/`globals.csv` or live Ghidra). I named them `*_instance_init_a`/`_tick_a` rather than guess.

- **Message-id semantics (`0x4a`, `0xed`, and the `1`/`5` verb selector).** Confirmed *sent*, but the receiving layer (news/finance/UI) and the meaning of the payload args (`0x4b` in the tornado dispatch, `0`/`1` in UFO) are outside this module. **[UNCERTAIN]** — missing: the handler in the target module keyed on these ids.

- **Record field layouts in the serialisers.** Sizes are exact (0x30 / 0x20) and the read/write vtable slot *sequence* is captured, but each slot's field name/type (which offset is coordinate vs timer vs id) is not determinable from the stream-interface calls alone. **[UNCERTAIN]** — missing: the struct definition of the vector element (the append helpers `FUN_10014475`/`FUN_10017687`/`FUN_1000ea0b`/`FUN_10006b8e` would show it).

- **`FUN_1002e80e`/`FUN_1002e675` owning class.** They live in the shared `0x1002exxx` infra region and take a generic `this`; the `0x80199683`-queried sub-object and the `<<8` height field tie them to a cloud/atmosphere instance but are not proven to be Toxic-Cloud. **[UNCERTAIN]** — missing: the caller/vtable slot that invokes them.
