#!/usr/bin/env python3
r"""pe_patch.py -- the WRITE path for a PE, addressed by virtual address.

WHY THIS EXISTS
`pe_read.py` reads `.rdata`/`.text` at a Ghidra VA; there was no way to write one back. Every
tunable this project has changed so far lived in a shipped data file (`syspak_mod.py`,
`sprite_patch.py`, `city_write.py`), so the toolkit had no answer for the large class of values
that are **compiled into a module as literals** -- the camera scroll step, the edge-scroll
margins, a hardcoded clamp. Those have no INI and no registry key; the only mechanism is a byte
patch, and a byte patch with no guard rails is how a game install gets quietly corrupted.

  py -3.12 re/tools/pe_patch.py <binary> --info
  py -3.12 re/tools/pe_patch.py <binary> --read 0x10067690:f32 -n 5
  py -3.12 re/tools/pe_patch.py <binary> --set 0x10067690:f32=0.0 --expect 32.0 --out <new>
  py -3.12 re/tools/pe_patch.py <binary> --recipe scroll_zero --out <new>
  py -3.12 re/tools/pe_patch.py <binary> --diff <other>
  py -3.12 re/tools/pe_patch.py <binary> --selftest

FOUR INVARIANTS, and they are the point of the module rather than decoration

  1. **Every patch declares the bytes it expects to replace, and a mismatch is REFUSED.** This is
     the guard that makes a patch reproducible: it cannot silently apply to a binary that is not
     the one the RVAs were read from -- a different language build, an already-patched file, a
     later EA release. A recipe additionally pins the input SHA-256.
  2. **Same length, always.** Patches are in-place overwrites at a mapped file offset. Nothing
     inserts, deletes or relocates, so no offset, no relocation and no section header moves.
     `build()` asserts the output length equals the input length.
  3. **The input is never written to.** Output always goes to `--out`. Staging the modified file
     into the install (and restoring it) is a deliberate separate step, per the
     move-aside-never-overwrite rule in `verify/tunable_mod_test/README.md`.
  4. **The diff is re-derivable.** `--diff` reports exact offsets, so a claim of the form "this
     file differs from shipped by exactly N bytes at these addresses" can be checked
     independently of the code that produced it. `verify/tunable_mod_test` established that as a
     method rule: re-diff the staged file before interpreting any observation.

WHAT IS NOT DONE, and why that is correct here
The PE OptionalHeader `CheckSum` is left alone. Measured on the targets in this install
(`Apps\SIMSPR.DLL`, `SC3U.exe`): the field is already **0x00000000**, i.e. the original linker
never computed one, and the Windows loader only validates it for kernel drivers and
forced-integrity images (`DllCharacteristics` is 0x0000 here -- no such flag). Writing a
*correct* checksum into a file that shipped with a zero would add a second diff site for no
behavioural gain and weaken invariant 4. If a future target ships a NON-zero checksum, `--info`
says so and that decision has to be revisited rather than inherited.

There is also no attempt at code injection. Changing an instruction's *operand* in place (a
`push imm8`, a `lea` displacement) is inside invariant 2; adding instructions is not, and the
one camera knob that would need it -- the missing 1/sqrt(2) on diagonal scroll -- is deliberately
left out of the recipe table rather than half-supported.
"""
import hashlib
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pe_read import PE


class PatchError(Exception):
    pass


# --- value codecs ----------------------------------------------------------------------
#
# `i8` exists as a distinct kind from `u8` because the displacement bytes in the edge-scroll
# rects are SIGNED (`lea edx,[eax+0x30]` vs `lea edi,[esi-0x30]` = 0xd0), and the project
# convention is to report sign-sensitive values as both raw hex and signed decimal. Keeping the
# two kinds separate means a caller writing -48 gets 0xd0 and a caller writing 208 is refused.

CODECS = {
    "f32": ("<f", 4), "f64": ("<d", 8),
    "u8": ("<B", 1), "i8": ("<b", 1),
    "u16": ("<H", 2), "i16": ("<h", 2),
    "u32": ("<I", 4), "i32": ("<i", 4),
}


def encode(kind, value):
    """-> bytes. `kind` is a CODECS key or 'hex' (value is a hex byte string)."""
    if kind == "hex":
        h = value.replace(" ", "").replace("_", "")
        if len(h) % 2:
            raise PatchError("hex value %r has an odd number of digits" % value)
        return bytes.fromhex(h)
    if kind not in CODECS:
        raise PatchError("unknown kind %r (want one of %s, hex)"
                         % (kind, ", ".join(sorted(CODECS))))
    fmt, _ = CODECS[kind]
    v = float(value) if kind.startswith("f") else int(str(value), 0)
    try:
        return struct.pack(fmt, v)
    except struct.error as e:
        raise PatchError("%s cannot hold %r: %s" % (kind, value, e))


def decode(kind, buf):
    if kind == "hex":
        return buf.hex(" ")
    fmt, n = CODECS[kind]
    return struct.unpack_from(fmt, buf, 0)[0]


def show(kind, buf):
    """Human form of a value: raw hex ALWAYS, plus the typed reading."""
    if kind == "hex":
        return buf.hex(" ")
    v = decode(kind, buf)
    if kind.startswith("f"):
        return "%s (%s)" % (buf.hex(" "), v)
    return "%s (%s = %d)" % (buf.hex(" "), hex(v & (1 << 8 * CODECS[kind][1]) - 1), v)


# --- the patcher -----------------------------------------------------------------------

