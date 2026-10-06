# RESULTS — dialogs follow the window, RCI under dialogs, no SetRect on freed windows

Run 2026-10-05. Pre-registration `PRE.md` (`47c25b9`). Build 198,144 B, `dialogs=1` read back from
`FLAGS>`. Single 1680x1050 display at 100%. Files: `T/` (pre-registered run), `T_max/` and
`T_native/` (surveys on the new build).

| # | check | result |
|---|---|---|
| 1 | maximized, each dialog centered in the map area (1584x923, center 792,461) | PASS: Reunirse, budget, city data 4 in the run. Snapshots and city data 6 did not open in the run's sequence. The survey that followed opened all five centered at (791..792, 461) |
| 2 | budget open across 1680x979 -> 1280x700 -> 1680x979 | PASS: re-centered each time (`[342 82 842 562]`, then `[542 221 1042 701]`) |
| 3 | Reunirse dragged to `[400 384 783 738]`, then resize to 1280x700 | PASS: `[400 346 783 700]`, moved only enough to stay inside the 700-tall client |
| 4 | Reunirse dragged over the RCI | PASS: dialog `[1420 771 1803 1125]` covers RCI `[1480 891 1521 979]`, mean pixel change 44.5 over the RCI, and the frame shows the dialog where the RCI was (`T/4_crop.png`) |
| 5a | Reunirse at 800x600 | FAIL as written, criterion wrong: see below |
| 5b | snapshots at 800x600 | PASS: `[96 92 608 452]`, inside the client (was `[584 309 1096 669]` before the change) |
| 6 | access violations | 0 in both launches |

**Row 5a.** The run opened Reunirse at 800x600 after rows 3 and 4 had dragged it to
`[1420 771 1803 1125]`. Dialogs are created once and reopen where they were last, so it reopened
outside the client and the manager centered it in the map area: `[160 95 543 449]` is exactly centered
in 704x544. The pre-registered expectation assumed a dialog that had never been moved. The stock game
would have reopened it off-screen in that case. A fresh launch at 800x600 (`T_native/`) shows every
dialog at its stock spot: Reunirse `[8 8 391 362]`, budget `[102 32 602 512]`, city data 4 `[8 8 392 362]`,
city data 6 `[40 34 464 474]`, snapshots `[96 92 608 452]`.

## Note for the owner

At 800x600 the stock game itself places Reunirse and city data 4 and 6 at the top-left, not centered.
The mod keeps that at native size and centers them at every other size.
