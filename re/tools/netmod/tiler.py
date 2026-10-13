"""tiler.py -- offline re-implementation of the SIMNTWRK network retiler (FUN_1001547b).

Read-only on the game install. Every step cites the SIMNTWRK.DLL function it reproduces; the
analysis is re/analysis/TILER_SIM.md. Image base 0x10000000, addresses are Ghidra VAs.

Model
  * A City holds the map size N, the terrain corner heights (DirtBag grid A, (N+1)^2) and water
    levels (grid B), and three occupant layers like the network manager's +0x3c / +0x40 / +0x44:
    "surface" (ROAD, RAIL, POWR, HWAY share it), "pipe", "subway". One occupant per cell.
  * An occupant is a network piece (id, state, z, props). Its class flags come from the piece
    class the factory would build for its id (FUN_1001a5f2 + FUN_1000bdcd, flag getters
    vt2+0x48 0x1000c306..0x1000c62e), its "removable" bit from props bit 12 (= occupant +0xc
    bit 25, saver FUN_1000ca2c / FUN_1000d536, test FUN_10023db8).
  * Rules is one TilingRules directory: Simple/Complex/final rule lists per net, Convert and
    Complex_Convert tables, Protected lists, Set lists (piece classes).
  * Tiler.retile(net, nodes) is FUN_1001547b: flood fill, removal of the region, Protected
    and slope split, slope pass, then Simple to fixpoint, Complex up to 5 passes, final once.

Two engine inputs are not decoded and are explicit switches (Options), never silent guesses:
  * conn_masks: what FUN_1000d73d returns for a piece (exemplar +0x140/+0x144/+0x148). Static
    reading says the fields are only ever zeroed as shipped (NETWORK_RULE_ENGINE.md 14.6).
  * nb_state: the state byte FUN_1001a056 reads for an occupied neighbour, through occupant
    vt+0xa0 (subobject +8, zero at construction, FUN_10023809) then vt+0x1c.
  * edge_conn: the +0x48 object's vt+0x58(net, x, y) (neighbour connection at a map edge).
"""
import os
import struct
import sys
from collections import namedtuple

from . import paths

sys.path.insert(0, paths.TOOLS)

NET_TAG = {1: "ROAD", 2: "RAIL", 3: "POWR", 4: "HWAY", 5: "PIPE", 6: "SUBW"}
TAG_NET = {v: k for k, v in NET_TAG.items()}
LAYER_OF = {1: "surface", 2: "surface", 3: "surface", 4: "surface", 5: "pipe", 6: "subway"}
SAVE_INSTANCE = {"surface": 1, "pipe": 2, "subway": 3}

# FUN_1002205c table at 0x10032134 (dir -> dx, dy); 0x1f = the tile itself.
DIRS = {0: (-1, 0), 1: (0, -1), 2: (1, 0), 3: (0, 1),
        4: (-1, -1), 5: (1, -1), 6: (1, 1), 7: (-1, 1),
        8: (-2, 0), 9: (-2, -1), 10: (-2, -2), 11: (-1, -2),
        12: (0, -2), 13: (1, -2), 14: (2, -2), 15: (2, -1),
        16: (2, 0), 17: (2, 1), 18: (2, 2), 19: (1, 2),
        20: (0, 2), 21: (-1, 2), 22: (-2, 2), 23: (-2, 1),
        0x1f: (0, 0)}
INV = {v: k for k, v in DIRS.items()}      # FUN_1002203e, table 0x10032118
SELF = 0x1f

# Piece class kind -> flags (vt2+0x48 constant getters, read 2026-10-13 from the PE)
CLASS_FLAGS = {1: 0xC804, 2: 0x14804, 3: 0x24804, 4: 0x44804, 5: 0x2C804, 6: 0x1C804,
               7: 0x34804, 8: 0x64804, 9: 0x800804, 10: 0x400804, 11: 0x40C804,
               12: 0x424804, 13: 0x414804, 14: 0x21C804, 15: 0x214804}

