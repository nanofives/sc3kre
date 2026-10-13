#!/usr/bin/env python3
r"""netpack_bridges.py - the netbridge parts of netpack (2026-10-13): variant inheritance, "replace_base", bridge
records and variant crossings. Used by netpack.py merge(); evidence and the walkthrough: re/analysis/NETBRIDGE.md.

1. Inheritance (variant "inherit", default true). Data a variant needs to behave as its base where the game reads
   piece ids from TilingRules files:
   - Set membership in EVERY network Set that holds the base, and DIAG_Set.txt when the base is there. The piece class
     comes from the Set lists (SIMNTWRK FUN_1001a5f2), so a variant of a piece in ROAD and RAIL (crossing 69) gets the
     base's ROAD+RAIL class only when it is in both.
   - <NET>_GRND_Protected.txt membership when the base is listed (FUN_1001a7f7 keeps protected tiles out of re-tiling
     and clearing; bridges, crossings and tunnel ends are protected).
   - Convert and Complex_Convert rows (variant, s) -> what the base reads as, for s = 0..3, in every network whose Set
     holds the base. The tiler reports a neighbour through these tables (FUN_1001a85a, last matching row wins), so a
     rule that tests for the base also matches the variant. Offline arm S1 (verify/netbridge/PRE.md): without the
     rows, replacing road 29 by a variant everywhere changed 818 other tiles in Berlin; with them, 0.
2. "replace_base": true on a variant: every RESULT that places the base in the stage rule files of the variant's
   network is retargeted to the variant (one set_results edit per rule, expect = the stock rule).
3. "bridges": records of <NET>_GRND_Bridges.txt, the only Bridges files the game loads (ROAD, RAIL, HWAY, POWR,
   SIMNTWRK FUN_10017f98). Record = [len, axis, minLen, nA, A.., nB, B.., nC, C.., nD, D.., nE, E..], values
   id << 8 | state. The road / rail / power builder (FUN_1000122a) takes the FIRST record whose axis matches and
   whose minLen <= the crossing length; the highway builder (FUN_10002693) takes the first whose axis key (0..3)
   matches and never reads minLen. A, B, D, E are copied into 5-slot stack buffers and C into 20, unchecked, so the
   lengths are limited here (a longer list overflows the game's stack).
4. "crossings": [{"over": variant, "crossing": stock crossing piece, "piece": variant of that crossing}]: when the
   existing piece is `over`, sc3netmod.dll (XCROSS) builds `piece` instead of the crossing the matrix gives.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import netpack_rules as NR  # noqa: E402

CRLF = b"\r\n"
BRIDGE_NETS = {"ROAD": 2, "RAIL": 2, "POWR": 2, "HWAY": 4}     # network -> number of axis values its builder reads
LIST_MAX = (5, 5, 20, 5, 5)                                     # A, B, C (span), D, E stack buffers
LIST_NAMES = ("a", "b", "span", "d", "e")
FILE_MAX = 0x20000                                              # FUN_100196ce reads into a 0x20000-byte buffer
NETS_ALL = ("ROAD", "RAIL", "POWR", "HWAY", "PIPE", "SUBW")
MATRIX_VA = 0x100318AC
# FUN_100167d4 maps the EXISTING piece id to a matrix index E [CONFIRMED @ 0x100167d4] (as pe_tables.CROSS_E)
CROSS_E = {0x1D: 1, 0x2BC4: 1, 0x2C: 2, 0x0E: 3, 0x0F: 3, 0x5C: 3, 0x49: 4, 0x3ACB: 5}


class BridgeError(Exception):
    pass


# --------------------------------------------------------------------------- Bridges files

def parse_bridges(data):
    """-> list of records, each (axis, min_len, [A, B, C, D, E]) with raw values. Refuses what the builders would
    misread (a len that does not match its lists)."""
    toks = [int(t) for t in data.replace(b",", b" ").split()]
    if not toks:
        return []
    body, recs, k = toks[1:], [], 0
    while k < len(body):
        n = body[k]
        if n < 3 or k + n > len(body):
            raise BridgeError("record at token %d: length %d runs past the file" % (k + 2, n))
        rec = body[k:k + n]
        axis, minlen, lists, j = rec[1], rec[2], [], 3
        for _ in range(5):
            if j >= n:
                raise BridgeError("record at token %d: fewer than 5 lists" % (k + 2))
            c = rec[j]
            lists.append(rec[j + 1:j + 1 + c])
            j += 1 + c
        if j != n:
            raise BridgeError("record at token %d: length %d, lists use %d" % (k + 2, n, j))
        recs.append((axis, minlen, lists))
        k += n
    return recs


def render_bridges(recs):
    body = []
    for axis, minlen, lists in recs:
        r = [axis, minlen]
        for l in lists:
            r += [len(l)] + list(l)
        body += [len(r) + 1] + r
    return CRLF.join(b"%d" % v for v in [len(body)] + body) + CRLF


def rec_from_manifest(r, where):
    try:
        axis, minlen = r["axis"], r.get("min_len", 1)
        lists = [[pid * 256 + st for pid, st in r[k]] for k in LIST_NAMES]
    except (KeyError, TypeError, ValueError):
        raise BridgeError("%s: a record needs axis, a, b, span, d, e as lists of [id, state]" % where)
    return axis, minlen, lists


def rec_to_manifest(rec):
    axis, minlen, lists = rec
    d = {"axis": axis, "min_len": minlen}
    for k, l in zip(LIST_NAMES, lists):
        d[k] = [[v >> 8, v & 0xFF] for v in l]
    return d


def check_record(net, rec, set_ids, where):
    axis, minlen, lists = rec
    if not 0 <= axis < BRIDGE_NETS[net]:
        raise BridgeError("%s: axis %d; the %s builder reads 0..%d" % (where, axis, net, BRIDGE_NETS[net] - 1))
    if not 1 <= minlen <= 255:
        raise BridgeError("%s: min_len %d outside 1..255" % (where, minlen))
    for name, l, mx in zip(LIST_NAMES, lists, LIST_MAX):
        if not 1 <= len(l) <= mx:
            raise BridgeError("%s: %s has %d entries; the builder copies it into a %d-slot stack buffer and reads its "
                              "first entry, so 1..%d" % (where, name, len(l), mx, mx))
        for v in l:
            pid, st = v >> 8, v & 0xFF
            if st > 3:
                raise BridgeError("%s: %s [%d, %d]: state over 3" % (where, name, pid, st))
            if pid not in set_ids:
                raise BridgeError("%s: %s piece %d is not in %s_GRND_Set.txt (merged), so the factory would not give "
                                  "it the %s class" % (where, name, pid, net, net))


def apply_bridge_edits(net, stock_bytes, edits, set_ids):
    """edits: [{"op": "insert", "at": N | "start" | "end", "record": {...}} | {"op": "delete", "record": N,
    "expect": {...}}], N = 0-based index of a STOCK record. All packages' edits to one file in one pass."""
    stock = parse_bridges(stock_bytes)
    keep = [True] * len(stock)
    before = {}
    tail = []
    for e in edits:
        where = "%s bridges (%s)" % (net, e.get("_pack", "?"))
        op = e.get("op")
        if op == "insert":
            rec = rec_from_manifest(e.get("record") or {}, where)
            check_record(net, rec, set_ids, where)
            at = e.get("at", "start")
            if at == "start":
                at = 0
            if at == "end":
                tail.append(rec)
            elif isinstance(at, int) and 0 <= at <= len(stock):
                if at == len(stock):
                    tail.append(rec)
                else:
                    before.setdefault(at, []).append(rec)
            else:
                raise BridgeError("%s: at %r is not 0..%d, \"start\" or \"end\"" % (where, at, len(stock)))
        elif op == "delete":
            n = e.get("record")
            if not isinstance(n, int) or not 0 <= n < len(stock):
                raise BridgeError("%s: record %r is not a stock record index (0..%d)" % (where, n, len(stock) - 1))
            if not keep[n]:
                raise BridgeError("%s: stock record %d deleted twice" % (where, n))
            if rec_from_manifest(e.get("expect") or {}, where) != stock[n]:
                raise BridgeError("%s: stock record %d is %r, not the expected one" % (where, n, rec_to_manifest(stock[n])))
            keep[n] = False
        else:
            raise BridgeError("%s: op %r (insert or delete)" % (where, op))
    out = []
    for i, rec in enumerate(stock):
        out += before.get(i, [])
        if keep[i]:
            out.append(rec)
    out += tail
    data = render_bridges(out)
    if len(data) >= FILE_MAX:
        raise BridgeError("%s_GRND_Bridges.txt would be %d bytes; the loader's buffer is %d" % (net, len(data), FILE_MAX))
    return data


