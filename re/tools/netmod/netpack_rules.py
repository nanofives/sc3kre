#!/usr/bin/env python3
r"""netpack_rules.py - structured edits to Apps\Res\TilingRules\*.txt for netpack packages (2026-10-13).

A package never edits rule files by byte offset. It names a rule by its number in the STOCK file or by its content,
says what to change, and this module applies the edit to the parsed file and renders it back. Rules nobody edited
are re-emitted as their original lines, so an edit touches only the lines it has to.

File families (grammar: re/tools/tilingrules.py, formats/TILINGRULES.md):
  RULES          *_SimpleRules, *_ComplexRules, *_final, Landfill*: "0,N" then N rules of
                 1,selector / 2,C / C x "3,dir,val" / 4,R / R x "5,dir,val"   (C and R are derived here)
  BRACED         *_Set.txt, DIAG_Set.txt: any integer token is a member (SIMNTWRK FUN_1001746e)
  COUNTED_LIST   *_Protected.txt: line 1 = N, then N ids
  COUNTED_PAIRS  *_Convert.txt, *_Complex_Convert.txt: line 1 = N, then N "from,to"

Edit objects (the "rules" list of a manifest; JSON Schema in netpack.schema.json):
  {"file": F, "op": "set_results",  "match": M, "results": [[dir, val], ...]}
  {"file": F, "op": "replace_rule", "match": M, "rule": R}
  {"file": F, "op": "insert_rule",  "rule": R, "before": M | "after": M | "at": "start" | "end"}
  {"file": F, "op": "delete_rule",  "match": M}
  {"file": F, "op": "set_add",      "ids": [id, ...]}             BRACED
  {"file": F, "op": "list_add",     "ids": [id, ...]}             COUNTED_LIST
  {"file": F, "op": "pairs_add",    "pairs": [[from, to], ...]}   COUNTED_PAIRS
R = {"selector": int, "conds": [[dir, val], ...], "results": [[dir, val], ...]}
M = {"rule": N} (1-based number in the stock file, as netcat prints it) and/or any of "selector", "conds", "results"
    (exact; conds and results are order-sensitive), plus "expect": how many rules must match (default 1).
val = int (raw id*256+state, or a sentinel < 256) or "ID:STATE" (state 0..3).

Library entry point for other tools (the netrules editor): apply(name, stock_bytes, edits) -> new bytes.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from tilingrules import DEAD  # noqa: E402  files the game never reads (formats/TILINGRULES.md)

DEAD_LOWER = {n.lower() for n in DEAD}
CRLF = b"\r\n"


class RuleEditError(Exception):
    pass


def family(name):
    n = name.lower()
    if n in DEAD_LOWER:
        return None
    if n.endswith("_set.txt"):
        return "BRACED"
    if "protected" in n:
        return "COUNTED_LIST"
    if n.endswith("convert.txt"):
        return "COUNTED_PAIRS"
    if "rules" in n or n.endswith("_final.txt") or n.startswith("landfill"):
        return "RULES"
    return None


def stage_mode(name):
    """-> the stage mode a RULES file is loaded into (exclusive bound on dir and on selector bits), or None.
    Same table as tilingrules.stage_mode: FUN_1001547b runs Simple (8) -> Complex (0x18) -> final (4)."""
    n = name.lower()
    if n.endswith("_final.txt"):
        return 4
    if "complexrules" in n:
        return 0x18
    if "simplerules" in n:
        return 8
    return None


def value(v):
    """int or "ID:STATE" -> int."""
    if isinstance(v, bool):
        raise RuleEditError("value %r is not a number" % (v,))
    if isinstance(v, int):
        if v < 0:
            raise RuleEditError("negative value %d" % v)
        return v
    m = re.fullmatch(r"\s*(\d+)\s*:\s*(\d+)\s*", str(v))
    if not m:
        raise RuleEditError("value %r is neither an int nor \"ID:STATE\"" % (v,))
    pid, st = int(m.group(1)), int(m.group(2))
    if st > 3:
        raise RuleEditError("state %d in %r: only 0..3 occur in shipped rules" % (st, v))
    if not 0 < pid <= 0xFFFF:
        raise RuleEditError("piece id %d in %r does not fit 16 bits" % (pid, v))
    return pid * 256 + st


def pairs(lst, what):
    out = []
    for p in lst or []:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise RuleEditError("%s entry %r is not [dir, val]" % (what, p))
        d = p[0]
        if not isinstance(d, int) or not (0 <= d <= 23 or d == 255):
            raise RuleEditError("%s dir %r: 0..23 or 255 (SIMNTWRK 0x10032134 table)" % (what, d))
        out.append((d, value(p[1])))
    return out


# --------------------------------------------------------------------------- RULES files

class Rule:
    __slots__ = ("stock_no", "lines", "sel", "conds", "results")

    def __init__(self, sel, conds, results, stock_no=None, lines=None):
        self.sel, self.conds, self.results = sel, list(conds), list(results)
        self.stock_no, self.lines = stock_no, lines

    def render(self):
        if self.lines is not None:
            return self.lines
        out = [b"1,%d" % self.sel, b"2,%d" % len(self.conds)]
        out += [b"3,%d,%d" % c for c in self.conds]
        out += [b"4,%d" % len(self.results)]
        out += [b"5,%d,%d" % r for r in self.results]
        return out


def _ints(line):
    return [int(x) for x in line.split(b",")]


def parse_rules(data):
    """-> (rules, trailer lines). Refuses anything the 9-state parser (SIMNTWRK FUN_10022676) would not accept."""
    lines = data.split(CRLF)
    if lines and lines[-1] == b"":
        lines = lines[:-1]
    head = _ints(lines[0])
    if len(head) != 2 or head[0] != 0:
        raise RuleEditError("first line %r is not 0,N" % lines[0])
    n, k, rules = head[1], 1, []
    for no in range(1, n + 1):
        start = k
        try:
            op, sel = _ints(lines[k])
            assert op == 1
            op, c = _ints(lines[k + 1])
            assert op == 2
            conds = [tuple(_ints(x)[1:]) for x in lines[k + 2:k + 2 + c]]
            assert all(_ints(x)[0] == 3 for x in lines[k + 2:k + 2 + c])
            k += 2 + c
            op, r = _ints(lines[k])
            assert op == 4
            results = [tuple(_ints(x)[1:]) for x in lines[k + 1:k + 1 + r]]
            assert all(_ints(x)[0] == 5 for x in lines[k + 1:k + 1 + r])
            k += 1 + r
        except (AssertionError, ValueError, IndexError):
            raise RuleEditError("rule %d at line %d does not parse" % (no, start + 1))
        rules.append(Rule(sel, conds, results, stock_no=no, lines=lines[start:k]))
    return rules, lines[k:]


def render_rules(rules, trailer):
    out = [b"0,%d" % len(rules)]
    for r in rules:
        out += r.render()
    out += trailer
    return CRLF.join(out) + CRLF


def _matches(rule, m):
    if "rule" in m and rule.stock_no != m["rule"]:
        return False
    if "selector" in m and rule.sel != m["selector"]:
        return False
    if "conds" in m and rule.conds != pairs(m["conds"], "match conds"):
        return False
    if "results" in m and rule.results != pairs(m["results"], "match results"):
        return False
    return True


def find(rules, m, where):
    if not isinstance(m, dict) or not any(k in m for k in ("rule", "selector", "conds", "results")):
        raise RuleEditError("%s: match needs \"rule\" and/or \"selector\"/\"conds\"/\"results\"" % where)
    hits = [i for i, r in enumerate(rules) if _matches(r, m)]
    want = m.get("expect", 1)
    if len(hits) != want:
        raise RuleEditError("%s: match %s found %d rule(s), expected %d" % (where, _short(m), len(hits), want))
    return hits


def _short(m):
    return "{" + ", ".join("%s=%s" % (k, m[k]) for k in sorted(m) if k != "expect") + "}"


def make_rule(r, where):
    if not isinstance(r, dict) or "selector" not in r:
        raise RuleEditError("%s: rule needs \"selector\"" % where)
    if not isinstance(r["selector"], int) or r["selector"] < 0:
        raise RuleEditError("%s: selector %r" % (where, r["selector"]))
    res = pairs(r.get("results"), where + " results")
    if not res:
        raise RuleEditError("%s: a rule with no results places nothing" % where)
    return Rule(r["selector"], pairs(r.get("conds"), where + " conds"), res)


def lint(name, rules):
    """-> problems for the rules this edit set created or changed (tilingrules.py --lint invariants)."""
    mode = stage_mode(name)
    probs = []
    if not mode:
        return probs
    for i, r in enumerate(rules):
        if r.lines is not None:
            continue
        if r.sel != 0x100 and r.sel >> mode:
            probs.append("%s: rule at position %d: selector 0x%x sets bits >= mode %d" % (name, i + 1, r.sel, mode))
        for d, v in r.conds + r.results:
            if d != 255 and d >= mode:
                probs.append("%s: rule at position %d: dir %d >= mode %d, unreachable in this stage" % (name, i + 1, d, mode))
    return probs


def apply_rules_file(name, data, edits):
    rules, trailer = parse_rules(data)
    for n, e in enumerate(edits):
        where = "%s%s edit %d (%s)" % (e.get("_pack", "") and e["_pack"] + ": ", name, n + 1, e.get("op"))
        op = e.get("op")
        if op == "set_results":
            for i in find(rules, e.get("match"), where):
                r = rules[i]
                rules[i] = Rule(r.sel, r.conds, pairs(e.get("results"), where), stock_no=r.stock_no)
        elif op == "replace_rule":
            for i in find(rules, e.get("match"), where):
                nr = make_rule(e.get("rule"), where)
                nr.stock_no = rules[i].stock_no
                rules[i] = nr
        elif op == "delete_rule":
            for i in sorted(find(rules, e.get("match"), where), reverse=True):
                del rules[i]
        elif op == "insert_rule":
            nr = make_rule(e.get("rule"), where)
            if "before" in e or "after" in e:
                key = "before" if "before" in e else "after"
                m = dict(e[key])
                if m.get("expect", 1) != 1:
                    raise RuleEditError("%s: an insert anchor must match exactly one rule" % where)
                i = find(rules, m, where)[0]
                rules.insert(i if key == "before" else i + 1, nr)
            elif e.get("at") == "start":
                rules.insert(0, nr)
            elif e.get("at") == "end":
                rules.append(nr)
            else:
                raise RuleEditError("%s: insert_rule needs before / after / at" % where)
        else:
            raise RuleEditError("%s: op %r does not apply to a RULES file" % (where, op))
    probs = lint(name, rules)
    if probs:
        raise RuleEditError("; ".join(probs))
    return render_rules(rules, trailer)


# --------------------------------------------------------------------------- list files

def braced_ids(data):
    return [int(x) for x in re.findall(rb"\d+", data)]


def set_add(data, ids):
    """Add ids before the closing brace (format kept: ", <id>" like the shipped lists)."""
    have = set(braced_ids(data))
    k = data.rindex(b"}")
    add = b"".join(b", %d" % i for i in ids if i not in have)
    return data[:k] + add + data[k:]


def counted_add(data, items):
    """COUNTED_LIST / COUNTED_PAIRS: append lines, rewrite the count on line 1."""
    lines = data.split(CRLF)
    if lines and lines[-1] == b"":
        lines = lines[:-1]
    n = int(lines[0])
    body = lines[1:1 + n]
    have = set(body)
    for it in items:
        if it not in have:
            body.append(it)
            have.add(it)
    return CRLF.join([b"%d" % len(body)] + body + lines[1 + n:]) + CRLF


def apply(name, data, edits):
    """Apply `edits` (all for this one file) to `data` (the stock bytes) -> new bytes."""
    fam = family(name)
    if fam is None:
        raise RuleEditError("%s: not an editable TilingRules file (unknown, or DEAD: the game never reads it)" % name)
    if fam == "RULES":
        return apply_rules_file(name, data, edits)
    for n, e in enumerate(edits):
        where = "%s%s edit %d (%s)" % (e.get("_pack", "") and e["_pack"] + ": ", name, n + 1, e.get("op"))
        op = e.get("op")
        if fam == "BRACED" and op == "set_add":
            ids = [value(i) if isinstance(i, str) else i for i in e.get("ids", [])]
            if any(not (0 < i <= 0xFFFF) for i in ids):
                raise RuleEditError("%s: Set ids are raw piece ids (1..65535)" % where)
            data = set_add(data, ids)
        elif fam == "COUNTED_LIST" and op == "list_add":
            data = counted_add(data, [b"%d" % i for i in e.get("ids", [])])
        elif fam == "COUNTED_PAIRS" and op == "pairs_add":
            data = counted_add(data, [b"%d,%d" % (value(a), value(b)) for a, b in e.get("pairs", [])])
        else:
            raise RuleEditError("%s: op %r does not apply to a %s file" % (where, op, fam))
    return data


def result_ids(data):
    """-> set of piece ids a RULES file can place (every RESULT value >= 256)."""
    rules, _ = parse_rules(data)
    return {v >> 8 for r in rules for _, v in r.results if v >= 256}
