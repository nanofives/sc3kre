#!/usr/bin/env python3
"""civicdeals_patch.py - install Civic Deals (D9 / DA petitioner offers) on the player's own files, in Spanish or English.

Civic Deals + Extra Cheats v1.0 (thronevintagetech, with the author's permission, re/analysis/COMMUNITY_MODS.md) ships
EA's SYS.PAK and six petitioner .IXF files with its additions. We never ship those: this applies the same additions to
the player's copies, which also keeps the player's language. What it does to <game>\\Apps:

  Sys\\SYS.PAK                     PetitionerExtraInfo.ini  + 0x000000D9=19,2 and 0x000000DA=19,2 (after 0x000000D8)
                                  PetitionerManager.ini    NumberOfPetitionerMessages 210 -> 212
  Res\\Text\\<lang>\\Sc3StringsPetitioner{Advice,Button1,Button2,Heading,Reaction1,Reaction2}.IXF
                                  two new records each (instance 0xD9, 0xDA), payload appended at the end, every
                                  original record untouched (the index has spare zero slots)
  SC3KExtraCheats.dll             Null 45's plugin (dotcom, moolah, SimDate), copied unchanged
  SC3KCivicDeals.dll              the author's DLL; for Spanish its visible strings (petitioner name, window titles,
                                  message bodies, buttons, reactions, cheat notices) are rewritten in place, each
                                  inside its original NUL-padded slot

Language per text folder: the folder's 0xD7 heading equal to English-UK's -> English, the ENGLISH folder with any other
text -> Spanish (that folder holds Spanish on Spanish installs), every other folder -> English text for now.
The DLL follows the ENGLISH folder's language unless --lang is given.

Safe to run twice: a file that already has 0xD9 is left alone. Every changed file is first copied to
<name>.civicdeals-orig (once), and written through a temp file + rename, so a hard-linked tree gets its own copy.

usage: py -3.12 re/tools/civicdeals_patch.py <Civic Deals package dir> <game dir> [--lang es|en] [--dry-run]
       py -3.12 re/tools/civicdeals_patch.py --restore <game dir>
"""
import os
import shutil
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ixf_parse  # noqa: E402
import syspak_parse  # noqa: E402

FILES = ("Advice", "Button1", "Button2", "Heading", "Reaction1", "Reaction2")
SUFFIX = ".civicdeals-orig"

# Spanish for the IXF records. The game's Spanish says "Alcalde", "arcas", "simlletes".
ES_IXF = {
    ("Heading", 0xD9): "Trato de desarrollo por la puerta de atrás",
    ("Heading", 0xDA): "Oferta de reurbanización TMC",
    ("Button1", 0xD9): "Aprobar el acuerdo privado",
    ("Button1", 0xDA): "Aprobar la prueba de la TMC",
    ("Button2", 0xD9): "Que decida el mercado",
    ("Button2", 0xDA): "Rechazar el experimento",
    ("Advice", 0xD9): "La inversión privada puede ir más rápido que una comisión de urbanismo, Alcalde, pero "
                      "esta propuesta no solo financia el desarrollo: deja que un consorcio elija quién construye. La "
                      "aportación ayudaría hoy a las arcas, pero el acceso preferente puede costarle a %YOURCITY% "
                      "competencia, confianza pública y mejores ofertas mañana. Si sigue adelante, no lo llame "
                      "libre mercado.",
    ("Advice", 0xDA): "El clima no es una herramienta de zonificación. La aportación es considerable, pero el "
                      "experimento puede golpear cualquier parte de %YOURCITY%, destruir edificios, colapsar el tráfico "
                      "y causar costes muy superiores a 100.000 simlletes. Victor Stone ha descrito las ventajas con "
                      "mucho cuidado y el lugar del impacto en absoluto. Recomiendo rechazarlo.",
    ("Reaction1", 0xD9): "Una decisión excelente, Alcalde. La aportación ya ha llegado a las arcas a través de "
                         "varias organizaciones cívicas de lo más respetables. Por favor, borre nuestro número.",
    ("Reaction1", 0xDA): "Una decisión excelente, Alcalde. La TMC se está activando. No podemos predecir dónde se "
                         "formará la rotación atmosférica, así que mejor quédese bajo techo. La aportación "
                         "ya está en las arcas.",
    ("Reaction2", 0xD9): "Qué íntegro, Alcalde. Llevaremos nuestra propuesta, y nuestras donaciones de campaña, a "
                         "una ciudad vecina con una idea más flexible del desarrollo.",
    ("Reaction2", 0xDA): "Qué prudente, Alcalde. El experimento se cancela, las arcas no reciben nada y el libre mercado "
                         "puede seguir con su tedioso trabajo.",
}