def winners(recs, net, lmax=30):
    """Which record the builder picks, per axis and crossing length (road / rail / power), or per axis (highway)."""
    out = {}
    for axis in range(BRIDGE_NETS[net]):
        if net == "HWAY":
            out[axis] = next((i for i, r in enumerate(recs) if r[0] == axis), None)
            continue
        runs, cur = [], None
        for L in range(1, lmax + 1):
            w = next((i for i, r in enumerate(recs) if r[0] == axis and r[1] <= L), None)
            if not runs or runs[-1][2] != w:
                runs.append([L, L, w])
            else:
                runs[-1][1] = L
        out[axis] = runs
    return out


# --------------------------------------------------------------------------- inheritance

def _real(stock, fname):
    n = [x for x in stock.listdir("Apps/Res/TilingRules") if x.lower() == fname.lower()]
    return n[0] if n else None


def convert_table(data):
    """-> {(id, state): (id, state)}: the last row wins, as FUN_1001a85a reads it."""
    out = {}
    for line in data.split(CRLF)[1:]:
        parts = line.replace(b" ", b"").split(b",")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            a, b = int(parts[0]), int(parts[1])
            out[(a >> 8, a & 0xFF)] = (b >> 8, b & 0xFF)
    return out


def inherit_edits(stock, variants):
    """variants: [{"id", "base", "net", "inherit"}] -> {file: [edits]} (list_add / convert_add, "_pack" set)."""
    edits = {}
    sets = {n: stock.set_ids(n) for n in NETS_ALL}
    diag = set(NR.braced_ids(stock.read("Apps/Res/TilingRules/DIAG_Set.txt"))) if _real(stock, "DIAG_Set.txt") else set()
    prot, conv = {}, {}
    for n in NETS_ALL:
        f = _real(stock, "%s_GRND_Protected.txt" % n)
        prot[n] = (f, {int(x) for x in NR.counted(stock.read("Apps/Res/TilingRules/" + f))[0] if x.strip().isdigit()} if f else set())
        for kind in ("Convert", "Complex_Convert"):
            f = _real(stock, "%s_GRND_%s.txt" % (n, kind))
            conv[(n, kind)] = (f, convert_table(stock.read("Apps/Res/TilingRules/" + f)) if f else {})
    for v in variants:
        if not v.get("inherit", True):
            continue
        vid, base, tag = v["id"], v["base"], "(inherit %d<-%d)" % (v["id"], v["base"])
        for n in NETS_ALL:
            if base not in sets[n]:
                continue
            if n != v["net"]:
                edits.setdefault("%s_GRND_Set.txt" % n, []).append({"op": "list_add", "ids": [vid], "_pack": tag})
            f, ids = prot[n]
            if f and base in ids:
                edits.setdefault(f, []).append({"op": "list_add", "ids": [vid], "_pack": tag})
            for kind in ("Convert", "Complex_Convert"):
                f, tab = conv[(n, kind)]
                if not f:
                    continue
                for s in range(4):
                    to = tab.get((base, s), (base, s))
                    edits.setdefault(f, []).append({"op": "convert_add", "from": [vid, s], "to": list(to), "_pack": tag})
        if base in diag:
            edits.setdefault("DIAG_Set.txt", []).append({"op": "list_add", "ids": [vid], "_pack": tag})
    return edits


