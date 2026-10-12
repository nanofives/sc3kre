# queryid: "Copiar ID" button in the query (?) dialog (pre-registration, 2026-10-12)

Owner: "necesito modificar el juego en profundidad para agregar tipos de caminos, más diseños, tipos de conexiones y
texturas que no están, pero para eso me gustaría señalar con ID el elemento que quiero trabajar, podemos implementar
un botón en el menú de '?' para que copie el ID de lo seleccionado?"

Written BEFORE the first in-game read of any field below.

## Static basis (read before this file)

- Query dialog object: SIMUI ctor `FUN_10061f53` (0x118 bytes, vtables `0x100aadc8` / `0x100aadb8` at +4), opened by
  `FUN_10062cee(occupant, mode)` (stores the occupant at `+0xd8`, AddRef, then occupant `vt+0xb8` GetLocation into
  `+0xdc`) or `FUN_10062cba(coord, mode)` (no occupant, coord copied to `+0xdc..+0xe4`).
- Its message handler is slot 3 of the `+4` vtable, `FUN_1006338f` (ret 0x14). Message `0xa2bf8ace` builds the window
  content (`FUN_100634a6`), message 3 with p3 = 1 carries a button id in p4 (0 and 4 are the game's, `0x42b7c353` the
  close box). Same shape as the Preferences handler HUDOPT already detours.
- `FUN_1006255a` reads cell = `+0xdc >> 8`, `+0xe0 >> 8` and calls city `vt+0x13c` (DirtBag) `vt+0x54` (IsWater) and
  city `vt+0x14c` (ZoneLayer) `vt+0x34` (GetValue, a byte) with it. City = SIMUI `FUN_1008e7da()`.
- Occupant slots from the GZCOM SDK header, three already matching SC3U call sites (`+0xb8` GetLocation, `+0x80`
  GetAttribData, attrib `+0x88` GetQueryFormatFlags read by `FUN_1006255a`). The rest are `[GZ-HINT]` until measured.
- Network pieces (SIMNTWRK): occupant subobject at piece+4, piece+0x14 = packed x/y/z + 2-bit state, piece+0x18 low 16
  bits = piece id; occupant attrib key `{0xe223741f, 0xa317745f, id}` `[CONFIRMED @ SIMNTWRK 0x1000c80b]`; TrBlkAtt
  exemplar key `{0x625c6226, 0x825c6289, id*0x100 + state}` `[CONFIRMED @ SIMNTWRK 0x1000d225]`. The six id lists
  read by the per-network membership predicates are filled from `ROAD/HWAY/RAIL/SUBW/PIPE/POWR_GRND_Set.txt`
  (`0x10032348/4c/50/54/58/5c`) `[CONFIRMED @ SIMNTWRK 0x1001726e..0x10017312, 0x1001a719..0x1001a7d2]`.

## Design

- One entry detour on SIMUI `0x1006338f` (prologue `55 8b ec 56 8b f1`, checked first).
  After the original handles `0xa2bf8ace`, add one button, caption "Copiar ID" (English install: "Copy ID"), made
  with the game's widget factory (`FUN_10085065` `+0x30`, the text-only path SIMUI `0x1000114e` uses).
  Message 3 / p3 1 / p4 = our id: build the text, put it on the clipboard (CF_TEXT), log it, handled.
- Text = labelled lines, one fact each, only fields measured below; anything else printed as `raw`.
- Opt-out `SC3RESIZE_QUERYID=0`: no detour, no button.

## Tests (instance `re/harness/inst_queryid`, 256 city copies, windowed, -multi, own PID)

For each object: query it with "?", click the button, read the clipboard (Win32 from the test script), save the city
under a new name, read the same object from the save with `re/tools/occupant_layer.py`, `network_layer.py`,
`city_write.City` (zones).

| # | prediction | fails if |
|---|------------|----------|
| P0 | the button shows in every query dialog seen (zone building, plopped building, road, rail, terrain, water), inside the dialog, not covering game controls | missing, overlapping, or off the dialog |
| P1 | one click = clipboard text, the dialog stays usable (OK closes it, close box closes it) | empty clipboard, crash, dialog stuck |
| P2 | road / rail / pipe / power line: the raw piece words (piece+0x14, piece+0x18) equal the save tile's word0 / word1 at the same x,y | any word differs |
| P3 | road / rail: piece id is in exactly the network's `*_GRND_Set.txt` list(s) the membership read reports (straight road -> ROAD only, level crossing -> ROAD + RAIL) | a road id reported as not ROAD, or a crossing as one network |
| P4 | network piece: attrib key from occupant `+0x80` -> attrib `+0x14` = `{0xe223741f, 0xa317745f, piece id}` | different key |
| P5 | building: occupant `vt+0x88` (TypeId) = the save record +8 type id (`[AgentTypes]` id, 12810 for a water pump) and attrib key = the save record +12 key | either differs |
| P6 | building: occupant cell (`vt+0xbc` GetLocationInCellCoords) = save record x, y (bits 0-10, 11-21) | differs |
| P7 | zone byte (ZoneLayer GetValue at the query cell) = the save's zone value at that cell (R 1-3, C 5-7, I 9-11, 22 plopped) | differs |
| P8 | water tile: IsWater true; dry tile: false | wrong on either |
| P9 | `SC3RESIZE_QUERYID=0`: no button, query dialog as stock | button present |
| P10 | final check on stock DLLs (section 10 hard-linked copy) | any P0/P1 failure |

A field whose prediction fails is dropped from the text or printed with its raw value and no meaning.
Results go to `verify/queryid/RESULTS.md`, the format spec to `re/analysis/QUERY_ID.md`.
