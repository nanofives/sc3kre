# Child protocol (standing, 2026-10-27)

This file replaces the dated `CHILD_PROTOCOL_2026-10-*.md` set. Those stay in the repo as history. Each of them repeated
the standing rules and then changed a few. A round brief now lists only its own streams (section 7) and points here.

MAIN = `<workspace>\Simcity` (repo root and live game install). `<workspace>` = `C:\Users\maria\Desktop\Proyectos`.

## 1. Your workspace (one command, made by the orchestrator)

```
pwsh re/scripts/sc3dev.ps1 new <name>        # from main, run in MAIN
```

| what | path |
|---|---|
| worktree, branch `child/<name>` (edit ONLY here) | `MAIN\dev\<name>\wt` |
| test tree, hard-linked from the base (`MAIN\stage\release` = the LAN build) | `MAIN\dev\<name>\tree` |
| built mods, `perf.ini`, logs (`SC3MODS_DIR`) | `MAIN\dev\<name>\inst` |

The base's `Apps\SC3U.exe` is already patched to import `sc3mods.dll`. `sc3dev new` builds the loader into
`tree\Apps` and every mod into `inst`. Never put a mod DLL in the tree's `Apps\`: the game maps every DLL there
(FUN_0040b00f). Never edit a linked file in place, delete it and copy first (`netpack.py install` is link-safe). Never
touch another child's folder or game, and never write under MAIN's `Apps`, `Cities`, `Buildings`, `Scripts`.
`dev\` and `stage\` are hidden by the deny-by-default `.gitignore`.

## 2. Build and run

```
pwsh re/scripts/sc3dev.ps1 build <name> [-Mods sc3resize,sc3perf]
pwsh re/scripts/sc3dev.ps1 run <name> [-City "Europolis 1024.sc3"] [-Stock]
```

`run` sets `SC3MODS_DIR` (or `SC3MODS_OFF=1` with `-Stock`), `SC3MODS_MULTI=1` and `SC3RESIZE_WINMEM=0` (always
windowed), starts `tree\Apps\SC3U.exe` and prints the PID, also saved in `dev\<name>\last_pid`. Set `SC3_PID` to it
for every sc3io or lab tool. Stop with `taskkill /PID <pid> /F` after checking the PID is yours. Never kill by name.
Freshly built DLLs take about 24 s on first start (Defender scans them). Never add Defender exclusions or restore
quarantined files. Report them to the orchestrator.

Load City lists `MAIN\Cities`: reach your tree with "Buscar en", or pass `-City`.

## 3. Account rules (children run on claude2, under a managed policy)

- **No `git add` / `git commit`.** Leave changes in the worktree and list every file under "files owned" in your
  STATUS file. The orchestrator commits by path. `git diff/log/status` are fine.
- Commands outside the allow list are refused. If you need one, write it under "blocked on" and message the
  orchestrator. Do not work around it.
- Clear `CL` before any build (`CL=/MP12` breaks VC6-era builds). `sc3dev build` does this.

## 4. Hard rules

- **Never take over the real mouse, keyboard or foreground** (owner 2026-10-25). No SetCursorPos, mouse_event,
  SendInput, keybd_event, SetForegroundWindow or topmost raising. Drive the game with posted messages (sc3io) or Frida
  game calls. Anything that needs a real cursor goes on a "needs owner check" list.
- Frida: any NativeFunction that makes the game DO something uses `{exceptions: 'propagate'}`
  (memory `project-rblab-cam-zoom-deadlock`). Do not attach while the game is paused.
- Pictures: `SC3RESIZE_FRAMEDUMP`. Desktop grabs are stale while the PC is in use. Delete BMP dumps once you have the
  GIF or PNG you need (C: filled once, memory `project-disk-full-frame-dumps`).
- Light testing (memory `feedback-light-testing`): build it well, one in-game check of the case and its neighbours,
  pictures into `MAIN\verify\<name>\owner_shots\`. The owner reviews the pictures.
- **Test slots**: at most 2 test runs at a time across all sessions on LIVING-PC. Wrap every batch, soak or A/B loop:
  bash `test-slot bash -c '<command>'`, PowerShell
  `py -3.12 C:\Users\maria\Desktop\Proyectos\.claude\scripts\testslot\proyectos_test_slot.py pwsh -NoProfile -Command '<command>'`.
  The hook does not run on claude2, so follow this yourself. One quick single launch may use `PROYECTOS_TEST_SLOT=off`.
- A change that touches a shared mod source (`sc3resize.c`, `sc3netmod*.c`) goes in its own block with an off switch
  (`SC3RESIZE_<NAME>=0`), so the orchestrator can merge several children.

## 5. Reporting

`MAIN\re\sessions\STATUS_<name>.md`, updated at every milestone (it survives a lost session). Headings: goal / verdict
+ deciding RVA / built / proven game-side vs static only / blocked on / files owned / game-harness need / asks of
other sessions. Message the orchestrator (`mcp__happy__list_peers`, then `mcp__happy__send_to_session`) at each
milestone:

1. **Cause found**: the case reproduced in your tree, the log lines, the code path and a 3-line summary.
2. **Fixed**: `verify/<name>/RESULTS.md`, pictures, files to commit listed in STATUS.

Do not change behaviour the owner did not report unless the fix needs it, and say so when it does.

## 6. Orchestrator side

```
pwsh re/scripts/sc3dev.ps1 status          # merged / ahead / dirty / game running, per child (-Size for disk)
pwsh re/scripts/sc3dev.ps1 remove <name>   # after the merge. Refuses if unmerged, dirty or running
pwsh re/scripts/sc3dev.ps1 prune           # every merged, clean, idle child
```

Prune at the end of every round. By 2026-10-27 the old layout had left 130 merged sibling folders in `<workspace>`.
The LAN release stages into `MAIN\stage\release` (`re/scripts/lan_release/deploy_lan_release.sh` default), which is
also the base for new trees. A re-stage makes new files: existing trees keep the build they were linked from.

## 7. Round brief template

```
# Round <date>: <topic>
Orchestrator: "<session title>". Rules: re/sessions/CHILD_PROTOCOL.md. Workspaces made from main <sha>.
| stream | owner report | expected |
```
