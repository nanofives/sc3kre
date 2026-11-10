r"""netpack_growables.py - task growable (2026-11-10): custom zoned buildings ADDED to the pool that grows in zones.

Manifest key (netpack.schema.json $defs/growable):

  "growables": [{"id": 36001, "base": 3065, "family": 11, "weight": 50,
                 "name": {"*": "Red test house"}, "art": {"recolor": "red"}}]

What one entry becomes (re/analysis/BUILDING_PICK.md section 6 C, verify/growable/RESULTS.md):

  exemplar     the base building's TKB1 record re-keyed {0x207EDC0E, 0x57E, id}; prop 0x67 -> {0x6300, 0x55908ADB, id}
               (the Korea frame table), prop 0x6D -> {0x2026960B, 0xA1096A4F, id} when named, prop 0x64 = the name.
               Goes into OccupantAttribs_Korea.IXF next to the network variants (different group, no key clash).
  frame table  the art source's table, frames pointed at the new pixel records, in CSAttrib_Korea.IXF.
  pixels       netpack's merged 4E3D00nn_netpack.DAT, keys (group, id << 16 | ordinal).
  family line  "Key: 1406,545184782,<id>,<weight>" inserted right after BuildingCount in BUILDFAM.IXF record
               {0x81F53D09, 0x01F58D3D, family}, BuildingCount raised by one. The parser SIMGEOM 0x10001250 reads
               LandUse, BuildingCount, then Key lines until BuildingCount resolve (an unresolved key lowers the
               count), so a line inserted first is read whatever the family's original count was. The weight is the
               number of times the attrib is pushed into the rule's draw list (BUILDING_PICK.md 2, 0x100274bb).

Ids share one space with netpack variants (frame-table and name instances are keyed by id) and must fit 16 bits
(pixel keys are id << 16 | ordinal).
"""
import re
import struct

BLD_TYPE, BLD_GROUP = 0x207EDC0E, 0x57E          # building occupant exemplar key {type, group, id}
FAM_TYPE, FAM_GROUP = 0x81F53D09, 0x01F58D3D     # BUILDFAM.IXF family records
BUILDFAM = "Apps/Res/BUILDFAM.IXF"


class GrowError(Exception):
    pass


def buildings(stock):
    """-> {id: (container rel, payload)} of building exemplars over every Occupant\\*.IXF (first in name order)."""
    if getattr(stock, "_bld", None) is None:
        stock._bld = {}
        for n in stock.listdir("Apps/Res/Occupant"):
            if n.lower().endswith(".ixf"):
                rel = "Apps/Res/Occupant/" + n
                for g, i, t, p in stock.records(rel):
                    if t == BLD_TYPE and g == BLD_GROUP:
                        stock._bld.setdefault(i, (rel, p))
    return stock._bld


def families(stock):
    """-> {instance: payload} of the BUILDFAM.IXF family records."""
    return {i: p for g, i, t, p in stock.records(BUILDFAM) if t == FAM_TYPE and g == FAM_GROUP}


def family_landuse(payload):
    m = re.search(rb"LandUse:\s*(\d+)", payload)
    return int(m.group(1)) if m else None


def tkb1_set_text(buf, prop, text, props_fn):
    """Replace a type-7 (u32 length + text) property's text -> new TKB1 bytes."""
    for p, t, n, off, ln in props_fn(buf):
        if p == prop:
            if t != 7:
                raise GrowError("prop 0x%x is type %d, not text" % (prop, t))
            b = text.encode("cp1252")
            return buf[:off] + struct.pack("<I", len(b)) + b + buf[off + ln:]
    raise GrowError("prop 0x%x not present" % prop)


def tkb1_u32(buf, prop, props_fn):
    for p, t, n, off, ln in props_fn(buf):
        if p == prop and t == 3:
            return struct.unpack_from("<%dI" % n, buf, off)
    return None


