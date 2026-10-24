# refaudit RESULTS (2026-10-24)

Task: audit the plain (non-atomic) refcount vtables left over from reload1024
(`verify/reload1024/plain_refcount_vtables.txt` + `plain_refcount_vtables_ecx.txt`: 87 vtables, 17 already fixed by
STRTSIM_REFCOUNT(_ALL) / SIMGROUP_REFCOUNT / SPR_REFCOUNT, 70 audited) for reachability from more than one thread,
then make the race-prone ones atomic in sc3perf.

## Verdict (Milestone 1)

**5 classes are RACE-PRONE** (objects that can be freed, touched by two live threads in turn more than a load-time
handoff): 4 from the first pass below, 1 more (SIMUI wrapper, rank 5) from the second pass over the `<= 1` template
(section "Second pass"). Two of the first 4 are outside the 70: they share an AddRef body with listed vtables and use a third Release
template the reload1024 scan did not match (`if count <= 1: destroy; else count -= 1`, list in
`le1_refcount_vtables.txt`, 86 vtables in 29 DLLs). Ranked by how often an object changed thread:

| rank | module | class (vtable) | AddRef / Release | threads | census (2 games, 1024 + reloads) |
|---|---|---|---|---|---|
| 1 | SIMSPR | resource object, 3-dword resource key at +0xc (vtables 0x1006896C / +4 0x10068950 / +0x18 0x10068934, ctor 0x10058a42) | AddRef 0x1005982A `inc [ecx+4]` (listed, shared with 0x100673A8) / Release 0x10059831 `if n<=1 vt+0x14(1)` via thunks 0x100589c6 -> 0x100598fc | game + sim + SIMSPR sprite-loader thread | 1,601 objects, 80 touched by 2+ threads, up to 11 thread switches on one object, 47k calls |
| 2 | GZResourceD | same framework resource class (vtables 0x1001D42C / +4 0x1001D410 / +0x18 0x1001D3F4, ctor 0x1000dc13) | AddRef 0x10015B03 `inc [ecx+4]` (listed, cSLTokenRecord 0x1001C62C [LINUX-HINT] shares it) / Release 0x1000B7C0 `if n<=1 vt+0x14(1)` via 0x1000ffdb -> 0x1000b8be | game + sim + sprite loader | 210 objects, 12 multi-thread, up to 8 switches |
| 3 | STRTSIM | cSSStrtSimOccupant family [LINUX-HINT] (base 0x1002B95C listed; live derived vtables 0x1002AF90, 0x1002C9BC, 0x1002B7AC) | AddRef 0x10003310 (already atomic, STRTSIM_REFCOUNT_ALL) / Release 0x1001607D `if n: n--; if !n vt+0x120(1)` (plain: the ALL pass only matches the esi form) | game + sim | 25 objects of 0x1002AF90, 17 multi-thread, up to 3 switches |
| 4 | SCENARIO | cSCNScenarioLayer [LINUX-HINT] (0x1001A64C, message-target subobject +4 vt 0x1001A604) | AddRef 0x10005B6F `inc [ecx+0xc]` / Release 0x100099A1 (esi form, dtor 0x100067f0 + delete); +4 thunks 0x1000f612 / 0x1000f61a | game + sim (GZ listener; 0xba3d133d sent synchronously from SIMCITY 0x100017e2 on the sim side) | 60 calls in 45 min, 3 switches: real but rare |
| 5 | SIMUI | wrapper object, 0x14 bytes (vtable 0x100A8164, ctor 0x10043d52; FUN_10043424 news it, AddRefs it, hands it to its owner's vt+0x9c and Releases it) | AddRef 0x100139B6 `inc [ecx+4]` (shared by other SIMUI classes) / Release 0x10043BA9 `if n<=1 vt+0x44(1)` | game + sim | 84 calls in 39 min, all 9 objects went game -> sim -> game (2 switches each): rare |

Everything else in the 70 is single-thread (42 not hit at all, 23 game thread only) or a **handoff only** (4): the
object is built on the game thread at load and then used by the sim thread, one or two switches per object over the
whole run, never back and forth (SIMGEOM 0x10029224: 430 objects, 190 with 2 threads, max 1 switch; SIMRCI
0x1004D39C: 137 M calls, max 2 switches = old sim thread, new sim thread after the reload).

**Benign although hammered:** the per-DLL `cRZCOMDllDirector` singletons (Linux-named in SimTransit
`RZGetCOMDllDirector_SimTransit` 0x100010d1 [LINUX-HINT]) use the plain AddRef `inc [ecx+0x20]` from every thread,
TRAFFIC_MT workers included (SimTransit's director: 107 M calls, 91 M thread switches). Their Release (slot 2 ->
vt+0x28 = slot 10) only decrements and never destroys (checked in SimTransit, SIMGEOM, SIMRCI, SIMSERV, SIMUTIL, SIMECO,
SIMMISC, SIMSPR, SIMNTWRK, SIMADV), so a lost update changes an unload count the game never acts on. Not patched.

Not exercised: no disaster instance was created in the census games (a crop-duster dispatch only), so the disaster
classes (SIMDSTR 0x10032498 / 0x10032C98 / 0x1003314C / 0x100332C8 / 0x100337B4) and the disaster layer 0x100325A0
(GZ listener, 142 calls, game thread only) are "single-thread as far as seen". The static read found only game-side or
posted senders for them.

## Method

1. Static (sub-agent over the Ghidra exports + PE): class identity from constructors / QI / Linux pairs, whether it is
   a GZ message listener (QI 0x58d, DoMessage, AddNotification calls through the message server vtable 0x10014618:
   +0xc MessageSend 0x10003922 dispatches on the caller's thread and AddRefs/Releases every listener, +0x10 MessagePost
   queues, +0x14 AddNotification 0x100039ee), and who holds it. Only 6 of the 70 are GZ listeners; none subscribes to
   the high-rate occupant messages 0x826cb9b6 / 0x426cb9b3 that broke the strike-crowd producer.
2. Runtime census (`re/tools/refaudit/census.py`): a Frida CModule (C, no JS per call) on every distinct AddRef and
   Release body of the lists (96 hooks, then 201 with the `<= 1` template list). Per call: object = ecx, its live
   vtable, the thread, whether the caller is GZServiceD. Per object: the set of threads and the number of
   consecutive calls that came from a different thread ("switches"). Threads are classed from their stacks: game
   (SC3U start), sim (SIMCITY frames, one new sim thread per city), TRAFFIC_MT worker (sc3perf+0x6993), SIMSPR sprite
   loader. Objects reached through a shared body with another class are attributed to their own vtable, which is how
   the two resource classes were found.
   - game c1 (25 min): Europolis 1024 maximized 3840x1984, speed 4, Load City -> Europolis 1024b, -> Berlin (256),
     -> Europolis 1024 (the last load after the census ended). 116 M calls.
   - game c2 (20 min, same process): 1024 at speed 4, emergency dispatch, Load City -> 1024b. 456 M calls.
   - Both: 0 access-violation faults outside KERNEL32 (the 566 first-chance KERNEL32+0x1CA9E reads on the game thread
     during the Load City dialog also appear in the reload1024 logs: pre-existing, handled).
   - Caveat: Frida resolves a hook on a body sc3perf already redirected (`jmp`) to sc3perf's function, and the linker
     folded identical sc3perf bodies, so per-function counts for already-patched bodies mix classes. The per-object
     table keys on the object's own vtable and is not affected.
3. Reference points measured the same way: the two classes that crashed in reload1024 (STRTSIM producer 0x1002C594:
   670 switches on one object; SIMCITY sim group 0x10013CF0: 31,863) and SIMSERV 0x1001F2C8 (958), SIMSPR overlays
   0x10067264 / 0x10064390 (741 / 641). All are already atomic.

Data: `census_merged.tsv` (all objects by vtable, v1+v2), `census_le1_merged.tsv` (v2+v3+v4), `census_c1_report.txt`, `census_c2_report.txt`,
`le1_refcount_vtables.txt` (the third template, all DLLs).

## All 70 audited vtables

| module | vtable | AddRef (+off) / Release | class (static) | threads seen (census) | verdict |
|---|---|---|---|---|---|
| SCENARIO.DLL | 0x1001A64C | 0x10005B6F (+0xc) / 0x100099A1 | cSCNScenarioLayer [LINUX-HINT]; GZ listener (msgs 0xda3fe447 0xa44fab08 0x84628d9a 0xba3d133d, Init 0x10007bd5); 0xba3d133d sent synchronously by SIMCITY 0x100017e2 (sim side) | main+sim (60 calls, 4 objs, 2 multi-thread, max 3 switches) | **RACE-PRONE** (rank 4, rare) |
| SIMADV.DLL | 0x100303F0 | 0x100064FD (+0x2c) / 0x10006504 | cSC3AdvisorMessageRecord [LINUX-HINT] | main (24 calls, 20 objs, 0 multi-thread, max 0 switches) | single-thread |
| SIMADV.DLL | 0x10030AA8 | 0x10011702 (+0x5c) / 0x10011709 | advisor record (3 strings), new in 0x1001019a | main (20 calls, 9 objs, 0 multi-thread, max 0 switches) | single-thread |
| SIMADV.DLL | 0x10031178 | 0x1001C97A (+0x58) / 0x1001C981 | advisor record, created in 0x100193dc | main (79 calls, 36 objs, 0 multi-thread, max 0 switches) | single-thread |
| SIMDSTR.DLL | 0x10032498 | 0x1000652F (+0x2c) / 0x100066F0 | cSC3FireDisasterInstance [LINUX-HINT] | not seen | single-thread / not hit |
| SIMDSTR.DLL | 0x10032C98 | 0x1000E087 (+0xc) / 0x1000E4EB | disaster instance (riot block) [UNCERTAIN type] | not seen | single-thread / not hit |
| SIMDSTR.DLL | 0x1003314C | 0x10013A81 (+0x78) / 0x10014090 | disaster instance (tornado block); GZ listener 0x42a343a0/0x62a343a0 (posted by SIMSPR) | not seen | single-thread / not hit |
| SIMDSTR.DLL | 0x100332C8 | 0x10016A93 (+0x50) / 0x1001715C | cSC3ToxicCloudDisasterInstance [LINUX-HINT]; GZ listener | not seen | single-thread / not hit |
| SIMDSTR.DLL | 0x100337B4 | 0x1000E087 (+0xc) / 0x100214F6 | disaster instance (parade block) [UNCERTAIN type] | not seen | single-thread / not hit |
| SIMGEOM.DLL | 0x1002942C | 0x1001474E (+0x4) / 0x10004DAB | cSGDemolitionTest functor [LINUX-HINT]; heap temp | not seen | single-thread / not hit |
| SIMSPR.DLL | 0x100673A8 | 0x1005982A (+0x4) / 0x10041564 | COM class CLSID 0xe476487b, one instance | main (9 calls, 5 objs, 0 multi-thread, max 0 switches) | single-thread itself; its AddRef 0x1005982A is shared with the rank 1 resource class |
| AUDIO.DLL | 0x10020D98 | 0x10011277 (+0x4c) / 0x1001127E | cSC3AudioInfo [LINUX-HINT]; GZ listener (0x620effde 0xc2684066 0x231e2493) | main (56 calls, 5 objs, 0 multi-thread, max 0 switches) | single-thread |
| GZResourceD.dll | 0x1001C62C | 0x10015B03 (+0x4) / 0x100039F1 | cSLTokenRecord [LINUX-HINT]; per record open | main (344 calls, 11 objs, 0 multi-thread, max 0 switches) | single-thread itself; its AddRef 0x10015B03 is shared with the rank 2 resource class |
| SCENARIO.DLL | 0x1001A308 | 0x100012AE (+0x4) / 0x100012B5 | occupant filter functor [LINUX-HINT cSCNOccFilterBase]; heap temp in 0x10005ee7/0x10006194 | not seen | single-thread / not hit |
| SCENARIO.DLL | 0x1001A31C | 0x100012AE (+0x4) / 0x100012B5 | base vtable of 0x1001A308 | not seen | single-thread / not hit |
| SCENARIO.DLL | 0x1001A6E8 | 0x100012AE (+0x4) / 0x1000C9A7 | layer algorithm object (IID 0x406c6f77), held by the layer | main (24 calls, 10 objs, 0 multi-thread, max 0 switches) | single-thread |
| SIMADV.DLL | 0x10030614 | 0x1000B606 (+0x50) / 0x1000B60D | advisor record, created via 0x100089e7/0x10008ef2 | main (959 calls, 378 objs, 0 multi-thread, max 0 switches) | single-thread |
| SIMDIRT.DLL | 0x100207D0 | 0x1001B9BF (+0x4) / 0x1001DAA9 | data-view adapter (id 0x2711) | main (22 calls, 6 objs, 0 multi-thread, max 0 switches) | single-thread |
| SIMDIRT.DLL | 0x10021104 | 0x1001B9BF (+0x4) / 0x1001DAA9 | adapter base | not seen | single-thread / not hit |
| SIMDSTR.DLL | 0x10032464 | 0x10005674 (+0x4) / 0x1000567B | functor, fire manager member | main+sim (1861 calls, 4 objs, 1 multi-thread, max 1 switches) | single-thread at a time (handoff only) |
| SIMDSTR.DLL | 0x10032478 | 0x10005674 (+0x4) / 0x1000567B | base of 0x10032464 | not seen | single-thread / not hit |
| SIMDSTR.DLL | 0x100325A0 | 0x10007661 (+0x10) / 0x10008DC8 | cSC3DisasterLayer [LINUX-HINT]; GZ listener (7 ids, Init 0x1000857d), lock at layer+0xe0 | main (142 calls, 5 objs, 0 multi-thread, max 0 switches) | single-thread |
| SIMDSTR.DLL | 0x100326B0 | 0x10009884 (+0x4) / 0x100098C1 | disaster-layer algorithm object | main (12 calls, 5 objs, 0 multi-thread, max 0 switches) | single-thread |
| SIMDSTR.DLL | 0x100326D8 | 0x10009884 (+0x4) / 0x100098C1 | disaster-layer algorithm object | main (12 calls, 5 objs, 0 multi-thread, max 0 switches) | single-thread |
| SIMDSTR.DLL | 0x10032700 | 0x10009884 (+0x4) / 0x100098C1 | disaster-layer algorithm object | main (12 calls, 5 objs, 0 multi-thread, max 0 switches) | single-thread |
| SIMDSTR.DLL | 0x10032728 | 0x10009884 (+0x4) / 0x100098C1 | disaster-layer algorithm object | main (12 calls, 5 objs, 0 multi-thread, max 0 switches) | single-thread |
| SIMECO.DLL | 0x1001BF40 | 0x100185C7 (+0x4) / 0x100185CE | pollution data-view adapter | not seen | single-thread / not hit |
| SIMECO.DLL | 0x1001BFA0 | 0x100185C7 (+0x4) / 0x100185CE | pollution data-view adapter | not seen | single-thread / not hit |
| SIMECO.DLL | 0x1001C000 | 0x100185C7 (+0x4) / 0x100185CE | pollution data-view adapter | not seen | single-thread / not hit |
| SIMECO.DLL | 0x1001C060 | 0x100185C7 (+0x4) / 0x100185CE | pollution data-view adapter | not seen | single-thread / not hit |
| SIMECO.DLL | 0x1001C0C0 | 0x100185C7 (+0x4) / 0x100185CE | adapter base | not seen | single-thread / not hit |
| SIMECO.DLL | 0x1001CCA4 | 0x100185C7 (+0x4) / 0x100185CE | adapter base | not seen | single-thread / not hit |
| SIMGEOM.DLL | 0x10029210 | 0x10003567 (+0x4) / 0x1000356E | functor, local temp in 0x100032ca | not seen | single-thread / not hit |
| SIMGEOM.DLL | 0x10029224 | 0x10003567 (+0x4) / 0x1000356E | base functor, member of 0x1000fc80 owner | main+sim (1916729 calls, 430 objs, 190 multi-thread, max 1 switches) | single-thread at a time (handoff only) |
| SIMGEOM.DLL | 0x10029A94 | 0x10003567 (+0x4) / 0x1000356E | functor, temp in cSC3FloraLayer::Init | not seen | single-thread / not hit |
| SIMGEOM.DLL | 0x10029F70 | 0x10003567 (+0x4) / 0x1000356E | functor, member of 0x1000d290 owner | main (22 calls, 15 objs, 0 multi-thread, max 0 switches) | single-thread |
| SIMGEOM.DLL | 0x1002BB20 | 0x10014A99 (+0x10) / 0x10023E54 | COM pointer list (CLSID 0xda0ac02e) | not seen | single-thread / not hit |
| SIMINIT.DLL | 0x1002F528 | 0x10004E3B (+0x4) / 0x100062AD | cSC3CitySchemeMgr [LINUX-HINT], app manager | main (3 calls, 2 objs, 0 multi-thread, max 0 switches) | single-thread |
| SIMINIT.DLL | 0x1002F940 | 0x10004E3B (+0x4) / 0x1000C175 | QI 0x43271e76 object (gfx probe) | not seen | single-thread / not hit |
| SIMINIT.DLL | 0x1002FB44 | 0x1000C605 (+0x8) / 0x1000D3B3 | cSC3OccupantAttribCache [LINUX-HINT], one app instance | main (54 calls, 2 objs, 0 multi-thread, max 0 switches) | single-thread |
| SIMINIT.DLL | 0x1002FBDC | 0x1000CD67 (+0x4) / 0x1000CD6E | functor member | not seen | single-thread / not hit |
| SIMINIT.DLL | 0x1002FBF0 | 0x1000CD67 (+0x4) / 0x1000CD6E | functor base | not seen | single-thread / not hit |
| SIMINIT.DLL | 0x1002FC04 | 0x1000D68D (+0x10) / 0x1000D694 | iterator temp | main (8 calls, 4 objs, 0 multi-thread, max 0 switches) | single-thread |
| SIMMISC.DLL | 0x1003C4A0 | 0x1002E3F0 (+0x4) / 0x10034523 | data-view adapter (id 0x271c) | not seen | single-thread / not hit |
| SIMMISC.DLL | 0x10040F3C | 0x10019B3E (+0x74) / 0x10019B45 | cSC3OrdinanceLayer [LINUX-HINT]; listener on a manager, not the GZ server | main (192 calls, 5 objs, 0 multi-thread, max 0 switches) | single-thread |
| SIMMISC.DLL | 0x10041CA8 | 0x1002E3F0 (+0x4) / 0x10034523 | adapter base | not seen | single-thread / not hit |
| SIMRCI.DLL | 0x1004C808 | 0x1004288D (+0x4) / 0x10042894 | land-value data-view adapter | not seen | single-thread / not hit |
| SIMRCI.DLL | 0x1004C870 | 0x1004288D (+0x4) / 0x10042894 | data-view adapter | not seen | single-thread / not hit |
| SIMRCI.DLL | 0x1004CFFC | 0x1004288D (+0x4) / 0x10042894 | data-view adapter (id 0x2724) | not seen | single-thread / not hit |
| SIMRCI.DLL | 0x1004D388 | 0x100318C1 (+0x4) / 0x100318C8 | functor, owner+0x2b4 (0x100314f0) | main+sim (326360 calls, 5 objs, 4 multi-thread, max 2 switches) | single-thread at a time (handoff only) |
| SIMRCI.DLL | 0x1004D39C | 0x100318C1 (+0x4) / 0x100318C8 | functor member (0x100314f0) | main+sim (137125059 calls, 5 objs, 4 multi-thread, max 2 switches) | single-thread at a time (handoff only) |
| SIMRCI.DLL | 0x1004D3B0 | 0x100318C1 (+0x4) / 0x100318C8 | functor base | not seen | single-thread / not hit |
| SIMRCI.DLL | 0x1004D46C | 0x1004288D (+0x4) / 0x10042894 | data-view adapter (id 0x271b) | main (22 calls, 6 objs, 0 multi-thread, max 0 switches) | single-thread |
| SIMRCI.DLL | 0x1004DFA8 | 0x1004288D (+0x4) / 0x10042894 | adapter base | not seen | single-thread / not hit |
| SIMSERV.DLL | 0x1001ED08 | 0x1001A9E6 (+0x4) / 0x100192AD | crime data-view adapter | not seen | single-thread / not hit |
| SIMSERV.DLL | 0x1001F1AC | 0x1001A9E6 (+0x4) / 0x100192AD | data-view adapter (id 0x272d) | not seen | single-thread / not hit |
| SIMSERV.DLL | 0x1001F370 | 0x1001A9E6 (+0x4) / 0x100192AD | data-view adapter (id 0x272c) | not seen | single-thread / not hit |
| SIMSERV.DLL | 0x1001F5E4 | 0x1001A9E6 (+0x4) / 0x100192AD | data-view adapter (id 0x271e) | not seen | single-thread / not hit |
| SIMSERV.DLL | 0x1001FFFC | 0x1001A9E6 (+0x4) / 0x100192AD | adapter base | not seen | single-thread / not hit |
| SIMUI.DLL | 0x100AA110 | 0x100139B6 (+0x4) / 0x10090D1C | adapter-shaped UI object (new in 0x10050de2) | main (14 calls, 5 objs, 0 multi-thread, max 0 switches) | single-thread |
| SIMUI.DLL | 0x100AEF50 | 0x100139B6 (+0x4) / 0x10090D1C | its base | not seen | single-thread / not hit |
| SIMUTIL.DLL | 0x10020794 | 0x1001CC1C (+0x4) / 0x100053AE | power-layer algorithm object | main (12 calls, 5 objs, 0 multi-thread, max 0 switches) | single-thread |
| SIMUTIL.DLL | 0x10020848 | 0x1001CC1C (+0x4) / 0x1001CC23 | data-view adapter (id 0x2722) | not seen | single-thread / not hit |
| SIMUTIL.DLL | 0x10022AE0 | 0x1001CC1C (+0x4) / 0x1001CC23 | data-view adapter (id 0x2720) | not seen | single-thread / not hit |
| SIMUTIL.DLL | 0x10024130 | 0x1001CC1C (+0x4) / 0x1001CC23 | adapter base | not seen | single-thread / not hit |
| STRTSIM.DLL | 0x1002B95C | 0x10003310 (+0x8) / 0x1001607D | cSSStrtSimOccupant base [LINUX-HINT]; derived classes 0x1002AF90 0x1002C9BC 0x1002B7AC share its Release 0x1001607D | not seen | **RACE-PRONE** through its live derived classes (rank 3): Release 0x1001607D is shared |
| STRTSIM.DLL | 0x1002D018 | 0x1001E004 (+0x2c) / 0x1001E1DE | QI 0xc2d827e7 object, street-sim setup | main (10 calls, 10 objs, 0 multi-thread, max 0 switches) | single-thread |
| STRTSIM.DLL | 0x1002D080 | 0x10015599 (+0x4) / 0x1001E2C3 | QI 0xc2d827e7 object | not seen | single-thread / not hit |
| SimTransit.dll | 0x1001A678 | 0x1001499A (+0x4) / 0x100149A1 | data-view adapter (id 0x2715), UI-requested | not seen | single-thread / not hit |
| SimTransit.dll | 0x1001B5A0 | 0x1001499A (+0x4) / 0x100149A1 | adapter base | not seen | single-thread / not hit |



## Second pass: the 86 `<= 1` vtables (le1_refcount_vtables.txt)

The `<= 1` template was found after the first census, so its 86 vtables (29 DLLs) got their own census with the same
light CModule. Hooks: every distinct AddRef and Release body of the three lists, 201 in all.

| census | game | coverage |
|---|---|---|
| v2 | the v1 process continued | Europolis 1024 at speed 4, 20 min, an emergency dispatch, Load City -> 1024b. 456 M calls |
| v3 | fresh, census from the start | Europolis 1024 at speed 4, 9 min (376 M calls). The game died at the reload teardown **inside frida-agent.dll** (below) |
| v4 | fresh, census attached 2.5 min in | Europolis 1024 at speed 4, 3 min, -> 1024b reload (+4 min), -> Berlin (256), 2 min (309 M calls). Died later in the same way |

Total for the `<= 1` bodies: about 39 min of 1024 play, a 1024 -> 1024 reload twice, 1024 -> 256 once.

**Result.** Only 10 of the 86 vtables had live objects. Each one is listed itself; no object reached these bodies
through an unlisted derived vtable (`le1_live.py`, which resolves every observed live vtable's slots through the
thunks). One is new and race-prone: **SIMUI wrapper 0x100A8164 (rank 5)**. Every one of its 9 objects went game ->
sim -> game, two-way use by two live threads, the same pattern as the SCENARIO layer, at a low rate. It is fixed in the
same block under its own switch. The two resource classes (ranks 1 and 2) belong to this template too and were already
fixed. Of the rest, 2 are a load-time handoff, 5 game thread only, and 76 never hit. The 76 are mostly per-DLL framework
copies (`+0x10` count / slot 0x2c and `+0x20` / slot 0x74 in every DLL) whose objects did not show up in play.

**Probe hazard, fixed in the tool.** v3 and v4 both died with the same `frida-agent.dll+0xC4BE37` read at a region
boundary, with a TRAFFIC_MT worker frame on the stack, shortly after a city load. Neither fault is in game or mod code.
The cause was the census itself: every 30 s it walked every thread with `Thread.backtrace(FUZZY)` inside the process.
It now reads each thread's stack top from outside the process (TEB StackBase + ReadProcessMemory, `stack_tops` in
census.py). This was checked for 60 s on the final soak game with no fault. Related: sc3netmod's resource overlay
re-patches the KERNEL32 imports of every module on each module load, frida-agent included (132 modules at the v3
reload). That is harmless for the owner's game but worth knowing before attaching Frida to a modded game.

