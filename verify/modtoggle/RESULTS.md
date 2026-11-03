# modtoggle: turn mods and features on/off from the mods page (2026-11-03)

Owner request 2026-11-03: "on the mods options add a feature to disable mod features".

## What it does

- The mods page ("Opciones de mods") has a new "Activar mods..." button, top right. It opens a third page with one
  checkbox per mod DLL (left, 10 rows) and per feature (right, 11 rows). "Volver" goes back to the mods page.
  OK writes what changed, anything else keeps (the MODSPAGE rule). Applies at the next start.
- Saved to `<mods dir>\sc3mods.ini` (beside sc3mods.dll / the mods):
  - `[mods] <dll>=0`: sc3mods.dll does not load that DLL. sc3resize.dll has no row and is never skipped (it hosts the
    page), even if the file says `sc3resize.dll=0`.
  - `[env] NAME=0`: sc3mods.dll sets NAME in the process environment before any mod loads, unless NAME is already set
    (a harness or the user's env wins). Each row maps to the off-switch the code already had:
    PLACEHINTS, STATIONWARN, GRAPHAXIS+GRAPHNEW+GRAPHTABS, VERDATOS_NATIVE, RCIBARS, PICKER, QUERYID, UITOGGLE,
    PAUSEKEY+SPEEDKEYS (all `SC3RESIZE_`), SC3SIMRUN_CHURN, SC3SIMRUN_SIRENS.
  - Turning a row back on deletes its keys, so the file only lists what is off.
- Off switches: `SC3RESIZE_MODTOGGLE=0` (no button/page), `SC3MODS_INI=0` (loader ignores the file).
- Strings: 27 keys `resize.mt_*`, es/en extracted, fr/de/it/nl/sv machine-translated (`sc3lang.py check` clean).

## Check (dev/modtoggle tree, Craterville, 800x600 windowed, posted input only, FRAMEDUMP)

| step | result |
|---|---|
| ini `[mods] sc3landfill.dll=0, sc3resize.dll=0`, `[env] SC3RESIZE_PLACEHINTS=0`, start | sc3mods.log: `[env] SC3RESIZE_PLACEHINTS=0`, `[-] sc3landfill.dll turned off`, sc3resize loaded anyway, `10 mod(s) loaded`; resize.log `PLACEHINTS> off` |
| Preferencias -> Opciones de mods -> Activar mods | `turn mods on/off page`: both columns drawn, Vertederos and Ayudas al colocar unticked (read from the ini), rest ticked |
| tick Vertederos, Volver, Activar mods again | mods page, then page C again, one click each |
| OK | `MODTOGGLE> sc3landfill.dll on at the next start`, `OK: 1 mod setting(s) written`; the `sc3landfill.dll=0` line gone from the ini, PLACEHINTS=0 kept |

Not checked: a second start after the page write (the loader side was checked from a hand-written ini), the English /
other-language layout widths, Esc from page C.

Known: test tools with a fixed DLL list (`sc3wait.py`) wait for every DLL and will not see a disabled one. Turning off
sc3bigcity or sc3netmod and then loading a city that needs them is the player's call; the page says so.
