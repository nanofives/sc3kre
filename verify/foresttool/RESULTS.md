# FORESTTOOL: "Bosque" button in the city's Paisaje flyout (child/foresttool, 2026-11-06)

Owner decision (re/analysis/COMMUNITY_MODS.md): Civic Deals' forestfill as a terrain-tool button.
Code: `re/harness/src/sc3resize_foresttool.c` (git add -f). Off: `SC3RESIZE_FORESTTOOL=0`. No button unless
SC3KCivicDeals.dll is loaded (installed by `re/tools/civicdeals_patch.py`).

## How

- The Paisaje flyout list is data (MenuItem.INI in SYS.PAK, 0xD1002000 = 0x2001..0x2006). After the stock fill
  (SIMUI FUN_1004bc7c) the category button's vt+0x1f8(0x2007) adds a 7th a917c button. Nothing in SYS.PAK changes.
- SIMUI 0x1004cdcd (icon + place per id) is wrapped: 0x2007 gets the trees icon's key at the 7th slot (y 237 at 600).
- Icon: the trees strip (144x36, 4 frames) is shared by every button with that key (same cSC3Buffer object, measured),
  so ours gets a new buffer drawn at run time from the game's own trees icon: the tree is lifted out and drawn three
  times at 62%. No EA art is stored in the repo.
- Paint: stock a917c GZPaint draws only the pressed / hover frames (+0xa4 bit 2 / bit 4); the normal icons are part of
  the flyout's art. At rest (+0xa4 0xa0, measured) ours draws frame 1 itself (vtable slot a917c+0x144 replaced, our
  button only).
- Click: FUN_1004c209 (a917c click, does nothing without a menu record) is wrapped for our button and sends
  "forestfill" through the game's cheat manager (frame -> Application -> QI 0xfa2 -> GetCheatCodeManager ->
  DoDefaultCheatCodeProcessing), the same path as the cheat box. "forestfill" is not yet registered while the side
  panel is built (measured), hence the DLL test.

## In game (dev/foresttool tree with Civic Deals, Craterville, 800x600, FRAMEDUMP)

| check | result |
|---|---|
| Paisaje flyout | 7th icon, three trees, at rest and under the pointer (`owner_shots/1_bosque_button.png`) |
| click | Civic Deals notice "Bosque terminado. Árboles plantados: 34568, casillas vacías revisadas: 49108"; the map is forested around the city, buildings and roads untouched |
| without the paint fix | icon only under the pointer (first build) |

Not checked: other window sizes (y 0x14e above 600 is the game's own 7th-slot value, not seen), HUD scale, a tooltip
(none: the button has no menu record), forestthicken (not wired, the cheat still works), an "Activar mods" row (the page's
feature column is full: a 15th row would overlap Volver; `--restore` of the Civic Deals install removes the button).
