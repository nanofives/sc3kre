#!/usr/bin/env python3
r"""batgrow.py - task batconvert (2026-11-10): reference implementation of bat_growables.ps1.

Every BAT building in the player's Apps\BARender\BAT.DAT becomes ITS OWN new growable building (occupant id 37000 to
37999) that grows in zones next to the stock buildings, nothing replaced. The player-facing tool is the PowerShell
script re/scripts/bat_growables.ps1 (players have no Python). This module produces the same bytes, so the PowerShell
port can be checked against it file by file (`compare`), and it computes the class table the script embeds
(`tables`, `check-ps`).

  py -3.12 re/tools/batgrow.py tables --game <tree>             class -> families + base building per lot size
  py -3.12 re/tools/batgrow.py check-ps --game <tree>           the table embedded in bat_growables.ps1 still matches
  py -3.12 re/tools/batgrow.py build --game <tree> --out <dir>  what a run would write (overlay-relative), game untouched
  py -3.12 re/tools/batgrow.py compare --game <tree>            build in memory, compare with the files in the tree
  py -3.12 re/tools/batgrow.py list --game <tree>               the BAT buildings and what the ini says about them

What one enabled BAT building becomes (verify/batconvert/RESULTS.md; recipe BUILDING_PICK.md 6 C, growable, stylemix):

  pixels       its 16 pixel (type 0) + 16 anchor (type 1) records, verbatim, re-keyed (GROUP, id << 16 | ordinal),
               ordinal = order of first use in the frame table. New container
               mods\netmod\overlay\Apps\Res\Sprites\BA7C0001_batgrow.DAT (Res\Sprites\*.DAT is enumerated at startup).
  frame table  its BAT.DAT 0x6300 table (20 entries: frames 16-19 re-use 12-15 with flag 2, as stock), verbatim
               except each entry's (group, instance) -> the re-keyed pixels. Key {0x6300, GROUP, id}, appended to the
               overlay CSAttrib_Korea.IXF.
  exemplar     the TKB1 record of a stock family member of the same class (LandUse, prop 0x65) and lot size (prop 0x66)
               re-keyed {0x207EDC0E, 0x57E, id}: prop 0x67 -> {0x6300, GROUP, id}, prop 0x6D -> {0x2026960B,
               0xA1096A4F, id}, prop 0x64 = the BAT name. Appended to the overlay OccupantAttribs_Korea.IXF
               ([OccAttribCache] Entry5; an exemplar outside the attrib cache crashed SIMRCI 0x10026D6D, growable OC).
  name         {0x2026960B, 0xA1096A4F, id} = u32 length + name, appended to every overlay
               Res\Text\<lang>\SC3StringsNetpack.IXF (already listed in [DBSegments] by the road packages).
  family line  "Key: 1406,545184782,<id>,<weight>   <name>" right after BuildingCount (count raised) in every family
               that is the first family of the class in some [ZoneDeveloperRules] row (minus family 1, row houses),
               in the overlay BUILDFAM.IXF (or a copy of Apps\Res\BUILDFAM.IXF). Record replaced netpack-style: new
               payload appended, slot re-pointed (netpack_lanes.replace_records).

Re-runnable: each run first puts back every file it wrote last time (state.json keeps the sha256 it wrote; a file
that changed since, e.g. replaced by a new sc3mods release, is taken as the new source and its old backup dropped),
then applies the ini again. -Restore / `restore` = that first step alone.
"""
import argparse
import hashlib
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

MAGIC = 0x80C381D7
REC = 20
FIRST_PAYLOAD = 0x5004
BLOCK = 0x5000

BAT_REL = "Apps/BARender/BAT.DAT"
BAT_GROUP, OVR_TYPE, CS_TYPE = 0xBA1DBF1E, 0x856CD19A, 0x6300
BLD_TYPE, BLD_GROUP = 0x207EDC0E, 0x57E
FAM_TYPE, FAM_GROUP = 0x81F53D09, 0x01F58D3D
TEXT_TYPE, TEXT_GROUP = 0x2026960B, 0xA1096A4F
GROUP = 0xBA7C0001                       # batconvert's own group: frame tables + pixels (no stock container uses it)
ID_FIRST, ID_LAST = 37000, 37999         # COORDINATION: 36001-36099 tests, 36100-36999 bat slots, +400000/+1500000 styles

