#!/usr/bin/env python3
r"""sc3pack_testpacks.py - task sc3compat-b (2026-11-19e): the three local test packs for sc3pack.py / sc3pack.js.

  py -3.12 re/tools/bldimport/webtest/sc3pack_testpacks.py --game <game tree> --batpatch <1999 .bld folder>
         --addons <maxis_addons_2000 folder> --out <stage\st_packs\testpacks>

They are made from EA files (the game's .bld, its Apps\BACustom parts, the Maxis 1999 patch and add-on packs), so
they stay on this PC: --out must be outside the repo (stage\ is gitignored).

  plain_bld.zip    3 shipped .bld (version 8) + 2 from the 1999 patch (version 7), deflate
  bld_parts.zip    "sc3pt Test Plant.bld" = Trash & Burn with 9 part names changed and those images stripped, plus
                   parts copied from the game's BACustom under new names (Details\, Props\, loose), one written from
                   the .bld's own embedded image, one same-named as a game file with other bytes (a conflict), one
                   duplicate, one missing, one loose image no .bld uses, a prop .met naming the renamed bmps, a readme
  nested.zip       readme + SETUP.INI + an unknown file + LandmarkPack2 .dat/.pin + a broken .zip + macOS metadata +
                   inner.zip (2 .bld) holding deeper.zip (1 .bld)
"""
import argparse
import io
import os
import struct
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import bldfile as B          # noqa: E402

MAGIC, SEP = 0x80C381D7, 0xEAEAEAEA


def records(b):
    out, o = [], 4
    while True:
        g, i, t, off, sz = struct.unpack_from("<5I", b, o)
        o += 20
        if (g, i, t) == (0, 0, 0):
            return out
        out.append([(g, i, t), b[off:off + sz]])


def ixf(recs):
    head = 4 + 20 * (len(recs) + 1)
    idx, data, off = [], [], head
    for k, p in recs:
        idx.append(struct.pack("<5I", k[0], k[1], k[2], off, len(p)))
        data.append(p)
        off += len(p)
    return struct.pack("<I", MAGIC) + b"".join(idx) + b"\0" * 20 + b"".join(data)


def rename_model(p, ren):
    n = p[2]
    o = 0x21 + n * n * 4
    o += 8 + struct.unpack_from("<I", p, o + 4)[0]
    cnt = struct.unpack_from("<I", p, o + 4)[0]
    head, o = p[:o + 8], o + 8
    lst = []
    for _ in range(cnt):
        ln = struct.unpack_from("<I", p, o)[0]
        nm = p[o + 4:o + 4 + ln].decode("cp1252")
        h = p[o + 4 + ln:o + 8 + ln]
        new = ren.get(nm.lower(), nm).encode("cp1252")
        lst.append(struct.pack("<I", len(new)) + new + h)
        o += 8 + ln
    return head + b"".join(lst) + p[o:]


def rename_texinfo(p, ren):
    n = struct.unpack_from("<I", p, 57)[0]
    nm = p[61:61 + n].decode("cp1252")
    new = ren.get(nm.lower(), nm).encode("cp1252")
    return p[:57] + struct.pack("<I", len(new)) + new + p[61 + n:], nm.lower()


def tga32(im):
    w, h = im.size
    raw = im.convert("RGBA").tobytes()
    bgra = bytearray(len(raw))
    bgra[0::4], bgra[1::4], bgra[2::4], bgra[3::4] = raw[2::4], raw[1::4], raw[0::4], raw[3::4]
    return struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, w, h, 32, 0x28) + bytes(bgra)


def zbytes(entries, method=zipfile.ZIP_DEFLATED):
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", method) as z:
        for name, data in entries:
            z.writestr(zipfile.ZipInfo(name, (2000, 1, 1, 0, 0, 0)), data, compress_type=method)
    return bio.getvalue()


