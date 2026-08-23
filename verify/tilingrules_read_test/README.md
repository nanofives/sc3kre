# tilingrules_read_test — does the game actually read `Apps\Res\TilingRules\`?

Built 2026-08-21. **Status: ARMED, NOT RUN.** The harness change is written and compiles; the
run is blocked (§6).

## 1. Why this question is worth a run

`Apps\Res\TilingRules\` holds **68 loose plain-text files** that describe, per network, which
tile pieces exist and how they auto-connect. If the game reads them, it is by a wide margin the
cheapest modding surface in the game: no compression, no container, no repack, no tool needed.
`re/analysis/NETWORK_TYPES.md` §6 ranks it as the highest-leverage untapped surface.

It is also the **only** thing standing between "SC3000 road behaviour is editable with Notepad"
and "those files are vestigial build-time leftovers".

**The loose-file precedent says do not assume.** `verify/loose_file_test/ARM3_RESULTS.md`
established that a loose `.ini` does **not** shadow `SYS.PAK` — the archive wins
`[CONFIRMED @0x004872e8]`. A directory full of plausible loose text files is exactly the shape of
thing this project has already been fooled by once.

## 2. What is already established without running anything

**The loose directory is the only candidate source on disk.** Measured 2026-08-21:

- `Apps/Sys/SYS.PAK` contains **zero** TilingRules content — binary grep for `TilingRules`,
  `GRND_Set`, `SimpleRules` returns 0 matches.
- **No** `.IXF` or `.DAT` under `Apps/Res` contains the rule filenames either (swept every
  container two levels deep).

So there is no packed copy that could be winning the way `SYS.PAK` won in ARM3. The rules are
read from this directory, or they are not read at all. That makes the test binary rather than
three-way, which is why it is worth running.

**The reads are observable.** `SIMNTWRK.DLL` imports `CreateFileA` and `GetFileAttributesA`
directly (verified in its import table) and contains the `TilingRules` string.

**The loader path is mapped** (`re/analysis/SIMNTWRK.md`): `0x10010dff` → `0x10016d87` /
`0x100175ed` / `0x10017f98`, reading through a GZCOM stream at `0x10017596`.

**What is NOT known, and is the actual uncertainty:** the loader builds only the literal prefix
`TilingRules\` (`0x10031efc`) against a **base directory supplied by a caller that has not been
identified**. So the path could resolve somewhere other than `Apps\Res\`. The test is designed
around not knowing this (§4).

## 3. The harness gap this test found and fixed

The probe already had a `-filetrace` switch (`re/harness/src/sc3probe.c`). **Run as shipped it
would have produced a false negative on this question**, for two independent reasons:

1. **It hooked only `SC3U.exe`'s IAT.** The tiling loader is in `SIMNTWRK.DLL`, which imports the
   file APIs *itself* and is loaded long after the probe attaches. Its opens never touch the
   exe's IAT, so nothing would have been logged.
2. **Its filter did not watch these files.** `ft_interesting()` matched only `SC3Tune`, `.PAK`,
   `\Sys\`, `.sc3`, `Cities`.

An empty log would have looked like proof the files are never read. **Anyone running this test
before this fix would have drawn the wrong conclusion.**

Changes made (all in `re/harness/src/sc3probe.c`, which is **gitignored** — hence documented
here, since git will not carry them):

- `ft_interesting()` widened with `TilingRules`, `_GRND_`, and `.txt`. The `.txt` clause is
  deliberate and load-bearing: **the base directory is the unknown**, so a rule file opened from
  an unexpected root still has to show up. SC3 opens few `.txt` files, so the noise cost is low.
- New `ft_hook_all()` walks **every loaded module** via `EnumProcessModules` and hooks each one's
  IAT, excluding the probe itself (`g_probe_mod`, new global set in `DllMain`) so `logf` cannot
  recurse.
- New `ft_thread()` re-arms every 100 ms for 180 s, so **on-demand sim DLLs are hooked before
  their first file touch**. 100 ms is far tighter than the gap between `SIMNTWRK.DLL` loading and
  network-layer registration.
- New `ft_bind_originals()` binds the real kernel32 entry points by `GetProcAddress` instead of
  lifting them out of an IAT slot. Necessary once hooking is repeated: a slot may already hold
  our own hook, and storing that as "the original" is the self-recursion trap the file already
  warns about at the `-clicks` hook.

Compiles clean (`re/harness/build.ps1`, MSVC, `sc3probe.c` only warning-free pass).

## 4. The ladder, with outcomes committed BEFORE the run

Per project convention, what each result means is fixed now, not after seeing it.

> **This section is the PRE-REGISTRATION and is deliberately left as written.** Two of its
> statements were disproven by the runs and are corrected in RESULTS, not here, so that the
> committed-in-advance record stays intact:
> (a) the `-GameArgs "-l<city>"` form below **does not load a city** on this build - use a bare
> absolute `.sc3` path, as §7 does; (b) the rules do **not** load "with the network layers during
> city setup" - they load unconditionally at startup, 1,735-1,749 ms, with no city required.
> Follow §7 for the procedure; read §4 only as the outcome table that was fixed before the data.

### T0 — baseline trace, non-destructive, nothing modified

```
pwsh re/harness/capture.ps1 -Name tiling_t0 -Switches "-nocom -windowed -origin -fix16 -fitclient -nointro -quiet -filetrace" -GameArgs "-l<city>" -AtSec 40
```

A city must be **loaded**, not just the menu: the rules load with the network layers during city
setup. Then grep the log for `TilingRules`, `_GRND_`, `.txt`.

| observation | conclusion |
|---|---|
| `CreateFileA` on `…\TilingRules\*.txt` → `ok` | **Files are read from this directory.** Surface is live. Proceed to T1. |
| Opens on `*_GRND_*.txt` from a **different** base dir | Read, but the base dir is elsewhere. **Record the real path** — this also answers the open `[UNCERTAIN]` in `SIMNTWRK.md`. Proceed to T1 against that path. |
| `GetFileAttributesA` → `exists` but no `CreateFileA` | Probed and skipped. Suggests a cached or precompiled form; investigate what consumes the attribute result. |
| Zero hits, **and** the log shows other FILETRACE lines (`SYS.PAK`, `.sc3`) | Hooks were live and the files were **never touched**. The directory is vestigial. **Surface is dead — stop, and downgrade `NETWORK_TYPES.md` §6 item 3.** |
| Zero hits **and** no FILETRACE lines at all | **Inconclusive, not negative.** The hooks failed to arm. Check the `--- FILETRACE: hooking ALL modules` line before concluding anything. |

That last row exists because it is the failure mode that masquerades as a result.

### T1 — content edit, only if T0 is positive

Back up the directory first (`Apps\Res\` is GAME content per `CLAUDE.md`):

```powershell
Copy-Item -Recurse "Apps\Res\TilingRules" "Apps\Res\TilingRules.bak"
```

Then make **one** change whose effect is a read-off rather than a judgement. Candidate: truncate
`ROAD_GRND_Set.txt`'s id list to a small subset. Expected if honoured: road auto-tiling visibly
degrades or the game errors on load. Restore from `.bak` afterwards, and confirm the restore.

| observation | conclusion |
|---|---|
| Visible tiling change or load failure | **Rules are honoured. The surface is real and moddable.** This would be the first behaviour change this project has driven from a plain-text game file. |
| No change, T0 was positive | Read but ignored, or overridden by the `.rdata` tables. Record and stop. |

## 5. Interpretation limit, stated up front

A positive T0 proves the files are **opened**. It does **not** prove edits take effect — §2 of
`NETWORK_TYPES.md` documents substantial hard-coded `.rdata` piece and orientation tables that
could override text rules. Only T1 settles behaviour. A negative T0 is decisive on its own.

## 6. Why it has not been run

Blocked on the harness, not on the question. At 01:05-01:07 on 2026-08-21 a **concurrent session
was actively driving the game**: `sc3probe.dll` rebuilt 01:05:03, `sc3probe.c` modified 01:06:02,
a fresh `SC3U.exe` + `sc3launch.exe` pair started 01:06:48. `sc3probe.dll` is held open by the
injected process, so the link step fails `LNK1104`.

`COORDINATION.md` has a single-writer contract for trackers but **no claim protocol for the game
or the harness**, and `re/harness/src` is gitignored, so neither session gets collision
protection from git. Racing for the link lock was declined.

**To resume:** confirm no `SC3U`/`sc3launch` process is live and no other session owns the
harness, then `pwsh re/harness/build.ps1` and run T0. The source changes in §3 are already in
place; verify they survived with
`Select-String -Path re/harness/src/sc3probe.c -Pattern "ft_hook_all|g_probe_mod"`.

**Worth considering:** a claim file (`re/harness/OWNED_BY.txt`) would have prevented this, and
would prevent the next occurrence. Owner call, not applied unilaterally.

**Update 2026-08-22:** resolved by the queue/game-launch session. Game runs now serialize through
`re/harness/game_lock.ps1`, `capture.ps1` takes the lease itself (pass `-Owner`), and
`GAME_PROTOCOL.md` rule 5 adopted `harness_claim.ps1` for `sc3probe.dll` rebuilds. T0 was run
under that protocol.

## 7. T1 is blocked on U-068, and is ready to fire

T0 is done (§RESULTS). T1 needs the map on screen, and **in-city rendering does not work**:
`LAUNCH_CONTROL.md` §33.2 **defect 6 / `U-068`** — the iso view's graphics device cannot create a
backing store after a DirectDraw teardown, `dev->vf0c(w,h)` returns 0, `Init` ignores the failure,
no terrain draws. Their own note: "the ONLY thing between the five verified in-city fixes and a
rendered city".

Re-checked empirically **2026-08-22** under the queue, install verified stock: city loaded,
70.9 s runtime, `Blt=0 Flip=0 Lock=0` throughout, **zero SHOT lines**. Still blocked. Two
independent observables (their surface probe, this blit-mirror reconstruction) fail at the same
place.

**Trigger: when `U-068` closes, run this.** No further setup needed; the backup, the edit
procedure and the outcome table are all above.

```powershell
# 1. baseline, stock rules
pwsh re/harness/capture.ps1 -Owner roads -Name t1_baseline `
  -Switches "-nocom -windowed -origin -fix16 -fitclient -nointro -quiet" `
  -GameArgs:" $((Resolve-Path 'Cities\Farmsville.sc3').Path)" -AtSec 75

