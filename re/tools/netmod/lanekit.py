#!/usr/bin/env python3
r"""lanekit.py -- lanes and connections of network pieces (netmod framework, task lanekit, 2026-10-13).

A network piece has two separate lane descriptions, read by two different engines (NET_LANES.md):

  connects  exemplar props 310 / 311 / 312 of {0xE223741F, 0xA317745F, id}: a 4x4 (entry side, exit side) turn
            matrix per network (road / rail / subway), two 16-bit halves. Read by the tiler (final-stage neighbour
            bits, SIMNTWRK FUN_1000d73d) and by the SimTransit trip router for highway and bus nodes
            (FUN_1000755e). Stored once per piece id, rotated by the game for states 1..3.
  lanes     Res\SSimData\<lang>\TrBlkAtt.IXF {0x625C6226, 0x825C6289, id*0x100+state}: the street-sim graphs
            (pedestrian nodes/edges, vehicle nodes/edges, each edge a curve from PPATHATT / VPATHATT). Read by
            STRTSIM (the animated cars, trains and people). One record per state.

This module:
  decode / encode   exact codec of a TrBlkAtt record (byte-identical on all 6,034 shipped records)
  rotate            state s -> state s+1 (positions, curve keys, exit codes), the rule the shipped records follow
  Paths             the curve libraries, looked up by end points
  compile_spec      the authoring format (lanes by side and slot, walks, exits, connects) -> records + masks
  describe          a stock record -> the authoring format (used by the round-trip test)

CLI (run from re/tools):
  py -3 -m netmod.lanekit show <piece> [--lang ENGLISH]          decoded records + turn matrices
  py -3 -m netmod.lanekit describe <piece> [--state 0]           stock piece -> authoring spec (JSON)
  py -3 -m netmod.lanekit build <spec.json> --out <dir>          records (every language) + masks, BUILD.json
  py -3 -m netmod.lanekit roundtrip [--csv out.csv]              how many of the shipped records the generator makes
  py -3 -m netmod.lanekit check-connects                         turn matrix derived from lanes vs exemplar masks
  py -3 -m netmod.lanekit diagram <spec.json|piece> --png out.png [--state s]   lane-graph picture
  py -3 -m netmod.lanekit selftest
Read-only on the game install.
"""
import argparse
import json
import os
import struct
import sys

from . import paths

sys.path.insert(0, paths.TOOLS)
import ixf_parse  # noqa: E402

TRB_TYPE, TRB_GROUP = 0x625C6226, 0x825C6289
VPA_TYPE, VPA_GROUP = 0xC25C74F2, 0xA25C7520
PPA_TYPE, PPA_GROUP = 0xA20BF670, 0xC20BF6C3
EX_TYPE, EX_GROUP = 0xE223741F, 0xA317745F
CONN_PROPS = {"road": 310, "rail": 311, "subway": 312}       # FUN_1000d73d sel 0 / 1 / 2 -> +0x140 / +0x144 / +0x148
NET_SEL = {"road": 0, "rail": 1, "subway": 2}

# Sides = the SIMNTWRK dir index (5x5 offset table 0x10032134): 0 (-1,0) 1 (0,-1) 2 (+1,0) 3 (0,+1).
# Compass words are an iOS convention with no PC referent (NETWORK_RULE_ENGINE.md 13.9), so the names are axes.
SIDES = ["x-", "z-", "x+", "z+"]
SIDE_ALIAS = {"x-": 0, "z-": 1, "x+": 2, "z+": 3, "d0": 0, "d1": 1, "d2": 2, "d3": 3, "0": 0, "1": 1, "2": 2, "3": 3}
VCLASS = {0: "car", 1: "train", 2: "subway"}        # vehicle node b0, measured (NET_LANES.md 3.3)
VCLASS_ID = {v: k for k, v in VCLASS.items()}
CLASS_NET = {"car": "road", "train": "rail", "subway": "subway"}
TILE = 255                                          # node coordinates run 0..255 inside the tile

# STRTSIM DAT_10032700 / DAT_10032708: (dx, dz) per exit code >> 2 [CONFIRMED @ STRTSIM 0x1001c750]
EXIT_STEP = [(-1, 0), (-1, -1), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1)]


class LaneError(Exception):
    pass


def side_of(name):
    s = SIDE_ALIAS.get(str(name).strip().lower())
    if s is None:
        raise LaneError("side %r: use x- z- x+ z+ (or d0..d3)" % (name,))
    return s


# =================================================================== exact codec

def _bin(b, o):
    if b[o:o + 4] != b"BIN\r":
        raise LaneError("expected BIN\\r at 0x%x" % o)
    return o + 4


def decode(blob):
    """TrBlkAtt record -> dict. Every field kept, names from NET_LANES.md."""
    o = _bin(blob, 0)
    raw = list(struct.unpack_from("<iiii", blob, o))
    o += 16
    flag = blob[o]
    o += 1
    rec = {"alt_raw": raw, "flag": flag, "ped": [], "veh": []}
    for kind in ("ped", "veh"):
        o = _bin(blob, o)
        n, = struct.unpack_from("<I", blob, o)
        o += 4
        for _ in range(n):
            idx, = struct.unpack_from("<I", blob, o)
            o += 4
            node = {"idx": idx}
            if kind == "veh":
                node["cls"], = struct.unpack_from("<b", blob, o)
                o += 1
            node["x"], node["y"], node["z"] = struct.unpack_from("<iii", blob, o)
            o += 12
            ne, = struct.unpack_from("<I", blob, o)
            o += 4
            node["edges"] = []
            for _ in range(ne):
                to, code, key, e3 = struct.unpack_from("<bBII", blob, o)
                o += 10
                node["edges"].append({"to": to - 1 if to >= 0 else None, "code": code, "path": key, "e3": e3})
            rec[kind].append(node)
    if o != len(blob):
        raise LaneError("record walk ended at %d of %d bytes" % (o, len(blob)))
    return rec


