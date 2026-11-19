#!/usr/bin/env python3
r"""sc3plugin.py - task plop (round 2026-11-19h): Maxis add-on plugins (.pin + .dat) for SimCity 3000 Unlimited.

SC3U still loads the 2000 plugin format natively (re/analysis/PLOPPABLES.md, verify/plop/RESULTS.md):

  where     every *.pin under <Apps>\PlugIn\ (any depth): SIMINIT cISC3PluginBuildingMgr::CheckForPluginBuildings
            0x1000ea2a, initialised by the scheme manager 0x1000583e with FS->PlugInDirectory() + "PlugIn\"
            (SC3U.exe cGZFileSystem::PlugInDirectory 0x00482532: [Directories] PlugIn= of Apps\SC3U.ini, default the
            Apps folder). Measured: the game opens Apps\PlugIn\LandmarkPack1\LandmarkPack1.dat
  [DBSegments]      key=0x80C381D7;%PluginDirectory%<sub>\<file>.dat  one DB segment (exemplars, names, frame tables)
  [SpriteSegments]  <sub>=addon-enabled                                 every *.DAT of Apps\Plugin\<sub>\ is a sprite
                                                                        segment (SIMINIT 0x1000eeef)
  [OccupantKeys]    0xTYPE,0xGROUP,0xINST=<label>                        registered as "sc3occattrib" (0x1000ee62)

What SC3U does NOT do is draw the 2000 art: a 1999 pixel record is format 1 with dword1 = 0x8000 and an LZO1X-1
stream, and SC3U's SIMSPR decoder only takes the QFS case (dword1 & 0x80000, sc3spr_decode_record 0x1001de49); the
0x8000 / 0xC000 cases of the raw dispatcher 0x1001e086 call a stub that returns 0 (0x1004efdd). The building is
placed and saved but shows a blank lot. So `convert_dat` rewrites those records: LZO1X-1 decode (the plaintext is the
same span block SC3U's QFS records hold: all 16 frames of the pack's Palace of Fine Arts decode byte-identical to
SC3U's stock 9510 frames) and the QFS encoder bldimport uses (qfs_encode.compress_stream quick 1).

1999 pixel record:  +0x00 0x107 (format 1)  +0x04 0x8000  +0x08 w  +0x0C h  +0x10 decoded length
                    +0x14 len(record) - 0x10  +0x18 LZO1X-1 stream ending in the M4 end marker 11 00 00
SC3U record:        +0x00 0x107  +0x04 0x80000  +0x08 w  +0x0C h  +0x10 len(stream) + 4  +0x14 QFS stream (10 FB)

  py -3.12 re/tools/bldimport/sc3plugin.py convert <in.dat> <out.dat>     1999 records -> SC3U records
  py -3.12 re/tools/bldimport/sc3plugin.py info <in.dat>                  record census
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)

import batgrow as BG        # noqa: E402  IXF container helpers
import qfs_encode           # noqa: E402

D1_1999 = 0x8000
D1_QFS = 0x80000


class PluginError(Exception):
    pass


def lzo1x_decompress(src):
    """LZO1X-1 (lzo1x_d.ch, the safe decoder's rules) -> (bytes, bytes used). Raises PluginError on a bad stream."""
    out = bytearray()
    ip = 0
    n = len(src)

    def need(k):
        if ip + k > n:
            raise PluginError("LZO stream ends early")

    def ext(t, base):
        nonlocal ip
        if t == 0:
            need(1)
            while src[ip] == 0:
                t += 255
                ip += 1
                need(1)
            t += base + src[ip]
            ip += 1
        return t

    def lits(k):
        nonlocal ip
        need(k)
        out.extend(src[ip:ip + k])
        ip += k

    def copy(dist, k):
        p = len(out) - dist
        if p < 0:
            raise PluginError("LZO match before the start of the output")
        for j in range(k):
            out.append(out[p + j])

    need(1)
    t = src[ip]
    state = "loop"
    if t > 17:
        ip += 1
        t -= 17
        lits(t)
        if t < 4:
            need(1)
            t = src[ip]
            ip += 1
            state = "match"
        else:
            state = "first"
    while True:
        if state == "loop":
            need(1)
            t = src[ip]
            ip += 1
            if t >= 16:
                state = "match"
                continue
            t = ext(t, 15)
            lits(t + 3)
            state = "first"
        if state == "first":
            need(1)
            t = src[ip]
            ip += 1
            if t >= 16:
                state = "match"
                continue
            need(1)
            dist = 1 + 0x800 + (t >> 2) + (src[ip] << 2)
            ip += 1
            copy(dist, 3)
            state = "done"
        if state == "match":
            if t >= 64:
                need(1)
                dist = 1 + ((t >> 2) & 7) + (src[ip] << 3)
                ip += 1
                k = (t >> 5) + 1
            elif t >= 32:
                t = ext(t & 31, 31)
                need(2)
                dist = 1 + (src[ip] >> 2) + (src[ip + 1] << 6)
                ip += 2
                k = t + 2
            elif t >= 16:
                hi = (t & 8) << 11
                t = ext(t & 7, 7)
                need(2)
                d = (src[ip] >> 2) + (src[ip + 1] << 6)
                ip += 2
                if hi == 0 and d == 0:
                    return bytes(out), ip
                dist = hi + d + 0x4000
                k = t + 2
            else:
                need(1)
                dist = 1 + (t >> 2) + (src[ip] << 2)
                ip += 1
                k = 2
            copy(dist, k)
            state = "done"
        if state == "done":
            t = src[ip - 2] & 3
            if t == 0:
                state = "loop"
                continue
            lits(t)
            need(1)
            t = src[ip]
            ip += 1
            state = "match"


def is_1999_record(p):
    return len(p) >= 0x18 and (struct.unpack_from("<I", p, 0)[0] >> 8) & 0xFF == 1 and \
        struct.unpack_from("<I", p, 4)[0] == D1_1999


def convert_record(p):
    """A 1999 pixel record -> the SC3U QFS record of the same pixels."""
    d0, d1, d2, d3, d4, clen = struct.unpack_from("<6I", p, 0)
    if clen != len(p) - 0x10:
        raise PluginError("1999 record length field %d, record %d bytes" % (clen, len(p)))
    block, used = lzo1x_decompress(p[0x18:])
    if len(block) != d4 or used != len(p) - 0x18:
        raise PluginError("LZO stream decoded to %d bytes (header says %d), used %d of %d" % (
            len(block), d4, used, len(p) - 0x18))
    if len(block) < 4 or struct.unpack_from("<I", block, 0)[0] != d4:
        raise PluginError("decoded block does not start with its own length")
    stream = qfs_encode.compress_stream(block, quick=1)
    return struct.pack("<5I", d0, D1_QFS, d2, d3, len(stream) + 4) + bytes(stream)


def convert_dat(d):
    """-> (new container bytes, number of records converted). Every other record is kept byte for byte, in order."""
    idx, order = BG.records(d)
    recs, n = [], 0
    for g, i, t in order:
        p = idx[(g, i, t)]
        if t == 0 and is_1999_record(p):
            p = convert_record(p)
            n += 1
        recs.append((g, i, t, p))
    return (BG.new_container(recs) if n else d), n


def main(argv):
    if len(argv) >= 2 and argv[0] == "info":
        idx, order = BG.records(open(argv[1], "rb").read())
        c = {}
        for g, i, t in order:
            k = (t, "1999" if t == 0 and is_1999_record(idx[(g, i, t)]) else "")
            c[k] = c.get(k, 0) + 1
        for (t, w), v in sorted(c.items()):
            print("type 0x%08X %s: %d" % (t, w, v))
        return 0
    if len(argv) == 3 and argv[0] == "convert":
        out, n = convert_dat(open(argv[1], "rb").read())
        with open(argv[2], "wb") as fh:
            fh.write(out)
        print("%d record(s) converted -> %s" % (n, argv[2]))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
