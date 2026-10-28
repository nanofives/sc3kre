# modspage: "Opciones de mods" page inside Preferencias (2026-10-27)

Owner request 2026-10-27: "la opción de auto-guardado tiene que ser desactivable en el menú de opciones, hacé un
submenú dentro de preferencias con todas las opciones de los mods".

## What it does

- Preferencias has a new "Opciones de mods..." button in "Opciones generales". A click turns the same window into a
  mods page (the game's controls hidden, the title bar kept); "Volver" brings the game's page back. OK and the close
  box work from both pages with the existing rules: OK applies, anything else keeps.
- Mods page sections (a section appears only when its mod is loaded):
  - Interfaz: interface scale (Auto, Normal, 125%, 150%, 200%), Suavizado, Zoom extra (moved from the game page).
  - Rendimiento: Ver FPS, Ver perfilador (moved from the game page).
  - Autoguardado: Autoguardar on/off, Mostrar aviso, Cada 5 / 10 / 15 / 30 min. Applied at once: OK writes
    `autosave.ini`, and sc3autosave re-reads it within a second when the file changes.
  - Al reiniciar el juego: "La ciudad sigue al mover la cámara" (`simrun.ini [sim] run_while_scrolling`),
    "Cámara más allá del borde" (`overscroll.ini [camera] overscroll`, 50 = off, the mod's floor), "Mover en el
    borde" (`overscroll.ini [edge] enabled`), "Deshacer (Ctrl+Z)" and "Botones de deshacer" (`undo.ini [undo]
    enabled / buttons`). These mods read their ini once at start.
- OK writes only the settings the player changed.

## How

`sc3resize.c` MODSPAGE block (`SC3RESIZE_MODSPAGE=0` turns it off). Built on the HUDOPT detours of SIMUI
`FUN_10055e07` (dialog messages) and `FUN_100562b1` (close). A button click reaches the command handler
`FUN_10058f14` as message 3, p3 1, p4 = control id [CONFIRMED @ SIMUI 0x10055e07]; our two buttons
(`0x02F95B51` / `0x02F95B52`) are taken there. `FUN_10058f14` itself starts with `mov eax, imm32` + `call` (EH
prolog), so it is not detoured. Controls: the game's widget factory (checkbox +0x3c, option group +0x48, label +0x44,
text button +0x2c). Page switch: window vt+0xf4(1, 0/1) on every game child except OK and the title bar (local
top < 30). New ids `0x02F95B51..0x02F95B64`. The game builds a new Preferences window on every open (two opens
logged two different windows), so the page always starts on the game's.

`sc3autosave.c`: the watcher always runs (enabled=0 only stops saving), and re-reads `autosave.ini` when its write time
changes (also when the file appears after start); the indicator thread always runs.

## Check (dev/autosave tree, Craterville, 2560x1351, HUD 2.25x, posted clicks only)

| step | result |
|---|---|
| open Preferencias | "Opciones de mods..." in Opciones generales, the scale / FPS / zoom boxes gone from that page |
| click it | `MODSPAGE> mods page`: all sections drawn, title bar and close box kept, accents right |
| untick Autoguardar, OK | `MODSPAGE> OK: 1 mod setting(s) written`, `autosave.ini enabled=0`, sc3autosave `INI> autosave.ini changed: enabled=0` |
| reopen, mods page, Volver | `game page`, every game control back |
| mods page, tick Autoguardar, OK | `enabled=1`, `INI> ... enabled=1` |
| reopen after closing on the mods page | a new window, game page shown |

HUDOPT / PERFPREFS / CITYZOOM still read back and save on OK from the mods page (`HUDOPT> OK`, `PERFPREFS> OK` logged).

Not checked: the restart options actually changing behaviour after a restart (each only writes the ini key the mod
already reads), cancel with Esc from the mods page, the English text.
