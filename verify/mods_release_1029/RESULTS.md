# RESULTS - sc3mods release 2026-10-29 + LAN republish

Replaces `sc3mods-2026-10-28e`. Owner reports 2026-10-28: "i'm not able to place road over these residential buildings",
"some cars are rendering over the trees" (owner call: fix, stock avenue included, then release). Source as of `596fc53`.

| what | commits | record |
|---|---|---|
| ROADOVER: road / rail / highway / power drags demolish zoned buildings under valid cells, bulldoze charged once per building, undo restores, under "Construir sobre zonas" | 783a8ba | verify/roadover/RESULTS.md, re/analysis/ROADOVER.md |
| cartrees: far-carriageway cars behind median trees (tree layer art built at install, avenue_lanes 0.4.0, look-only 21742 for two-way straights, AVP paints them) | 596fc53 | verify/cartrees/RESULTS.md, re/analysis/NET_ART.md 8.2 |

Shipped: sc3resize.dll, sc3netmod.dll, mods/netmod/** (avenue_lanes 0.4.0 as installed in stage/src by cartrees), README.txt.

## Stage and checks

- `stage/bins_1029` = `stage/bins_1028e` + sc3resize / sc3netmod built from main. Label `2026-10-29`, 3,607 files, 697.4 MB.
- Launch check (stage/release patched, windowed, no input): Seoul, `8 mod(s) loaded`, `RELOCATE> on`, `ROADOVER> on` chained after
  sc3netmod's predicate wrappers, table `variant 21742 -> base 11204`, `stats: avl ... cells written=1526` and
  `avp ... cells painted=580` (the same counts cartrees measured), only the benign `0xC0000096 @ SC3U+0x84122`. Then `-Restore`,
  logs deleted, 3,607 manifest files re-hashed: 0 changed, 0 missing, 0 extra.

LAN: 66 of 3,607 files sent (55.3 MB, the netmod overlay rebuilt by the pack change). Served label `2026-10-29`.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/sc3resize.dll | 464384 | 4EC3E5143B5D2F0D8D3B6B86CBD9E0B3FB245E2A66F19BB2BA2E3E1D1E3F1C2C |
| Apps/sc3netmod.dll | 411136 | 9307EB0DF0C7BFCE9A3B9503A86F82DEB6870A693191449C3D9C6494C8EF5179 |
| mods/netmod/** | | as stage/release (zip files cmp-equal) |
| README.txt | | 2026-10-29 section |
| every other file | | as `verify/mods_release_1028e/RESULTS.md` |
| `sc3mods_2026-10-29.zip` | 43,684,012 | 63761CC1EA6052BD0F976AC948677CE02CA8A52A3908D6F8059BEC71C9DF286C |

Not tested: a highway drag over houses, slope/water refusals during a road-over drag, avenue trees at zooms 0..3 in game (offline pixel check only).