# Per netType: the predicate triple FUN_1001547b loads, as flag masks / functions.
#  predA  DAT_100323c0.. : vt+0x3c(mask) = (flags & mask) == mask   (FUN_10023cf6)
#  predNeg DAT_100323e4..: !(flags & bit)
#  cross  DAT_10032400.. : FUN_1001ab26 / ac2b / abb2 / acbe; PIPE/SUBW the generic 0x400 test
NETCFG = {
    1: dict(predA=0x8800, neg=0x8000, cross="road", radius=5, side=True, under=False),
    2: dict(predA=0x20800, neg=0x20000, cross="rail", radius=2, side=True, under=False),
    3: dict(predA=0x400800, neg=0x400000, cross="power", radius=2, side=False, under=False),
    4: dict(predA=0x10800, neg=0x10000, cross="hway", radius=5, side=True, under=False),
    5: dict(predA=0x800000, neg=0x800000, cross="generic", radius=2, side=False, under=True),
    6: dict(predA=0x40000, neg=0x40000, cross="generic", radius=5, side=False, under=True),
}
CROSS_IDS = {  # id lists inside the crossing predicates [CONFIRMED @ 0x1001ab26/ac2b/abb2/acbe]
    "road": (0x8000, {0x5C, 0x49, 0x3ACB, 0x2C, 0x2D, 0x2711, 0x2734, 0x2735, 0xF, 0xE}),
    "rail": (0x20000, {0x1D, 0x2BC4, 0x49, 0x3ACB, 0x5C, 0x1E, 0x2711, 0x2734, 0x2735, 0xF, 0xE}),
    "power": (0x400000, {0x1D, 0x2BC4, 0x2C, 0x49, 0x3ACB, 0x1E, 0x2D}),
    "hway": (0x10000, {0x1D, 0x2BC4, 0x2C, 0x5C, 0x1E, 0x2D, 0x2711, 0x2734, 0x2735, 0xF, 0xE}),
}
SURFACE_FLAG = 0x800          # DAT_100323d8, FUN_1001a9f3
PROPS_NEW = 0x3000            # FUN_10023809 sets occupant +0xc = 0x3000000 (bits 24, 25)

# FUN_1001a2c0: per-net slope result tables (u32[8]) and the pattern table 0x1003193c
SLOPE_TABLE_VA = {1: 0x1003195C, 2: 0x1003197C, 6: 0x1003199C, 5: 0x100319BC,
                  "powr_a": 0x100319DC, "powr_b": 0x100319FC,
                  "hway_absent": 0x10031A1C, "hway_present": 0x10031A3C}
CROSS_MATRIX_VA = 0x100318AC

# FUN_1000d73d permutation table 0x1003123c, closed form (NETWORK_RULE_ENGINE.md 13.1)
def _perm(frm, state, k):
    return 4 * ((frm - state) % 4) + ((k - state) % 4)


Rec = namedtuple("Rec", "id dir state")


class Rule:
    __slots__ = ("file", "index", "line", "selector", "conds", "results", "stage")

    def __init__(self, file, index, line, selector, conds, results, stage):
        self.file, self.index, self.line = file, index, line
        self.selector, self.conds, self.results, self.stage = selector, conds, results, stage

    def where(self):
        return "%s rule #%d (line %d)" % (self.file, self.index, self.line)


def _dir(d):
    return SELF if d == 255 else d          # parser FUN_10022676 maps 0xff -> 0x1f


def _rec(d, val):
    return Rec(val >> 8, _dir(d), val & 0xFF)


def parse_rules_file(path, stage):
    """RULES family -> [Rule] with 1-based line numbers of each `1,` line."""
    name = os.path.basename(path)
    out, cur = [], None
    with open(path, "rb") as fh:
        lines = fh.read().decode("ascii").splitlines()
    for ln, text in enumerate(lines, 1):
        t = text.strip()
        if not t:
            continue
        p = [int(x) for x in t.split(",")]
        if p[0] == 0:
            continue
        if p[0] == 1:
            cur = Rule(name, len(out), ln, p[1], [], [], stage)
            out.append(cur)
        elif p[0] == 3:
            cur.conds.append(_rec(p[1], p[2]))
        elif p[0] == 5:
            cur.results.append(_rec(p[1], p[2]))
    return out


def _counted(path):
    with open(path, "rb") as fh:
        ls = [l.strip() for l in fh.read().decode("ascii").splitlines() if l.strip()]
    return ls[1:]


