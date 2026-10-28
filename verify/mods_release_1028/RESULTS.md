# RESULTS - sc3mods release 2026-10-28 + LAN republish

Replaces `sc3mods-2026-10-27f`. Owner call 2026-10-28: "release con lo de esta sesión + las otras sesiones". Target
`main` at this file's commit (source as of `d9ebcdd`). Changes since 10-27f (`95b033b`):

| what | commits | shipped files |
|---|---|---|
| MODSPAGE: "Opciones de mods" page in Preferencias, autosave on/off/interval | f5b756d | sc3resize.dll, sc3autosave.dll |
| edge push while placing + CAMSET camera speed sliders (on the mods page) | aacdd64, 214f800 | sc3overscroll.dll, sc3resize.dll |
| avpaint: AVL corner + T (AVLCT), look-only paint for refused bands (AVP), avenue_lanes 0.3.0 | b3b6ec5, 7fc2df4 | sc3netmod.dll, mods/netmod/** |
| sc3mods_patch only refuses when the game runs from that folder | c495214 | sc3mods_patch.ps1 |

`git diff 95b033b main -- re/harness/src`: sc3resize, sc3overscroll, sc3autosave, sc3netmod (+ _avl, _avp, _rbt) only.
sc3bigcity, sc3mods, sc3perf, sc3simrun, sc3undo are the 10-27f files, byte-identical (hash-checked against the
10-27f zip, downloaded back from GitHub: SHA-256 `8D890DE8...` as recorded).

## Stage and checks

- `stage/src`: avenue_lanes uninstalled (0.2.0) and installed as 0.3.0 from `dev/avpaint/tree/mods/netmod/packs/avenue_lanes`
  (art 21718..21741 present). Ledger order, overlay and tables identical to the avpaint test tree (`diff -rq`: none).
  Backup of the old `stage/src/mods/netmod` kept in the session scratchpad until this release is confirmed.
- `stage/bins_1028` = `stage/bins_1027f` + sc3resize / sc3overscroll / sc3autosave / sc3netmod built from main.
- `stage_lan_release.py --game stage/src --bins stage/bins_1028 --stock-modules original/modules --menu-bg <10-27f>
  --perf-ini <10-27f> --out stage/release --label 2026-10-28`: 3,606 files, 697.3 MB, exe = anchor `49DD55E1...`.
- Launch check (stage/release patched, windowed, posted input only):
  - Big One: `8 mod(s) loaded`, overscroll `PUSH: low-level mouse hook installed`, netmod table load: 6 corner + T
    pieces, look-only twins, `avp: avenue look on two-way bands on (9 twin(s))`.
  - Owner save `BigOne_owner.autosave1.sc3` (copied in, removed after): `avl: corner + T on (6 avlt piece(s))`,
    `stats: avl bands converted=5, refused=0, cells written=88, reverted=0` (avpaint's after-state).
  - Faults: only the benign `0xC0000096 @ SC3U+0x84122`.
  - Then `-Restore` (anchor `49DD55E1...`), logs and the save deleted, 3,606 manifest files re-hashed: 0 changed,
    0 missing, 0 extra.

LAN: `deploy_lan_release.sh` sent 67 of 3,606 files (54.9 MB). Served label `2026-10-28`, served sc3resize /
sc3overscroll / sc3netmod / sc3autosave SHA-256 match the stage.

Not hand-tested in this build by the owner: the edge push and camera sliders were owner-tested in the dev tree
before the MODSPAGE merge (sliders then sat on the game page). Not tested by avpaint: traffic over the corner + T
box, a T on the inner side (21740 / 21741).

| file | bytes | SHA-256 |
|---|---|---|
| Apps/sc3resize.dll | 444,416 | 3E6069D9AA7865A39FF16C5BD3E8BAD587A46C08922C5A68B98D4D8DC09973DF |
| Apps/sc3overscroll.dll | 133,632 | 6239B3921651B2B8945F543E471158FEE8B6CEA488579F844F73C9EA589C8E2F |
| Apps/sc3autosave.dll | 127,488 | 2DD3C5E337E637096831AC2F90DD74604AA3CE54B6BFC24A3657C8A2F77D1D5E |
| Apps/sc3netmod.dll | 411,136 | 5EC7B9319FAA4A426219AAD8C59C373B627C840E210C93739116A40DF1478FA9 |
| sc3mods_patch.ps1 | 14,571 | F5A1E9AD9AFA4881EF951F1AA03C850CE27B3091388A309F461E74F4DC1E9F4B |
| README.txt | 17,630 | CA9D4878A0AD1C351AD843C2DDF2DCF9B959D7ABBF9493F0A3E9D5437CAEB954 |
| mods/netmod/** | | as stage/release (avenue_lanes 0.3.0) |
| every other file | | as `verify/mods_release_1027f/RESULTS.md` |
| `sc3mods_2026-10-28.zip` | 43,611,810 | 22DC147132CE506121781F10B2ECEEC4898AEAD7DD100AA1E5FFC68EEA6A231A |

GitHub: `sc3mods-2026-10-28`, target `9f842f7`, https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-10-28, asset
downloaded back, SHA-256 matches. The 10-27f notes now start with a "superseded" line.