class Patcher:
    """Stage VA-addressed same-length overwrites on a PE, then build the output."""

    def __init__(self, path):
        self.path = path
        self.pe = PE(path)
        self.d = self.pe.d
        self.sha = hashlib.sha256(self.d).hexdigest()
        self.patches = []                       # list of dicts: off, va, sec, old, new, kind, note

    # -- reading

    def read(self, va, n):
        return self.pe.raw(va, n)

    # -- staging

    def stage(self, va, kind, value, expect=None, note=""):
        """Stage one overwrite. Refuses unless the bytes on disk are what the caller expected.

        `expect` may be a value of the same `kind` (the readable form -- `32.0`, `-2`) or a hex
        byte string. It is not optional in spirit: `--set` without `--expect` is allowed only
        because `--read` is one command away, and the staged patch still reports the old bytes.
        """
        new = encode(kind, value)
        off, sec = self.pe.off(va)
        old = self.d[off:off + len(new)]
        if len(old) != len(new):
            raise PatchError("0x%08x: %d bytes requested but only %d are in raw data"
                             % (va, len(new), len(old)))
        if expect is not None:
            want = encode("hex", expect) if _is_hexish(expect, len(new)) else encode(kind, expect)
            if len(want) != len(new):
                raise PatchError("0x%08x: --expect is %d bytes, the patch is %d"
                                 % (va, len(want), len(new)))
            if old != want:
                raise PatchError(
                    "0x%08x (%s, file offset 0x%x): REFUSED -- expected %s but the file has %s.\n"
                    "  This binary is not the one the address was read from (different build, "
                    "already patched, or the wrong file). Nothing was written."
                    % (va, sec, off, show(kind, want), show(kind, old)))
        for p in self.patches:
            if off < p["off"] + len(p["new"]) and p["off"] < off + len(new):
                raise PatchError("0x%08x overlaps an already-staged patch at 0x%08x"
                                 % (va, p["va"]))
        self.patches.append({"off": off, "va": va, "sec": sec, "old": old, "new": new,
                             "kind": kind, "note": note})
        return self.patches[-1]

    # -- building

    def build(self):
        """-> output bytes. Length-preserving by construction, and asserted."""
        out = bytearray(self.d)
        for p in self.patches:
            out[p["off"]:p["off"] + len(p["new"])] = p["new"]
        if len(out) != len(self.d):
            raise PatchError("length changed %d -> %d" % (len(self.d), len(out)))
        return bytes(out)

    def write(self, out_path):
        if os.path.abspath(out_path) == os.path.abspath(self.path):
            raise PatchError("refusing to overwrite the input %s -- write elsewhere and stage it "
                             "deliberately" % self.path)
        blob = self.build()
        with open(out_path, "wb") as fh:
            fh.write(blob)
        return blob

    # -- reporting

    def report(self):
        lines = ["%s  %d bytes  sha256 %s" % (self.path, len(self.d), self.sha[:16] + "..."),
                 "  %d patch(es) staged:" % len(self.patches)]
        for p in self.patches:
            lines.append("    0x%08x  off 0x%-6x %-7s %s -> %s%s"
                         % (p["va"], p["off"], p["sec"], show(p["kind"], p["old"]),
                            show(p["kind"], p["new"]),
                            "   # " + p["note"] if p["note"] else ""))
        return "\n".join(lines)


def _is_hexish(s, n):
    """True if `s` looks like an n-byte hex literal rather than a typed value."""
    if not isinstance(s, str):
        return False
    t = s.replace(" ", "").replace("_", "")
    if len(t) != 2 * n or t.lower().startswith("0x"):
        return False
    return all(c in "0123456789abcdefABCDEF" for c in t)


# --- diff ------------------------------------------------------------------------------

def diff(a, b):
    """-> (runs, total) where runs is a list of (offset, a_bytes, b_bytes) for each differing run.

    Independent of the patcher: it reads two files and compares them. That independence is the
    whole value -- it is how a "differs by exactly these N bytes" claim gets checked without
    trusting the code that made the file.
    """
    if len(a) != len(b):
        return None, "lengths differ: %d vs %d" % (len(a), len(b))
    runs, i, n = [], 0, len(a)
    while i < n:
        if a[i] == b[i]:
            i += 1
            continue
        j = i
        while j < n and a[j] != b[j]:
            j += 1
        runs.append((i, a[i:j], b[i:j]))
        i = j
    return runs, sum(len(r[1]) for r in runs)


# --- recipes ---------------------------------------------------------------------------
#
# A recipe is a NAMED, ANCHORED, SELF-VERIFYING patch set. Named so a verify run is reproducible
# from a RESULTS.md line instead of a remembered command; anchored so it refuses a binary other
# than the one the addresses came from; self-verifying because every entry carries its expected
# shipped bytes.
#
# CAMERA / VIEW SCROLL -- all in Apps\SIMSPR.DLL, class cSC3WinCityView (vtable 0x10067894).
# .text and .rdata are both mapped 1:1 in this module (`--info` shows va-base == raw), so
# file offset == VA - 0x10000000.
#
#   The step bank, `.rdata` 0x10067690..0x100676a0, five float32s, ALL shipped 32.0f.
#   [CONFIRMED @ 0x100440b1] copies them into the object:
#       +0x1dc <- 0x100676a0    +0x1d8 <- 0x1006769c    +0x1d4 <- 0x10067698
#       +0x1d0 <- 0x10067694    +0x1cc <- 0x10067690    +0x1c8 <- 0x10067694
#   +0x1c8 is the ACTIVE step. [CONFIRMED @ 0x10042d8a] (ZoomIn) re-selects it by zoom index:
#       0 -> +0x1dc   1 -> +0x1d8   2 -> +0x1d4   3 or other -> +0x1d0   4 -> +0x1cc
#   so the .rdata slot for a zoom level is: 0 -> 0x676a0, 1 -> 0x6769c, 2 -> 0x67698,
#   3 -> 0x67694, 4 -> 0x67690. **0x67694 is both the zoom-3 slot and the boot default**, since
#   0x100440b1 writes it into +0x1c8 unconditionally at construction.
#   The consumer: [CONFIRMED @ 0x10043daf] reads `param_1[0x72]` (= +0x1c8) and passes it to
#   Translate (vtbl +0x34) as +-step on one or both axes, for BOTH the arrow keys (VK 0x26/0x28/
#   0x25/0x27 polled through param_1[0x84] vtbl+0xc) and edge-scroll. One step, no ramp.
#
#   The mouse-drag path is SEPARATE and is not touched by the step bank: 0x10043daf's
#   `+0x1e6 != 0` branch passes `param_1[0x7d]`/`[0x7e]` (= +0x1f4/+0x1f8), computed in
#   [CONFIRMED @ 0x10043a38]. That separation is what makes drag-scroll a free negative control
#   for a step-bank patch: if the step goes to 0 and right-drag still pans, the game is running
#   and reading input, so "nothing moved" cannot be a frozen client.
#
#   0x100676a4 (12.0f, drag dead zone) and 0x100676a8 (80.0f, drag velocity clamp) belong to that
#   drag path. 0x100676ac is NOT a float -- it reads 29 ad 04 10 = pointer 0x1004ad29, which is
#   where the float run ends.