### All 86 `<= 1` vtables

| module | vtable | AddRef (+off) / Release (destroy slot) | family | threads seen (census v2-v4) | verdict |
|---|---|---|---|---|---|
| AUDIO.DLL | 0x10020258 | 0x100164C7 (+0x10) / 0x100164CE (0x2c) | framework class, one copy per DLL | not hit | not hit |
| AUDIO.DLL | 0x10021570 | 0x1001BD04 (+0x20) / 0x1001BD0B (0x74) | framework class, one copy per DLL (the COM director AddRef shares its body) | not hit | not hit |
| GIMEX.DLL | 0x10018278 | 0x10016F85 (+0x10) / 0x10016F8C (0x2c) | framework class, one copy per DLL | not hit | not hit |
| GZGraphicD.dll | 0x1001F024 | 0x1001C3FE (+0x10) / 0x1001C405 (0x2c) | framework class, one copy per DLL | not hit | not hit |
| GZResourceD.dll | 0x1001C308 | 0x1000A5FB (+0x10) / 0x100023C0 (0x2c) | framework class, one copy per DLL | not hit | not hit |
| GZResourceD.dll | 0x1001CB18 | 0x10015B03 (+0x4) / 0x1000B7C0 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| GZResourceD.dll | 0x1001CB34 | 0x10015B03 (+0x4) / 0x1000B7C0 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| GZResourceD.dll | 0x1001CCE8 | 0x10015B03 (+0x4) / 0x1000B7C0 (0x14) | resource object family (3-dword resource key at +0xc) | main (5 calls, 2 objs, 0 multi-thread, max 0 switches) | single-thread |
| GZResourceD.dll | 0x1001CD04 | 0x10015B03 (+0x4) / 0x1000B7C0 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| GZResourceD.dll | 0x1001CD48 | 0x10015B03 (+0x4) / 0x1000B7C0 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| GZResourceD.dll | 0x1001CED4 | 0x10015B03 (+0x4) / 0x1000B7C0 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| GZResourceD.dll | 0x1001CEF0 | 0x10015B03 (+0x4) / 0x1000B7C0 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| GZResourceD.dll | 0x1001D104 | 0x10015B03 (+0x4) / 0x1000B7C0 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| GZResourceD.dll | 0x1001D130 | 0x10015B03 (+0x4) / 0x1000B7C0 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| GZResourceD.dll | 0x1001D1F0 | 0x10015B03 (+0x4) / 0x1000B7C0 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| GZResourceD.dll | 0x1001D3F4 | 0x10015B03 (+0x4) / 0x1000B7C0 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| GZResourceD.dll | 0x1001D410 | 0x10015B03 (+0x4) / 0x1000B7C0 (0x14) | resource object family (3-dword resource key at +0xc) | main+sim (14566 calls, 77 objs, 6 multi-thread, max 5 switches) | RACE-PRONE (rank 2), fixed: res_refcount_gzres |
| GZResourceD.dll | 0x1001D42C | 0x10015B03 (+0x4) / 0x1000B7C0 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| GZResourceD.dll | 0x1001D68C | 0x10015B03 (+0x4) / 0x1000B7C0 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| GZResourceD.dll | 0x1001D6B8 | 0x10015B03 (+0x4) / 0x1000B7C0 (0x14) | resource object family (3-dword resource key at +0xc) | main (1062 calls, 14 objs, 0 multi-thread, max 0 switches) | single-thread |
| GZResourceD.dll | 0x1001D6D4 | 0x10015B03 (+0x4) / 0x1000B7C0 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| GZResourceD.dll | 0x1001D7C4 | 0x10015B03 (+0x4) / 0x1000B7C0 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| GZResourceD.dll | 0x1001D7F0 | 0x10015B03 (+0x4) / 0x1000B7C0 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| GZResourceD.dll | 0x1001D80C | 0x10015B03 (+0x4) / 0x1000B7C0 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| GZResourceD.dll | 0x1001DCE4 | 0x10015B03 (+0x4) / 0x10015B0A (0x24) | resource-manager class (GZResourceD / SIMBABLD) | main+sim (2953 calls, 2 objs, 1 multi-thread, max 1 switches) | handoff only |
| GZResourceD.dll | 0x1001E128 | 0x1001814D (+0x20) / 0x10018154 (0x74) | framework class, one copy per DLL (the COM director AddRef shares its body) | not hit | not hit |
| GZSOUNDD.DLL | 0x1000C318 | 0x10002431 (+0x10) / 0x10002438 (0x2c) | framework class, one copy per DLL | not hit | not hit |
| GZServiceD.dll | 0x10014358 | 0x100063F7 (+0x10) / 0x100063FE (0x2c) | framework class, one copy per DLL | not hit | not hit |
| GZServiceD.dll | 0x10014DC4 | 0x10011DA9 (+0x20) / 0x10011DB0 (0x74) | framework class, one copy per DLL (the COM director AddRef shares its body) | not hit | not hit |
| GZTOOLSD.DLL | 0x1000918C | 0x10005F1C (+0x10) / 0x10005F23 (0x2c) | framework class, one copy per DLL | not hit | not hit |
| GZWIND.DLL | 0x1002AB40 | 0x10023411 (+0x10) / 0x10023418 (0x2c) | framework class, one copy per DLL | not hit | not hit |
| GZWIND.DLL | 0x1002E290 | 0x10027149 (+0x20) / 0x10027150 (0x74) | framework class, one copy per DLL (the COM director AddRef shares its body) | not hit | not hit |
| GZWWWD.DLL | 0x100213D8 | 0x1000A9A7 (+0x10) / 0x1000A9AE (0x2c) | framework class, one copy per DLL | not hit | not hit |
| GZWWWD.DLL | 0x10021908 | 0x1000A0FE (+0x20) / 0x1000DA87 (0x74) | framework class, one copy per DLL (the COM director AddRef shares its body) | not hit | not hit |
| MaxisAddOn.dll | 0x1000324C | 0x10002136 (+0x10) / 0x1000213D (0x2c) | framework class, one copy per DLL | not hit | not hit |
| SCENARIO.DLL | 0x1001A3D8 | 0x100101C1 (+0x10) / 0x100101C8 (0x2c) | framework class, one copy per DLL | not hit | not hit |
| SCENARIO.DLL | 0x1001AA80 | 0x1000FAC6 (+0x20) / 0x10013D1B (0x74) | framework class, one copy per DLL (the COM director AddRef shares its body) | not hit | not hit |
| SIMADV.DLL | 0x100301A8 | 0x1002507E (+0x10) / 0x10025085 (0x2c) | framework class, one copy per DLL | main+sim (742 calls, 135 objs, 15 multi-thread, max 1 switches) | handoff only |
| SIMADV.DLL | 0x100317D8 | 0x100287B1 (+0x20) / 0x100287B8 (0x74) | framework class, one copy per DLL (the COM director AddRef shares its body) | not hit | not hit |
| SIMBABLD.DLL | 0x120692E0 | 0x12055FED (+0x10) / 0x12055FF4 (0x2c) | framework class, one copy per DLL | not hit | not hit |
| SIMBABLD.DLL | 0x1206BF70 | 0x12059E64 (+0x4) / 0x12050943 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| SIMBABLD.DLL | 0x1206BF8C | 0x12059E64 (+0x4) / 0x12050943 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| SIMBABLD.DLL | 0x1206BFA8 | 0x12059E64 (+0x4) / 0x12050943 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| SIMBABLD.DLL | 0x1206C128 | 0x12059E64 (+0x4) / 0x12050943 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| SIMBABLD.DLL | 0x1206C144 | 0x12059E64 (+0x4) / 0x12050943 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| SIMBABLD.DLL | 0x1206C204 | 0x12059E64 (+0x4) / 0x12050943 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| SIMBABLD.DLL | 0x1206CC34 | 0x12059E64 (+0x4) / 0x12059E6B (0x24) | resource-manager class (GZResourceD / SIMBABLD) | not hit | not hit |
| SIMBABLD.DLL | 0x1206CDC8 | 0x12058E3C (+0x20) / 0x1205C3C5 (0x74) | framework class, one copy per DLL (the COM director AddRef shares its body) | not hit | not hit |
| SIMCITY.DLL | 0x1001378C | 0x100098AE (+0x10) / 0x100098B5 (0x2c) | framework class, one copy per DLL | main (2 calls, 1 objs, 0 multi-thread, max 0 switches) | single-thread |
| SIMDIRT.DLL | 0x10020770 | 0x1001AE08 (+0x10) / 0x1001AE0F (0x2c) | framework class, one copy per DLL | not hit | not hit |
| SIMDSTR.DLL | 0x1003232C | 0x10007661 (+0x10) / 0x10025643 (0x2c) | framework class, one copy per DLL | not hit | not hit |
| SIMDSTR.DLL | 0x10033E4C | 0x100236CC (+0x20) / 0x10029CD2 (0x74) | framework class, one copy per DLL (the COM director AddRef shares its body) | not hit | not hit |
| SIMECO.DLL | 0x1001B130 | 0x1000E760 (+0x10) / 0x1000E767 (0x2c) | framework class, one copy per DLL | not hit | not hit |
| SIMECO.DLL | 0x1001C5DC | 0x10012E9D (+0x20) / 0x10012EA4 (0x74) | framework class, one copy per DLL (the COM director AddRef shares its body) | not hit | not hit |
| SIMGEOM.DLL | 0x100291A0 | 0x10014A99 (+0x10) / 0x10014AA0 (0x2c) | framework class, one copy per DLL | not hit | not hit |
| SIMGEOM.DLL | 0x1002AE74 | 0x1001A2AF (+0x20) / 0x1001AFD9 (0x74) | framework class, one copy per DLL (the COM director AddRef shares its body) | not hit | not hit |
| SIMINIT.DLL | 0x1002F230 | 0x1000D68D (+0x10) / 0x1001F795 (0x2c) | framework class, one copy per DLL | not hit | not hit |
| SIMINIT.DLL | 0x10031430 | 0x1001FF93 (+0x20) / 0x10025247 (0x74) | framework class, one copy per DLL (the COM director AddRef shares its body) | not hit | not hit |
| SIMMISC.DLL | 0x1003C434 | 0x1002AD53 (+0x10) / 0x1002AD5A (0x2c) | framework class, one copy per DLL | not hit | not hit |
| SIMMISC.DLL | 0x100419F0 | 0x10030A1E (+0x20) / 0x10030A25 (0x74) | framework class, one copy per DLL (the COM director AddRef shares its body) | not hit | not hit |
| SIMNTWRK.DLL | 0x10029234 | 0x1001EEB2 (+0x10) / 0x1001EEB9 (0x2c) | framework class, one copy per DLL | not hit | not hit |
| SIMNTWRK.DLL | 0x1002CBF0 | 0x1002048F (+0x20) / 0x10020496 (0x74) | framework class, one copy per DLL (the COM director AddRef shares its body) | not hit | not hit |
| SIMRCI.DLL | 0x1004B140 | 0x10036F79 (+0x10) / 0x10036F80 (0x2c) | framework class, one copy per DLL | not hit | not hit |
| SIMRCI.DLL | 0x1004D868 | 0x1003B9EB (+0x20) / 0x1003B9F2 (0x74) | framework class, one copy per DLL (the COM director AddRef shares its body) | not hit | not hit |
| SIMSERV.DLL | 0x1001E140 | 0x100106F9 (+0x10) / 0x10010700 (0x2c) | framework class, one copy per DLL | not hit | not hit |
| SIMSERV.DLL | 0x1001F938 | 0x10014159 (+0x20) / 0x10014160 (0x74) | framework class, one copy per DLL (the COM director AddRef shares its body) | not hit | not hit |
| SIMSPR.DLL | 0x10062304 | 0x1004F11B (+0x10) / 0x1004F122 (0x2c) | framework class, one copy per DLL | not hit | not hit |
| SIMSPR.DLL | 0x100686A8 | 0x100561C4 (+0x20) / 0x100561CB (0x74) | framework class, one copy per DLL (the COM director AddRef shares its body) | not hit | not hit |
| SIMSPR.DLL | 0x10068934 | 0x1005982A (+0x4) / 0x10059831 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| SIMSPR.DLL | 0x10068950 | 0x1005982A (+0x4) / 0x10059831 (0x14) | resource object family (3-dword resource key at +0xc) | main+sim (3036 calls, 56 objs, 5 multi-thread, max 1 switches) | RACE-PRONE (rank 1; census v1 saw up to 11 switches with the sprite loader), fixed: res_refcount_simspr |
| SIMSPR.DLL | 0x1006896C | 0x1005982A (+0x4) / 0x10059831 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| SIMSPR.DLL | 0x10068AE8 | 0x1005982A (+0x4) / 0x10059831 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| SIMSPR.DLL | 0x10068B04 | 0x1005982A (+0x4) / 0x10059831 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| SIMSPR.DLL | 0x10068BC4 | 0x1005982A (+0x4) / 0x10059831 (0x14) | resource object family (3-dword resource key at +0xc) | not hit | not hit |
| SIMUI.DLL | 0x100A2410 | 0x100842B0 (+0x10) / 0x100842B7 (0x2c) | framework class, one copy per DLL | main (4 calls, 2 objs, 0 multi-thread, max 0 switches) | single-thread |
| SIMUI.DLL | 0x100A811C | 0x100139B6 (+0x4) / 0x10043BA9 (0x44) | SIMUI wrapper object (0x14 bytes, ctor 0x10043d52) | main (48 calls, 24 objs, 0 multi-thread, max 0 switches) | single-thread |
| SIMUI.DLL | 0x100A8164 | 0x100139B6 (+0x4) / 0x10043BA9 (0x44) | SIMUI wrapper object (0x14 bytes, ctor 0x10043d52) | main+sim (84 calls, 9 objs, 9 multi-thread, max 2 switches) | RACE-PRONE (rank 5, rare), fixed: le1_refcount_simui |
| SIMUI.DLL | 0x100AED1C | 0x100849EB (+0x20) / 0x1008BEA1 (0x74) | framework class, one copy per DLL (the COM director AddRef shares its body) | not hit | not hit |
| SIMUTIL.DLL | 0x100201C8 | 0x10013402 (+0x10) / 0x10013409 (0x2c) | framework class, one copy per DLL | not hit | not hit |
| SIMUTIL.DLL | 0x10023AB0 | 0x10017C14 (+0x20) / 0x10017C1B (0x74) | framework class, one copy per DLL (the COM director AddRef shares its body) | not hit | not hit |
| STRTSIM.DLL | 0x1002A5D0 | 0x10021980 (+0x10) / 0x10021987 (0x2c) | framework class, one copy per DLL | not hit | not hit |
| STRTSIM.DLL | 0x1002D4D8 | 0x100244CB (+0x20) / 0x10025664 (0x74) | framework class, one copy per DLL (the COM director AddRef shares its body) | not hit | not hit |
| SimTransit.dll | 0x1001A518 | 0x1000E91F (+0x10) / 0x1000E926 (0x2c) | framework class, one copy per DLL | not hit | not hit |
| SimTransit.dll | 0x1001B304 | 0x10011A38 (+0x20) / 0x10011A3F (0x74) | framework class, one copy per DLL (the COM director AddRef shares its body) | not hit | not hit |
| simvariables.dll | 0x1000B2C8 | 0x10003419 (+0x10) / 0x10003420 (0x2c) | framework class, one copy per DLL | not hit | not hit |
| simvariables.dll | 0x1000BA08 | 0x10003F96 (+0x20) / 0x10007CA3 (0x74) | framework class, one copy per DLL (the COM director AddRef shares its body) | not hit | not hit |

