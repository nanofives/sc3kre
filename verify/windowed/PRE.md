# windowed: pre-registration (2026-10-12, before any run)

## Question
Owner: on a STOCK install (stock GZGraphicD.dll / SIMSPR.DLL) + release sc3mods-2026-10-12 started with
mods_launch.exe, the game was not windowed and the "escalado" was missing. On this PC every owner test ran on
MAIN\Apps, whose GZGraphicD carries on-disk recipes resizable_frame + close_button_quit.

## Hypotheses (each with what would falsify it)
- H1 race: the windowed byte GZGraphicD+0x6cdac lands after GZGraphicD Init (FUN_100114b8) reads it.
  Three mods write it: sc3bigcity and sc3overscroll poll every Sleep(1), sc3resize every 100 ms after BOTH
  SIMSPR and GZGraphicD are mapped. Falsified if, over >= 5 cold stock launches, every log shows the first
  WINDOWED line with value 0 -> 1 and the window comes up windowed.
- H2 runtime style: without resizable_frame the live style slammed by FUN_1001854a (push 0x90C80000) has no
  WS_THICKFRAME. sc3resize adds it at runtime (rz_make_resizable). Falsified if on stock the window has
  WS_THICKFRAME (0x00040000) and a WM_SIZING resize changes the client size.
- H3 something sets the flag back: FUN_10010ef2 (vtable setter of DAT_1006cdac) called by the game with 0
  after the mods wrote 1. Check by a read-only Frida hook if H1/H2 do not explain a failure.
- H4 not a mod failure: "escalado" = the HUD scale option (HUDOPT, branch child/hudfix, NOT in release
  sc3mods-2026-10-12) or Windows DPI scaling of a DPI-unaware window on a 125-150% laptop panel.

## Measurements
Per run: launcher + every mod log, the game window's style / client size / DPI awareness over time (wrun.py),
screenshots at 5/15/30/40 s, LOOKED at. Stock = Simcity_stock\re\harness\inst_windowed with the release
binaries. Control = MAIN\re\harness\inst_windowed with the same release binaries (patched GZGraphicD).
Cold launches: no city (as "Jugar con mods.bat") and with Europolis.

## Pass bar for a fix
>= 5 consecutive cold stock launches windowed + resizable (style has WS_THICKFRAME, resize_client changes the
client and the view follows), logs show the windowed byte written before Init reads it.
