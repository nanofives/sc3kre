r"""Read or set a city save's building style (task stylemix). The scheme record {type 0x0525A6B9, group 0x4525A6E2,
instance 1}, 12 bytes = building set, flora set, landscape (SIMINIT FUN_10009e1f reads three u32 in that order and
calls cISC3CitySchemeMgr::SetCityScheme(landscape, flora, buildingSet, 0); without the record it uses the defaults
vt+0x24 / +0x4c / +0x68). The payload is stored uncompressed in every shipped save (size 12).
  py -3.12 stylemix_verify_setscheme.py <in.sc3>                     # print
  py -3.12 stylemix_verify_setscheme.py <in.sc3> <out.sc3> <set hex> # write a copy with the building set changed"""
import os
import struct, sys
def find(raw):
    pat = struct.pack("<II", 0x4525A6E2, 1)
    o = raw.find(pat)
    while o >= 0 and struct.unpack_from("<I", raw, o + 8)[0] != 0x0525A6B9:
        o = raw.find(pat, o + 1)
    if o < 0:
        raise SystemExit("no scheme record")
    off, size = struct.unpack_from("<II", raw, o + 12)
    if size != 12:
        raise SystemExit("scheme record size %d, expected 12" % size)
    return off
raw = bytearray(open(sys.argv[1], "rb").read())
off = find(raw)
print("building set %08x  flora %08x  landscape %08x" % struct.unpack_from("<3I", raw, off))
if len(sys.argv) > 3:
    struct.pack_into("<I", raw, off, int(sys.argv[3], 16))
    open(sys.argv[2], "wb").write(raw)
    print("wrote %s with building set %s" % (sys.argv[2], sys.argv[3]))
