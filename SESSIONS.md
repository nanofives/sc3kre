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
