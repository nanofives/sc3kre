# PRE-REGISTRATION — the window stored-RECT write (`D-004` fix attempt 1)

Committed **before** the code is built and before any run. Owner is the instrument: this is a
real-display hand-test, same protocol as `verify/resize_handtest/`.

## Why

`D-004` failed on 2026-08-29 (`verify/resize_handtest/RESULTS.md`): after maximize, the city stayed
drawn in the top-left at 800x600. Cause identified and byte-confirmed (`re/analysis/RESIZABLE_WINDOW.md`
§8/§8b): the mod resizes the **SIMSPR** surfaces but never updates the **GZGraphicD window object's
stored RECT**, so `FUN_100185f5` keeps publishing an 800x600 rect and `FUN_10018c58` keeps Blt-ing an
800x600 block to the window's top-left.

## The change (one function, `re/harness/src/sc3resize.c`)

In `rz_wndproc`'s `WM_SIZE` branch, **before** forwarding to the game's handler, write the new client
size into the window object's stored RECT:

```
win = *(void **)(GZGraphicD_base + 0x6cdb8)          /* the WndProc thunk's own source, RVA 0x17e11 */
*(LONG *)(win+0x40) = *(LONG *)(win+0x38) + LOWORD(lp)   /* right  = left + newW */
*(LONG *)(win+0x44) = *(LONG *)(win+0x3c) + HIWORD(lp)   /* bottom = top  + newH */
```

Right/bottom are set **relative to the existing left/top** rather than zeroing them, because
`FUN_100185f5` maps the rect through `ClientToScreen` and left/top may carry a position.

**Expect-or-refuse, per the BOARD standing rule.** The write is skipped and LOGGED, never forced, if:
`win` is NULL or `IsBadReadPtr(win, 0x48)`; or `*(DWORD *)win != GZGraphicD_base + 0x1f740`
(the primary vftable identity, §8b); or `lp` is 0x0. A refusal is a logged result, not a crash.

Also in this change: the **false comments** at `sc3resize.c:44` and `:719` claiming the subclass already
publishes the true client size are corrected (see `RESIZABLE_WINDOW.md` §3).

Nothing else changes. No on-disk patch. The mod still writes no file.

## Addresses this depends on (all `GZGraphicD.dll`, all `[CONFIRMED]` in §8b, all base-relative at runtime)

| what | RVA | evidence |
|---|---|---|
| window object global | `0x6cdb8` | WndProc thunk `0x17e11` does `mov ecx,[0x1006cdb8]`; ctor stores it (`A3 B8 CD 06 10`) |
| primary vftable | `0x1f740` | installed as `[this+0]` at `0x17bf7` and `0x17c6e` |
| stored RECT | `win+0x38..+0x44` | `vt+0x68` = `[ecx+0x40]-[ecx+0x38]`, `vt+0x6c` = `[ecx+0x44]-[ecx+0x3c]` |

## Outcomes, committed in advance

| observation | verdict |
|---|---|
| Log shows `STOREDRECT: ... -> right/bottom updated` once per resize AND the city **fills the window** on screen | **PASS — `D-004` confirmed, mod complete end-to-end** |
| Log shows the write happening, but the screen still shows 800x600 top-left | **FAIL, and it FALSIFIES §8** — the published rect is not what `FUN_10018c58` consumes. That is the one link §8b left `[UNCERTAIN]`. Report; do not patch further without new evidence |
| Log shows `STOREDRECT REFUSED` (vftable mismatch / unreadable) | **VOID, not a fail.** The global or vftable identity is wrong; re-derive before retrying |
| View fills but is garbage / torn | **PARTIAL** — geometry reaches the primary, contents wrong. New question, separate item |
| Crash / `FAULT CAUGHT` | **FAIL.** The log localises it (code + MODULE+RVA + step). Restore and report |
| HUD still 1024x768 with margins | **NOT A FAIL** — known separate item, unchanged by this |

**Decisive:** does the city fill the window on a real display. Everything else is diagnosis.

## Falsifiability — what would make me wrong

§8 predicts that updating this one RECT is sufficient. If the write lands (logged, vftable verified) and
the screen is unchanged, **§8's causal claim is wrong**, not merely incomplete — the surviving
`[UNCERTAIN]` is that `FUN_10018c58`'s dest rect comes from `FUN_100185f5`'s publish, which is
DirectDraw-ABI inference and has never been byte-proven (the call is virtual, no textual caller).
That outcome is a genuine result and must be recorded as such, not retried blind.

## Protocol

Harness claimed as `handtest`. Owner launches (`resize_launch.exe -- <city>`, `SC3RESIZE_LOG` set, no
`-kill`), maximizes/restores/shrinks by hand, reports what is on screen. I read the log. Owner's standing
install (`SIMSPR f5b9f1d9`, `GZGraphicD acefadf0`) verified before and after; this mod needs no on-disk
change, so both hashes MUST be unchanged at the end.

## STATUS

Pre-registered. Not yet built.
