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

Civic looks (task civicstyle 2026-11-21, "civic": true on an entry): the set exemplars of the stock civic buildings and
parks a civic button builds (CIVIC_BASES, re/analysis/CIVIC_REWARD.md section 1) are copied the same way (verbatim,
id + offset, their frame tables and pixels), with NO family line: nothing grows them. sc3resize CIVSTYLE offers them in
the civic list window. The set exemplar keeps the base's type id (prop 0x65) and footprint (prop 0x66 x and z; only
the height differs), checked here for every copy, so the copy is counted, covered and priced as its base
(CIVIC_REWARD.md 1.1). The "00000000" entry with "civic": true adds the stock exemplar of every civic base another
civic entry re-skins, so a city whose own set re-skins it can still place the North American look.

Reward looks (task rewardlook 2026-11-25, "rewards": true on an entry): the same for the reward and business-deal
buildings whose exemplar a set re-skins (REWARD_BASES: the exemplar the City Planner catalog offers, read of the two set
archives against Advisor-CityPlanner.ini [REWARD_BUILDINGS] / [BUSINESS_DEAL_BUILDINGS], verify/rewardlook/RESULTS.md).
Copied verbatim at id + offset, no family line, type id and footprint checked like the civic copies, so the City
Planner, which keys "placed" by type id (SIMADV 0x1000b32a), counts a copy as the reward itself. sc3resize REWARDLOOK
offers them after a pick in the Rewards list. The "00000000" entry with "rewards": true adds the stock exemplar of every
reward another "rewards" entry re-skins.

Lot colours (task stylepal 2026-11-24, "lot_colour" on an entry, netpack_lotcolour.py): the grown copies' lot ground
(lawn, garden soil) recoloured per building toward the host style's art of the same id, at build time. "lawn_soil" on
a European / Asian entry (host = the North American art), "lawn" on the "00000000" entry (host = the other sets' art;
the North American copies then get their own frame tables and pixels, group NA_PIX_GROUP, so stock art never changes).
Civic copies are not recoloured.
"""
import os
import re
import struct

import netpack_lotcolour as LC                     # task stylepal: the copies' lot ground follows the host style

BLD_TYPE, BLD_GROUP = 0x207EDC0E, 0x57E
CS_TYPES = (0x6300, 0x6301)                       # frame tables ("BIN\r", 15-byte frame entries from +0x18)
PIX_TYPES = (0, 1)                                # pixels, anchor
SET_DIR = "Apps/Res/Sprites/BuildingSets"
PIX_FILE = "Apps/Res/Sprites/%08X_netpack_set.DAT"
KEY_RE = re.compile(rb"Key:\s*(\d+),(\d+),(\d+),(\d+)")


# task civicstyle: base instances of the stock civic exemplars {0x207EDC0E, 0x57E, inst} the civic commands build:
# the 17 plain ones (SIMGEOM 0x1000a896 -> 0x1000b1a3) and the Marina (0x1000afc0, shore tool). CIVIC_REWARD.md 1.
CIVIC_BASES = (0xd2, 0x1f41, 0xd3, 0xd1, 0x1f94, 0xd6, 0xf5, 0xd4, 0xd, 0xd5, 0xda, 0xd7, 0x234b, 0x234c, 0x234e,
               0x1f96, 0xed, 0xf8)

# task rewardlook: instances of the stock reward / business deal exemplars a building set re-skins (every reward and deal
# type of Advisor-CityPlanner.ini, its exemplars in Apps/Res/Occupant, checked against both set archives 2026-11-25):
# Mayor's House 243 (Asian), City Hall 208 (E, A), County Courthouse 8013 (E, A), Historic Statue 219 (A),
# Lighthouse 8019 (E, A), Performing Arts Center 8011 (A), Stadium 8020 (E, A; the other type-14600 exemplar 16333 has
# no set art), Stock Exchange 8017 (E, A), GigaMall 8085 (a business deal, E, A). The other 15 reward / deal types
# (the four-piece Military Base, University and Theme Park among them) have no set exemplar.
REWARD_BASES = (243, 208, 8013, 219, 8019, 8011, 8020, 8017, 8085)


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


def _u32s(buf, prop, props_fn):
    for p, t, n, off, ln in props_fn(buf):
        if p == prop and t == 3:
            return struct.unpack_from("<%dI" % n, buf, off)
    return None


def _civic_check(np, where, bid, ex, base_ex):
    """the copy must keep its base's type id (0x65) and footprint (0x66 x and z)"""
    t1, t0 = _u32s(ex, 0x65, np.tkb1_props), _u32s(base_ex, 0x65, np.tkb1_props)
    l1, l0 = _u32s(ex, 0x66, np.tkb1_props), _u32s(base_ex, 0x66, np.tkb1_props)
    if not t1 or t1 != t0:
        raise StyleError("%s: civic %d: type %r differs from the base's %r" % (where, bid, t1, t0))
    if not l1 or not l0 or len(l1) != 3 or len(l0) != 3 or (l1[0], l1[2]) != (l0[0], l0[2]):
        raise StyleError("%s: civic %d: lot %r differs from the base's %r" % (where, bid, l1, l0))


