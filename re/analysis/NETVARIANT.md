# Network piece variants at runtime: crossings and stock-safe saves (netmod suite, 2026-10-13)

**Status: game-proven on stock DLLs** (`verify/netvariant/RESULTS.md`, PRE `ea83d76` + addendum `verify/netvariant/PRE.md`).
A *variant* is a new piece id made as data by `newpiece.py` (`NEW_PIECE.md`): today 20029, a blue copy of road
straight 29. Pure data gives it the road class, the cost, the tiling and traffic. It lost two things, which the new DLL
`sc3netmod.dll` (`re/harness/src/sc3netmod.c`, injected by `mods_launch.exe`) restores:

1. **Crossings.** Rail and power lines now cross a variant as they cross its base. The crossing tile is the stock
   crossing piece (69 rail, 67 power over road 29), so the variant look is lost on that one tile. That is the first
   version by design: a variant-coloured crossing needs its own crossing piece and matrix row, which is new art plus a
   matrix patch (not done).
2. **Stock-safe saves.** A city saved with the DLL stores each variant tile with its BASE id in the tile word, so a game
   without the mod loads grey road instead of dropping the tiles. The variant ids ride in one extra section that the
   stock game ignores. With the DLL they come back on load, exactly, on the same tiles.

Opt-outs: `SC3NETMOD_CROSS=0`, `SC3NETMOD_SAVEBASE=0` (save side only; the load side always runs and only acts on files
that carry the section). Log: `sc3netmod.log` beside the DLL (`SC3NETMOD_LOG` overrides).

## 1. The variant table (manifest "base")

Each variant declares the piece it behaves as. `newpiece.py build --base <id>` (default `--src`) writes it in the mod's
`manifest.json` as `"base"` and installs `Apps\Res\netmod_variants.txt` (one `<variant> <base>` pair per line, `#`
comments). The DLL reads that file next to `SC3U.exe` (`SC3NETMOD_TABLE` overrides). No table, or an empty one: the DLL
patches nothing. The table travels with the data files, so "variant installed" and "variant in the table" are the same
fact.

## 2. Inventory: every SIMNTWRK path that decides by piece id

How a piece id is read: every network piece class (22 classes, factory `FUN_1000bdcd`) shares primary vt+0x30 =
`FUN_1000cc83` (`[this+0x18] & 0xffff`) and primary vt+0x5c = `FUN_1000c2fc` (`[this+0x18] & mask`); the secondary
interface's vt+0x5c `FUN_1000d6fd` is `sub ecx,4; jmp 0x1000c2fc`. `FUN_1001a93d(occ)` = QI 0x41658d28 then vt+0x30
`[CONFIRMED @0x1001a93d, 0x1000cc83, 0x1000c2fc, 0x1000d6fd]` (vtables read from the PE).

**Predicates.** Small objects built by `FUN_10010dff` into `DAT_100323c0..DAT_10032468`, 5-slot vtables, slot +0xc =
`test(occupant)`, `ret 4`. The network manager hands them out by index through vt+0x54 (`FUN_10013771`), also to other
DLLs. All 15 below were checked: vtable slot +0xc holds the function, every `ret` is `ret 4`.