# Spanish for the DLL strings: file offset in SC3KCivicDeals.dll v1.0 -> (English original, Spanish). The original is
# checked before writing; the Spanish must fit the original's NUL-padded slot (checked too).
ES_DLL = {
    0x3438c: ("Victor Stone, Property Developer", "Victor Stone, promotor inmobiliario"),
    0x343b0: ("The Preferred Development Initiative", "Iniciativa de Desarrollo Preferente"),
    0x343d8: ("Mayor, the city urgently needs more commercial and industrial space",
              "Alcalde, la ciudad necesita con urgencia más suelo comercial e industrial, pero comprar terreno en el "
              "libre mercado es caro, lento y demasiado público. Recalifique la ampliación, dé a nuestro "
              "consorcio la primera opción y haremos una generosa aportación a las arcas. Como siempre, esta "
              "conversación nunca existió. Ni correos, ni actas, ni fotos juntos en las redes."),
    0x34570: ("Approve the private arrangement", "Aprobar el acuerdo privado"),
    0x34590: ("Let the market decide", "Que decida el mercado"),
    0x345a8: ("An excellent decision, Mayor. The contribution has already reached",
              "Excelente decisión, Alcalde. La aportación ya llegó a las arcas a través de varias "
              "organizaciones cívicas muy respetables. Borre nuestro número."),
    0x3464c: ("How principled of you, Mayor.",
              "Qué íntegro, Alcalde. Llevaremos la propuesta, y nuestras donaciones, a una ciudad vecina con "
              "una idea más flexible del desarrollo."),
    0x346f0: ("The WMT Redevelopment Initiative", "Iniciativa de Reurbanización TMC"),
    0x34714: ("Mayor, land values in our preferred expansion district are far too high.",
              "Alcalde, el suelo en nuestra zona de expansión preferida está demasiado caro. Nuestros "
              "laboratorios han creado la TMC, Tecnología de Modificación del Clima. Un breve fenómeno "
              "meteorológico podría despejar obstáculos y bajar los precios. Por desgracia, la TMC no se "
              "puede apuntar con precisión. Sobreviva o no el distrito, se ganará dinero. Apruebe la prueba, dé a nuestro consorcio la primera opción sobre el terreno afectado y "
              "llegarán 100.000 simlletes a las arcas. Naturalmente, esta conversación nunca existió."),
    0x34928: ("Approve the WMT field test", "Aprobar la prueba de TMC"),
    0x34943: ("Reject the experiment", "Rechazar el experimento"),
    0x3495c: ("An excellent decision, Mayor. WMT is activating now.",
              "Excelente decisión, Alcalde. La TMC se está activando. No sabemos dónde se formará el "
              "remolino, así que mejor quédese bajo techo. La aportación ya está en las arcas."),
    0x34a08: ("How cautious of you, Mayor.",
              "Qué prudente, Alcalde. El experimento se cancela, las arcas no reciben nada y el libre mercado "
              "sigue con su tedioso trabajo."),
    0x34a94: ("The private arrangement was approved.", "Acuerdo privado aprobado. Se ingresaron 100.000 simlletes."),
    0x34aec: ("The private arrangement was rejected.", "Acuerdo privado rechazado. Los fondos no cambian."),
    0x34b30: ("The WMT experiment was rejected.", "Experimento TMC rechazado. Sin tornado y sin cambio de fondos."),
    0x34b88: ("WMT was activated.", "TMC activada. Se forma un tornado y se ingresaron 100.000 simlletes."),
    0x34be0: ("The contribution was deposited, but WMT failed",
              "Se ingresó la aportación, pero la TMC no pudo activar el tornado."),
    0x34c2e: ("Corrupt & Crazy", "Corrupto y loco"),
    0x34001: ("Corrupt & Crazy", "Corrupto y loco"),   # title of the cheat's first notice
    0x34c40: ("The developer deal was completed, but the WMT follow-up could not be queued.",
              "El trato se completó, pero la oferta TMC no pudo ponerse en cola. Puede que el archivo de asesores "
              "de la ciudad esté lleno."),
    0x33df4: ("This civic deal was already offered this session.",
              "Este trato ya se ofreció en esta sesión. Reinicie el juego para volver a usar el código."),
    0x33e60: ("The first private development proposal is waiting in the inbox.",
              "La primera propuesta de desarrollo le espera en Reunirse. La propuesta TMC llegará cuando la responda."),
    0x33ed8: ("Only one of the two proposals could be queued",
              "Solo se pudo poner en cola una de las dos propuestas: el archivo de asesores está lleno. "
              "Respóndala antes de repetir el truco."),
    0x33f5b: ("Native tornado event sent.", "Tornado del juego enviado."),
    0x33f78: ("The tornado event could not be sent.", "No se pudo enviar el tornado."),
    0x33a20: ("Rain and clouds requested.", "Lluvia y nubes pedidas. Si se van, use clouds off y luego clouds on."),
    0x33a6c: ("Cloud lock disabled and clear weather requested.", "Nubes desbloqueadas, se pide cielo despejado."),
    0x33acc: ("Forest operation completed.\n\nTrees planted: %lu\nEligible empty tiles examined: %lu",
              "Bosque terminado.\n\nÁrboles plantados: %lu\nCasillas vacías revisadas: %lu"),
    0x33fa0: ("Forest thickening completed.\n\nTree tiles increased by one density level: %lu",
              "Bosque más denso.\n\nCasillas con árboles, un nivel más: %lu"),
}


