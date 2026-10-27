# sc3autosave: save the city every 5 minutes (2026-10-27)

Owner request 2026-10-27: "auto-save feature every 5 minutes".

## What it does

- Every `minutes` (default 5) of wall time with a city loaded, the city is saved with the game's own Save command
  to `<city folder>\<city>.autosave<N>.sc3`, N = 1..`keep` (default 2). Empty slots fill first, then the oldest is
  overwritten. A city never saved goes to `<game>\Cities\Untitled.autosaveN.sc3`.
- The player's own file is never written. The city's file name is put back after each autosave, so the player's
  Save still goes to their file, and the game still asks "save changes?" on quit (the menu save's post-success call
  `thunk_FUN_0045d5ae()->vt+0x40(0)` is not made).
- Each save goes to `<city>.autosave<N>.tmp.sc3` and is renamed over the slot only if the command reports success,
  so a failed save never destroys the previous autosave. A save byte-identical to the newest autosave (a paused,
  untouched city) is deleted.
- Loading an autosave and playing on autosaves back to `<city>.autosave<N>.sc3`, not `.autosave2.autosave1`.
- Put off one second at a time while: a mouse button is held or captured (a drag), a text field has focus, the city
  appeared less than 20 s ago, or the city lock counter `city+0x144` is nonzero (the game is saving).
- Loading another city, or starting a new one, restarts the interval.
- **Idle wait (2026-10-27, round 2).** A due save waits until there has been no mouse or keyboard input on the game
  window for `idle_seconds` (default 3). After one more full interval without such a pause it saves anyway.
- **No "Guardando..." box on autosaves (round 2).** The game's progress box is replaced by a small "Autoguardando..."
  indicator with a bar in the game's top-left corner, then "Autoguardado HH:MM" for 2 s. The player's own Save and
  Load still show the game's box. Hiding the box cut the freeze from 1.6 - 2.7 s to about 0.3 s on Frankfurt.

## How (static evidence)

| piece | address | source |
|---|---|---|
| Save command, CLSID `0x410438DD`, one string arg | SC3U `0x004108f3` (the File menu save) | `[CONFIRMED @ 0x004108f3]`, first used by sc3undo snapshot mode (`verify/undo_spike/`) |
| hold / release around the command | city vt+0x21c `SIMCITY 0x100058ac`, vt+0x220 `0x1000590e`: `city+0x144` +1 / -1, sim object `+0x130` vt+0x2c / +0x30 | `[CONFIRMED @ 0x100058ac, 0x1000590e]`, same calls the menu save makes |
| city file name get / set | vt+0x254 `0x10007116` (string at city+0x15c), vt+0x258 `0x1000713b` | sc3undo v1 |
| `DoSaveCity` slot 49 | `SIMCITY 0x1000ebe6` | a stub, `return 0`. Not the save path |

Round 2 (box and indicator):

| piece | address | source |
|---|---|---|
| city Save, the handler of message `0x111fdae5` the Save command posts | SIMCITY `0x1000429d` (city vt+0x20, dispatched in `0x10002fa6`) | `[CONFIRMED @ 0x10002fa6]` |
| progress box: `FUN_10002678(steps, string 0x2dd)` at `city+0x1a4` | SIMCITY `0x10002678`, step `0x100026e4`, close `0x100026a8` | `[CONFIRMED @ 0x10002678, 0x100026e4, 0x100026a8]` |
| progress service `FUN_1000edff()`: vt+0x88(total, title) open, vt+0x8c(step) advance + redraw, vt+0x90() close | vtable at SC3U `0x004CF59C`, methods `0x004032F0 / 0x00403410 / 0x004034D3` (measured at run time) | the mod wraps the three slots, pass-through unless an autosave is running |

The indicator is a separate small window (own thread, `WS_EX_NOACTIVATE | WS_EX_TRANSPARENT | WS_EX_LAYERED`): GDI drawn
on the game window itself never reached the screen (desktop grab during a held save showed the frozen frame, no box).
It goes above the game only: topmost when the game window is `WS_EX_TOPMOST` (seen as ex-style `0x108`), else only when
the game is the foreground window. It never takes focus and clicks go through it.