def replace_base_edits(stock, v):
    """Every stage-rule RESULT of the variant's network that places the base -> the variant."""
    out = {}
    for fn in stock.listdir("Apps/Res/TilingRules"):
        if not fn.upper().startswith(v["net"] + "_") or NR.family(fn) != "RULES" or not NR.stage_mode(fn):
            continue
        rules, _ = NR.parse_rules(stock.read("Apps/Res/TilingRules/" + fn))
        for r in rules:
            d = r.as_dict()
            if any(x[1] == v["base"] for x in d["results"]):
                out.setdefault(fn, []).append({
                    "op": "set_results", "file": fn, "rule": r.stock_no, "expect": d, "_pack": v["_pack"],
                    "results": [[x[0], v["id"] if x[1] == v["base"] else x[1], x[2]] for x in d["results"]]})
    return out


# --------------------------------------------------------------------------- crossings

def crossing_matrix(stock):
    import pe_read
    pe = pe_read.PE(stock.path("Apps/SIMNTWRK.DLL"))
    return [pe.dword(MATRIX_VA + 4 * k)[0] for k in range(36)]


def check_crossings(stock, packs_crossings, variants_by_id):
    """packs_crossings: [(pack, [entry, ...])] -> {pack: table bytes}. An entry is valid when `over` is a variant whose
    base the crossing switch knows (CROSS_E), `crossing` is a piece the matrix builds for that base, and `piece` is a
    variant whose base is `crossing`."""
    m = crossing_matrix(stock)
    out, seen = {}, {}
    for pack, entries in packs_crossings:
        lines = []
        for e in entries:
            where = "%s crossing %r" % (pack, e)
            o, c, p = e.get("over"), e.get("crossing"), e.get("piece")
            vo, vp = variants_by_id.get(o), variants_by_id.get(p)
            if vo is None:
                raise BridgeError("%s: over %r is not a variant of any installed package" % (where, o))
            ei = CROSS_E.get(vo["base"])
            if ei is None:
                raise BridgeError("%s: the base %d of %d is not one the crossing switch FUN_100167d4 knows (%s)"
                                  % (where, vo["base"], o, sorted(CROSS_E)))
            row = {m[ei * 6 + k] >> 8 for k in range(6) if m[ei * 6 + k]} | {m[k * 6 + ei] >> 8 for k in range(6) if m[k * 6 + ei]}
            if c not in row:
                raise BridgeError("%s: the matrix builds %s over base %d, not %r" % (where, sorted(row), vo["base"], c))
            if vp is None or vp["base"] != c:
                raise BridgeError("%s: piece %r must be a variant whose base is %d" % (where, p, c))
            if (o, c) in seen:
                raise BridgeError("%s: %d over crossing %d is already set by %s" % (where, o, c, seen[(o, c)]))
            seen[(o, c)] = pack
            lines.append(b"%d %d %d" % (o, c, p))
        if lines:
            out[pack] = (b"# netpack %s: <variant> <crossing piece> <replacement>, read by sc3netmod.dll (XCROSS)\r\n"
                         % pack.encode()) + CRLF.join(lines) + CRLF
    return out