def write_new(path, data, dry):
    """backup once, then temp + rename (breaks a hard link instead of writing through it)"""
    if dry:
        return
    if os.path.exists(path) and not os.path.exists(path + SUFFIX):
        shutil.copy2(path, path + SUFFIX)
    tmp = path + ".civicdeals-tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def ixf_texts(path):
    d = open(path, "rb").read()
    recs, _ = ixf_parse.parse(path)
    out = {}
    for r in recs:
        n = struct.unpack_from("<I", d, r["offset"])[0]
        out[r["instance"]] = d[r["offset"] + 4: r["offset"] + 4 + n]
    return d, recs, out


def ixf_append(path, group, items, dry):
    """items: [(instance, bytes)] -> new records in the spare index slots, payloads appended"""
    d, recs, texts = ixf_texts(path)
    if 0xD9 in texts:
        return "already has 0xD9"
    slots = ixf_parse.read_index_slots(d)
    term = 4 + (len(slots) - 1) * 20          # the all-zero terminator slot
    first = min(s[3] for s in slots if s[3] not in (0, 0xFFFFFFFF))
    need_end = term + (len(items) + 1) * 20
    if need_end > first or any(d[term:need_end]):
        raise SystemExit(f"{path}: no spare index slots ({term}..{need_end}, data at {first})")
    # the file's own size convention: size == string length (prefix excluded) or the whole payload
    r0 = recs[0]
    excl = struct.unpack_from("<I", d, r0["offset"])[0] == r0["size"]
    out = bytearray(d)
    for i, (inst, text) in enumerate(items):
        off = len(out)
        out += struct.pack("<I", len(text)) + text
        struct.pack_into("<5I", out, term + i * 20, group, inst, 0x2026960B, off, len(text) if excl else len(text) + 4)
    write_new(path, bytes(out), dry)
    r, _ = ixf_parse.parse(path) if not dry else (None, None)
    return f"+{len(items)} records" + ("" if dry else f" ({len(r)} records now)")


def folder_lang(textdir, folder):
    uk = os.path.join(textdir, "English-UK", "Sc3StringsPetitionerHeading.IXF")
    me = os.path.join(textdir, folder, "Sc3StringsPetitionerHeading.IXF")
    if folder.lower() == "english" and os.path.exists(uk) and ixf_texts(me)[2].get(0xD7) != ixf_texts(uk)[2].get(0xD7):
        return "es"
    return "en"


def patch_syspak(path, dry):
    data = open(path, "rb").read()
    names, _o, _t, recs = syspak_parse.parse(data)
    lines = [list(r["lines"]) for r in recs]
    low = [n.lower() for n in names]
    ei, mi = low.index("petitionerextrainfo.ini"), low.index("petitionermanager.ini")
    if "0x000000D9=19,2" in lines[ei]:
        return "already patched"
    k = lines[ei].index("0x000000D8=5,6")
    lines[ei][k + 1:k + 1] = ["0x000000D9=19,2", "0x000000DA=19,2"]
    j = lines[mi].index("NumberOfPetitionerMessages=210")
    lines[mi][j] = "NumberOfPetitionerMessages=212"
    out = syspak_parse.build(names, lines)
    n2, _o, _t, r2 = syspak_parse.parse(out)
    ch = [n for n, a, b in zip(n2, recs, r2) if a["lines"] != b["lines"]]
    assert n2 == names and sorted(ch) == sorted([names[ei], names[mi]]), ch
    write_new(path, out, dry)
    return "D9/DA added, 212 messages"


