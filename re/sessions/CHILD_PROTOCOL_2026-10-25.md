# Child protocol, 2026-10-25 (supersedes the launch lines of CHILD_PROTOCOL_2026-10-23_ownerbugs.md)

You are a child of the orchestrator session titled **"SC3: owner bugs 10-23 (minimap, UI toggle, FPS overlay, 1024
reload)"** (find it with `mcp__happy__list_peers`, message it with `mcp__happy__send_to_session` at each milestone).
Everything in `CHILD_PROTOCOL_2026-10-23_ownerbugs.md` still applies (claude2 policy: no git add / commit, the
orchestrator commits by path; never kill by name, only your own PID; always windowed; light testing; the owner reviews
pictures; STATUS file `MAIN\re\sessions\STATUS_<name>.md`) EXCEPT how the game is launched.

## Launching (new loader, main 4a291be and later)

`mods_launch.exe` is gone. `version.dll` beside `SC3U.exe` loads the mods itself (`re/harness/src/sc3modldr.c`):

| env var | effect |
|---|---|
| `SC3MODS_DIR=<folder>` | load the mods from that folder (the built-in list, or `SC3MODS_LIST`) |
| `SC3MODS_LIST=a.dll;b.dll` | override the list |
| `SC3MODS_MULTI=1` | per-pid single-instance mutex, so several test games run at once |
| `SC3MODS_OFF=1` | stock game, nothing loads |

Your test tree's `Apps\` has NO `version.dll` and no mods. Build them from your worktree:
```
pwsh -NoProfile -Command "$env:CL=$null; & <WT>\re\scripts\build_mod.ps1 -Mod sc3modldr -Src <WT>\re\harness\src -Out <TREE>\Apps"
for m in sc3resize sc3bigcity sc3overscroll sc3simrun sc3perf sc3netmod sc3undo:
  pwsh -NoProfile -Command "$env:CL=$null; & <WT>\re\scripts\build_mod.ps1 -Mod <m> -Src <WT>\re\harness\src -Out <TREE>\re\harness\inst_<name>"
```
Launch (logs land in the instance folder), and read the pid from the process you started:
```
$env:SC3MODS_DIR="<TREE>\re\harness\inst_<name>"; $env:SC3MODS_MULTI="1"; $env:SC3RESIZE_WINMEM="0"
$p = Start-Process -FilePath "<TREE>\Apps\SC3U.exe" -WorkingDirectory "<TREE>\Apps" -ArgumentList '"<TREE>\Cities\<city>.sc3"' -PassThru
```
Set `SC3_PID=$p.Id` for every sc3io-based tool. The first start of freshly built DLLs takes about 24 s (Defender scans
each new file). Never add Defender exclusions, never restore quarantined files: report to the orchestrator.
Frida: any NativeFunction that makes the game DO something uses `{exceptions: 'propagate'}` (memory
project-rblab-cam-zoom-deadlock). Pictures: `SC3RESIZE_FRAMEDUMP` (desktop grabs are stale while the PC is in use).
Load City lists `MAIN\Cities`; reach your tree with "Buscar en", or pass the city on the command line.

HARD RULE (owner 2026-10-25): never take over the real mouse, keyboard or foreground. No SetCursorPos, mouse_event,
SendInput, keybd_event, SetForegroundWindow or topmost raising. Drive the game with posted messages (sc3io posted input,
PostMessage) or Frida game calls only. Anything that needs a real cursor goes on a "needs owner check" list.

TEST SLOTS (workspace rule 2026-10-26): LIVING-PC runs at most 2 test runs at a time across all sessions. Wrap every
game-harness batch / soak / A-B loop: bash `test-slot bash -c '<command>'`, PowerShell
`py -3.12 C:\Users\maria\Desktop\Proyectos\.claude\scripts\testslot\proyectos_test_slot.py pwsh -NoProfile -Command '<command>'`.
On claude2 the hook that enforces this does not run: follow it yourself. "[test-slot] all N test slots busy, waiting" is the
queue, not a hang. One quick single launch may skip it with PROYECTOS_TEST_SLOT=off.