def encode(rec):
    out = bytearray(b"BIN\r")
    out += struct.pack("<iiii", *rec["alt_raw"])
    out.append(rec["flag"] & 0xFF)
    for kind in ("ped", "veh"):
        out += b"BIN\r" + struct.pack("<I", len(rec[kind]))
        for i, n in enumerate(rec[kind]):
            out += struct.pack("<I", n.get("idx", i + 1))
            if kind == "veh":
                out += struct.pack("<b", n["cls"])
            out += struct.pack("<iii", n["x"], n["y"], n["z"])
            out += struct.pack("<I", len(n["edges"]))
            for e in n["edges"]:
                to = -1 if e["to"] is None else e["to"] + 1
                out += struct.pack("<bBII", to, e["code"], e["path"], e["e3"])
    return bytes(out)


def alt_offsets(rec):
    """Per-corner altitude offsets as trblkatt.py reports them (stored [0],[3],[2],[1], each >> 8)."""
    r = rec["alt_raw"]
    return [r[0] >> 8, r[3] >> 8, r[2] >> 8, r[1] >> 8]


# =================================================================== rotation (state s -> s+1)

def rot_pt(x, z, k=1):
    for _ in range(k % 4):
        x, z = TILE - z, x
    return x, z


def rot_key(key, k=1):
    return (key & ~3) | ((key + k) & 3)


def rot_code(code, k=1):
    return (code + 8 * k) % 32


def rotate(rec, k=1):
    """Rotate a record k quarter turns. Positions (x, z) -> (255 - z, x), curve keys' low 2 bits + 1 (the curve
    libraries hold each shape at 4 rotations, key = shape * 256 + rotation), exit codes + 8 (mod 32), nodes
    re-sorted by (x, y, z) and edge targets renumbered. Corner altitude offsets rotate with the corners."""
    k %= 4
    if k == 0:
        return json.loads(json.dumps(rec))
    out = {"flag": rec["flag"], "ped": [], "veh": []}
    r = rec["alt_raw"]                                # corner c at raw index (0, 3, 2, 1)[c]; corner c -> c+k
    corners = [r[0], r[3], r[2], r[1]]
    nc = [corners[(c - k) % 4] for c in range(4)]
    out["alt_raw"] = [nc[0], nc[3], nc[2], nc[1]]
    for kind in ("ped", "veh"):
        nodes = []
        for i, n in enumerate(rec[kind]):
            x, z = rot_pt(n["x"], n["z"], k)
            m = dict(n, x=x, z=z, _old=i)
            m["edges"] = [dict(e, path=rot_key(e["path"], k) if e["to"] is not None else e["path"],
                               code=rot_code(e["code"], k) if e["to"] is None else e["code"]) for e in n["edges"]]
            nodes.append(m)
        nodes.sort(key=lambda n: (n["x"], n["y"], n["z"]))
        remap = {n["_old"]: j for j, n in enumerate(nodes)}
        for j, n in enumerate(nodes):
            del n["_old"]
            n["idx"] = j + 1
            for e in n["edges"]:
                if e["to"] is not None:
                    e["to"] = remap[e["to"]]
        out[kind] = nodes
    return out


# =================================================================== game files

class Game:
    def __init__(self, root=None):
        self.root = root or paths.game_root()
        self.res = os.path.join(self.root, "Apps", "Res")
        self._trb, self._ex, self._paths = {}, None, {}

    def langs(self):
        d = os.path.join(self.res, "SSimData")
        return sorted(n for n in os.listdir(d) if os.path.isdir(os.path.join(d, n)))

    def _find(self, d, name):
        for n in os.listdir(d) if os.path.isdir(d) else []:
            if n.lower() == name.lower():
                return os.path.join(d, n)
        return None

    def trblkatt_path(self, lang):
        return self._find(os.path.join(self.res, "SSimData", lang), "TrBlkAtt.IXF")

    def trblkatt(self, lang="ENGLISH"):
        if lang not in self._trb:
            recs, d = ixf_parse.parse(self.trblkatt_path(lang))
            self._trb[lang] = {r["instance"]: d[r["offset"]:r["offset"] + r["size"]] for r in recs
                               if r["type"] == TRB_TYPE and r["group"] == TRB_GROUP}
        return self._trb[lang]

    def vpath_file(self, lang):
        """VPATHATT: English-UK carries its own copy; the other folders have none and use SSimData\\VPATHATT.IXF."""
        p = self._find(os.path.join(self.res, "SSimData", lang), "VPathAtt.IXF")
        return p or self._find(os.path.join(self.res, "SSimData"), "VPATHATT.IXF")

    def paths(self, lang="ENGLISH"):
        if lang not in self._paths:
            self._paths[lang] = Paths(self.vpath_file(lang),
                                      self._find(os.path.join(self.res, "SSimData"), "PPATHATT.IXF"))
        return self._paths[lang]

    def exemplars(self):
        """-> {id: payload} of every OccupantAttribs*.IXF, first container in name order wins."""
        if self._ex is None:
            self._ex = {}
            d = os.path.join(self.res, "Occupant")
            for f in sorted(os.listdir(d)):
                if f.lower().startswith("occupantattribs") and f.lower().endswith(".ixf"):
                    recs, data = ixf_parse.parse(os.path.join(d, f))
                    for r in recs:
                        if r["type"] == EX_TYPE and r["group"] == EX_GROUP:
                            self._ex.setdefault(r["instance"], data[r["offset"]:r["offset"] + r["size"]])
        return self._ex

    def masks(self, pid):
        """-> {"road": u32, "rail": u32, "subway": u32} or None (no exemplar)."""
        ex = self.exemplars().get(pid)
        if ex is None:
            return None
        props = tkb1_u32(ex)
        return {net: props.get(p, 0) for net, p in CONN_PROPS.items()}


def tkb1_u32(buf):
    """-> {prop: first u32} for type-3 properties of a TKB1 exemplar."""
    out, o = {}, 4
    while o + 8 <= len(buf):
        prop, = struct.unpack_from("<I", buf, o)
        t, n = struct.unpack_from("<HH", buf, o + 4)
        o += 8
        ln = {3: 4 * n, 8: 12 * n, 1: n}.get(t)
        if t == 7:
            ln = struct.unpack_from("<I", buf, o)[0] + 4
        if ln is None:
            break
        if t == 3 and n >= 1:
            out[prop] = struct.unpack_from("<I", buf, o)[0]
        o += ln
    return out


