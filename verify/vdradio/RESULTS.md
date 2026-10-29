# vdradio: Ver datos option radios ignored with the HUD scaled up (owner report 2026-10-29)

Owner report: "cambiar el mapa de contaminación no funciona cuando está grande la UI". In Ver datos, "Mapa de
contaminación", picking "Polución aire / Agua / Basuras" did not change the map with the interface enlarged.

## Cause (sc3resize VERDATOS)

VERDATOS draws a twin of the Ver datos map view (a Clone of the view) at the dialog's factor and pastes it over the
enlarged dialog. A panel's radios show one layer of the view and hide the others through the view's ShowLayer /
HideLayer, SIMUI `0x10043252` / `0x100432ba` (all: `0x10043288` / `0x100432f0`). Those set byte +0xc of the layer wrapper
(vt `0x100a811c`, setter vt+0x1c `0x10043c3e`, getter vt+0x20 `0x10043c48`) and the view's dirty byte. The texture
render `0x10043882` and the draw `0x10043937` skip a wrapper whose +0xc is 0.

Measured with the new `SC3RESIZE_VDRADIO_DIAG=1` log (Berlin, pollution panel): the native view holds 4 wrappers
(terrain, air, water, garbage) with shown bytes `1 1 0 0`, and its fresh twin had `1 1 1 1`. The twin drew every layer
stacked from the first frame. A radio changed the native map underneath, but not the twin pasted over it. The twin's
change signature (`mn_state`) hashes only the list pointers, so a shown-byte change also never caused a redraw.

VDSCROLL is not the cause. On the release build, each radio logged `VDSCROLL> twin redraw (at once): native pixels
changed`, and the twin redrew the same stacked layers. DLGSCALE input is fine: the radio state changes in the picture.

## Fix (sc3resize.c, new block VDRADIO, `SC3RESIZE_VDRADIO=0` turns it off)

- At the clone, the native view's shown bytes are copied into the twin's wrappers. Twin and native wrappers share the
  inner layer object (+8, `0x10043bc4`), so they pair by it whatever the list order.
- The shown bytes are part of the twin's signature (`vd_shown`). A change copies them again and redraws the twin at once
  with its texture re-rendered, with no re-clone (orchestrator's request: a re-clone costs up to ~0.4 s on a 1024 city).
- If the wrappers do not pair, a change frees the twin and the next draw clones it again (the old path).

## Check (dev/vdradio/tree, all 8 mods, Berlin, client 2560x1351, HUD 2.252x, dialog 2.250x, posted clicks only)

Driver: `re/tools/vdradio_lab.py` (opens Ver datos, picks a data view, clicks the radios, dumps frames via FRAMEDUMP).

| run | build | pollution map per radio (aire / agua / basuras / aire again) |
|---|---|---|
| B_on | release 10-29c | the same map for all four frames (the stacked layers) |
| C_vdoff | `SC3RESIZE_VERDATOS_NATIVE=0` (control) | 3 different maps: air heavy blobs, water light blobs, garbage terrain + landfill |
| F_fix | VDRADIO | the same 3 maps as the control, drawn sharp; "aire" again returns the air map |

F_fix log: `VDRADIO> twin ...: 2 shown byte(s) taken from its map view at the clone`, then per radio
`showed / hid a layer: 2 shown byte(s) copied into the twin` and `twin redrawn with the new layer in 25.8 to 27.6 ms`.

Other panels:

- Criminalidad ("Cobertura de Policía", a single radio that is already on): with the fix and with `SC3RESIZE_VDRADIO=0`
  the map is the same. A click changes nothing, as in stock. The fire panel has the same single radio (not clicked).
- Europolis 1024, all 10 panels dumped with the fix (`5_europolis1024_all_panels_vdradio.png`): each panel draws. This
  city has no pollution data, so its 3 pollution maps are flat and only the timing counts.

Timing of one radio switch, Europolis 1024 (texture 1024): `twin redrawn with the new layer in 235.1 ms` and `227.0 ms`
(2 switches). That is one twin redraw at texture 1024, with no clone on top.

Pictures (`MAIN\verify\vdradio\owner_shots\`, not in git; each strip is in click order: panel, radio 1, 2, 3, radio 1 again):
`1_before_pollution_radios_release_10-29c.png`, `2_control_pollution_radios_verdatos_off.png`,
`3_after_pollution_radios_vdradio.png`, `4_after_crime_panel.png`, `4b_before_crime_panel.png`,
`5_europolis1024_all_panels_vdradio.png`.

## Not checked / open

- Only the pollution panel hides layers among the ones clicked. Other panels whose default state hides a layer would
  have shown every layer stacked before this fix. The fix copies the bytes at the clone, so they now match too. Not
  checked panel by panel.
- MININAT (the minimap's twin) uses the same Clone and is likely to start with every layer shown too. No minimap layer
  bug was reported, so it was not changed.
- On Europolis 1024 the twin is freed `unused for 1 s` several times while the dialog stays open, then cloned again. This
  was already the case before this fix and it does not affect the result.
