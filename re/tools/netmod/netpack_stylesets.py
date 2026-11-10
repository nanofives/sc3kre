r"""netpack_stylesets.py - task stylemix (2026-11-10): the building styles grow side by side, at random, in one city.

Manifest key (netpack.schema.json $defs/style_set):

  "style_sets": [{"set": "e523f3fb", "offset": 400000,  "weight": 1},
                 {"set": "6523f3d5", "offset": 1500000, "weight": 1}]

Why it is needed (re/analysis/BUILDING_PICK.md sections 0, 3, 6 A): a building set adds no ids. Its TKB1 records sit
at the SAME occupant keys as the base buildings and only point at other art (prop 0x67), and SetCityScheme
(SIMINIT 0x10006589) registers the set DATs FRONT in GZResourceD, so a key answers with one style or the other, never
both. So each style variant needs its own occupant id, and the set's art has to be reachable while the active set
stays 0.

What one entry becomes, for every set exemplar that is a member of a BUILDFAM family:

  exemplar     the SET's TKB1 record, verbatim, re-keyed {0x207EDC0E, 0x57E, id + offset}. prop 0x67 (the set's frame
               table) and prop 0x6D (the set's name, group 0x453BBDE0, SC3MBEStringsBuildings.IXF, a stock
               [DBSegments] row) are left as they are. Goes into OccupantAttribs_Korea.IXF ([OccAttribCache] Entry5:
               an exemplar outside the attrib cache crashed SIMRCI 0x10026D6D, verify/growable arm OC).
  frame tables the set's 0x6300 / 0x6301 records named by prop 0x67, verbatim (keys unchanged: the set's own group,
               0x5432D60F / 0x547B7DF6, which no stock container uses), into CSAttrib_Korea.IXF ([DBSegments]).
  pixels       every type 0 (pixels) and type 1 (anchor) record those tables name, verbatim, in the set DAT's own
               index order, into Res\Sprites\<group>_netpack_set.DAT (Res\Sprites\*.DAT is enumerated at startup as
               SC3DBSegmentSprite, SC3U cSC3App::LoadRegistry 0x0040b761).
  family lines "Key: 1406,545184782,<id + offset>,<member weight * weight>" in each family that lists the base id,
               inserted after BuildingCount with the count raised (netpack_growables.patch_buildfam, the same line
               insert growables use), so stock members and other packages' lines are kept.

Mix ratio: a family member X of weight w keeps its stock line (weight w, base style) and gains one line per set that
re-skins X, at weight w * weight. With weight 1 for both sets a member that both sets re-skin grows in each style a
third of the time. Members a set does not re-skin keep the base art, exactly as in a stock set city.

The new ids are above 0xFFFF, so they never collide with netpack variant / growable ids (frame-table, name and
pixel keys of those are keyed by a 16-bit id); they do share the building occupant key space with growables, so the
merge checks them against every stock exemplar and every other package.
"""
import os
import re
import struct

BLD_TYPE, BLD_GROUP = 0x207EDC0E, 0x57E
CS_TYPES = (0x6300, 0x6301)                       # frame tables ("BIN\r", 15-byte frame entries from +0x18)
PIX_TYPES = (0, 1)                                # pixels, anchor
SET_DIR = "Apps/Res/Sprites/BuildingSets"
PIX_FILE = "Apps/Res/Sprites/%08X_netpack_set.DAT"
KEY_RE = re.compile(rb"Key:\s*(\d+),(\d+),(\d+),(\d+)")


class StyleError(Exception):
    pass


def set_files(stock, set_id):
    """-> [rel] of the set's archives (the folder SetCityScheme scans, FUN_1000641b: Res\\Sprites\\BuildingSets\\%08lX\\*.DAT)."""
    d = "%s/%08x" % (SET_DIR, set_id)
    names = [n for n in stock.listdir(d) if n.lower().endswith(".dat")]
    if not names:
        d = "%s/%08X" % (SET_DIR, set_id)
        names = [n for n in stock.listdir(d) if n.lower().endswith(".dat")]
    return ["%s/%s" % (d, n) for n in names]


def family_members(stock, buildfam):
    """-> {family instance: [(id, weight)]} in file order."""
    out = {}
    for g, i, t, p in stock.records(buildfam):
        if t == 0x81F53D09 and g == 0x01F58D3D:
            out[i] = [(int(m.group(3)), int(m.group(4))) for m in KEY_RE.finditer(p)
                      if int(m.group(1)) == BLD_GROUP and int(m.group(2)) == BLD_TYPE]
    return out


