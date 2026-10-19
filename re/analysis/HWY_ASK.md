# HWY_ASK: the game asks before building a highway interchange (task hwask, 2026-10-19)

Owner decision 2026-10-19: "Dialog: default bridge, the game asks whether to build the interchange." This note is the
dialog mechanism (with RVAs) and how sc3netmod uses it. Code: `re/harness/src/sc3netmod_hwask.c`. Package:
`re/tools/netmod/examples/highway_ask`. In-game check: `verify/hwask/RESULTS.md`.

## 1. The stock confirm dialog (SIMNTWRK)

The tunnel builders confirm through the network manager's own method:

| what | where | evidence |
|---|---|---|
| road / rail tunnel builder (manager vt+0x13c) calls `this vt+0x140(0x253, cost)`, proceeds only on a non-zero return; on a refused build it calls `this vt+0x140(0x284, 0)` | `FUN_1001c102` lines at `0x1001c102` (decomp line 166 / 397) | `[CONFIRMED @ 0x1001c102]` |
| highway tunnel builder does the same | `FUN_1001ca1a` | `[CONFIRMED @ 0x1001ca1a]` (NET_RAMPS.md) |
| manager vtable `0x1002c7bc` slot +0x140 = `FUN_10006018` (slot +0x13c = `FUN_1001c102`, +0x90 = `FUN_100145aa`, +0xac = `FUN_1000abde`) | read from `Apps\SIMNTWRK.DLL` | `[CONFIRMED @ 0x1002c7bc + 0x140]` |
| `FUN_10006018` ends `c2 08 00` (ret 8): thiscall, two stack arguments (message id, cost) | bytes at `0x1000631e` | `[CONFIRMED @ 0x1000631e]` |

`FUN_10006018(msg, cost)` step by step `[CONFIRMED @ 0x10006018]`:

1. Sends GZ message `0x4372cf29` through `FUN_1001ef65()` vt+0xc (and `0xa372cf2d` at the end): the pair brackets
   the dialog (the sim shows "Simulación en pausa" in the lab either way; what the pair does is not decoded).
2. `FUN_1001f015()` vt+0x94(0) returns a formatter; its vt+0x3c(cost, cost >> 31, &str) writes the cost as money
   ("$5,100" in game).
3. `FUN_10021cd9(key, msg, 0x29541f4)` builds the resource key `{type 0x2026960B, group 0x029541F4, instance msg}`;
   `FUN_10021d11` reads it into a string (empty when the key resolves to nothing).
4. `FUN_1001ef1c(&body, text)` = `_vsnprintf(buf, 0x8000, text, ...)` with the money string: the text is a printf
   format, so it carries exactly one `%s`.
