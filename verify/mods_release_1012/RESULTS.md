# RESULTS - sc3mods release 2026-10-12

Fix release on top of sc3mods-2026-10-11. Owner hand test 2026-10-11 on the merged fix-round build staged in
`re/harness/combo/` (main 7c1db20): "everything seems to be working fine". Release target: `7c1db20`.
Only `sc3resize.dll` and `mods_launch.exe` changed. The other four DLLs and `perf.ini` are byte-identical to 2026-10-11.

**Owner decision 2026-10-11:** ship `menu_bg.bmp` (the owner's AI upscale of the stock main-menu picture) by default.
It is derived from Maxis art, so it is an explicit exception to the tools-and-notes-only publish policy, risk accepted
by the owner. `menu_orig.raw` is not shipped and no longer needed (MENUBG decodes MAIN.IXF record 0x22729921 at runtime).

## Contents

| file | bytes | SHA-256 |
|---|---|---|
| `README.txt` | 5,907 | `B5E221C8FC71B93112B6CBF366BBB4319868F86A0039019B40BFAC697F3F94D7` |
| `mods_launch.exe` | 123,392 | `04061206A67F9F87EB5A360D7F730A36C19BE93C4A1F13513E82165EF2742970` |
| `perf.ini` | 2,090 | `2B1C536C2C1284C5AAFF63EDDE74D5ACAE45557D75ED2CEC73AC93A3E3F86164` |
| `menu_bg.bmp` | 4,717,638 | `10792812B2BAED12A62D9207FE47FB0E3FD827E3B5B642F3C2C8A253856945AE` |
| `sc3resize.dll` | 227,840 | `B51A8BD21DA5C5EFFDE554823DD68B378F41F35E3ECB4DCB8AEA42333756B7A1` |
| `sc3bigcity.dll` | 137,728 | `CBBE0C97961E029E8C62940BD29B6A5B3E1EE4FF5EF59EAB0659283A55428101` |
| `sc3overscroll.dll` | 123,392 | `BB0E81BDDFE4D772272BA0C27F133D0A5642F3DEFE798B5E4A307729CF4220C0` |
| `sc3simrun.dll` | 115,712 | `58A946F2CC9021272C55C3DB8F15C38B06C72D8490D0E9F40F592C0459FDD287` |
| `sc3perf.dll` | 178,176 | `BAA78D5A11E8B007EDEA18CB49F52BCEE3F8695E9FC3586332398A1C3C817E38` |
| `sc3mods_2026-10-12.zip` | 4,694,185 | `61B8CFCA63EEF7CC9505B20E9EAEB82A119290667085CC7557F7689AE427CF3B` |
## Package smoke test (package folder at bin depth, no SC3* env, -multi)

- Main menu run: MENUBG decoded the stock art from `Apps\Res\UI\Shared\MAIN.IXF` and loaded `menu_bg.bmp` 1448x1086.
  The maximized-menu visual could not be checked: the owner was using the PC and the game window was not frontmost, so
  it drew no frames after the size change. The same code path was verified in-game by the menubg child (pixel-identical
  to the combo build without `menu_orig.raw`) and by the owner's hand test of the combo build.
- City run (1024 test city, speed 3, 3 maximize/restore cycles): passes 162 to 319 ms, DIRTGUARD 0, CELLFIX active,
  VEH only the benign SC3U+0x84122, `DAYS> 43 days in 60 s` median 665 ms. One restore waited 3.4 s for the sim thread
  (SIMLOCK), listed as a known limit.

## Published

GitHub release `sc3mods-2026-10-12` on nanofives/sc3kre, target `7c1db20`:
https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-10-12
Asset downloaded back with `gh release download`: SHA-256 matches `61B8CFCA...CF3B`.
The 2026-10-11 release notes now start with a "superseded" line pointing here.