class Rules:
    """One TilingRules directory, loaded the way FUN_10016d87 / FUN_100175ed / FUN_10017f98 /
    FUN_10019600 / FUN_100196ce bind it."""

    FILES = {  # stage file names exactly as built by FUN_100175ed (case as in the binary)
        1: ("ROAD_GRND_SimpleRules.txt", "ROAD_GRND_ComplexRules.txt", "ROAD_GRND_final.txt"),
        2: ("RAIL_GRND_SIMPLERULES.txt", "RAIL_GRND_COMPLEXRULES.txt", "RAIL_GRND_final.txt"),
        4: ("HWAY_GRND_SIMPLERULES.txt", "HWAY_GRND_COMPLEXRULES.txt", "HWAY_GRND_final.txt"),
        6: ("SUBW_GRND_SIMPLERULES.txt", "SUBW_GRND_COMPLEXRULES.txt", "SUBW_GRND_final.txt"),
        5: ("PIPE_GRND_SIMPLERULES.txt", "PIPE_GRND_COMPLEXRULES.txt", "PIPE_GRND_final.txt"),
        3: ("POWR_GRND_SIMPLERULES.txt", "POWR_GRND_COMPLEXRULES.txt", "POWR_GRND_final.txt"),
    }

    def __init__(self, tiling_dir):
        self.dir = tiling_dir
        names = {f.lower(): f for f in os.listdir(tiling_dir)}
        self.real = names

        def p(n):
            f = names.get(n.lower())
            return os.path.join(tiling_dir, f) if f else None

        self.path = p
        self.simple, self.complex, self.final = {}, {}, {}
        for net, (s, c, f) in self.FILES.items():
            self.simple[net] = parse_rules_file(p(s), "Simple") if p(s) else []
            self.complex[net] = parse_rules_file(p(c), "Complex") if p(c) else []
            self.final[net] = parse_rules_file(p(f), "final") if p(f) else []
        self.sets = {}
        for tag in ("ROAD", "HWAY", "RAIL", "SUBW", "PIPE", "POWR", "DIAG"):
            fp = p("DIAG_Set.txt" if tag == "DIAG" else "%s_GRND_Set.txt" % tag)
            ids = []
            if fp:
                import re
                with open(fp, "rb") as fh:
                    ids = [int(m) for m in re.findall(rb"\d+", fh.read())]
            self.sets[tag] = set(ids)
        self.protected, self.convert, self.cconvert = {}, {}, {}
        for net, tag in NET_TAG.items():
            fp = p("%s_GRND_Protected.txt" % ("Road" if tag == "ROAD" else tag))
            self.protected[net] = [int(x) for x in _counted(fp)] if fp else []
            for kind, store in (("Convert", self.convert), ("Complex_Convert", self.cconvert)):
                fp = p("%s_GRND_%s.txt" % (tag, kind))
                recs = []
                if fp:
                    for ln, t in enumerate(_counted(fp), 2):
                        a, b = (int(x) for x in t.split(","))
                        recs.append((a >> 8, a & 0xFF, b >> 8, b & 0xFF, ln))
                store[net] = recs
        self._kind = {}
        for st in (self.simple, self.complex, self.final):
            for net, rl in st.items():
                idx = {}
                for r in rl:
                    idx.setdefault(r.selector, []).append(r)
                st[net] = (rl, idx)

    def arms(self, pid, st):
        """Arm set (4-bit, W N E S = dirs 0..3) of a piece, derived from rule geometry only:
        final.txt (mask -> centre piece; the largest mask wins for a piece placed at several),
        then SimpleRules centre results (intersection of their orthogonal selector bits)."""
        if not hasattr(self, "_arms"):
            a = {}
            for net in NET_TAG:
                for r in self.final[net][0]:
                    for res in r.results:
                        if res.dir == SELF and res.id:
                            k = (res.id, res.state)
                            m = r.selector & 15
                            if k not in a or bin(m).count("1") > bin(a[k]).count("1"):
                                a[k] = m
            simple = {}
            for net in NET_TAG:
                for r in self.simple[net][0]:
                    if r.selector == 0x100:
                        continue
                    for res in r.results:
                        if res.dir == SELF and res.id and (res.id, res.state) not in a:
                            k = (res.id, res.state)
                            simple[k] = simple.get(k, 15) & (r.selector & 15)
            a.update({k: v for k, v in simple.items() if k not in a})
            self._arms = a
        return self._arms.get((pid, st))

    def stage(self, which, net):
        return {"Simple": self.simple, "Complex": self.complex, "final": self.final}[which][net]

    # FUN_1001a5f2 + factory kind, through pe_tables.classify
    def kind(self, pid):
        k = self._kind.get(pid)
        if k is None:
            from .pe_tables import classify
            in_ = [t for t in ("ROAD", "HWAY", "RAIL", "SUBW", "POWR", "PIPE") if pid in self.sets[t]]
            k = classify(pid, in_)[0]
            self._kind[pid] = k
        return k

    def flags(self, pid):
        return CLASS_FLAGS.get(self.kind(pid), 0)

    def is_protected(self, net, pid):          # FUN_1001a7f7
        return pid in self.protected[net]

    def convert_(self, mode, net, pid, st):     # FUN_1001a85a: last match wins
        table = self.convert[net] if mode in (4, 8) else self.cconvert[net] if mode == 0x18 else []
        rid, rst, hit = pid, st, None
        for a, s, b, t, ln in table:
            if a == pid and s == st:
                rid, rst, hit = b, t, ln
        return rid, rst, hit


class Piece:
    __slots__ = ("id", "state", "z", "props", "flags", "kind")

    def __init__(self, pid, state, z, props=PROPS_NEW, flags=None, kind=None):
        self.id, self.state, self.z, self.props = pid, state, z, props
        self.flags = flags        # None = network piece (flags from its class); else a building
        self.kind = kind          # building type id for a non-network occupant

    def removable(self):          # FUN_10023db8: occupant +0xc bit 25 = save word1 bit 28
        return bool(self.props & 0x1000)

    def __repr__(self):
        return "%d/%d" % (self.id, self.state)