def compile_entries(np, stock, pack_dir, man, names_fn, langs_text):
    """np = the netpack module (art + TKB1 helpers). -> [growable dict] for one package."""
    pname = man["name"]
    bld = buildings(stock)
    fams = families(stock)
    out = []
    for n, g in enumerate(man.get("growables", [])):
        where = "%s growable %d (id %s)" % (pname, n + 1, g.get("id"))
        gid, base, fam, weight = g["id"], g["base"], g["family"], g.get("weight", 1)
        if not 0 < gid <= 0xFFFF:
            raise GrowError("%s: id must fit 16 bits (pixel record keys are id << 16 | ordinal)" % where)
        if gid in bld:
            raise GrowError("%s: id %d already has a stock building exemplar (%s)" % (where, gid, bld[gid][0]))
        if base not in bld:
            raise GrowError("%s: base %d has no stock building exemplar {0x207EDC0E, 0x57E, id}" % (where, base))
        if fam not in fams:
            raise GrowError("%s: BUILDFAM.IXF has no family record %d" % (where, fam))
        if not isinstance(weight, int) or weight < 1:
            raise GrowError("%s: weight must be a positive integer (0 drops the line, SIMGEOM 0x10001250)" % where)
        lu = family_landuse(fams[fam])
        base_lu = tkb1_u32(bld[base][1], 0x65, np.tkb1_props)
        if not base_lu or base_lu[0] != lu:
            raise GrowError("%s: base %d LandUse (prop 0x65) %s differs from family %d LandUse %s; every stock "
                            "family member matches its family (BUILDING_PICK.md 2)" % (where, base, base_lu, fam, lu))
        art_spec = g.get("art")
        if art_spec and art_spec.get("from") is not None and art_spec["from"] not in bld:
            raise GrowError("%s: art.from %d has no stock building exemplar" % (where, art_spec["from"]))
        try:
            art = np.compile_art(stock, pack_dir, art_spec, base, where, exemplars=bld)
        except np.NetpackError as e:
            raise GrowError(str(e))
        ex = np.tkb1_set_key(bld[base][1], 0x67, (np.CS_TYPE, np.KOREA_CS_GROUP, gid))
        names = names_fn(g, langs_text)
        if names:
            if np.tkb1_key(ex, 0x6D) is None:
                raise GrowError("%s: base %d exemplar has no name key (prop 0x6D)" % (where, base))
            ex = np.tkb1_set_key(ex, 0x6D, (np.TEXT_TYPE, np.TEXT_GROUP, gid))
            first = names.get("ENGLISH") or sorted(names.items())[0][1]
            ex = tkb1_set_text(ex, 0x64, first, np.tkb1_props)
        np.tkb1_props(ex)                                   # walk check: the record still parses end to end
        out.append({"id": gid, "base": base, "family": fam, "landuse": lu, "weight": weight, "art": art,
                    "exemplar": ex, "names": names, "where": where, "_pack": pname,
                    "comment": (names or {}).get("ENGLISH") or "netpack %s" % pname})
    return out


def patch_buildfam(stock_bytes, growables, ixf_parse, replace_records):
    """-> new BUILDFAM.IXF bytes with each growable's Key line in its family (package name order, then id)."""
    by_fam = {}
    for g in growables:
        by_fam.setdefault(g["family"], []).append(g)
    cur = {s[1]: stock_bytes[s[3]:s[3] + s[4]] for s in ixf_parse.read_index_slots(stock_bytes)
           if s[0] == FAM_GROUP and s[2] == FAM_TYPE}          # slot = (group, instance, type, offset, size)
    new = []
    for fam, lst in sorted(by_fam.items()):
        text = cur[fam]
        m = re.search(rb"BuildingCount:\s*(\d+)[^\r\n]*\r?\n", text)
        if not m:
            raise GrowError("BUILDFAM family %d has no BuildingCount line" % fam)
        count = int(m.group(1)) + len(lst)
        lines = b"".join(b"Key: 1406,545184782,%d,%d   %s\r\n" % (g["id"], g["weight"], g["comment"].encode("cp1252"))
                         for g in lst)
        text = text[:m.start()] + b"BuildingCount: %d\r\n" % count + lines + text[m.end():]
        new.append((FAM_GROUP, fam, FAM_TYPE, text))
    return replace_records(stock_bytes, new)
