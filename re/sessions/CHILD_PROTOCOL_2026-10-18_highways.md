# Child protocol, 2026-10-18: the highway program

You are one child of the orchestrator session titled **"SC3 avenues merged; highway intersections + diagonal"** (find it
with `mcp__happy__list_peers`). The owner asked to "improve on the [highway] intersections, add diagonal intersections"
and picked the full set: a **cloverleaf X**, a **T that connects**, **diagonal flyovers with ramps**. Each child owns ONE
stream. Several children run the game AT THE SAME TIME. MAIN = `C:\Users\maria\Desktop\Proyectos\Simcity` (repo root,
live game install). This program follows the avenue program (`CHILD_PROTOCOL_2026-10-17.md`): same tools, same rules,
now all on `main`.

## 0. First minutes
1. Write `MAIN\re\sessions\STATUS_<name>.md` (headings in section 9, "starting"). Update it at every milestone: it is
   what survives a crash or a lost session.
2. Read, in your worktree: `verify/highways/STOCK.md` (what the stock game does, measured in game, READ FIRST),
   `re/tools/netmod/hw_lab.py`, `re/tools/netmod/rb_lab.py`, `re/harness/src/sc3netmod_rbt.c` (the shared hooks; note
   `rb_pass` returns early for `net != 1`: highways are net 4), `re/harness/src/sc3netmod_dav.c` + `sc3netmod_dbv.c`
   (blocks on those hooks, claims, save overrides), `re/tools/netmod/diagave_paint.py` (world-scene painter),
   `re/analysis/NET_LANES.md` (turn matrix props 310, highway lanes: node y 1024, two lanes of one direction per cell),
   `re/analysis/NETBRIDGE.md` + `NETVARIANT.md` (highway variants as bases), `MULTITILE.md` (templates write pieces into
   cells the player did not draw; the On-ramp tool path), `NET_RAMPS.md`, `NETPACK.md`, `NET_ART.md`, `TILER_SIM.md` (skim).
   Memory notes in `C:\Users\maria\.claude-account3\projects\C--Users-maria-Desktop-Proyectos-Simcity\memory\`:
   `project-highway-program.md`, `project-avenue-program.md`, `project-diagonal-avenue-feasibility.md`,
   `project-net-ramps.md`, `project-multitile-templates.md`, `project-net-art-kit.md`, `project-new-network-piece.md`,
   `project-tiler-simulator.md`, `reference-sc3-mod-recipes.md`, `feedback-light-testing.md`, `feedback-always-windowed.md`.

## 1. Your paths (already created for you)
| what | path |
|---|---|
| worktree (edit ONLY here) | `C:\Users\maria\Desktop\Proyectos\Simcity_wt_<name>`, branch `child/<name>` from `main` (avenue program merged) |
| test tree (hard-linked stock install) | `C:\Users\maria\Desktop\Proyectos\Simcity_stock_<name>` |
| instance folder | `Simcity_stock_<name>\re\harness\inst_<name>\` (mods_launch.exe, sc3resize.dll, `lab.sc3`) |

Hard links share data with the other trees: never edit a game file in place in your test tree (netpack install is
link-safe). Never touch another stream's worktree, tree or game (reading another worktree's files is fine). Never write
anything under MAIN's `Apps`, `Cities`, `Buildings`, `Scripts`.

## 2. Account rules (you run on claude2, under a managed policy)
- Python: `~/bin/py -3.12` (or `py -3.12`). Commands outside the allow list are refused, not prompted. Compound commands
  need every part allowed; set env vars with `env X=1 cmd` or `export`.
- **You cannot `git add` / `git commit`.** Leave your changes in the worktree. List every file you created or changed
  under "files owned" in your status file; the orchestrator commits them by path. `git diff`, `git log`, `git status`
  are fine.
- Launch the game through `cmd //c` or `pwsh -c` (a bare `./mods_launch.exe` is not on the allow list).
- If something you need is refused, write it under "blocked on" and message the orchestrator; do not work around it.

## 3. Build, install, launch
```
pwsh -NoProfile -File <WT>\re\scripts\build_mod.ps1 -Mod sc3netmod -Src <WT>\re\harness\src -Out <TREE>\re\harness\inst_<name>
~/bin/py -3.12 <WT>\re\tools\netmod\netpack.py install <WT>\re\tools\netmod\examples\<package> --tree <TREE> --allow-tree
cmd //c "<TREE>\re\harness\inst_<name>\mods_launch.exe -multi -- <TREE>\re\harness\inst_<name>\<city copy>.sc3"   (run in background)
```
The launcher prints `pid = N`: that N is yours. Set `SC3_PID=N` and `SC3_LAB_DIR=<inst folder>` for every lab tool.
Stop with `taskkill //PID N //F` after checking N is yours. NEVER kill by name. `harness_claim.ps1` is NOT used. Always
windowed. Start at least 15 s after another stream's launch if you see one starting (`tasklist`).

