# RESULTS - sc3mods release 2026-11-09 + LAN 2026-11-09

Replaces `sc3mods-2026-11-08` (GitHub) and LAN `2026-11-08b`. Owner call 2026-11-09: "Release it now (LAN + GitHub)".
Source: main `7b69360`.

| what | commit | record |
|---|---|---|
| avdir step 1: AVP off by default (SC3NETMOD_AVP=1 = on), saved twins given back; avenue_markings uninstalled | 790a52c | verify/avdir/RESULTS.md |
| avdiamond group D: avenues under highway diamonds go one-way (SC3NETMOD_AVDIAMOND), package avenue_diamond 0.1.0 (20850..20861) | 03a9899..a072c20 | verify/avdiamond/RESULTS.md |
| hwt keeps road crossings under a T (twin 20858, guard, SC3NETMOD_HWTCROSS) | beca29d | verify/avdiamond/RESULTS.md |
| lanekit.rotate keeps slope alt (cars dropped on rotated slope pieces of avenue_lanes / boulevard_slopes) | 03a9899 | verify/avdiamond/RESULTS.md |

## Stage and checks

- Stage source: backup of the netmod-managed files + `mods/netmod` in `stage/src_bak_1109`. `netpack uninstall avenue_markings
  --tree stage/src`, then `netpack install dev/avdiamond/wt/re/tools/netmod/examples/avenue_diamond --tree stage/src --allow-tree`
  (the install recompiles every package's lanes with the fixed lanekit). `mods/netmod/overlay` + `tables` are byte-identical to
  the child's tested tree (dev/avdiamond/tree) except SYS.PAK (community inserts are applied at staging).
- `stage/bins_1109` = `stage/bins_1108b` with `sc3netmod.dll` rebuilt from main (`build_mod.ps1`, 447,488 bytes).
- `stage_lan_release.py --game stage/src --bins stage/bins_1109 --stock-modules original/modules --menu-bg
  stage/release/Apps/menu_bg.bmp --perf-ini stage/release/Apps/perf.ini --out stage/release_1109 --label 2026-11-09
  --community stage/community_1106`: 3,644 files, 711.4 MB. Against LAN 2026-11-08b: 84 changed (sc3netmod.dll + 83 netmod
  overlay files: TRBLKATT/VPATHATT 14, strings 7, tiling rules 9, Korea occupants, 52 sprite DATs), 2 added
  (`4E3D0034_netpack.DAT`, `tables/avenue_diamond.txt`), 1 removed (`overlay/Apps/Res/Sprites/CSATTRIB.IXF`, the
  avenue_markings reskin of stock 11204).
- Launch check (release_1109 patched, windowed, Berlin, no input, ~120 s): `11 mod(s) loaded`, avenue_diamond.txt variants
  20850..20861 read, hwt crossing twins 20858..20860, `avdiamond ... on`, `avp: ... off (default)`, ramp walks 82,
  0 bad table lines; only the benign `0xC0000096 @ SC3U+0x84122`. Then `-Restore`, 13 logs + dataview.ini + landfill.ini
  deleted, manifest re-hashed: 0 changed, 0 missing, 0 extra.

LAN: `deploy_lan_release.sh stage/release_1109` sent 86 of 3,644 files (73.8 MB). Served label `2026-11-09`, served
sc3netmod.dll = staged. `stage/release` -> `stage/release_1108b_old`, `stage/release_1109` -> `stage/release`.
**Removed file:** the LAN updater only deletes with `-Prune`, and unzipping never deletes. Without it the old CSATTRIB.IXF keeps
the white-dash look on two-way avenues. README and release notes say: delete `mods\netmod` before unzipping, LAN
`update.bat -Prune` once.

Zip: the 11-08 zip (downloaded back, SHA-256 D1C397BD... as recorded) with Apps/sc3netmod.dll and README.txt (NEW IN
2026-11-09) replaced and `mods/` replaced from the stage. 158 entries, 157 checked against the staged manifest, 0 mismatches
(README.txt is not in it), 120 mods files = manifest. `sc3mods_2026-11-09.zip` 51,386,510 bytes, SHA-256
C2D77D1BFB634F6DF6509FF5261BBABEF69E2CD636CAB18B28FCBDD9BB82A091.

Owner checks: on MARIANO-PC re-drag the avenue's west half across (608,134) on the Big One (the old hwt deleted that road);
then the screenshot avenue converts. Car directions through the 598 knot and the screenshot chain are proven by routed trips,
not by cars seen on screen.

Not checked: English-UK game run, the twin 20858 art (draws as the stock highway-over-road crossing).

GitHub: `sc3mods-2026-11-09`, target 1b13990, https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-11-09, asset
downloaded back, SHA-256 matches. The 11-08 notes start with a "superseded" line.
