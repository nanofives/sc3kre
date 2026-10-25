# ladder: confidence ladder update from the 2026-10-23..25 work (child/ladder, 2026-10-25)

Owner request: "update the confidence ladder with all the things you have developed". The ladder is `functions.csv`.

**Result: 336 rows changed, 336 verified.** Every edit went through `py -3.12 re/scripts/tracker.py batch --legacy-names
--apply`, keyed on (module, rva). The tracker checked a blast radius of 336 records. `git diff -U0 functions.csv` against
main c9602a3 also shows 336 lines out and 336 in. A second batch of 3 rows (`ladder_batch_fix_subsystem.tsv`) then set the
`font-render` subsystem on three of those C1 rows, so the total of changed records stayed 336.

| set | source | rows |
|---|---|---|
| primary | the 14 streams of 10-23..25: reload1024, refaudit, avflow, bventry, sprcrash, zoomcrash, uiaudit, verdatos, minimap, uitoggle, perfscale, spr47b70, loader2, rc_1023, plus HUD_SCALE.md / RESIZABLE_WINDOW.md and the memory notes they cite | 278 |
| secondary | other `verify/*/RESULTS.md` committed 2026-10-01 or later, rows still at C0 / C1 with a clear description or runtime witness | 58 |

## Rules applied

- **C2:** the code was read and the behaviour described mechanically, with a `sc3_<subsystem>_<verb>_<noun>` name.
  - This includes the plain AddRef / Release bodies matched by the byte-template scans (`verify/reload1024/plain_refcount_vtables*.txt`, `verify/refaudit/le1_refcount_vtables.txt`).
- **C3:** a runtime witness of the described behaviour, cited by verify path. Examples:
  - the refaudit per-object census saw the body live;
  - a Frida probe or hook;
  - an A/B or trace in the cited RESULTS.
- **C4:** only where a fix that depends on the function was measured against a crash rate:
  - STRTSIM producer AddRef / Release 0x10010569 / 0x100110fc: 5 of 18 loads crashed before, 0 of 24 after.
  - SIMCITY sim group AddRef / Release 0x10010d0d / 0x10010d14: 8 of 13 runs died before, 0 of 8 after.
- **Kept at C3 with the measurement in the notes**, because no before/after crash rate isolates them:
  - the RES_REFCOUNT classes, made atomic with a clean soak;
  - GZResourceD 0x1001816f and SIMSPR 0x10044471. The held-file fix took them from 3 of 3 crashed to 6 of 6 alive, but that survival comes mostly from the SIMSPR retry and skip.
- **Nothing was lowered, and no existing name or subsystem was replaced.** Notes are appended, tagged `[ladder 2026-10-25]`. 12 rows got notes only, at the level they already had.
- **Two new subsystem labels** (orchestrator call):
  - `gzcom-refcount`: AddRef / Release bodies and their thunks across 26 DLLs.
  - `font-render`: the GZServiceD glyph draw and its three text loops.
- **Mechanical names where no class is known:**
  - `_fwobject` (+0x10 framework class);
  - `_comdirector` (+0x20 AddRef, shared with the per-DLL cRZCOMDllDirector);
  - `_fwobject20`;
  - `_vt<low vtable digits>` (the 12 unnamed STRTSIM Releases).

## Not changed

- **No row exists.** These are not Ghidra function entries:
  - SIMSPR 0x100589c6 and GZResourceD 0x1000ffdb (thunks on the resource Release paths);
  - SIMINIT 0x1001fe55 (`GZDllGetGZCOMDirector`).
- **Secondary cites left out:**
  - stack frames that are only cited as frames of the Frida deadlock;
  - "read for this task" cites with no description (multitile, roundabout3/4);
  - SimTransit 0x100086e7, SIMNTWRK 0x10009c65, STRTSIM 0x1001e673, and the SIMSPR anchor chain 0x100159e2 / 0x1005ad34 / 0x100014e7;
  - UV.DLL, which is not a tracker module;
  - two minimap clamps whose module is not given.
- **66 rows already at C2 in the secondary sweep** carry runtime evidence that could raise them to C3. They are out of this task's scope; the list is in `tools/secondary_cites.tsv` (evidence RUNTIME).

## Confidence counts, whole file

| level | before | after | change |
|---|---|---|---|
| C0 | 38,439 | 38,150 | -289 |
| C1 | 5,088 | 5,080 | -8 |
| C2 | 1,833 | 2,003 | +170 |
| C3 | 298 | 421 | +123 |
| C4 | 11 | 15 | +4 |

## Per module (only modules with a change; "a -> b" = before -> after)

| module | rows changed | C0 | C1 | C2 | C3 | C4 |
|---|---|---|---|---|---|---|
| AUDIO.DLL | 6 | 891 -> 885 | 120 | 24 -> 28 | 0 -> 2 | 0 |
| GIMEX.DLL | 2 | 504 -> 502 | 24 | 0 -> 2 | 0 | 0 |
| GZGraphicD.dll | 3 | 774 -> 771 | 52 | 15 -> 18 | 5 | 2 |
| GZResourceD.dll | 13 | 1,150 -> 1,140 | 155 -> 154 | 14 -> 19 | 7 -> 13 | 4 |
| GZSOUNDD.DLL | 2 | 457 -> 455 | 44 | 0 -> 2 | 0 | 0 |
| GZServiceD.dll | 11 | 615 -> 604 | 64 -> 68 | 0 -> 5 | 0 -> 2 | 0 |
| GZTOOLSD.DLL | 2 | 390 -> 388 | 53 | 0 -> 2 | 0 | 0 |
| GZWWWD.dll | 4 | 796 -> 792 | 83 | 25 -> 29 | 0 | 0 |
| GZWinD.dll | 6 | 1,621 -> 1,615 | 113 | 29 -> 34 | 1 -> 2 | 0 |
| MaxisAddOn.dll | 2 | 73 -> 71 | 11 | 0 -> 2 | 0 | 0 |
| SC3U.exe | 15 | 6,128 -> 6,113 | 605 -> 616 | 95 -> 97 | 10 -> 12 | 0 |
| SCENARIO.DLL | 13 | 730 -> 717 | 114 | 66 -> 75 | 0 -> 4 | 0 |
| SIMADV.DLL | 12 | 974 -> 962 | 135 | 40 -> 42 | 1 -> 11 | 0 |
| SIMBABLD.DLL | 7 | 2,187 -> 2,180 | 206 | 36 -> 43 | 2 | 0 |
| SIMCITY.DLL | 20 | 544 -> 532 | 196 -> 189 | 85 -> 95 | 38 -> 45 | 0 -> 2 |
| SIMDIRT.DLL | 5 | 577 -> 573 | 165 -> 164 | 26 -> 28 | 21 -> 24 | 0 |
| SIMDSTR.DLL | 19 | 1,670 -> 1,652 | 167 | 149 -> 161 | 0 -> 6 | 0 |
| SIMECO.DLL | 7 | 765 -> 758 | 170 | 72 -> 78 | 37 -> 38 | 0 |
| SIMGEOM.DLL | 9 | 1,435 -> 1,426 | 275 | 132 -> 139 | 18 -> 20 | 0 |
| SIMINIT.DLL | 12 | 1,366 -> 1,354 | 198 | 26 -> 32 | 4 -> 10 | 0 |
| SIMMISC.DLL | 8 | 1,250 -> 1,242 | 268 | 142 -> 148 | 21 -> 23 | 0 |
| SIMNTWRK.DLL | 11 | 952 -> 941 | 162 | 128 -> 134 | 6 -> 11 | 0 |
| SIMRCI.DLL | 8 | 1,705 -> 1,697 | 287 | 160 -> 164 | 52 -> 56 | 0 |
| SIMSERV.DLL | 11 | 904 -> 895 | 143 | 92 -> 97 | 3 -> 7 | 0 |
| SIMSPR.DLL | 37 | 2,662 -> 2,645 | 410 -> 397 | 71 -> 86 | 40 -> 55 | 5 |
| SIMUI.DLL | 25 | 3,700 -> 3,679 | 379 -> 378 | 136 -> 147 | 4 -> 15 | 0 |
| SIMUTIL.DLL | 7 | 1,005 -> 998 | 143 | 93 -> 98 | 17 -> 19 | 0 |
| SIMVARIABLES.DLL | 4 | 418 -> 414 | 57 | 35 -> 39 | 0 | 0 |
| STRTSIM.DLL | 40 | 1,541 -> 1,502 | 162 | 57 -> 72 | 3 -> 25 | 0 -> 2 |
| SimTransit.dll | 15 | 655 -> 647 | 127 | 85 -> 87 | 8 -> 14 | 0 |