def rd(p):
    with open(p, "rb") as fh:
        return fh.read()


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--batpatch", required=True)
    ap.add_argument("--addons", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    bld = os.path.join(a.game, "Buildings")
    cus = os.path.join(a.game, "Apps", "BACustom")

    # 1. plain .bld zip
    plain = [(n, rd(os.path.join(bld, n))) for n in ("Dupont House.bld", "HiTech Lab.bld", "Longview Park.bld")]
    plain += [(n, rd(os.path.join(a.batpatch, n))) for n in ("Castle.bld", "Licks.bld")]
    with open(os.path.join(a.out, "plain_bld.zip"), "wb") as fh:
        fh.write(zbytes(plain))

    # 2. .bld + parts
    src = os.path.join(bld, "Trash & Burn.bld")
    ren = {"blue_t55.tga": "sc3pt blue paint.tga", "bourbon 03.tga": "sc3pt bourbon 03.tga",
           "blue line 09.tga": "Mariners 04.tga", "blue_276.tga": "sc3pt missing.tga",
           "blue line 10.tga": "sc3pt hardware-13.tga"}
    for k in range(4):
        ren["stair3 %d.bmp" % k] = "sc3pt arcade1 %d.bmp" % k
    custom = {c["name"].lower(): c for c in B.custom_textures(src)}
    paint_img = tga32(B.embedded_image(src, custom["blue_t55.tga"]))
    strip = {tuple(c["image_key"]) for n, c in custom.items() if n in ren}
    recs = []
    for k, p in records(rd(src)):
        if k in strip:
            continue
        if k[2] == B.T_MODEL:
            p = rename_model(p, ren)
        elif k[2] == B.T_TEXINFO:
            p, _old = rename_texinfo(p, ren)
        elif k[2] == B.T_INFO:
            nm = b"sc3pt Test Plant"
            n0 = p[1]
            p = p[:1] + bytes([len(nm)]) + nm + p[2 + n0:]
        recs.append([k, p])
    test_bld = ixf(recs)
    conflict = bytearray(rd(os.path.join(cus, "Details", "Mariners 04.tga")))
    conflict[-1] ^= 0xFF
    bourbon = rd(os.path.join(cus, "Details", "bourbon 03.TGA"))
    met = "".join('%s:%s\r\n' % (h, ",".join('"sc3pt arcade1 %d.bmp"' % ((k + r) % 4) for k in range(4)))
                  for r, h in enumerate(("1,3,3", "3,1,3", "1,3,3", "3,1,3")))
    parts = [("sc3pt Test Plant.bld", test_bld),
             ("Readme sc3pt.txt", b"sc3pack test pack: parts renamed from the game's BACustom.\r\n"),
             ("BACustom/Paints/sc3pt blue paint.tga", paint_img),
             ("BACustom/Details/sc3pt bourbon 03.tga", bourbon),
             ("BACustom/Details/Mariners 04.tga", bytes(conflict)),
             ("copy/sc3pt bourbon 03.tga", bourbon),
             ("sc3pt hardware-13.tga", rd(os.path.join(cus, "Details", "hardware-13.TGA"))),
             ("sc3pt loose.tga", rd(os.path.join(cus, "Details", "sunlight 13.TGA"))),
             ("sc3pt arcade1x3x3.met", met.encode())]
    parts += [("BACustom/Props/sc3pt arcade1 %d.bmp" % k, rd(os.path.join(cus, "Props", "arcade1 %d.bmp" % k)))
              for k in range(4)]
    with open(os.path.join(a.out, "bld_parts.zip"), "wb") as fh:
        fh.write(zbytes(parts))

    # 3. nested
    deeper = zbytes([("Wren's House.bld", rd(os.path.join(a.batpatch, "Wren's House.bld")))], zipfile.ZIP_STORED)
    inner = zbytes([("Buildings/Hotel Splash.bld", rd(os.path.join(bld, "Hotel Splash.bld"))),
                    ("Buildings/Castle.bld", rd(os.path.join(a.batpatch, "Castle.bld"))),
                    ("more/deeper.zip", deeper)])
    lp = os.path.join(a.addons, "landmarkpack2", "disk1")
    nested = [("README.TXT", b"nested test pack\r\n"),
              ("inner.zip", inner),
              ("LandmarkPack2/LandmarkPack2.dat", rd(os.path.join(lp, "data", "LandmarkPack2.dat"))),
              ("LandmarkPack2/LandmarkPack2.pin", rd(os.path.join(lp, "data", "LandmarkPack2.pin"))),
              ("SETUP.INI", rd(os.path.join(lp, "SETUP.INI"))),
              ("notes.xyz", b"\x00\x01unknown"),
              ("bad.zip", b"PK\x03\x04 this is not a zip"),
              ("__MACOSX/._Castle.bld", b"\x00\x05\x16\x07mac")]
    with open(os.path.join(a.out, "nested.zip"), "wb") as fh:
        fh.write(zbytes(nested))
    for n in ("plain_bld.zip", "bld_parts.zip", "nested.zip"):
        print("wrote %s (%d bytes)" % (os.path.join(a.out, n), os.path.getsize(os.path.join(a.out, n))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
