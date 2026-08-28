# PRE-REGISTRATION — FIX A (grid-B index clamp) witness (before the lease)

**The fix is proven by construction:** the cave recomputes the bucket index with row clamped to
`[esi+0x388]-1` (gh-1) and col to `[esi+0x384]-1` (gw-1), so `index <= (gh-1)<<stride + (gw-1) =
gw*gh-1 = 63` — it can no longer reach 64+ on the 64-bucket grid. Disassembly-verified. This run is a
sanity check that the patch APPLIED, did not break rendering, and that the churn (which caught the fault
unfixed) now produces none.

**Method.** Same churn as `verify/resize_rootcause` (8 large resizes, load zoom, gate on), clamp
applied, SEH catcher still armed.

| # | reading | verdict |
|---|---|---|
| 1 | `GRIDB_CLAMP: FUN_1000cedb index clamped` logged; churn runs; **zero `FAULT CAUGHT`**; resizes complete all 9 steps | ⭐ **PASS** — patch applied, no fault, rendering intact |
| 2 | `FAULT CAUGHT` at `FUN_1000cedb+0x12a` again | **FAIL** — the clamp did not take; re-examine |
| 3 | `FAULT CAUGHT` at a DIFFERENT address (e.g. FUN_1000d0f5/be25) | **PARTIAL** — FUN_1000cedb fixed but a sibling walker has the same latent OOB (expected per the scope note); report the address |
| 4 | `GRIDB_CLAMP: ... NOT patching` | **FAIL** — byte mismatch; the fix did not install |

⚠️ The fault is intermittent, so "no fault in one churn" is confirmation, not proof — **the proof is the
clamp arithmetic** (index <= 63 by construction). Outcome 3 is the one to watch: it would show FIX A is
correct but incomplete (siblings need the same clamp), which the scope note already predicts.

---

# AMENDMENT — FIX A COMPLETION witness (before the lease)
Added two more clamps (`FUN_1000d0f5` @0x1000d281, `FUN_1000be25` @0x1000c412) as clones of the shipped
cedb clamp — caves capstone-verified, placed in non-overlapping slack (0x61520, 0x61560), fail-closed
byte checks. All three installed in memory at load. Witness: churn run, confirm all three log
`index clamped`, and zero faults.
| # | reading | verdict |
|---|---|---|
| 1 | all 3 `GRIDB_CLAMP ... index clamped` lines; churn runs; zero `FAULT CAUGHT`; resizes complete | ⭐ **PASS — FIX A complete (all 4 grid-B walkers clamped)** |
| 2 | any `NOT patching` | **FAIL** — a byte/slack mismatch on that entry |
| 3 | `FAULT CAUGHT` anywhere | **FAIL** — report address/step |