def patch_dll(src, dst, lang, dry):
    b = bytearray(open(src, "rb").read())
    if lang == "es":
        for off, (en, es) in sorted(ES_DLL.items()):
            if b[off:off + len(en)] != en.encode("cp1252"):
                raise SystemExit(f"SC3KCivicDeals.dll: 0x{off:x} is not '{en[:30]}': not v1.0?")
            z = b.index(0, off)
            while z < len(b) and b[z] == 0:
                z += 1
            slot = z - off - 1
            enc = es.encode("cp1252")
            if len(enc) > slot:
                raise SystemExit(f"0x{off:x}: Spanish is {len(enc)} bytes, slot {slot}: '{es[:40]}'")
            b[off:off + slot + 1] = enc + b"\0" * (slot + 1 - len(enc))
    write_new(dst, bytes(b), dry)
    return f"{'Spanish' if lang == 'es' else 'English'} ({len(ES_DLL) if lang == 'es' else 0} strings rewritten)"


def restore(game):
    n = 0
    for root, _d, files in os.walk(os.path.join(game, "Apps")):
        for f in files:
            if f.endswith(SUFFIX):
                os.replace(os.path.join(root, f), os.path.join(root, f[:-len(SUFFIX)]))
                n += 1
    for leaf in ("SC3KCivicDeals.dll", "SC3KExtraCheats.dll"):
        dll = os.path.join(game, "Apps", leaf)
        if os.path.exists(dll) and not os.path.exists(dll + SUFFIX):
            os.remove(dll)
            n += 1
    print(f"restored {n} file(s)")


def main(argv):
    if len(argv) >= 2 and argv[0] == "--restore":
        restore(argv[1])
        return 0
    args = [a for a in argv if not a.startswith("--")]
    dry = "--dry-run" in argv
    lang = argv[argv.index("--lang") + 1] if "--lang" in argv else None
    if lang:
        args.remove(lang)
    if len(args) != 2:
        print(__doc__)
        return 2
    pkg, game = args
    pk = None
    for root, _d, files in os.walk(pkg):
        if "SC3KCivicDeals.dll" in files:
            pk = root
            break
    if not pk:
        raise SystemExit("SC3KCivicDeals.dll not found in the package")
    apps = os.path.join(game, "Apps")
    textdir = os.path.join(apps, "Res", "Text")
    src_en = os.path.join(pk, "Res", "Text", "ENGLISH")
    _g = {}
    en_items = {}
    for f in FILES:
        d, recs, t = ixf_texts(os.path.join(src_en, f"Sc3StringsPetitioner{f}.IXF"))
        _g[f] = recs[0]["group"]
        en_items[f] = [(0xD9, t[0xD9]), (0xDA, t[0xDA])]
    print("SYS.PAK:", patch_syspak(os.path.join(apps, "Sys", "SYS.PAK"), dry))
    for folder in sorted(os.listdir(textdir)):
        fl = folder_lang(textdir, folder)
        for f in FILES:
            p = os.path.join(textdir, folder, f"Sc3StringsPetitioner{f}.IXF")
            if not os.path.exists(p):
                continue
            items = en_items[f] if fl == "en" else [(i, ES_IXF[(f, i)].encode("cp1252")) for i in (0xD9, 0xDA)]
            print(f"{folder}\\{f} [{fl}]:", ixf_append(p, _g[f], items, dry))
    dl = lang or folder_lang(textdir, "ENGLISH")
    xc = os.path.join(pk, "SC3KExtraCheats.dll")   # Null 45's plugin, MIT: shipped unchanged (owner decision)
    if os.path.exists(xc):
        write_new(os.path.join(apps, "SC3KExtraCheats.dll"), open(xc, "rb").read(), dry)
        print("SC3KExtraCheats.dll: copied unchanged")
    print("SC3KCivicDeals.dll:", patch_dll(os.path.join(pk, "SC3KCivicDeals.dll"), os.path.join(apps, "SC3KCivicDeals.dll"), dl, dry))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
