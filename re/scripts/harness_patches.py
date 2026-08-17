#!/usr/bin/env python3
"""
harness_patches.py - versioned baseline for every in-memory patch the launch
harness (re/harness/sc3probe.dll) applies, plus a DRY-RUN verifier that checks
each patch site against the on-disk binaries WITHOUT launching the game.

Why this exists
---------------
The probe source lives in gitignored re/harness/src, so there is no committed
reference for the byte patches it installs. If a game update, a wrong build, or
an anchor drift changes the bytes at a patch site, the probe would either patch
the wrong thing or silently no-op (it verifies original bytes and skips on
mismatch - reading as "feature off", not "error"). This manifest makes those
sites explicit and independently checkable:

    py -3 re/scripts/harness_patches.py            # verify all sites, PASS/FAIL
    py -3 re/scripts/harness_patches.py --list     # print the manifest

Exit code 0 = every site matches its expected pre-patch bytes AND the SC3U
anchor SHA matches. Non-zero = at least one mismatch (a real HARNESS-FAIL: the
probe's patches cannot be trusted on this binary).

Addresses are image VAs; image base is read from each PE. Bytes are the ORIGINAL
(pre-patch) sequence the probe checks before patching - so a match here means the
patch will apply cleanly.
"""
import struct, hashlib, sys, os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
APPS = os.path.join(ROOT, "Apps")

# SC3U.exe anchor (CLAUDE.md). If this differs, every RVA is invalid.
SC3U_SHA256 = "49dd55e183c68dffe6ac57e85a91ef3b3e79c45a9d137edfcbb3840026349dc7"

# module -> on-disk path
MODULES = {
    "SC3U.exe":      os.path.join(APPS, "SC3U.exe"),
    "GZGraphicD.dll": os.path.join(APPS, "GZGraphicD.dll"),
}

# One row per patch site. orig = expected pre-patch bytes (what the probe checks).
MANIFEST = [
    {
        "name": "windowed_flag",
        "module": "GZGraphicD.dll", "va": 0x1006CDAC,
        "orig": [0x00], "runtime": True,
        "switch": "-windowed",
        "note": "Init windowed-mode flag, 0 -> 1. Runtime data (zero-init BSS), not a "
                "file byte; verified as an address-in-range sanity check only.",
    },
    {
        "name": "windowed_no_refullscreen",
        "module": "GZGraphicD.dll", "va": 0x100117D6,
        "orig": [0xC6, 0x43, 0x48, 0x01],   # mov byte [ebx+0x48], 1
        "switch": "-windowed",
        "note": "'mov [ebx+0x48],1' -> nop x4 so 16bpp is not re-forced to fullscreen.",
    },
    {
        "name": "fix16_surface_format",
        "module": "GZGraphicD.dll", "va": 0x10019349,
        "orig": [0xF6, 0xDB, 0x1B, 0xDB, 0x81, 0xE3, 0xC0, 0x0F, 0x00, 0x00],
        "switch": "-fix16",
        "note": "U-040 merge point in FUN_10019273; stolen for the injected 16bpp branch.",
    },
    {
        "name": "nointro_movie_start",
        "module": "SC3U.exe", "va": 0x00429F78,
        "orig": [0xE8, 0x18, 0x00, 0x00, 0x00],   # call FUN_00429f95
        "switch": "-nointro",
        "note": "movie-start call in FUN_00429f54 -> 'xor al,al'+nop so the boot advances.",
    },
]


def _sections(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe+4] != b"PE\0\0":
        raise ValueError("not a PE")
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    optsz = struct.unpack_from("<H", data, pe + 20)[0]
    imgbase = struct.unpack_from("<I", data, pe + 24 + 28)[0]
    sect = pe + 24 + optsz
    secs = []
    for i in range(nsec):
        o = sect + i * 40
        secs.append((
            struct.unpack_from("<I", data, o + 8)[0],   # vsize
            struct.unpack_from("<I", data, o + 12)[0],   # vaddr
            struct.unpack_from("<I", data, o + 16)[0],   # rawsize
            struct.unpack_from("<I", data, o + 20)[0],   # rawoff
        ))
    return imgbase, secs


def _va_to_off(imgbase, secs, va):
    rva = va - imgbase
    for vsize, vaddr, rawsize, rawoff in secs:
        if vaddr <= rva < vaddr + max(vsize, rawsize):
            return rawoff + (rva - vaddr)
    raise ValueError("VA 0x%08X not in any section" % va)


def verify():
    fails = 0
    # anchor check first - if the exe is not the anchored build, RVAs are meaningless.
    p = MODULES["SC3U.exe"]
    if not os.path.exists(p):
        print("HARNESS-FAIL: SC3U.exe not found at %s" % p)
        return 2
    sha = hashlib.sha256(open(p, "rb").read()).hexdigest()
    if sha == SC3U_SHA256:
        print("PASS  anchor    SC3U.exe SHA-256 matches")
    else:
        print("FAIL  anchor    SC3U.exe SHA-256 %s != anchor %s" % (sha, SC3U_SHA256))
        print("HARNESS-FAIL: wrong SC3U build; every patch RVA is invalid. Aborting.")
        return 2

    cache = {}
    for m in MANIFEST:
        path = MODULES[m["module"]]
        if path not in cache:
            data = open(path, "rb").read()
            cache[path] = (data,) + _sections(data)
        data, imgbase, secs = cache[path]
        # runtime sites live in zero-init/virtual regions with no backing file bytes:
        # confirm the VA is within the module's virtual range, but do not byte-compare.
        if m.get("runtime"):
            rva = m["va"] - imgbase
            in_range = any(vaddr <= rva < vaddr + max(vsize, rawsize)
                           for vsize, vaddr, rawsize, rawoff in secs)
            print("%s  %-24s %s @0x%08X  [%s]  (runtime flag, not byte-checked)" % (
                "PASS" if in_range else "FAIL", m["name"], m["module"], m["va"], m["switch"]))
            if not in_range:
                fails += 1
            continue
        try:
            off = _va_to_off(imgbase, secs, m["va"])
            got = list(data[off:off + len(m["orig"])])
        except ValueError as e:
            print("FAIL  %-24s %s" % (m["name"], e))
            fails += 1
            continue
        ok = got == m["orig"]
        exp_s = " ".join("%02X" % b for b in m["orig"])
        got_s = " ".join("%02X" % b for b in got)
        print("%s  %-24s %s @0x%08X  [%s]%s" % (
            "PASS" if ok else "FAIL", m["name"], m["module"], m["va"],
            m["switch"], "" if ok else "  expected %s got %s" % (exp_s, got_s)))
        if not ok:
            fails += 1

    if fails:
        print("\nHARNESS-FAIL: %d patch site(s) do not match; probe patches are unreliable." % fails)
    else:
        print("\nOK: all %d patch sites match their expected pre-patch bytes." % len(MANIFEST))
    return 1 if fails else 0


def show():
    for m in MANIFEST:
        print("%-24s %-16s @0x%08X  %-11s  %s" % (
            m["name"], m["module"], m["va"], m["switch"],
            " ".join("%02X" % b for b in m["orig"])))


if __name__ == "__main__":
    if "--list" in sys.argv:
        show()
    else:
        sys.exit(verify())
