# avflag: Bitdefender flags sc3netmod.dll (Simtropolis report, 2026-11-10)

Report: a Simtropolis player had to turn Bitdefender off to install the mods: "Bitdefender does not like the mod file for
the avenues and highways".

Verdict: **reproduced and cleared.** Every `sc3netmod.dll` we built since 2026-10-27 is detected as
`Gen:Variant.Draftor.8144` by the Bitdefender engine. The same code with a VERSIONINFO resource scans clean, so
`re/scripts/build_mod.ps1` now gives every mod DLL one (AVVERSION, `-NoVersionInfo` builds without it).

## Scanner

VirusTotal needs an API key or a browser, neither available to this session. Jotti's malware scan
(virusscan.jotti.org) runs 13 engines, BitDefender among them, plus eScan and G DATA, which are built on the
Bitdefender engine. Jotti shares uploads with antivirus vendors, as VirusTotal does; these DLLs are already public as
GitHub release assets. It stopped accepting uploads after about 25 files in an hour.

## Results

| file | build | detections (of 13) |
|---|---|---|
| sc3netmod.dll | release 2026-11-10 (`6BF6948F`) | 3: BitDefender, eScan, G DATA = `Gen:Variant.Draftor.8144` |
| sc3netmod.dll | bins_1109, bins_1102d (`85ADA281`, also shipped in the SC3KU package), bins_1031, bins_1028, bins_1027e | 3 each, same name |
| sc3resize, sc3perf, sc3mods, sc3undo | release 2026-11-10 | 0 |

The same variant id across five builds of different sizes means a generic (model) detection, not a hash: rebuilding
alone does not clear it.

### Bisect (sc3netmod, main source, same compiler and flags as build_mod.ps1)

| variant | change | detections |
|---|---|---|
| v0 | none (control) | 3, Draftor.8144 |
| v1 | file overlay compiled out (`overlay_init` and `ov_hook_all` empty: no IAT hooks on CreateFileA / GetFileAttributesA / FindFirstFileA / FindNextFileA / FindClose / LoadLibraryA / LoadLibraryExA) | 3, Draftor.8144 |
| v2 | overlay kept, the LoadLibraryA / ExA IAT hooks dropped | 3, Draftor.8144 |
| v3 | **source unchanged, VERSIONINFO resource linked in** | **0** |

So the IAT file hooks are not the trigger. All our DLLs share one profile (static CRT, no resources, no version info,
unsigned, VirtualProtect / SuspendThread / GetThreadContext imports); sc3netmod is the one the model scored over its
threshold, and version information brings it under.

### After the fix

`build_mod.ps1` (AVVERSION) on child/crashguard, all 12 shipped mod DLLs built with it (sc3perf includes the
crashguard changes):

| file | detections |
|---|---|
| sc3netmod, sc3resize, sc3perf, sc3mods, sc3undo, sc3bigcity, sc3overscroll, sc3simrun, sc3autosave, sc3landfill | 0 each |
| one of sc3dataview / sc3restore (two files sent, one job id returned) | 0 |
| the other of sc3dataview / sc3restore, and sc3resize with VALVEREF | not scanned yet (Jotti refused further uploads): scan before release |

## Limits

- A model detection can come back on a later build. Scan every release's DLLs before publishing.
- Releases already published stay flagged until Bitdefender clears them or players update. A false-positive report
  (bitdefender.com/submit, category False Positive, detection name `Gen:Variant.Draftor.8144`) covers the old files.
- Code signing is the durable fix and needs a certificate (owner call).
- Only Jotti's 13 engines were checked, not VirusTotal's ~70.
