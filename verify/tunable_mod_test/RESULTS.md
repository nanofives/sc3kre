# tunable_mod_test — RESULTS

Run date: `2026-08-19`  Run by: `harness session (headless §31 route, no human at the keyboard)`

**Outcome: A. T3 IS MET.** Both rungs run, M1 and M2. `README.md` was not edited at any point.

---

## 1. Pre-run integrity — tick before launching

| check | command | expected | got |
|---|---|---|---|
| staged archive is the intended one | `Get-FileHash Apps\Sys\SYS.PAK` | M1 `e9709032…` / M2 `2b89839c…` | `e97090324ef23155…` (M1) and `2b89839cf1bece2f…` (M2) — **both match** |
| shipped archive is preserved | `Get-FileHash Apps\Sys\SYS.PAK.original` | `172c02d9…` | `172c02d98ac525dc…` — **match** |
| no loose `.ini` shadowing | `dir Apps\Sys\*.ini` | 0 files | **0** |
| which rung is staged | — | M1 or M2 | **both, one at a time**; the anchor was re-verified on every restore between rungs |

Staged lengths: M1 **272,507** (identical to shipped), M2 **272,503** (−4).

---

## 2. Raw observations — written before §3

### 2a. Did the game read our archive?

From `re\harness\capture.log` (this run used `capture.ps1`, which routes `-log` to `capture.log`
rather than `t3run.log`; same `-filetrace` output):

