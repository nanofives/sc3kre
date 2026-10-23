# Child protocol, 2026-10-23: owner hand-test bugs (scaled UI, UI toggle, FPS overlay, 1024 reload)

You are one child of the orchestrator session titled **"SC3: owner bugs 10-23 (minimap, UI toggle, FPS overlay, 1024
reload)"** (find it with `mcp__happy__list_peers`). The owner tested the LAN build (`Proyectos\Simcity` on MARIANO-PC,
2560x1440 primary at dpi 120, NVIDIA, HUD scale Auto) and reported 4 problems. Each child owns ONE (table below).
MAIN = `<workspace>\Simcity` (on this PC, LIVING-PC).

Rules as `re/sessions/CHILD_PROTOCOL_2026-10-21_ownerbugs.md` and `CHILD_PROTOCOL_2026-10-18_highways.md` sections 1-4:
claude2 policy (no git add / commit: the orchestrator commits by path; launch via `cmd //c` or `pwsh -c`), never kill by
name, only your own PID, always windowed (`SC3RESIZE_WINMEM=0` or check `sc3resize.ini [window] fullscreen`), light
testing (memory `feedback-light-testing`), the owner reviews pictures, STATUS file `MAIN\re\sessions\STATUS_<name>.md`,
message the orchestrator at every milestone. Use `SC3RESIZE_FRAMEDUMP` for pictures (desktop grabs are stale while the
PC is in use). Several children run games at once: `-multi`, `SC3_PID` set, 15 s between launches.

## Your paths (already created from main `eeb27ce`)
| what | path |
|---|---|
| worktree (edit ONLY here) | `<workspace>\Simcity_wt_<name>`, branch `child/<name>` |
| test tree (hard-linked copy of `Simcity_release` = the LAN build the owner ran, with `mods\netmod`; `Cities\Europolis 1024.sc3` included) | `<workspace>\Simcity_stock_<name>` |
| instance folder | `Simcity_stock_<name>\re\harness\inst_<name>\` (`perf.ini`, `menu_bg.bmp`) |

The tree's `Apps\` has NO mod DLLs and its own unlinked `version.dll` (the loader). Build ALL mods from your worktree into
the instance folder (the owner's game runs all of them):
```
for m in mods_launch sc3resize sc3bigcity sc3overscroll sc3simrun sc3perf sc3netmod sc3undo:
  pwsh -NoProfile -Command "$env:CL=$null; & <WT>\re\scripts\build_mod.ps1 -Mod <m> -Src <WT>\re\harness\src -Out <TREE>\re\harness\inst_<name>"
cmd //c "<TREE>\re\harness\inst_<name>\mods_launch.exe -multi -- <TREE>\Cities\<city>.sc3"
```
Never put a mod DLL in the tree's `Apps\`. Never edit a hard-linked file in place (copy first). Logs land in the instance
folder. Test the owner's window size class too: maximized on a large client, so the HUD factor is above 1.

## Streams
| stream | owner report | expected |
|---|---|---|
| `minimap` | "on scaled UI I want the renderer of the minimap to be natively rendering at the size of the new UI so it doesn't look pixelated / a lot of antialiasing" (`MAIN\verify\minimap\owner_shots\img1_minimap_scaled.png`: the minimap diamond enlarged by HUDSCALE, blurry) | with HUD scale above 1, the minimap's map image is drawn by the game (or by us from the city data) at the enlarged size, so its pixels are 1:1 on screen, while the frame, buttons and click mapping keep working. Find where the minimap image is built (SIMUI / minimap vt, memory `project-undo-mod` has minimap vt 0x100aa180, sc3resize MINIMAP notes, HUDSCALE in `re/analysis/HUD_SCALE.md`) and whether its size can be raised, or a second render at the scaled size made. Report the options with cost before a big rework |
| `uitoggle` | "hiding / unhiding UI has a major delay / freeze on the game" | find the hide/unhide UI control (the HUD toggle), reproduce at the owner's size class with HUD scale Auto, measure the stall (log timestamps, sc3perf BUSY lines), find which work runs on toggle (HUDSCALE tables, surface re-creation, layout, DLGSCALE caches, the city view resize) and cut it. Compare with HUD scale off and with all mods stock (SC3RESIZE_HUDSCALE=0 etc.) to place the cost |
| `perfscale` | "de-maximizing windowed game makes the FPS / Profiler not scale" | the sc3perf FPS counter / profiler text (UISCALE, reads `sc3resize_ui_scale` / `sc3resize_menu_rect`, memory `project-dialog-overlay-scale`) keeps the right scale and position through maximize -> restore -> maximize, in a city and at the menu |
| `reload1024` | "I retried to load Europolis 1024 for a second time after I loaded it once and the game crashed" (logs of the owner's run in `MAIN\verify\reload1024\owner_log\`: after ~4 min in the city, the load tore down the traffic grids (`sc3perf TRAFFIC_SMOOTH> traffic grids being destroyed`, `TRANSIT_CLEAR`), then `VEH FAULT 0xC0000005 at STRTSIM.DLL+0x11908, access=READ addr=0x00000008`, stack STRTSIM+0x118D2 < +0x11407 < +0x11099 < +0x10EB3 < GZServiceD+0x39D7) | load Europolis 1024, play a while, load it again (Cargar Ciudad, same city) without a crash, also 256 -> 1024 and 1024 -> 256. Find which mod's state survives the unload (sc3perf traffic threads / hash index / list_find caches, sc3bigcity wider lists, sc3netmod, sc3undo logs) and leaves STRTSIM reading a freed or zeroed object. Check first whether stock + only sc3bigcity + sc3perf reproduces it, then add mods back |

## Milestones
1. **Reproduce + cause** (light): the owner's case in your tree, the log lines, the code path, the exact cause. Message
   "cause found" with a 3-line summary (and a frame dump where a picture helps).
2. **Fix**: in your worktree, one in-game check of the owner's case + its neighbours, pictures into
   `MAIN\verify\<name>\owner_shots\`, `verify/<name>/RESULTS.md`, files to commit listed in STATUS. Message "fixed".
Do not change behaviour the owner did not report unless your fix needs it; if it does, say so in the message.
`minimap`, `uitoggle` and `perfscale` may all touch `sc3resize.c`: keep your changes in their own block with an off
switch (`SC3RESIZE_<NAME>=0`), so the orchestrator can merge them.