class City:
    """Map size, terrain, water and the three occupant layers of one save."""

    def __init__(self, n, heights, water, layers, edge_cells=None, name=""):
        self.n = n
        self.A = heights          # bytes, (N+1)^2, save order: vertex (x,y) at (N-x)*(N+1)+y
        self.B = water
        self.layers = layers      # {"surface": {(x,y): Piece}, ...}
        self.edge_cells = edge_cells or {}
        self.name = name

    @classmethod
    def load(cls, path):
        import city_write
        import network_layer as nl
        c = city_write.City.load(path)
        n = c.n
        m = (n + 1) ** 2
        sec = [s for s in c.sections if s.group == 0x21737DE5 and s.instance == 0][0]
        A = bytes(sec.data[12:12 + m])
        B = bytes(sec.data[12 + m:12 + 2 * m])
        nets, _hdr = nl.read_networks(path)
        layers = {}
        for lname, inst in SAVE_INSTANCE.items():
            d = {}
            for (x, y, z, state, pid, props) in nets.get(inst, []):
                d[(x, y)] = Piece(pid, state, z, props)
            layers[lname] = d
        edge = {}
        import neighbor_layer
        secs = [s for s in c.sections if s.group == neighbor_layer.GROUP]
        if secs:
            nb = neighbor_layer.parse(bytes(secs[0].data))
            name_net = {"road": 1, "rail": 2, "power": 3, "highway": 4, "water": 5, "subway": 6}
            for name, cells in nb["edges"].items():
                edge[name_net[name]] = set(cells)
        city = cls(n, A, B, layers, edge, os.path.basename(path))
        city.buildings = {}
        try:
            import occupant_layer
            _c, _s0, _s1, _cnt, _ver, recs = occupant_layer.parse(path)
            for r in recs:
                city.buildings.setdefault(r["t18"], []).append(
                    (r["a"], r["b"], max(r["sa"], 1), max(r["sb"], 1), r["key"]))
        except Exception as ex:          # occupant section absent or unparsed
            city.buildings_error = str(ex)
        return city

    def add_stations(self, spec):
        """Insert transport buildings into the network layers as non-network occupants.
        spec: {building type: (layer, flags)}. Removable bit clear (a building is not removed by
        the tiler: FUN_1001547b only removes occupants whose vt+0x74 is true)."""
        for t, (lname, fl) in spec.items():
            for (a, b, sa, sb, key) in self.buildings.get(t, []):
                for x in range(a, a + sa):
                    for y in range(b, b + sb):
                        self.layers[lname].setdefault(
                            (x, y), Piece(key[2] & 0xFFFF, 0, self.h(x, y), 0, fl, t))

    def copy(self):
        lay = {k: {p: Piece(v.id, v.state, v.z, v.props, v.flags, v.kind) for p, v in d.items()}
               for k, d in self.layers.items()}
        c = City(self.n, self.A, self.B, lay, self.edge_cells, self.name)
        c.buildings = getattr(self, "buildings", {})
        return c

    # +0x30 terrain object (SIMDIRT vtable 0x1002046c)
    def h(self, x, y):                     # vt+0x4c FUN_10005ab0: grid[x][y]
        n = self.n
        if not (0 <= x <= n and 0 <= y <= n):
            return 0
        return self.A[(n - x) * (n + 1) + y]

    def wl(self, x, y):                    # vt+0x50 water level
        n = self.n
        if not (0 <= x <= n and 0 <= y <= n):
            return 0
        return self.B[(n - x) * (n + 1) + y]

    def is_water(self, x, y):              # vt+0x54 FUN_100065f0: any corner ground <= water
        for (a, b) in ((x, y), (x + 1, y), (x + 1, y + 1), (x, y + 1)):
            if self.h(a, b) <= self.wl(a, b):
                return True
        return False


class Options:
    def __init__(self, conn_masks="exemplar", nb_state="piece", edge_conn="cells", stations="subway",
                 trace=False):
        self.stations = stations        # "none" | "subway" (12360/12361 in subway, flags 0x40100)
        self.conn_masks = conn_masks    # "zero" (as shipped, 14.6) | "shape" (diagnostic)
        self.nb_state = nb_state        # "piece" (orientation bits) | "zero" (vt+0xa0 null)
        self.edge_conn = edge_conn      # "none" | "cells" (save neighbour-deal edge cells) | "all"
        self.trace = trace


class Event:
    __slots__ = ("stage", "cell", "rule", "mask", "obs", "results", "committed", "why")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))


