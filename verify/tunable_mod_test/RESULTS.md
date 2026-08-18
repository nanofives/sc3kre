# tunable_mod_test — RESULTS

> **TEMPLATE — nothing here is filled in yet.** Fill the `____` blanks. Complete §2 (raw
> observations) **before** reading §3, and do not edit `README.md` at any point: its predictions
> were committed in `acc50fa` ahead of the run and their value is that they are fixed.

Run date: `____`  Run by: `____`

---

## 1. Pre-run integrity — tick before launching

Answer these from the terminal, not from memory. If any is NO, stop and fix it; a result
gathered on an unverified install settles nothing.

| check | command | expected | got |
|---|---|---|---|
| staged archive is the intended one | `certutil -hashfile "Apps\Sys\SYS.PAK" SHA256` | M1 `e9709032…` / M2 `2b89839c…` | `____` |
| shipped archive is preserved | `certutil -hashfile "Apps\Sys\SYS.PAK.original" SHA256` | `172c02d9…` | `____` |
| no loose `.ini` shadowing | `dir Apps\Sys\*.ini` | 0 files | `____` |
| which rung is staged | — | M1 or M2 | `____` |

---

## 2. Raw observations — write these down BEFORE §3

Verbatim. No interpretation in this section, not even a parenthetical.

### 2a. Did the game read our archive?

From `re\harness\t3run.log`:

- `GetFileAttributesA` on `Apps\Sys\SYS.PAK` → `____`
- `CreateFileA` on `Apps\Sys\SYS.PAK` → `____`
- loose `\Sys\` probe reported → `____`
- game reached the menu / rendered normally: `____`

> If `CreateFileA` is absent, **stop**. Whatever happened on screen is not evidence about the
> edit, because the game never opened the file we changed.

### 2b. The city

- City loaded: `____`
- Has industry / heavy road: `____`
- Game year or elapsed sim time at observation: `____`

### 2c. The panel — the gate observation

Query tiles and record the **exact word** on the air-pollution line.

| # | tile (x,y) or description | what the air line said | band position (1st–6th) |
|---|---|---|---|
| 1 | `____` polluted tile near industry | `____` | `____` |
| 2 | `____` second polluted tile | `____` | `____` |
| 3 | `____` **control**: undeveloped tile, far from anything | `____` | `____` |

Band reference — record the word, then map it here:

| position | English-UK | ES |
|---|---|---|
| 1st | None | Nula |
| 2nd | Low | Baja |
| 3rd | Medium | Media |
| 4th | High | Alta |
| 5th | Very High | Muy Alta |
| 6th | **Hazardous** | **Peligrosa** |

- Water-pollution line on the same tile (untouched by this edit, so a **negative control**):
  `____`
- Anything else that looked different: `____`
- Crashes, hangs, visual corruption: `____`

---

## 3. Which pre-registered outcome fired

From `README.md`, unedited. Tick exactly one.

| | outcome | what it settles |
|---|---|---|
| ☐ | A polluted tile reads the **6th band** where it previously read a middle band; the undeveloped tile still reads the 1st | **T3 IS MET.** Close the gate. Promote `0x100046bb` and `0x1000c95c` to a confirmed behavioural witness (C3). |
| ☐ | Panel unchanged, and §2a confirms the game opened our archive | Writer exonerated by the 3-byte diff. Finding is about the **consumer**: log an `[UNCERTAIN]` that `0x1000c95c` is falsified as this panel's source, and look for a second banding site. **Re-diff the staged archive against shipped before concluding anything.** |
| ☐ | Panel unchanged and §2a shows no `CreateFileA` on our archive | Staging failed. Not a result. Re-stage and re-run. |
| ☐ | Game fails to boot on **M1** | Most informative failure available: M1 is shipped-identical apart from 3 digit bytes, so this would mean the value destabilises SIMECO — a finding about the game, not the toolkit. |
| ☐ | Every tile reads the 1st band | Undeveloped tiles were sampled. Not a result; re-observe near industry. |

Selected: `____`

### 3b. M2 only — the relayout claim

Fill this only on the M2 run.

| | outcome | what it settles |
|---|---|---|
| ☐ | M2 boots and the panel matches M1 | **`build()`'s relayout is validated game-side.** Nothing had tested this: every archive the game accepted from us before had shipped-identical offsets. |
| ☐ | M1 booted but M2 does not | A real defect in `build()`'s offset table, isolated to the relayout path since the two archives differ in nothing else. Matters beyond this test — every future key-adding edit uses that path. |
| ☐ | M2 boots but the panel differs from M1's | The relayout corrupted a *different* member. Re-parse both and diff member by member. |

Selected: `____`

---

## 4. Verdict

**T3:** `____`  (MET / NOT MET / inconclusive — and if inconclusive, say which check was missing)

One paragraph, stating the claim at exactly the strength the evidence supports:

`____`

---

## 5. Settled vs not settled

- **SETTLED:** `____`
- **NOT SETTLED:** `____`

Be explicit about anything the run *could* have covered and didn't. The T1 record's value came
from listing what it left open, not from claiming more than it measured.

---

## 6. Restore — confirm, do not assume

| check | expected | got |
|---|---|---|
| `certutil -hashfile "Apps\Sys\SYS.PAK" SHA256` | `172c02d9…` | `____` |
| `Apps\Sys\SYS.PAK.original` | must NOT exist | `____` |
| loose `.ini` in `Apps\Sys\` | 0 | `____` |

---

## 7. Follow-ups this run created

Anything that needs to reach a tracker. Note the owner file for each.

- `____`

Trackers to update once §4 is decided: `ROADMAP.md` (T3 status), `HANDOFF.md` (banner + verdict),
`functions.csv` (`0x1000c95c`, `0x100046bb` confidence), `UNCERTAINTIES.md` (only if a new
unknown appeared), `.happy/project-info.json`.
