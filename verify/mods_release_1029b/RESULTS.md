# RESULTS - sc3mods release 2026-10-29b + LAN republish

Replaces `sc3mods-2026-10-29`. Owner requests 2026-10-29: zoning over another zone type's buildings and de-zoning demolish
them; "i need this S curve for highways". Source as of `c0c7157`.

| what | commits | record |
|---|---|---|
| ZONEDEMO (sc3resize): zone tools over other-type zoned buildings and DeZone over any demolish them, bulldoze charged and shown, one undo entry, under "Construir sobre zonas" | 1e6cceb | verify/zonedemo/RESULTS.md, re/analysis/ZONEDEMO.md |
| HWSC (sc3netmod) + highway_scurve pack: S curve for two parallel highways one cell apart overlapping 2..4 cells, drivable, saves as 15149 | c0c7157 | verify/hwyscurve/RESULTS.md |

Shipped: sc3resize.dll, sc3netmod.dll, mods/netmod/** (highway_scurve installed into stage/src by hwyscurve, 19 packs), README.txt.

## Stage and checks

- `stage/bins_1029b` = `stage/bins_1029` + sc3resize / sc3netmod built from main. Label `2026-10-29b`, 3,612 files, 706.0 MB.
- Launch check (stage/release patched, windowed, no input): Seoul, `8 mod(s) loaded`, `ZONEDEMO> on`, `ROADOVER> on`,
  `stats: avl ... cells written=1526` (same as 10-29). Faults: the benign `0xC0000096 @ SC3U+0x84122` and one first-chance
  READ at KERNEL32+0x2CF80 from sc3resize+0x239E7 under SIMSPR+0x4ECD3 (an IsBadReadPtr-style probe, game kept running).
  Then `-Restore`, logs deleted, 3,612 manifest files re-hashed: 0 changed, 0 missing, 0 extra.

LAN: 43 of 3,612 files sent (40.2 MB). Served label `2026-10-29b`.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/sc3resize.dll | 468480 | 7B45A371AE7E1031E2C236D2F9BA1ABFC070B91A6463DBC173D8054BB17D78A0 |
| Apps/sc3netmod.dll | 414208 | 11B2B45C1A22E6138AAC4583BE5ABA9B3886B4C6E095AEF5CB3B66972BA5827A |
| mods/netmod/** | | as stage/release (zip files cmp-equal) |
| README.txt | | 2026-10-29b section |
| `sc3mods_2026-10-29b.zip` | 50,220,725 | 76B0BA6FE8ED05BEC97E6446C4A9F8A8E95ADDA4178D9BA93E11032C0D9951A7 |

Open: startup crash GZGraphicD+0x14904 (null read in the blit dispatcher FUN_10014894) seen in 2 of 6 hwyscurve launches with
another game running (re/sessions/STATUS_hwyscurve.md), not routed yet. zonedemo reported sc3undo records only while paused
(not confirmed by the orchestrator).

GitHub: `sc3mods-2026-10-29b`, target `0b14467`, https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-10-29b, asset
downloaded back, SHA-256 matches. The 10-29 notes now start with a "superseded" line.
