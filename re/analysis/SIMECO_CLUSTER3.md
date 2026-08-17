## Analysis of `FUN_10010634` (0x10010634, 371 bytes)

**Mechanical behavior.** `__thiscall(void *this, int param_1)`. This is a **stream text-line reader**. It reads one text line from a stream object held at `this+0x28` and writes it into a `std::string` field at `param_1+4`. Returns `undefined1` (`local_12`) = 1 if any bytes were read, 0 otherwise.

Step by step `[CONFIRMED @ 0x10010634]`:

1. Constructs a temporary string accumulator `local_30` via `FUN_10002624(&local_30, 8)` (reserve 8) then `FUN_100025e5(&local_30)` (init) — lines 35-37.
2. `piVar6 = this + 0x28` — the stream object `[CONFIRMED @ 0x10010634:38]`.
3. `local_1c = stream->vtable[0x18]()` — current position (tell); `iVar2 = stream->vtable[0x1c]()` — end/length; `uVar3 = iVar2 - local_1c` = bytes remaining `[CONFIRMED @ 0x10010634:41-43]`.
4. `local_24 = param_1 + 4`; `FUN_1000ed6d(local_24,0,0)` clears the output string; `memset(local_5c, 0, 0x2a)` clears a 42-byte scratch buffer `[CONFIRMED @ 0x10010634:45-47]`.
5. Read loop: `local_18 = min(uVar3, 0x28)` (40-byte chunk). `stream->vtable[0x38](local_5c, local_18)` reads that many bytes, returns success flag `[CONFIRMED @ 0x10010634:50-54]`.
6. Scan chunk for `'\r'` or `'\n'`. On hit at index `uVar3`: seek stream to the delimiter position `local_1c+uVar3` via `stream->vtable[0x30]`, null-terminate the buffer there, set EOL flag `local_11=1`, jump to CRLF-consume `[CONFIRMED @ 0x10010634:61-67]`.
7. CRLF-consume (`LAB_10010716`): read 1 byte at a time into a stack scratch (`(int)&param_1 + 3`) via `vtable[0x38](...,1)`; while it is `'\r'`/`'\n'` keep reading; then `stream->vtable[0x2c](0xffffffff)` seeks back 1 to unget the first non-terminator byte `[CONFIRMED @ 0x10010634:81-86]`.
8. Append (`LAB_1001073c`): null-terminate at `uVar3`, `strlen`, `FUN_100029c7(&local_30, buf, buf+len)` appends the range to the accumulator. If EOL was found, finish; else re-tell (`vtable[0x18]`), set `uVar3=local_20` (leftover), loop for the rest of the line `[CONFIRMED @ 0x10010634:87-94]`.
9. Finish (`LAB_10010773`): `FUN_10002b19(local_24, local_30, local_2c)` assigns the accumulated string into `param_1+4`; string destructor `FUN_10002658(&local_30)`; return `local_12` `[CONFIRMED @ 0x10010634:75-80]`.

**Stream interface (`this+0x28`) — recovered vtable slots** `[CONFIRMED @ 0x10010634]`:
- `+0x18` → tell / current position
- `+0x1c` → end position / length
- `+0x2c` → seek relative (called with `-1`)
- `+0x30` → seek to absolute position
- `+0x38` → read N bytes into buffer, returns bool

**Callees (all std::string / helpers, no ecology logic):** `FUN_10002624` (string reserve), `FUN_100025e5` (string init), `FUN_1000ed6d` (clear output string), `FUN_100029c7` (string append range), `FUN_10002b19` (string assign), `FUN_10002658` (string dtor), `memset`, `strlen`.

**Constants/tunables:** `0x28`=40 (chunk size), `0x29`=41 (bound test), `0x2a`=42 (buffer memset), `0xffffffff`=-1 (unget seek), `8` (initial reserve). No message ids, no INI keys, no tunable table.

---

### 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x10010634,io-stream,C2,sc3_eco_stream_read_line,"reads a CR/LF-terminated text line from stream at this+0x28 (vtable 0x18 tell / 0x1c len / 0x2c seek-rel / 0x30 seek-abs / 0x38 read) into std::string at param_1+4; accumulates via FUN_100029c7, assigns via FUN_10002b19; 40-byte chunks; returns bool bytes-read [CONFIRMED @ 0x10010634]"
```

### 2. Notable findings

- **Not a tick / serializer / dispatch table / tunable owner.** This function is a **generic text-stream `readLine` utility**, not an ecology algorithm. It belongs to the module's shared IO/string layer rather than the pollution/garbage subsystem. It consumes CR, LF, and CRLF/LFCR terminators correctly (consume-run-then-unget), reads in 40-byte chunks, and appends across chunks so lines longer than 40 bytes are handled.
- **Value as a witness for the stream vtable.** It confirms a reusable stream interface at object offset `+0x28` with slots `+0x18/+0x1c/+0x2c/+0x30/+0x38`. That interface is the same kind of resource/INI stream the tuning loaders (`FUN_100046bb`, §3 of SIMECO.md) sit on top of, so this `readLine` is a plausible primitive under the `[TuningParameters]` / `[AgentIDModifiers]` line parsing — though this function itself contains **no INI-key strings**, so that linkage is not proven here.
- `[iOS-HINT]` The engine's text/stream layer in the iOS sibling exposes equivalent `cIGZIStream`-style tell/seek/read methods; algorithm shape (chunked readLine with terminator run consumption) transfers, offsets do not.

### 3. Not determined

- **The concrete type of the stream object at `this+0x28`** and the identity of `this`. The function only uses it through vtable slots; no ctor, class-name string, or GZCLSID is referenced in this body. Missing evidence: the owning object's ctor / vtable RVA (which module member installs the `+0x28` stream) — not present in this function.
- **The layout of `param_1`.** Only `param_1+4` is touched (a `std::string` output). Whether `param_1` is a bare string wrapper or a larger struct with other fields is not determinable from this body. Missing evidence: a caller of `FUN_10010634`. No caller/xref data is available in this read-only export (`re/ghidra_export_simeco/` has no `symbols.csv`/xref index, per SIMECO.md §note).
- **Whether this is the exact line reader used by the INI tuning loaders.** Plausible (shared stream interface) but not confirmed — no string/key constant ties it to `SC3Pollution.INI` parsing. Missing evidence: an xref from `FUN_100046bb`/`FUN_1000564a` to `0x10010634`.

**Confidence: C2** — body fully read, mechanically described, all callees identified, named. Not raised to C3 (no second witness / caller available read-only).