5. The title is instance `0x252` of the same group (English-UK "Engineer's Report", ENGLISH folder "Informe de
   Ingeniería").
6. `FUN_100063ce(dlg, body, title, type)` with type = `(cost < 1) + 1`: 1 for a positive cost, 2 otherwise.
7. `FUN_10006321(dlg)`: creates the dialog (`FUN_1001e4d8()` vt+0xc with `0xa2a79fd0` / `0xa2a79fd1`), sets four
   flags, then `FUN_1001efbd()` vt+0x9c(0, window) returns the answer synchronously, vt+0x28 removes the window.
8. Returns 1 when the answer is `0x12340001`, else 0.

Measured in game (2026-10-19): type 1 shows two buttons, "No" (left) and "Sí" (right, the 1 answer); the call
blocks on the thread that ran the highway drag (the game window's thread, tid 9e74 / 0ce0 in the two runs) and
returns the click. Stock texts in group 0x029541F4: `0x253` "Do you want to construct a tunnel for %s?",
`0x284` "Tunnel construction was discontinued due to possible damage to above ground structures." (English-UK).

**So the dialog can carry any question with one number**: a new string in group 0x029541F4 with one `%s` is enough.
No new UI was built.

## 2. Where the text comes from

String tables are `.IXF` segments (`re/analysis/formats/IXF_segment.md`), opened by the names in SYS.PAK
`Default.ini [DBSegments]`, `%Language%` substituted. Each shipped key is the group id its file holds
(`0x029541f4=0x80c381d7;Res\Text\%Language%\SC3StringsWindow.IXF`), and the shipped list repeats a key for a second
file of the same group (`0x42C1ED2D` and `0xa1096a4f`, the Holidays files). netpack's new manifest key `texts` uses
that pattern: per group it writes `Apps\Res\Text\<folder>\SC3StringsNetpack_<GROUP>.IXF` and appends
`0x<group>=0x80c381d7;Res\Text\%Language%\SC3StringsNetpack_<GROUP>.IXF` to `[DBSegments]`.

Measured: GZResourceD opened `Text\English\SC3StringsNetpack_029541F4.IXF` at startup (served from the overlay),
and `vt+0x140(0x4E560001, 5100)` showed our text with "$5,100" in place of `%s`. The game runs from the `ENGLISH`
folder, which holds Spanish text (RESOURCE_KEYS.md), so the dialog is Spanish in the lab.

Texts (package `highway_ask`, all seven folders, wording copied from each language's own tunnel question):

| id | used for | English-UK | ENGLISH folder (Spanish) |
|---|---|---|---|
| `0x4E560001` | X and diagonal crossings | Do you want to build a highway interchange for %s? If you choose No, only a bridge is built. | ¿Quieres construir un enlace de autopista por %s? Si eliges No, solo se construye un puente. |
| `0x4E560002` | T | Do you want to build a highway interchange for %s? If you choose No, the highway ends here. | ¿Quieres construir un enlace de autopista por %s? Si eliges No, la autopista acaba aquí. |

The body box holds four lines at this width: the first T text ("... termina en el cruce.") ran into the frame, so it
was shortened.

## 3. sc3netmod: `hwask_ok()`

`hwask_ok(hp, kind, x, z, r, trigger id, ramp cells)` is called by each highway block right before it would build
the FULL interchange (after its own checks passed):

| block | call site | yes | no |
|---|---|---|---|
| hwx | new X branch, cloverleaf qualifies | cloverleaf (96 cells) | clean flyover (12 cells), as the fallback |
| hwt | new T, `hwt_check(.., set 1)` passed | trumpet T | stays stock; decline remembered |
| hwdx | fresh crossing, at least one quadrant buildable (one question for all of them) | core + those quadrants | core only (the flyover) |
| hwdd | stock stub candidate, cloverleaf test returned 2 (fresh) | cloverleaf | flyover |

Rules:
- **Edit passes only.** A load pass gets the default without asking (hwx never builds at a load anyway; hwt: stays
  stock; hwdx: core only; hwdd: flyover). Interchanges already built come back from the save as before.
- **Ask once.** X / diagonal crossings: the bridge written on "no" is not the stock aftermath the blocks start a new
  interchange from, so no record is needed (hwx: the new-X branch needs stock 15113.0 at the centre; hwdx: fresh =
  the 15149 aftermath; hwdd: a candidate that is not the stock stub is never upgraded while hwask is on, so a built
  flyover stays a flyover). The T stays stock, so its decline is remembered: (trigger cell, turn, trigger id), where
  the trigger is the stem's cap 11235 / 15053 or the stub X centre 15113 / 15114. `hwask_prune` forgets a decline when
  its trigger cell (inside the pass box) holds something else.
- **Persistence.** Declines are saved as extra entries of sc3netmod's network-layer section `{0x206c6e7c, 0x2147c2dd,
  0x4E56}`: `w0 = x | z << 12 | r << 24 | kind << 28`, `w1 = 0x4B53 << 16 | trigger id`, `id = 0`. The loader of
  every earlier sc3netmod skips entries whose id word is 0 (`load_begin`), and the stock loader never reads 0x4E56.
  The section is now written when there are declines and no variant tiles.
- **Thread.** It asks only when running on the game window's thread (the thread the window procedure runs on, which
  runs tool retiles: MULTITILE.md); otherwise the default, logged.
- **Money.** cost = ramp cells x `price(0x4332)` (17202 OffRamp: what the stock On-ramp tool charges per ramp cell,
  `FUN_100145aa` `[CONFIRMED @ 0x10014678]`), read from budget = manager +0x38 vt+0x54 (75 in the lab). With less
  money than the cost (the tunnel builders' test, `funds < 2^32 && funds < cost`, or negative) it does not ask and
  builds the default. On yes it charges through budget vt+0x14(cost), as `FUN_1000abde` and the tunnel builders do.
  The ramp cells were free before this task. Counts: hwx 68 (cls 1), hwt 30 (land cells of set 1), hwdx the ramp-alone
  cells of the buildable quadrants, hwdd the land rows of the cloverleaf table.
- **Off.** `SC3NETMOD_HWASK=0`, or package `highway_ask` not installed (no `hwask` table line): `hwask_ok` returns 1
  and every block builds automatically, as before this task.

Table line (package `highway_ask`, manifest `highway_lines`): `hwask <crossing text id> <T text id>` (decimal).

## 4. Open

- hwdx and hwdd asks were not run in game (same helper; their call sites are the fresh-build branches above).
- A declined T is asked again if its trigger cell changes and comes back (the decline is forgotten on change).
- Upgrading an existing bridge later (the owner's "click it" idea) is not built: with hwask on, a flyover stays a
  flyover.
