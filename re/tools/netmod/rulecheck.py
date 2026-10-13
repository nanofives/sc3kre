"""rulecheck.py -- what the SIMNTWRK engine does with a TilingRules rule: the one set of checks behind
`netrules lint`, `netrules apply-edits` and `netpack validate / build / install` (2026-10-13, child/packlint).

Every bound below is taken from tiler.py (the re-implementation validated in re/analysis/TILER_SIM.md) or from
the function it cites; nothing here keeps its own copy of a table. Image base 0x10000000, Ghidra VAs.

Severities
  ERROR    the game would read the file differently from what it says, or a record points outside the
           engine's tables: a package with one is refused, `netrules lint` exits 1.
  WARNING  legal, but the rule (or one condition) can never take effect: it never matches, or an earlier
           rule always matches first.
  INFO     legal and harmless (a rule that duplicates an earlier one).

Checks, per stage file (tiler.Rules.FILES, the names FUN_100175ed builds) and stage mode (FUN_1001547b runs
Simple = 8, Complex = 0x18, final = 4):
  misparse     FUN_10022676 (ERROR). The parser is a token state machine: it stores a rule when its `4,N`
               result count is reached, never reads `2,N` back, and resets the selector to 0 after each stored
               rule (FUN_10022338). The file is re-read that way and compared with its `1,` records.
  bad-value    (ERROR) a dir outside the 25-entry table FUN_1002205c reads at 0x10032134 (0..23, and 0xff,
               which the parser turns into 0x1f = self): entries 24..31 hold zero offsets, from 32 on the bytes
               belong to other data, so a result there lands on another cell. Also an id over 0xFFFF, a state
               over 3 with an id, or id 0 with a state other than 5 / 1 / 0: none of the 4,219 shipped rules
               uses one (tilingrules.py --lint) and what the piece factory does with it was not read.
  never-matches (WARNING)
               - a Complex selector other than 0x100 or 0: FUN_10019768 writes no mask bit in mode 0x18
                 (every FUN_10022092 call sits in the other branch), so the mask FUN_100222f9 compares is 0;
               - a Simple / final selector with a bit >= the mode: a mask bit d is set only for d < mode;
               - a Simple / final condition outside the 3x3 ring (dirs 0..7): the collector walks x-1..x+1,
                 z-1..z+1. Dirs 4..7 ARE reported in the final stage: FUN_1001a056 sets the dir with no mode
                 test (the old netpack lint refused them);
               - a Simple / final condition (dir != self, id 0, ...): an id-0 record keeps dir 0x1f
                 (FUN_100220b7 sets it, FUN_1001a056 only overwrites it for predicate-A occupants);
               - two different conditions at one dir: one cell yields one record.
  shadowed     (WARNING) an earlier rule matches whenever this one would (first match wins, FUN_100228ff;
               selector 0x100 or equal, FUN_100222f9; in Complex 0 and 0x100 both match the zero mask).
  duplicate    (INFO) the same rule as an earlier one, conditions in another order.
  unknown-id   (WARNING) a result id in no *_GRND_Set.txt nor DIAG_Set.txt.
Result dirs are never compared with the stage mode: FUN_10016327 does not, any of the 24 dirs is legal in any
stage (the old netpack lint refused results at dir >= mode).

Findings carry a position-free key, so "only what an edit adds" (`lint --base`, netpack against stock) is not
thrown off by an insert shifting the rules after it.
"""
import os
import re
from collections import Counter

from . import tiler

ERROR, WARNING, INFO = "ERROR", "WARNING", "INFO"
STAGES = (("Simple", 8), ("Complex", 0x18), ("final", 4))      # FUN_1001547b order (tiler.Tiler.retile)
WILDCARD = 0x100                                               # FUN_100222f9: matches any mask
RING = 8                                                       # 3x3 collector of modes 4 / 8: dirs 0..7
SENTINEL_STATES = (5, 1, 0)                                    # id 0: empty / pending / foreign (FUN_1001a056)
MAX_ID = 0xFFFF
MAX_STATE = 3