## Every changed row

The full notes are in `functions.csv` and `ladder_plan.tsv`. "pri" = primary, "sec" = secondary.

| set | module | rva | before | after | name | evidence (see the row notes) |
|---|---|---|---|---|---|---|
| pri | SCENARIO.DLL | 0x10005b6f | C0 | C3 | sc3_scenario_addref_layer | verify/refaudit, verify/reload1024/plain_refcount_vtables.txt |
| pri | SCENARIO.DLL | 0x100099a1 | C0 | C3 | sc3_scenario_release_layer | verify/refaudit, verify/reload1024/plain_refcount_vtables.txt |
| pri | SIMADV.DLL | 0x100064fd | C0 | C3 | sc3_simadv_addref_msgrecord | verify/refaudit, verify/reload1024/plain_refcount_vtables.txt |
| pri | SIMADV.DLL | 0x10006504 | C0 | C3 | sc3_simadv_release_msgrecord | verify/refaudit, verify/reload1024/plain_refcount_vtables.txt |
| pri | SIMADV.DLL | 0x10011702 | C0 | C3 | sc3_simadv_addref_record5c | verify/refaudit, verify/reload1024/plain_refcount_vtables.txt |
| pri | SIMADV.DLL | 0x10011709 | C0 | C3 | sc3_simadv_release_record5c | verify/refaudit, verify/reload1024/plain_refcount_vtables.txt |
| pri | SIMADV.DLL | 0x1001c97a | C0 | C3 | sc3_simadv_addref_record58 | verify/refaudit, verify/reload1024/plain_refcount_vtables.txt |
| pri | SIMADV.DLL | 0x1001c981 | C0 | C3 | sc3_simadv_release_record58 | verify/refaudit, verify/reload1024/plain_refcount_vtables.txt |
| pri | SIMDSTR.DLL | 0x1000652f | C0 | C2 | sc3_dstr_addref_fireinstance | verify/reload1024/plain_refcount_vtables.txt |
| pri | SIMDSTR.DLL | 0x100066f0 | C0 | C2 | sc3_dstr_release_fireinstance | verify/reload1024/plain_refcount_vtables.txt |
| pri | SIMDSTR.DLL | 0x1000e087 | C0 | C2 | sc3_dstr_addref_instance | verify/reload1024/plain_refcount_vtables.txt |
| pri | SIMDSTR.DLL | 0x1000e4eb | C0 | C2 | sc3_dstr_release_riotinstance | verify/reload1024/plain_refcount_vtables.txt |
| pri | SIMDSTR.DLL | 0x10013a81 | C0 | C2 | sc3_dstr_addref_tornadoinstance | verify/reload1024/plain_refcount_vtables.txt |
| pri | SIMDSTR.DLL | 0x10014090 | C0 | C2 | sc3_dstr_release_tornadoinstance | verify/reload1024/plain_refcount_vtables.txt |
| pri | SIMDSTR.DLL | 0x10016a93 | C0 | C2 | sc3_dstr_addref_toxiccloud | verify/reload1024/plain_refcount_vtables.txt |
| pri | SIMDSTR.DLL | 0x1001715c | C0 | C2 | sc3_dstr_release_toxiccloud | verify/reload1024/plain_refcount_vtables.txt |
| pri | SIMDSTR.DLL | 0x100214f6 | C0 | C2 | sc3_dstr_release_paradeinstance | verify/reload1024/plain_refcount_vtables.txt |
| pri | SIMGEOM.DLL | 0x1001474e | C0 | C2 | sc3_simgeom_addref_demolishtest | verify/reload1024/plain_refcount_vtables.txt |
| pri | SIMGEOM.DLL | 0x10004dab | C0 | C2 | sc3_simgeom_release_demolishtest | verify/reload1024/plain_refcount_vtables.txt |
| pri | SIMSPR.DLL | 0x1005982a | C0 | C3 | sc3_spr_addref_resource | verify/refaudit, verify/refaudit/le1_refcount_vtables.txt, verify/reload1024/plain_refcount_vtables.txt |
| pri | SIMSPR.DLL | 0x10041564 | C0 | C3 | sc3_spr_release_comclass | verify/refaudit, verify/reload1024/plain_refcount_vtables.txt |
| pri | STRTSIM.DLL | 0x10003310 | C0 | C3 | sc3_strtsim_addref_object08 | verify/refaudit, verify/reload1024/plain_refcount_vtables.txt, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | STRTSIM.DLL | 0x10003b58 | C0 | C3 | sc3_strtsim_release_vt2a558 | verify/refaudit, verify/reload1024/plain_refcount_vtables.txt |
| pri | STRTSIM.DLL | 0x10005f32 | C0 | C3 | sc3_strtsim_release_vt2a92c | verify/refaudit, verify/reload1024/plain_refcount_vtables.txt |
| pri | STRTSIM.DLL | 0x10010569 | C0 | C4 | sc3_strtsim_addref_crowdproducer | verify/refaudit, verify/reload1024, verify/reload1024/plain_refcount_vtables.txt |
| pri | STRTSIM.DLL | 0x100076a8 | C0 | C3 | sc3_strtsim_release_layerobj104 | verify/refaudit, verify/reload1024, verify/reload1024/plain_refcount_vtables.txt |
| pri | STRTSIM.DLL | 0x10015599 | C0 | C3 | sc3_strtsim_addref_object04 | verify/refaudit, verify/reload1024/plain_refcount_vtables.txt, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | STRTSIM.DLL | 0x1000934f | C0 | C3 | sc3_strtsim_release_vt2b550 | verify/refaudit, verify/reload1024/plain_refcount_vtables.txt |
| pri | STRTSIM.DLL | 0x10010111 | C0 | C3 | sc3_strtsim_release_vt2c328 | verify/refaudit, verify/reload1024/plain_refcount_vtables.txt |
| pri | STRTSIM.DLL | 0x100110fc | C0 | C4 | sc3_strtsim_release_crowdproducer | verify/refaudit, verify/reload1024, verify/reload1024/plain_refcount_vtables.txt |
| pri | STRTSIM.DLL | 0x10021980 | C0 | C3 | sc3_strtsim_addref_object10 | verify/refaudit, verify/refaudit/le1_refcount_vtables.txt, verify/reload1024/plain_refcount_vtables.txt |
| pri | STRTSIM.DLL | 0x1001413a | C0 | C3 | sc3_strtsim_release_vt2c600 | verify/refaudit, verify/reload1024/plain_refcount_vtables.txt |
| pri | STRTSIM.DLL | 0x10015613 | C0 | C3 | sc3_strtsim_release_vt2c7c8 | verify/refaudit, verify/reload1024/plain_refcount_vtables.txt |
| pri | STRTSIM.DLL | 0x100166df | C0 | C3 | sc3_strtsim_release_vt2c840 | verify/refaudit, verify/reload1024/plain_refcount_vtables.txt |
| pri | STRTSIM.DLL | 0x10017158 | C0 | C3 | sc3_strtsim_release_vt2c8cc | verify/refaudit, verify/reload1024/plain_refcount_vtables.txt |
| pri | STRTSIM.DLL | 0x10017a01 | C0 | C3 | sc3_strtsim_release_vt2cb28 | verify/refaudit, verify/reload1024/plain_refcount_vtables.txt |
| pri | STRTSIM.DLL | 0x1001dd1a | C0 | C3 | sc3_strtsim_release_vt2cf40 | verify/refaudit, verify/reload1024/plain_refcount_vtables.txt |
| pri | STRTSIM.DLL | 0x1001dfc2 | C0 | C2 | sc3_strtsim_release_vt2cfa8 | verify/reload1024/plain_refcount_vtables.txt |
| pri | STRTSIM.DLL | 0x1001f229 | C0 | C3 | sc3_strtsim_release_vt2d1d0 | verify/refaudit, verify/reload1024/plain_refcount_vtables.txt |
| pri | AUDIO.DLL | 0x10011277 | C0 | C3 | sc3_audio_addref_audioinfo | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | AUDIO.DLL | 0x1001127e | C0 | C3 | sc3_audio_release_audioinfo | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | GZResourceD.dll | 0x10015b03 | C0 | C3 | sc3_gzres_addref_resource | verify/refaudit, verify/refaudit/le1_refcount_vtables.txt, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | GZResourceD.dll | 0x100039f1 | C0 | C3 | sc3_gzres_release_tokenrecord | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SCENARIO.DLL | 0x100012ae | C0 | C3 | sc3_scenario_addref_functor | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SCENARIO.DLL | 0x100012b5 | C0 | C2 | sc3_scenario_release_occfilter | verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SCENARIO.DLL | 0x1000c9a7 | C0 | C3 | sc3_scenario_release_layeralgo | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMADV.DLL | 0x1000b606 | C0 | C3 | sc3_simadv_addref_record50 | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMADV.DLL | 0x1000b60d | C0 | C3 | sc3_simadv_release_record50 | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMDIRT.DLL | 0x1001b9bf | C0 | C3 | sc3_dirt_addref_dataadapter | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMDIRT.DLL | 0x1001daa9 | C0 | C3 | sc3_dirt_release_dataadapter | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMDSTR.DLL | 0x10005674 | C0 | C3 | sc3_dstr_addref_firefunctor | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMDSTR.DLL | 0x1000567b | C0 | C3 | sc3_dstr_release_firefunctor | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMDSTR.DLL | 0x10007661 | C0 | C3 | sc3_dstr_addref_layer | verify/refaudit, verify/refaudit/le1_refcount_vtables.txt, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMDSTR.DLL | 0x10008dc8 | C0 | C3 | sc3_dstr_release_layer | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMDSTR.DLL | 0x10009884 | C0 | C3 | sc3_dstr_addref_layeralgo | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMDSTR.DLL | 0x100098c1 | C0 | C3 | sc3_dstr_release_layeralgo | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMECO.DLL | 0x100185c7 | C0 | C2 | sc3_simeco_addref_dataadapter | verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMECO.DLL | 0x100185ce | C0 | C2 | sc3_simeco_release_dataadapter | verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMGEOM.DLL | 0x10003567 | C0 | C3 | sc3_simgeom_addref_functor | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMGEOM.DLL | 0x1000356e | C0 | C3 | sc3_simgeom_release_functor | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMGEOM.DLL | 0x10014a99 | C0 | C2 | sc3_simgeom_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMGEOM.DLL | 0x10023e54 | C0 | C2 | sc3_simgeom_release_comptrlist | verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMINIT.DLL | 0x10004e3b | C0 | C3 | sc3_siminit_addref_schememgr | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMINIT.DLL | 0x100062ad | C0 | C3 | sc3_siminit_release_schememgr | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMINIT.DLL | 0x1000c175 | C0 | C2 | sc3_siminit_release_gfxprobe | verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMINIT.DLL | 0x1000c605 | C0 | C3 | sc3_siminit_addref_attribcache | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMINIT.DLL | 0x1000d3b3 | C0 | C3 | sc3_siminit_release_attribcache | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMINIT.DLL | 0x1000cd67 | C0 | C2 | sc3_siminit_addref_functor | verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMINIT.DLL | 0x1000cd6e | C0 | C2 | sc3_siminit_release_functor | verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMINIT.DLL | 0x1000d68d | C0 | C3 | sc3_siminit_addref_iterator | verify/refaudit, verify/refaudit/le1_refcount_vtables.txt, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMINIT.DLL | 0x1000d694 | C0 | C3 | sc3_siminit_release_iterator | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMMISC.DLL | 0x1002e3f0 | C0 | C2 | sc3_simmisc_addref_dataadapter | verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMMISC.DLL | 0x10034523 | C0 | C2 | sc3_simmisc_release_dataadapter | verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMMISC.DLL | 0x10019b3e | C0 | C3 | sc3_simmisc_addref_ordinancelayer | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMMISC.DLL | 0x10019b45 | C0 | C3 | sc3_simmisc_release_ordinancelayer | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMRCI.DLL | 0x1004288d | C0 | C3 | sc3_simrci_addref_dataadapter | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMRCI.DLL | 0x10042894 | C0 | C3 | sc3_simrci_release_dataadapter | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMRCI.DLL | 0x100318c1 | C0 | C3 | sc3_simrci_addref_functor | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMRCI.DLL | 0x100318c8 | C0 | C3 | sc3_simrci_release_functor | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMSERV.DLL | 0x1001a9e6 | C0 | C2 | sc3_simserv_addref_dataadapter | verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMSERV.DLL | 0x100192ad | C0 | C2 | sc3_simserv_release_dataadapter | verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMUI.DLL | 0x100139b6 | C0 | C3 | sc3_ui_addref_object | verify/refaudit, verify/refaudit/le1_refcount_vtables.txt, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMUI.DLL | 0x10090d1c | C0 | C3 | sc3_ui_release_uiadapter | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMUTIL.DLL | 0x1001cc1c | C0 | C3 | sc3_simutil_addref_object | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMUTIL.DLL | 0x100053ae | C0 | C3 | sc3_simutil_release_poweralgo | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SIMUTIL.DLL | 0x1001cc23 | C0 | C2 | sc3_simutil_release_dataadapter | verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | STRTSIM.DLL | 0x1001607d | C0 | C3 | sc3_strtsim_release_occupant | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | STRTSIM.DLL | 0x1001e004 | C0 | C3 | sc3_strtsim_addref_setupobj | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | STRTSIM.DLL | 0x1001e1de | C0 | C3 | sc3_strtsim_release_setupobj | verify/refaudit, verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | STRTSIM.DLL | 0x1001e2c3 | C0 | C2 | sc3_strtsim_release_setupobj2 | verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SimTransit.dll | 0x1001499a | C0 | C2 | sc3_transit_addref_dataadapter | verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | SimTransit.dll | 0x100149a1 | C0 | C2 | sc3_transit_release_dataadapter | verify/reload1024/plain_refcount_vtables_ecx.txt |
| pri | AUDIO.DLL | 0x100164c7 | C0 | C2 | sc3_audio_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | AUDIO.DLL | 0x100164ce | C0 | C2 | sc3_audio_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | AUDIO.DLL | 0x1001bd04 | C0 | C2 | sc3_audio_addref_comdirector | verify/refaudit/le1_refcount_vtables.txt |
| pri | AUDIO.DLL | 0x1001bd0b | C0 | C2 | sc3_audio_release_fwobject20 | verify/refaudit/le1_refcount_vtables.txt |
| pri | GIMEX.DLL | 0x10016f85 | C0 | C2 | sc3_gimex_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | GIMEX.DLL | 0x10016f8c | C0 | C2 | sc3_gimex_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | GZGraphicD.dll | 0x1001c3fe | C0 | C2 | sc3_gzgfx_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | GZGraphicD.dll | 0x1001c405 | C0 | C2 | sc3_gzgfx_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | GZResourceD.dll | 0x1000a5fb | C0 | C2 | sc3_gzres_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | GZResourceD.dll | 0x100023c0 | C0 | C2 | sc3_gzres_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | GZResourceD.dll | 0x1000b7c0 | C0 | C3 | sc3_gzres_release_resource | verify/refaudit, verify/refaudit/le1_refcount_vtables.txt |
| pri | GZResourceD.dll | 0x10015b0a | C0 | C3 | sc3_gzres_release_resourcemgr | verify/refaudit, verify/refaudit/le1_refcount_vtables.txt |
| pri | GZResourceD.dll | 0x1001814d | C0 | C2 | sc3_gzres_addref_comdirector | verify/refaudit/le1_refcount_vtables.txt |
| pri | GZResourceD.dll | 0x10018154 | C0 | C2 | sc3_gzres_release_fwobject20 | verify/refaudit/le1_refcount_vtables.txt |
| pri | GZSOUNDD.DLL | 0x10002431 | C0 | C2 | sc3_gzsound_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | GZSOUNDD.DLL | 0x10002438 | C0 | C2 | sc3_gzsound_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | GZServiceD.dll | 0x100063f7 | C0 | C2 | sc3_gzsvc_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | GZServiceD.dll | 0x100063fe | C0 | C2 | sc3_gzsvc_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | GZServiceD.dll | 0x10011da9 | C0 | C2 | sc3_gzsvc_addref_comdirector | verify/refaudit/le1_refcount_vtables.txt |
| pri | GZServiceD.dll | 0x10011db0 | C0 | C2 | sc3_gzsvc_release_fwobject20 | verify/refaudit/le1_refcount_vtables.txt |
| pri | GZTOOLSD.DLL | 0x10005f1c | C0 | C2 | sc3_gztools_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | GZTOOLSD.DLL | 0x10005f23 | C0 | C2 | sc3_gztools_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | GZWinD.dll | 0x10023411 | C0 | C2 | sc3_gzwin_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | GZWinD.dll | 0x10023418 | C0 | C2 | sc3_gzwin_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | GZWinD.dll | 0x10027149 | C0 | C2 | sc3_gzwin_addref_comdirector | verify/refaudit/le1_refcount_vtables.txt |
| pri | GZWinD.dll | 0x10027150 | C0 | C2 | sc3_gzwin_release_fwobject20 | verify/refaudit/le1_refcount_vtables.txt |
| pri | GZWWWD.dll | 0x1000a9a7 | C0 | C2 | sc3_gzwww_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | GZWWWD.dll | 0x1000a9ae | C0 | C2 | sc3_gzwww_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | GZWWWD.dll | 0x1000a0fe | C0 | C2 | sc3_gzwww_addref_comdirector | verify/refaudit/le1_refcount_vtables.txt |
| pri | GZWWWD.dll | 0x1000da87 | C0 | C2 | sc3_gzwww_release_fwobject20 | verify/refaudit/le1_refcount_vtables.txt |
| pri | MaxisAddOn.dll | 0x10002136 | C0 | C2 | sc3_maxisaddon_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | MaxisAddOn.dll | 0x1000213d | C0 | C2 | sc3_maxisaddon_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SCENARIO.DLL | 0x100101c1 | C0 | C2 | sc3_scenario_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SCENARIO.DLL | 0x100101c8 | C0 | C2 | sc3_scenario_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SCENARIO.DLL | 0x1000fac6 | C0 | C2 | sc3_scenario_addref_comdirector | verify/refaudit/le1_refcount_vtables.txt |
| pri | SCENARIO.DLL | 0x10013d1b | C0 | C2 | sc3_scenario_release_fwobject20 | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMADV.DLL | 0x1002507e | C0 | C3 | sc3_simadv_addref_fwobject | verify/refaudit, verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMADV.DLL | 0x10025085 | C0 | C3 | sc3_simadv_release_fwobject | verify/refaudit, verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMADV.DLL | 0x100287b1 | C0 | C2 | sc3_simadv_addref_comdirector | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMADV.DLL | 0x100287b8 | C0 | C2 | sc3_simadv_release_fwobject20 | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMBABLD.DLL | 0x12055fed | C0 | C2 | sc3_simbabld_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMBABLD.DLL | 0x12055ff4 | C0 | C2 | sc3_simbabld_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMBABLD.DLL | 0x12059e64 | C0 | C2 | sc3_simbabld_addref_resource | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMBABLD.DLL | 0x12050943 | C0 | C2 | sc3_simbabld_release_resource | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMBABLD.DLL | 0x12059e6b | C0 | C2 | sc3_simbabld_release_resourcemgr | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMBABLD.DLL | 0x12058e3c | C0 | C2 | sc3_simbabld_addref_comdirector | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMBABLD.DLL | 0x1205c3c5 | C0 | C2 | sc3_simbabld_release_fwobject20 | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMCITY.DLL | 0x100098ae | C0 | C3 | sc3_simcity_addref_fwobject | verify/refaudit, verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMCITY.DLL | 0x100098b5 | C0 | C3 | sc3_simcity_release_fwobject | verify/refaudit, verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMDIRT.DLL | 0x1001ae08 | C0 | C2 | sc3_dirt_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMDIRT.DLL | 0x1001ae0f | C0 | C2 | sc3_dirt_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMDSTR.DLL | 0x10025643 | C0 | C2 | sc3_dstr_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMDSTR.DLL | 0x100236cc | C0 | C2 | sc3_dstr_addref_comdirector | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMDSTR.DLL | 0x10029cd2 | C0 | C2 | sc3_dstr_release_fwobject20 | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMECO.DLL | 0x1000e760 | C0 | C2 | sc3_simeco_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMECO.DLL | 0x1000e767 | C0 | C2 | sc3_simeco_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMECO.DLL | 0x10012e9d | C0 | C2 | sc3_simeco_addref_comdirector | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMECO.DLL | 0x10012ea4 | C0 | C2 | sc3_simeco_release_fwobject20 | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMGEOM.DLL | 0x10014aa0 | C0 | C2 | sc3_simgeom_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMGEOM.DLL | 0x1001a2af | C0 | C2 | sc3_simgeom_addref_comdirector | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMGEOM.DLL | 0x1001afd9 | C0 | C2 | sc3_simgeom_release_fwobject20 | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMINIT.DLL | 0x1001f795 | C0 | C2 | sc3_siminit_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMINIT.DLL | 0x1001ff93 | C0 | C2 | sc3_siminit_addref_comdirector | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMINIT.DLL | 0x10025247 | C0 | C2 | sc3_siminit_release_fwobject20 | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMMISC.DLL | 0x1002ad53 | C0 | C2 | sc3_simmisc_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMMISC.DLL | 0x1002ad5a | C0 | C2 | sc3_simmisc_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMMISC.DLL | 0x10030a1e | C0 | C2 | sc3_simmisc_addref_comdirector | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMMISC.DLL | 0x10030a25 | C0 | C2 | sc3_simmisc_release_fwobject20 | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMNTWRK.DLL | 0x1001eeb2 | C0 | C2 | sc3_ntwrk_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMNTWRK.DLL | 0x1001eeb9 | C0 | C2 | sc3_ntwrk_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMNTWRK.DLL | 0x1002048f | C0 | C2 | sc3_ntwrk_addref_comdirector | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMNTWRK.DLL | 0x10020496 | C0 | C2 | sc3_ntwrk_release_fwobject20 | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMRCI.DLL | 0x10036f79 | C0 | C2 | sc3_simrci_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMRCI.DLL | 0x10036f80 | C0 | C2 | sc3_simrci_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMRCI.DLL | 0x1003b9eb | C0 | C2 | sc3_simrci_addref_comdirector | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMRCI.DLL | 0x1003b9f2 | C0 | C2 | sc3_simrci_release_fwobject20 | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMSERV.DLL | 0x100106f9 | C0 | C2 | sc3_simserv_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMSERV.DLL | 0x10010700 | C0 | C2 | sc3_simserv_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMSERV.DLL | 0x10014159 | C0 | C2 | sc3_simserv_addref_comdirector | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMSERV.DLL | 0x10014160 | C0 | C2 | sc3_simserv_release_fwobject20 | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMSPR.DLL | 0x1004f11b | C0 | C2 | sc3_spr_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMSPR.DLL | 0x1004f122 | C0 | C2 | sc3_spr_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMSPR.DLL | 0x100561c4 | C0 | C2 | sc3_spr_addref_comdirector | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMSPR.DLL | 0x100561cb | C0 | C2 | sc3_spr_release_fwobject20 | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMSPR.DLL | 0x10059831 | C0 | C3 | sc3_spr_release_resource | verify/refaudit, verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMUI.DLL | 0x100842b0 | C0 | C3 | sc3_ui_addref_fwobject | verify/refaudit, verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMUI.DLL | 0x100842b7 | C0 | C3 | sc3_ui_release_fwobject | verify/refaudit, verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMUI.DLL | 0x10043ba9 | C0 | C3 | sc3_ui_release_wrapper | verify/refaudit, verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMUI.DLL | 0x100849eb | C0 | C2 | sc3_ui_addref_comdirector | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMUI.DLL | 0x1008bea1 | C0 | C2 | sc3_ui_release_fwobject20 | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMUTIL.DLL | 0x10013402 | C0 | C2 | sc3_simutil_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMUTIL.DLL | 0x10013409 | C0 | C2 | sc3_simutil_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMUTIL.DLL | 0x10017c14 | C0 | C2 | sc3_simutil_addref_comdirector | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMUTIL.DLL | 0x10017c1b | C0 | C2 | sc3_simutil_release_fwobject20 | verify/refaudit/le1_refcount_vtables.txt |
| pri | STRTSIM.DLL | 0x10021987 | C0 | C2 | sc3_strtsim_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | STRTSIM.DLL | 0x100244cb | C0 | C2 | sc3_strtsim_addref_comdirector | verify/refaudit/le1_refcount_vtables.txt |
| pri | STRTSIM.DLL | 0x10025664 | C0 | C2 | sc3_strtsim_release_fwobject20 | verify/refaudit/le1_refcount_vtables.txt |
| pri | SimTransit.dll | 0x1000e91f | C0 | C2 | sc3_transit_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SimTransit.dll | 0x1000e926 | C0 | C2 | sc3_transit_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SimTransit.dll | 0x10011a38 | C0 | C2 | sc3_transit_addref_comdirector | verify/refaudit/le1_refcount_vtables.txt |
| pri | SimTransit.dll | 0x10011a3f | C0 | C2 | sc3_transit_release_fwobject20 | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMVARIABLES.DLL | 0x10003419 | C0 | C2 | sc3_simvar_addref_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMVARIABLES.DLL | 0x10003420 | C0 | C2 | sc3_simvar_release_fwobject | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMVARIABLES.DLL | 0x10003f96 | C0 | C2 | sc3_simvar_addref_comdirector | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMVARIABLES.DLL | 0x10007ca3 | C0 | C2 | sc3_simvar_release_fwobject20 | verify/refaudit/le1_refcount_vtables.txt |
| pri | SIMCITY.DLL | 0x10010d0d | C0 | C4 | sc3_simcity_addref_simgroup | verify/reload1024 |
| pri | SIMCITY.DLL | 0x10010d14 | C0 | C4 | sc3_simcity_release_simgroup | verify/reload1024 |
| pri | SIMSERV.DLL | 0x1000c3df | C2 | C3 | sc3_simserv_addref_object | verify/refaudit |
| pri | SIMSERV.DLL | 0x1000cab6 | C2 | C3 | sc3_simserv_release_object | verify/refaudit |
| pri | STRTSIM.DLL | 0x10002ea6 | C0 | C3 | sc3_strtsim_alloc_pool | verify/reload1024 |
| pri | STRTSIM.DLL | 0x10002fdd | C0 | C3 | sc3_strtsim_free_pool | verify/reload1024 |
| pri | STRTSIM.DLL | 0x1000304f | C0 | C2 | sc3_strtsim_refill_pool | verify/reload1024 |
| pri | STRTSIM.DLL | 0x10011036 | C0 | C2 | sc3_strtsim_handle_occupant_inserted | verify/reload1024 |
| pri | STRTSIM.DLL | 0x10011399 | C0 | C2 | sc3_strtsim_insert_occupant_set | verify/reload1024 |
| pri | STRTSIM.DLL | 0x10011861 | C0 | C2 | sc3_strtsim_insert_set_node | verify/reload1024 |
| pri | STRTSIM.DLL | 0x100118e3 | C0 | C2 | sc3_strtsim_rebalance_set_tree | verify/reload1024 |
| pri | STRTSIM.DLL | 0x1001125c | C0 | C3 | sc3_strtsim_destroy_occupant_set | verify/reload1024 |
| pri | STRTSIM.DLL | 0x100142bb | C0 | C2 | sc3_strtsim_shutdown_layer | verify/reload1024 |
| pri | GZServiceD.dll | 0x10003922 | C0 | C3 | sc3_gzsvc_send_message | verify/refaudit, verify/reload1024 |
| pri | GZServiceD.dll | 0x100039ee | C0 | C2 | sc3_gzsvc_add_notification | verify/refaudit |
| pri | GZServiceD.dll | 0x10003b65 | C0 | C1 | sc3_gzsvc_remove_notification | verify/reload1024 |
| pri | SIMCITY.DLL | 0x10001914 | C1 | C2 | sc3_simcity_iterate_registry | verify/reload1024 |
| pri | SIMCITY.DLL | 0x1000e93f | C0 | C3 | sc3_simcity_simulate_group | verify/reload1024 |
| pri | SIMCITY.DLL | 0x1000e7a7 | C0 | C2 | sc3_simcity_add_group_member | verify/reload1024 |
| pri | SIMCITY.DLL | 0x1000ebeb | C0 | C2 | sc3_simcity_push_group_member | verify/reload1024 |
| pri | SIMCITY.DLL | 0x1000e787 | C0 | C2 | sc3_simcity_addref_simgroup_thunk | verify/reload1024 |
| pri | SIMCITY.DLL | 0x1000e78f | C0 | C2 | sc3_simcity_release_simgroup_thunk | verify/reload1024 |
| pri | SIMCITY.DLL | 0x100017e2 | C0 | C1 | sc3_simcity_send_message_ba3d133d | verify/refaudit |
| pri | SCENARIO.DLL | 0x100067f0 | C0 | C2 | sc3_scenario_destruct_layer | verify/refaudit |
| pri | SCENARIO.DLL | 0x10007bd5 | C0 | C2 | sc3_scenario_init_layer | verify/refaudit |
| pri | SCENARIO.DLL | 0x1000f612 | C0 | C2 | sc3_scenario_addref_layer_thunk | verify/refaudit |
| pri | SCENARIO.DLL | 0x1000f61a | C0 | C2 | sc3_scenario_release_layer_thunk | verify/refaudit |
| pri | SIMDSTR.DLL | 0x1000857d | C2 | C2 | sc3_dstr_layer_init_city | verify/refaudit |
| pri | SIMSPR.DLL | 0x10058a42 | C1 | C2 | sc3_spr_construct_resource | verify/refaudit |
| pri | SIMSPR.DLL | 0x100598fc | C0 | C2 | sc3_spr_release_resource_thunk | verify/refaudit |
| pri | GZResourceD.dll | 0x1000dc13 | C1 | C2 | sc3_gzres_construct_resource | verify/refaudit |
| pri | GZResourceD.dll | 0x1000b8be | C0 | C2 | sc3_gzres_release_resource_thunk | verify/refaudit |
| pri | SIMUI.DLL | 0x10043d52 | C1 | C2 | sc3_ui_construct_wrapper | verify/refaudit |
| pri | SIMUI.DLL | 0x10043424 | C0 | C2 | sc3_ui_post_wrapper_to_owner | verify/refaudit |
| pri | SIMSPR.DLL | 0x1000dc17 | C3 | C3 | sc3_spritecellmap_update_all_dirty_rects | verify/sprcrash |
| pri | SIMSPR.DLL | 0x1001cab9 | C1 | C3 | sc3_cityviewiso_plot | verify/sprcrash |
| pri | SIMSPR.DLL | 0x10006752 | C2 | C3 | sc3_spritecellmap_set_zoom | verify/sprcrash |
| pri | SIMSPR.DLL | 0x10006a55 | C3 | C3 | sc3_spritecellmap_set_rotate | verify/sprcrash |
| pri | SIMSPR.DLL | 0x1001d1d9 | C1 | C3 | sc3_cityviewiso_set_zoom_and_rotation | verify/sprcrash |
| pri | SIMSPR.DLL | 0x1001d2d6 | C1 | C3 | sc3_cityviewiso_zoom_in | verify/sprcrash, verify/zoomcrash |
| pri | SIMSPR.DLL | 0x1001d365 | C1 | C3 | sc3_cityviewiso_zoom_out | verify/zoomcrash |
| pri | SIMSPR.DLL | 0x1001d3f3 | C1 | C2 | sc3_cityviewiso_rotate_camera_cw | verify/sprcrash |
| pri | SIMSPR.DLL | 0x1001d47b | C1 | C1 | sc3_cityviewiso_rotate_camera_ccw | verify/sprcrash |
| pri | SIMSPR.DLL | 0x10042d8a | C1 | C3 | sc3_wincityview_zoom_in | verify/zoomcrash |
| pri | SIMSPR.DLL | 0x10042a95 | C3 | C3 | sc3_wincityview_tick | verify/sprcrash |
| pri | SIMSPR.DLL | 0x10044471 | C2 | C3 | sc3spr_view_register_cursors | verify/spr47b70 |
| pri | SIMSPR.DLL | 0x10043daf | C3 | C3 | sc3_wincityview_scroll_step | verify/spr47b70 |
| pri | GZResourceD.dll | 0x10007603 | C2 | C3 | sc3_gzres_load_imagefile | verify/spr47b70 |
| pri | GZResourceD.dll | 0x1001816f | C2 | C3 | sc3_gzres_open_file | verify/spr47b70 |
| pri | GZResourceD.dll | 0x1000a89b | C0 | C2 | sc3_gzres_open_path | verify/spr47b70 |
| pri | STRTSIM.DLL | 0x1001d2c0 | C3 | C3 | sc3_vehicle_update_tick | verify/zoomcrash |
| pri | GZWinD.dll | 0x10020260 | C0 | C3 | sc3_gzwin_get_cursor_client_pos | verify/rc_1023 |
| pri | SIMUI.DLL | 0x10042866 | C2 | C2 | sc3ui_ctor_clsid_5a9 | verify/minimap, verify/verdatos |
| pri | SIMUI.DLL | 0x10043937 | C0 | C3 | sc3_ui_draw_map_view | verify/minimap, verify/verdatos |
| pri | SIMUI.DLL | 0x100436b4 | C0 | C3 | sc3_ui_compute_map_texture_side | verify/minimap, verify/verdatos |
| pri | SIMUI.DLL | 0x10042aec | C0 | C3 | sc3_ui_clone_map_view | verify/minimap, verify/verdatos |
| pri | SIMUI.DLL | 0x10043afc | C0 | C2 | sc3_ui_set_map_view_rect | verify/minimap |
| pri | SIMUI.DLL | 0x10042ca4 | C0 | C2 | sc3_ui_deactivate_map_view | re/analysis/HUD_SCALE.md |
| pri | SIMUI.DLL | 0x1004367e | C0 | C2 | sc3_ui_free_map_texture | re/analysis/HUD_SCALE.md |
| pri | SIMUI.DLL | 0x10050de2 | C0 | C2 | sc3_ui_build_minimap_view | verify/minimap, verify/refaudit |
| pri | SIMUI.DLL | 0x100507ad | C0 | C3 | sc3_ui_handle_minimap_message | verify/minimap |
| pri | SIMUI.DLL | 0x1006d56c | C2 | C3 | sc3_ui_sync_surface | verify/minimap |
| pri | SIMUI.DLL | 0x10044021 | C2 | C2 | sc3ui_ctor_clsid_5a3 | verify/verdatos |
| pri | SIMUI.DLL | 0x10044430 | C0 | C2 | sc3_ui_create_dataview_panels | re/analysis/HUD_SCALE.md |
| pri | SIMUI.DLL | 0x10045df2 | C0 | C2 | sc3_ui_create_panel_map_view | verify/verdatos |
| pri | SIMUI.DLL | 0x10044aa6 | C0 | C3 | sc3_ui_switch_dataview_panel | verify/verdatos |
| pri | SimTransit.dll | 0x1000755e | C2 | C3 | sc3_transit_select_next_cell | verify/bventry |
| pri | SimTransit.dll | 0x100070d0 | C2 | C3 | sc3_transit_route_trip | verify/avflow |
| pri | SimTransit.dll | 0x10006edd | C2 | C3 | sc3_transit_add_congestion | verify/avflow |
| pri | SimTransit.dll | 0x100093e9 | C2 | C3 | sc3_transit_recompute_stats | verify/avflow |
| pri | SimTransit.dll | 0x100057f6 | C0 | C3 | sc3_transit_get_lot_kind | verify/bventry |
| pri | SimTransit.dll | 0x10008a94 | C2 | C2 | sc3_transit_query_reachable | verify/bventry |
| pri | SimTransit.dll | 0x1000559e | C2 | C2 | sc3_transit_fill_station_coverage | verify/bventry |
| pri | SimTransit.dll | 0x100010d1 | C2 | C2 | sc3_transit_director_ctor | verify/refaudit |
| pri | SC3U.exe | 0x0048a575 | C0 | C2 | sc3_gzcom_load_director_dll | verify/loader2 |
| pri | SC3U.exe | 0x0048a920 | C0 | C1 | sc3_gzcom_register_director_path | verify/loader2 |
| pri | SC3U.exe | 0x0048aa95 | C0 | C1 | sc3_gzcom_find_director_clsid | verify/loader2 |
| pri | SC3U.exe | 0x00482aee | C0 | C1 | sc3_app_read_maxis_ini | verify/loader2 |
| pri | SC3U.exe | 0x00482532 | C0 | C1 | sc3_app_read_plugin_dirs | verify/loader2 |
| pri | SC3U.exe | 0x00464368 | C0 | C1 | sc3_app_resolve_path_tokens | verify/loader2 |
| pri | SC3U.exe | 0x0047ffd2 | C0 | C1 | sc3_app_enum_directory | verify/loader2 |
| sec | SIMSPR.DLL | 0x100192aa | C0 | C2 | sc3_spr_apply_frame_layerflags | verify/artkit, verify/hwcore, verify/roundabout4 |
| sec | SIMSPR.DLL | 0x10001c90 | C0 | C2 | sc3_spr_read_frame_layerflags | verify/artkit |
| sec | SIMSPR.DLL | 0x1000b352 | C0 | C2 | sc3_spr_store_cell_anchor | verify/artkit |
| sec | SIMSPR.DLL | 0x1001a303 | C0 | C2 | sc3_spr_draw_terrain_under | verify/roundabout4 |
| sec | SIMSPR.DLL | 0x10002088 | C0 | C2 | sc3_spr_create_sprite_by_class | verify/hwcore |
| sec | SIMSPR.DLL | 0x10015e72 | C0 | C2 | sc3_spr_attach_terrain_672 | verify/hwcore |
| sec | SIMSPR.DLL | 0x10015dd0 | C0 | C2 | sc3_spr_draw_attached_terrain_672 | verify/hwcore |
| sec | SIMSPR.DLL | 0x1000a513 | C0 | C2 | sc3_spr_convert_tile_to_world | verify/leftclick |
| sec | SIMSPR.DLL | 0x1004adcd | C0 | C3 | sc3_spr_query_drag_highlight | verify/netbridge |
| sec | SIMSPR.DLL | 0x10042cd3 | C1 | C3 | sc3_wincityview_set_edge_scroll | verify/resize_edgescroll |
| sec | SIMSPR.DLL | 0x1004979a | C1 | C2 | sc3_wincityview_def_on_key_down | verify/resize_edgescroll |
| sec | SIMSPR.DLL | 0x1004985a | C1 | C2 | sc3_wincityview_def_on_key_up | verify/resize_edgescroll |
| sec | SIMSPR.DLL | 0x10043540 | C1 | C3 | sc3_wincityview_focus_camera_on | verify/simrun |
| sec | SIMSPR.DLL | 0x10048a08 | C1 | C3 | sc3_wincityview_set_active_handler | verify/undo_spike |
| sec | SIMSPR.DLL | 0x10048a2d | C1 | C3 | sc3_wincityview_switch_handler | verify/undo_spike |
| sec | STRTSIM.DLL | 0x10016520 | C0 | C2 | sc3_strtsim_enter_vehicle_block | verify/avdiag |
| sec | STRTSIM.DLL | 0x1001ff93 | C0 | C2 | sc3_strtsim_build_intersect_list | verify/avdiag |
| sec | STRTSIM.DLL | 0x100167fe | C0 | C2 | sc3_strtsim_test_chord_intersect | verify/avdiag |
| sec | STRTSIM.DLL | 0x1001c9e0 | C0 | C3 | sc3_vehicle_shutdown_car | verify/hwcars |
| sec | STRTSIM.DLL | 0x10020108 | C0 | C2 | sc3_strtsim_find_arrival_node | verify/lanekit, verify/roundabout2 |
| sec | SC3U.exe | 0x00425a10 | C0 | C3 | sc3_heartbeat_tick_agents | verify/cartrips, verify/cartrips3, verify/pausetrips |
| sec | SC3U.exe | 0x0040b00f | C0 | C2 | sc3_gzcom_load_plugin_dlls | verify/windowed |
| sec | SC3U.exe | 0x0048a675 | C0 | C1 | sc3_gzcom_free_director_dll | verify/windowed |
| sec | SC3U.exe | 0x00407f25 | C0 | C3 | sc3_app_end_session | verify/undo_spike |
| sec | SC3U.exe | 0x00407fbf | C0 | C1 | sc3_app_destroy_city | verify/undo_spike |
| sec | SC3U.exe | 0x00407b5e | C0 | C1 | sc3_app_create_city | verify/undo_spike |
| sec | SC3U.exe | 0x004430f3 | C0 | C1 | sc3_ui_anchor_tooltip | verify/toolicon |
| sec | SC3U.exe | 0x0046135a | C0 | C1 | sc3_app_run_message_pump | verify/dlgscale |
| sec | GZServiceD.dll | 0x10006e54 | C0 | C3 | sc3_gzsvc_draw_font_glyph | verify/dlgscale |
| sec | GZServiceD.dll | 0x100072e2 | C0 | C1 |  | verify/dlgscale |
| sec | GZServiceD.dll | 0x1000736f | C0 | C1 |  | verify/dlgscale |
| sec | GZServiceD.dll | 0x10007477 | C0 | C1 |  | verify/dlgscale |
| sec | GZGraphicD.dll | 0x10011f73 | C0 | C2 | sc3_gfx_set_display_mode | verify/fullscreen |
| sec | GZWinD.dll | 0x10020971 | C0 | C2 | sc3_gzwin_run_modal_loop | verify/hudclick |
| sec | SIMNTWRK.DLL | 0x10016ccd | C0 | C3 | sc3_ntwrk_test_cell_flat | verify/hwcap |
| sec | SIMNTWRK.DLL | 0x10016d69 | C0 | C3 | sc3_ntwrk_test_cell_water | verify/hwcap |
| sec | SIMNTWRK.DLL | 0x10008919 | C0 | C3 | sc3_ntwrk_write_piece | verify/hwcap, verify/hwcore |
| sec | SIMNTWRK.DLL | 0x10004754 | C0 | C3 | sc3_ntwrk_add_tool_cell | verify/netramp, verify/onramp |
| sec | SIMNTWRK.DLL | 0x1001d6ef | C0 | C3 | sc3_ntwrk_remove_pieces | verify/netbridge |
| sec | SIMNTWRK.DLL | 0x10012fc3 | C0 | C2 | sc3_ntwrk_save_tiles | verify/hwcore, verify/hwdd |
| sec | SIMNTWRK.DLL | 0x1000d688 | C0 | C2 | sc3_ntwrk_write_tile_record | verify/hwcore |
| sec | SimTransit.dll | 0x10009e8e | C0 | C3 | sc3_transit_pop_path_node | verify/hwtrips |
| sec | SIMCITY.DLL | 0x100056bb | C1 | C2 | sc3_city_pause | verify/avcore, verify/pausetrips |
| sec | SIMCITY.DLL | 0x10005773 | C1 | C2 | sc3_city_unpause | verify/avcore |
| sec | SIMCITY.DLL | 0x1000d036 | C1 | C2 | sc3_simcity_start_thread | verify/pausetrips |
| sec | SIMCITY.DLL | 0x10005a70 | C1 | C2 | sc3_city_get_simulation_clock | verify/pausetrips |
| sec | SIMCITY.DLL | 0x100059cf | C1 | C3 | sc3_city_hidden_clock_pause | verify/pausetrips, verify/simrun |
| sec | SIMCITY.DLL | 0x100058ac | C1 | C3 | sc3_city_sim_hidden_pause | verify/pausetrips |
| sec | SIMCITY.DLL | 0x1000590e | C1 | C2 | sc3_city_sim_hidden_unpause | verify/pausetrips |
| sec | SIMCITY.DLL | 0x1000ee96 | C0 | C3 | sc3_simcity_get_heartbeat | verify/pausetrips |
| sec | SIMCITY.DLL | 0x1000c0a5 | C0 | C3 | sc3_simclock_timer_callback | verify/pausetrips |
| sec | SIMUI.DLL | 0x1006c61b | C0 | C2 | sc3_ui_rebuild_window_rects | verify/resize_edgescroll |
| sec | SIMUI.DLL | 0x10050cb3 | C0 | C2 | sc3_ui_center_compass_label | verify/undo_mod |
| sec | SIMDIRT.DLL | 0x1000c5d0 | C1 | C3 | sc3_dirtbag_level_terrain | verify/undo_mod |
| sec | SIMSERV.DLL | 0x100087b2 | C0 | C3 | sc3_simserv_erase_map_key | verify/undo_mod, verify/undo_spike |
| sec | SIMSERV.DLL | 0x10007f7e | C0 | C3 | sc3_simserv_map_subscript | verify/undo_mod |
| sec | SIMSERV.DLL | 0x10005f64 | C0 | C2 | sc3_simserv_init_modifier_map | verify/undo_spike |
| sec | SIMECO.DLL | 0x1000a88a | C0 | C3 | sc3_simeco_erase_map_node | verify/undo_mod |

## Files

- `ladder_batch.tsv` (primary), `ladder_batch_secondary.tsv`, `ladder_batch_all.tsv` (what was applied), `ladder_batch_fix_subsystem.tsv`
- `ladder_plan.tsv`: per row old / new level and name, proposal, notes
- `counts_before.json`, `counts_after.json` (`tools/counts.py`)
- `tools/`: `refbodies.py` (parses the refcount lists + census), `gen.py` + `rows_named.py` + `rows_secondary.py` (build the batch; run from the worktree root with the tools dir as argument), `bodies.json`, `secondary_cites.tsv` (the secondary sweep)