def _base_entry(stock, fams, stock_buildings, s, where, set_id, offset, weight, reskinned, pname, civic=(), rewards=()):
    """task stylepick (2026-11-21): set "00000000" = North American copies. For every family member that another set
    of the same manifest re-skins, the BASE exemplar (stock Occupant/*.IXF, verbatim) re-keyed at id + offset. Its
    prop 0x67 names the stock frame table, which no set archive shadows (sets only shadow the TKB1 exemplar at the base
    key, BUILDING_PICK.md section 0), so the copy draws the North American art even while a city's own building set
    is European or Asian. No frame tables or pixels are added. sc3netmod STYLEPICK serves these lines only when a city
    with a set skin asks for North American art; with STYLEPICK off it drops them, so the stock mix ratio is kept."""
    exemplars, lines, civ = [], [], []
    for bid in sorted(civic) + sorted(rewards):    # task civicstyle / rewardlook: North American looks, no family line
        nid = bid + offset
        if nid in stock_buildings:
            raise StyleError("%s: id %d (%d + offset) already has a stock building exemplar" % (where, nid, bid))
        exemplars.append((nid, stock_buildings[bid][1]))
        civ.append(bid)
    for bid in sorted(reskinned):
        nid = bid + offset
        if nid in stock_buildings:
            raise StyleError("%s: id %d (%d + offset) already has a stock building exemplar" % (where, nid, bid))
        if bid not in stock_buildings:
            raise StyleError("%s: base exemplar %d not found in Apps/Res/Occupant" % (where, bid))
        exemplars.append((nid, stock_buildings[bid][1]))
        for f, w in reskinned[bid]:
            lines.append({"family": f, "id": nid, "weight": w * weight,
                          "comment": "%d [North American copy]" % bid})
    if not lines:
        raise StyleError("%s: no other set of this manifest re-skins a family member" % where)
    return {"set": set_id, "offset": offset, "weight": weight, "where": where, "_pack": pname,
            "exemplars": exemplars, "tables": [], "pix_group": None, "pixels": [], "lines": lines,
            "families": sorted({ln["family"] for ln in lines}), "civic": sorted(civic), "rewards": sorted(rewards)}


