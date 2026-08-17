## Analysis — SIMVARIABLES.DLL toolkit slice (3 functions)

All three functions operate on a **text file/stream object held at `this+0x28`** (a `sysser`/tunable-store member). Its vtable slots are used consistently across the slice: `+0x18` = tell/position, `+0x1c` = size/length, `+0x2c` = seek relative, `+0x30` = seek absolute, `+0x38` = read(buf,len), `+0x40` = write(ptr,len), `+0x10/+0x14/+0x28/+0x44/+0x48/+0x70` = open/close/flush/begin-transaction helpers. Together they are the **INI/tunable text serialiser** (the write-side counterpart to the load path `FUN_100013de`/`FUN_100015e9` in the map).

### 0x10004dd1 — INI-format keyed entry writeback (2356 B) — HIGH VALUE

`bool __thiscall FUN_10004dd1(this, key_str, value_str, param_3)` `[CONFIRMED @ 0x10004dd1 L5]`

Mechanical behaviour:
- Treats `param_1`/`param_2` as `std::string` (begin at `+4`, end at `+8`). **Returns `false` immediately if either string is empty** `[CONFIRMED @ L60–67]`.
- Builds two working strings `local_64`/`local_44` via container-init `FUN_10001147`, and two more via `FUN_1000623b(...,8)` `[CONFIRMED @ L70–80]`.
- Drives the stream at `this+0x28` (`piVar1`) and consults `FUN_100081af(this+4)` to branch between two modes `[CONFIRMED @ L84]`.
- **Uses all three INI writeback format strings** via `FUN_10003995` (format-into-string) + `FUN_10005705` (append) then stream write `+0x40(ptr,len)`:
  - `s___s__1000e258` = `"\n[%s]\n"` — new-section-with-leading-newline `[CONFIRMED @ L146]`
  - `s__s____s_1000e264` = `"%s = %s\n"` — key = value line `[CONFIRMED @ L96,149,196,226,303]`
  - `s___s__1000e270` = `"[%s]\n"` — section header `[CONFIRMED @ L93]`