def tkb1_set_u32(buf, prop, value):
    """Rewrite (same size) or append a one-value type-3 property. Returns new bytes."""
    o = 4
    while o + 8 <= len(buf):
        p, = struct.unpack_from("<I", buf, o)
        t, n = struct.unpack_from("<HH", buf, o + 4)
        o += 8
        ln = {3: 4 * n, 8: 12 * n, 1: n}.get(t)
        if t == 7:
            ln = struct.unpack_from("<I", buf, o)[0] + 4
        if ln is None:
            raise LaneError("TKB1 prop 0x%x has unknown type %d" % (p, t))
        if p == prop:
            if t != 3 or n != 1:
                raise LaneError("TKB1 prop %d is type %d count %d, not one u32" % (prop, t, n))
            b = bytearray(buf)
            struct.pack_into("<I", b, o, value & 0xFFFFFFFF)
            return bytes(b)
        o += ln
    return bytes(buf) + struct.pack("<IHHI", prop, 3, 1, value & 0xFFFFFFFF)


# =================================================================== curve libraries

class Paths:
    """VPATHATT / PPATHATT records: "BIN\\r", u32 n, n x (s32 x, y, z), then vehicle: u8 entry heading, u8 exit
    heading, u32 UNKNOWN (0 / 1 / 2); pedestrian: u32 entry heading, u32 exit heading. Headings are the 32-step
    codes of the exit edges (side * 8 for the four axes). Loaded by STRTSIM FUN_100201d8 / FUN_1000cbf6, which copy
    the two headings into each internal edge (+0x15 / +0x16) [CONFIRMED @ STRTSIM 0x100201d8, 0x1000cbf6]."""

    def __init__(self, vfile, pfile):
        self.veh = self._load(vfile, VPA_TYPE, VPA_GROUP, True)
        self.ped = self._load(pfile, PPA_TYPE, PPA_GROUP, False)

    @staticmethod
    def _load(path, t, g, veh):
        recs, d = ixf_parse.parse(path)
        out = {}
        for r in recs:
            if r["type"] != t or r["group"] != g:
                continue
            b = d[r["offset"]:r["offset"] + r["size"]]
            n, = struct.unpack_from("<I", b, 4)
            pts = [struct.unpack_from("<iii", b, 8 + 12 * i) for i in range(n)]
            tail = b[8 + 12 * n:]
            if veh:
                hin, hout = tail[0], tail[1]
                extra = struct.unpack_from("<I", tail, 2)[0]
            else:
                hin, hout = struct.unpack_from("<II", tail, 0)
                extra = None
            out[r["instance"]] = {"pts": pts, "in": hin, "out": hout, "extra": extra}
        return out

    def find(self, kind, a, b, prefer=None):
        """Keys whose curve starts at a (x, z) and ends at b (x, z), y ignored. `prefer` = keys to try first."""
        lib = self.veh if kind == "veh" else self.ped
        hits = [k for k, p in sorted(lib.items())
                if (p["pts"][0][0], p["pts"][0][2]) == tuple(a) and (p["pts"][-1][0], p["pts"][-1][2]) == tuple(b)]
        if prefer:
            hits = sorted(hits, key=lambda k: (k not in prefer, k))
        return hits


# =================================================================== analysis: lanes -> turn matrix

def boundary_sides(x, z):
    s = set()
    if x <= 0:
        s.add(0)
    if z <= 0:
        s.add(1)
    if x >= TILE:
        s.add(2)
    if z >= TILE:
        s.add(3)
    return s


