"""rules.py -- every place a piece id appears in Apps\\Res\\TilingRules, with file and line.

Read-only, line-aware. The structural grammar and the live/lazy/DEAD status come from
`re/tools/tilingrules.py` (68/68 round-trip, `formats/TILINGRULES.md`); this module only adds
line numbers and a per-piece index on top.

Value encodings used below:
  * `*_Set.txt`, `DIAG_Set.txt`, `*_Protected.txt`, `Collapse.txt`: raw piece ids.
  * rule values (`3,dir,val` / `5,dir,val`), `*_Convert.txt`, `*_Complex_Convert.txt`,
    `*_Bridges.txt` values >= 256: `pieceId * 256 + state` (`NETWORK_RULE_ENGINE.md` 4.3).
    Checked here, not assumed: `selftest()` asserts every Convert value's id is in the network's
    own Set and every state is 0..3.
"""
import os
import re
import sys

from . import paths

sys.path.insert(0, paths.TOOLS)
import tilingrules as _tr  # noqa: E402

# netType -> network tag. [CONFIRMED @ SIMNTWRK 0x1001547b:104-167 + 0x100175ed, NETWORK_TYPES.md 1]
NETTYPE = {1: "ROAD", 2: "RAIL", 3: "POWR", 4: "HWAY", 5: "PIPE", 6: "SUBW"}
NETS = ["ROAD", "RAIL", "POWR", "HWAY", "PIPE", "SUBW"]
NET_LONG = {"ROAD": "Road", "RAIL": "Rail", "POWR": "Power line", "HWAY": "Highway",
            "PIPE": "Water pipe", "SUBW": "Subway", "DIAG": "Diagonal list"}
# Save instance holding each network (QUERY_ID.md 4.3: inst 2 is PIPE, not rail)
SAVE_INSTANCE = {"ROAD": 1, "RAIL": 1, "POWR": 1, "HWAY": 1, "PIPE": 2, "SUBW": 3}

TOKEN = re.compile(r"\d+")


def status(name):
    if name in _tr.DEAD:
        return "DEAD"
    if name in _tr.LAZY:
        return "lazy"
    return "live"


def stage(name):
    n = name.lower()
    if n.endswith("_final.txt"):
        return "final"
    if "complexrules" in n:
        return "Complex"
    if "simplerules" in n:
        return "Simple"
    if "sloperules" in n:
        return "Slope"
    if n.startswith("landfill"):
        return "Landfill"
    if "complex_convert" in n:
        return "Complex_Convert"
    if n.endswith("_convert.txt"):
        return "Convert"
    if "protected" in n:
        return "Protected"
    if "bridges" in n:
        return "Bridges"
    if n.endswith("_set.txt"):
        return "Set"
    if "exits" in n:
        return "Exits"
    if n == "collapse.txt":
        return "Collapse"
    return "other"


def net_of(name):
    for n in NETS:
        if name.upper().startswith(n + "_"):
            return n
    if name.upper().startswith("DIAG"):
        return "DIAG"
    return None


def _lines(path):
    with open(path, "rb") as fh:
        return fh.read().decode("ascii").splitlines()


def split(v):
    """pieceId*256+state -> (id, state); a value < 256 is a sentinel -> (None, v)."""
    return (None, v) if v < 256 else (v >> 8, v & 0xFF)


class Ref:
    """One appearance of a piece in a rules file."""
    __slots__ = ("file", "line", "stage", "net", "status", "role", "rule", "selector",
                 "dir", "state", "text", "extra")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def as_dict(self):
        return {k: getattr(self, k) for k in self.__slots__ if getattr(self, k) is not None}

    def short(self):
        s = "%s:%d" % (self.file, self.line)
        if self.rule is not None:
            s += " rule %d" % self.rule
        if self.selector is not None:
            s += " sel=0x%x" % self.selector
        s += " %s" % self.role
        if self.dir is not None:
            s += " dir=%s" % self.dir
        if self.state is not None:
            s += " state=%d" % self.state
        if self.extra:
            s += " " + self.extra
        return s