Lab: `lab.sc3` = the "Roadless Paradise" lab (altitude 82) with flat dry windows **x 42..74 / z 12..44** (32x32),
**x 94..116 / z 78..100** and **x 120..142 / z 2..46**. Trees do not block highway drags. Copy it per run (`lab2.sc3`,
...), never load the original. Driving: `re/tools/netmod/hw_lab.py` = rb_lab plus `hway X0,Z0 X1,Z1 --alt 82` (Highway
tool, diagonal when |dx| == |dz|) and `funds NOW` (the lab starts at $24,675 and a highway costs ~$300 per cell: set
$2,000,000 first, see its docstring). `cam X,Z ZOOM ROT` can fail silently and leave the old state: print its output
and check that the drag pixels are inside 800x600. Save: `nr_drive.py save` (menu 0x10009002). Unpause = click the
HUD play button, pause = the pause button (or sc3resize keys P, 1-4). Your DLL log is `sc3netmod.log` in the instance.

## 4. How the existing pieces work (reuse, do not reinvent)
- **Pieces** are netpack variants (new ids with a stock base piece for tiling and saves), with art (`png_dir` +
  `anchors.json`) and lanes (`*.lanes.json`, lanekit) and the turn matrix (props 310, `connects`): **a highway piece
  whose turn matrix is wrong blocks highway trips** (`NET_LANES.md` arm H). sc3netmod places them itself after a retile
  and after a city load via the piece writer FUN_10008919, reverts what no longer qualifies with the rect retile, and
  overrides the saved id (`rb_save_id`) so a game without the mod loads a sane stock city.
- **Blocks** hang off RBT's two hooks in `sc3netmod_rbt.c` (`rb_pass` = edit, `rb_load_pass` = load), each with its own
  table lines (read in `rb_file`, skipped in `sc3netmod.c table_read`), env opt-out (`SC3NETMOD_<X>=0`), install gate
  term in `rbt_install`, and stats. Highways arrive as `net == 4` passes. Put your rule in its OWN file
  `re/harness/src/sc3netmod_<name>.c`; keep edits to shared files (sc3netmod.c, sc3netmod_rbt.c, netpack.py,
  netpack.schema.json) to a few lines each, marked `/* task <name> */`. Merge trap from the avenue program: the
  `rbt_install` gate and its error resets must name EVERY block; a block missing there is silently off.
- **Art**: world-scene painting (`diagave_paint.py`): every output pixel is unprojected to world coordinates and
  coloured by sampling STOCK frames, so plain highway equals stock and neighbours meet exactly. Highways are ELEVATED
  (deck on embankment walls; the X has a bridge deck and an underpass), so the highway painter (stream `hwcore`,
  section 5) adds height: deck surface at the deck height, walls as vertical faces, decks over a lower carriageway.
  Lane markings: the stock highway dashes (`lanelines.py` palette comes from highway 73).
- **Offline first**: `netart.preview` (see `diagave.py cmd_preview`) before any game run; the stock tiler runs offline
  (`tiler.Tiler(...).retile(4, cells)` for highways).