The command appends `.sc3` to a path that does not end in it (first run wrote `...autosave1.sc3.tmp.sc3`), hence the
`.tmp.sc3` temp name.

## Measured (dev/autosave tree, Frankfurt, Germany 690 KB, `SC3AUTOSAVE_SECONDS=30`, windowed)

| run | result |
|---|---|
| loaded paused | #1 written (705,743 B, 2,500 ms). Next two: "unchanged, dropped" (2,656 / 1,781 ms) |
| unpaused (posted P) | #2 to slot 2, #3 to slot 1, #4 to slot 2: 1,640 - 2,031 ms each. Sim still running after each (pause depth 0) |
| name check after every save | no "NOT restored" line: name stays `...\Frankfurt, Germany.sc3` |
| player file | `Frankfurt, Germany.sc3` unchanged (mtime 2000-04-18) |
| load `Frankfurt, Germany.autosave2.sc3` | loads and renders (`owner_shots/autosave2_loaded.png`: Frankfurt, pop 491,851, 1/16/2056). Its next autosave went to `Frankfurt, Germany.autosave1.sc3` |

Cost (round 1, game box shown): the game froze 1.5 - 2.7 s per save on this city.

### Round 2: box replaced by the indicator, idle wait

| run | result |
|---|---|
| paused, box replaced | 343 ms (round 1, same city paused: 2,500 ms) |
| sim running, box replaced | ~281 ms (4,281 ms minus the 4,000 ms `SC3AUTOSAVE_HOLD` test hold). Sim still running after |
| indicator | drawn (`owner_shots/indicator.png`: "Autoguardando..." with bar, then "Autoguardado 18:19"), captured with PrintWindow under `SC3AUTOSAVE_INDFORCE=1` because the game was not in front on the shared PC |
| no leftovers | city view clean right after the save (no box, no stale pixels) |
| idle wait | posted mouse moves every 1 s for 40 s: due at 138.3 s, log "due, waiting for 3 s without input", saved at 150.4 s, 3 s after the last move |

Freeze now ~0.3 s on this city. Bigger cities take longer.

## Not checked (owner check)

- An autosave firing while a game dialog is open (budget, query, Load City list).
- A city never saved (`Untitled`).
- 1024 cities: the freeze length.
- The indicator over the game while it is in front (seen here only through PrintWindow), and its size on a
  high-DPI screen (176x36 physical pixels, same scale as the game's own 800x600 window).
- The player's own Save and Load still show the game's "Guardando..." box (the wrap passes through; not clicked here).

## Settings

`autosave.ini` beside `sc3autosave.dll` (optional, not shipped; defaults apply without it):

```
[autosave]
enabled=1
minutes=5
keep=2
dir=          ; empty = next to the city file
idle_seconds=3
indicator=1   ; 0 = no indicator (the game's box is still hidden on autosaves)
```

Test overrides: `SC3AUTOSAVE_SECONDS=<n>`, `SC3AUTOSAVE_LOG=<path>`, `SC3AUTOSAVE_HOLD=<ms>`, `SC3AUTOSAVE_INDFORCE=1`. Log: `sc3autosave.log` beside the DLL.

## Files

`re/harness/src/sc3autosave.c` (new). Added to the mod lists in `sc3mods.c`, `sc3modldr.c`, `mods_launch.c`,
`re/scripts/build_mod.ps1`, `re/scripts/sc3dev.ps1`, `re/scripts/lan_release/stage_lan_release.py`.

## Parked: background save by process clone

Tried 2026-10-27 at owner request, branch `child/autosave-clone` (e092d1f), off by default. RtlCloneUserProcess works on
the game (held 10-30 ms) and the clone runs the save, but it needed a workaround per Windows layer (window manager,
locale data, DirectDraw, graphics driver, network) and still idles ~27 s and dies in an IMM32 thread exit without
writing a file. Parked by owner call in favour of the indicator + idle wait above.