class Rules:
    """Parses every TilingRules file once and indexes references by piece id."""

    def __init__(self, game):
        self.dir = game.tiling
        self.files = sorted(f for f in os.listdir(self.dir) if f.lower().endswith(".txt"))
        self.sets = {}              # net -> [ids in file order]
        self.set_lines = {}         # net -> {id: line}
        self.refs = {}              # id -> [Ref]
        self.collapse_groups = []   # [[ids]]
        self.bridges = {}           # net -> [record dict]
        for f in self.files:
            self._scan(f)

    def _add(self, pid, **kw):
        self.refs.setdefault(pid, []).append(Ref(**kw))

    # ----------------------------------------------------------------- per family

    def _scan(self, f):
        path = os.path.join(self.dir, f)
        lines = _lines(path)
        st, net, stg = status(f), net_of(f), stage(f)
        base = dict(file=f, stage=stg, net=net, status=st)
        if stg == "Set":
            ids, where = [], {}
            for ln, text in enumerate(lines, 1):
                for m in TOKEN.finditer(text):
                    v = int(m.group(0))
                    ids.append(v)
                    where.setdefault(v, ln)
                    self._add(v, line=ln, role="set member", **base)
            self.sets[net] = ids
            self.set_lines[net] = where
        elif stg in ("Simple", "Complex", "final", "Slope", "Landfill"):
            self._scan_rules(lines, base)
        elif stg in ("Convert", "Complex_Convert"):
            for ln, text in enumerate(lines[1:], 2):
                if "," not in text:
                    continue
                a, b = (int(x) for x in text.split(","))
                fa, fs = split(a)
                ta, ts = split(b)
                if fa is not None:
                    self._add(fa, line=ln, role="convert FROM", state=fs, text=text.strip(),
                              extra="-> %s state %s" % (ta, ts), **base)
                if ta is not None:
                    self._add(ta, line=ln, role="convert TO", state=ts, text=text.strip(),
                              extra="<- %s state %s" % (fa, fs), **base)
        elif stg == "Protected":
            for ln, text in enumerate(lines[1:], 2):
                for m in TOKEN.finditer(text):
                    self._add(int(m.group(0)), line=ln, role="protected", **base)
        elif stg == "Bridges":
            self._scan_bridges(lines, base)
        elif stg == "Collapse":
            self._scan_collapse(lines, base)
        elif stg == "Exits":
            for ln, text in enumerate(lines[1:], 2):
                if "," in text:
                    a, b = (int(x) for x in text.split(","))
                    self._add(a, line=ln, role="exits entry", text=text.strip(),
                              extra="second=0x%x" % b, **base)
        else:
            # DEAD braced leftovers (ROAD_GRND_FinalRules.txt, networkIntesection.txt):
            # report tokens whose >>8 is a piece id, as raw values.
            for ln, text in enumerate(lines, 1):
                for m in TOKEN.finditer(text):
                    v = int(m.group(0))
                    pid, s = split(v)
                    if pid is not None:
                        self._add(pid, line=ln, role="value in dead file", state=s,
                                  text=m.group(0), **base)

    def _scan_rules(self, lines, base):
        rule, sel = -1, None
        for ln, text in enumerate(lines, 1):
            t = text.strip()
            if not t:
                continue
            p = [int(x) for x in t.split(",")]
            if ln == 1:
                continue                      # 0,N header
            if p[0] == 1:
                rule += 1
                sel = p[1]
            elif p[0] in (3, 5):
                pid, s = split(p[2])
                if pid is None:
                    continue
                self._add(pid, line=ln, role="condition" if p[0] == 3 else "RESULT",
                          rule=rule, selector=sel, dir=p[1], state=s, text=t, **base)

    def _scan_bridges(self, lines, base):
        """Record shape measured on all 4 live files (see NETMOD_CATALOG.md 'Bridges'):
        line 1 = total token count; each record = [len, a, b, (n, v*n) x 5], len counts itself."""
        toks = [(ln, int(t)) for ln, text in enumerate(lines, 1) for t in TOKEN.findall(text)]
        if not toks:
            return
        total = toks[0][1]
        body = toks[1:]
        recs, i = [], 0
        while i < len(body):
            start_ln, ln_tok = body[i]
            n = ln_tok
            rec_toks = body[i:i + n]
            i += n
            vals = [v for _, v in rec_toks]
            r = {"line": start_ln, "len": n, "a": vals[1], "b": vals[2], "lists": [],
                 "ok": True}
            j = 3
            for k in range(5):
                if j >= len(vals):
                    r["ok"] = False
                    break
                cnt = vals[j]
                r["lists"].append([(rec_toks[j + 1 + q][0], vals[j + 1 + q]) for q in range(cnt)])
                j += 1 + cnt
            if j != n:
                r["ok"] = False
            recs.append(r)
            for li, lst in enumerate(r["lists"]):
                for pos, (ln, v) in enumerate(lst):
                    pid, s = split(v)
                    if pid is not None:
                        self._add(pid, line=ln, role="bridge list %d[%d]" % (li, pos), state=s,
                                  extra="record@%d a=%d b=%d" % (start_ln, r["a"], r["b"]),
                                  **base)
        self.bridges[base["net"]] = {"declared": total, "tokens": len(body), "records": recs}

    def _scan_collapse(self, lines, base):
        """Collapse.txt: line 1 = token count; then groups [n, id*(n-1)] where n counts itself
        (the same convention as a Bridges record). Measured shape, the
        meaning of a group is not decoded here (NETWORK_RULE_ENGINE.md 5: slot 0x100323ac)."""
        toks = [(ln, int(t)) for ln, text in enumerate(lines, 1) for t in TOKEN.findall(text)]
        body, i, g = toks[1:], 0, 0
        while i < len(body):
            n = body[i][1]
            grp = body[i + 1:i + n]
            self.collapse_groups.append([v for _, v in grp])
            for ln, v in grp:
                self._add(v, line=ln, role="collapse group %d" % g, **base)
            i += n
            g += 1
        self.collapse_declared = toks[0][1] if toks else 0
        self.collapse_tokens = len(body)

    # ------------------------------------------------------------------ queries

    def all_ids(self):
        return sorted({i for ids in self.sets.values() for i in ids})

    def sets_of(self, pid):
        return [n for n in NETS + ["DIAG"] if pid in self.sets.get(n, ())]

    def refs_of(self, pid):
        return self.refs.get(pid, [])

    def selftest(self):
        """-> list of (name, ok, detail)."""
        out = []
        want = {"ROAD": 109, "HWAY": 191, "RAIL": 38, "SUBW": 38, "PIPE": 32, "POWR": 26,
                "DIAG": 14}
        for n, w in want.items():
            got = len(self.sets.get(n, []))
            out.append(("Set size %s" % n, got == w, "%d (map says %d)" % (got, w)))
        for f in self.files:
            if stage(f) in ("Convert", "Complex_Convert"):
                net = net_of(f)
                own = set(self.sets[net])
                bad = 0
                for ln, text in enumerate(_lines(os.path.join(self.dir, f))[1:], 2):
                    for v in (int(x) for x in TOKEN.findall(text)):
                        pid, s = split(v)
                        if pid not in own or s > 3:
                            bad += 1
                out.append(("%s values = own-Set id*256+state(0..3)" % f, bad == 0,
                            "%d bad" % bad))
        for net, b in self.bridges.items():
            ok = b["declared"] == b["tokens"] and all(r["ok"] for r in b["records"])
            out.append(("%s_GRND_Bridges.txt record walk" % net, ok,
                        "declared %d tokens, walked %d, %d records" %
                        (b["declared"], b["tokens"], len(b["records"]))))
        out.append(("Collapse.txt group walk", self.collapse_declared == self.collapse_tokens,
                    "declared %d, walked %d, %d groups" % (self.collapse_declared,
                                                           self.collapse_tokens,
                                                           len(self.collapse_groups))))
        return out
