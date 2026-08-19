# MenuItem.INI - the SimCity 3000 UI command table

Member of `Apps/Sys/SYS.PAK` (20,616 bytes, 251 lines). Parser: `re/tools/menuitem_parse.py`
(`--selftest` green, 8 checks). Framing is NOT re-derived here: SYS.PAK is parsed by the
validated `re/tools/syspak_parse.py`, whose spec is `re/analysis/formats/SYSPAK.md`.

**What it is for.** A button in the live UI carries a command id, readable off the `cIGZWin`
object at `vt+0x214` (`LAUNCH_CONTROL.md` section 31). That id is a bare number. This file is the
table that names it, so the harness can drive gameplay by name instead of by magic number, and so
a dump of the window tree becomes readable.

## Record spec `[CONFIRMED - 90/90 records parse]`

Section `[SC3MenuItemInfo]`, one line per command:

```
0x10006602=1,0x225872FE,0x00000034,0x225872FE,0x00000034,COMM,0x22ff0548,0,0,0,END  ; Big Park
```

| field | meaning |
|---|---|
| command id | what the button's `vt+0x214` returns, and what `FUN_1004c209` posts as `{0x025F0A91, id, 0, 0}` |
| enabled | `1` on every shipped record |
| LTEXT group + instance | the localized DISPLAY string key (`0x225872FE`, or `0x041F2625` on a few) |
| help group + instance | a second key; identical to the display key on **88 of 90** records |
| kind | `COMM` = dispatch a command (83 records), `PMSG` = post a message (7) |
| command GUID | the GZCOM command / message id actually dispatched |
| param | a second argument, non-zero only on the palette-opening entries |
| `; name` | the English name - a COMMENT |

The English names are trailing comments, so they are **not** what the game displays; the shown
string comes from the LTEXT key, and the install under test renders the UI in Spanish. They are
the developers' own labels, which is what makes them the right thing to annotate with. Resolving
an LTEXT key to its displayed text is a separate job and was not done here.

## Provenance of the naming

`0x10006602` was fired blind into a loaded city **before** any of this was parsed, and the status
bar showed a **$1,000** cost readout. The table independently says `0x10006602` = **Big Park**,
which costs $1,000 in SC3000. Two unrelated routes agreeing on one id is the check that this is
the right table.

## Coverage against the live UI

The in-city window walk (`LAUNCH_CONTROL.md` section 31.7) finds 109 command-carrying buttons,
**89 distinct** ids. **All 89 appear here - 100%.** The table holds 90; the one command
never seen on a live in-city button is `0x10008011` **NEW Take Snapshot**.

## The table

"live" = observed on a button in a loaded city (Berlin) during the section 31.7 walk.