OVL = "mods/netmod/overlay/"
OCC_KOREA = "Apps/Res/Occupant/OccupantAttribs_Korea.IXF"
CS_KOREA = "Apps/Res/Sprites/CSAttrib_Korea.IXF"
BUILDFAM = "Apps/Res/BUILDFAM.IXF"
NAMES = "SC3StringsNetpack.IXF"
PIX_DAT = "Apps/Res/Sprites/BA7C0001_batgrow.DAT"
STATE_DIR = "mods/netmod/batgrow"
INI = "bat_growables.ini"

# .bld record 0x644D7179 -> default class by lot size. 0x208 houses, 0x209 shops and offices, 0x20A factories (the
# value as a category is read from the 17 shipped .bld names only, BUILDING_PICK.md 7 [UNCERTAIN]); anything else
# (school 0x20F, 0x212, park 0x217) starts disabled for the player to choose.
CATEGORY_ZONE = {0x208: "R", 0x209: "C", 0x20A: "I"}
DEFAULT_CLASS = {"R": {1: 3300, 2: 3900, 3: 4500, 4: 4500},
                 "C": {1: 5100, 2: 5700, 3: 6300, 4: 6700},
                 "I": {1: 8700, 2: 8700, 3: 8900, 4: 9100}}
CLASS_LABEL = {
    3100: "Residential light, low wealth", 3300: "Residential light, mid wealth",
    3500: "Residential light, high wealth", 3700: "Residential medium, low wealth",
    3900: "Residential medium, mid wealth", 4100: "Residential medium, high wealth",
    4300: "Residential dense, low wealth", 4500: "Residential dense, mid wealth",
    4700: "Residential dense, high wealth",
    5100: "Commercial light, low wealth", 5500: "Commercial light, high wealth",
    5700: "Commercial medium, low wealth", 6100: "Commercial medium, high wealth",
    6300: "Commercial dense, low wealth", 6700: "Commercial dense, high wealth",
    8100: "Industrial dirty, light", 8300: "Industrial dirty, medium", 8500: "Industrial dirty, dense",
    8700: "Industrial clean, light", 8900: "Industrial clean, medium", 9100: "Industrial clean, dense",
    9300: "Farm",
}
EXCLUDE_FAMILIES = {1}                   # row-house rule family (batslots_build.EXCLUDE)
KEY_RE = re.compile(rb"Key:\s*(\d+),(\d+),(\d+),(\d+)")


class BatError(Exception):
    pass


# =================================================================== IXF

def slots(d):
    if len(d) < 4 or struct.unpack_from("<I", d, 0)[0] != MAGIC:
        raise BatError("not an IXF container")
    out, n = [], 0
    while 4 + (n + 1) * REC <= len(d):
        s = struct.unpack_from("<5I", d, 4 + n * REC)
        out.append(s)
        n += 1
        if s[:3] == (0, 0, 0):
            break
    if not out or out[-1][:3] != (0, 0, 0):
        raise BatError("IXF index has no terminator")
    return out


def records(d):
    """-> {(group, instance, type): payload} of live slots (first wins), and the key order."""
    idx, order = {}, []
    for g, i, t, o, n in slots(d)[:-1]:
        if t == 0xFFFFFFFF or o == 0xFFFFFFFF or n == 0xFFFFFFFF:
            continue
        if (g, i, t) not in idx:
            idx[(g, i, t)] = d[o:o + n]
            order.append((g, i, t))
    return idx, order


def new_container(recs):
    """recs: [(group, instance, type, payload)] -> container bytes in the shipped shape (= ixf_insert.new_container)."""
    n = len(recs)
    first = FIRST_PAYLOAD if 4 + (n + 1) * REC <= FIRST_PAYLOAD else 4 + (n + 1) * REC
    out = bytearray(struct.pack("<I", MAGIC))
    off = first
    for g, i, t, p in recs:
        out += struct.pack("<5I", g, i, t, off, len(p))
        off += len(p)
    out += b"\x00" * (first - len(out))
    for r in recs:
        out += r[3]
    return bytes(out)


