# fridaprop: NativeFunction exceptions audit (re/tools)

Rule: a NativeFunction that makes the game DO something uses `exceptions: 'propagate'`. Pure reads keep the default (`steal`, so a bad pointer is survivable).
Lines are the pre-edit line numbers. Raw grep and the Grep tool agree: 56 `NativeFunction(` sites in 27 files.

| file | line | function called | class | changed |
|---|---|---|---|---|
| cs_probe.py | 85-87 | CModule draw_first/draw_last/draw_forget | READ (own bookkeeping, comment added) | no |
| cs_probe.py | 95 | sc3simrun_animate | ACTION (sets sim animation) | yes |
| cs_probe.py | 96 | sc3simrun_stats | READ | no |
| cs_probe.py | 99 | sc3simrun_carmargin | ACTION (sets margin) | yes |
| cs_probe.py | 101 | sc3cartrips_fill | ACTION (fills cars) | yes |
| cs_probe.py | 181 | kernel32 QueryPerformanceFrequency | READ | no |
| ctm_alt.py | 32 | sc3cartrips_set | ACTION | yes |
| ctm_alt.py | 33 | sc3cartrips_stats | READ (comment added) | no |
| ctm_modealt.py | 27 | sc3cartrips_mode | ACTION | yes |
| ctm_modealt.py | 28 | sc3cartrips_cars | READ (comment added) | no |
| ct_hbenum.py | 31 | SC global getter (0xee96) | READ | no |
| ct_probe.py | 228, 229 | CModule acc_last / acc_forget | READ | no |
| ct_probe.py | 458 | CModule layout | READ | no |
| ct_probe.py | 490 | QueryPerformanceFrequency | READ | no |
| frida_hittest.py | 136 | hit-test walk | READ | no |
| frida_nudge.py | 84 | SetRect (thiscall) | ACTION (moves a control) | yes |
| frida_widen.py | 156 | SetRect (thiscall) | ACTION | yes |
| invalidate.py | 55 | panel invalidate (sets dirty flag) | ACTION | yes |
| leftclick_trace.py | 48 | screen-to-world (0xa513) | READ | no |
| netmod/avflow_probe.py | 46 | sc3netmod_avf_grid | READ | no |
| netmod/avflow_probe.py | 47 | sc3netmod_avf_set | ACTION | yes |
| netmod/avflow_probe.py | 48 | sc3netmod_avd_set | ACTION | yes |
| netmod/avflow_probe.py | 50 | sc3netmod_avf_bv_set | ACTION | yes |
| netmod/bvtrace_probe.py | 42 | sc3netmod_avf_grid | READ | no |
| netmod/hwave_probe.py | 31 | vfn helper (flag queries only) | READ (comment added) | no |
| netmod/hwcars_mode.py | 16 | sc3cartrips_mode | ACTION | yes |
| netmod/hwtrips_probe.py | 46, 47 | QueryPerformanceCounter / Frequency | READ | no |
| netmod/hwtrips_probe.py | 169 | sc3netmod_rf_set | ACTION | yes |
| netmod/ld_alt.py | 36 | lane density set | ACTION | yes |
| netmod/nb_drive.py | 38 | vfn helper | ACTION sites (msg server 0x10 x2) get `prop=1`; the rest READ | yes (new `prop` arg) |
| netmod/nb_drive.py | 102, 159, 205 | trace/remove/centre calls | ACTION | already propagate |
| netmod/nb_drive.py | 114, 172, 220 | ntw 0x21b37 global getter | READ | no |
| netmod/np_drive.py | 36 | vfn helper with `prop` | mixed | already (prop at ACTION sites, READs keep steal) |
| netmod/nramp_cam.py | 45, 46, 48 | zoom / rotate / SetZoomAndRotation | ACTION | already propagate (SC3_CAM_RAW=1 keeps old path on purpose) |
| netmod/nr_drive.py | 31 | vfn helper | ACTION sites (msg server 0x10 x2) get `prop=1`; rest READ | yes (new `prop` arg) |
| netmod/nr_drive.py | 65 | QueryInterface on a piece | READ | no |
| panel_repaint.py | 39 | panel repaint | ACTION | yes |
| place_direct.py | 49 | vfn helper | ACTION sites: msg server x2, pause/unpause x2 (+ the 125/135 calls), place 0x38, zone 0x88; rest READ | yes (new `prop` arg) |
| pt_probe.py | 100 | SC getter | READ | no |
| reunirse2_probe.py | 46, 47 | getter + vtable read | READ | no |
| reunirse_ab.py | 26, 27 | getter + vtable read | READ | no |
| sim_status.py | 22 | budget getter | READ | no |
| zoomcenter_run_arm.py | 32, 34 | pick / screen-to-world | READ | no |

Totals: 56 sites, 27 files. ACTION switched to propagate: 18 (the 3 vfn helpers count once each, their action call sites pass `prop=1`). ACTION already propagate: 7. READ left on default: 31.

Other change: `zoomcenter_run_arm.py` had the absolute `C:\Users\...\re\tools` path; now `pathlib.Path(__file__).resolve().parent`. No other absolute user paths in the touched files.

Verification: every changed .py passes `py -3.12 -m py_compile`. No game launch (the optional smoke check was skipped).
