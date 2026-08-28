# RESULTS — root cause of the resize AV (2026-08-28). ⭐⭐⭐ FOUND. OOB grid-B bucket index, not a freed node.
# PRE git (rootcause). Fault caught + fully diagnosed on the churn run.

```
RZ *** FAULT CAUGHT *** code=0xC0000005 at SIMSPR+0xD005 (=FUN_1000cedb+0x12a), STEP 7
RZ FAULT regs: eax=0x80020003 ecx=0 edx=0x0F0A9CAC ebx=8 esi=0x0DAF6188 edi=0x0E13254C
RZ FAULT eax (the node cmp'd) readable=0
RZ FAULT grid: base=0x0E132430 dims=8x8 stride=3 (64 buckets = base..base+0x100) |
              edi in-grid=0 (edi-base=284, /4=71) | extent=(-848,2924,1200,4005)
              scale39c=0.003906 3a0=0.007407
RZ FAULT grid scan: 8 total nodes, 0 dangling heads, 0 dangling next-ptrs
```

## The cause, unambiguous
- The grid is **8x8 = 64 buckets** (`base..base+0x100`). The faulting access is at **`edi = base+284`
  = bucket index 71** — **7 past the end of the array.** `edi in-grid=0`.
- `eax = 0x80020003` — the dword read from `bucket[71]` (adjacent heap, past the array), non-null and
  **unreadable**; `cmp [eax],edx` at `+0x12a` faults.
- **The grid itself is INTACT: 0 dangling heads, 0 dangling next-ptrs, 8 live nodes.** So this is
  **NOT a freed/dangling node** (the earlier hypothesis is refuted by the scan). It is an
  **out-of-bounds bucket INDEX.**

## Why the index is 71 — an off-by-one at the far edge, in the engine's own math
`FUN_1000cedb` computes the max column/row as `round((coord_far - 1 - origin) * (gw / extent))`:
- col: `round((2048-1) * 8 / 2048) = round(7.996) = 8`  (grid cols are 0..7)
- row: `round((1081-1) * 8 / 1081) = round(7.994) = 8`  (grid rows are 0..7)
- index `(row<<3) + col` with row=8 → `64 + 7 = 71`. **Matches the measured edi exactly.**

The `-1` guard is defeated by round-half-up: `round(gw - gw/extent) = gw` for any extent > ~16. So the
far-edge cell maps to index == grid dimension, one past the row/array.

## ⚠️ This is a LATENT ENGINE BUG, present even at native res — the resize only exposes it
At **800x600**: `round(799 * 8 / 800) = 8` — the SAME index-8 overrun. **The engine computes an OOB
bucket index at native resolution too.** It does not crash there because the memory just past the
64-bucket array happens to be **benign (readable/null)** → null head → the `test eax,eax` skips it. The
crash is therefore **heap-layout-dependent**: it faults only when `bucket[64..71]` lands on an
unreadable/garbage dword (here `0x80020003`). **That is exactly why it is intermittent** — and why five
earlier controlled runs at 2048 were clean while the churn caught it. "Real crash" and "not
reproducible under 5 conditions" are now fully reconciled: a latent OOB read whose lethality depends on
adjacent heap contents.

## Fix options (design, not yet built — naive grid-enlarge does NOT work)
- ⛔ **Enlarging grid B (ee29 with 16x16) does NOT fix it:** the round-up scales with the grid —
  `round((W-1)*16/W) = 16`, OOB again at the larger dimension. The far edge always maps to `gw`.
- **(A) Clamp the index in `FUN_1000cedb`** (code cave: `min(col, gw-1)`, `min(row, gh-1)`). The correct
  fix, but a cave in a hot function.
- **(B) Over-allocate the bucket buffer** so `bucket[gw*gh .. +gw]` is always readable/zero: after
  `FUN_1000ee29`, replace `iso+0x380` with a mod-owned zeroed buffer sized `gw*gh + gw + slack`. No
  engine-code patch, but the mod must re-do it after every `ee29` (every resize) and manage lifetime.
- **(B) is the more DLL-friendly fix and matches how the game already tolerates the bug at native**
  (benign adjacent memory) — the mod would guarantee that condition instead of relying on luck.

## Status
Root cause **FOUND and evidence-backed** (registers + arithmetic + grid scan agree). This is the real
open defect of the resizable-window mod. `U-069` (downward) still separately untested. The fix is a
follow-on (option B recommended).

## State
Fault was CAUGHT (SEH), game continued then exited; no orphan. Owner build verified `f5b9f1d9` /
`acefadf0`. Mod patches nothing on disk. Lease + claim released.