def stage_files():
    """-> {file name lower: (stage name, mode, net)} for every file the engine loads into a stage."""
    out = {}
    for net, names in tiler.Rules.FILES.items():
        for (stage, mode), n in zip(STAGES, names):
            out[n.lower()] = (stage, mode, net)
    return out


_STAGE_FILES = stage_files()


def stage_mode(name):
    """-> the mode a RULES file is loaded into (8 / 0x18 / 4), None if the engine does not load it as a stage."""
    s = _STAGE_FILES.get(os.path.basename(name).lower())
    return s[1] if s else None


def engine_dir(d):
    """The dir byte as FUN_10022676 stores it: (char)atoi, 0xff -> 0x1f."""
    d &= 0xFF
    return tiler.SELF if d == 0xFF else d


# ---------------------------------------------------------------------------- labels (also used by netrules)
# dir -> label by grid offset. The engine has no compass (NETWORK_RULE_ENGINE.md 13), so offsets, not N/E/S/W.
def dlabel(d):
    if d == tiler.SELF:
        return "self"
    if d not in tiler.DIRS:
        return "dir %d" % d
    dx, dy = tiler.DIRS[d]
    return "%s%s" % ("" if not dx else ("x%+d" % dx), "" if not dy else ("z%+d" % dy))


def mask_label(m):
    if m == WILDCARD:
        return "any"
    bits = [dlabel(d) for d in range(24) if m >> d & 1]
    return "0x%x (%s)" % (m, " ".join(bits) if bits else "none")


def rec_label(dir_, pid, st):
    if pid == 0:
        return "%s:%s" % (dlabel(dir_), {5: "empty", 1: "pending", 0: "empty-or-foreign"}.get(st, "0/%d" % st))
    return "%s:%d/%d" % (dlabel(dir_), pid, st)


# ---------------------------------------------------------------------------- findings
class Finding:
    __slots__ = ("severity", "kind", "file", "index", "line", "sig", "msg", "ref")

    def __init__(self, severity, kind, rule, msg, ref=""):
        self.severity, self.kind, self.msg, self.ref = severity, kind, msg, ref
        self.file, self.index, self.line = rule.file, rule.index, rule.line
        self.sig = (rule.selector, tuple(rule.conds), tuple(rule.results))

    def key(self):
        """Position-free identity: the same finding on the same rule content in the same file."""
        return (self.kind, self.file.lower(), self.sig, self.msg)

    def text(self):
        return "%s rule #%d (line %d): %s%s" % (self.file, self.index, self.line, self.msg, self.ref)

    def __str__(self):
        return "[%s %s] %s" % (self.severity, self.kind, self.text())


def record_problem(d, pid, st):
    """-> why a record (as the file states it: dir, id, state) is outside the engine's tables, or None."""
    if not 0 <= d <= 0xFF:
        return "dir %d: the parser keeps one byte of it (FUN_10022676)" % d
    if engine_dir(d) not in tiler.DIRS:
        return "dir %d is outside the 25-entry table FUN_1002205c reads at 0x10032134 (0..23, 255 = self)" % d
    if pid < 0 or pid > MAX_ID:
        return "id %d is outside 1..65535" % pid
    if pid == 0 and st not in SENTINEL_STATES:
        return "id 0 takes state 5 (empty), 1 (pending) or 0 (foreign), not %d (FUN_1001a056)" % st
    if pid and not 0 <= st <= MAX_STATE:
        return ("state %d with id %d: an id's state is the 2-bit orientation (0..3) every shipped rule uses; "
                "the piece factory's handling of other values was not read" % (st, pid))
    return None


