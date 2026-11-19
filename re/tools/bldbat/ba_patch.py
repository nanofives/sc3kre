#!/usr/bin/env python3
r"""ba_patch.py - task bldbat (2026-11-18): build bawinonly.dll and a BaappW.exe that imports it, in a dev tree.

  py -3.12 re/tools/bldbat/ba_patch.py --tree dev\bldbat\tree [--src re\harness\src] [--no-build]

Writes <tree>\Apps\bawinonly.dll and <tree>\Apps\BaappW.exe (a NEW file: Baapp.exe in a test tree is a hard link into
the release stage and is never written). BaappW.exe = the stock Baapp.exe (SHA-256 below) plus one section `.bawin`
holding a copy of the import directory with one more descriptor (bawinonly.dll!bawinonly_state). No code changes.
"""
import argparse
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import tempfile

BAAPP_SHA = "1829cbe2df17cc67c07bf5da8ed4aa3b3d9f6ca7f51bd9ee5a233b7bb7a57b5e"   # GOG Apps\Baapp.exe, 647,168 bytes
DLL, EXPORT, SECNAME = b"bawinonly.dll", b"bawinonly_state", b".bawin"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))


def align(v, a):
    return (v + a - 1) & ~(a - 1)


def add_import(b):
    b = bytearray(b)
    lf = struct.unpack_from("<I", b, 0x3C)[0]
    nsec, = struct.unpack_from("<H", b, lf + 6)
    optsz, = struct.unpack_from("<H", b, lf + 20)
    opt = lf + 24
    if struct.unpack_from("<H", b, opt)[0] != 0x10B:
        raise SystemExit("not PE32")
    sec_align, file_align = struct.unpack_from("<II", b, opt + 32)
    size_image, size_hdrs = struct.unpack_from("<I", b, opt + 56)[0], struct.unpack_from("<I", b, opt + 60)[0]
    imp_rva, imp_size = struct.unpack_from("<II", b, opt + 96 + 8)
    st = opt + optsz
    secs = [struct.unpack_from("<8sIIIIIIHHI", b, st + 40 * i) for i in range(nsec)]
    if any(s[0].rstrip(b"\0") == SECNAME for s in secs):
        raise SystemExit("already patched")
    if st + 40 * (nsec + 1) > size_hdrs:
        raise SystemExit("no room for a section header")

    def rva2off(rva):
        for s in secs:
            if s[2] <= rva < s[2] + max(s[1], s[3]):
                return rva - s[2] + s[4]
        raise SystemExit("rva %x in no section" % rva)

    o = rva2off(imp_rva)
    descs = []
    while True:
        d = bytes(b[o:o + 20])
        if d == b"\0" * 20:
            break
        descs.append(d)
        o += 20
    new_rva = align(size_image, sec_align)
    nd = len(descs) + 2
    dsz = 20 * nd
    ilt = dsz
    iat = ilt + 8
    ibn = iat + 8
    name = ibn + 2 + len(EXPORT) + 1
    name += name & 1
    blob = bytearray(name + len(DLL) + 1)
    for i, d in enumerate(descs):
        blob[20 * i:20 * i + 20] = d
    struct.pack_into("<5I", blob, 20 * len(descs), new_rva + ilt, 0, 0, new_rva + name, new_rva + iat)
    struct.pack_into("<I", blob, ilt, new_rva + ibn)
    struct.pack_into("<I", blob, iat, new_rva + ibn)
    blob[ibn + 2:ibn + 2 + len(EXPORT)] = EXPORT
    blob[name:name + len(DLL)] = DLL
    raw_size = align(len(blob), file_align)
    raw_off = align(len(b), file_align)
    b += b"\0" * (raw_off - len(b))
    b += blob + b"\0" * (raw_size - len(blob))
    hdr = struct.pack("<8sIIIIIIHHI", SECNAME, len(blob), new_rva, raw_size, raw_off, 0, 0, 0, 0, 0xC0000040)
    b[st + 40 * nsec:st + 40 * nsec + 40] = hdr
    struct.pack_into("<H", b, lf + 6, nsec + 1)
    struct.pack_into("<I", b, opt + 56, align(new_rva + len(blob), sec_align))
    struct.pack_into("<II", b, opt + 96 + 8, new_rva, dsz)
    struct.pack_into("<II", b, opt + 96 + 11 * 8, 0, 0)      # no bound imports (0 in stock already)
    struct.pack_into("<I", b, opt + 64, 0)                     # checksum (not checked for exes)
    return bytes(b)


def build_dll(src, out_dir):
    """re/scripts/build_mod.ps1 -Mod bawinonly (same cl flags, plus the VERSIONINFO resource every shipped DLL carries,
    AVVERSION) into a temp folder, then copied (delete first: never write through a hard link)."""
    obj = tempfile.mkdtemp(prefix="bawin_")
    script = os.path.join(REPO, "re", "scripts", "build_mod.ps1")
    r = subprocess.run(["pwsh", "-NoProfile", "-File", script, "-Mod", "bawinonly", "-Src", src, "-Out", obj])
    if r.returncode:
        raise SystemExit("build failed")
    out = os.path.join(obj, "bawinonly.dll")
    dst = os.path.join(out_dir, "bawinonly.dll")
    if os.path.exists(dst):
        os.remove(dst)
    shutil.copyfile(out, dst)
    shutil.rmtree(obj, ignore_errors=True)
    print("built %s (%d bytes)" % (dst, os.path.getsize(dst)))


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tree", required=True)
    ap.add_argument("--src", default=os.path.join(REPO, "re", "harness", "src"))
    ap.add_argument("--no-build", action="store_true")
    a = ap.parse_args(argv)
    apps = os.path.join(a.tree, "Apps")
    src_exe = os.path.join(apps, "Baapp.exe")
    with open(src_exe, "rb") as fh:
        b = fh.read()
    h = hashlib.sha256(b).hexdigest()
    if h != BAAPP_SHA:
        raise SystemExit("Baapp.exe %s is not the known stock build %s" % (h, BAAPP_SHA))
    if not a.no_build:
        build_dll(a.src, apps)
    out = os.path.join(apps, "BaappW.exe")
    if os.path.exists(out):
        os.remove(out)          # never write through a link
    with open(out, "wb") as fh:
        fh.write(add_import(b))
    print("wrote %s (imports %s)" % (out, DLL.decode()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
