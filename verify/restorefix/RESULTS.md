# restorefix (round 2026-11-02b): results

Pictures: `MAIN\verify\restorefix\owner_shots\` (not staged). Runs: `MAIN\verify\restorefix\runs\` (Berlin, windowed 800x600,
posted input only). Tree: `dev\restorefix\tree` from main be42ba9.

## 1. Bug: a restored recycling center dies (owner, MARIANO-PC, release 2026-11-02c)

**Verdict.** The recycling center's SetBirthdate is SIMECO 0x10003441 (building vtable 0x1001b784 +0x44). Unlike SIMUTIL
0x10006b86 and the SIMECO incinerator 0x100013dc, which read the date's day number through date vt+0x68, it reads date
vt+0x34 (year, date class 0x10011cc0 -> 0x100118c4) and vt+0x38 (day of the year, 0x10011cc8 -> 0x100116f7), then
rebuilds the number as jdn(12/31, year - 1) + day of the year (0x100113a4). sc3restore's stand-in date object answered
every slot except vt+0x10 with the day number, so the year came out near 2,476,000 and the birthdate landed millions of
years ahead. GetAge (SIMECO 0x100035a0, date at mortal +0x0c) then reads about -29.9 million months, shown as
"355,4xx,xxx años", and the building dies on the game's next check.

A second fault made it cost money: `restore_one` reported success when its post-write check could not read the
building, so the owner paid for the 5 broken centers (6,430 of the 65,799 charged).

**Owner's log** (`sc3restore.log` pulled from MARIANO-PC): 34 of 34 "restored", the 29 SIMUTIL buildings with a RESTORE>
line each, the 5 recycling centers (type 12851, mortal vtable SIMECO+0x1B5D0) only as
`INFO> ... MaxAge 900 age -29931277 are out of range: ignored`. The list scan after that: 29 alive.

**Reproduced** in my tree with the shipped code (run `repro`): Berlin's recycling center at (16, 26), Restaurar $325 ->
"(Envejecida)", "Edad (max) 355,433,092 años (75 años)", the same INFO line, funds 117,006 -> 116,681.
Shots 01, 02.

**Fixed** (`sc3restore.c`):

- The stand-in date answers vt+0x34 with the year and vt+0x38 with the day of the year (the game's own arithmetic).
- After the write the date is read back through GetBirthdate. It must equal what was written, and the building must then
  read age 0 and alive. Otherwise the old date is written back, the restore is refused and nothing is charged.
- A building whose date is already broken (MaxAge valid, age below -1200 or above 1,000,000 months) used to be ignored.
  Now it is listed and its "?" offers "Reparar (gratis)", with the date set to the first day of the city's current month
  (city vt+0x1e4). Measured: the game kills such a building within a few seconds (the age passes MaxAge), so in practice
  it shows up dead and Reconstruir (below) is the way back.

Measured after the fix (run `fix1`): the same recycling center, age 115 -> 0 months, birthdate day 2472596 -> 2476076 read
back equal, "0 años (75 años)", "Vida restante 75a", funds 117,006 -> 116,687 (cost 319). Shot 03.

## 2. Feature: Reconstruir a dead building in place

- A building with a lifespan that dies leaves rubble of its own class, with its type id and name ("(Muerta)" in the
  "?"). Its attrib key is the rubble art's, not the building's. Measured: the rubble's key {0x207edc0e, 0x57e, 0x2345}
  placed an "Escombros de Edificio" (type 15410) for $0 on the first try. SIMECO 0x100035f7 makes the rubble from
  occupant +0x24 through building layer vt+0x1c.
- So the building's key comes from a type -> key table. It is seeded with the 15 stock types measured over 12 shipped
  cities. Every live building sc3restore reads also teaches it, saved to `restore_keys.ini` beside sc3restore.dll.

| types | key instance (group 0x207edc0e / 0x57e) |
|---|---|
| power plants 12111..12118 | 0xcf 0xca 0xc9 0xcd 0xcb 0xce 0xcc 0xc8 |
| water pump 12810, treatment 12820, desalination 12830, 12840 | 0xdc 0xf4 0xfa 0xeb |
| recycling 12851, incinerator 12852, power incinerator 12853 | 0x2714 0x2713 0x272d |

- The rebuild is the game's own check and place. SIMGEOM 0x10006ba6 runs through the building layer's CanPlace / Place
  slot for the tool kind of the key, the way SIMGEOM 0x10007e64 picks the tool (the water buildings are kind 2), at the
  rubble's first cell. The stock check prices it (build price + clearing) and the stock Place withdraws that itself. The
  rubble is accepted and removed through RELOCATE's site-check cave and commit detour, as "the building being moved". A
  refused spot removes nothing.
- Funds short: refused before Place with "Fondos insuficientes: cuesta $N, hay $M", and the stock Place also refuses
  [static only: no city with funds below a build price was run].
- "?" of the rubble: "Reconstruir $price". After the rebuild the dialog reopens on the new building with
  "Reconstruido ($N)". Vida útil list: dead rows first, "En ruinas. Reconstruir: $N", button "Reconstruir". The header
  reads "216 con vida útil, 13 en ruinas". "Restaurar todos" leaves dead rows out.

Measured:

| run | building | result |
|---|---|---|
| rb2 | Berlin recycling center (16, 26), killed with test message 8 | "?" "Reconstruir $5,000", cost 5000, funds 117,006 -> 112,006, new Centro de reciclaje age 0 (shots 04, 05) |
| bad2 | the same center killed by an 11-02c style date (test message 10), the owner's exact state "(Muerta) 355,443,412 años" | Reconstruir from the "?", $5,000, new building age 0 of 900 (shots 06, 07) |
| ui3 | list row: Central Térmica de Carbón (59, 164), dead in the stock Berlin save | "Reconstruido por $5,000", row gone from the dead rows (shot 09) |

**Free for the bug's victims** (orchestrator call, 2026-11-02). Rubble whose birthdate GetAge cannot make sense of (age
below -1200 or above 1,000,000 months, the signature the 11-02c bug leaves) is flagged DEAD + BADDATE. It is placed
with the game's free flag, so the stock commit withdraws nothing and does not test funds. The button reads
"Reconstruir (gratis)", the list row "En ruinas (fecha dañada). Gratis". Every other dead building pays the build price.
Each rebuild logs which case applied (`REBUILD> ...: FREE (died from the 11-02c restore bug ...)` or
`PAID (died of old age: the build price)`). Measured in run `free1`, one game:

| building | case | result |
|---|---|---|
| recycling center (16, 26), date broken as 11-02c did, "(Muerta) 355,443,412 años" | FREE | cost 0, funds 117,006 -> 117,006, "Reconstruido sin costo", new building type 12851 (shots 17, 18) |
| coal plant (59, 164), dead of old age in the stock save | PAID | cost 5,000, funds 117,006 -> 112,006 (shots 19, 20) |

Not covered: a building removed altogether (bulldozed, or its rubble cleared) leaves nothing that records what stood
there, so it has no row. That would need a record kept by the mod while the building existed.

## 3. Vida útil list polish

- **RSTITLE.** The page's title is the game's own text window in its title bar (caption at window +0x44, SetCaption
  vt+0x10c). While the list is up it reads "Vida Útil", drawn by the game in its own title font. Volver and a page close
  put "Reunirse" back (log `RSTITLE> title back to "Reunirse"`). Shots 08, 11.
- **RSARROWS.** A text button's pill is wider than 40 px, and the next button's box paints over its right end, so the old
  arrows overlapped. "<" and ">" are now 24x25 image buttons, 6 px apart, centred on the footer row:
  - "<" is the game's own back arrow (row 1 of the close box's art sheet).
  - ">" is the same art with the glyph mirrored inside its square.
  - Tooltips "Anterior" / "Siguiente". Shots 10, 14, 15, 16.
- **RSHG2.** The art sheet's frames (order: disabled, normal, pressed, hover) hold the glyph in an inner square, outline
  x 4..17, y 4..15, one row lower when pressed (measured). The 11-02c code found that square from dark pixels and took the
  button's bevel rows for its edges, so the glass was drawn over the square's lines (the bar under it in the owner's shot).
  The square is now painted in the face colour and an 11x12 pixel hourglass drawn in its place: bars, two bulbs, sand
  left in the top one, its stream and the pile. Bevel and state frames stay stock. Shots 12, 13.

## Off switches

| switch | off = |
|---|---|
| `SC3RESIZE_REBUILD=0` | no Reconstruir, dead buildings get no button or row action (rows show, button grey) |
| `SC3RESIZE_RSTITLE=0` | the list keeps the "Reunirse" title |
| `SC3RESIZE_RSARROWS=0` | the 40 px text arrows of 11-02c |
| `SC3RESIZE_RSHG2=0` | the 11-02c hourglass drawing |

The date fix and the refund-on-failure have no switch (`SC3RESTORE=0` still turns the whole mod off).

## Test-only messages (WM_RZ_RESTORE, `re/tools/restore_lab.py msg`)

8 = age the building at cell lParam one month past its MaxAge (the game kills it), 9 = one list scan (logs rows and the
key table), 10 = break its date the way 11-02c did.