def engine_parse(data):
    """Re-read a RULES file the way FUN_10022552 + FUN_10022676 do -> [(selector, conds, results)], records as
    (engine dir, id, state). Tokens: strtok over the file (the delimiter string at the call is not visible in the
    export; ',' CR LF assumed, the only separators the shipped and netpack-written files use), a token whose first
    character is not a digit is skipped (isdigit), values through atoi."""
    state, sel, rcount, nres, cur, conds, results, out = 0, 0, 0, 0, tiler.SELF, [], [], []
    nxt = {0: 1, 1: 2, 2: 3, 3: 4, 4: 6, 5: 7}
    for tok in re.split(rb"[,\r\n]+", data):
        m = re.match(rb"\d+", tok)
        if not m:
            continue
        v = int(m.group())
        if state == 0:
            state = nxt.get(v, 0)
        elif state in (1, 2, 3, 6):          # 1 header count (+0x14), 2 selector, 3 cond count (+0x18), 6 result count
            if state == 2:
                sel = v
            elif state == 6:
                rcount = v
            state = 0
        elif state in (4, 7):
            cur = engine_dir(v)
            state = 5 if state == 4 else 8
        elif state == 5:
            conds.append((cur, v >> 8, v & 0xFF))
            cur, state = tiler.SELF, 0
        else:                                 # 8: result; the rule is stored when the count is reached
            results.append((cur, v >> 8, v & 0xFF))
            cur, state = tiler.SELF, 0
            nres += 1
            if nres == rcount:
                out.append((sel, tuple(conds), tuple(results)))
                conds, results, nres, sel = [], [], 0, 0
    return out


def _declared(rl):
    return [(r.selector, tuple((engine_dir(c.dir), c.id, c.state) for c in r.conds),
             tuple((engine_dir(x.dir), x.id, x.state) for x in r.results)) for r in rl]


def _implied(ci, cj):
    """A condition of rule i is met whenever rule j's condition cj is (same dir and id; state equal, or ci.state
    0 which also accepts an observed 5, FUN_100220c5)."""
    return ci.dir == cj.dir and ci.id == cj.id and (ci.state == cj.state or (ci.state == 0 and cj.state in (0, 5)))


def _can_reach(sel_i, sel_j, mode):
    """Rule i (earlier) is tried whenever rule j would be: FUN_100222f9 takes selector 0x100 or == mask."""
    if mode == 0x18:
        return sel_i in (0, WILDCARD)
    return sel_i in (WILDCARD, sel_j)


