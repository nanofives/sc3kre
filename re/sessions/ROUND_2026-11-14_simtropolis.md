# Round 2026-11-14: Simtropolis thread feedback

Orchestrator: "SC3 Simtropolis feedback triage (Wine patch, land value 255, avenues, UI rescale)".
Rules: `re/sessions/CHILD_PROTOCOL.md`. Workspaces made from main `e6da51d` (release sc3mods-2026-11-10d, base
`stage\release` = LAN 2026-11-10d).

| stream | player report | expected |
|---|---|---|
| `lxpatch` | "not certain there's a way to apply the patch on Linux or macOS ... would be lovely if the patch could be tool-agnostic" (plays through Wine/Lutris, GOG build; patched the exe on Windows and copied it over) | `re/scripts/sc3mods_patch.sh` (POSIX sh, coreutils only) whose output is byte-identical to `sc3mods_patch.ps1` on every accepted build, plus `-Restore`; README section for Wine/Lutris/macOS |
| `lvwrap` | "when land value is astronomical and exceeds 255, the land value becomes suddenly very low ... stops me from playing every time"; reply: "the traditional workaround was to improve it again to a second 250ish range" | every reader of the land value average traced; cause confirmed in game; fix with an off switch if it is ours to fix |
| `uirepro` | (a) "new avenue not showing up when 2 roads are placed orthogonal (all network pieces disappear - diagonal seems to work)"; (b) "resize and dragging window does not rescale UI, nor does Alt+Enter. Game will enter windowed full screen but UI will remain same size (3440x1440)" | each case reproduced or not on 11-10d, with pictures and the log lines; a fix only if it reproduces and the cause is clear |
| `streply` | the whole thread | a draft reply in the owner's voice, not posted |

## Leads from the triage (static only, not proven in game)

- **Land value.** Per-cell value is clamped 1..255 at SIMRCI `0x1001deca` (`local_5c / 4`, `< 0x100` else `0xff`), so
  one cell cannot wrap. The city average (`cISC3LandValueLayer::GetAverageValue`, layer `+0xc0`) is written at
  `0x1001d616` as `(char)(sum / count)`, where `sum` (`+0xc8`) and `count` (`+0xcc`) are accumulated in
  `0x1001deca` from the per-sub-cell values BEFORE the clamp, with no clamp on the quotient. So an average of 300 reads
  as 44. `0x1001d69b` pushes that byte monthly into the object at layer `+0xd0` (`vt+0x6c`). Nothing else traced yet.
  Background: `re/analysis/LAND_VALUE.md`.
- **HUD Auto scale** (`sc3resize.c` `rz_hs_pre`): factor = min(cw/800, ch/600), recomputed every present, logged as
  `HUDSCALE> Auto: client WxH -> factor F`. At 3440x1440 it is 2.4. An ini with `[hud] scale` = Normal and `ver=2`
  keeps Normal. The SC3KU fork (thronevintagetech) bundles our mods from older sources (memory `project-sc3ku-fork`).
- **Patch script.** `sc3mods_patch.ps1` accepts 2 stock hashes (2.0.0.3 `49DD55E1...`, 2.0.949 `42E30CE0...`) plus a
  signed copy recognised by normalised bytes (signature cut, security dir + checksum zeroed: the Steam exe), and
  appends a `.sc3mod` section with one import of `sc3mods.dll!sc3mods_version`. Stock exes: `original\SC3U.exe`,
  `original\gog_2.0.949\Apps\SC3U.exe`. No real Steam file exists here: `verify/steamsig` built a synthetic one.
