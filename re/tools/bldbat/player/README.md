# Render Building Architect buildings (.bld) into real game pictures

A `.bld` file holds the Building Architect's model and one small preview, not the game's pictures. These tools let
your own Building Architect draw all four views of every `.bld` in a folder, in a window, and save them next to the
files. The building importer (the classifier page or `bldimport.py`) then uses those pictures. Works for SimCity 3000
Unlimited `.bld` files and for the older 1999 Building Architect ones.

## What is in the kit

| file | what it is |
|---|---|
| `render_bld.cmd` | drop a folder of `.bld` files on it |
| `render_bld.ps1` | what the .cmd runs |
| `baappw_patch.ps1` | makes `Apps\BaappW.exe` from your own `Apps\Baapp.exe` (run by render_bld.ps1) |
| `bawinonly.dll` | keeps the Building Architect in a window and runs the render |

No game file is shipped. `BaappW.exe` is made on your PC from your own `Baapp.exe`, which is never changed.

## Use

1. The sc3mods zip puts the kit in `tools\bld_render\` inside the game folder, and the scripts find the game's
   `Apps` folder from there. Kept anywhere else, pass `-Apps <game>\Apps`.
2. Close the Building Architect if it is open.
3. Drop the folder with your `.bld` files on `render_bld.cmd`.
   The Building Architect opens in an 800x600 window for one or two minutes (17 buildings took 65 s). Leave it alone:
   it closes by itself.
4. The folder now holds `bld_frames.ixf` (the pictures) and `bld_frames.txt` (what ran). Open the folder in the
   classifier page: each `.bld` shows its four views, and Install uses them.

The game's own `Apps\BARender\BAT.DAT` is never touched.

## Safety

- The Building Architect normally switches the screen to fullscreen. `bawinonly.dll` refuses every display-mode switch
  and exclusive mode before the display starts. If any byte it patches is not the one it expects, the Building
  Architect is closed before it shows anything.
- `render_bld.ps1` also reads every display's mode 50 times a second while it runs, and ends the Building Architect at
  once if one changes.
- Only the known Building Architect build (GOG 2.0.949, and its signed copies) is accepted. Any other `Baapp.exe` is
  refused with its hash: please report it.
- `powershell -ExecutionPolicy Bypass -File baappw_patch.ps1 -Remove` deletes `BaappW.exe` and `bawinonly.dll` again.

## Exit codes (render_bld.ps1 prints them)

| code | meaning |
|---|---|
| 0 | rendered |
| 0xBA0F | a display patch did not match: closed before the display started |
| 0xBA10 | no .bld files |
| 0xBA11 | the Building Architect menu did not appear in 120 s |
| 0xBA12 | the Building Architect is not the expected build |
| 0xBA13 | the Building Architect crashed while rendering |
| 0xBA14 | the renderer wrote nothing |
| 0xBA15 | bad output path |
| 0xBA16 | took longer than the time limit (30 min) |

Details for developers: `re/analysis/BLD_FORMAT.md` sections 5 to 7, `re/harness/src/bawinonly.c`.