## 5. Streams, shapes and ids (no two blocks may convert the same cells)
| stream | owns | ids |
|---|---|---|
| `hwcore` | the SHARED base: net-4 dispatch on RBT's hooks (`sc3netmod_hwy.c`: read highway cells, write a highway variant into a cell that holds highway AND into an EMPTY cell (claim rule: no building, zone or other network; trees are cleared), revert, save ids, a `hwy_claimed()` like `dbv_claimed()`), the elevated-highway painter `hwpaint.py` (deck, walls, curves and arcs of any radius, 45-degree runs, a deck bridging over a lower carriageway, ramps that rise or fall), and highway lanes / turn matrices for one-lane ramps. Proof: stock 73 / 15051 / a stock curve repainted by `hwpaint.py` match the stock frames; one variant written into an empty cell next to a highway in game, kept through a retile and a save + reload. | 21100..21119 |
| `hwx` | straight highway x straight highway (the stock 4x4 flyover, `STOCK.md`): a CLOVERLEAF (four loop ramps for the left turns, outer ramps for the right turns, every movement connected) when the quadrants are free, else a cleaned-up flyover in the stock 4x4. Also the X on a slope (stock leaves 15149 forever) if it fits. | 21120..21199 |
| `hwt` | straight highway ending on a straight highway (a T): the stem's end next to the through highway's side, and the side hit that stock leaves as 15149. Every movement connects (stem to both directions, both directions to the stem); a ramp that crosses the near carriageway bridges over it. | 21200..21259 |
| `hwdx` | diagonal highway x straight highway (45 degrees; stock leaves two 15149 blocks and breaks the diagonal): a flyover with connecting ramps for every movement. | 21260..21359 + 21460..21559 (granted 2026-10-18) |
| `hwdd` | diagonal highway x diagonal highway (the two diagonal families meet at 90 degrees; stock makes a straight stub + 15149): a flyover with connecting ramps, a cloverleaf turned 45 degrees if that reads best. | 21360..21459 |
**Lane curve shape numbers** (hwlanes.py writes one new VPathAtt curve per lane cut, key = shape * 256 + rotation;
granted 2026-10-18, clear of the stock shapes, which end at 20002, and of every piece id): hwcore its piece ids
21100..21119 plus 23300..23399, hwdx 22000..22499, hwx 22500..22799, hwt 22800..22999, hwdd 23000..23299.
**Wave 2 grant (2026-10-19):** `hwave` (highway <-> avenue transition) piece ids 21600..21699, lane curve shapes 23400..23599.
**Ramp geometry** (program rule 2026-10-18): ramp deck 0.62 (stock ramp width), hwx.py's W 0.31, loop R 1.25, outer
ramp radius 2.06, turn arcs 0.75, 0.19 cell of ground between decks; open the highway parapet at every join (Deck gaps).

Not in this wave (say so if your rule meets them, refuse them): T's involving a diagonal, highway x avenue, highway
merges / splits, interchanges closer than their footprint. If your rule would match another stream's shape, refuse it.

**hwcore publishes, the others copy.** Until hwcore's files exist, the four shape streams work on geometry and rules
(below). When hwcore messages "published" (it also writes the list in `STATUS_hwcore.md`), COPY its files verbatim into
your worktree (`sc3netmod_hwy.c`, `hwpaint.py`, whatever it lists) and never edit them: ask hwcore for changes
(`mcp__happy__send_to_session` to hwcore's session, cc the orchestrator). Identical copies merge cleanly.

## 6. Milestones (shape streams)
1. **Plan** (no art needed): run the drags in game (or offline tiler) and record what stock leaves; design the footprint
   (which cells, which carriageway goes over, where each ramp runs, lane directions, minimum free area, the fallback),
   and the rule (pattern that triggers it, refusals). Draw a TOP-DOWN plan: cell grid, carriageways and ramps as lines
   with direction arrows, the deck that bridges, piece ids per cell. Save `MAIN\verify\<name>\owner_shots\<name>_plan.png`
   and message the orchestrator "plan ready". Keep going; the orchestrator relays the owner's corrections.
2. **Mockup**: the plan painted with `hwpaint.py` (netart preview, zoom 4 and 3, views 0 and 1):
   `MAIN\verify\<name>\owner_shots\<name>_mockup.png`, message "mockup ready".
3. **Build**: block file, package `re/tools/netmod/examples/<package>` (art builder, lanes, turn matrices, saved ids),
   offline twin + check, one in-game check (drags, every movement's lanes exist, save + reload), final sheet
   `MAIN\verify\<name>\owner_shots\<name>_sheet.png`, `verify/<name>/RESULTS.md` in your worktree.

## 7. Owner workflow (read this twice)
- The owner reviews PICTURES and corrects with sketches. Light testing (`feedback-light-testing.md`): build it well,
  one quick in-game check, screenshots. No A/B campaigns, no pre-registration.
- Stock look: sample stock highway art (deck, walls, dashes), curbs and walls continuous, no cyan, no terrain holes,
  no seams between neighbouring pieces.
- Game art (PNGs, screenshots) is never committed; `art/` folders are gitignored.

## 8. Talking to the orchestrator
`mcp__happy__send_to_session` to the session titled as above. One short message per milestone: "plan ready: <path>",
"mockup ready: <path>", "published: <files>" (hwcore), "in-game check done: <sheet>, files owned: ...", or
"blocked: <what>". The orchestrator answers the same way.

## 9. Status file headings (`MAIN\re\sessions\STATUS_<name>.md`)
goal / design (footprint, cells, pieces, rule) / built (files, uncommitted) / proven in game vs offline only /
blocked on / files owned / instance (folder, last PID) / needs owner (pictures, design questions) / asks of other
streams.

## 10. When done
Status file complete, game stopped (your PID only), changes left in your worktree, final owner sheet, results note.
Message the orchestrator and end your turn with a short summary.
