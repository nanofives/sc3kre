# MODULE_INVENTORY.md — every imported binary

All 29 GZCOM director DLLs plus `SC3U.exe` and the iOS oracle are imported into Ghidra and
exported as greppable decomp. Bulk driver: `re/scripts/import_all_modules.ps1` (resumable).
Anchored copies + SHA-256: `original/modules/ANCHORS.txt`.

| export dir | functions |
|---|---:|
| `re/ghidra_export_ios/` | 20,051 |
| `re/ghidra_export_simui/` | 6,045 |
| `re/ghidra_export_simspr/` | 3,265 |
| `re/ghidra_export_simrci/` | 3,263 |
| `re/ghidra_export_simbabld/` | 3,174 |
| `re/ghidra_export_simmisc/` | 2,603 |
| `re/ghidra_export_siminit/` | 2,102 |
| `re/ghidra_export_simadv/` | 1,940 |
| `re/ghidra_export_simdstr/` | 1,914 |
| `re/ghidra_export_simgeom/` | 1,749 |
| `re/ghidra_export_strtsim/` | 1,649 |
| `re/ghidra_export_gzwind/` | 1,596 |
| `re/ghidra_export_audio/` | 1,569 |
| `re/ghidra_export_gzwwwd/` | 1,561 |
| `re/ghidra_export_simutil/` | 1,508 |
| `re/ghidra_export_gzresourced/` | 1,456 |
| `re/ghidra_export_simntwrk/` | 1,353 |
| `re/ghidra_export_simserv/` | 1,343 |
| `re/ghidra_export_simeco/` | 1,212 |
| `re/ghidra_export_scenario/` | 1,209 |
| `re/ghidra_export_simtransit/` | 1,195 |
| `re/ghidra_export_simcity/` | 892 |
| `re/ghidra_export_simdirt/` | 795 |
| `re/ghidra_export_gzgraphicd/` | 767 |
| `re/ghidra_export_gzserviced/` | 728 |
| `re/ghidra_export_simvariables/` | 538 |
| `re/ghidra_export_gimex/` | 504 |
| `re/ghidra_export_gzsoundd/` | 499 |
| `re/ghidra_export_gztoolsd/` | 417 |
| `re/ghidra_export_maxisaddon/` | 95 |

**Total across module exports: 66,992 functions.** `SC3U.exe` (`re/ghidra_export/`) adds 9,727.

Grep any of these directly — that is the offline model. See `MODULE_MAP.md` for which
subsystem lives where, and `SIMRCI.md` / `SIMUTIL_SIMTRANSIT.md` for the analysed ones.
