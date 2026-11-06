#!/usr/bin/env python3
"""apache_patch.py - install Apache Flyover (our build) and its Reunirse petition 0xDB on the player's own files.

Apache Flyover v0.9 RC1 (thronevintagetech, MIT, with the author's permission; re/analysis/COMMUNITY_MODS.md), source and
our changes in re/community/apache. This copies the DLL and the author's three sprite files, and adds the petition data
the DLL's petition needs, the way civicdeals_patch.py does for D9 / DA:

  Sys\\SYS.PAK                     PetitionerExtraInfo.ini + 0x000000DB=19,2 (portrait 19, advisor slot 2, as D7 / D9)
  Res\\Text\\<lang>\\Sc3StringsPetitioner{Heading,Advice,Button1,Button2,Reaction1,Reaction2}.IXF   record 0xDB
                                  (Spanish in a Spanish ENGLISH folder, English elsewhere)

The DLL itself sets the petitioner name, window title, message, buttons and reactions at run time (Spanish when
sc3mods.dll reports "es"). Backups <file>.civicdeals-orig once; --restore of civicdeals_patch.py puts the text files back.

usage: py -3.12 re/tools/apache_patch.py <dir with SC3KUApacheFlyover.dll> <dir with the 3 SC3KU_ApacheFlyover sprites> <game dir>
"""
import os
import shutil
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import civicdeals_patch as cd  # noqa: E402
import syspak_parse  # noqa: E402

ID = 0xDB
TEXT = {
    "es": {
        "Heading": "Patrulla aérea de la base militar",
        "Advice": "Una patrulla aérea no baja la delincuencia por sí sola, Alcalde, pero se nota. Los vecinos de "
                  "%YOURCITY% verán helicópteros sobre sus casas durante unos minutos. No cuesta nada a la ciudad.",
        "Button1": "Autorizar la patrulla",
        "Button2": "Rechazar la oferta",
        "Reaction1": "Los helicópteros despegan ahora, Alcalde. Vigilaremos la ciudad desde el aire.",
        "Reaction2": "Entendido, Alcalde. La base sigue a su disposición si cambia de idea.",
    },
    "en": {
        "Heading": "Military base air patrol",
        "Advice": "An air patrol will not lower crime by itself, Mayor, but people will notice. Residents of %YOURCITY% "
                  "will see helicopters over their homes for a few minutes. It costs the city nothing.",
        "Button1": "Authorize the patrol",
        "Button2": "Decline the offer",
        "Reaction1": "The helicopters are taking off now, Mayor. We will watch the city from the air.",
        "Reaction2": "Understood, Mayor. The base remains at your service if you change your mind.",
    },
}


def patch_syspak(path):
    data = open(path, "rb").read()
    names, _o, _t, recs = syspak_parse.parse(data)
    lines = [list(r["lines"]) for r in recs]
    ei = [n.lower() for n in names].index("petitionerextrainfo.ini")
    if "0x000000DB=19,2" in lines[ei]:
        return "already patched"
    anchor = "0x000000DA=19,2" if "0x000000DA=19,2" in lines[ei] else "0x000000D8=5,6"
    k = lines[ei].index(anchor)
    lines[ei].insert(k + 1, "0x000000DB=19,2")
    out = syspak_parse.build(names, lines)
    n2, _o, _t, r2 = syspak_parse.parse(out)
    assert n2 == names and [n for n, a, b in zip(n2, recs, r2) if a["lines"] != b["lines"]] == [names[ei]]
    cd.write_new(path, out, False)
    return "0xDB added"


def ixf_add_one(path, group, text):
    d, recs, texts = cd.ixf_texts(path)
    if ID in texts:
        return "already has 0xDB"
    slots = cd.ixf_parse.read_index_slots(d)
    term = 4 + (len(slots) - 1) * 20
    first = min(s[3] for s in slots if s[3] not in (0, 0xFFFFFFFF))
    if term + 40 > first or any(d[term:term + 40]):
        raise SystemExit(f"{path}: no spare index slot")
    excl = struct.unpack_from("<I", d, recs[0]["offset"])[0] == recs[0]["size"]
    out = bytearray(d)
    off = len(out)
    out += struct.pack("<I", len(text)) + text
    struct.pack_into("<5I", out, term, group, ID, 0x2026960B, off, len(text) if excl else len(text) + 4)
    cd.write_new(path, bytes(out), False)
    return "+0xDB"


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    dll_dir, spr_dir, game = argv
    apps = os.path.join(game, "Apps")
    shutil.copy2(os.path.join(dll_dir, "SC3KUApacheFlyover.dll"), os.path.join(apps, "SC3KUApacheFlyover.dll"))
    for ext in ("DAT", "IXF", "SII"):
        shutil.copy2(os.path.join(spr_dir, f"SC3KU_ApacheFlyover.{ext}"), os.path.join(apps, "Res", "Sprites", f"SC3KU_ApacheFlyover.{ext}"))
    print("DLL + sprites copied")
    print("SYS.PAK:", patch_syspak(os.path.join(apps, "Sys", "SYS.PAK")))
    textdir = os.path.join(apps, "Res", "Text")
    for folder in sorted(os.listdir(textdir)):
        lang = cd.folder_lang(textdir, folder)
        res = []
        for f in cd.FILES:
            p = os.path.join(textdir, folder, f"Sc3StringsPetitioner{f}.IXF")
            if not os.path.exists(p):
                continue
            _d, recs, _t = cd.ixf_texts(p)
            res.append(ixf_add_one(p, recs[0]["group"], TEXT[lang][f].encode("cp1252")))
        print(f"{folder} [{lang}]: {', '.join(sorted(set(res)))}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