| predicate | object, index | id test | wrapped |
|---|---|---|---|
| `0x1001ab26` | `DAT_10032400`, 0x0a | road may take the cell: flags, or id in {0x5c,0x49,0x3acb,0x2c,0x2d,0x2711,0x2734,0x2735,0xf,0xe} | yes |
| `0x1001ac2b` | `DAT_10032404`, 0x0c | rail: flag 0x20000, or id in {0x1d,0x2bc4,0x49,0x3acb,0x5c,0x1e,0x2711,0x2734,0x2735,0xf,0xe} | yes |
| `0x1001abb2` | `DAT_10032408`, 0x0f | power: flag 0x400000, or id in {0x1d,0x2bc4,0x2c,0x49,0x3acb,0x1e,0x2d} | yes |
| `0x1001acbe` | `DAT_1003240c`, 0x0b | highway: flag 0x10000, or id in {0x1d,0x2bc4,0x2c,0x5c,0x1e,0x2d,0x2711,0x2734,0x2735,0xf,0xe} | yes |
| `0x1001ad60` / `0x1001ade7` / `0x1001ae36` | `DAT_10032418/1c/24`, 0x1c..0x1e | flags 0x8800 / 0x20800 / 0x10800, or id 0xe/0xf | yes |
| `0x1001ae85`, `0x1001af19`, `0x1001afc7`, `0x1001b07c`, `0x1001b10c`, `0x1001b248`, `0x1001b1a1`, `0x1001b2e0` | `DAT_10032430..54`, 0x10..0x1b | per rotation (vt+0xb4) id lists, e.g. `0x1001af19`: rot 0 {0x47,0x49,0x3e86,0x5c,0xf}, rot 1 {0x1d,0x2bc4,0x45,0x5c}, rot 2 {0x49,0x3e86}, rot 3 {0x2bc4} | yes |
| `0x1001b378` | `DAT_10032460` | decoration pick {0x1d,0x2bc4,0x23} | **no** |
| `0x1001b3c4` | `DAT_10032464` | already decorated {0x3ac0,0x3ac1,0x3ac2,0x235b} | **no** |

**Direct id reads with fixed lists** (`FUN_1001a93d` unless noted):

| function | test | what it decides | variant needs the base? |
|---|---|---|---|
| `0x100167d4` | switch {0x49,0xe,0xf,0x1d,0x2c,0x5c,0x2bc4,0x3acb} -> row of `DAT_100318ac` (6x6, values id*256+state: road x rail 69, road x power 67) | builds the crossing | **yes, call at `0x10016821` redirected** |
| `0x1001547b`, `0x10016327`, `0x100077e7`, `0x10007d32`, `0x10009613`, `0x1000986f` (vt+0x30), `0x1000ab5b`, `0x10014939` | `FUN_1001a7f7(type, id)`: membership of `TilingRules\*_GRND_Protected.txt` | protected tiles are kept out of re-tiling / clearing | no: neither 29 nor 20029 is in any Protected list (ROAD's has 63,64,67,69,87,88,11258), so the answer is the same |
| `0x1000de17` | via `0x1001b378`/`0x1001b3c4`, then the id | swaps a random 0x1d for 0x3ac0..0x3ac2 (and back) | **no, on purpose**: a blue tile must not become a grey decoration piece |
| `0x1000abde`, `0x10009d20` | getters `0x10009bc7`/`0x1000aaba`, ids 0x49/0x2bfa/0x3acb/0x3afa | highway onramps and diagonals | not for a road base; needed for a future highway variant (not wired) |
| `0x1001da5f`, `0x1001d761`, `0x1001e3cc`, `0x1001e2ea` | Collapse.txt groups, end-piece tables, 16-id list at `DAT_10031f94` | removal of multi-tile pieces (bridges and the like) | not for road 29; needed for a bridge variant (not wired) |
| `0x1000122a` | none (defaults 0x1d/0x2c/0x5c when the slope lookup fails) | | no |
| `0x10008a4a` | does not read piece ids | | no |

Other DLLs: no `vt+0x5c(0xffff)` reads and no 0x1d/0x2c/0x49 comparisons next to piece-id reads in SIMTRANSIT,
STRTSIM, SIMSPR, SIMUI, SIMDSTR or SIMCITY (inventory sweep; the QI 0x41658d28 users there call slots 0x54/0x48/0x4c/0x88).

**Why the rail stopped at the road (measured, not static).** A live read-only Frida trace of the id getters during a
rail drag over 20029 showed the reads came from `0x1001af19` (vt+0x5c at `0x1001af4f`), `0x1001ade7` (`0x1001ae22`) and
`0x10014939` (`0x1001497c`), and never from the crossing switch. So the path planner (outside SIMNTWRK, through manager
vt+0x54) asks the rotation predicates per cell before SIMNTWRK `FUN_1001547b` reaches `FUN_100167d4`. Redirecting only
the switch did nothing (PRE addendum 1).

## 3. How the crossing fix works

- The call at `0x10016821` (`FUN_1001a93d` inside `FUN_100167d4`) goes to a thunk that returns the base id.
- The two getters `0x1000c2fc` and `0x1000cc83` are replaced by stubs that do the same read and, only when a wrapped
  predicate is running on the calling thread (TLS depth counter), map a full 16-bit variant id to its base. Outside a
  predicate they are the stock read plus one compare.
- The 15 predicate vtables have slot +0xc swapped for wrappers that enter the scope, call the original, leave.
Each patch `memcmp`s the shipped bytes or the expected slot first and is skipped (logged) on mismatch.

What a crossing over a variant looks like: the stock crossing tile (69 / 67), with the road's other tiles keeping the
variant. The crossing tile is created by the stock matrix, so its record is the stock one (`(102,155)` piece 69 state 1
props 0x3000 in arm X1, the same fields as the stock crossing in newpiece arm XC). What it turns back into when the rail
is removed was not traced (the inventory found no literal that rebuilds a road from a crossing; the re-tiler treats 67/69
as Protected) and was not tried in game.

## 4. How the save fix works

Saver chain `[CONFIRMED @0x10012dff, 0x10012fc3, 0x1000d688]`: `FUN_10012dff` saves the three networks with
`FUN_10012fc3`, which writes one 8-byte record per occupied cell with `FUN_1000d688` (call at `0x10013082`, record +4 =
word0, +8 = word1, id in word1 bits 0..15), then writes the header section (instance 0). Loader `FUN_100130e9` opens
instance 0 and then 1, 2, 3 by key and reads each record with `FUN_1000d6b3` (calls at `0x10013264`, `0x10013338`,
`0x1001340b`) before the piece is created from it.

- **Save** (`SC3NETMOD_SAVEBASE`): a thunk at `0x10013082` rewrites word1's id to the base before the record is
  written and remembers `{word0, word1 as written, variant id}`. A hook at `0x10012ee0` (after the third network, before
  the header) writes the list as section `{type 0x206c6e7c, group 0x2147c2dd, instance 0x4E56}` with the game's own
  section writer `FUN_10026129` (version 1) and stream vt+0x88. A hook at `0x10012e3e` clears the list at save start.
- **Load**: a hook at the entry of `FUN_100130e9` opens instance 0x4E56 with the game's reader `FUN_10025f0d` (absent
  section: nothing to do) and builds a hash on word0. The three tile-read calls go through a thunk that, after the stock
  read, puts the variant id back when word0 AND word1 both match an entry. Entries for a variant that is not in the table
  (data uninstalled) are skipped, so those tiles stay base instead of being dropped.

