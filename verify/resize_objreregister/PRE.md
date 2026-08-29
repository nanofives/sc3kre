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

Built + string-verified (`step 8a] FUN_1000c8f9`, `step 8b] FUN_1000c9bd` present, PE32, all prior
fixes retained). Pre-registered. Awaiting the owner hand-test.