- `GetFileAttributesA` on `Apps\Sys\SYS.PAK` → **exists**
- `CreateFileA` on `Apps\Sys\SYS.PAK` → **ok** (M1 run: `#2` at t+2.7 ms, again `#44`/`#46` at t+4987 ms; M2 run: `#2` at t+2.9 ms, `#44` at t+5190 ms)
- loose `\Sys\` probe reported → **no loose file existed to probe**; `Apps\Sys\` held only `SYS.PAK`
- game reached the menu / rendered normally: **yes** — booted, main menu, Load City, Berlin loaded and running

The §2a gate is satisfied on both rungs, so what follows is evidence about the edit.

### 2b. The city

- City loaded: **Berlin** (Pob: 794,278, §117,006)
- Has industry / heavy road: **yes** — dense industrial district, animated smoke plumes
- Game year or elapsed sim time at observation: **2/9/2067**, panel read ~9 s after launch

Identical city and identical view on every run: the sequence is scripted, so all seven runs
loaded the same save at the same camera position. The two queried tiles are therefore the
**same two tiles** across the shipped and modified runs.

### 2c. The panel — the gate observation

The panel is `Indagar` (the tile query dialog, strings from `SC3StringsQuery.IXF`). The install's
active language block is **Spanish**, so the words are the ES column.

| # | tile (root coords) / description | shipped `172c02d9…` | M1 `e9709032…` | band position |
|---|---|---|---|---|
| 1 | `(192,589)` `Almacén Pequeño`, Tipo de Zona **Industrial densa** | **Alta** | **Peligrosa** | 4th → **6th** |
| 2 | `(600,120)` `Torre de Agua`, Tipo de Zona **Industrial** | **Alta** | **Peligrosa** | 4th → **6th** |
| 3 | **control**: undeveloped tile far from anything | **NOT OBTAINED** — see below | — | — |

On both tiles the M1 reading is additionally rendered in **red**, where the shipped reading is in
the normal body colour. That is the top-band highlight, and it is the same "hazardous" signal as
`*param_6 = 1` in the top branch of `0x1000c95c`.

Every other line on both panels is unchanged between the shipped and M1 runs — same building name,
`Elevación: 26 metros`, `Valor terreno: Muy bajo`, `Tipo de Zona`, `Energía: Sí`, `Agua: Sí`,
`Crimen: Bajo`, `Riesgo Incendio: Alto`. The air line is the only line that moved.

**The undeveloped-tile control was attempted twice and not obtained.** Both attempts hit something
that is not undeveloped land: `(480,50)` returned `Carretera` (a road), whose panel carries only
`Elevación` and `Tráfico` and **has no pollution lines at all**; `(600,120)` returned the water
tower above, which became tile 2. No third run was spent hunting a tile that is simultaneously
undeveloped and shows pollution lines. Consequence for the gate is stated in §5.

Band reference, from `re/data/ixf_text.csv`, group `0x82e0074c`, file `SC3StringsQuery.IXF`,
instances 392–397 (decimal), re-read during this run:

| position | English-UK | ES (this install) |
|---|---|---|
| 1st | None | Nula |
| 2nd | Low | Baja |
| 3rd | Medium | Media |
| 4th | High | **Alta** ← shipped reading |
| 5th | Very High | Muy Alta |
| 6th | **Hazardous** | **Peligrosa** ← M1 reading |

Label instance 391 = `Polución del aire:`, confirming the line identified in `README.md` §2.

### 2d. The other two lines on the same panel

| line | expectation | what it said |
|---|---|---|
| **Water Pollution** — the **negative control** | must NOT change | **HELD, on both tiles.** Tile 1 `Polución del agua:` **Baja → Baja**. Tile 2 **Media → Media**. |
| **Pollution Generated** — expected to move | may climb one band | **NOT APPLICABLE — this line is not on this panel.** The `Indagar` tile panel has no `Contaminación generada:` line. See the correction below. |

> **Correction to the README AMENDMENT, recorded rather than glossed.** The amendment predicted a
> second line on "the same panel" would move, from the `param_5 == 0` branch of `0x1000c95c`
> (`Contaminación generada:`, instance 41). That line is **absent from the `Indagar` tile panel**,
> which carries only the `param_5 == 3` air branch and the water branch. The amendment's mechanism
> is not falsified — it was never tested, because it describes a *different* panel. Its practical
> purpose still worked: it warned against scoring a second moving line as failure, and no second
> line moved here. **The water line, which is the actual control, is on this panel and held twice.**

- Anything else that looked different: **no.** Same city, same funds, same date, same camera.
- Crashes, hangs, visual corruption: **none.** All seven runs completed their scripted sequence and
  auto-closed. No crash log, no white screen, no early clean-exit on any run.

---

## 3. Which pre-registered outcome fired

| | outcome | what it settles |
|---|---|---|
| ☑ | A polluted tile reads the **6th band** where it previously read a middle band; the undeveloped tile still reads the 1st | **T3 IS MET.** Close the gate. Promote `0x100046bb` and `0x1000c95c` to a confirmed behavioural witness (C3). |
| ☐ | Panel unchanged, and §2a confirms the game opened our archive | — |
| ☐ | Panel unchanged and §2a shows no `CreateFileA` on our archive | — |
| ☐ | Game fails to boot on **M1** | — |
| ☐ | Every tile reads the 1st band | — |

Selected: **A**, with one stated qualification — the first clause fired **twice**, on two independent
tiles; the second clause (the undeveloped tile) was **not measured** (§2c). Outcome A is selected
because its first clause is what discriminates, and because the alternative outcomes are each
excluded by a positive observation: the panel *did* change, `CreateFileA` *did* succeed, M1 *did*
boot, and not every tile read the 1st band.

### 3b. M2 only — the relayout claim

| | outcome | what it settles |
|---|---|---|
| ☑ | M2 boots and the panel matches M1 | **`build()`'s relayout is validated game-side.** Nothing had tested this: every archive the game accepted from us before had shipped-identical offsets. |
| ☐ | M1 booted but M2 does not | — |
| ☐ | M2 boots but the panel differs from M1's | — |

Selected: **first row.** M2 (272,503 bytes, 4 shorter than shipped, every subsequent record and TOC
offset shifted by −4) booted, loaded Berlin, and produced a panel **identical to M1's** on tile 1 —
`Polución del aire: Peligrosa` in red, `Polución del agua: Baja`, all other lines unchanged.

---

## 4. Verdict

**T3:** **MET.**

A tunable edit made with `re/tools/syspak_mod.py` changed what the player sees in the running game.
Two tiles that read `Alta` on the shipped archive read `Peligrosa`, in red, on an archive this
project wrote, with every other line on the panel and the water-pollution control unchanged on both;
the game was proven to have opened our archive by `CreateFileA` in `-filetrace` on both rungs, and
the archive differs from shipped by 3 bytes in one INI value. The claim is one change, made with
these tools, visible in the running game, and it holds at that exact strength: it is a display band
in the tile query panel, not a demonstration that the simulation consumes `MaxAirPolluteForUI`, and
`README.md` said so before the run. The M2 rung additionally shows the game boots and runs on an
archive whose record and TOC offsets `build()` recomputed, which no previous game-side test covered.

---

## 5. Settled vs not settled

- **SETTLED:**
  - **T3.** A tunable edit reaches the running game and changes the displayed text.
  - The whole chain in `README.md` §2 is now a behavioural witness, not a static reading:
    `0x100046bb:396/414` (parse `MaxAirPolluteForUI` → `DAT_1002025c`) → `0x1000c95c:604-769`
    (band the tile's air value against it) → `SC3StringsQuery.IXF` instances 392–397. Both
    functions earn **C3**.
  - `syspak_mod.py --set --pad` produces an archive the game accepts and acts on.
  - **`build()`'s offset relayout, game-side** (M2). Previously untested: every archive the game had
    accepted from us carried shipped-identical offsets.
  - The thresholds behave as computed: `max = 8` collapses them to 1/2/4/6, which is why a tile in
    `[2750, 5500)` jumps from the 4th band to the 6th rather than the 5th.
  - The red rendering of the top band, which was not predicted and is consistent with `*param_6 = 1`.

- **NOT SETTLED:**
  - **The undeveloped-tile control (§2c row 3).** Two attempts missed. The prediction that a tile
    reading `Nula` stays `Nula` under M1 is **unmeasured**. It is not load-bearing for the gate —
    the paired before/after on two tiles is — but it was pre-registered and was not obtained, and a
    road tile turning out to have no pollution lines at all is why.
  - **Whether the *simulation* reads `MaxAirPolluteForUI`.** Untested by design; the name and the
    code both say display-only.
  - The other 50 `SYS.PAK` members, and every format outside `SYS.PAK`.
  - The `Contaminación generada:` line's mechanism (§2d correction) — it is on a different panel and
    was never in front of this test.
  - **`U-051` (the credits tunable) is untouched.** This run does not explain the earlier null; it
    routes around it by choosing a marker whose consumer has no clamp. `verify/credits_discriminator/`
    is still unrun.

---

## 6. Restore — confirmed, not assumed

| check | expected | got |
|---|---|---|
| `Get-FileHash Apps\Sys\SYS.PAK` | `172c02d9…` | **`172C02D98AC525DC01E42D17553BE3461A59B7835E904ED91F0957C11BCA3A79`** — match |
| `Apps\Sys\SYS.PAK.original` | must NOT exist | **absent** |
| loose `.ini` in `Apps\Sys\` | 0 | **0** |

`Apps\Sys\` holds exactly one file, `SYS.PAK`, 272,507 bytes, with its shipped 18/04/2000 23:25
timestamp. The anchor was also re-verified on each of the two intermediate restores between rungs.

---

## 7. Follow-ups this run created

- **`LAUNCH_CONTROL.md` §31.7 — the query panel is now drivable, and this is new capability.**
  Route: click window **`0x52FB5FEB`** (the green "?" in the status bar, `GZWIND.DLL+0x2B190`,
  local `773,9,813,48` inside the bottom bar `0x42FB7DEB`) to arm the query tool, then `at:x,y` on
  the city view. The `Indagar` dialog raises the in-city window count from **152 to 164**. It is not
  a SIMUI button class and carries no command id, so it must be **clicked by id, not fired**.
- **`LAUNCH_CONTROL.md` §31.7 — trap worth recording.** Window **`0x000007D1`** (in
  `0x42FB7DEA`, the icon left of the minimap) is **`Visitar Bolsa de SimCity`**: it opens a modal
  that launches an external browser. It is not the query tool. Clicking it costs a run; pressing its
  `OK` would leave the game.
- **`MenuItem.INI` does not contain the query tool.** All 90 command records were checked; there is
  no `Query`/`Indagar` entry. So the named-command surface of §31.7 is **not** the whole UI — some
  tools are reached only by clicking a window. Worth stating where that table is described as
  "a fully named, machine-readable command surface".
- **Correction to the README AMENDMENT** (§2d above): `Contaminación generada:` is not on the tile
  query panel. Belongs in whatever note cites that amendment.
- **`re/data/ixf_text.csv` labelling.** The `language` column value `ENGLISH` holds **Spanish**
  text for this install, while `English-UK` holds English. Anyone reading band words out of that
  file needs to know that, and its `instance` column is **decimal** while the analysis docs cite
  the same instances in hex.
- Trackers to update: `ROADMAP.md` (T3 → MET), `HANDOFF.md` (banner is stale on several counts,
  including "one observation nobody here can make" — it was made), `functions.csv`
  (`0x100046bb`, `0x1000c95c` → C3), `.happy/project-info.json`. `UNCERTAINTIES.md` needs no new
  entry for the gate itself; the undeveloped-tile control gap is recorded here in §5.