## Milestone 2: fix (sc3perf RES_REFCOUNT) and soak

**Fix.** New sc3perf block RES_REFCOUNT (worktree `re/harness/src/sc3perf.c`, after SIMGROUP_REFCOUNT). It makes the 4
RACE-PRONE classes atomic with the same results. No lock is added. Each module is byte-checked against the shipped DLL
and left alone if it differs. Armed 0.1 to 0.25 s after start, before any city:

| perf.ini switch (default 1) | bodies made atomic |
|---|---|
| `res_refcount_simspr` | SIMSPR AddRef 0x1005982a, Release 0x10059831 (`<= 1` destroys through vt+0x14) |
| `res_refcount_gzres` | GZResourceD AddRef 0x10015b03, Release 0x1000b7c0 (same template) |
| `strtsim_refcount_ecx` | STRTSIM Release 0x1001607d (if-nonzero, vt+0x120). Its AddRef 0x10003310 was already atomic through `strtsim_refcount_all` |
| `scenario_refcount` | SCENARIO AddRef 0x10005b6f, Release 0x100099a1 (the STRTSIM esi template: dtor 0x100067f0 + delete) |
| `le1_refcount_simui` (second pass) | SIMUI AddRef 0x100139b6, Release 0x10043ba9 (`<= 1`, vt+0x44) |