SIMSPR_SHA = "eec715009152eec0ce756f74db5bb6f9718469562c7b9ac64d25f94509e9291d"

# zoom index -> (VA, shipped value)
ZOOM_STEP = {4: 0x10067690, 3: 0x10067694, 2: 0x10067698, 1: 0x1006769c, 0: 0x100676a0}
SHIPPED_STEP = 32.0
DEFAULT_ZOOM = 3                # the slot 0x100440b1 copies into the active field at construction

DRAG_DEADZONE_VA = 0x100676a4   # 12.0f
DRAG_CLAMP_VA = 0x100676a8      # 80.0f
DRAG_DIVISOR_VAS = (0x10043a5e, 0x10043a68)      # the imm8 of `push -2`, X then Y

# The eight signed lea displacements that build the edge-scroll hit rects [CONFIRMED @ 0x10043989].
# Order as they appear; keep the +-pairs consistent or the rects disagree with each other.
#
# These are the addresses of the DISPLACEMENT BYTE, which is the instruction start + 2 (the form
# is `8d /r disp8`, e.g. `8d 50 30` = `lea edx,[eax+0x30]` at 0x10043992, displacement at
# 0x10043994). Worth stating because the first table written for this was a list of instruction
# starts, and `--expect` refused it -- 0x10043992 holds 0x8d, the opcode, not 48. The eight sites
# below were then re-derived by scanning 0x43989..0x43a38 for `8d` with mod=01, which finds
# exactly eight and no others.
EDGE_MARGIN_VAS = (0x10043994, 0x100439b5, 0x100439d6, 0x100439f7,
                   0x10043a06, 0x10043a0f, 0x10043a18, 0x10043a1b)
EDGE_SHIPPED = (48, 64, -48, -64, 64, 48, -48, -64)


def _anchor(p, sha, what):
    if p.sha != sha:
        raise PatchError(
            "%s expects %s\n  sha256 %s\n  but %s has\n  sha256 %s\n"
            "  The addresses in this recipe were read from that exact file; applying them "
            "elsewhere is not a patch, it is a guess. Nothing was written."
            % (what, os.path.basename(p.path), sha, p.path, p.sha))


def r_scroll_zero(p, arg=None):
    """Every zoom level's keyboard/edge scroll step -> 0.0f. The discriminator, not a mod."""
    _anchor(p, SIMSPR_SHA, "recipe scroll_zero")
    for z in sorted(ZOOM_STEP, reverse=True):
        p.stage(ZOOM_STEP[z], "f32", 0.0, expect=SHIPPED_STEP, note="zoom %d step" % z)


def r_scroll_default_zero(p, arg=None):
    """Only the default/zoom-%d slot -> 0.0f; the other four keep 32.0f. Isolates the selector."""
    _anchor(p, SIMSPR_SHA, "recipe scroll_default_zero")
    p.stage(ZOOM_STEP[DEFAULT_ZOOM], "f32", 0.0, expect=SHIPPED_STEP,
            note="zoom %d step (also the construction default)" % DEFAULT_ZOOM)


def r_scroll_speed(p, arg):
    """`--recipe scroll_speed=N` -> every zoom level's step becomes N. The actual sensitivity mod.

    Accepts `N` for all five, or `z0:a,z1:b,...` for per-zoom values (which the shipped binary
    does not use: all five ship 32.0f, so zoom currently has no effect on scroll speed).
    """
    _anchor(p, SIMSPR_SHA, "recipe scroll_speed")
    if arg is None:
        raise PatchError("scroll_speed needs a value: --recipe scroll_speed=64 "
                         "(or scroll_speed=z0:16,z3:64)")
    if ":" in arg:
        for part in arg.split(","):
            k, _, v = part.partition(":")
            z = int(k.lstrip("zZ"))
            if z not in ZOOM_STEP:
                raise PatchError("zoom index %d is outside 0..4" % z)
            p.stage(ZOOM_STEP[z], "f32", float(v), expect=SHIPPED_STEP,
                    note="zoom %d step" % z)
        return
    for z in sorted(ZOOM_STEP, reverse=True):
        p.stage(ZOOM_STEP[z], "f32", float(arg), expect=SHIPPED_STEP, note="zoom %d step" % z)