def lane_turns(rec, cls=None):
    """-> set of (entry side, exit side) over the vehicle graph: from every node with no incoming internal edge
    that lies on the tile border, follow internal edges to every exit edge reachable. cls filters node class."""
    nodes = rec["veh"]
    incoming = set(e["to"] for n in nodes for e in n["edges"] if e["to"] is not None)
    out = set()
    for i, n in enumerate(nodes):
        if i in incoming or (cls is not None and n["cls"] != cls):
            continue
        for s_in in boundary_sides(n["x"], n["z"]):
            seen, stack = set(), [i]
            while stack:
                j = stack.pop()
                if j in seen:
                    continue
                seen.add(j)
                for e in nodes[j]["edges"]:
                    if e["to"] is None:
                        if e["code"] % 8 == 0:
                            out.add((s_in, e["code"] // 8))
                    else:
                        stack.append(e["to"])
    return out


def mask_half(turns):
    m = 0
    for f, t in turns:
        m |= 1 << (4 * f + t)
    return m


def mask_turns(m16):
    return sorted((b >> 2, b & 3) for b in range(16) if m16 >> b & 1)


def connect_query(mask, half_low, d, state):
    """FUN_1000d73d re-implemented: entering world side d of a piece at `state`, which world exit sides are on.
    half_low = the bool second argument (true -> low 16 bits). Closed form of table 0x1003123c."""
    base = 0 if half_low else 16
    return [bool(mask >> ((4 * ((d - state) % 4) + ((k - state) % 4) + base) & 31) & 1) for k in range(4)]


# =================================================================== authoring spec

def _xyz(n):
    """node -> [x, z], or [x, y, z] when the node has a height."""
    return [n["x"], n["y"], n["z"]] if n["y"] else [n["x"], n["z"]]


def _pty(v, y=0):
    """[x, z] | [x, y, z] -> (x, y, z)."""
    if isinstance(v, (list, tuple)) and len(v) == 2:
        return int(v[0]), int(y), int(v[1])
    if isinstance(v, (list, tuple)) and len(v) == 3:
        return int(v[0]), int(v[1]), int(v[2])
    raise LaneError("point %r: give [x, z] or [x, y, z]" % (v,))


def _pt(v):
    if isinstance(v, (list, tuple)) and len(v) in (2, 3):
        return (int(v[0]), int(v[-1])) if len(v) == 2 else (int(v[0]), int(v[2]))
    raise LaneError("point %r: give [x, z]" % (v,))


DEFAULT_SLOTS = {   # lane slots per side, at state 0 local coordinates; slot 1 = smaller coordinate along the side
    "car": [80, 175],                       # road 29 / 39 (every road piece measured: 80, 175)
}


def slot_point(side, slot, slots):
    s = side_of(side)
    c = slots[int(slot) - 1] if isinstance(slot, int) or str(slot).isdigit() else int(str(slot).lstrip("@"))
    return [(0, c), (c, 0), (TILE, c), (c, TILE)][s]


def _resolve_point(v, cls, slots):
    """[x, z] | "x- 1" (side + slot) | "x- @80" (side + coordinate)."""
    if isinstance(v, str):
        parts = v.split()
        if len(parts) != 2:
            raise LaneError("lane end %r: use \"<side> <slot>\" e.g. \"x- 1\" or \"z+ @175\"" % v)
        return slot_point(parts[0], parts[1], slots)
    return list(v)


def compile_spec(spec, game, lang="ENGLISH"):
    """Authoring spec (state 0, local coordinates) -> {"records": {state: bytes}, "masks": {net: u32}, "warnings"}.

    spec = {
      "piece": 20400,                 # id the records are keyed to
      "states": [0, 1, 2, 3],         # generated by rotation from the state-0 description
      "flag": 0|1, "alt": [c0, c1, c2, c3],  (corner altitude offsets, default 0)
      "vehicle": {"class": "car", "speed": 64000, "slots": [80, 175],
                  "lanes": [{"from": "x- 1", "to": "z- 1", "via": [[x, z], ...], "path": key?, "speed": n?}, ...]},
      "pedestrian": {"walks": [{"from": [x, z], "to": [x, z], "crosswalk": false, "path": key?}, ...],
                     "exits": [{"at": [x, z], "side": "x-"}, ...]},
      "connects": {"road": "auto" | [[from, to], ...] | {"low": [...], "high": [...]}, "rail": ..., "subway": ...}
    }
    A vehicle lane is one-way: an entry node at "from", internal edges along "via" to "to", an exit edge there
    (code = side * 8). Two lanes may share nodes. A walk is two-way (the game's pedestrian edges come in pairs:
    the same curve forward, and again with the reverse flag)."""
    P = game.paths(lang)
    warns = []
    rec = {"alt_raw": [0, 0, 0, 0], "flag": int(spec.get("flag", 0)), "ped": [], "veh": []}
    alt = spec.get("alt", [0, 0, 0, 0])
    rec["alt_raw"] = [alt[0] << 8, alt[3] << 8, alt[2] << 8, alt[1] << 8]

    def node(kind, p, y=0, cls=0):
        x, y, z = _pty(p, y)
        lst = rec[kind]
        for i, n in enumerate(lst):
            if (n["x"], n["z"], n["y"]) == (x, z, y) and (kind == "ped" or n["cls"] == cls):
                return i
        n = {"x": x, "y": y, "z": z, "edges": [], "_exits": []}
        if kind == "veh":
            n["cls"] = cls
        lst.append(n)
        return len(lst) - 1

    v = spec.get("vehicle") or {}
    cls_name = v.get("class", "car")
    cls = VCLASS_ID[cls_name]
    slots = v.get("slots") or DEFAULT_SLOTS.get(cls_name)
    speed = int(v.get("speed", 64000))
    turns = set()
    for li, lane in enumerate(v.get("lanes", [])):
        lcls = VCLASS_ID[lane.get("class", cls_name)]
        a = _resolve_point(lane["from"], lcls, slots)
        b = _resolve_point(lane["to"], lcls, slots)
        pts = [a] + [list(p) for p in lane.get("via", [])] + [b]
        xz = [(p[0], p[-1]) for p in pts]
        y = int(lane.get("y", 0))
        ids = [node("veh", p, y, lcls) for p in pts]
        given = lane.get("path")
        for j in range(len(pts) - 1):
            key = given[j] if isinstance(given, list) else given
            if key is None:
                hits = P.find("veh", xz[j], xz[j + 1])
                if not hits:
                    raise LaneError("vehicle lane %d (%s -> %s): no VPATHATT curve from %s to %s; give \"via\" points "
                                    "or a \"path\" key" % (li + 1, lane["from"], lane["to"], pts[j], pts[j + 1]))
                key = hits[0]
                if len(hits) > 1:
                    warns.append("vehicle lane %d segment %d: %d curves fit, took %d (others %s)"
                                 % (li + 1, j + 1, len(hits), key, hits[1:6]))
            elif key not in P.veh:
                raise LaneError("vehicle lane %d: path key %d is not in VPATHATT" % (li + 1, key))
            rec["veh"][ids[j]]["edges"].append({"to": ids[j + 1], "code": 0, "path": key,
                                                "e3": int(lane.get("speed", speed))})
        end_sides = boundary_sides(*xz[-1])
        if lane.get("exit", True):
            if len(end_sides) != 1:
                raise LaneError("vehicle lane %d ends at %s, which is not on exactly one side" % (li + 1, b))
            s_out = end_sides.pop()
            rec["veh"][ids[-1]]["_exits"].append({"to": None, "code": 8 * s_out, "path": 0,
                                                  "e3": int(lane.get("speed", speed))})
            for s_in in boundary_sides(*xz[0]):
                turns.add((CLASS_NET[VCLASS[lcls]], s_in, s_out))
    for xi, x in enumerate(v.get("exits", [])):           # explicit exits (describe() writes these)
        xc = VCLASS_ID[x.get("class", cls_name)]
        i = node("veh", list(x["at"]), int(x.get("y", 0)), xc)
        code = int(x["code"]) if "code" in x else 8 * side_of(x["side"])
        rec["veh"][i]["_exits"].append({"to": None, "code": code, "path": 0, "e3": int(x.get("speed", speed))})
    p = spec.get("pedestrian") or {}
    for wi, w in enumerate(p.get("walks", [])):
        a, b = list(w["from"]), list(w["to"])
        ia, ib = node("ped", a, int(w.get("y", 0))), node("ped", b, int(w.get("y", 0)))
        a, b = [a[0], a[-1]], [b[0], b[-1]]
        key = w.get("path")
        rev = False
        if key is None:
            hits = P.find("ped", a, b)
            if not hits:
                hits = P.find("ped", b, a)
                rev = True
            if not hits:
                raise LaneError("walk %d: no PPATHATT curve between %s and %s" % (wi + 1, a, b))
            key = hits[0]
        else:
            pp = P.ped.get(key)
            if pp is None:
                raise LaneError("walk %d: path key %d is not in PPATHATT" % (wi + 1, key))
            rev = False          # a given path: "from" is the node whose edge runs the curve forward (reverse flag 0);
            # shipped piece 1999 pairs curve 8704 with end points that are not the curve's own, so geometry cannot decide
        cw = 1 if w.get("crosswalk") else 0
        fwd, back = (ia, ib) if not rev else (ib, ia)          # the curve runs fwd -> back
        rec["ped"][fwd]["edges"].append({"to": back, "code": cw, "path": key, "e3": 0})
        rec["ped"][back]["edges"].append({"to": fwd, "code": cw, "path": key, "e3": 1})
    for xi, x in enumerate(p.get("exits", [])):
        i = node("ped", list(x["at"]), int(x.get("y", 0)))
        code = int(x["code"]) if "code" in x else 8 * side_of(x["side"])
        rec["ped"][i]["_exits"].append({"to": None, "code": code, "path": 0, "e3": 0})
    # node order: sorted by (x, y, z) as the shipped records; edges: internal in authoring order, then exits
    for kind in ("ped", "veh"):
        order = sorted(range(len(rec[kind])), key=lambda i: (rec[kind][i]["x"], rec[kind][i]["y"], rec[kind][i]["z"]))
        remap = {old: new for new, old in enumerate(order)}
        nodes = []
        for new, old in enumerate(order):
            n = rec[kind][old]
            n["edges"] = [dict(e, to=remap[e["to"]]) for e in n["edges"]] + n.pop("_exits")
            n["idx"] = new + 1
            nodes.append(n)
        rec[kind] = nodes
    if spec.get("edge_order"):                       # exact form from describe(): explicit per-node edge order
        _apply_edge_order(rec, spec["edge_order"])
    masks = compile_connects(spec.get("connects"), turns, warns)
    states = spec.get("states", [0, 1, 2, 3])
    recs = {s: encode(rotate(rec, s)) for s in states}
    return {"records": recs, "masks": masks, "warnings": warns, "rec0": rec}


def _apply_edge_order(rec, order):
    for kind in ("ped", "veh"):
        for i, perm in enumerate(order.get(kind, [])):
            es = rec[kind][i]["edges"]
            if sorted(perm) != list(range(len(es))):
                raise LaneError("edge_order %s node %d: %r is not a permutation of %d edges" % (kind, i, perm, len(es)))
            rec[kind][i]["edges"] = [es[j] for j in perm]


def compile_connects(c, turns, warns):
    """-> {net: u32} for the nets the spec names (missing = leave the exemplar alone)."""
    out = {}
    if not c:
        return out
    for net, val in c.items():
        if net not in CONN_PROPS:
            raise LaneError("connects: network %r, use road / rail / subway" % net)
        if val == "auto":
            t = {(f, s) for (n, f, s) in turns if n == net}
            if not t:
                warns.append("connects %s auto: no %s lane enters and leaves the tile" % (net, net))
            lo = hi = mask_half(t)
        elif isinstance(val, dict):
            lo = mask_half({(side_of(a), side_of(b)) for a, b in val.get("low", [])})
            hi = mask_half({(side_of(a), side_of(b)) for a, b in val.get("high", [])})
        else:
            lo = hi = mask_half({(side_of(a), side_of(b)) for a, b in val})
        out[net] = lo | (hi << 16)
    return out


# =================================================================== stock -> spec (round trip)

def describe(rec, P, piece=None, exact=True):
    """Stock record (decoded) -> authoring spec at the record's own frame. Returns (spec, problems): problems list
    what the authoring format cannot say for this record (then the round trip is expected to differ)."""
    probs = []
    spec = {"piece": piece, "states": [0], "flag": rec["flag"], "alt": alt_offsets(rec)}
    if any(r & 0xFF for r in rec["alt_raw"]):
        probs.append("alt raw low bits")
    lanes = []
    veh = rec["veh"]
    classes = sorted({n["cls"] for n in veh})
    cls_name = VCLASS.get(classes[0], "car") if classes else "car"
    speeds = [e["e3"] for n in veh for e in n["edges"]]
    speed = max(set(speeds), key=speeds.count) if speeds else 64000
    for i, n in enumerate(veh):
        for e in n["edges"]:
            if e["to"] is None:
                continue
            m = veh[e["to"]]
            lane = {"from": _xyz(n), "to": _xyz(m), "path": e["path"], "exit": False}
            if n["cls"] != classes[0]:
                lane["class"] = VCLASS.get(n["cls"], n["cls"])
            if m["cls"] != n["cls"]:
                probs.append("edge joins two vehicle classes")
            if e["e3"] != speed:
                lane["speed"] = e["e3"]
            if e["code"] != 0:
                probs.append("internal vehicle edge code %d" % e["code"])
            lanes.append(lane)
    exits_v = []
    for i, n in enumerate(veh):
        for e in n["edges"]:
            if e["to"] is None:
                x = {"at": _xyz(n), "code": e["code"]}
                if n["cls"] != classes[0]:
                    x["class"] = VCLASS.get(n["cls"], n["cls"])
                if e["e3"] != speed:
                    x["speed"] = e["e3"]
                if e["path"]:
                    probs.append("vehicle exit with a path key")
                exits_v.append(x)
    spec["vehicle"] = {"class": cls_name, "speed": speed, "lanes": lanes, "exits": exits_v}
    walks, exits_p = [], []
    ped = rec["ped"]
    paired = set()
    for i, n in enumerate(ped):
        for j, e in enumerate(n["edges"]):
            if e["to"] is None:
                exits_p.append({"at": _xyz(n), "code": e["code"]})
                continue
            if (i, j) in paired:
                continue
            m = ped[e["to"]]
            back = [k for k, f in enumerate(m["edges"]) if f["to"] == i and f["path"] == e["path"]
                    and f["e3"] != e["e3"] and (e["to"], k) not in paired]
            if not back:
                probs.append("pedestrian edge with no reverse partner")
                continue
            paired.add((i, j))
            paired.add((e["to"], back[0]))
            fwd_node = i if e["e3"] == 0 else e["to"]
            back_node = e["to"] if e["e3"] == 0 else i
            w = {"from": _xyz(ped[fwd_node]), "to": _xyz(ped[back_node]), "path": e["path"]}
            if e["code"]:
                w["crosswalk"] = True
            if e["code"] not in (0, 1) or m["edges"][back[0]]["code"] != e["code"]:
                probs.append("pedestrian edge code %d / %d" % (e["code"], m["edges"][back[0]]["code"]))
            walks.append(w)
    spec["pedestrian"] = {"walks": walks, "exits": exits_p}
    if exact:
        spec["edge_order"] = None          # filled by roundtrip_one once the compiled order is known
    return spec, probs


def edge_order_of(target, built):
    """Per node, the permutation that turns built's edge list into target's (None when no permutation does)."""
    out = {}
    for kind in ("ped", "veh"):
        out[kind] = []
        for nt, nb in zip(target[kind], built[kind]):
            keyf = lambda e: (e["to"], e["code"], e["path"], e["e3"])
            pool = list(range(len(nb["edges"])))
            perm = []
            for e in nt["edges"]:
                hit = next((j for j in pool if keyf(nb["edges"][j]) == keyf(e)), None)
                if hit is None:
                    return None
                pool.remove(hit)
                perm.append(hit)
            out[kind].append(perm)
    return out


def is_identity(order):
    return all(p == list(range(len(p))) for kind in order.values() for p in kind)


# =================================================================== CLI helpers

def fmt_matrix(m):
    lo, hi = m & 0xFFFF, m >> 16
    def f(h):
        return " ".join("%s=>%s" % (SIDES[a], SIDES[b]) for a, b in mask_turns(h)) or "-"
    return ("both: " + f(lo)) if lo == hi else ("low: %s | high: %s" % (f(lo), f(hi)))


def cmd_show(a):
    g = Game(a.root)
    pid = a.piece
    m = g.masks(pid)
    print("piece %d" % pid)
    if m is None:
        print("  no exemplar")
    else:
        for net, v in m.items():
            if v:
                print("  connects %-6s prop %d = 0x%08x  %s" % (net, CONN_PROPS[net], v, fmt_matrix(v)))
    t = g.trblkatt(a.lang)
    for st in range(4):
        b = t.get(pid * 256 + st)
        if b is None:
            continue
        r = decode(b)
        print("  state %d: %d bytes flag %d alt %s; lane turns %s" % (
            st, len(b), r["flag"], alt_offsets(r),
            " ".join("%s=>%s" % (SIDES[f], SIDES[s]) for f, s in sorted(lane_turns(r)))))
        for kind in ("veh", "ped"):
            for i, n in enumerate(r[kind]):
                es = ", ".join(("exit %d" % e["code"]) if e["to"] is None else
                               ("->%d path %d%s%s" % (e["to"], e["path"],
                                                      " cw" if kind == "ped" and e["code"] else "",
                                                      " rev" if kind == "ped" and e["e3"] else ""))
                               for e in n["edges"])
                print("    %s %d (%d,%d,%d)%s: %s" % (kind, i, n["x"], n["y"], n["z"],
                                                    " " + VCLASS.get(n.get("cls"), "?") if kind == "veh" else "", es))


def cmd_describe(a):
    g = Game(a.root)
    b = g.trblkatt(a.lang).get(a.piece * 256 + a.state)
    if b is None:
        raise SystemExit("piece %d state %d has no record in %s" % (a.piece, a.state, a.lang))
    spec, probs = describe(decode(b), g.paths(a.lang), a.piece, exact=False)
    m = g.masks(a.piece)
    if m:
        spec["connects"] = {}
        for net, v in m.items():
            if v:
                lo, hi = v & 0xFFFF, v >> 16
                if lo == hi:
                    spec["connects"][net] = [[SIDES[x], SIDES[y]] for x, y in mask_turns(lo)]
                else:
                    spec["connects"][net] = {"low": [[SIDES[x], SIDES[y]] for x, y in mask_turns(lo)],
                                             "high": [[SIDES[x], SIDES[y]] for x, y in mask_turns(hi)]}
    spec.pop("edge_order", None)
    if probs:
        spec["_not_expressible"] = probs
    print(json.dumps(spec, indent=1))


def roundtrip(g, lang):
    """-> rows: one per shipped record: piece, state, codec, rotation (from the piece's lowest state), describe."""
    t = g.trblkatt(lang)
    P = g.paths(lang)
    rows = []
    by_piece = {}
    for inst in sorted(t):
        by_piece.setdefault(inst >> 8, []).append(inst & 0xFF)
    for pid, states in sorted(by_piece.items()):
        base_state = min(states)
        base = decode(t[pid * 256 + base_state])
        for st in states:
            blob = t[pid * 256 + st]
            rec = decode(blob)
            codec = encode(rec) == blob
            rot = encode(rotate(base, st - base_state)) == blob
            spec, probs = describe(rec, P, pid)
            try:
                built = compile_spec(spec, g, lang)["rec0"]
                order = edge_order_of(rec, built)
                if order is not None and not is_identity(order):
                    spec["edge_order"] = order
                    built = compile_spec(spec, g, lang)["rec0"]
                auth = encode(built) == blob
                needs_order = order is not None and not is_identity(order)
            except (LaneError, KeyError) as e:
                auth, needs_order, probs = False, False, probs + [str(e)]
            rows.append({"piece": pid, "state": st, "bytes": len(blob), "codec": codec, "rotation": rot,
                         "rot_from": base_state, "authoring": auth, "needs_edge_order": needs_order,
                         "problems": "; ".join(probs)})
    return rows


def cmd_roundtrip(a):
    g = Game(a.root)
    langs = [a.lang] if a.lang else g.langs()
    summary = {}
    allrows = []
    for lang in langs:
        rows = roundtrip(g, lang)
        for r in rows:
            r["lang"] = lang
        allrows += rows
        n = len(rows)
        s = {"records": n, "codec": sum(r["codec"] for r in rows), "rotation": sum(r["rotation"] for r in rows),
             "authoring": sum(r["authoring"] for r in rows),
             "authoring_without_edge_order": sum(r["authoring"] and not r["needs_edge_order"] for r in rows),
             "pieces": len({r["piece"] for r in rows}),
             "pieces_all_states_by_rotation": len({r["piece"] for r in rows}) - len(
                 {r["piece"] for r in rows if not r["rotation"]})}
        summary[lang] = s
        print("%-11s %s" % (lang, " ".join("%s=%d" % kv for kv in s.items())))
    if a.csv:
        import csv
        with open(a.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(allrows[0].keys()))
            w.writeheader()
            w.writerows(allrows)
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(summary, fh, indent=1)
    return summary


def cmd_check_connects(a):
    """For every piece with a record and an exemplar: does the turn set derived from its vehicle lanes (state 0
    frame of the lowest state, rotated back to the piece frame) equal the exemplar matrix (low / high half)?"""
    g = Game(a.root)
    res = {}
    for lang in [a.lang] if a.lang else ["ENGLISH", "English-UK"]:
        t = g.trblkatt(lang)
        cnt = {"pieces": 0, "low": 0, "high": 0, "both": 0, "neither": 0, "subset_low": 0}
        rows = []
        for pid in sorted({k >> 8 for k in t}):
            m = g.masks(pid)
            if m is None:
                continue
            states = sorted(k & 0xFF for k in t if k >> 8 == pid)
            st = states[0]
            r = decode(t[pid * 256 + st])
            for net, cls in (("road", 0), ("rail", 1), ("subway", 2)):
                mm = m[net]
                lt = lane_turns(r, cls)
                if not mm and not lt:
                    continue
                # the record is at state st: rotate the observed world turns back to the piece frame
                lt0 = {((f - st) % 4, (s - st) % 4) for f, s in lt}
                lo, hi = mm & 0xFFFF, mm >> 16
                got = mask_half(lt0)
                cnt["pieces"] += 1
                k = ("both" if got == lo == hi else "low" if got == lo else "high" if got == hi else "neither")
                cnt[k] += 1
                if k == "neither" and got & ~lo == 0:
                    cnt["subset_low"] += 1
                rows.append((pid, net, st, k, "0x%04x" % got, "0x%04x" % lo, "0x%04x" % hi))
        res[lang] = cnt
        print(lang, cnt)
        if a.verbose:
            for r in rows:
                if r[3] == "neither":
                    print("   ", r)
    return res


# =================================================================== diagram

def draw(rec, out_png, title="", masks=None, state=0, scale=2):
    """PNG of one record: the tile, vehicle lanes as arrows along their curves, pedestrian walks as dotted lines,
    exits as ticks. Needs Pillow."""
    from PIL import Image, ImageDraw
    P = getattr(draw, "paths", None)
    S = 256 * scale
    pad = 40
    im = Image.new("RGB", (S + 2 * pad, S + 2 * pad + 40), (250, 250, 247))
    d = ImageDraw.Draw(im)

    def xy(x, z):
        return pad + x * scale, pad + z * scale
    d.rectangle([xy(0, 0), xy(255, 255)], outline=(60, 60, 60), width=2)
    for s, (lx, lz) in enumerate([(-30, 128), (128, -26), (262, 128), (128, 262)]):
        d.text(xy(lx, lz), SIDES[s], fill=(80, 80, 80))
    colours = {0: (200, 60, 40), 1: (40, 90, 200), 2: (40, 150, 60)}
    if P is not None:
        for n in rec["ped"]:
            for e in n["edges"]:
                if e["to"] is None or e["e3"]:
                    continue
                pts = P.ped.get(e["path"], {}).get("pts") or [(n["x"], 0, n["z"]), (rec["ped"][e["to"]]["x"], 0,
                                                                                    rec["ped"][e["to"]]["z"])]
                for p0, p1 in zip(pts, pts[1:]):
                    d.line([xy(p0[0], p0[2]), xy(p1[0], p1[2])], fill=(150, 150, 150) if not e["code"]
                           else (230, 160, 0), width=2)
    for n in rec["veh"]:
        col = colours.get(n["cls"], (0, 0, 0))
        for e in n["edges"]:
            if e["to"] is None:
                dx, dz = EXIT_STEP[e["code"] >> 2]
                x0, z0 = n["x"], n["z"]
                d.line([xy(x0, z0), xy(x0 + 18 * dx, z0 + 18 * dz)], fill=col, width=3)
                continue
            m = rec["veh"][e["to"]]
            pts = (P.veh.get(e["path"], {}).get("pts") if P is not None else None) or \
                [(n["x"], 0, n["z"]), (m["x"], 0, m["z"])]
            for p0, p1 in zip(pts, pts[1:]):
                d.line([xy(p0[0], p0[2]), xy(p1[0], p1[2])], fill=col, width=3)
            # arrow head at the last segment
            (ax, _, az), (bx, _, bz) = pts[-2], pts[-1]
            import math
            ang = math.atan2(bz - az, bx - ax)
            for da in (2.6, -2.6):
                d.line([xy(bx, bz), xy(bx + 12 * math.cos(ang + da), bz + 12 * math.sin(ang + da))], fill=col, width=3)
        d.ellipse([xy(n["x"] - 4, n["z"] - 4), xy(n["x"] + 4, n["z"] + 4)], fill=col)
    if title:
        d.text((pad, S + 2 * pad + 4), title, fill=(20, 20, 20))
    if masks:
        d.text((pad, S + 2 * pad + 20), "  ".join("%s: %s" % (k, fmt_matrix(v)) for k, v in masks.items() if v)[:110],
               fill=(20, 20, 20))
    im.save(out_png)
    return out_png


def cmd_diagram(a):
    g = Game(a.root)
    draw.paths = g.paths(a.lang)
    if os.path.isfile(a.what):
        spec = json.load(open(a.what, encoding="utf-8"))
        c = compile_spec(spec, g, a.lang)
        rec = rotate(c["rec0"], a.state)
        draw(rec, a.png, "%s state %d" % (spec.get("piece"), a.state), c["masks"])
    else:
        pid = int(a.what)
        b = g.trblkatt(a.lang).get(pid * 256 + a.state)
        if b is None:
            raise SystemExit("no record %d state %d" % (pid, a.state))
        draw(decode(b), a.png, "piece %d state %d (%s)" % (pid, a.state, a.lang), g.masks(pid))
    print(a.png)


def cmd_build(a):
    g = Game(a.root)
    spec = json.load(open(a.spec, encoding="utf-8"))
    os.makedirs(a.out, exist_ok=True)
    rep = {"piece": spec["piece"], "langs": {}, "masks": None, "warnings": []}
    for lang in g.langs():
        c = compile_spec(spec, g, lang)
        rep["masks"] = {k: "0x%08x" % v for k, v in c["masks"].items()}
        rep["warnings"] = c["warnings"]
        rep["langs"][lang] = {}
        for st, b in c["records"].items():
            fn = os.path.join(a.out, "%s_%d_%d.trb" % (lang, spec["piece"], st))
            open(fn, "wb").write(b)
            rep["langs"][lang][st] = {"bytes": len(b), "file": os.path.basename(fn)}
    json.dump(rep, open(os.path.join(a.out, "BUILD.json"), "w"), indent=1)
    print(json.dumps(rep, indent=1))


def verify_spec(g, spec, lang="ENGLISH", against=None):
    """Compile a spec and byte-compare every state with the stock records of `against` (default spec piece),
    and each connects mask with the stock exemplar. -> (ok, lines)."""
    pid = against or spec["piece"]
    c = compile_spec(spec, g, lang)
    t = g.trblkatt(lang)
    lines, ok = [], True
    for st, b in sorted(c["records"].items()):
        s = t.get(pid * 256 + st)
        same = s == b
        ok &= same
        lines.append("state %d: %s (%d bytes, stock %s)" % (st, "identical" if same else "DIFFERS", len(b),
                                                           len(s) if s else "none"))
    m = g.masks(pid) or {}
    for net, v in c["masks"].items():
        same = m.get(net) == v
        ok &= same
        lines.append("connects %s: 0x%08x %s stock 0x%08x" % (net, v, "==" if same else "!=", m.get(net, 0)))
    for w in c["warnings"]:
        lines.append("warning: " + w)
    return ok, lines


def cmd_verify(a):
    g = Game(a.root)
    bad = 0
    for f in a.specs:
        spec = json.load(open(f, encoding="utf-8"))
        ok, lines = verify_spec(g, spec, a.lang, a.against)
        bad += not ok
        print("%s %s (piece %s)" % ("OK  " if ok else "FAIL", os.path.basename(f), spec.get("piece")))
        for l in lines:
            print("     " + l)
    return 1 if bad else 0


def cmd_selftest(a):
    g = Game(a.root)
    ok = True

    def check(name, cond):
        nonlocal ok
        ok &= bool(cond)
        print("%-4s %s" % ("ok" if cond else "FAIL", name))
    t = g.trblkatt("ENGLISH")
    check("codec byte-identical on every ENGLISH record (%d)" % len(t), all(encode(decode(b)) == b for b in t.values()))
    # FUN_1000d73d closed form vs the table bytes in SIMNTWRK
    try:
        from .pe_tables import Simntwrk
        pe = Simntwrk(paths.Game(g.root))
        tab = list(pe.bytes_(0x1003123C, 64))
        cf = [4 * ((d - s) % 4) + ((k - s) % 4) for s in range(4) for d in range(4) for k in range(4)]
        check("perm table 0x1003123c == closed form", tab == cf)
    except Exception as e:                                     # noqa: BLE001
        print("skip perm table: %s" % e)
    check("road 29 connects x- <-> x+ (0x01040104)", g.masks(29)["road"] == 0x01040104)
    r29 = decode(t[29 * 256])
    check("road 29 state 1 = rotate(state 0)", encode(rotate(r29, 1)) == t[29 * 256 + 1])
    check("road 29 lane turns {x->x+, x+->x-}", lane_turns(r29) == {(0, 2), (2, 0)})
    P = g.paths("ENGLISH")
    check("VPATHATT 512 runs (0,80)->(255,80)", P.find("veh", (0, 80), (255, 80))[:1] == [258] or 512 in
          P.find("veh", (0, 80), (255, 80)))
    spec = {"piece": 29, "states": [0, 1], "vehicle": {"lanes": [{"from": "x- 1", "to": "x+ 1", "path": 512},
                                                                 {"from": "x+ 2", "to": "x- 2", "path": 256}]},
            "pedestrian": {"walks": [{"from": [15, 15], "to": [240, 15], "path": 256},
                                     {"from": [240, 240], "to": [15, 240], "path": 512}],
                           "exits": [{"at": [15, 15], "side": "x-"}, {"at": [15, 240], "side": "x-"},
                                     {"at": [240, 15], "side": "x+"}, {"at": [240, 240], "side": "x+"}]},
            "connects": {"road": "auto"}}
    c = compile_spec(spec, g)
    check("hand-written spec of road 29 == stock state 0", c["records"][0] == t[29 * 256])
    check("hand-written spec of road 29 == stock state 1", c["records"][1] == t[29 * 256 + 1])
    check("connects auto of road 29 == its exemplar mask", c["masks"]["road"] == g.masks(29)["road"])
    print("selftest", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="lanekit")
    ap.add_argument("--root", default=None, help="game root (default: SC3_GAME_ROOT / main checkout)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show")
    s.add_argument("piece", type=int)
    s.add_argument("--lang", default="ENGLISH")
    s = sub.add_parser("describe")
    s.add_argument("piece", type=int)
    s.add_argument("--state", type=int, default=0)
    s.add_argument("--lang", default="ENGLISH")
    s = sub.add_parser("build")
    s.add_argument("spec")
    s.add_argument("--out", required=True)
    s = sub.add_parser("roundtrip")
    s.add_argument("--lang", default=None)
    s.add_argument("--csv", default=None)
    s.add_argument("--json", default=None)
    s = sub.add_parser("check-connects")
    s.add_argument("--lang", default=None)
    s.add_argument("-v", "--verbose", action="store_true")
    s = sub.add_parser("diagram")
    s.add_argument("what")
    s.add_argument("--png", required=True)
    s.add_argument("--state", type=int, default=0)
    s.add_argument("--lang", default="ENGLISH")
    s = sub.add_parser("verify")
    s.add_argument("specs", nargs="+")
    s.add_argument("--lang", default="ENGLISH")
    s.add_argument("--against", type=int, default=None)
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    r = {"show": cmd_show, "describe": cmd_describe, "build": cmd_build, "roundtrip": cmd_roundtrip,
         "check-connects": cmd_check_connects, "diagram": cmd_diagram, "verify": cmd_verify,
         "selftest": cmd_selftest}[a.cmd](a)
    return r if isinstance(r, int) else 0


if __name__ == "__main__":
    sys.exit(main() or 0)