def compile_entries(np, stock, man, buildfam, stock_buildings):
    """-> [style dict] for one package. np = the netpack module (TKB1 helpers)."""
    pname = man["name"]
    fams = family_members(stock, buildfam)
    out = []
    seen_sets = set()
    reskinned = {}                                 # task stylepick: base id -> [(family, weight)] any set re-skins
    civic_skinned = set()                          # task civicstyle: civic bases a "civic" entry re-skins
    reward_skinned = set()                         # task rewardlook: reward bases a "rewards" entry re-skins
    base_spec = None
    for n, s in enumerate(man.get("style_sets", [])):
        where = "%s style_set %d (%s)" % (pname, n + 1, s.get("set"))
        try:
            set_id = int(str(s["set"]), 16)
        except ValueError:
            raise StyleError("%s: set must be the set's folder name in hex, e.g. e523f3fb" % where)
        if set_id in seen_sets:
            raise StyleError("%s: set listed twice" % where)
        seen_sets.add(set_id)
        lc = s.get("lot_colour")
        if lc is not None and lc not in LC.MODES:
            raise StyleError("%s: lot_colour must be one of %s" % (where, ", ".join(LC.MODES)))
        if set_id == 0:                            # task stylepick: North American copies, built after the sets
            base_spec = (n, s, where)
            continue
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
        civ = []                                   # task civicstyle: civic set exemplars, copied with no family line
        if s.get("civic"):
            for bid in CIVIC_BASES:
                if bid in set_bld and bid not in members:
                    if bid not in stock_buildings:
                        raise StyleError("%s: civic base %d has no stock exemplar" % (where, bid))
                    _civic_check(np, where, bid, set_bld[bid], stock_buildings[bid][1])
                    civ.append(bid)
            civic_skinned.update(civ)
        rew = []                                   # task rewardlook: reward set exemplars, the same way
        if s.get("rewards"):
            for bid in REWARD_BASES:
                if bid in set_bld and bid not in members:
                    if bid not in stock_buildings:
                        raise StyleError("%s: reward base %d has no stock exemplar" % (where, bid))
                    _civic_check(np, where, bid, set_bld[bid], stock_buildings[bid][1])
                    rew.append(bid)
            reward_skinned.update(rew)
        for bid, fl in members.items():            # task stylepick: union over the sets, for the base copies
            have = reskinned.setdefault(bid, [])
            for fw in fl:
                if fw not in have:
                    have.append(fw)
        exemplars, tables, pix_keys, lines = [], {}, [], []
        pix_seen = set()
        for bid in sorted(members) + civ + rew:
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
            for f, w in members.get(bid, ()):
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
                    "families": sorted({ln["family"] for ln in lines}), "civic": civ, "rewards": rew,
                    "_lot": {"mode": lc, "idx": idx, "set_bld": set_bld, "members": sorted(members)}})
    if base_spec:
        n, s, where = base_spec
        offset, weight = s["offset"], s.get("weight", 1)
        if not isinstance(offset, int) or offset <= 0xFFFF:
            raise StyleError("%s: offset must be an integer above 65535 (ids stay clear of netpack's 16-bit ids)" % where)
        if not isinstance(weight, int) or weight < 1:
            raise StyleError("%s: weight must be a positive integer (0 drops the line, SIMGEOM 0x10001250)" % where)
        out.append(_base_entry(stock, fams, stock_buildings, s, where, 0, offset, weight, reskinned, pname,
                               sorted(civic_skinned) if s.get("civic") else (),
                               sorted(reward_skinned) if s.get("rewards") else ()))
        out[-1]["_lot"] = {"mode": s.get("lot_colour"), "members": sorted(reskinned)}
    if any(e["_lot"]["mode"] for e in out):
        _lot_colour(np, stock, stock_buildings, out)
    for e in out:
        e.pop("_lot", None)
    return out


class _StockArt:
    """stock frame tables (CSATTRIB*.IXF) and pixel + anchor records (Res\\Sprites\\*.DAT), first container in name
    order wins, read once."""

    def __init__(self, stock):
        self.tables, self.pix, self.groups = {}, {}, set()
        sp = "Apps/Res/Sprites"
        for n in stock.listdir(sp):
            low = n.lower()
            if not (low.endswith(".dat") or (low.startswith("csattrib") and low.endswith(".ixf"))):
                continue
            try:
                recs = stock.records(sp + "/" + n)
            except Exception:                      # not a DBPF container
                continue
            raw = {}
            for g, i, t, p in recs:
                self.groups.add(g)
                if t in CS_TYPES:
                    self.tables.setdefault((t, g, i), p)
                elif t in PIX_TYPES:
                    raw.setdefault((g, i), {}).setdefault(t, p)
            for k, d in raw.items():
                if 0 in d and 1 in d:
                    self.pix.setdefault(k, (d[0], d[1]))


def _set_pix(idx):
    return {(g, i): (idx[(0, g, i)], idx[(1, g, i)]) for (t, g, i) in idx if t == 0 and (1, g, i) in idx}


def _lot_n(np, ex):
    lot = _u32s(ex, 0x66, np.tkb1_props)
    if not lot or len(lot) != 3 or lot[0] != lot[2] or lot[0] < 1:
        return None
    return lot[0]