def r_drag_divisor(p, arg):
    """`--recipe drag_divisor=N` -> the `push -2` imm8 in UpdateScroll becomes -N.

    The drag velocity is `(anchor - mouse) / -N`, so a SMALLER magnitude is MORE sensitive
    (`-1` doubles it, `-4` halves it). The sign carries the direction and must stay negative;
    N=0 would be a division by zero and is refused.
    """
    _anchor(p, SIMSPR_SHA, "recipe drag_divisor")
    n = int(str(arg), 0) if arg is not None else 0
    if n <= 0:
        raise PatchError("drag_divisor needs a positive N (the code divides by -N); N=0 would "
                         "divide by zero")
    if n > 128:
        raise PatchError("N=%d does not fit a signed imm8 as -N (max 128)" % n)
    for va, axis in zip(DRAG_DIVISOR_VAS, ("X", "Y")):
        p.stage(va, "i8", -n, expect=-2, note="drag divisor %s axis" % axis)


def r_drag_deadzone(p, arg):
    """`--recipe drag_deadzone=N` -> the right-drag dead zone (shipped 12.0f) becomes N.

    The dead zone is a per-axis gate on the POST-divisor velocity `(anchor - mouse)/-N_div`
    [CONFIRMED @ 0x10043a38]: an axis does not pan until `|v| > deadzone`, and at that instant its
    velocity field steps discontinuously from 0 to ~deadzone. So a SMALLER dead zone engages sooner
    (the engage distance is `deadzone * N_div` px, so on a drag_divisor=4 build the shipped 12 means
    48 px), softens the onset step, and widens the diagonal band (the gate is per-axis/box, not
    radial). N=0 disables the gate (pans on any motion, risking tremor drift). Must stay below the
    drag clamp (80.0f) or no proportional band remains.
    """
    _anchor(p, SIMSPR_SHA, "recipe drag_deadzone")
    if arg is None:
        raise PatchError("drag_deadzone needs a value: --recipe drag_deadzone=4 (shipped is 12)")
    n = float(arg)
    if not 0.0 <= n < 80.0:
        raise PatchError("drag_deadzone %g is outside 0..80 (the drag clamp at 0x100676a8); at or "
                         "above the clamp no proportional velocity band remains" % n)
    p.stage(DRAG_DEADZONE_VA, "f32", n, expect=12.0, note="right-drag dead zone")


def r_edge_margin(p, arg):
    """`--recipe edge_margin=H,V` -> the edge-scroll trigger band (shipped 64 horizontal, 48 vertical).

    All eight displacements move together, keeping every +-pair consistent.
    """
    _anchor(p, SIMSPR_SHA, "recipe edge_margin")
    if arg is None or "," not in arg:
        raise PatchError("edge_margin needs H,V: --recipe edge_margin=32,24 "
                         "(shipped is 64,48)")
    h, v = (int(x, 0) for x in arg.split(",", 1))
    for x in (h, v):
        if not 1 <= x <= 127:
            raise PatchError("margin %d is outside 1..127 (signed imm8)" % x)
    # EDGE_SHIPPED order: 48(V) 64(H) -48(V) -64(H) 64(H) 48(V) -48(V) -64(H)
    want = (v, h, -v, -h, h, v, -v, -h)
    for va, old, new in zip(EDGE_MARGIN_VAS, EDGE_SHIPPED, want):
        p.stage(va, "i8", new, expect=old, note="edge rect displacement")


# --- U-068 resizable-window rect-push fix (code cave, still same-length) ----------------
#
# UNLIKE every recipe above, this one is NOT a constant edit -- it installs a CALL. The confirmed
# U-068 fix (verify/u068_rectpush_test/RESULTS.md, probe da6f2080) is: after the iso-view Init
# `FUN_10005b42` erases the persistent present-rect list `iso+0x4d0` on a resize, replay the ctor's
# single `push_back {0,0,new_w,new_h}` via `FUN_10010586`, so the per-frame present `FUN_1000e058`
# has a rect again and blits `iso+0x74` to the composite. `iso+0x4d0` is appended-only (no per-frame
# clear -- Init and the dtor are the only emptiers), so one push is enough and there is no leak; the
# dormant `iso+0x4f0`-gated flush recorder was rejected precisely because forcing it on WOULD leak.
#
# It stays inside invariant 2 (same length) by living in EXISTING executable slack: SIMSPR `.text`
# ends its content at VirtualSize 0x6049a (VA 0x1006149a) but the raw section runs to 0x61000, so
# 0x1006149a..0x10062000 is 0xB66 zero bytes inside `.text`'s single RX page based at 0x10061000
# (real code occupies 0x10061000..0x1006149a, so the page is already mapped). We overwrite 37 of
# those zeros with a trampoline and rewrite ONE call's rel32 to reach it. No insert, no relocation,
# no section-header edit. `.text` chars 0x60000020 (CODE|EXECUTE|READ); checksum ships 0x0.
#
# Hook: Init's `call FUN_1000b70e` at 0x10005f55 (bytes e8 b4 57 00 00), chosen because `iso` is live
# in ECX there (`mov ecx,ebx` @ 0x10005f4b; EBX also holds it, but the trampoline uses ECX) and the
# call is a plain `__thiscall(this)` with no stack args, so wrapping it is clean.
#   [CONFIRMED @ SIMSPR byte-scan 0x10005f30..0x10005f60; FUN_1000b70e __fastcall(this); ret]
#
# Trampoline @ 0x1006149a (37 bytes; rel32s ASLR-invariant, both callees intra-module):
#   51                   push ecx                 ; save iso across FUN_1000b70e
#   e8 <rel FUN_1000b70e> call FUN_1000b70e        ; original line-253 behaviour, ecx=iso
#   5a                   pop edx                  ; edx = iso  (do not rely on ebx surviving)
#   50                   push eax                 ; save FUN_1000b70e result (caller uses it)
#   ff 72 60             push [edx+0x60]          ; rect.bottom = new height
#   ff 72 5c             push [edx+0x5c]          ; rect.right  = new width
#   6a 00                push 0                   ; rect.top
#   6a 00                push 0                   ; rect.left
#   8b c4                mov eax, esp             ; -> &rect
#   50                   push eax                 ; push_back arg = &rect
#   8d 8a d0 04 00 00    lea ecx, [edx+0x4d0]     ; this = &iso.presentlist
#   e8 <rel FUN_10010586> call FUN_10010586        ; __thiscall push_back; ret 4 (cleans &rect)
#   83 c4 10             add esp, 0x10            ; drop the 16-byte rect
#   58                   pop eax                  ; restore FUN_1000b70e result
#   c3                   ret                      ; -> 0x10005f5a
# [CONFIRMED @ FUN_10010586 __thiscall(this,ptr) ends 5f c2 04 00 = pop edi; ret 4]
#
# The rel32s are pre-baked for the shipped layout; the recipe REFUSES any file but SIMSPR_SHA, so a
# different build (where the addresses would be wrong) cannot be mispatched.