Log lines: `RES_REFCOUNT> ... atomic` (5 of them), or `... differ from shipped - not patched`. Environment overrides:
`SC3PERF_RES_REFCOUNT_SIMSPR=0` etc., the same as every sc3perf switch.

**Soak, first build (4 switches)** (test tree, all 8 mods built from the worktree, windowed, maximized 3840x1984, HUD scale 3.3, speed 4, no
probe attached). Faults are counted the reload1024 way. First-chance access violations inside KERNEL32 are not
counted: +0x1CA9E during the Load City dialog, and +0x2CF80 called from the NVIDIA driver nvd3dum, one per load. Both
appear in the reload1024 logs, before this change.

| run | sequence | result |
|---|---|---|
| s1 (one game) | Europolis 1024, 10 min | alive, the date ran 1/1/2100 -> 6/6/2103, 0 faults |
| s1 | Load City -> 1024b, -> 1024, -> 1024b (3 reloads, 2 min play after each) | each load 6 to 9 s, 0 faults |
| s1 | -> Big One (256; the dialog had switched back to MAIN\Cities), -> Farmsville (192), -> Europolis 1024 | 0 faults; see the slow start below |
| abOff (switches off) | Farmsville -> Europolis 1024 | first second at >= 10 fps 4 s after the teardown; next 180 s mean 35.2 fps; 0 faults |
| abOn (switches on, same game continues below) | Farmsville -> Europolis 1024 | 5 s; next 180 s mean 41.4 fps; 0 faults |
| abOn | -> Berlin (256) -> Europolis 1024 | Berlin 4 s, 59.0 fps; 1024 21 s, 41.9 fps over 120 s; 1.59 M background trips, 0 faulted; 0 faults |