def append(d, recs):
    """= ixf_insert.append (grow by whole 0x5000 blocks when the reserved index is full)."""
    sl = slots(d)
    term_at = 4 + (len(sl) - 1) * REC
    live = [s for s in sl[:-1] if s[3] != 0xFFFFFFFF and s[4] != 0xFFFFFFFF]
    first = min(s[3] for s in live) if live else len(d)
    need_end = term_at + (len(recs) + 1) * REC
    if need_end > first:
        if any(d[term_at:first]):
            raise BatError("bytes between the index terminator and the first payload are not zero")
        delta = BLOCK * ((need_end - first + BLOCK - 1) // BLOCK)
        g = bytearray(d[:first]) + bytearray(delta) + bytearray(d[first:])
        for k, s in enumerate(sl[:-1]):
            if s[3] != 0xFFFFFFFF:
                struct.pack_into("<I", g, 4 + k * REC + 12, s[3] + delta)
        d = bytes(g)
        sl = slots(d)
    keys = {s[:3] for s in sl[:-1]}
    out = bytearray(d)
    off = len(out)
    blob = bytearray()
    for g, i, t, p in recs:
        if (g, i, t) in keys:
            raise BatError("key group 0x%08X instance 0x%08X type 0x%08X already present" % (g, i, t))
        keys.add((g, i, t))
        blob += struct.pack("<5I", g, i, t, off, len(p))
        off += len(p)
    blob += b"\x00" * REC
    if any(out[term_at:term_at + len(blob)]):
        raise BatError("bytes after the index terminator are not zero")
    out[term_at:term_at + len(blob)] = blob
    for r in recs:
        out += r[3]
    return bytes(out)


def replace(d, recs):
    """= netpack_lanes.replace_records for keys that exist: payload appended at the end, slot re-pointed."""
    out = bytearray(d)
    pos = {s[:3]: 4 + k * REC for k, s in enumerate(slots(d)) if s[:3] != (0, 0, 0)}
    for g, i, t, p in recs:
        at = pos.get((g, i, t))
        if at is None:
            raise BatError("record {0x%08X,0x%08X,%d} not in the container" % (t, g, i))
        off = len(out)
        out += p
        struct.pack_into("<II", out, at + 12, off, len(p))
    return bytes(out)


# =================================================================== TKB1

def tkb1_props(buf):
    if buf[:4] != b"TKB1":
        raise BatError("not a TKB1 record")
    out, o = [], 4
    while o + 8 <= len(buf):
        prop, = struct.unpack_from("<I", buf, o)
        t, n = struct.unpack_from("<HH", buf, o + 4)
        o += 8
        if t == 7:
            ln = struct.unpack_from("<I", buf, o)[0] + 4
        elif t == 3:
            ln = 4 * n
        elif t == 8:
            ln = 12 * n
        elif t == 1:
            ln = n
        else:
            raise BatError("TKB1 prop 0x%x has unknown type %d" % (prop, t))
        out.append((prop, t, n, o, ln))
        o += ln
    if o != len(buf):
        raise BatError("TKB1 walk ended at %d of %d bytes" % (o, len(buf)))
    return out


def tkb1_get(buf, prop):
    for p, t, n, off, ln in tkb1_props(buf):
        if p == prop:
            if t == 3:
                return struct.unpack_from("<%dI" % n, buf, off)
            if t == 8:
                return struct.unpack_from("<%dI" % (3 * n), buf, off)
            if t == 7:
                return buf[off + 4:off + ln]
            return buf[off:off + ln]
    return None


def tkb1_set_key(buf, prop, key):
    b = bytearray(buf)
    for p, t, n, off, ln in tkb1_props(buf):
        if p == prop:
            if t != 8 or n != 1:
                raise BatError("prop 0x%x is not one key" % prop)
            struct.pack_into("<3I", b, off, *key)
            return bytes(b)
    raise BatError("prop 0x%x not present" % prop)


def tkb1_set_text(buf, prop, raw):
    for p, t, n, off, ln in tkb1_props(buf):
        if p == prop:
            if t != 7:
                raise BatError("prop 0x%x is not text" % prop)
            return buf[:off] + struct.pack("<I", len(raw)) + raw + buf[off + ln:]
    raise BatError("prop 0x%x not present" % prop)


# =================================================================== game files

class Game:
    def __init__(self, root):
        self.root = os.path.abspath(root)

    def path(self, rel):
        return os.path.join(self.root, *rel.split("/"))

    def exists(self, rel):
        return os.path.isfile(self.path(rel))

    def read(self, rel):
        with open(self.path(rel), "rb") as fh:
            return fh.read()

    def listdir(self, rel):
        p = self.path(rel)
        return sorted(os.listdir(p), key=str.lower) if os.path.isdir(p) else []

    def overlay_or_stock(self, rel):
        return self.read(OVL + rel) if self.exists(OVL + rel) else self.read(rel)


def stock_buildings(game):
    """-> {id: (file name, TKB1)} over Apps\\Res\\Occupant\\*.IXF in case-insensitive name order, first wins."""
    out = {}
    for n in game.listdir("Apps/Res/Occupant"):
        if n.lower().endswith(".ixf"):
            idx, order = records(game.read("Apps/Res/Occupant/" + n))
            for g, i, t in order:
                if t == BLD_TYPE and g == BLD_GROUP:
                    out.setdefault(i, (n, idx[(g, i, t)]))
    return out


def base_exemplar(game, bid, fname):
    """The base's TKB1 from the file the class table names (the PowerShell script reads the same file)."""
    idx, _ = records(game.read("Apps/Res/Occupant/" + fname))
    p = idx.get((BLD_GROUP, bid, BLD_TYPE))
    if p is None:
        raise BatError("stock building %d not found in Apps/Res/Occupant/%s" % (bid, fname))
    return p


def family_records(d):
    idx, order = records(d)
    return {i: idx[(g, i, t)] for g, i, t in order if t == FAM_TYPE and g == FAM_GROUP}


def family_landuse(p):
    m = re.search(rb"LandUse:\s*(\d+)", p)
    return int(m.group(1)) if m else None


def class_table(game):
    """-> {class: {"families": [...], "bases": {size: (id, file)}}} from the stock files (Apps, not the overlay).
    Families: every family that is the first family of the class in some [ZoneDeveloperRules] row (a rule Apply takes
    the first record whose LandUse matches, BUILDING_PICK.md 2), minus family 1. Base per lot size: the first member,
    in family order, with a plain 0x6300 frame table, attrib flag prop 0xCA & 0x100 clear (set on filler lots such as
    Playground 3079) and a square footprint of that size."""
    sys.path.insert(0, os.path.join(HERE, "netmod"))
    import batslots_build as BB      # rule_first_families: parses SYS.PAK [ZoneDeveloperRules]
    fams = family_records(game.read(BUILDFAM))
    firsts = BB.rule_first_families(game.read("Apps/Sys/SYS.PAK"), fams)
    bld = stock_buildings(game)
    out = {}
    for lu in sorted(CLASS_LABEL):
        fl = [f for f in firsts.get(lu, []) if f not in EXCLUDE_FAMILIES]
        if not fl:
            raise BatError("class %d: no rule uses a family with that LandUse" % lu)
        bases = {}
        for f in fl:
            for m in KEY_RE.finditer(fams[f]):
                if int(m.group(1)) != BLD_GROUP or int(m.group(2)) != BLD_TYPE:
                    continue
                bid = int(m.group(3))
                if bid not in bld:
                    continue
                p = bld[bid][1]
                fp, cs, fl_ = tkb1_get(p, 0x66), tkb1_get(p, 0x67), tkb1_get(p, 0xCA)
                if not fp or fp[0] != fp[2] or not 1 <= fp[0] <= 4 or fp[0] in bases:
                    continue
                if not cs or cs[0] != CS_TYPE or (fl_ and fl_[0] & 0x100):
                    continue
                if tkb1_get(p, 0x65) != (lu,) or tkb1_get(p, 0x6D) is None:
                    continue
                bases[fp[0]] = (bid, bld[bid][0])
        out[lu] = {"families": fl, "bases": dict(sorted(bases.items()))}
    for z, row in DEFAULT_CLASS.items():
        for size, lu in row.items():
            if size not in out[lu]["bases"]:
                raise BatError("default class %d for zone %s has no %dx%d base" % (lu, z, size, size))
    return out


def bat_buildings(game):
    """-> [dict] per override record of BAT.DAT, in index order."""
    d = game.read(BAT_REL)
    idx, order = records(d)
    out = []
    for g, i, t in order:
        if t != OVR_TYPE or g != BAT_GROUP:
            continue
        p = idx[(g, i, t)]
        b = {"inst": i, "size": p[0], "problem": None}
        try:
            key = struct.unpack_from("<3I", p, 1)
            nl = struct.unpack_from("<I", p, 13)[0]
            b["name"] = p[17:17 + nl]
            al = struct.unpack_from("<I", p, 17 + nl)[0]
            b["architect"] = p[21 + nl:21 + nl + al]
        except struct.error:
            b.update(name=b"", architect=b"", problem="override record too short")
            out.append(b)
            continue
        tab = idx.get((key[1], key[2], key[0]))
        if key[0] != CS_TYPE or tab is None or len(tab) < 0x18 or tab[:4] != b"BIN\r" or (len(tab) - 0x18) % 15:
            b["problem"] = "frame table {0x%X,0x%X,0x%X} missing or not a 0x6300 table" % key
        elif not 1 <= b["size"] <= 4:
            b["problem"] = "lot size %d" % b["size"]
        else:
            ents = [struct.unpack_from("<II", tab, 0x18 + 15 * k + 2) for k in range((len(tab) - 0x18) // 15)]
            pix = []
            for e in ents:
                if e not in pix:
                    pix.append(e)
            if any((pg, pi, 0) not in idx or (pg, pi, 1) not in idx for pg, pi in pix) or len(pix) > 0xFFFF:
                b["problem"] = "frame table names a pixel record BAT.DAT does not hold"
            else:
                b.update(table=tab, entries=ents, pixels=[(idx[(pg, pi, 0)], idx[(pg, pi, 1)]) for pg, pi in pix],
                         pix_keys=pix)
        out.append(b)
    return out


def bld_categories(game):
    """-> ({instance: category}, {name bytes: category}) from <game>\\Buildings\\*.bld (record 0x644D7179; the
    instance is the last u32 of record 0xE3F87B0F, which matched BAT.DAT for 13 of the 15 shipped buildings)."""
    by_inst, by_name = {}, {}
    for n in game.listdir("Buildings"):
        if not n.lower().endswith(".bld"):
            continue
        try:
            idx, _ = records(game.read("Buildings/" + n))
        except (BatError, OSError, struct.error):
            continue
        cat = info = None
        for (g, i, t), p in idx.items():
            if t == 0x644D7179 and len(p) >= 4:
                cat = struct.unpack_from("<I", p, 0)[0]
            if t == 0xE3F87B0F:
                info = p
        if cat is None or info is None or len(info) < 6:
            continue
        by_inst.setdefault(struct.unpack_from("<I", info, len(info) - 4)[0], cat)
        nl = info[1]
        by_name.setdefault(info[2:2 + nl], cat)
    return by_inst, by_name


# =================================================================== ini

def ini_parse(raw):
    """-> [{"id": int, key: value}] in file order. Lines: [<id>], key = value, ';' comments at line start."""
    secs, cur = [], None
    for ln in raw.decode("cp1252").splitlines():
        s = ln.strip()
        if not s or s.startswith(";"):
            continue
        m = re.match(r"^\[\s*(\d+)\s*\]$", s)
        if m:
            cur = {"id": int(m.group(1))}
            secs.append(cur)
            continue
        if cur is not None and "=" in s:
            k, v = s.split("=", 1)
            cur[k.strip().lower()] = v.strip()
    return secs


def ini_render(table, entries):
    L = ["; bat_growables.ini: your Building Architect (BAT) buildings that grow in zones as buildings of their own.",
         "; Written by bat_growables.ps1. Change enabled, class or weight, then run bat_growables.ps1 again.",
         "; Keep each building's [number] and bat as they are: saved cities refer to the building by that number.",
         ";",
         "; enabled  1 = grows in zones, 0 = does not",
         "; class    the kind of zone lot it grows on (the lot sizes each class takes are listed after it):"]
    for lu in sorted(table):
        L.append(";   %d  %-34s %s" % (lu, CLASS_LABEL[lu], " ".join("%dx%d" % (s, s) for s in table[lu]["bases"])))
    L += ["; weight   how often the game picks it, against a stock building of the same class (stock ones have 1 to 10)",
          "; size     the lot size BAT.DAT gives it (read only)",
          ""]
    for e in sorted(entries, key=lambda e: e["id"]):
        L.append("[%d]" % e["id"])
        L.append("name = %s" % e["name"])
        L.append("bat = %08X" % e["bat"])
        L.append("size = %d" % e["size"])
        L.append("enabled = %s" % e["enabled"])
        L.append("class = %s" % e["class"])
        L.append("weight = %s" % e["weight"])
        if e.get("note"):
            L.append("; %s" % e["note"])
        L.append("")
    return ("\r\n".join(L)).encode("cp1252", "replace")


def ini_merge(game, table, bats, old):
    """-> entries: one per BAT building (old section matched by bat, then by name), plus old sections whose
    building is gone (kept so their number is not reused)."""
    cats_i, cats_n = bld_categories(game)
    by_bat, by_name, used = {}, {}, set()
    for s in old:
        try:
            by_bat.setdefault(int(s.get("bat", ""), 16), s)
        except ValueError:
            pass
        by_name.setdefault(s.get("name", ""), s)
        used.add(s["id"])
    live_bats = {b["inst"] for b in bats}
    taken, out = set(), []
    for b in bats:
        name = b["name"].decode("cp1252")
        s = by_bat.get(b["inst"])
        if s is None or s["id"] in taken:
            s = by_name.get(name)
            if s is not None:
                try:
                    if int(s.get("bat", ""), 16) in live_bats:
                        s = None
                except ValueError:
                    pass
            if s is not None and s["id"] in taken:
                s = None
        if s is None:
            nid = next((k for k in range(ID_FIRST, ID_LAST + 1) if k not in used), None)
            if nid is None:
                raise BatError("no free number left in %d-%d" % (ID_FIRST, ID_LAST))
            used.add(nid)
            cat = cats_i.get(b["inst"], cats_n.get(b["name"]))
            zone = CATEGORY_ZONE.get(cat)
            size = b["size"] if 1 <= b["size"] <= 4 else 1
            s = {"id": nid, "enabled": "1" if zone else "0",
                 "class": str(DEFAULT_CLASS[zone or "R"][size]), "weight": "1"}
        taken.add(s["id"])
        e = {"id": s["id"], "name": name, "bat": b["inst"], "size": b["size"],
             "enabled": s.get("enabled", "1"), "class": s.get("class", ""), "weight": s.get("weight", "1"),
             "building": b}
        out.append(e)
    for s in old:
        if s["id"] not in taken:
            try:
                bat = int(s.get("bat", "0"), 16)
            except ValueError:
                bat = 0
            size = s.get("size", "")
            out.append({"id": s["id"], "name": s.get("name", ""), "bat": bat,
                        "size": int(size) if re.match(r"^[0-9]+$", size) else 0,
                        "enabled": s.get("enabled", "0"), "class": s.get("class", ""), "weight": s.get("weight", "1"),
                        "building": None, "note": "not in BAT.DAT now: skipped"})
    return out


def validate(table, e):
    """-> (class, weight, base) or a reason string for skipping."""
    b = e["building"]
    if b is None:
        return "not in BAT.DAT now"
    if e["enabled"] != "1":
        return "enabled = 0"
    if b["problem"]:
        return b["problem"]
    if not ID_FIRST <= e["id"] <= ID_LAST:
        return "number %d is outside %d-%d" % (e["id"], ID_FIRST, ID_LAST)
    if not re.match(r"^[0-9]+$", e["class"]) or int(e["class"]) not in table:
        return "class %r is not one of the listed classes" % e["class"]
    lu = int(e["class"])
    if b["size"] not in table[lu]["bases"]:
        return "class %d has no %dx%d lot" % (lu, b["size"], b["size"])
    if not re.match(r"^[0-9]+$", e["weight"]) or not 1 <= int(e["weight"]) <= 1000:
        return "weight %r is not a whole number from 1 to 1000" % e["weight"]
    return lu, int(e["weight"]), table[lu]["bases"][b["size"]]


# =================================================================== build

def sha(b):
    return hashlib.sha256(b).hexdigest()


def sources(game):
    """-> ({rel: bytes or None}, state). The files as they were before this tool's last run: a file whose bytes
    still match what the last run wrote comes from its backup (None = the last run created it)."""
    st_path = STATE_DIR + "/state.json"
    state = json.loads(game.read(st_path)) if game.exists(st_path) else {"files": {}}
    src = {}
    for rel, ent in state["files"].items():
        cur = game.read(rel) if game.exists(rel) else None
        if cur is not None and sha(cur) == ent["written"]:
            src[rel] = game.read(STATE_DIR + "/backup/" + rel) if ent["existed"] else None
        else:
            src[rel] = cur
    return src, state


def build(game, src=None):
    """-> (files {rel: bytes}, ini bytes, report lines). rel are game-root-relative paths."""
    if src is None:
        src, _ = sources(game)

    def cur(rel):
        if rel in src:
            return src[rel]
        return game.read(rel) if game.exists(rel) else None

    for rel in (OVL + OCC_KOREA, OVL + CS_KOREA):
        if cur(rel) is None:
            raise BatError("%s not found: the road mod (sc3netmod, mods\\netmod) must be installed" % rel)
    langs = [n for n in game.listdir(OVL + "Apps/Res/Text") if cur(OVL + "Apps/Res/Text/%s/%s" % (n, NAMES))]
    if not langs:
        raise BatError("no mods\\netmod\\overlay\\Apps\\Res\\Text\\<language>\\%s found" % NAMES)
    table = class_table(game)
    bats = bat_buildings(game)
    old = ini_parse(game.read(INI)) if game.exists(INI) else []
    entries = ini_merge(game, table, bats, old)
    files, rep = {}, []
    occ, cs, pix, names, lines = [], [], [], [], {}
    for e in sorted(entries, key=lambda e: e["id"]):
        v = validate(table, e)
        if isinstance(v, str):
            rep.append("skip  [%d] %s: %s" % (e["id"], e["name"], v))
            continue
        lu, weight, (base, bfile) = v
        b, nid = e["building"], e["id"]
        ex = base_exemplar(game, base, bfile)
        ex = tkb1_set_key(ex, 0x67, (CS_TYPE, GROUP, nid))
        ex = tkb1_set_key(ex, 0x6D, (TEXT_TYPE, TEXT_GROUP, nid))
        ex = tkb1_set_text(ex, 0x64, b["name"])
        tkb1_props(ex)
        occ.append((BLD_GROUP, nid, BLD_TYPE, ex))
        tab = bytearray(b["table"])
        for k, ent in enumerate(b["entries"]):
            struct.pack_into("<II", tab, 0x18 + 15 * k + 2, GROUP, (nid << 16) | b["pix_keys"].index(ent))
        cs.append((GROUP, nid, CS_TYPE, bytes(tab)))
        for o, (p0, p1) in enumerate(b["pixels"]):
            pix.append((GROUP, (nid << 16) | o, 0, p0))
            pix.append((GROUP, (nid << 16) | o, 1, p1))
        names.append((TEXT_GROUP, nid, TEXT_TYPE, struct.pack("<I", len(b["name"])) + b["name"]))
        for f in table[lu]["families"]:
            lines.setdefault(f, []).append(b"Key: 1406,545184782,%d,%d   %s\r\n" % (nid, weight, b["name"]))
        rep.append("grow  [%d] %s: class %d (%s), %dx%d, weight %d, stats of stock %d, families %s"
                   % (nid, e["name"], lu, CLASS_LABEL[lu], b["size"], b["size"], weight, base,
                      ",".join(map(str, table[lu]["families"]))))
    if occ:
        files[OVL + OCC_KOREA] = append(cur(OVL + OCC_KOREA), occ)
        files[OVL + CS_KOREA] = append(cur(OVL + CS_KOREA), cs)
        files[OVL + PIX_DAT] = new_container(pix)
        for lang in langs:
            rel = OVL + "Apps/Res/Text/%s/%s" % (lang, NAMES)
            files[rel] = append(cur(rel), names)
        bf = cur(OVL + BUILDFAM)
        if bf is None:
            bf = game.read(BUILDFAM)
        fams = family_records(bf)
        new = []
        for f in sorted(lines):
            text = fams[f]
            m = re.search(rb"BuildingCount:\s*(\d+)[^\r\n]*\r?\n", text)
            if not m:
                raise BatError("BUILDFAM family %d has no BuildingCount line" % f)
            text = text[:m.start()] + b"BuildingCount: %d\r\n" % (int(m.group(1)) + len(lines[f])) + \
                b"".join(lines[f]) + text[m.end():]
            new.append((FAM_GROUP, f, FAM_TYPE, text))
        files[OVL + BUILDFAM] = replace(bf, new)
    return files, ini_render(table, entries), rep


# =================================================================== commands

def cmd_tables(a):
    t = class_table(Game(a.game))
    for lu, v in t.items():
        print("%d  %-34s families %-10s bases %s" % (lu, CLASS_LABEL[lu], ",".join(map(str, v["families"])),
                                                    " ".join("%dx%d=%d(%s)" % (s, s, b[0], b[1])
                                                             for s, b in v["bases"].items())))
    print()
    print(ps_table(t))


def ps_table(t):
    """The class table as the PowerShell literal bat_growables.ps1 embeds between its TABLE markers."""
    L = []
    for lu, v in t.items():
        bases = "; ".join("%d = @(%d, '%s')" % (s, b[0], b[1]) for s, b in v["bases"].items())
        L.append("    %d = @{ Label = '%s'; Families = @(%s); Bases = @{ %s } }"
                 % (lu, CLASS_LABEL[lu], ", ".join(map(str, v["families"])), bases))
    return "\n".join(L)


def cmd_check_ps(a):
    ps = os.path.join(HERE, "..", "scripts", "bat_growables.ps1")
    with open(ps, encoding="utf-8-sig") as fh:
        txt = fh.read()
    m = re.search(r"# TABLE BEGIN[^\n]*\n(.*?)\n# TABLE END", txt, re.S)
    want = ps_table(class_table(Game(a.game)))
    got = m.group(1).strip("\n") if m else None
    body = got.split("\n")[1:-1] if got else None        # between "$Classes = [ordered]@{" and "}"
    ok = body == want.split("\n")
    print("bat_growables.ps1 class table:", "matches" if ok else "DIFFERS")
    if not ok:
        print(want)
    return 0 if ok else 1


def cmd_build(a):
    files, ini, rep = build(Game(a.game))
    for r in rep:
        print(r)
    for rel, b in sorted(files.items()):
        p = os.path.join(a.out, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(b)
        print("wrote %-70s %9d  %s" % (rel, len(b), sha(b)[:16]))
    with open(os.path.join(a.out, INI), "wb") as fh:
        fh.write(ini)


def cmd_compare(a):
    """Build from the sources the PowerShell run started from, compare with what it left in the tree."""
    g = Game(a.game)
    files, ini, rep = build(g)
    st = json.loads(g.read(STATE_DIR + "/state.json"))
    bad = 0
    for rel, b in sorted(files.items()):
        cur = g.read(rel) if g.exists(rel) else None
        same = cur == b
        bad += not same
        print("%-4s %-70s python %s  tree %s" % ("same" if same else "DIFF", rel, sha(b)[:16],
                                                 sha(cur)[:16] if cur is not None else "absent"))
    extra = set(st["files"]) - set(files)
    for rel in sorted(extra):
        print("DIFF %s written by the script, not by python" % rel)
        bad += 1
    same = g.read(INI) == ini
    bad += not same
    print("%-4s %s" % ("same" if same else "DIFF", INI))
    print("compare: %d difference(s)" % bad)
    return 1 if bad else 0


def cmd_list(a):
    g = Game(a.game)
    t = class_table(g)
    old = ini_parse(g.read(INI)) if g.exists(INI) else []
    for e in ini_merge(g, t, bat_buildings(g), old):
        v = validate(t, e)
        print("[%d] %-28s bat %08X size %d  %s" % (e["id"], e["name"], e["bat"], e["size"],
                                                  v if isinstance(v, str) else "class %d weight %d base %d" % (v[0], v[1], v[2][0])))


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("tables", "check-ps", "compare", "list"):
        s = sub.add_parser(n)
        s.add_argument("--game", required=True)
    s = sub.add_parser("build")
    s.add_argument("--game", required=True)
    s.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    try:
        return {"tables": cmd_tables, "check-ps": cmd_check_ps, "build": cmd_build, "compare": cmd_compare,
                "list": cmd_list}[a.cmd](a) or 0
    except BatError as e:
        print("batgrow: %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
