# PRE-REGISTRATION — object re-register fix (defect B), option 1 surgical

Committed **before** the hand-test. Owner is the instrument (real-display run, same protocol as
`verify/resize_storedrect/`).

## Why

`D-004` is confirmed (`verify/resize_storedrect/`): the resized view now fills the monitor. Two
rendering defects remain, root-caused in `RESIZABLE_WINDOW.md` §9:
- **B.** the resize drops buildings and roads permanently — step 8 called the LEAF `FUN_1000fa36`
  instead of the real object re-register.
- **A.** the newly exposed area is black until a scroll (System-B repaint not run for the new region).

This fix targets **B** (the severe one). Defect A is **not** addressed by option 1 and is expected to
persist (it would need `FUN_100071a3` for the exposed region — deferred by the owner's choice).

## The change (`re/harness/src/sc3resize.c`, step 8 only)

Replace the bare `FUN_1000fa36(iso,1,0)` with the engine's real sequence, disassembled from
`FUN_10006a55` at `0x10006bc0`:
- **8a** `FUN_1000c8f9(iso)` — `__thiscall(ecx=iso)`, 0 stack args. Recompute every object's draw key
  `wrapper+0x24`.
- **8b** `FUN_1000c9bd(iso, &sentinel, iso+0x54, 1)` — `__thiscall(ecx=iso)` + 3 stack args, `ret 0xC`.
  `sentinel` = a RECT of four `0x80000001` dwords (the exact value the engine pushes). This clears the
  fine grid `iso+0x380` (`FUN_1000edd9`), does the tag-2 region pickup (`FUN_1000cedb`), then calls
  `FUN_1000fa36` (tag-1) internally — so the leaf call is REMOVED, not duplicated.

Convention and args were taken from the machine code, not the decompiler (Ghidra mislabels the
`__thiscall`): call site bytes `8B CE` (mov ecx,esi=iso) + `push iso+0x54` + `push &sentinel` +
`push 1`, callee `ret 0xC`. Both internal taggers are already grid-B-clamp-hooked, so the path is
crash-protected, and the whole step runs under the mod's SEH fault catcher (`g_rz_step = 8`).

No on-disk patch. Nothing else changes.

## Outcomes, committed in advance

| observation | verdict |
|---|---|
| Log shows `[step 8a]` + `[step 8b] FUN_1000c9bd returned` each resize AND **buildings and roads render** after a resize | **PASS — defect B fixed** |
| Log shows 8a/8b run, buildings/roads still missing | **FAIL, and it narrows the cause** — the objects are not in `iso+0x3a4` after a resize (placement is cross-DLL, `[UNCERTAIN]` in §9), so re-registering that container cannot bring them back. Report; do not retry blind |
| `FAULT CAUGHT` at step 8 (code + MODULE+RVA) | **FAIL** — `FUN_1000c9bd` faulted; the log localises it. The clamp hooks should prevent the known OOB, so a fault here is new information |
| Buildings/roads render, but the **new area is still black until scroll** | **PARTIAL as expected** — defect B fixed, defect A still open (option 1 does not address it). Not a failure of this fix |
| Crash on resize / hang | **FAIL** — restore, report the last `RZ` line |

**Decisive:** do buildings and roads come back after a resize, on screen.

## Falsifiability

If 8a/8b run cleanly (logged, no fault) and buildings/roads are STILL gone, then defect B is **not** a
re-registration problem — the building/road objects are not present in `iso+0x3a4` post-resize, which
would point at the cross-DLL placement path (SIMCITY/SIMNTWRK) that §9 left `[UNCERTAIN]`. That is a
real result and redirects the investigation; it is not a reason to iterate on step 8.

## Protocol

Harness claimed `handtest`. Owner launches (`resize_launch.exe -- <city>`, `SC3RESIZE_LOG` set, no
`-kill`), resizes by hand, reports what renders. Prior log archived as
`re/harness/sc3resize_handtest.storedrect.log`. Install (`SIMSPR f5b9f1d9`, `GZGraphicD acefadf0`)
verified before and after; no on-disk change.

## STATUS

Built + string-verified. Pre-registered. **Hand-tested 2026-08-29 — see RESULT below.**

---

## RESULT (2026-08-29)

**Option 1 ran clean but did NOT visibly fix defect B on a plain resize** — owner: "same as before".
The log shows `[step 8a]` + `[step 8b] FUN_1000c9bd returned` on all three resize cycles, **zero
`FAULT CAUGHT`**, three `done (all 9 steps)`, STOREDRECT still working (win `0x00B4AD60`). So the
convention/args disassembled from `0x10006bc0` were correct and the clamp-hooked taggers held — the
call executed — but buildings/roads were still missing after a bare resize.

**⭐ THE DECISIVE NEW FINDING — a runtime action fully repairs the render.** Owner: *"when changing
layers and i go to the water lines view and go back to buildings, everything renders when resized."*
Toggling a **data layer** (water view -> back to the normal/buildings view) after a resize makes the
**entire scene render correctly**, buildings and roads included.

**This REFUTES the pre-registered falsification hypothesis.** The buildings/road objects are **present
and renderable** post-resize — they are not gone from the engine, and this is not a cross-DLL placement
problem. The resize leaves them in a **not-drawn state that a full view/layer rebuild clears**.

⚠️ **Caveat, owner-stated:** "i didn't check this before so i don't know if any of your changes did make
an effect." The layer-toggle workaround is **not confirmed to be new** — it may repair the old build
too. So option 1's 8a/8b cannot be credited with enabling it. Treat option 1 as **did not visibly fix
B**, and the layer-toggle repair as a **property of the engine**, not of this change.

**What this points at:** the data-view switch is empirically hitting the engine's real "rebuild the
whole visible scene" path (the family around `FUN_10006a55` — `FUN_1000b70e`/`FUN_1000e248`/
`FUN_100071a3`/`FUN_1000b352`/`FUN_1000c9bd`). Option 1 ran only `FUN_1000c8f9` + `FUN_1000c9bd`, so
the missing ingredient is whatever the layer switch does that those two do not. **Next: read the
data-view/layer-switch handler to find the exact sequence, then replicate the delta** — rather than
guessing `FUN_10006a55`'s args. Delegated 2026-08-29.

**Also note (consistent with the above):** the OLD step 8 already called `FUN_1000fa36` (tag-1 re-add
of the `iso+0x3a4` objects) and buildings/roads were still missing then too. So buildings/roads are
**not** tag-1 `iso+0x3a4` objects — otherwise the pre-fix re-add would have shown them. They are either
tag-2 region sprites (whose pickup in `FUN_1000c9bd` is guarded by `2 < iso+0x28` and the exposed-rect
list `iso+0x4c4`, possibly empty at resize time) or driven by the layer-visibility system. `[UNCERTAIN]`
— the layer-switch read will settle which.