def lint_stage(rl, mode, stage_name, sets, data=None):
    """Findings for one stage file. rl = [tiler.Rule]; sets = {tag: set of ids}; data = the file bytes (for the
    misparse check)."""
    out = []
    if data is not None and rl:
        got, want = engine_parse(data), _declared(rl)
        if got != want:
            k = next((i for i in range(min(len(got), len(want))) if got[i] != want[i]), min(len(got), len(want)))
            r = rl[min(k, len(rl) - 1)]
            out.append(Finding(ERROR, "misparse", r, "the game reads this file as %d rules, its `1,` records "
                               "declare %d, and they part from this rule on (FUN_10022676 stores a rule when its "
                               "`4,N` result count is reached, does not use `2,N`, a rule with no results runs "
                               "into the next)" % (len(got), len(want))))
    for j, rj in enumerate(rl):
        sel = rj.selector
        bad = False
        for what, recs in (("condition", rj.conds), ("result", rj.results)):
            for c in recs:
                p = record_problem(c.dir, c.id, c.state)
                if p:
                    out.append(Finding(ERROR, "bad-value", rj, "%s %s: %s" % (what, rec_label(c.dir, c.id, c.state), p)))
                    bad = True
        if mode == 0x18 and sel not in (0, WILDCARD):
            out.append(Finding(WARNING, "never-matches", rj, "selector %s in a Complex file can never match: "
                               "FUN_10019768 builds no mask in mode 0x18, so the mask is always 0" % mask_label(sel)))
        elif mode != 0x18 and sel != WILDCARD and sel >> mode:
            out.append(Finding(WARNING, "never-matches", rj, "selector %s sets bits the %s stage never sets "
                               "(FUN_10019768 sets bit d only for d < mode %d)" % (mask_label(sel), stage_name, mode)))
        for c in rj.conds:
            if mode == 0x18 or c.dir == tiler.SELF or c.dir not in tiler.DIRS:
                continue
            if c.dir >= RING:
                out.append(Finding(WARNING, "never-matches", rj, "condition %s is outside the %s stage's 3x3 window "
                                   "(modes 4/8 collect dirs 0..7, FUN_10019768)"
                                   % (rec_label(c.dir, c.id, c.state), stage_name)))
            elif c.id == 0:
                out.append(Finding(WARNING, "never-matches", rj, "condition %s can never be observed in the %s "
                                   "stage: modes 4/8 report neighbours only for occupied cells, and a sentinel record "
                                   "keeps dir self (FUN_1001a056 / FUN_100220b7)"
                                   % (rec_label(c.dir, c.id, c.state), stage_name)))
        dirs = {}
        for c in rj.conds:
            if c.dir != tiler.SELF:
                dirs.setdefault(c.dir, set()).add((c.id, c.state if c.state not in (0, 5) or c.id else 0))
        for d, s in sorted(dirs.items()):
            if len(s) > 1:
                out.append(Finding(WARNING, "never-matches", rj, "two different conditions at %s; one cell yields "
                                   "one record, so the rule never matches" % dlabel(d)))
        if not bad and rj.results:
            for i in range(j):
                ri = rl[i]
                if not ri.results or not _can_reach(ri.selector, sel, mode):
                    continue
                if all(any(_implied(ci, cj) for cj in rj.conds) for ci in ri.conds):
                    if ri.selector == sel and set(ri.conds) == set(rj.conds) and list(ri.results) == list(rj.results):
                        out.append(Finding(INFO, "duplicate", rj, "duplicate of an earlier rule, conditions in "
                                           "another order; never reached, harmless",
                                           " (rule #%d, line %d)" % (ri.index, ri.line)))
                    else:
                        out.append(Finding(WARNING, "shadowed", rj, "never reached: an earlier rule matches first "
                                           "whenever it would (same or wildcard selector, conditions a subset; first "
                                           "match wins, FUN_100228ff)", " (rule #%d, line %d)" % (ri.index, ri.line)))
                    break
        for r in rj.results:
            if r.id and not any(r.id in s for s in sets.values()):
                out.append(Finding(WARNING, "unknown-id", rj, "result %s places id %d, which is in no *_GRND_Set.txt "
                                   "nor DIAG_Set.txt" % (rec_label(r.dir, r.id, r.state), r.id)))
    return out


def lint_rules(rules):
    """-> [Finding] over every stage file of a tiler.Rules."""
    out = []
    for stage_name, mode in STAGES:
        for net in tiler.NET_TAG:
            rl, _ = rules.stage(stage_name, net)
            if not rl:
                continue
            fp = rules.path(rl[0].file)
            with open(fp, "rb") as fh:
                data = fh.read()
            out += lint_stage(rl, mode, stage_name, rules.sets, data)
    return out


def new_findings(found, base):
    """`found` minus `base`, compared by Finding.key() as multisets (an edit's own findings)."""
    have = Counter(f.key() for f in base)
    out = []
    for f in found:
        k = f.key()
        if have[k]:
            have[k] -= 1
        else:
            out.append(f)
    return out


def lint_dir(d, base=None):
    """-> [Finding] for a TilingRules directory; with `base`, only those absent from that directory."""
    found = lint_rules(tiler.Rules(d))
    return new_findings(found, lint_rules(tiler.Rules(base))) if base else found


def lint_files(base_files, new_files):
    """Like lint_dir(new, base) for in-memory directories ({file name: bytes}, new = base overlaid)."""
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="rulecheck_")
    try:
        dirs = []
        for sub, files in (("base", base_files), ("new", dict(base_files, **new_files))):
            p = os.path.join(tmp, sub)
            os.makedirs(p)
            for n, b in files.items():
                with open(os.path.join(p, n), "wb") as fh:
                    fh.write(b)
            dirs.append(p)
        return lint_dir(dirs[1], dirs[0])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def summary(found):
    c = Counter(f.severity for f in found)
    return ", ".join("%d %s" % (c[s], s) for s in (ERROR, WARNING, INFO) if c[s]) or "clean"
