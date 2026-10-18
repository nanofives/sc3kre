#!/usr/bin/env python3
r"""netpack_rules.py - structured edits to Apps\Res\TilingRules\*.txt for netpack packages (2026-10-13).

The format was agreed with the sibling `netrules` (tiler simulator + rule editor), which owns its semantics; this
module is the one implementation, used by netpack install/validate and offered to `netrules apply-edits`. A package
never edits a rule file by byte offset: it names a rule by its index in the STOCK file plus the content it expects.

Manifest key "rule_edits": a list, applied in order to a copy of each named file. File names are case-insensitive.
Rule record = [dir, id, state]: dir 0..23 (5x5 neighbourhood table, SIMNTWRK 0x10032134) or 255 (the tile itself),
id = piece id, state 0..3; id 0 with state 5 / 1 / 0 = empty / pending / foreign (the sentinels). Raw file values
(id*256+state) never appear in a manifest. Rule = {"selector": int, "conds": [rec, ...], "results": [rec, ...]}.

  {"op": "set_results", "file": F, "rule": N, "expect": RULE, "results": [rec, ...]}
  {"op": "insert_rule", "file": F, "at": N | "end", "rule": RULE}
  {"op": "delete_rule", "file": F, "rule": N, "expect": RULE}
  {"op": "list_add" | "list_remove", "file": "<NET>_GRND_Set.txt" | "DIAG_Set.txt" | "<NET>_GRND_Protected.txt", "ids": [...]}
  {"op": "convert_add" | "convert_remove", "file": "<NET>_GRND_Convert.txt" | "<NET>_GRND_Complex_Convert.txt",
   "from": [id, state], "to": [id, state]}

Indexes: N is 0-based in the STOCK file order. That keeps packages composable: netpack applies every installed
package's edits to one file in one pass, and an insert by one package does not shift another's indexes.
set_results / delete_rule are refused when stock rule N was already deleted or its current content differs from
"expect" (so two packages editing one rule fail loudly). insert_rule "at": N goes before stock rule N ("end": after
the last rule); several inserts at one N keep list order. Header counts are recomputed, untouched rules and lines are
re-emitted byte for byte, CRLF kept. list_add skips ids already present; list_remove and convert_remove refuse an
absent item.

What a rule may contain and what can match is NOT decided here: records go through rulecheck.record_problem, and the
merged result is checked by rulecheck (check() below), the same code `netrules lint` runs (re/analysis/TILER_SIM.md
section 11). apply() refuses only what cannot be applied (bad shape, expect mismatch, stock rule gone, index past
the file, a record outside the engine's tables).

Library: apply(file_name, stock_bytes, edits) -> new bytes; check(stock_files, new_files) -> [rulecheck.Finding];
parse_rules, result_ids, family, stage_mode.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from tilingrules import DEAD  # noqa: E402  files the game never reads (formats/TILINGRULES.md)
from netmod import rulecheck as RC  # noqa: E402  the engine-derived checks, shared with netrules lint

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


stage_mode = RC.stage_mode      # the 18 files tiler.Rules.FILES binds (FUN_100175ed), -> 8 / 0x18 / 4 or None


# --------------------------------------------------------------------------- values

def _is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def piece_state(p, where):
    """[id, state] -> raw id*256+state."""
    if not isinstance(p, (list, tuple)) or len(p) != 2 or not all(_is_int(x) for x in p):
        raise RuleEditError("%s: %r is not [id, state]" % (where, p))
    pid, st = p
    prob = RC.record_problem(RC.tiler.SELF, pid, st)
    if prob:
        raise RuleEditError("%s: [%d, %d]: %s" % (where, pid, st, prob))
    return pid * 256 + st


def records(lst, where):
    """[[dir, id, state], ...] -> [(dir, raw value)]."""
    out = []
    for r in lst or []:
        if not isinstance(r, (list, tuple)) or len(r) != 3:
            raise RuleEditError("%s: %r is not [dir, id, state]" % (where, r))
        d = r[0]
        if not _is_int(d):
            raise RuleEditError("%s: dir %r is not an integer" % (where, d))
        prob = RC.record_problem(d, 0, 5)
        if prob:
            raise RuleEditError("%s: %s" % (where, prob))
        out.append((d, piece_state(list(r[1:]), where)))
    return out


def as_records(pairs_):
    """[(dir, raw)] -> [[dir, id, state]] (to print a rule, or to read a file back into manifest form)."""
    return [[d, v >> 8, v & 0xFF] for d, v in pairs_]


# --------------------------------------------------------------------------- RULES files

class Rule:
    __slots__ = ("stock_no", "lines", "sel", "conds", "results")

    def __init__(self, sel, conds, results, stock_no=None, lines=None):
        self.sel, self.conds, self.results = sel, list(conds), list(results)
        self.stock_no, self.lines = stock_no, lines      # stock_no: 0-based index in the stock file, None if new

    def render(self):
        if self.lines is not None:
            return self.lines
        out = [b"1,%d" % self.sel, b"2,%d" % len(self.conds)]
        out += [b"3,%d,%d" % c for c in self.conds]
        out += [b"4,%d" % len(self.results)]
        out += [b"5,%d,%d" % r for r in self.results]
        return out

    def as_dict(self):
        return {"selector": self.sel, "conds": as_records(self.conds), "results": as_records(self.results)}


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
    for no in range(n):
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


def make_rule(r, where):
    if not isinstance(r, dict) or not _is_int(r.get("selector")) or r["selector"] < 0:
        raise RuleEditError("%s: rule needs an integer \"selector\"" % where)
    res = records(r.get("results"), where + " results")
    if not res:
        raise RuleEditError("%s: a rule with no results places nothing" % where)
    return Rule(r["selector"], records(r.get("conds"), where + " conds"), res)


def check(stock_files, new_files):
    """-> the rulecheck findings `new_files` ({TilingRules file name: bytes}, laid over `stock_files`) add to the
    stock directory: exactly what `netrules lint --rules <merged> --base <stock>` prints."""
    return RC.lint_files(stock_files, new_files)


def _where(name, n, e):
    return "%s%s edit %d (%s)" % (e.get("_pack", "") and e["_pack"] + ": ", name, n + 1, e.get("op"))


def _stock_index(rules, e, where):
    """-> current list position of stock rule e["rule"], after checking e["expect"] against its current content."""
    n = e.get("rule")
    if not _is_int(n) or n < 0:
        raise RuleEditError("%s: \"rule\" must be a 0-based index into the stock file" % where)
    if "expect" not in e:
        raise RuleEditError("%s: \"expect\" (the rule's current content) is required" % where)
    pos = [i for i, r in enumerate(rules) if r.stock_no == n]
    if not pos:
        raise RuleEditError("%s: stock rule %d does not exist or was deleted by an earlier edit" % (where, n))
    r = rules[pos[0]]
    want = make_rule(e["expect"], where + " expect")
    if (r.sel, r.conds, r.results) != (want.sel, want.conds, want.results):
        raise RuleEditError("%s: rule %d is %s, expect says %s" % (where, n, r.as_dict(), e["expect"]))
    return pos[0]


def apply_rules_file(name, data, edits):
    rules, trailer = parse_rules(data)
    nstock = len(rules)
    for n, e in enumerate(edits):
        where = _where(name, n, e)
        op = e.get("op")
        if op == "set_results":
            i = _stock_index(rules, e, where)
            r = rules[i]
            res = records(e.get("results"), where + " results")
            if not res:
                raise RuleEditError("%s: empty results" % where)
            rules[i] = Rule(r.sel, r.conds, res, stock_no=r.stock_no)
        elif op == "delete_rule":
            del rules[_stock_index(rules, e, where)]
        elif op == "insert_rule":
            nr = make_rule(e.get("rule"), where)
            at = e.get("at")
            if at == "end":
                rules.append(nr)
            elif _is_int(at) and 0 <= at <= nstock:
                # before the first surviving stock rule with index >= at; earlier inserts at the same index sit
                # right before that rule, so this one lands after them (list order kept)
                nxt = [i for i, r in enumerate(rules) if r.stock_no is not None and r.stock_no >= at]
                rules.insert(nxt[0] if nxt else len(rules), nr)
            else:
                raise RuleEditError("%s: \"at\" must be 0..%d (stock index) or \"end\"" % (where, nstock))
        else:
            raise RuleEditError("%s: op %r does not apply to a RULES file" % (where, op))
    return render_rules(rules, trailer)


# --------------------------------------------------------------------------- list files

def braced_ids(data):
    return [int(x) for x in re.findall(rb"\d+", data)]


def braced_add(data, ids):
    """Add ids before the closing brace, as ", <id>" like the shipped lists."""
    have = set(braced_ids(data))
    k = data.rindex(b"}")
    add = b""
    for i in ids:
        if i not in have:
            add += b", %d" % i
            have.add(i)
    return data[:k] + add + data[k:]


def braced_remove(data, pid, where):
    m = re.search(rb"(?<!\d)%d(?!\d)" % pid, data)
    if not m:
        raise RuleEditError("%s: id %d is not in the list" % (where, pid))
    a, b = m.start(), m.end()
    before = re.search(rb",\s*$", data[:a])
    if before:                                   # ", id" -> ""
        return data[:before.start()] + data[b:]
    after = re.match(rb"\s*,\s*", data[b:])      # first element: "id, " -> ""
    return data[:a] + data[b + (after.end() if after else 0):]


def counted(data):
    lines = data.split(CRLF)
    if lines and lines[-1] == b"":
        lines = lines[:-1]
    n = int(lines[0])
    return lines[1:1 + n], lines[1 + n:]


def counted_render(body, tail):
    return CRLF.join([b"%d" % len(body)] + body + tail) + CRLF


def apply(name, data, edits):
    """Apply `edits` (all for this one file, in order) to `data` (the stock bytes) -> new bytes."""
    fam = family(name)
    if fam is None:
        raise RuleEditError("%s: not an editable TilingRules file (unknown, or DEAD: the game never reads it)" % name)
    if fam == "RULES":
        return apply_rules_file(name, data, edits)
    for n, e in enumerate(edits):
        where = _where(name, n, e)
        op = e.get("op")
        if op in ("list_add", "list_remove") and fam in ("BRACED", "COUNTED_LIST"):
            ids = e.get("ids") or []
            if not ids or any(not _is_int(i) or not 0 < i <= 0xFFFF for i in ids):
                raise RuleEditError("%s: \"ids\" must be piece ids 1..65535" % where)
            if fam == "BRACED":
                if op == "list_add":
                    data = braced_add(data, ids)
                else:
                    for i in ids:
                        data = braced_remove(data, i, where)
            else:
                body, tail = counted(data)
                for i in ids:
                    t = b"%d" % i
                    if op == "list_add":
                        if t not in body:
                            body.append(t)
                    elif t in body:
                        body.remove(t)
                    else:
                        raise RuleEditError("%s: id %d is not in the list" % (where, i))
                data = counted_render(body, tail)
        elif op in ("convert_add", "convert_remove") and fam == "COUNTED_PAIRS":
            line = b"%d,%d" % (piece_state(e.get("from"), where + " from"), piece_state(e.get("to"), where + " to"))
            body, tail = counted(data)
            if op == "convert_add":
                body.append(line)                     # the game scan takes the LAST matching row (netrules)
            elif line in body:
                del body[len(body) - 1 - body[::-1].index(line)]
            else:
                raise RuleEditError("%s: row %s is not in the file" % (where, line.decode()))
            data = counted_render(body, tail)
        else:
            raise RuleEditError("%s: op %r does not apply to a %s file" % (where, op, fam))
    return data


def result_ids(data):
    """-> set of piece ids a RULES file can place (every RESULT value >= 256)."""
    rules, _ = parse_rules(data)
    return {v >> 8 for r in rules for _, v in r.results if v >= 256}
