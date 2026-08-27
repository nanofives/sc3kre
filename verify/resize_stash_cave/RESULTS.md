# RESULTS — bridge_stash CAVE witness (2026-08-26). CONFIRMED, under relocation. Plus a hook-collision fix.

**Verdict: the pre-registered top row landed.** The pure-DLL, position-independent stash cave wrote the SAME
valid bridge pointer the harness's independent `g_bridge` capture proved good, into the `.data` slot, and it
survives a resize. Confirmed with SIMSPR RELOCATED (base `0x03350000`) - the exact condition an absolute
`.data` write would have corrupted.

## The measurement (`STASHW> … .data STASH slot`, capture.log)
| phase | slot0 (bridge) | gen | == g_bridge | slot readable | iso(slot+0x18) | vtOK |
|---|---|---|---|---|---|---|
| PRE-resize | `0x0F2D6D58` | 1 | **YES** | 1 | `0x0EC62B88` | **1** |
| POST-resize | `0x0F2D6D58` (same) | 1 | **YES** | 1 | `0x0EC62B88` (same) | **1** |

- **The cave fired and stashed the bridge** (slot0 nonzero, gen=1 = one FUN_10016eba call).
- **slot0 == g_bridge** - the pure-DLL inline hook captured the SAME pointer as the harness's fnlog detour.
  Direct comparison, not a proxy.
- **slot0 validates** - readable, and `slot0+0x18` (the iso view) carries the iso vtable `SIMSPR+0x6250c`.
- **Survives the resize** - identical PRE/POST.
- **Position-independence exercised:** SIMSPR base `0x03350000`, GZGraphicD `0x027C0000` (both RELOCATED).
  The `call/pop EIP -> eax`, `[eax+offset]` slot write landed correctly at a non-preferred base.

## ⚠️ Hook-collision fix (a real finding, cost one hung run)
The first cave hooked the FUN_10016eba **ENTRY** (`0x10016eba`). That is exactly where the harness's `-gzlog`
fnlog table installs its OWN detour to capture `g_bridge`. **Two hooks on one address corrupt the function:
the game HUNG at `FUN_10016EBA hit#1` (t+4063 ms, log froze).** Fix: hook the `push ecx;push ecx;push ebx;
push esi;push edi` sequence at **`0x10016ec4`** (after EH_prolog, past the fnlog entry detour); ECX is still
the bridge there (EH_prolog preserves it; the function's own `push ecx` saves it as `this`). The cave
re-executes the 5 displaced pushes and returns to `0x10016ec9`. Entry `0x10016eba` left UNTOUCHED. 30-byte
cave + 5-byte hook, 29 bytes / 5 runs. **General note:** a pure-DLL cave and the harness fnlog cannot share a
hook address; hook past the fnlog entry detour, or the game hangs.

## State
Owner four-recipe SIMSPR restored + verified (`f5b9f1d9`, dz 2.0); GZGraphicD stays hardened (`acefadf0`).
Lease + harness claim released. `bridge_stash` recipe (0x10016ec4 hook) committed. The stash is NOT in the
owner's standing build - it is staged only for witness runs until the WM_SIZE cave + resize routine complete
the bridge.

## Next
The stash-and-validate falsifier AND the cave are both witnessed. Next: the WM_SIZE cave (GZGraphicD, reads
lParam, sets a pending flag) then the deferred per-frame resize routine (render-target resize + FUN_10018cdf
refill + present), reading the bridge from this slot - both position-independent from the start.
