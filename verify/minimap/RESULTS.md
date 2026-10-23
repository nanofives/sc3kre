# minimap: the map drawn by the game at the HUD factor (child/minimap, 2026-10-23)

Owner report: "on scaled UI I want the renderer of the minimap to be natively rendering at the size of the new UI so it
doesn't look pixelated / a lot of antialiasing" (`owner_shots/img1_minimap_scaled.png`).

## Cause (SIMUI decompilation)

- The minimap window (vt `0x100aa180`, 160x164) holds a generic map-view child (factory id `0x5a9`, ctor `FUN_10042866`,
  vt `0x100a7e68`) at `(14,15)`, 129x129 (`FUN_10050de2`, SetRect `FUN_10043afc` forces an odd square).
- The map view's Draw (`FUN_10043937`, vt+0x144) blits a square texture rotated into the diamond. The texture side is
  `width * 0.70710677` quantised to 32/64/128/256 (`FUN_100436b4`, constants `0x100a7db4`, `0x100a8110..18`). Native: 128,
  so a 256 city shows 2x2 cells per texel squeezed to about 90 px per axis.
- sc3resize HUD scale then enlarged that 160x164 picture (bilinear + EPX). Enlarging an already reduced picture is the blur.

## Fix (sc3resize.c, MININAT block, `SC3RESIZE_MINIMAP_NATIVE=0` turns it off)

While the HUD factor s is above 1, a twin of the minimap's map view is made with the game's own Clone (iface vt+0x10
`FUN_10042aec`: layers, rotation, view box), sized `2*round(64 s)+1` with its own raster (vt+0x170). The game draws it every
time it draws the native map view (vt+0x144 wrapped). The HUD pass copies the twin's pixels 1:1 over the enlarged map,
only where the twin drew and where the frame's native pixel is still the map's own pixel, so the zoom, rotate and layers
buttons drawn over the map keep their enlarged copy. Native layout and click mapping are not touched.

The twin is re-cloned when the native view's rotation or layer list changes, resized when the factor changes, and freed
before the minimap drops or rebuilds its map view (messages `0x311fdae5` / `0x511fdae5` / `0x45462fd2` to the minimap's
vt+0xc `FUN_100507ad`: measured, the minimap itself survives a city load) and when the minimap shuts down (vt+0x28).
Hooks are installed from the first enlarged HUD pass, not at DLL map time.

## Check (Simcity_stock_minimap, all 8 mods built from the worktree, windowed, HUD scale Auto)

| case | result |
|---|---|
| 2528x1312 client, factor 2.187 | twin 281x281, texture 256 (native 128). `03_ab_2187.png`, `04_ab_2187_zoom3x.png` (left: before, right: after) |
| maximized 3840x1984, factor 3.307 | twin resized to 425x425, view box complete with 1 px lines. `05_on_3307_maximized.png`, `06_on_3307_viewbox_zoom3x.png` |
| restore to 2.187 | twin back to 281x281, drawn for the new factor within 1 s |
| rotate (PageDown) | rotation 135 -> 45, twin re-cloned, map rotated. `07_on_rotated.png` |
| Cargar ciudad Europolis -> Berlin -> Europolis | twin freed on "the minimap drops its map view", a new one made for the new city, no crash. `08_on_after_two_city_loads.png` |
| city layers dialog, "Vista de capas: Crimen" | the minimap keeps the zone picture, same as the control run with MININAT off (stock behaviour) |
| control `SC3RESIZE_MINIMAP_NATIVE=0` | the old enlarged copy (`01_off_2187.png`) |
| native vs scaled old vs scaled new, 2.187x | `09_native_old_new_2187.png` (native = `SC3RESIZE_HUDSCALE=0`) |
| Europolis 1024, 2.187x | twin 281x281, texture 256 = 4 cells per texel. Old: 8 cells per texel, enlarged, the road rings read as blobs. New: each district's road rings and blocks are visible, hard-edged pixels, no blur (`10`, `11`, `12_1024_old_new_zoom3x.png`) |
| click on the enlarged minimap (1024) | the camera moved to the clicked spot and the view box followed (`13_1024_new_after_minimap_click.png`). Near the diamond edge the box is clipped to the diamond, as the game draws it (`14`) |

Cost, 50 s still in Europolis at 2.187: compose 0.137 to 0.147 ms per frame (39,370 px), twin draw 0.35 to 0.47 ms each,
about 3.3 draws per second while paused. Pass total 2.80 to 3.79 ms per frame. The two control runs were not still
(clicks and dialogs in most beats): their first, still beats read 3.42 and 2.37 ms. The direct compose timer above is
the number to go by.

## Seen, not changed

- First load of the session (Europolis -> Berlin) logged 168 first-chance AVs in 2.4 s inside `IsBadReadPtr`, called from
  existing `rz_poll` (+0x8f, reading `g_bridge+0x18`, the old city's iso view) and `rz_hs_city`, while the load dialog was
  up. The read address `0x65757020` is ASCII text, so the freed iso view memory had been reused. The game continued and
  loaded. The second load in the same game logged 0, and no other session log on this PC has that fault. Freeing the
  twin changes the heap layout during the load, which is the likely reason it showed here first. The stale `g_bridge`
  read is older than this change. Worth a look by the reload1024 stream.
- The texture tops out at 256 texels (the game's quantiser). At 2.187x the diamond is about 199 px per texture axis, so a
  256 texture is drawn at 0.78 px per texel: on a 1024 city one screen pixel spans about 5 cells per axis. A texel
  reaches 1 px at about 2.83x, so raising the cap (patch `0x100a8110`, all map views) would add detail only above that.
- Between factors 1.01 and 1.41 the twin gets a 128 texture (same detail as native, drawn 1:1 without blur).