RESIZE_CAVE_VA = 0x1006149a
RESIZE_CAVE_BYTES = ("51e86ea2faff5a50ff7260ff725c6a006a00"
                     "8bc4508d8ad0040000e8ccf0faff83c41058c3")   # 37 bytes, see table above
RESIZE_CAVE_EXPECT = "00" * 37                                   # slack, all zero in shipped
RESIZE_HOOK_VA = 0x10005f55
RESIZE_HOOK_NEW = "e840b50500"          # call rel32 -> 0x1006149a
RESIZE_HOOK_EXPECT = "e8b4570000"       # call FUN_1000b70e in shipped


def r_resize_rectfix(p, arg=None):
    """`--recipe resize_rectfix` -> install the U-068 post-resize present-rect push (code cave).

    Two same-length overwrites: fill 37 bytes of `.text` slack at 0x1006149a with a trampoline that
    (a) performs Init's original `FUN_1000b70e` call, then (b) push_backs {0,0,new_w,new_h} into the
    iso present-rect list; and rewrite Init's `call FUN_1000b70e` at 0x10005f55 to reach it. Anchored
    to the shipped SIMSPR SHA. Expected `--diff` vs shipped: 36 bytes (33 in the cave, 3 at the hook).
    """
    _anchor(p, SIMSPR_SHA, "recipe resize_rectfix")
    p.stage(RESIZE_CAVE_VA, "hex", RESIZE_CAVE_BYTES, expect=RESIZE_CAVE_EXPECT,
            note="U-068 rect-push trampoline (erase->push_back {0,0,w,h})")
    p.stage(RESIZE_HOOK_VA, "hex", RESIZE_HOOK_NEW, expect=RESIZE_HOOK_EXPECT,
            note="redirect Init call FUN_1000b70e -> cave")


# --- GZGraphicD resizable-window frame (style flip) ------------------------------------
#
# The main "Gonzo" window ships as a FIXED frame: WS_POPUP|CAPTION|SYSMENU|MINIMIZEBOX
# (0x80CA0000), with no WS_THICKFRAME (sizing border) and no WS_MAXIMIZEBOX. To let the owner
# drag/maximize the window on a REAL display (the D-004 hand-test), three same-length imm bytes
# add WS_THICKFRAME (0x40000) + WS_MAXIMIZEBOX (0x10000) at both style sources:
#   - create-time style FUN_100181d0(mask): mask 0x1b is set by `mov [ebx+0x10],0x1b` at
#     0x10017ca1 (imm byte 0x10017ca4). Bit 0x20 enables the MAXIMIZEBOX branch; that branch's
#     `or eax,0x10000` (imm byte 0x10018223) folds THICKFRAME in beside it. [CONFIRMED @ 0x100181d0]
#   - runtime windowed override FUN_1001854a: `push 0x90C80000` (imm byte 0x10018570) is the LIVE
#     style slammed via SetWindowLongA(GWL_STYLE) - the load-bearing one. [CONFIRMED @ 0x1001854a]
# Trap-2 note: FUN_1001854a's SetWindowPos snap-back is a mode-apply method, NOT on the WM_SIZE
# path, so the flip holds during normal windowed drag (it only refits on a fullscreen<->windowed
# toggle). This recipe does NOT make the resized view re-render - that is the separate "bridge",
# which cannot ship as a pure DLL (SIMSPR has no global for the live iso-view/bridge pointers).
# Bytes verified by disassembly of original\modules\GZGraphicD.dll.

GZGRAPHICD_SHA = "48201f476121adeea2957b8cc9b3063326aee28b86b026acab7179c878ad454d"


# --- GZGraphicD X-button (WM_CLOSE) quit fix (code cave) --------------------------------
#
# The Gonzo WndProc FUN_10017e2f SWALLOWS WM_CLOSE (the `je 0x100181c7` at 0x10017eab, msg==0x10 →
# shared return-0 epilogue) — the X does nothing, PRE-EXISTING (shipped WS_SYSMENU always had a close
# box). SC3U's main loop is a PeekMessage loop (GZWIN FUN_10020971) that exits ONLY on WM_QUIT(0x12)
# or the GZ end-message 0x700, with NO window-alive check — so DestroyWindow alone would orphan the
# process (loop spins on a dead window). The SAFE quit is PostQuitMessage(0), but GZGraphicD does not
# import it. It DOES import LoadLibraryA + GetProcAddress (kernel32) and depends on USER32, and has
# 2038 bytes of .text slack at 0x1001d80a. So a 67-byte cave resolves PostQuitMessage at runtime and
# calls it, FAIL-CLOSED: a NULL from LoadLibraryA or GetProcAddress falls through to the original
# return-0 (X still does nothing) rather than faulting in the WndProc. Blast radius = the WM_CLOSE
# branch only (which did nothing before). Bytes assembled + capstone-verified; cave disassembles to:
#   push "user32.dll"; call [LoadLibraryA]; test eax,eax; je ret0
#   push "PostQuitMessage"; push eax; call [GetProcAddress]; test eax,eax; je ret0
#   push 0; call eax  (PostQuitMessage(0)); ret0: jmp 0x100181c7
# IAT slots [CONFIRMED @ GZGraphicD]: LoadLibraryA 0x1001e05c, GetProcAddress 0x1001e048.

