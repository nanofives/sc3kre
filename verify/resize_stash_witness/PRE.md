# PRE-REGISTRATION — #3 bridge stash-and-validate WITNESS (committed BEFORE the lease)

Owner: resizeship session. 2026-08-26. The cheapest falsifier for the whole pure-DLL bridge, spent first:
does a bridge pointer captured at `FUN_10016eba` (the exact hook a pure-DLL stash would use) **survive and
validate across a resize**, and is there **exactly one iso view**? Tested WITHOUT building any cave — via
the harness's existing `g_bridge` capture — so it exposes zero relocation/data-slot risk. If it fails,
nothing downstream matters.

## Instrument
Probe `sc3probe.dll` sha256 `a1d0c7c70037b95c1c51fb34d485beacadcab02eb88264c8f7505fd9aba5d55d` (280064 b),
new verb `SC3PROBE_STASH_WITNESS`. `stash_witness()` runs PRE-resize (start of `rz_iso_resize`, before Init)
and POST-resize (after the redraw/present). Each logs, with expect-or-refuse (a null/unreadable/wrong-vtable
is a logged REFUSAL, never a crash):
- SIMSPR + GZGraphicD **runtime bases** (confirm the relocation inference empirically).
- `g_bridge` readable (`IsBadReadPtr 0xf4`); `iso = bridge+0x18` readable; `*(iso) == SIMSPR+0x6250c` (iso
  vtable); `iso == g_iso` (independent harness capture).
- **count of iso-vtable objects reachable** via `rd_find_iso` (the cam-verb >1-view trap).

Env: `SC3PROBE_RESIZE=1 RESIZETO=1280x1024 RESIZEAT=22 SC3PROBE_STASH_WITNESS=1`, Europolis, `-AtSec` under
800. The harness resize re-runs Init + refill, so it is a STRONGER survival test than a real WM_SIZE (which
never touches the SIMSPR bridge at all). Live install (four-recipe SIMSPR + patched GZGraphicD) — the
witnessed pointers (bridge/iso vtable) are unaffected by any recipe, so no restore is needed; noted for
audit. No cave, no SIMSPR/GZGraphicD patch this run.

## Outcomes, committed in advance
| PRE and POST | conclusion |
|---|---|
| **same bridge ptr; br_ok+iso_ok+vt_ok at BOTH; iso==g_iso; count==1** | **FALSIFIER PASSES** — the bridge survives + validates across a resize, single view. The pure-DLL stash is viable; build the (position-independent, `.data`-slot) cave next. |
| validates PRE but REFUSES / different ptr POST | the bridge does NOT survive the resize (freed/recreated) → a one-time stash goes stale → redesign to re-capture per resize. Report, do not build the cave. |
| **count > 1 at either phase** | **AMBIGUOUS — first-class outcome, not a sanity check.** Multiple iso-vtable objects (minimap?) → the stash must disambiguate the main city view → changes the design (the exact `cam`-verb trap that voided a camera series). |
| REFUSE at PRE (g_bridge not captured) | the bridge Init `FUN_10016eba` was not seen → no live view or instrument mis-arm → report, VOID. |
| vt mismatch (iso vtable != `SIMSPR+0x6250c`) | `bridge+0x18` is not the iso class under this path → the one-stash-yields-both assumption is wrong; report. |

## Base check (committed expectation, to verify not assume)
SIMSPR base logged (**relocated: YES** expected — it lost the `0x10000000` collision to GZGraphicD);
GZGraphicD base (**relocated: NO** expected — at `0x10000000`, consistent with the X-cave's absolute refs
working). If SIMSPR reads `0x10000000` instead, the relocation inference is WRONG and the cave's data-slot
addressing can be simpler — either way the cave will be built position-independent (correct under both).

## Reported whatever happens
The full PRE/POST `STASHW>` lines; the base readings; the view count as a first-class result; and a plain
verdict against the table above, **including a refusal as a result, not a failed run.**

## STATUS
Probe BUILT (`a1d0c7c7…`). Pre-registered. Harness claim held (`resizeship`). Lease free. Not yet run.