def _lot_colour(np, stock, stock_buildings, out):
    """task stylepal: recolour the grown copies' lot ground per building (netpack_lotcolour.py). Fills e["lot_colour"]."""
    art = _StockArt(stock)
    for g in (LC.NA_CS_GROUP, LC.NA_PIX_GROUP):
        if g in art.groups:
            raise StyleError("lot_colour: group 0x%08X is already used by a stock sprite container" % g)
    sets = [e for e in out if e["set"] != 0]
    spix = {e["set"]: _set_pix(e["_lot"]["idx"]) for e in sets}

    def stock_frames(bid):
        k = np.tkb1_key(stock_buildings[bid][1], 0x67)
        tab = art.tables.get(tuple(k)) if k else None
        return k, tab, (LC.zoom3_frames(tab, art.pix) if tab else None)

    def set_frames(e, bid):
        k = np.tkb1_key(e["_lot"]["set_bld"][bid], 0x67)
        tab = e["_lot"]["idx"][(k[0], k[1], k[2])]
        return tab, LC.zoom3_frames(tab, spix[e["set"]])

    for e in out:
        mode = e["_lot"]["mode"]
        rep = {"mode": mode, "buildings": 0, "records": 0, "unchanged": 0, "skipped": []}
        e["lot_colour"] = rep
        if not mode:
            continue
        if e["set"] != 0:                          # European / Asian copies: host = the stock art of the same id
            owner = {}
            for bid in e["_lot"]["members"]:
                n = _lot_n(np, stock_buildings[bid][1])
                host = stock_frames(bid)[2]
                tab, mine = set_frames(e, bid)
                if n is None or host is None or mine is None:
                    rep["skipped"].append(bid)
                    continue
                p = LC.params(LC.stats(LC.lot_pixels(mine, n)), LC.stats(LC.lot_pixels(host, n)), mode)
                if p is None:
                    rep["unchanged"] += 1
                    continue
                rep["buildings"] += 1
                for _, g, i in LC.table_refs(tab):
                    if (g, i) in spix[e["set"]]:
                        owner.setdefault((g, i), (bid, n, p))      # a record two tables share: the lower id's look
            pixels = []
            for g, i, t, pl in e["pixels"]:
                if t == 0 and (g, i) in owner:
                    _, n, p = owner[(g, i)]
                    pl = LC.recolour(pl, spix[e["set"]][(g, i)][1], n, p)
                    rep["records"] += 1
                pixels.append((g, i, t, pl))
            e["pixels"] = pixels
            continue
        # North American copies: host = the other sets' art of the same id, pooled. Own tables + pixels.
        pos = {nid - e["offset"]: j for j, (nid, _) in enumerate(e["exemplars"])}
        exemplars, tables, pixels, nxt = list(e["exemplars"]), [], [], 0
        for bid in e["_lot"]["members"]:
            n = _lot_n(np, stock_buildings[bid][1])
            k, tab, mine = stock_frames(bid)
            hosts = [h for h in (set_frames(s, bid)[1] for s in sets if bid in s["_lot"]["set_bld"]) if h]
            if n is None or mine is None or not hosts:
                rep["skipped"].append(bid)
                continue
            host_lab = LC.np.concatenate([LC.lot_pixels(h, n) for h in hosts])
            p = LC.params(LC.stats(LC.lot_pixels(mine, n)), LC.stats(host_lab), mode)
            if p is None:
                rep["unchanged"] += 1
                continue
            keymap = {}
            for _, g, i in LC.table_refs(tab):
                if (g, i) in art.pix and (g, i) not in keymap:
                    keymap[(g, i)] = (LC.NA_PIX_GROUP, nxt)
                    pl, anc = art.pix[(g, i)]
                    pixels.append((LC.NA_PIX_GROUP, nxt, 1, anc))
                    pixels.append((LC.NA_PIX_GROUP, nxt, 0, LC.recolour(pl, anc, n, p)))
                    nxt += 1
                    rep["records"] += 1
            nid = bid + e["offset"]
            tables.append((LC.NA_CS_GROUP, nid, k[0], LC.retarget(tab, keymap)))
            j = pos[bid]
            exemplars[j] = (nid, np.tkb1_set_key(exemplars[j][1], 0x67, (k[0], LC.NA_CS_GROUP, nid)))
            rep["buildings"] += 1
        if pixels:
            e["exemplars"], e["tables"], e["pix_group"], e["pixels"] = exemplars, tables, LC.NA_PIX_GROUP, pixels