class Tiler:
    def __init__(self, rules, city, opts=None, pe=None, ex=None):
        self.ex = ex
        self.R = rules
        self.C = city
        self.o = opts or Options()
        self.pe = pe
        self.events = []
        self.unknown = {}
        self._load_tables()

    # ------------------------------------------------------------------ tables from the PE
    def _load_tables(self):
        self.slope_rows = None
        self.perm = [_perm(f, s, k) for s in range(4) for f in range(4) for k in range(4)]
        self.slope_tab = {}
        self.cross_matrix = None
        if self.pe is None:
            return
        pat = self.pe.bytes_(0x1003193C, 32)
        self.slope_rows = [[struct.unpack_from("b", pat, r * 4 + k)[0] for k in range(4)]
                           for r in range(8)]
        for k, va in SLOPE_TABLE_VA.items():
            self.slope_tab[k] = self.pe.dwords(va, 8)
        self.cross_matrix = self.pe.dwords(CROSS_MATRIX_VA, 36)
        self.perm = list(self.pe.bytes_(0x1003123C, 64))      # DAT_1003123c, FUN_1000d73d

    # ------------------------------------------------------------------ occupant predicates
    def flags(self, p):
        if p.flags is not None:
            return p.flags
        return self.R.flags(p.id)

    def test(self, p, mask):               # FUN_10023cf6
        return (self.flags(p) & mask) == mask

    def predA(self, net, p):
        return self.test(p, NETCFG[net]["predA"])

    def predNeg(self, net, p):
        return (self.flags(p) & NETCFG[net]["neg"]) == 0

    def predCross(self, net, p):
        kind = NETCFG[net]["cross"]
        if kind == "generic":              # DAT_100323e0 = FUN_1001aa7b, test 0x400
            return self.test(p, 0x400)
        if not p.removable():
            return False
        f = self.flags(p)
        if f & 0x400:
            return True
        if not (f & 0x800):
            return False
        bit, ids = CROSS_IDS[kind]
        return bool(f & bit) or (p.id & 0xFFFF) in ids

    # ------------------------------------------------------------------ map helpers
    def inb(self, x, y):                   # layer +0x68 / +0x2c dims
        return 0 <= x < self.C.n and 0 <= y < self.C.n

    def corners(self, x, y):               # FUN_1001a1f3
        if not self.inb(x, y):
            return None
        h0 = self.C.h(x, y)
        return [0, self.C.h(x + 1, y) - h0, self.C.h(x + 1, y + 1) - h0, self.C.h(x, y + 1) - h0]

    def flat(self, x, y):                  # FUN_10016ccd
        c = self.corners(x, y)
        return c is not None and c[0] == c[1] == c[2] == c[3]

    def legal_slope(self, x, y):           # FUN_10016d00
        c = self.corners(x, y)
        if c is None:
            return False
        if c[0] == c[1] and c[2] == c[3] and abs(c[0] - c[2]) <= 2:
            return True
        if c[1] == c[2] and c[3] == c[0] and abs(c[0] - c[2]) < 3:
            return True
        return False

    def edge_dim(self):                    # +0x30 vt+0xb0/0xb4 = DirtBag grid dims = N+1
        return self.C.n + 1

    def edge_conn(self, net, x, y):        # +0x48 vt+0x58(net, x, y)  [UNCERTAIN]
        m = self.o.edge_conn
        if m == "none":
            return False
        if m == "all":
            return True
        return (x, y) in self.C.edge_cells.get(net, ())

    def layer(self, net):
        return self.C.layers[LAYER_OF[net]]

    # ------------------------------------------------------------------ FUN_1001a056
    def rec_from_occ(self, net, occ, centre, x, y, mode):
        rid, rdir, rst = 0, SELF, 0
        conv = None
        if not self.predA(net, occ):
            if self.predNeg(net, occ):
                rid, rst = 0, (5 if self.test(occ, 0x400) else 0)
        else:
            st = occ.state if self.o.nb_state == "piece" else 0
            rid, rst, conv = self.R.convert_(mode, net, occ.id, st)
            if (x, y) != centre:
                rdir = INV[(x - centre[0], y - centre[1])]
        return [rid, rdir, rst, conv]

    # ------------------------------------------------------------------ FUN_1000d73d
    def conn_bits(self, occ, sel, half, frm):
        """FUN_1000cd35 -> FUN_1000d73d. The masks are exemplar properties 310/311/312 of
        {0xE223741F, 0xA317745F, id} in Apps Res Occupant OccupantAttribs*.IXF (live-read 2026-10-13:
        +0x140 = prop 310 on road 29/11203/39). A building occupant has no such exemplar: QI fails,
        all four outputs stay 0."""
        mode = self.o.conn_masks
        if mode == "zero" or occ.flags is not None:
            return (0, 0, 0, 0)
        if mode == "shape":          # diagnostic only, superseded by "exemplar"
            arms = self.R.arms(occ.id, occ.state)
            return (1, 0, 0, 0) if arms is not None and arms >> frm & 1 else (0, 0, 0, 0)
        m = self.ex.mask(occ.id, sel) if self.ex else None
        if m is None:
            self.unknown["conn: piece without exemplar"] = self.unknown.get("conn: piece without exemplar", 0) + 1
            return (0, 0, 0, 0)
        base = 0 if half else 0x10
        st = occ.state & 3
        row = self.perm[4 * (frm + st * 4): 4 * (frm + st * 4) + 4]
        return tuple(1 if m >> ((b + base) & 0x1F) & 1 else 0 for b in row)

    # ------------------------------------------------------------------ FUN_10019768
    def collect(self, net, centre, pending_set, work_set, mode):
        xc, yc = centre
        lay = self.layer(net)
        recs = []
        mask = 0
        n = self.C.n
        if mode == 0x18:
            W = self.edge_dim()
            edge = 0xFFFF
            if xc == 0:
                edge = 0
            if xc == W - 2:
                edge = 2
            if yc == 0:
                edge = 1
            if yc == W - 2:
                edge = 3
            for x in range(xc - 2, xc + 3):
                for y in range(yc - 2, yc + 3):
                    d = INV[(x - xc, y - yc)]
                    if not self.inb(x, y):
                        st = 5
                        if edge == d and self.edge_conn(net, xc, yc):
                            st = 1
                        recs.append([0, d, st, None])
                        continue
                    occ = lay.get((x, y))
                    if occ is None:
                        recs.append([0, d, 1 if (x, y) in work_set else 5, None])
                        continue
                    r = self.rec_from_occ(net, occ, centre, x, y, 0x18)
                    r[1] = d
                    if r[0] == 0 and r[2] == 5 and (x, y) in work_set:
                        r[2] = 1
                    recs.append(r)
            return mask, recs
        x0 = 0 if xc == 0 else xc - 1
        y0 = 0 if yc == 0 else yc - 1
        x1 = xc + 1 if xc < n - 1 else n - 1
        y1 = yc + 1 if yc < n - 1 else n - 1
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                occ = lay.get((x, y))
                if occ is None:
                    continue
                if self.predA(net, occ):
                    d = INV[(x - xc, y - yc)]
                    if d < mode:
                        if mode == 4 and net in (1, 6, 2):
                            if net == 6 and self.test(occ, 0x40100):
                                mask |= 1 << d
                            else:
                                sel = {1: 0, 2: 1, 6: 2}[net]
                                frm = (d + 2) % 4
                                b = self.conn_bits(occ, sel, 1, frm)
                                if not any(b):
                                    b = self.conn_bits(occ, sel, 0, frm)
                                if any(b):
                                    mask |= 1 << d
                        else:
                            mask |= 1 << d
                recs.append(self.rec_from_occ(net, occ, centre, x, y, mode))
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                p = (xc + dx, yc + dy)
                if p not in pending_set:
                    continue
                d = INV[(dx, dy)]
                if d >= mode:
                    continue
                occ = lay.get(p)
                if occ is None or not self.predA(net, occ):
                    mask |= 1 << d
        W = self.edge_dim()
        f = 0
        if xc == 0:
            f = 8
        if xc == W - 2:
            f |= 2
        if yc == 0:
            f |= 1
        if yc == W - 2:
            f |= 4
        k = 1
        while f:
            if f & 1:
                d = k if k <= 3 else 0
                if self.edge_conn(net, xc, yc):
                    mask |= 1 << d
            f >>= 1
            k += 1
        return mask, recs

    # ------------------------------------------------------------------ FUN_100228ff
    @staticmethod
    def match(stage, mask, recs):
        rl, idx = stage
        obs = set((r[1], r[0], r[2]) for r in recs)
        cand = idx.get(mask, [])
        wild = idx.get(0x100, [])
        if cand and wild:
            seq = sorted(cand + wild, key=lambda r: r.index)
        else:
            seq = cand or wild
        for rule in seq:
            ok = True
            for c in rule.conds:
                if (c.dir, c.id, c.state) in obs:
                    continue
                if c.state == 0 and ((c.dir, c.id, 0) in obs or (c.dir, c.id, 5) in obs):
                    continue
                ok = False
                break
            if ok:
                return rule
        return None

    # ------------------------------------------------------------------ FUN_100165d8
    def commit(self, net, cell, results):
        cfg = NETCFG[net]
        lay = self.layer(net)
        if not cfg["under"] and self.C.is_water(*cell):
            return False
        ok = False
        for r in results:
            dx, dy = DIRS[r.dir]
            t = (cell[0] + dx, cell[1] + dy)
            if not self.inb(*t):
                continue
            if r.id == 0:
                occ = lay.get(t)
                if occ is not None and occ.removable():
                    del lay[t]
                continue
            piece = Piece(r.id, r.state & 3, self.C.h(*t))
            if t not in lay:
                lay[t] = piece
                ok = True
            else:
                occ = lay[t]
                ok = False
                if (self.predA(net, occ) or self.predCross(net, occ)) and occ.removable():
                    lay[t] = piece
                    ok = True
        return ok

    # ------------------------------------------------------------------ FUN_10016327
    def evaluate(self, net, work, pending_set, changed, deferred, stage_name, mode):
        stage = self.R.stage(stage_name, net)
        lay = self.layer(net)
        work_set = set(work)
        for cell in list(work):
            if not self.flat(*cell):
                continue
            mask, recs = self.collect(net, cell, pending_set, work_set, mode)
            rule = self.match(stage, mask, recs)
            if rule is None or not rule.results:
                if self.o.trace:
                    self.events.append(Event(stage=stage_name, cell=cell, rule=rule, mask=mask,
                                             obs=recs, results=None, committed=False,
                                             why="no rule" if rule is None else "empty result"))
                continue
            ok = True
            why = None
            for r in rule.results:
                dx, dy = DIRS[r.dir]
                t = (cell[0] + dx, cell[1] + dy)
                if self.inb(*t):
                    if not self.flat(*t):
                        ok, why = False, "target %s not flat" % (t,)
                    occ = lay.get(t)
                    if occ is not None:
                        if not self.predA(net, occ) and not self.predCross(net, occ):
                            ok, why = False, "target %s holds a foreign piece %d" % (t, occ.id)
                        elif (net != 3 and self.R.is_protected(net, occ.id)
                              and not (r.id == 0 and r.state == 5)):
                            ok, why = False, "target %s is Protected (%d)" % (t, occ.id)
                if not ok:
                    break
            if self.o.trace:
                self.events.append(Event(stage=stage_name, cell=cell, rule=rule, mask=mask,
                                         obs=recs, results=rule.results, committed=ok, why=why))
            if not ok:
                continue
            self.commit(net, cell, rule.results)
            for r in rule.results:
                dx, dy = DIRS[r.dir]
                t = (cell[0] + dx, cell[1] + dy)
                (deferred if (r.id == 0 and r.state == 0) else changed).append(t)

    # ------------------------------------------------------------------ FUN_1001a2c0
    def slope_lookup(self, net, cell, slope_set, flag):
        if self.slope_rows is None:
            return None
        x, y = cell
        if net in (1, 2, 5, 6):
            tab = self.slope_tab[net]
        elif net == 3:
            tab = self.slope_tab["powr_b"] if (x + y) % 5 == 0 else self.slope_tab["powr_a"]
        elif net == 4:
            tab = self.slope_tab["hway_absent"] if flag else self.slope_tab["hway_present"]
        else:
            return None
        c = self.corners(x, y)
        if c is None:
            return None
        for row in range(8):
            if c == self.slope_rows[row]:
                break
        else:
            return None
        if net == 3:
            ax, ay = (1, 0) if row % 2 == 0 else (0, 1)
            fwd = (x + ax, y + ay) in slope_set
            back = (x - ax, y - ay) in slope_set
            if not (fwd and back):
                tab = self.slope_tab["powr_b"]
        elif net == 4:
            sx, sy = (0, 1) if row % 2 == 0 else (1, 0)
            tab = (self.slope_tab["hway_present"] if (x + sx, y + sy) in slope_set
                   else self.slope_tab["hway_absent"])
        v = tab[row]
        return (v >> 8) & 0xFFFF, v & 0xFF, row

    # ------------------------------------------------------------------ FUN_100167d4
    def cross_build(self, net, cell, toggle, ddx, ddy):
        cfg = NETCFG[net]
        lay = self.layer(net)
        if not cfg["under"] and self.C.is_water(*cell):
            return False
        occ = lay.get(cell)
        if occ is None or self.cross_matrix is None:
            return False
        if (not self.predA(net, occ) and not self.predCross(net, occ)) or self.R.is_protected(net, occ.id):
            return False
        est = occ.state
        N = net
        b = True
        if net == 4:
            if ddy != 0:
                N = 5
            if not toggle:
                if ddx < 0 or ddy < 0:
                    b = False
            elif ddx > 0 or ddy > 0:
                b = False
        elif est == 0:
            b = False
        pid = occ.id
        E, hit = 0, False
        if pid == 0x49:
            E, hit = 4, True
        elif pid in (0xE, 0xF):
            if pid == 0xF and est == 0:
                b = True
            E, hit = 3, True
        elif pid == 0x1D:
            E, hit = 1, True
        elif pid == 0x2C:
            E, hit = 2, True
        elif pid == 0x5C:
            E, hit = 3, True
        elif pid == 0x2BC4:
            if net != 4 and est == 2:
                b = False
            E, hit = 1, True
        elif pid == 0x3ACB:
            E, hit = 5, True
        idx = (E + N * 6) if b else (N + E * 6)
        v = self.cross_matrix[idx] if idx < 36 else 0
        if not hit or v == 0:
            return False
        if not occ.removable():
            return False
        lay[cell] = Piece(v >> 8, v & 3, self.C.h(*cell))
        return True

    # ------------------------------------------------------------------ FUN_1001547b
    def retile(self, net, nodes):
        cfg = NETCFG[net]
        lay = self.layer(net)
        nodes = list(nodes)
        n = self.C.n
        ddx = ddy = 0
        if net == 4 and len(nodes) >= 2:
            ddx = nodes[1][0] - nodes[0][0]
            ddy = nodes[1][1] - nodes[0][1]
        node_set = set(nodes)
        r = cfg["radius"]
        flood = set()
        for (xc, yc) in nodes:
            occb = [0] * 32
            for x in range(xc - r, xc + r):
                for y in range(yc - r, yc + r):
                    if 0 <= x < n and 0 <= y < n:
                        o = lay.get((x, y))
                        if (x, y) in node_set or (o is not None and self.predA(net, o)):
                            occb[16 + y - yc] |= 1 << (16 + x - xc)
            w = [0] * 32
            w[16] = 1 << 16
            for _it in range(32):
                ch = False
                for i in range(32):
                    u = w[i]
                    v = ((u >> 1) | ((u << 1) & 0xFFFFFFFF) | u) & occb[i]
                    ch |= v != u
                    w[i] = v
                for i in range(30):
                    u = w[i + 1]
                    v = (w[i] | w[i + 1] | w[i + 2]) & occb[i + 1]
                    ch |= v != u
                    w[i + 1] = v
                if not ch:
                    break
            for x in range(xc - r, xc + r):
                for y in range(yc - r, yc + r):
                    if 0 <= x < n and 0 <= y < n and w[16 + y - yc] >> (16 + x - xc) & 1:
                        flood.add((x, y))
        flood = sorted(flood)
        changed = []
        toggle = False
        for c in nodes:                                  # crossing pre-pass
            toggle = not toggle
            o = lay.get(c)
            if o is not None and self.test(o, SURFACE_FLAG):
                if self.cross_build(net, c, toggle, ddx, ddy):
                    changed.append(c)
        work = []
        prot74 = []
        for c in flood:                                  # remove the region
            if not self.inb(*c):
                continue
            o = lay.get(c)
            if o is not None and self.predA(net, o):
                if not self.R.is_protected(net, o.id):
                    if o.removable():
                        work.append(c)
                        del lay[c]
                elif net == 3:
                    prot74.append(c)
        work.extend(nodes)
        work = sorted(set(work))
        for c in work:
            o = lay.get(c)
            if self.inb(*c) and o is not None and self.predA(net, o) and self.R.is_protected(net, o.id):
                changed.append(c)
        ch = set(changed)
        work = [c for c in work if c not in ch]
        changed = []
        slope = [c for c in work if not self.flat(*c) and self.legal_slope(*c)]
        list70 = list(work)
        list74 = prot74 + list(work)
        sl = set(slope)
        work = [c for c in work if c not in sl]
        flag = not (ddy + ddx < 0)
        for c in slope:                                  # slope pass
            flag = not flag
            got = self.slope_lookup(net, c, sl, flag)
            if got is None:
                continue
            pid, st, row = got
            res = [Rec(pid, SELF, st)]
            ok = self.commit(net, c, res)
            if self.o.trace:
                self.events.append(Event(stage="slope", cell=c, rule=None, mask=row, obs=None,
                                         results=res, committed=ok, why="slope row %d" % row))
        pending = set(list70)
        deferred = []
        while True:                                      # Simple, to fixpoint
            n0 = len(work)
            changed = []
            self.evaluate(net, work, pending, changed, deferred, "Simple", 8)
            cs = set(changed)
            work = [c for c in work if c not in cs]
            if len(work) == n0:
                break
        passes = 0
        while True:                                      # Complex, at most 5
            changed = []
            self.evaluate(net, list74, pending, changed, deferred, "Complex", 0x18)
            cs = set(changed)
            work = [c for c in work if c not in cs]
            passes += 1
            if not changed or passes >= 5:
                break
        work = work + list(deferred)                     # final, once
        changed = []
        self.evaluate(net, work, pending, changed, [], "final", 4)
        return list70


class Exemplars:
    """Connectivity masks of the piece exemplars {0xE223741F, 0xA317745F, id}: TKB1 properties
    310 (sel 0, +0x140), 311 (sel 1, +0x144), 312 (sel 2, +0x148)."""
    PROPS = (310, 311, 312)

    def __init__(self, occupant_dir):
        import ixf_parse
        import sprite_patch
        self.masks = {}
        for f in sorted(os.listdir(occupant_dir)):
            if not f.lower().startswith("occupantattribs") or not f.lower().endswith(".ixf"):
                continue
            recs, d = ixf_parse.parse(os.path.join(occupant_dir, f))
            for r in recs:
                if r["type"] == 0xE223741F and r["group"] == 0xA317745F:
                    props = sprite_patch.parse_tkb1(d[r["offset"]:r["offset"] + r["size"]])
                    self.masks[r["instance"]] = tuple(props.get(p, 0) or 0 for p in self.PROPS)

    def mask(self, pid, sel):
        m = self.masks.get(pid)
        if m is None or not 0 <= sel <= 2:
            return None if m is None else 0
        return m[sel]


def load_pe(game):
    from .pe_tables import Simntwrk
    return Simntwrk(game)