# 2. break the road allowed-piece list (backup already at TilingRules.bak, 68/68 verified)
Set-Content "Apps\Res\TilingRules\ROAD_GRND_Set.txt" -Value "{99999}" -NoNewline -Encoding ascii

# 3. same capture, new name
pwsh re/harness/capture.ps1 -Owner roads -Name t1a_setbroken `
  -Switches "-nocom -windowed -origin -fix16 -fitclient -nointro -quiet" `
  -GameArgs:" $((Resolve-Path 'Cities\Farmsville.sc3').Path)" -AtSec 75

# 4. RESTORE and verify (must print 9926948A...1358)
Copy-Item "verify\tilingrules_read_test\TilingRules.bak\ROAD_GRND_Set.txt" `
          "Apps\Res\TilingRules\ROAD_GRND_Set.txt" -Force
(Get-FileHash "Apps\Res\TilingRules\ROAD_GRND_Set.txt" -Algorithm SHA256).Hash
```

**Why the path is built with `Resolve-Path` instead of written out:** the fixture must be an
**absolute** path (that is the finding - see RESULTS), but hardcoding one leaks the local install
location into a public repo, and a *relative* path does not work because the game's cwd is
`Apps\`, so `Cities\Farmsville.sc3` would resolve to `Apps\Cities\...`.
Building it at run time keeps it absolute, portable and leak-free. Do not "simplify" it back.

Then diff the two PNGs. Compare **road tiles only** — the T1a run already established the game
does not crash and the city still loads with a 7-byte Set file, so the difference, if any, is
purely visual.

Notes for whoever runs it: pass a **bare absolute `.sc3` path**, not `-l` (§RESULTS, and
`LAUNCH_CONTROL.md` "Loading a city at launch"). Keep `-AtSec` at 60+; the shot fires at ~44 s.
Queue every launch: `capture.ps1` takes the lease itself, so pass `-Owner`.

### Mandatory before trusting any number from T1 (`GAME_PROTOCOL.md` rule 6)

Road results are **map-dependent** — costs, tile counts, and whether a road connected. And the
failure mode is not a crash: **a wrong-city run still produces numbers.** So:

1. **Confirm which city loaded, from the log, not from a fault signature.** With the bare-path
   fixture the filetrace line names the file directly
   (`CreateFileA "…\Cities\Farmsville.sc3" -> ok`), which is why this test uses that method rather
   than the dialog click sequence — the dialog's confirm id `0x02DFDD6A` selects a **list
   position**, so any added or removed `.sc3` silently re-points it at a different map.
2. **Also sample the map dimensions** at `+0xec`/`+0xf0` on the occupant bridge, **after they are
   populated, not at function entry**. Farmsville must read its stock size; a 512 reading means a
   different city loaded.
3. **Never leave a non-shipped save in `Cities\`.** Park experiment cities under
   `verify/tilingrules_read_test/` and copy them in only for the run that needs them, removing
   them in a `finally`. **Do not create subdirectories in `Cities\`** — the game enumerates that
   folder and a holding directory alone caused a round of drive failures.
4. **Count saves case-insensitively.** Stock is **15** `.sc3`; a bash or Python `glob` on `*.sc3`
   returns **14** because `TUTORIAL.SC3` is upper-case, which looks like a missing city.

If a run dies with a SIMDIRT crash at `FUN_10013556` / `0x10013A8F`, the discriminator: a small
constant (e.g. `ECX = 0xBC`) is a null bits pointer on an unlocked surface; a wild-but-large value
(`0x740d8c90`, `0x5baa5baa`, `0x8800d900`) is heap garbage from the 132 KB overrun, i.e. **you
loaded a 512-tile city by accident**. And an early exit at ~840 ms with **no crash dump** is the
single-instance guard — another session held the game, not a broken patch.
