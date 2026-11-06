#!/usr/bin/env python3
"""community_bundle.py - build the release's community\\ folder: the thronevintagetech mods (used with the author's
permission, re/analysis/COMMUNITY_MODS.md) plus install_data.json for community_patch.ps1.

Players have PowerShell, not Python, so the edits civicdeals_patch.py and apache_patch.py make are written out here as
plain data and applied by re/scripts/community_patch.ps1 on the player's own files:
  - files to copy into the game (the authors' DLLs, our Apache build, the Apache sprites)
  - SYS.PAK line inserts (PetitionerExtraInfo.ini 0xD9 / 0xDA / 0xDB = 19,2; NumberOfPetitionerMessages 212 like the author)
  - petitioner IXF records 0xD9 / 0xDA / 0xDB, English and Spanish text (Spanish goes to a Spanish ENGLISH folder)
  - in-place Spanish strings for SC3KCivicDeals.dll (offset, original, new, all checked by the installer)
No EA file or EA text goes into the bundle: the IXF records are the authors' and our texts only.

usage: py -3.12 re/tools/community_bundle.py <Civic Deals package dir> <Apache package dir> <our Apache build dir> <out dir>
"""
import base64
import json
import os
import shutil
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apache_patch as ap  # noqa: E402
import civicdeals_patch as cd  # noqa: E402


def b64(b):
    return base64.b64encode(b).decode("ascii")


def find(root, leaf):
    for r, _d, files in os.walk(root):
        if leaf in files:
            return os.path.join(r, leaf)
    raise SystemExit(f"{leaf} not found under {root}")


def main(argv):
    if len(argv) != 4:
        print(__doc__)
        return 2
    cdpkg, appkg, apbuild, out = argv
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, "Apps", "Res", "Sprites"))
    files = []
    for leaf in ("SC3KCivicDeals.dll", "SC3KExtraCheats.dll"):
        shutil.copy2(find(cdpkg, leaf), os.path.join(out, "Apps", leaf))
        files.append(f"Apps/{leaf}")
    shutil.copy2(os.path.join(apbuild, "SC3KUApacheFlyover.dll"), os.path.join(out, "Apps", "SC3KUApacheFlyover.dll"))
    files.append("Apps/SC3KUApacheFlyover.dll")
    for ext in ("DAT", "IXF", "SII"):
        leaf = f"SC3KU_ApacheFlyover.{ext}"
        shutil.copy2(find(appkg, leaf), os.path.join(out, "Apps", "Res", "Sprites", leaf))
        files.append(f"Apps/Res/Sprites/{leaf}")
    for leaf in ("LICENSE.txt", "README.txt"):   # the Apache author's notices go with the DLL
        shutil.copy2(find(appkg, leaf), os.path.join(out, f"Apache-{leaf}"))
    relink = os.path.join(os.path.dirname(apbuild), "Source", "RELINK-LGPL.txt")   # our build links the LGPL SDK
    if os.path.exists(relink):
        shutil.copy2(relink, os.path.join(out, "Apache-RELINK-LGPL.txt"))
    for p in ("LICENSE-sc3k-extra-cheats.txt", "LEGAL-NOTICE.txt", "THIRD-PARTY-NOTICES.txt"):
        try:
            shutil.copy2(find(cdpkg, p), os.path.join(out, f"CivicDeals-{p}"))
        except SystemExit:
            pass

    # IXF records: the author's English for D9 / DA, our Spanish; ours for DB in both
    src_en = os.path.dirname(find(cdpkg, "Sc3StringsPetitionerHeading.IXF"))
    ixf = []
    for f in cd.FILES:
        _d, recs, t = cd.ixf_texts(os.path.join(src_en, f"Sc3StringsPetitioner{f}.IXF"))
        group = recs[0]["group"]
        for inst in (0xD9, 0xDA):
            ixf.append({"file": f"Sc3StringsPetitioner{f}.IXF", "group": group, "instance": inst,
                        "en": b64(t[inst]), "es": b64(cd.ES_IXF[(f, inst)].encode("cp1252"))})
        ixf.append({"file": f"Sc3StringsPetitioner{f}.IXF", "group": group, "instance": ap.ID,
                    "en": b64(ap.TEXT["en"][f].encode("cp1252")), "es": b64(ap.TEXT["es"][f].encode("cp1252"))})

    # Spanish strings for the Civic Deals DLL, with the slot each one must fit
    dll = open(find(cdpkg, "SC3KCivicDeals.dll"), "rb").read()
    edits = []
    for off, (en, es) in sorted(cd.ES_DLL.items()):
        enc = es.encode("cp1252")
        if dll[off:off + len(en)] != en.encode("cp1252"):
            raise SystemExit(f"0x{off:x}: not '{en[:30]}'")
        z = dll.index(0, off)
        while z < len(dll) and dll[z] == 0:
            z += 1
        slot = z - off - 1
        if len(enc) > slot:
            raise SystemExit(f"0x{off:x}: {len(enc)} > slot {slot}")
        old = dll[off:off + slot + 1]
        edits.append({"off": off, "old": b64(old), "new": b64(enc + b"\0" * (slot + 1 - len(enc)))})

    data = {
        "version": 1,
        "files": files,
        "syspak": [
            {"member": "PetitionerExtraInfo.ini", "after": "0x000000D8=5,6", "insert": ["0x000000D9=19,2", "0x000000DA=19,2"]},
            {"member": "PetitionerExtraInfo.ini", "after": "0x000000DA=19,2", "insert": ["0x000000DB=19,2"]},
            {"member": "PetitionerManager.ini", "replace": "NumberOfPetitionerMessages=210", "with": "NumberOfPetitionerMessages=212"},
        ],
        "ixf": ixf,
        "dll_es": {"file": "Apps/SC3KCivicDeals.dll", "edits": edits},
    }
    with open(os.path.join(out, "install_data.json"), "w", encoding="ascii") as fh:
        json.dump(data, fh, indent=1)
    print(f"{out}: {len(files)} files, {len(ixf)} IXF records, {len(edits)} DLL strings")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
