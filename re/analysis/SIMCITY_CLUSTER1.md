## 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x1000429d,sim-save,C2,sc3_sim_serialize_city,"__thiscall(this,stream); seeds RNG this+0x10 via FUN_100071ce if 0; writes header (FUN_10007963), descriptor (FUN_10004851), options (FUN_10004ccd); iterates subsystem vector this+0x94..0x98 calling each vtable+0x28; sets state this+8=3 under lock this+0x1a8"
0x10004851,sim-save,C2,sc3_sim_build_city_descriptor,"__thiscall(this,stream); fills 128-byte descriptor local_bc from city fields: this+0xe4 vtable+0x78, 64-bit this+0xc4 vtable+0x10, date (FUN_1000930f year 0x76c=1900), name this vtable+0x88, this vtable+0x78; commits via FUN_1001097d"
0x1001097d,sim-save,C2,sc3_descriptor_write_and_destroy,"__fastcall(descriptor); writes chunk tag 0xe2f42628/0x62f42635 to embedded stream desc+8 via FUN_10004838/FUN_10010837/FUN_1000e9f4; branch on desc[4] (0/1/2) uses calendar FUN_100095af,FUN_10009708 on desc+0x40; then frees 4 embedded strings at +0x68/+0x54/+0x20/+0xc"
0x10007963,sim-save,C2,sc3_sim_write_globals_chunk,"__thiscall(this,stream); chunk tag 0x35ad1cb/0x835ad1d1; writes this+0x24, this+0x10 (RNG seed), this+0x14, this+0x18 via writer vtable+0x88/+0x98; plus two service values from FUN_10008775 vtable+0x20 and +0x6c"
0x10004ccd,sim-save,C2,sc3_sim_write_options_chunk,"FUN(stream); FUN_1000edff service vtable+0x80 obj; QI clsid 0x525a6b9/0x4525a6e2 (iid 0x199627); writes 3 values from service vtable+0x64/+0x48/+0x20 into stream sub-object via vtable+0x88"
0x1000f3f8,text-tokens,C2,sc3_token_expand_value,"resolves a %TOKEN% (param_3) by comparing (FUN_1001012f) against 8 token-key strings DAT_1001768c..0x10017734 (the +4 heads of the 8 token tables); appends resolved value to output stream param_2 vtable+0x1c via FUN_10010060; enum-switch (0x20/6/0x11/0x13/0x1f/0x2d/0x2e/0x31/0x36) loads localized strings id 0x259..0x260 group 0x41f2625"
0x1000c8db,scheduler,C2,sc3_scheduler_dispatch_loop,"__fastcall(sched); worker-thread pump: while sched[0x80]==0, walk callback list sched+4 (node[7]=due,node[6]=period,node[8]=one-shot,node+2/node[3]=callback); fire due nodes, reschedule/remove, sleep min-remaining via FUN_1000cff1(ms*1000); locks sched+0x40 (+0x38) and sched+0x5c; running flag sched+0x81"
0x10006bfa,sim-notify,C2,sc3_sim_rebuild_notification_set,"__fastcall(sim); broadcasts message 0x82684131 for each queued entry in list sim+0x66, clears it; per state sim[2] (3 vs 7) registers id ranges via FUN_10007635->FUN_10007e31; instantiates class 0x80f6a7ed at sim+0x4a (GetClassObject); enumerates subsystems (IID 0x13dee82) adding ids; sets sim+0x4b=1"
0x10007b28,sim-query,C2,sc3_sim_dispatch_query_check_debt,"FUN(target); creates collection via clsid 0x610438a4 (iid 0x6856f7); adds two 0x28-byte request objects (FUN_1000aec5) tagged 0x83172ad7 and target; commits (vtable+0x2c/+0x24); then debt check: if 64-bit at +0xc4 vtable+0x10 below -100000 (0xfffe7960), posts message 0x724a82e3/0x628d0c45/0xce"
0x10007a6d,sim-query,C2,sc3_sim_check_debt_warning,"__fastcall(city); queries clsid 0xe3270fe9 (iid 0x6856f7), reads flag via obj vtable+0xbc; if unset and 64-bit funds at city+0xc4 (vtable+0x10) below -100000 (0xfffe7960), posts message 0x724a82e3/0x628d0c45/0xce"
0x10005dde,sim-subsystem,C2,sc3_sim_enum_subsystems,"__thiscall(this,max,out[]); iterates subsystem vector this+0x94..0x98, QI(IID 0x13dee82) each, writes up to `max` object pointers into out[]"
0x10005d81,sim-subsystem,C2,sc3_sim_find_subsystem_by_id,"__thiscall(this,id,out); iterates this+0x94..0x98, QI(IID 0x13dee82), compares subsystem vtable+0x4c()==id; on match stores pointer in *out, releases, returns 1"
0x10005d35,sim-subsystem,C2,sc3_sim_count_subsystems,"__fastcall(this); iterates this+0x94..0x98, QI(IID 0x13dee82) each, releases, returns count of subsystems supporting the interface"
```

## 2. Notable findings

**Save/serialisation cluster (5 functions) — highest-value find.** `FUN_1000429d` is the **city serialise/save orchestrator**: under the lock at `this+0x1a8`, it seeds the RNG into `this+0x10` when fresh (`FUN_100071ce` from the map), writes a globals chunk, a city descriptor, an options chunk, then drives **every registered subsystem's `vtable+0x28`** over the `this+0x94..0x98` vector and sets simulator state `this+8 = 3` `[CONFIRMED @ 0x1000429d lines 110-117, 290-307]`. Its three writers:
- `FUN_10007963` writes chunk **tag `0x35ad1cb`/`0x835ad1d1`** carrying `this+0x24`, the **RNG seed `this+0x10`**, `this+0x14`, `this+0x18`, plus two `FUN_10008775`-service values `[CONFIRMED @ 0x10007963 lines 34-74]`.
- `FUN_10004851` builds the 128-byte **city descriptor** (the load-dialog metadata: a value from `this+0xe4`, a 64-bit value from `this+0xc4`, a date defaulting to year `0x76c`=1900, and two name strings) `[CONFIRMED @ 0x10004851 lines 46-78]`.
- `FUN_1001097d` writes that descriptor as chunk **tag `0xe2f42628`/`0x62f42635`** to the descriptor's embedded stream then destroys its 4 string members `[CONFIRMED @ 0x1001097d lines 40-47, 137-155]`.
- `FUN_10004ccd` writes an **options chunk** (IID `0x199627`, clsid `0x525a6b9`/`0x4525a6e2`) of 3 service values `[CONFIRMED @ 0x10004ccd lines 18-47]`.

**Bankruptcy/debt warning tunable.** Both `FUN_10007a6d` and `FUN_10007b28` read a **64-bit funds value at `city+0xc4` (`vtable+0x10`)** and, when it drops below `0xfffe7960` (= **-100,000** signed), post **notification message `0x724a82e3`** (with `0x628d0c45`, `0xce`) via the message server `FUN_100086c5` `[CONFIRMED @ 0x10007a6d lines 36-46, 0x10007b28 lines 74-84]`.

**Scheduler dispatch loop.** `FUN_1000c8db` is a **worker-thread callback pump** distinct from the sim-clock tick (map §3.2): it walks the callback list at `sched+4` where each node holds `[7]`=due-time, `[6]`=period, `[8]`=one-shot flag, `[2]`/`[3]`=callback; fires due nodes, reschedules or removes them, then sleeps the minimum remaining interval (`FUN_1000cff1(ms*1000)`). Guarded by stop flag `sched+0x80` and running flag `sched+0x81`, locks `sched+0x40`/`sched+0x5c` `[CONFIRMED @ 0x1000c8db lines 30-98]`. This matches the registered **`7000` scheduler class** (ctor `0x10001000`) shape from the map, not the internal sim-clock.

**Message-broadcast / mode activation.** `FUN_10006bfa` broadcasts **message `0x82684131`** for each queued item in list `sim+0x66`, then per game-state `sim[2]` (values **3** or **7**) registers different notification/menu id ranges (`FUN_10007635`→`FUN_10007e31`), instantiates the `0x80f6a7ed` helper class at `sim+0x4a`, and enumerates subsystems (IID `0x13dee82`) `[CONFIRMED @ 0x10006bfa lines 41-120]`.

**Subsystem interface IID `0x13dee82`.** Confirmed across five functions (`0x1000429d`, `0x10006bfa`, `0x10005dde`, `0x10005d81`, `0x10005d35`) as the QueryInterface IID for entries in the simulator's subsystem vector `this+0x94..0x98`. `vtable+0x4c` on a subsystem returns its type id; `vtable+0x28` is its serialise method.

**Text-token resolver.** `FUN_1000f3f8` is the value-producing half of the `%TOKEN%` system (companion to `FUN_1000f352` in the map): it matches the token key against the **8 token-table head strings** (`DAT_1001768c`, `0x100176a4`, `0x100176bc`, `0x100176d4`, `0x100176ec`, `0x10017704`, `0x1001771c`, `0x10017734` — each `+4` from the 8 table bases in map §3.5) and appends the resolved text to the output stream, including an enum→localized-string map over string ids `0x259`–`0x260` (group `0x41f2625`) `[CONFIRMED @ 0x1000f3f8 lines 132-360]`.

## 3. Not determined (residual uncertainty — all 13 classified, these are semantic gaps)

- **`FUN_1000429d` save-vs-load direction.** The descriptor path clearly *writes* (reads city fields → emits chunks), so it is classified as serialise/save; whether the subsystem `vtable+0x28` drive is symmetric write-only is not provable from this body alone. *Missing:* the subsystem-side `vtable+0x28` implementation, or a matching deserialise caller.
- **`FUN_10007b28` / `FUN_10007a6d` query purpose.** Mechanically they create/submit request objects (clsids `0x610438a4`, `0xe3270fe9`) and gate on the debt threshold, but what the request objects *do* is opaque. *Missing:* the bodies behind those clsids' vtables and the meaning of tag `0x83172ad7`.
- **`FUN_1000c8db` owning class.** Structurally the registered `7000` scheduler, but not tied to it by a call edge in the read set. *Missing:* the `7000`-class thread-proc that invokes this loop.
- **`FUN_10006bfa` state values `sim[2]==3` vs `==7`.** The two branches register different id ranges (`0x2ed`/`0x2f2`/`0x2f9` vs `100..0x68`); the game-mode meaning of 3 and 7 is not named here. *Missing:* the writer of `sim[2]` / a string mapping the modes.
- **Opaque 32-bit ids** (`0x82684131`, `0x724a82e3`, `0x628d0c45`, `0x35ad1cb`, `0xe2f42628`, `0x525a6b9`, message/chunk/clsid values): reported raw; no name strings map them in this module. *Missing:* the `SYS.PAK`/`CitySim.ini` id table or a cross-module director scan.

All 13 are rated **C2** (body read, mechanically described, callees identified, named). None reach C3 — no runtime trace or second witness was produced, and none was claimed.