GZ_XQUIT_CAVE_VA = 0x1001d80a
GZ_XQUIT_CAVE = ("6832d80110ff155ce0011085c07414683dd8011050ff1548e0011085c074046a00ffd0"
                 "e995a9ffff7573657233322e646c6c00506f7374517569744d65737361676500")  # 67 bytes
GZ_XQUIT_HOOK_VA = 0x10017ead          # the je's rel32 (je itself at 0x10017eab: 0f 84 <rel32>)


def r_close_button_quit(p, arg=None):
    """`--recipe close_button_quit` -> make the window X button quit the game (GZGraphicD, code cave).

    A 67-byte cave (PostQuitMessage(0), fail-closed on NULL) in .text slack + one 4-byte rel32 redirect
    of the WM_CLOSE branch. Anchored to shipped GZGraphicD SHA. Expected `--diff` vs shipped: 66 bytes /
    4 runs (67 cave minus 3 bytes that coincide with the pre-existing zero slack = 64, plus 2 changed
    bytes in the hook rel32 - the other 2 rel bytes are unchanged 0x00).
    """
    _anchor(p, GZGRAPHICD_SHA, "recipe close_button_quit")
    p.stage(GZ_XQUIT_CAVE_VA, "hex", GZ_XQUIT_CAVE, expect="00" * 67,
            note="WM_CLOSE -> resolve+call PostQuitMessage(0), fail-closed")
    p.stage(GZ_XQUIT_HOOK_VA, "hex", "59590000", expect="16030000",
            note="redirect WM_CLOSE je rel32 -> cave 0x1001d80a")


def r_resizable_frame(p, arg=None):
    """`--recipe resizable_frame` -> add WS_THICKFRAME|WS_MAXIMIZEBOX to the Gonzo window (GZGraphicD).

    Three same-length imm bytes at the two style sources. Anchored to the shipped GZGraphicD SHA.
    Expected `--diff` vs shipped: 3 bytes. Does NOT re-render on resize (that is the bridge).
    """
    _anchor(p, GZGRAPHICD_SHA, "recipe resizable_frame")
    p.stage(0x10017ca4, "hex", "3b", expect="1b", note="create-style mask 0x1b->0x3b (enable MAXIMIZEBOX branch)")
    p.stage(0x10018223, "hex", "05", expect="01", note="or eax,0x10000->0x50000 (fold in WS_THICKFRAME)")
    p.stage(0x10018570, "hex", "cd", expect="c8", note="live windowed style 0x90C80000->0x90CD0000")


RECIPES = {
    "resizable_frame": r_resizable_frame,
    "close_button_quit": r_close_button_quit,
    "scroll_zero": r_scroll_zero,
    "scroll_default_zero": r_scroll_default_zero,
    "scroll_speed": r_scroll_speed,
    "drag_divisor": r_drag_divisor,
    "drag_deadzone": r_drag_deadzone,
    "edge_margin": r_edge_margin,
    "resize_rectfix": r_resize_rectfix,
}


def apply_recipe(p, spec):
    name, _, arg = spec.partition("=")
    fn = RECIPES.get(name)
    if fn is None:
        raise PatchError("unknown recipe %r (have: %s)" % (name, ", ".join(sorted(RECIPES))))
    fn(p, arg or None)
    return name


# --- selftest --------------------------------------------------------------------------