def _frame_refs(buf, pix_idx):
    """(group, instance) of every frame of a BIN\\r table: 15-byte entries (u16 frame, u32 group, u32 inst, u8 flag)
    from +0x18 (newpiece.cs_frames reads 0x6300 this way; the 0x6301 tables use the same stride, checked on the data:
    every entry from +0x18 names a record of the set DAT)."""
    if buf[:4] != b"BIN\r":
        raise StyleError("not a BIN\\r frame table")
    out = []
    for o in range(0x18, len(buf) - 14 + 1, 15):
        g, i = struct.unpack_from("<II", buf, o + 2)
        if (g, i) in pix_idx:
            out.append((g, i))
    return out


def _text(buf, prop, props_fn):
    for p, t, n, off, ln in props_fn(buf):
        if p == prop and t == 7:
            return buf[off + 4:off + ln].decode("cp1252", "replace")
    return None


def compile_entries(np, stock, man, buildfam, stock_buildings):
    """-> [style dict] for one package. np = the netpack module (TKB1 helpers)."""
    pname = man["name"]
    fams = family_members(stock, buildfam)
    out = []
    seen_sets = set()
    for n, s in enumerate(man.get("style_sets", [])):
        where = "%s style_set %d (%s)" % (pname, n + 1, s.get("set"))
        try:
            set_id = int(str(s["set"]), 16)
        except ValueError:
            raise StyleError("%s: set must be the set's folder name in hex, e.g. e523f3fb" % where)
        if set_id in seen_sets:
            raise StyleError("%s: set listed twice" % where)
        seen_sets.add(set_id)
        offset, weight = s["offset"], s.get("weight", 1)
        if not isinstance(offset, int) or offset <= 0xFFFF:
            raise StyleError("%s: offset must be an integer above 65535 (ids stay clear of netpack's 16-bit ids)" % where)
        if not isinstance(weight, int) or weight < 1:
            raise StyleError("%s: weight must be a positive integer (0 drops the line, SIMGEOM 0x10001250)" % where)
        only = set(s.get("families") or fams)
        bad = only - set(fams)
        if bad:
            raise StyleError("%s: BUILDFAM.IXF has no family %s" % (where, sorted(bad)))
        files = set_files(stock, set_id)
        if not files:
            raise StyleError("%s: no *.DAT in %s/%08x" % (where, SET_DIR, set_id))
        idx, order = {}, []
        for rel in files:
            for g, i, t, p in stock.records(rel):
                if (t, g, i) not in idx:
                    idx[(t, g, i)] = p
                    order.append((t, g, i))
        pix_idx = {(g, i) for (t, g, i) in idx if t == 0} & {(g, i) for (t, g, i) in idx if t == 1}
        set_bld = {i: idx[(t, g, i)] for (t, g, i) in order if t == BLD_TYPE and g == BLD_GROUP}
        members = {}                               # id -> [(family, weight)]
        for f in sorted(only):
            for bid, w in fams[f]:
                if bid in set_bld and w > 0:
                    members.setdefault(bid, []).append((f, w))
        if not members:
            raise StyleError("%s: the set re-skins no family member" % where)
        exemplars, tables, pix_keys, lines = [], {}, [], []
        pix_seen = set()
        for bid in sorted(members):
            nid = bid + offset
            if nid in stock_buildings:
                raise StyleError("%s: id %d (%d + offset) already has a stock building exemplar" % (where, nid, bid))
            ex = set_bld[bid]
            np.tkb1_props(ex)                      # walk check
            key = np.tkb1_key(ex, 0x67)
            if not key or len(key) != 3 or key[0] not in CS_TYPES or tuple(key) not in idx:
                raise StyleError("%s: set exemplar %d: frame table %r not in the set archives" % (where, bid, key))
            k = tuple(key)
            if k not in tables:
                refs = _frame_refs(idx[k], pix_idx)
                if not refs:
                    raise StyleError("%s: frame table {0x%X,0x%X,%d} names no pixel record of the set" % ((where,) + k))
                tables[k] = idx[k]
                for r in refs:
                    if r not in pix_seen:
                        pix_seen.add(r)
                        pix_keys.append(r)
            name = _text(ex, 0x64, np.tkb1_props) or str(bid)
            exemplars.append((nid, ex))
            for f, w in members[bid]:
                lines.append({"family": f, "id": nid, "weight": w * weight,
                              "comment": ("%s [set %08x]" % (name, set_id)).replace("\r", " ").replace("\n", " ")})
        groups = {g for g, _ in pix_keys}
        if len(groups) != 1:
            raise StyleError("%s: pixel records span groups %s (one DAT per group expected)" % (where, sorted(groups)))
        pix_group = groups.pop()
        pix = [(g, i, t, idx[(t, g, i)]) for (t, g, i) in order if t in PIX_TYPES and (g, i) in pix_seen]
        out.append({"set": set_id, "offset": offset, "weight": weight, "where": where, "_pack": pname,
                    "exemplars": exemplars, "tables": [(k[1], k[2], k[0], p) for k, p in sorted(tables.items())],
                    "pix_group": pix_group, "pixels": pix, "lines": lines,
                    "families": sorted({ln["family"] for ln in lines})})
    return out