- Scans the stream line by line for section markers: tests each line's first char for `'['` (0x5b, new section) and skips comment lines beginning `';'` `[CONFIRMED @ L187–188]`.
- Uses a red-black-tree / map lookup on `local_18+7` (`this+0x1c`) via `FUN_100063dd`/`FUN_10006313` to resolve the key `[CONFIRMED @ L142,157]`, then either appends (`+0x28` begin, `+0x18` pos, `+0x48` commit) or rewrites in place.
- Reads a region into a freshly `operator_new`'d buffer (`local_14`, size = `pos_end - pos_start`), rewrites the entry, and writes the buffer back; frees it via `FUN_1000942e(local_14)` `[CONFIRMED @ L192,299–306,312]`.
- Calls delimiter helper `FUN_10003461(&str,&out,&DAT_1000e254)` per line `[CONFIRMED @ L206]`.

**This is the tunable/INI save-serialiser: update-or-insert a `key = value` under an INI section, seeking the existing section and rewriting in place, else appending a new `[section]`.** It is the write counterpart of the documented load path and the highest-value find in this slice.

### 0x10005f31 — read one line from the tunable stream (371 B)

`bool __thiscall FUN_10005f31(this, out_str)` `[CONFIRMED @ 0x10005f31 L5]`

Mechanical behaviour:
- Builds a `std::string` accumulator `local_30` (reserve 8 via `FUN_100019d1`) `[CONFIRMED @ L35]`.
- `local_1c = stream->+0x18()` (current position), `iVar2 = stream->+0x1c()` (size); `uVar3 = size - pos` = **bytes remaining** `[CONFIRMED @ L41–43]`.
- Reads in chunks of up to `0x28` (40) bytes via `stream->+0x38(buf,len)` into a 44-byte stack buffer `local_5c` `[CONFIRMED @ L47,50–54]`.
- Scans each chunk for `'\r'` (0x0d) or `'\n'` (0x0a); on hit, NUL-terminates at the delimiter, seeks the stream back to the char after the newline via `+0x30`, and sets the done flag `local_11` `[CONFIRMED @ L61–67]`.
- Handles `\r\n`: peeks one byte (`+0x38(...,1)`); if not a second EOL char, seeks back one (`+0x2c(0xffffffff)`) `[CONFIRMED @ L81–86]`.
- Appends each chunk to the accumulator via `FUN_10001d05(&local_30, buf, buf+strlen)` `[CONFIRMED @ L88–90]`.
- Assigns the accumulated line into `out_str = param_1` via `FUN_10002efc`(clear) + `FUN_10001e57`(assign) `[CONFIRMED @ L46,76]`.
- Returns `local_12` = whether any bytes were read `[CONFIRMED @ L80]`.

**This is `getline()` over the same `this+0x28` stream** — the line reader the load/parse path consumes.

### 0x10008267 — file move/rename with MoveFileExA fallback (183 B)

`bool __cdecl FUN_10008267(src_obj, dst_obj)` `[CONFIRMED @ 0x10008267 L3]`

> Note argument order: `param_1` = **source**, `param_2` = **destination** (from the `MoveFileA(pCVar4=param_1, pCVar3=param_2)` call at L24–25).

Mechanical behaviour:
- One-time lazy resolve of `MoveFileExA` from `"KERNEL32.DLL"` (`s_KERNEL32_DLL_1000e2d0`, proc `s_MoveFileExA_1000e2c4`), caching the `FARPROC` in `DAT_1000e5c4` behind guard byte `DAT_1000e5c0` `[CONFIRMED @ L14–21]`.
- Both `param_1`/`param_2` expose their path string through vtable slot `+0x14` `[CONFIRMED @ L23–24,29–30]`.
- **Preferred path** (`MoveFileExA` present): calls `MoveFileExA(src, dst, 2)` — flag **`2` = `MOVEFILE_COPY_ALLOWED`** `[CONFIRMED @ L29–31]`.
- **Fallback**: `MoveFileA(src, dst)` — used when `MoveFileExA` is unresolved, or when the `Ex` call fails; on a successful fallback it **permanently disables** the `Ex` path by zeroing `DAT_1000e5c4` `[CONFIRMED @ L22–41]`.
- Returns success bool.

**This is a cross-OS-version file rename utility** (`MoveFileExA` on capable Windows, `MoveFileA` otherwise). Given the INI writeback in `0x10004dd1` builds a rewritten buffer, this is the plausible commit step (write-temp-then-rename), though the caller edge is not read here.

---

## 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x10004dd1,tune,C2,sc3_tune_ini_write_entry,"update-or-insert 'key = value' under an INI section on stream this+0x28; uses fmt '\n[%s]\n'@1000e258, '%s = %s\n'@1000e264, '[%s]\n'@1000e270; scans for '['/';' lines; map lookup FUN_100063dd/FUN_10006313; empty key/value -> false [@0x10004dd1 L60-67,93,96,142,146,188]"
0x10005f31,tune,C2,sc3_tune_stream_read_line,"getline over stream this+0x28; remaining = +0x1c size - +0x18 pos; reads 0x28-byte chunks via +0x38; splits on \r/\n, handles \r\n by peek+seekback +0x2c(-1); accumulates via FUN_10001d05; writes out_str param_1 [@0x10005f31 L41-90]"
0x10008267,util,C2,sc3_util_move_file,"rename src(param_1)->dst(param_2); lazy-load MoveFileExA from KERNEL32.DLL cached DAT_1000e5c4/guard DAT_1000e5c0; MoveFileExA(...,2=MOVEFILE_COPY_ALLOWED) preferred, MoveFileA fallback disables Ex on success; paths via vtable +0x14 [@0x10008267 L14-41]"
```

## 2. Notable findings (structural)

- **Save/serialise path found (`0x10004dd1`).** This is the write counterpart to the documented tunable load path (`FUN_100013de` SimTune.INI, `FUN_100015e9` SYS.PAK). It performs section-aware **update-or-insert** of a `key = value` line using the exact INI writeback format strings the module map catalogued at `0x1000e258/0x1000e264/0x1000e270`. Highest-value find in the slice.
- **Line reader (`0x10005f31`)** is the `getline()` primitive over the same `this+0x28` text stream, driving the parse/load side.
- **Stream object contract confirmed across the slice**: `this+0x28` vtable — `+0x18` tell, `+0x1c` size, `+0x2c` seek-rel, `+0x30` seek-abs, `+0x38` read, `+0x40` write. This extends the map's stream documentation with concrete read/write slot semantics.
- **File-commit utility (`0x10008267`)**: `MoveFileExA` with `MOVEFILE_COPY_ALLOWED` (0x2), `MoveFileA` fallback — the plausible atomic-commit step for the rewritten INI, and a general filesystem util reusable by the toolkit.

## 3. Not determined

- **Caller edges are not proven.** That `0x10008267` commits the buffer produced by `0x10004dd1` is consistent with the code but the call site was not read (xref sweep out of scope for this slice). *Missing:* `-Xref` over the export for `FUN_10008267` and `FUN_10004dd1`.
- **`&DAT_1000e254`** passed to the per-line delimiter helper `FUN_10003461` at `0x10004dd1 L206` — its literal content (the `key`/`value` split delimiter, presumably `"="`) was not read here. *Missing:* the string/bytes at `0x1000e254` (adjacent to the `"\n[%s]\n"` at `0x1000e258`).
- **`param_3` of `0x10004dd1`** is only ever overwritten (`param_3 = *piVar1`) and never read as input `[CONFIRMED @ L200,307]` — its role as an incoming argument is not determined; it functions as a scratch local in every path read.
- No iOS cross-reference was consulted for this slice; all three are plain C-runtime/Win32 + stream-vtable code with no transferable magic constants, so no `[iOS-HINT]` was warranted.

All rows are static-decompilation reads only (C2). Nothing here reaches C3/C4 — that needs runtime or a second witness I cannot produce.