| command id | name | kind | command GUID | live |
|---|---|---|---|---|
| `0x10001006` | Meet Advisor | PMSG | `0x724a82d0` | yes |
| `0x10002001` | Place Trees | COMM | `0x4253EC3F` | yes |
| `0x10002002` | Place Water | COMM | `0x02E763C1` | yes |
| `0x10002003` | Lower Terrain | COMM | `0xc25ad94f` | yes |
| `0x10002004` | Raise Terrain | COMM | `0x825ad7f6` | yes |
| `0x10002005` | Level Terrain | COMM | `0x825ad954` | yes |
| `0x10002006` | Demolish | COMM | `0xe3166801` | yes |
| `0x10003004` | Landfill | COMM | `0xc2e889b6` | yes |
| `0x10003005` | Seaport | COMM | `0x02e889c4` | yes |
| `0x10003006` | Airport | COMM | `0xE2E889D4` | yes |
| `0x10003007` | DeZone | COMM | `0x82e88c9c` | yes |
| `0x10003008` | Demolish | COMM | `0xe3166801` | yes |
| `0x10003101` | Res Low Density | COMM | `0x42e88586` | yes |
| `0x10003102` | Res Medium Density | COMM | `0x02e88915` | yes |
| `0x10003103` | Res High Density | COMM | `0xa2e8893b` | yes |
| `0x10003201` | Com Low Density | COMM | `0x02e88949` | yes |
| `0x10003202` | Com Medium Density | COMM | `0xa2e8895a` | yes |
| `0x10003203` | Com High Density | COMM | `0x02e88968` | yes |
| `0x10003301` | Ind Low Density | COMM | `0xc2e8898f` | yes |
| `0x10003302` | Ind Medium Density | COMM | `0xa2e8899d` | yes |
| `0x10003303` | Ind High Density | COMM | `0x02e889aa` | yes |
| `0x10004001` | Roads | COMM | `0xC2B5DE77` | yes |
| `0x10004004` | Bus Stop | COMM | `0x02ff04fe` | yes |
| `0x10004009` | Rail To Subway | COMM | `0x22ff0521` | yes |
| `0x1000400A` | Demolish | COMM | `0xe3166801` | yes |
| `0x10004101` | Lay Rail | COMM | `0x42B5DE98` | yes |
| `0x10004102` | Train Station | COMM | `0x22ff058f` | yes |
| `0x10004201` | Lay Subway Rail | COMM | `0xC2B5DEA6` | yes |
| `0x10004202` | Subway Station | COMM | `0x62ff059b` | yes |
| `0x10004301` | Highway | COMM | `0x42b5DE86` | yes |
| `0x10004302` | Onramps | COMM | `0x02b5debb` | yes |
| `0x10005001` | Wires | COMM | `0x42C2F8BF` | yes |
| `0x10005002` | Power Plants | COMM | `0xE2ED3560` | yes |
| `0x10005003` | Pipes | COMM | `0x22C2F8C5` | yes |
| `0x10005009` | Water Buildings | COMM | `0xE2ED3560` | yes |
| `0x1000500A` | Garbage Buildings | COMM | `0xE2ED3560` | yes |
| `0x1000500B` | Demolish | COMM | `0xe3166801` | yes |
| `0x10006003` | Fire | COMM | `0x22ff054c` | yes |
| `0x10006008` | Landmarks | COMM | `0xE2ED3560` | yes |
| `0x10006009` | Rewards | COMM | `0xE2ED3560` | yes |
| `0x1000600A` | Demolish | COMM | `0xe3166801` | yes |
| `0x10006201` | Police Station | COMM | `0x42ff052f` | yes |
| `0x10006202` | Jail | COMM | `0x22ff053f` | yes |
| `0x10006401` | Hospital | COMM | `0xe2ff0555` | yes |
| `0x10006402` | School | COMM | `0xc2ff0563` | yes |
| `0x10006403` | College | COMM | `0xc2ff0571` | yes |
| `0x10006404` | Library | COMM | `0xc2ff057a` | yes |
| `0x10006405` | Museum | COMM | `0x62ff0585` | yes |
| `0x10006601` | Small Park | COMM | `0x02ff05aa` | yes |
| `0x10006602` | Big Park | COMM | `0x82ff05b7` | yes |
| `0x10006603` | Marina | COMM | `0x42ff05c2` | yes |
| `0x10006604` | Zoo | COMM | `0x22ff05ca` | yes |
| `0x10006605` | Baseball Field | COMM | `0x62ff05d1` | yes |
| `0x1000660A` | Playground | COMM | `0xc2ff05e0` | yes |
| `0x1000660B` | Pond | COMM | `0x22ff05ea` | yes |
| `0x1000660C` | Fountain | COMM | `0x22ff05f3` | yes |
| `0x10008001` | Budget | COMM | `0x025ddc4a` | yes |
| `0x10008002` | Ordinances | PMSG | `0x724a82D7` | yes |
| `0x10008003` | Scenario goals | COMM | `0x844587ae` | yes |
| `0x10008004` | Map View | COMM | `0x411164f1` | yes |
| `0x10008005` | NEIGHBORS | COMM | `0x630288e9` | yes |
| `0x10008010` | NEW View Snapshots ... | PMSG | `0x2435FF70` | yes |
| `0x10008011` | NEW Take Snapshot | COMM | `0x00000000` | - |
| `0x10008020` | NEW Snapshot Small | PMSG | `0x2435FF70` | yes |
| `0x10008021` | NEW Snapshot Medium | PMSG | `0x2435FF70` | yes |
| `0x10008022` | NEW Snapshot Large | PMSG | `0x2435FF70` | yes |
| `0x10009001` | Prefs | COMM | `0xc3001401` | yes |
| `0x10009002` | Save | COMM | `0x410438DD` | yes |
| `0x10009004` | New | COMM | `0xe3270fe9` | yes |
| `0x10009005` | Quit | COMM | `0xA10438E9` | yes |
| `0x10009006` | Save As ... | COMM | `0x410438DD` | yes |
| `0x1000900A` | NEW City Properties | COMM | `0x855a2dc4` | yes |
| `0x10009301` | Load Saved City | COMM | `0x610438A4` | yes |
| `0x10009302` | Load Starter Town | COMM | `0x610438A4` | yes |
| `0x10009303` | Load Real City Terrain | COMM | `0x610438A4` | yes |
| `0x10009304` | Load Scenario | COMM | `0x610438A4` | yes |
| `0x1000A001` | Goto | PMSG | `0xC30177CA` | yes |
| `0x1000A002` | Early Warning | COMM | `0x02b5aecf` | yes |
| `0x1000A003` | Police Dispatch | COMM | `0x029a52dd` | yes |
| `0x1000A004` | Fire Dispatch | COMM | `0x229a528c` | yes |
| `0x1000A006` | Plane Dispatch | COMM | `0xa5354652` | yes |
| `0x1000A101` | Fire | COMM | `0xc26ce54d` | yes |
| `0x1000A102` | Tornado | COMM | `0x626ce901` | yes |
| `0x1000A103` | Earthquake | COMM | `0x22fe8786` | yes |
| `0x1000A104` | Riot | COMM | `0x02fe87a7` | yes |
| `0x1000A105` | UFO | COMM | `0x42fe87ae` | yes |
| `0x1000A106` | Toxic cloud | COMM | `0x447f1e40` | yes |
| `0x1000A107` | Whirlpool | COMM | `0x447f1e41` | yes |
| `0x1000A108` | Locusts | COMM | `0x447f1e42` | yes |
| `0x1000A109` | SpaceDebris | COMM | `0x447f1e43` | yes |

## Notes

- Ids are dense in `0x1000xxxx` and group by palette: `2xxx` terrain, `3xxx` zones, `4xxx`
  transport, `5xxx` utilities, `6xxx` civic and parks, `8xxx` views/budget, `9xxx` file,
  `Axxx` disasters and dispatch.
- `Demolish` appears five times under different ids (`0x10002006`, `0x10003008`, `0x1000400A`, `0x1000500B`, `0x1000600A`) - one per palette, all dispatching
  the same GUID `0xe3166801`.
- The 7 `PMSG` records (`0x10001006` Meet Advisor, `0x10008002` Ordinances, `0x10008010` NEW View Snapshots ..., `0x10008020` NEW Snapshot Small, `0x10008021` NEW Snapshot Medium, `0x10008022` NEW Snapshot Large, `0x1000A001` Goto) post a message instead of dispatching a command. A driver
  must not assume `COMM` for everything.
- The LTEXT group appears in both cases (`0x225872FE` and `0x041F2625`, the latter spelled
  lowercase in some records). Case-insensitive comparison is required.