Total: 3 games, 10 loads, 0 faults, 0 crashes, no freeze.

**Slow start seen once, not tied to the change.** s1's last load (Farmsville -> Europolis 1024, the 6th load of a 37-min
game, 1059 MB) presented about 0 fps for about 140 s while paused. It then ran at 0 to 60 fps for a few minutes, and was
back at 30 to 60 fps 7.5 min after the load. The date kept advancing and the process stayed responsive. The same load in
fresh games shows no difference between the switches: off 4 s, on 5 s. The patched bodies carry about 50 calls a second
in total in the census, so an atomic instruction there cannot cost seconds. Not investigated further. It is a candidate
for the owner's next hand test after many loads in one session.

**Final soak, all 5 switches (run f1, one game, no probe).** Every load walked the full folder path and its selection
was frame-dumped and checked (`owner_shots/6_final_soak_load_selections.png`: 1024b, 1024, 1024b, Berlin, 1024, all from
the test tree).

| step | result |
|---|---|
| patches | 5 `RES_REFCOUNT> ... atomic` lines, 0.11 to 0.35 s after start |
| Europolis 1024, maximized, speed 4, 10 min | PASS, 0 faults, mean 35.7 fps (112 s below 10, all in the first minutes of the city) |
| reload -> 1024b | PASS, 6 s to the first second at >= 10 fps, then 32.8 fps over 2 min |
| reload -> 1024 | PASS, 5 s, then 40.2 fps |
| reload -> 1024b | PASS, 4 s, then 41.1 fps |
| 1024 -> Berlin (256) | PASS, 3 s, then 58.5 fps |
| Berlin -> 1024 | PASS, 4 s, then 39.7 fps |
| end | alive, 0 faults outside the KERNEL32 first-chance reads, 6.57 M background trips with 0 faulted, 1024 MB |

The slow start seen once in s1 (below) did not recur in this run's 5 loads.

Pictures (`owner_shots/`):
- `1_europolis1024_10min_speed4.png`: s1 after 10 min. The frame dump itself drops that second to 2 fps.
- `2_after_third_1024_reload.png`: s1 after the third 1024 reload.
- `3_berlin_then_europolis1024.png`: abOn, Berlin -> Europolis 1024, 2 min after the load.
- `4_final_soak_1024_10min.png`, `5_final_soak_berlin_then_1024.png`: final soak f1.
- `6_final_soak_load_selections.png`: the 5 Load City selections of f1.