def selftest(target):
    """-> (n_pass, n_fail). Checks the module's own invariants, not the game's behaviour."""
    ok = fail = 0

    def check(name, cond, detail=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print("  PASS  %s" % name)
        else:
            fail += 1
            print("  FAIL  %s %s" % (name, detail))

    # 1. codec round-trip over every kind
    # f32 samples are all exactly representable in binary32, so `decode(encode(v)) == v` is the
    # right assertion. A value like 1e30 is NOT (it round-trips to 1.0000000150474662e+30), and
    # demanding equality there would be testing IEEE-754 rather than this module.
    samples = {"f32": [0.0, 32.0, -1.5, 65536.0], "f64": [0.0, 32.0, -1.5, 1e30],
               "u8": [0, 1, 255], "i8": [-128, -2, 0, 127],
               "u16": [0, 0x1234, 0xFFFF], "i16": [-32768, 0, 32767],
               "u32": [0, 0xDEADBEEF, 0xFFFFFFFF], "i32": [-2147483648, 0, 2147483647]}
    bad = [(k, v) for k, vs in samples.items() for v in vs
           if decode(k, encode(k, v)) != v]
    check("codec round-trip (%d values)" % sum(len(v) for v in samples.values()),
          not bad, bad[:3])

    # 2. out-of-range is refused rather than truncated
    refused = 0
    for k, v in (("u8", 256), ("i8", 128), ("i8", -129), ("u16", 0x10000), ("i32", 1 << 31)):
        try:
            encode(k, v)
        except PatchError:
            refused += 1
    check("out-of-range values refused (5 cases)", refused == 5, "only %d refused" % refused)

    files = []
    if os.path.isdir(target):
        for root, _, names in os.walk(target):
            files += [os.path.join(root, x) for x in sorted(names)
                      if x.lower().endswith((".dll", ".exe"))]
    else:
        files = [target]
    pes = []
    for f in files:
        try:
            pes.append(Patcher(f))
        except (ValueError, OSError):
            pass
    check("opened at least one PE under %s" % target, bool(pes), "found none")
    if not pes:
        return ok, fail

    # 3. identity build: no patches -> byte-identical
    bad = [p.path for p in pes if p.build() != p.d]
    check("identity build byte-identical (%d PEs)" % len(pes), not bad, bad[:3])

    # 4. VA->offset mapping agrees with the section table at each section's first byte
    bad = []
    for p in pes:
        for name, vaddr, vsize, raddr, rsize in p.pe.sections:
            if rsize == 0:
                continue
            try:
                o, sec = p.pe.off(p.pe.base + vaddr)
            except ValueError:
                bad.append((p.path, name, "unmapped"))
                continue
            if o != raddr or sec != name:
                bad.append((p.path, name, "off 0x%x != raw 0x%x" % (o, raddr)))
    check("section-start VA maps to raw offset", not bad, bad[:3])

    # 5. an address below the first section must be refused, not silently mapped
    refused = 0
    for p in pes:
        try:
            p.pe.off(p.pe.base)          # the PE header itself is in no section
        except ValueError:
            refused += 1
    check("header VA refused (%d/%d PEs)" % (refused, len(pes)), refused == len(pes))

    # 6. a wrong --expect is refused
    p = pes[0]
    sec_va = None
    for name, vaddr, vsize, raddr, rsize in p.pe.sections:
        if rsize and name == ".rdata":
            sec_va = p.pe.base + vaddr
    sec_va = sec_va or p.pe.base + p.pe.sections[0][1]
    real, _ = p.read(sec_va, 4)
    wrong = bytes((b ^ 0xFF) for b in real)
    try:
        p.stage(sec_va, "hex", "00000000", expect=wrong.hex())
        check("wrong --expect refused", False, "it was accepted")
    except PatchError:
        check("wrong --expect refused", True)

    # 7. a correct --expect is accepted, preserves length, and NOTHING outside the patch moves.
    #
    # The patch value is the bitwise complement of the shipped bytes, so all four bytes are
    # guaranteed to change and the expected diff is exactly one 4-byte run. (Writing zeros here
    # was the first attempt and it under-reported: the shipped bytes already contained zeros, so
    # only 2 of 4 bytes differed and an "exactly 4 bytes" assertion failed on a correct patch.)
    p2 = Patcher(p.path)
    off, _ = p2.pe.off(sec_va)
    p2.stage(sec_va, "hex", wrong.hex(), expect=real.hex())
    blob = p2.build()
    runs, total = diff(p2.d, blob)
    check("staged patch: length preserved", len(blob) == len(p2.d))
    check("staged patch: diff is exactly the 4 patched bytes",
          runs == [(off, real, wrong)],
          "%d run(s), %d byte(s)" % (len(runs or []), total))
    # and the general invariant, which is the one that matters for a multi-patch recipe:
    # every differing byte must fall inside some staged patch's range.
    q = Patcher(simspr.path) if (simspr := next(
        (x for x in pes if os.path.basename(x.path).upper() == "SIMSPR.DLL"), None)) else None
    if q is not None:
        apply_recipe(q, "scroll_zero")
        apply_recipe(q, "drag_divisor=4")
        ranges = [(x["off"], x["off"] + len(x["new"])) for x in q.patches]
        runs, total = diff(q.d, q.build())
        stray = [hex(o) for o, oa, _ in runs
                 for i in range(o, o + len(oa))
                 if not any(lo <= i < hi for lo, hi in ranges)]
        check("multi-patch: no byte changes outside a staged range (7 patches)",
              not stray, stray[:4])

    # 8. overlapping patches are refused
    p3 = Patcher(p.path)
    p3.stage(sec_va, "hex", "00000000", expect=real.hex())
    try:
        p3.stage(sec_va + 2, "hex", "0000", expect=real[2:4].hex())
        check("overlapping patch refused", False, "it was accepted")
    except PatchError:
        check("overlapping patch refused", True)

    # 9. writing over the input is refused
    p4 = Patcher(p.path)
    try:
        p4.write(p.path)
        check("overwrite of input refused", False, "it was accepted")
    except PatchError:
        check("overwrite of input refused", True)

    # 10. the shipped anchor: if SIMSPR is present, every camera recipe must anchor and its
    #     expected bytes must match, which re-checks the documented constants against the file.
    simspr = next((x for x in pes if os.path.basename(x.path).upper() == "SIMSPR.DLL"), None)
    if simspr is None:
        print("  SKIP  camera recipes (no SIMSPR.DLL under %s)" % target)
        return ok, fail
    check("SIMSPR.DLL matches the recipe anchor", simspr.sha == SIMSPR_SHA, simspr.sha[:16])
    for spec in ("scroll_zero", "scroll_default_zero", "scroll_speed=64",
                 "drag_divisor=1", "drag_deadzone=4", "edge_margin=32,24"):
        try:
            q = Patcher(simspr.path)
            apply_recipe(q, spec)
            n = len(q.patches)
            runs, total = diff(q.d, q.build())
            check("recipe %-22s stages %d patch(es), %d byte(s) differ"
                  % (spec, n, total), n > 0 and total > 0)
        except PatchError as e:
            check("recipe %s applies" % spec, False, str(e).splitlines()[0])
    # the shipped values themselves, read out of the file rather than trusted from the comment
    steps = [decode("f32", simspr.read(va, 4)[0]) for va in ZOOM_STEP.values()]
    check("all five zoom steps ship %.1ff" % SHIPPED_STEP,
          steps == [SHIPPED_STEP] * 5, steps)
    check("drag dead zone ships 12.0f",
          decode("f32", simspr.read(DRAG_DEADZONE_VA, 4)[0]) == 12.0)
    check("drag clamp ships 80.0f",
          decode("f32", simspr.read(DRAG_CLAMP_VA, 4)[0]) == 80.0)
    check("both drag divisors ship -2",
          all(decode("i8", simspr.read(va, 1)[0]) == -2 for va in DRAG_DIVISOR_VAS))
    check("eight edge displacements ship %s" % (EDGE_SHIPPED,),
          tuple(decode("i8", simspr.read(va, 1)[0]) for va in EDGE_MARGIN_VAS) == EDGE_SHIPPED)
    return ok, fail


# --- cli -------------------------------------------------------------------------------

def _split_spec(s):
    """'0x10067690:f32=0.0' -> (va, kind, value); value may be absent for --read."""
    lhs, _, value = s.partition("=")
    addr, _, kind = lhs.partition(":")
    return int(addr, 0), (kind or "hex"), (value if value != "" else None)


def cmd_info(path):
    p = Patcher(path)
    pe_off = struct.unpack_from("<I", p.d, 0x3C)[0]
    csum = struct.unpack_from("<I", p.d, pe_off + 24 + 64)[0]
    dllc = struct.unpack_from("<H", p.d, pe_off + 24 + 70)[0]
    print("%s\n  %d bytes\n  sha256 %s\n  image base 0x%08x" % (path, len(p.d), p.sha, p.pe.base))
    print("  OptionalHeader CheckSum 0x%08x  DllCharacteristics 0x%04x" % (csum, dllc))
    if csum:
        print("  NOTE: this image ships a NON-ZERO checksum. This tool does not recompute it; "
              "decide deliberately whether that matters for this target.")
    else:
        print("  (checksum is zero as shipped, so leaving it alone adds no diff and changes "
              "nothing the loader checks)")
    print("  sections (file offset == VA - base where 'raw' equals 'va-base'):")
    for name, vaddr, vsize, raddr, rsize in p.pe.sections:
        print("    %-8s va 0x%08x  va-base 0x%-7x raw 0x%-7x rsize 0x%-6x %s"
              % (name, p.pe.base + vaddr, vaddr, raddr, rsize,
                 "1:1" if vaddr == raddr else "shifted"))
    if p.sha == SIMSPR_SHA:
        print("  this IS the anchored SIMSPR.DLL -- camera recipes apply: %s"
              % ", ".join(sorted(RECIPES)))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    target, args = argv[1], argv[2:]

    if "--selftest" in args:
        print("pe_patch selftest on %s" % target)
        ok, fail = selftest(target)
        print("%d passed, %d failed" % (ok, fail))
        return 0 if fail == 0 else 1

    if "--info" in args:
        cmd_info(target)
        return 0

    if "--diff" in args:
        other = args[args.index("--diff") + 1]
        a = open(target, "rb").read()
        b = open(other, "rb").read()
        runs, total = diff(a, b)
        if runs is None:
            print("NOT COMPARABLE: %s" % total)
            return 1
        if not runs:
            print("identical: %d bytes, sha256 %s" % (len(a), hashlib.sha256(a).hexdigest()))
            return 0
        print("%d differing run(s), %d byte(s) total" % (len(runs), total))
        try:
            pe = PE(target)
            base = pe.base
        except ValueError:
            pe, base = None, 0
        for off, oa, ob in runs:
            va = ""
            if pe:
                for name, vaddr, vsize, raddr, rsize in pe.sections:
                    if raddr <= off < raddr + rsize:
                        va = "  VA 0x%08x [%s]" % (base + vaddr + (off - raddr), name)
                        break
            print("  off 0x%-8x %-24s -> %-24s%s" % (off, oa.hex(" "), ob.hex(" "), va))
        return 0

    p = Patcher(target)

    if "--read" in args:
        spec = args[args.index("--read") + 1]
        va, kind, _ = _split_spec(spec)
        n = 1
        if "-n" in args:
            n = int(args[args.index("-n") + 1], 0)
        width = 1 if kind == "hex" else CODECS[kind][1]
        for i in range(n):
            a = va + i * width
            buf, sec = p.read(a, width)
            off, _ = p.pe.off(a)
            print("0x%08x  off 0x%-6x %-7s %s" % (a, off, sec, show(kind, buf)))
        return 0

    staged = []
    for i, a in enumerate(args):
        if a == "--recipe":
            staged.append(apply_recipe(p, args[i + 1]))
        elif a == "--set":
            va, kind, value = _split_spec(args[i + 1])
            if value is None:
                raise PatchError("--set needs a value: --set 0x10067690:f32=0.0")
            expect = None
            # --expect immediately after this --set applies to it
            if i + 2 < len(args) and args[i + 2] == "--expect":
                expect = args[i + 3]
            p.stage(va, kind, value, expect=expect)
            staged.append("%s:%s=%s" % (hex(va), kind, value))

    if not p.patches:
        cmd_info(target)
        print("\nnothing staged. Use --set or --recipe (recipes: %s)"
              % ", ".join(sorted(RECIPES)))
        return 0

    print(p.report())
    if "--out" not in args:
        print("\nDRY RUN -- no --out given, nothing written.")
        return 0
    out = args[args.index("--out") + 1]
    blob = p.write(out)
    runs, total = diff(p.d, blob)
    print("\nwrote %s\n  %d bytes  sha256 %s" % (out, len(blob), hashlib.sha256(blob).hexdigest()))
    print("  differs from %s in %d run(s), %d byte(s) -- re-check with --diff before staging"
          % (os.path.basename(target), len(runs), total))
    print("  recipe/spec: %s" % ", ".join(staged))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except PatchError as e:
        print("REFUSED: %s" % e, file=sys.stderr)
        sys.exit(1)
