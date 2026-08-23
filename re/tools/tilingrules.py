#!/usr/bin/env python3
"""tilingrules.py - parser / writer / validator for Apps\\Res\\TilingRules\\*.txt

The network auto-tiling ruleset of SimCity 3000: 68 loose plain-text files that say, per network,
which tile pieces exist and how they connect. Read from disk at startup and parsed into engine
records - both facts game-verified, see verify/tilingrules_read_test/RESULTS.md:

  * T0  - all 48 referenced files are opened from Apps\\Res\\TilingRules\\, every one ok.
  * T1b - contents are CONSUMED: cutting ROAD_GRND_Set.txt from 109 ids to 1 moved the per-id
          append count (SIMNTWRK 0x1001b456) from 448 to 340, exactly the -108 predicted, with the
          per-file control (0x1001746e) unmoved at 7.

Byte-exactness strategy
-----------------------
Every file is CRLF + pure ASCII + no tabs (all 68, measured). Rather than re-emit from a
pretty-printer and hope, this splits the raw text into an alternating (separator, numeric token)
layout. Separators are kept verbatim, and an UNEDITED token is re-emitted as its original bytes -
only tokens actually assigned are re-rendered from the int. So round-trip is byte-exact by
construction, and an edit preserves the surrounding wrapping and indentation for free.

Re-emitting untouched tokens verbatim rather than via str(int(v)) is not defensive padding: it is
required. networkIntesection.txt stores zero-padded quoted numbers ({{"0", "00004500", ...}}), and
str(int("00004500")) is "4500", so a naive rebuild silently rewrites that file. `--selftest`
reports which files contain such tokens.

Grammar, established from the decompilation and validated against every file
--------------------------------------------------------------------------
BRACED         `{a, b, c, ...}` - a bare id list, braces/commas/newlines are noise.
               Parser witness: SIMNTWRK FUN_1001746e - strtok, skip to the first digit, atoi,
               then append a 12-byte record {0xE223741F, 0xA317745F, value} via FUN_1001b456.
               So *any* integer token counts and punctuation is irrelevant to the game.
COUNTED_LIST   line 1 = N, then N lines of one int.
COUNTED_PAIRS  line 1 = N, then N lines of `from,to`.
RULES          line 1 = `0,N`, then N rules, each:
                   1,selector        bitmask of which dirs hold a same-network neighbour;
                                     0x100 = wildcard (FUN_100222f9 / FUN_10022092)
                   2,C2              length prefix: exactly C2 following `3` lines
                   3,dir,val   x C2  match / neighbour conditions
                   4,C4              length prefix: exactly C4 following `5` lines
                   5,dir,val   x C4  results
               opcode arity is fixed (1->2, 2->2, 3->3, 4->2, 5->3) and opcode 2 == len(3),
               opcode 4 == len(5) hold for 100% of the 4,219 shipped rules.
               Parser witness: FUN_10022676 (9-state). It builds 6-byte records
               {u32 id; u8 dir; u8 state} via FUN_100229e8 with 0xff -> 0x1f, grouped into
               0x18-byte {conds, results} groups, held by 0x10-byte rule entries
               {u32 selector; vector<group>} appended by FUN_10022a7e.

Field encodings - all DECODED, see re/analysis/NETWORK_RULE_ENGINE.md section 4
------------------------------------------------------------------------------
dir    an index into the 24-entry 5x5-neighbourhood offset table at SIMNTWRK 0x10032134
       (FUN_1002205c): 0-3 orthogonal, 4-7 diagonal, 8-23 the distance-2 ring. 255 -> 0x1f ->
       (0,0), i.e. the tile itself. Cross-checked against the inverse table at 0x10032118,
       which inverts it 25/25. Mirrored here as DIR_TABLE.
val    val >> 8 is a piece id (100% accounted for by --crosscheck); val < 256 is a sentinel and
       only {0, 1, 5} ever occur.
state  val & 0xff. Two disjoint roles. With id == 0 it is an occupancy sentinel (5 empty,
       1 pending, 0 present-but-filtered). With id != 0 it is a 2-bit piece orientation and is
       only ever {0,1,2,3} across every shipped value. Passed verbatim as the 4th argument to
       the 0xc14f8955 piece factory (FUN_100165d8).

Still open: which predicate sets each selector bit beyond the city-edge contributor, and the
geometric facing convention for state 0/1/2/3. Not guessed here.

--lint enforces the stage invariants (a rule that parses but can never match): a file's dir
values and selector bits must fit the stage it is loaded into (final=4, Simple=8, Complex=0x18).
Zero findings across all 18 stage-bound shipped files.

Usage
-----
  python tilingrules.py --selftest [DIR]
  python tilingrules.py --show FILE
  python tilingrules.py --dump FILE [--json]
  python tilingrules.py --crosscheck [DIR]        # rule-value accounting
  python tilingrules.py --set-value FILE INDEX NEW   # edit one numeric token, in place
  python tilingrules.py --replace-id FILE OLD NEW    # swap every occurrence of an id value
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

# Files never opened by any module at startup, measured 2026-08-21/23. 13 dead, 7 lazy.
# Editing a DEAD file produces no effect and looks like a failed experiment - hence this list.
DEAD = {
    "ROAD_GRND_SlopeRULES.txt", "RAIL_GRND_SlopeRULES.txt", "HWAY_GRND_SlopeRULES.txt",
    "SUBW_GRND_SlopeRULES.txt", "POWR_GRND_SlopeRULES.txt", "PIPE_GRND_SlopeRULES.txt",
    "ROAD_Exits.txt", "RAIL_Exits.txt", "SUBW_Exits.txt",
    "networkIntesection.txt",          # shipped typo, referenced by nothing
    "ROAD_GRND_FinalRules.txt",        # distinct from ROAD_GRND_final.txt, which IS read
    "PIPE_GRND_Bridges.txt", "SUBW_GRND_Bridges.txt",   # and both declare 0 entries
}
LAZY = {f"LandfillRules{i}.txt" for i in range(1, 7)} | {"LandfillStartRule.txt"}

NETWORKS = ["ROAD", "RAIL", "HWAY", "SUBW", "POWR", "PIPE"]

TOKEN_RE = re.compile(rb"\d+")

# dir -> (dx,dy), the 24-entry 5x5-neighbourhood table at SIMNTWRK 0x10032134, plus 0x1f/255 = self.
# Decoded from FUN_1002205c and cross-checked against the inverse table at 0x10032118 (25/25 cells).
# See re/analysis/NETWORK_RULE_ENGINE.md section 4.1.
DIR_TABLE = {
    0: (-1, 0), 1: (0, -1), 2: (1, 0), 3: (0, 1),
    4: (-1, -1), 5: (1, -1), 6: (1, 1), 7: (-1, 1),
    8: (-2, 0), 9: (-2, -1), 10: (-2, -2), 11: (-1, -2),
    12: (0, -2), 13: (1, -2), 14: (2, -2), 15: (2, -1),
    16: (2, 0), 17: (2, 1), 18: (2, 2), 19: (1, 2),
    20: (0, 2), 21: (-1, 2), 22: (-2, 2), 23: (-2, 1),
    255: (0, 0),            # 0xff -> 0x1f -> (0,0): the tile itself
}
DIR_SELF = 255
WILDCARD_SELECTOR = 0x100   # FUN_100222f9: matches any neighbourhood; unreachable as a real mask

# Which rule stage a file is loaded into, and therefore the exclusive upper bound on `dir`.
# FUN_1001547b runs Simple(mode 8) -> Complex(mode 0x18) -> final(mode 4).
STAGE_MODE = {"simplerules": 8, "complexrules": 0x18, "_final": 4}


def stage_mode(name: str):
    """Return the dir bound for a RULES file, or None if the file is not stage-bound."""
    n = name.lower()
    if n.endswith("_final.txt"):
        return 4
    if "complexrules" in n:
        return 0x18
    if "simplerules" in n:
        return 8
    return None            # SlopeRULES (dead) and Landfill* (loaded by SIMRCI, not SIMNTWRK)


def decode(dir_: int, val: int):
    """(dx, dy, piece_id, state) for a rule record. piece_id is None for a sentinel val<256."""
    dxdy = DIR_TABLE.get(dir_)
    return (dxdy, None if val < 256 else val >> 8, val & 0xff)


class Layout:
    """Alternating separators and numeric tokens. Byte-exact rebuild, unconditionally.

    An untouched token is re-emitted as its ORIGINAL bytes, not as str(int(value)). That
    distinction is load-bearing: networkIntesection.txt stores zero-padded quoted numbers
    ({{"0", "00004500", ...}}), so str(int("00004500")) == "4500" would silently rewrite it.
    Only tokens actually assigned through set_value()/replace_id() are re-rendered.
    """

    __slots__ = ("seps", "values", "raw_tokens", "dirty")

    def __init__(self, data: bytes):
        self.seps: list[bytes] = []
        self.values: list[int] = []
        self.raw_tokens: list[bytes] = []
        pos = 0
        for m in TOKEN_RE.finditer(data):
            self.seps.append(data[pos:m.start()])
            tok = m.group(0)
            self.raw_tokens.append(tok)
            self.values.append(int(tok))
            pos = m.end()
        self.seps.append(data[pos:])          # trailing separator, always present
        self.dirty: list[bool] = [False] * len(self.values)

    def set(self, index: int, value: int) -> None:
        self.values[index] = value
        self.dirty[index] = True

    def build(self) -> bytes:
        out = bytearray()
        for i, v in enumerate(self.values):
            out += self.seps[i]
            out += (str(v).encode("ascii") if self.dirty[i] else self.raw_tokens[i])
        out += self.seps[-1]
        return bytes(out)

    def zero_padded(self) -> bool:
        """True if any token is not str(int)-stable, i.e. zero-padded or signed."""
        return any(str(int(t)) != t.decode("ascii") for t in self.raw_tokens)


class TilingFile:
    def __init__(self, path: str):
        self.path = path
        self.name = os.path.basename(path)
        with open(path, "rb") as fh:
            self.raw = fh.read()
        self.layout = Layout(self.raw)
        self.family = self._classify()
        self.model = self._parse()

    # ---------------------------------------------------------------- structure

    def _body_lines(self) -> list[str]:
        text = self.raw.decode("ascii")
        return [l.strip() for l in text.splitlines() if l.strip()]

    def _classify(self) -> str:
        text = self.raw.decode("ascii").lstrip()
        if text.startswith("{"):
            return "BRACED"
        lines = self._body_lines()
        if not lines:
            return "EMPTY"
        if lines[0].startswith("0,"):
            return "RULES"
        if "," not in lines[0]:
            return "COUNTED_PAIRS" if (len(lines) > 1 and "," in lines[1]) else "COUNTED_LIST"
        return "UNKNOWN"

    def _parse(self):
        fam = self.family
        if fam == "BRACED":
            return {"ids": list(self.layout.values)}
        lines = self._body_lines()
        if fam == "COUNTED_LIST":
            return {"declared": int(lines[0]), "items": [int(l) for l in lines[1:]]}
        if fam == "COUNTED_PAIRS":
            pairs = []
            for l in lines[1:]:
                a, b = l.split(",")
                pairs.append((int(a), int(b)))
            return {"declared": int(lines[0]), "pairs": pairs}
        if fam == "RULES":
            declared = int(lines[0].split(",")[1])
            rules, cur = [], None
            for l in lines[1:]:
                p = [int(x) for x in l.split(",")]
                op = p[0]
                if op == 1:
                    if cur is not None:
                        rules.append(cur)
                    cur = {"selector": p[1], "conds": [], "results": [],
                           "n_conds": None, "n_results": None}
                elif op == 2:
                    cur["n_conds"] = p[1]
                elif op == 3:
                    cur["conds"].append((p[1], p[2]))
                elif op == 4:
                    cur["n_results"] = p[1]
                elif op == 5:
                    cur["results"].append((p[1], p[2]))
                else:
                    raise ValueError(f"{self.name}: unknown opcode {op} in {l!r}")
            if cur is not None:
                rules.append(cur)
            return {"declared": declared, "rules": rules}
        return {}

    # --------------------------------------------------------------- validation

    def validate(self) -> list[str]:
        """Structural problems, as a list of strings. Empty list means clean."""
        errs: list[str] = []
        m, fam = self.model, self.family

        if self.layout.build() != self.raw:
            errs.append("round-trip mismatch")

        if fam == "COUNTED_LIST":
            if m["declared"] != len(m["items"]):
                errs.append(f"header says {m['declared']}, found {len(m['items'])} items")
        elif fam == "COUNTED_PAIRS":
            if m["declared"] != len(m["pairs"]):
                errs.append(f"header says {m['declared']}, found {len(m['pairs'])} pairs")
        elif fam == "RULES":
            if m["declared"] != len(m["rules"]):
                errs.append(f"header says {m['declared']} rules, found {len(m['rules'])}")
            for i, r in enumerate(m["rules"]):
                if r["n_conds"] != len(r["conds"]):
                    errs.append(f"rule {i}: opcode2={r['n_conds']} but {len(r['conds'])} cond(s)")
                if r["n_results"] != len(r["results"]):
                    errs.append(f"rule {i}: opcode4={r['n_results']} but "
                                f"{len(r['results'])} result(s)")
        return errs

    def lint(self) -> list[str]:
        """Semantic problems: rules that parse fine but can never match.

        Distinct from validate(), which is structural. These invariants come from the decoded
        engine (NETWORK_RULE_ENGINE.md section 4.4) and hold with zero exceptions across all
        4,219 shipped rules, so a violation means an authoring mistake.
        """
        if self.family != "RULES":
            return []
        mode = stage_mode(self.name)
        if mode is None:
            return []                       # not stage-bound; nothing to enforce
        out: list[str] = []
        for i, r in enumerate(self.model["rules"]):
            sel = r["selector"]
            if sel != WILDCARD_SELECTOR and sel >> mode:
                out.append(f"rule {i}: selector 0x{sel:x} sets bits >= mode {mode}; "
                           f"the engine can never build that mask")
            for kind in ("conds", "results"):
                for d, v in r[kind]:
                    if d == DIR_SELF:
                        continue
                    if d not in DIR_TABLE:
                        out.append(f"rule {i}: {kind} dir {d} is not a valid direction")
                    elif d >= mode:
                        out.append(f"rule {i}: {kind} dir {d} >= mode {mode}; "
                                   f"unreachable in this stage")
                    if v >= 256 and (v & 0xff) > 3:
                        out.append(f"rule {i}: {kind} state {v & 0xff} > 3 with a non-zero id "
                                   f"(orientation is 2-bit)")
        return out

    # -------------------------------------------------------------------- edits

    def set_value(self, index: int, new: int) -> None:
        self.layout.set(index, new)

    def replace_id(self, old: int, new: int) -> int:
        n = 0
        for i, v in enumerate(self.layout.values):
            if v == old:
                self.layout.set(i, new)
                n += 1
        return n

    def save(self, path: str | None = None) -> None:
        with open(path or self.path, "wb") as fh:
            fh.write(self.layout.build())

    # ------------------------------------------------------------------ display

    def summary(self) -> str:
        status = "DEAD" if self.name in DEAD else "lazy" if self.name in LAZY else "live"
        m = self.model
        if self.family == "BRACED":
            detail = f"{len(m['ids'])} ids"
        elif self.family == "COUNTED_LIST":
            detail = f"{m['declared']} items"
        elif self.family == "COUNTED_PAIRS":
            detail = f"{m['declared']} pairs"
        elif self.family == "RULES":
            nc = sum(len(r["conds"]) for r in m["rules"])
            nr = sum(len(r["results"]) for r in m["rules"])
            detail = f"{m['declared']} rules, {nc} conds, {nr} results"
        else:
            detail = "-"
        return (f"{self.name:34s} {self.family:14s} {status:4s} "
                f"{len(self.raw):7d} B  {detail}")


# ------------------------------------------------------------------------ driver

def load_dir(d: str) -> list[TilingFile]:
    files = sorted(f for f in os.listdir(d) if f.lower().endswith(".txt"))
    return [TilingFile(os.path.join(d, f)) for f in files]


def cmd_selftest(d: str) -> int:
    files = load_dir(d)
    rt_ok = struct_ok = 0
    failures: list[str] = []
    lints: list[str] = []

    for tf in files:
        if tf.layout.build() == tf.raw:
            rt_ok += 1
        else:
            failures.append(f"{tf.name}: ROUND-TRIP MISMATCH")
        errs = tf.validate()
        if errs:
            failures.extend(f"{tf.name}: {e}" for e in errs)
        else:
            struct_ok += 1
        lints.extend(f"{tf.name}: {e}" for e in tf.lint())

    n = len(files)
    print(f"round-trip byte-identical : {rt_ok}/{n}")
    print(f"structurally valid        : {struct_ok}/{n}")
    fam: dict[str, int] = {}
    for tf in files:
        fam[tf.family] = fam.get(tf.family, 0) + 1
    print(f"families                  : {fam}")
    odd = [t.name for t in files if t.layout.zero_padded()]
    if odd:
        print(f"zero-padded tokens        : {odd} (rebuilt from original bytes, not reformatted)")
    live = [t for t in files if t.name not in DEAD and t.name not in LAZY]
    print(f"live / lazy / dead        : {len(live)} / {len(LAZY & {t.name for t in files})}"
          f" / {len(DEAD & {t.name for t in files})}")
    tot_rules = sum(t.model.get("declared", 0) for t in files if t.family == "RULES")
    print(f"total rules across RULES   : {tot_rules}")
    staged = [t for t in files if t.family == "RULES" and stage_mode(t.name) is not None]
    print(f"stage-bound rule files     : {len(staged)} "
          f"(lint findings: {len(lints)})")
    if lints:
        print("\nLINT (parses, but can never match):")
        for l in lints[:20]:
            print("  " + l)
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print("  " + f)
        return 1
    print("\nOK - every file parses, validates, and rebuilds byte-identically.")
    return 0


SENTINELS = {0, 1, 5}       # every rule value < 256 seen across all 68 files is one of these


def cmd_crosscheck(d: str) -> int:
    """Account for every rule value under the {id>>8, dir, state} record layout.

    Three buckets, and the point is that they sum to 100%: a sentinel (val < 256), a piece in the
    network's OWN Set list, or a piece in a CROSSED network's Set list (power lines over road /
    rail / highway). Anything left over is unexplained and printed loudly.
    """
    files = {t.name: t for t in load_dir(d)}
    sets = {n: set(files[f"{n}_GRND_Set.txt"].model["ids"])
            for n in NETWORKS if f"{n}_GRND_Set.txt" in files}
    if "DIAG_Set.txt" in files:
        sets["DIAG"] = set(files["DIAG_Set.txt"].model["ids"])

    print("Rule-value accounting under FUN_10022676's 6-byte {id>>8, dir, state} record layout.")
    print("val>>8 is read as a piece id; val<256 is treated as a sentinel.\n")
    print(f"  {'net':5s} {'total':>7s} {'sentinel':>9s} {'own Set':>9s} {'crossed':>8s} "
          f"{'UNEXPLAINED':>12s}")

    g = [0, 0, 0, 0]
    unexplained: dict[int, int] = {}
    for net in NETWORKS:
        own = sets.get(net, set())
        tot = sent = hit = cross = 0
        for name, tf in files.items():
            if not name.startswith(net) or tf.family != "RULES":
                continue
            for r in tf.model["rules"]:
                for _dir, val in r["conds"] + r["results"]:
                    tot += 1
                    if val < 256:
                        sent += 1
                    elif (val >> 8) in own:
                        hit += 1
                    elif any((val >> 8) in s for n, s in sets.items() if n != net):
                        cross += 1
                    else:
                        unexplained[val >> 8] = unexplained.get(val >> 8, 0) + 1
        left = tot - sent - hit - cross
        g[0] += tot; g[1] += sent; g[2] += hit; g[3] += cross
        print(f"  {net:5s} {tot:7d} {sent:9d} {hit:9d} {cross:8d} {left:12d}")

    left = g[0] - g[1] - g[2] - g[3]
    print(f"  {'TOTAL':5s} {g[0]:7d} {g[1]:9d} {g[2]:9d} {g[3]:8d} {left:12d}")
    print(f"\n  accounted for: {100.0 * (g[0] - left) / g[0]:.2f}%")
    seen_sent = sorted({v for t in files.values() if t.family == "RULES"
                        for r in t.model["rules"] for _d, v in r["conds"] + r["results"]
                        if v < 256})
    print(f"  sentinel values actually present: {seen_sent}"
          f"{'  (== the expected set)' if set(seen_sent) <= SENTINELS else '  <-- NEW SENTINEL'}")
    if unexplained:
        print(f"  UNEXPLAINED piece ids: {dict(sorted(unexplained.items()))}")

    print("\nCAVEAT: 100% accounting is strong support, not a decode. It shows val>>8 behaves like")
    print("a piece id everywhere. The low byte (val & 0xff) and the `dir` encoding, including its")
    print("special value 255, remain UNDECODED - see re/analysis/formats/TILINGRULES.md.")
    return 0


def main(argv: list[str] | None = None) -> int:
    default_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "Apps", "Res", "TilingRules")
    default_dir = os.path.normpath(default_dir)

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", nargs="?", const=default_dir, metavar="DIR")
    ap.add_argument("--crosscheck", nargs="?", const=default_dir, metavar="DIR")
    ap.add_argument("--show", metavar="FILE")
    ap.add_argument("--dump", metavar="FILE")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--set-value", nargs=3, metavar=("FILE", "INDEX", "NEW"))
    ap.add_argument("--replace-id", nargs=3, metavar=("FILE", "OLD", "NEW"))
    args = ap.parse_args(argv)

    if args.selftest:
        return cmd_selftest(args.selftest)
    if args.crosscheck:
        return cmd_crosscheck(args.crosscheck)

    if args.show:
        tf = TilingFile(args.show)
        print(tf.summary())
        errs = tf.validate()
        print("  validation: " + ("clean" if not errs else "; ".join(errs)))
        lints = tf.lint()
        print(f"  lint      : {'clean' if not lints else str(len(lints)) + ' finding(s)'}")
        for l in lints[:5]:
            print("    " + l)
        if tf.family == "RULES" and tf.model["rules"]:
            mode = stage_mode(tf.name)
            print(f"  stage mode: {mode if mode is not None else 'not stage-bound'}")
            r = tf.model["rules"][0]
            sel = r["selector"]
            tag = "WILDCARD" if sel == WILDCARD_SELECTOR else f"dirs {[b for b in range(8) if sel >> b & 1]}"
            print(f"  first rule: selector={sel} ({tag})")
            for kind in ("conds", "results"):
                for d, v in r[kind]:
                    dxdy, pid, st = decode(d, v)
                    what = f"piece {pid} state {st}" if pid is not None else f"SENTINEL {v}"
                    print(f"    {kind[:4]:4s} dir={d:3d} {str(dxdy):9s} {what}")
        return 0

    if args.dump:
        tf = TilingFile(args.dump)
        if args.json:
            print(json.dumps({"file": tf.name, "family": tf.family, "model": tf.model},
                             indent=2, default=list))
        else:
            print(tf.summary())
            print(tf.model)
        return 0

    if args.set_value:
        path, idx, new = args.set_value
        tf = TilingFile(path)
        old = tf.layout.values[int(idx)]
        tf.set_value(int(idx), int(new))
        tf.save()
        print(f"{tf.name}: token[{idx}] {old} -> {new}")
        return 0

    if args.replace_id:
        path, old, new = args.replace_id
        tf = TilingFile(path)
        n = tf.replace_id(int(old), int(new))
        tf.save()
        print(f"{tf.name}: replaced {n} occurrence(s) of {old} with {new}")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
