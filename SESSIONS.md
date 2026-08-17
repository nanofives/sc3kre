# SESSIONS.md — who is working in this repo right now

Three Claude sessions were live in this working copy on **2026-08-17**, all writing the same
trackers. Nothing was lost, and that was checked rather than assumed — but it was luck as much as
design, so this file exists to make the split explicit. **Read it before writing a tracker.**

Delete or update this file when the sessions are done. A stale coordination file is worse than
none.

## The sessions

| session | scope | files it owns |
|---|---|---|
| **city-save format** (wrote this file) | the `.sc3` family, the writer/editing API, P1 gate criterion 2 | `re/tools/city_*.py`, `re/tools/qfs_encode.py`, `re/scripts/scope_toolkit.py`, `re/scripts/verify_worker_rows.py`, `formats/CITY_SAVE.md`, `formats/QFS.md`, `GATE_RESCOPE.md` |
| **sc3k-gzcom-dll evaluation** | enumeration, carving, GZCOM interfaces and IIDs, criterion 1 | `GZCOM_INTERFACE_CATALOGUE.md`, `MODULE_MAP.md`, `re/scripts/ForceSignature.java`, `enumerate_functions.py` runs |
| **windowed mode / launch harness** | getting the game to render, the probe harness | `LAUNCH_CONTROL.md`, `re/harness/`, the launch-harness suite |

## The rules we are working to

1. **`functions.csv` is read-modify-write, never a blind rewrite.** Read the whole file, change
   your rows, write it back. All three sessions have been doing this and no row has been lost
   (verified: 0 lost, 0 downgraded, 0 names dropped across every merge today). Do not "optimise"
   it into a partial write.
2. **Whoever changes a number in `ROADMAP.md` or `HANDOFF.md` re-measures it.** Do not copy a
   figure from another session's text. The good version of this happened today: the gzcom session
   edited criterion 2 to 530/562 and an independent `scope_toolkit.py` run agreed exactly.
3. **Do not touch another session's uncommitted files.** If `git status` shows something modified
   that you did not modify, leave it. Say so in your report instead.
4. **The repo is PUBLIC** (`github.com/nanofives/sc3kre`). Before committing anything new, grep the
   diff for the local Windows username, the worker account name and the owner's email. Tools and
   notes only, never game assets or bulk decompiled output.
5. **Announce a re-carve before running it.** A vtable-seeded re-analysis on 2026-08-17 added
   12,529 previously invisible `FUN_` bodies, which grew the toolkit-necessary set 530 → 562 and
   re-opened a gate criterion that had just been closed. That is fine and the work was good, but a
   session reading functions one at a time needs to know the export is about to move under it.

## Why rule 5 has teeth

The export is the denominator for every metric in this project. On 2026-08-17 the toolkit-necessary
set moved **513 → 530 → 562** in one day, purely from re-exports and re-carves. Two consequences
worth internalising:

- **Any count derived from the tracker or the export is a snapshot.** Re-run the script; never
  quote a number out of a document. Both `scope_toolkit.py` and `enumerate_functions.py` are cheap.
- **"Met" means met at a measurement.** Criterion 2 was closed at 530/530 and re-opened at
  530/562 within hours. Nothing that had been read got unread — the set simply grew.

---

## Carve status — DONE (gzcom session, 2026-08-17)

**The vtable-seeded re-carve is FINISHED. The export is settled. No further carve is planned or
queued.** Recorded here per rule 5, so the next session does not have to infer it from mtimes.

If that changes, this section gets edited *before* the run, not after.

### What was carved

All 30 binaries, in two passes: SIMRCI + SIMMISC first, then the remaining 28.

```
targets seeded          12,879 + 1,174
function starts created 12,787 + 1,170     failures: 1
FUN_ rows enumerated    12,529 +   129
real backlog            33,011 -> 45,669   (+38%)
```

The one failure is `SIMBABLD.DLL 0x12055fcd` — `MakeFunctions.java` could not create a function
there. Recorded, not chased: one in ~14,000 is an acceptable rate for a heuristic that takes any
dword in a vtable-shaped run as a code pointer.

### How "finished" was established

Re-ran the target scan against **every** binary and asked how many vtable-slot targets still have
no Ghidra function at all:

```
TOTAL REAL RESIDUAL: 1     (the SIMBABLD failure above)
```

The carve is idempotent from here: creating functions does not change `.rdata`, so no new slot
targets can appear. A second pass would find the same one address.

> **The first version of that test said 1,914, and it was wrong.** It compared targets against
> `functions.csv`, which excludes `thunk_*` by policy, so ~1,900 thunk targets that *do* have Ghidra
> functions looked missing. The correct denominator is the export's `symbols.csv`. Flagging it
> because this is the **third** loose-filter error in this repo today (271 vs 129, 20,100 vs 129,
> 1,914 vs 1) and the pattern is worth naming: **a count over the exports must state its filter and
> be cross-checked by a second method before it goes in a tracker.**

### Consequence, already recorded

P1 criterion 2 re-opened at **530/562**. 32 functions to read: SIMGEOM 13, SIMDSTR 10, SIMUTIL 5,
SIMNTWRK 3, SimTransit 1. `scope_toolkit.py --validate` recall is still 50/50 = 100% after the
re-export, so the instrument is sound and the number can be trusted.

Four of the 32 are **S1 serialisers** — SIMGEOM `0x1000d290`, `0x1000d950`, `0x1000fc80`,
`0x10010220`. S1 is the criterion that located the city-save writer's own stream primitives, so
those four are the ones most likely to bear on `city_write.py`.

### Files: no longer uncommitted

`UNCERTAINTIES.md`, `MODULE_MAP.md`, `GZCOM_INTERFACE_CATALOGUE.md` and `ForceSignature.java` were
committed in **`c174ad3`**, together with the `ROADMAP.md` criterion 1 + 2 text and the
`functions.csv` rows. Scrubbed per rule 4 before committing (no username, account name, email or
absolute paths). The shared worktree is clean of gzcom-session work.

One item that belongs to the city-save session under the split but was edited by this one:
`ROADMAP.md` criterion 2's **status text** (530/530 → 530/562). Done because this session caused the
change; flagged for review rather than assumed. Proposed standing rule: whoever breaks a criterion
records the new measurement, the owner of that criterion adjudicates.
