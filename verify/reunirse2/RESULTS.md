# RESULTS: every Reunirse page follows the dragged position (child `reunirse2`, 2026-10-12)

Pre-registration: `PRE.md` (7d74790). Branch `child/reunirse2` from `round/1012`. Fix: sc3resize MEETALL (b0000a3 plus
the size-rule commit), `SC3RESIZE_MEETALL=0` turns the new parts off, `SC3RESIZE_DLGSTAY=0` everything.
Evidence per arm: `<arm>/chain.json` (`reunirse2_chain.py`), `F4_sizes/sizes.json` (`reunirse2_sizes.py`), probe
states `*.json`, frames `*.png` (gitignored, kept in MAIN `verify/reunirse2/`), mod logs
`MAIN re/harness/inst_reunirse2/resize_<arm>.log`.

**Verdict: PASS.** The owner's "otro cartel" is the advisor's topic text page (and the pages after it). Reproduced on
round/1012, fixed, looked at in screenshots at 800x600 and maximized.

## Deviations from PRE.md (stated before scoring)

1. **The static inventory was wrong about the topic page.** PRE named `FUN_1000823d` (337x254, no slot) as the topic
   page. In C1 the topic page came up 384x354 at [640 296] = slot +0x18/+0x1c. Its real builder/closer are
   `FUN_10008d40` / `FUN_1000a1a2` (handler `FUN_10008ceb`). `FUN_1000823d` is the petitioner answer popup. F2 in PRE
   (centre the topic page on the previous rect) was replaced by the same slot sharing as the other pages.
2. **Second cause, found in F1:** the topic page's back arrow builds the advisor BEFORE the topic page's closer runs
   (log: build at 68581 ms, topic close at 68587 ms), so the advisor read the stale slot (F1: 5/6, back JUMPS).
   Added before the counted runs: every builder first takes the spot of the page still open.
3. **Size rule, found in F3:** closed maximized, restored, reopened at 800x600 -> kept at [210 125]. The 800x600
   "fully inside: keep the game's spot" rule kept it. Added: a Reunirse page whose spot was noted at another client
   size is centred at 800x600 too (F4_sizes).
4. Page 0x62be6000 (button 0x62be5009 on a topic page) and the answer popup (petitions with answer buttons) did not
   come up in the test city. They are covered by the same code, static only.

## Results

| Arm | Build, flags | Size | Switches that follow | Notes |
|---|---|---|---|---|
| C1 control | round/1012 (c30dc0d) | 800x600 | list -> advisor only | advisor dragged to [140 115] -> topic at its slot [640 296], centred to [160 95] by the poll. Topic dragged to [280 195] -> back -> advisor at [140 115] |
| X1 control | final, `MEETALL=0` | 800x600 | 1/2 before the chain broke | topic at [640 296 1024 650], half outside the client, X out of reach (it reused the advisor's address, so the poll did not see it as new) |
| F2 | b0000a3 defaults | 800x600 | 6/6 | list, advisor, topic, back, topic 2, reopen, advisor |
| F2 | same | 2560x1351 | 6/6 (two passes) | |
| F3 | b0000a3 defaults | 800x600 | list -> petitioner [40 195], petitioner dragged [210 125] -> back -> list [210 125] | petitioners after unpausing |
| F3 | same | maximize with the dragged petitioner page open | stays [210 125], back -> list [210 125] | |
| F4 | final defaults | 800x600 | 6/6 | frames looked at: topic over the dragged advisor spot, advisor over the dragged topic spot, no stale copy |
| F4 | same | 2560x1351 | 6/6 | frame looked at |
| F4_sizes | same | 800 -> max -> 800 | 4/4 | closed at 800x600 [20 235], reopened maximized centred [1040 470], advisor follows; closed maximized, reopened at 800x600 centred [160 95], advisor follows |
| D0 | final, `DLGSTAY=0` | 800x600 | 1/6 (stock per-page spots) | no DLGSTAY detour installed, the opt-out works |
| K1 stock DLLs | final defaults, `Simcity_stock_reunirse2` | 800x600 | 6/6 | first open at the stock (8,8) |
| K1 | same | 2560x1351 | 6/6 | |

Faults: every log has exactly one `VEH FAULT 0xC0000096 @ SC3U.exe+0x84122` at startup (known, unrelated).

## Still open
- Answer popup and page 0x62be6000: static only.
- DPI: positions are game client coordinates, the rule does not depend on DPI. The owner's laptop was not tested.
- Known from `reunirse`, not touched: the first click on the Reunirse button right after an X close is sometimes
  dropped (the drivers click twice when nothing opened).