Section bytes: frame `01 00 02 00 ef be ad de`, then `u32 "NVR1"`, `u32 count`, `count x {u32 word0, u32 word1, u32 id}`.

Why a section and not a bit field or a sidecar: word0 is full (coord 30 bits + state 2) and word1 bits 0..29 all have a
saver behind them (`FUN_1000ca2c`); a sidecar needs the save path and is lost when the file is copied alone. The stock
loader asks for instances 0..3 by key only; measured: stock loads a file with the section and keeps the city intact
(arms S2, S4a, XS, FBS). **Limit (measured, arm S5):** a stock game that SAVES the city writes it without the section,
so the variants of that file are gone for good; the tiles stay as base pieces, nothing is dropped.

## 5. Old saves with raw variant ids

- Without the mod at all: the tiles are dropped on load and on the next save (newpiece arm R, -22 tiles). No DLL change
  can help a game that does not run the DLL.
- With the mod: they load as variants (the data is installed) and the first save converts the file to the safe form
  (arm S1 is exactly this: newpiece's raw save, opened and saved once).
- Offline, for a player who no longer has the mod: `re/tools/netmod/netvariant.py fallback <in> <out> --table
  <netmod_variants.txt>` rewrites raw variant ids to their base and writes the same section. On newpiece's raw save its
  output has network sections byte-identical to the in-game S1 save, and it loads on stock with no tile lost (arm FBS).
  `netvariant.py scan <city>` lists raw variant tiles and the section's entries.

## 6. Not covered

Highway, onramps, subway, pipes, bridges as bases (their id paths are listed above but not wired); variants of rail or
power pieces; a crossing that keeps the variant look; removing a crossing again; 1024 cities; the owner's dev install
(MAIN\Apps); the release layout (DLL in Apps); a traffic run over a crossing the DLL built (see RESULTS, arm T).
