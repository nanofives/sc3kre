#!/usr/bin/env python3
"""overlay_base.py - the stock fingerprints sc3netmod needs to merge other mods' edits into the overlay (task
overlaymerge, 2026-11-21, verify/overlaymerge/RESULTS.md).

WHY. With sc3netmod the game reads mods\\netmod\\overlay\\<path> instead of <path> for every file the overlay holds
(sc3netmod.c, OVERLAY block). A mod that edits the stock Apps\\ copy of such a file (a farm mod changing
Apps\\Res\\BUILDFAM.IXF, a tuning mod changing Apps\\Sys\\SYS.PAK) installs fine and is never seen. sc3netmod's OVMERGE
block (sc3netmod_ovmerge.c) notices that the Apps copy is no longer stock and merges the change into the copy it
serves. A three-way merge needs the stock version as its base. The stock files are EA's, so the base ships as hashes
only: this file.

  mods\\netmod\\overlay_base.txt   (beside overlay\\, never inside it: the overlay serves every file it holds)

FORMAT (text, one record per line, written by this tool, read by sc3netmod_ovmerge.c):

  sc3netmod overlay base 1
  F <sha256 of the stock file, upper hex> <kind ixf|pak|file> <path relative to the game root, backslashes>
  R <group> <instance> <type> <fnv>     IXF record of the file above (hex u32 x3, payload FNV-1a 64)
  M <fnv> <member name>                 SYS.PAK member of the file above (member lines joined with LF)
  L <skey> <value> <whole>              one keyed text line of the record / member above (FNV-1a 64 each)
  C <n>                                 the record's "BuildingCount: n" (merged as a count, not as a line)

Keyed text lines (identical rules in sc3netmod_ovmerge.c, keep them in step):
  - a record is text when it is a SYS.PAK member, or an IXF payload that starts with "TXT!"
  - lines split on LF, one trailing CR dropped; a line is trimmed of spaces and tabs
  - "[x]" sets the section to lower(trim(x)); comment lines (";", "#", "//") and lines without '=' or ':' (or with it
    first) are structural: they are never merged, the overlay copy keeps its own
  - else the FIRST of '=' / ':' splits it: k = lower(trim(left)), v = trim(right)
  - a BUILDFAM line "Key: g,t,id,weight  name" (three digit-only fields before the 3rd comma) is keyed by its id:
    k = "key:g,t,id", v = trim(weight  name), so a weight changed on both sides is a conflict, not two lines
    skey = section + 0x1F + k, whole = skey + "=" + v (bytes, latin-1)

Usage:
  py -3.12 overlay_base.py --tree <game root> [--stock <root holding the stock Apps>] [--manifest <gog_manifest.csv>]
  py -3.12 overlay_base.py --tree <game root> --check      # list the shadowed files and whether Apps is stock

--stock defaults to --tree. Every stock file must match the GOG 2.0.949 manifest when one is given (default:
<repo>\\original\\gog_2.0.949\\gog_manifest.csv when present), so a base is never built from a modded install.
"""
import argparse
import csv
import hashlib
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..")))
import syspak_parse                                    # noqa: E402

IXF_MAGIC = 0x80C381D7
OVERLAY = os.path.join("mods", "netmod", "overlay")
BASE_REL = os.path.join("mods", "netmod", "overlay_base.txt")
HEADER = "sc3netmod overlay base 1"


def _find_manifest():
    """original/gog_2.0.949/gog_manifest.csv in the repo root or above it (a worktree under dev/<name>/wt has none)."""
    d = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
    for _ in range(5):
        p = os.path.join(d, "original", "gog_2.0.949", "gog_manifest.csv")
        if os.path.isfile(p):
            return p
        d = os.path.dirname(d)
    return None


DEFAULT_MANIFEST = _find_manifest()


def fnv(b):
    h = 0xCBF29CE484222325
    for c in b:
        h ^= c
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def split_lines(payload):
    """IXF text payload -> lines (LF split, one trailing CR dropped, a final empty piece dropped)."""
    parts = payload.split(b"\n")
    if parts and parts[-1] == b"":
        parts.pop()
    return [p[:-1] if p.endswith(b"\r") else p for p in parts]


def keyed(lines):
    """-> [(skey, value, whole)] for the keyed lines, in order (rules in the module doc)."""
    out, section = [], b""
    for ln in lines:
        s = ln.strip(b" \t")
        if s.startswith(b"[") and s.endswith(b"]") and len(s) >= 2:
            section = s[1:-1].strip(b" \t").lower()
            continue
        if not s or s.startswith(b";") or s.startswith(b"#") or s.startswith(b"//"):
            continue
        ie, ic = s.find(b"="), s.find(b":")
        cand = [i for i in (ie, ic) if i >= 0]
        if not cand:
            continue
        sep = min(cand)
        if sep == 0:
            continue
        k = s[:sep].strip(b" \t").lower()
        v = s[sep + 1:].strip(b" \t")
        if k == b"key":                                # BUILDFAM "Key: group,type,id,weight  name": the id is the key
            f = v.split(b",", 3)
            if len(f) == 4 and all(x.isdigit() for x in f[:3]):
                k = b"key:" + b",".join(f[:3])
                v = f[3].strip(b" \t")
        skey = section + b"\x1f" + k
        out.append((skey, v, skey + b"=" + v))
    return out


def text_lines(kind, lines_out, keyed_lines):
    for skey, v, whole in keyed_lines:
        if skey.endswith(b"\x1fbuildingcount"):
            try:
                lines_out.append("C %d" % int(v.split()[0]))
            except (ValueError, IndexError):
                pass
            continue
        lines_out.append("L %016x %016x %016x" % (fnv(skey), fnv(v), fnv(whole)))


def ixf_records(d):
    """-> [(group, instance, type, payload)] live records in index order."""
    if len(d) < 4 or struct.unpack_from("<I", d, 0)[0] != IXF_MAGIC:
        return None
    out, n = [], 0
    while 4 + (n + 1) * 20 <= len(d):
        g, i, t, off, size = struct.unpack_from("<5I", d, 4 + n * 20)
        n += 1
        if (g, i, t) == (0, 0, 0):
            break
        if off == 0xFFFFFFFF or size == 0xFFFFFFFF or off + size > len(d):
            continue
        out.append((g, i, t, d[off:off + size]))
    return out


def describe(rel, data):
    """Lines of the base file for one stock file."""
    sha = hashlib.sha256(data).hexdigest().upper()
    recs = ixf_records(data)
    if recs is not None:
        out = ["F %s ixf %s" % (sha, rel)]
        for g, i, t, p in recs:
            out.append("R %08x %08x %08x %016x" % (g, i, t, fnv(p)))
            if p.startswith(b"TXT!"):
                text_lines("ixf", out, keyed(split_lines(p)))
        return out
    if os.path.basename(rel).lower() == "sys.pak":
        names, _offs, _toc, recs = syspak_parse.parse(data)
        out = ["F %s pak %s" % (sha, rel)]
        for nm, r in zip(names, recs):
            lines = [ln.encode("latin1") for ln in r["lines"]]
            out.append("M %016x %s" % (fnv(b"\n".join(lines)), nm))
            text_lines("pak", out, keyed(lines))
        return out
    return ["F %s file %s" % (sha, rel)]


def shadowed(tree):
    """Overlay files (root-relative, backslashes) -> list, sorted."""
    base = os.path.join(tree, OVERLAY)
    out = []
    for r, _ds, fs in os.walk(base):
        for f in fs:
            out.append(os.path.relpath(os.path.join(r, f), base).replace("/", "\\"))
    return sorted(out, key=str.lower)


def load_manifest(path):
    if not path or not os.path.isfile(path):
        return None
    with open(path, newline="", encoding="utf-8") as fh:
        return {row["path"].replace("/", "\\").lower(): row["sha256"].upper() for row in csv.DictReader(fh)}


def build(tree, stock=None, manifest=DEFAULT_MANIFEST, allow_nonstock=False):
    """-> (text, report rows). Covers every overlay file that has a stock counterpart under `stock`."""
    stock = stock or tree
    man = load_manifest(manifest)
    out, rows = [HEADER], []
    for rel in shadowed(tree):
        src = os.path.join(stock, rel)
        if not os.path.isfile(src):
            continue                                   # new file: shadows nothing
        with open(src, "rb") as fh:
            data = fh.read()
        sha = hashlib.sha256(data).hexdigest().upper()
        want = man.get(rel.lower()) if man is not None else None
        if man is not None and want != sha and not allow_nonstock:
            raise SystemExit("overlay_base: %s is not the GOG 2.0.949 stock file (sha256 %s, manifest %s). Build the "
                             "base from a stock install (--stock)." % (src, sha[:16], (want or "absent")[:16]))
        d = describe(rel, data)
        out += d
        rows.append((rel, d[0].split()[2], len(d) - 1, want == sha if man is not None else None))
    return "\r\n".join(out) + "\r\n", rows


def write(tree, stock=None, manifest=DEFAULT_MANIFEST, allow_nonstock=False):
    text, rows = build(tree, stock, manifest, allow_nonstock)
    dst = os.path.join(tree, BASE_REL)
    old = open(dst, "rb").read() if os.path.isfile(dst) else None
    if old != text.encode("latin1"):
        if os.path.lexists(dst):
            os.remove(dst)                             # never write through a hard link into another tree
        with open(dst, "wb") as fh:
            fh.write(text.encode("latin1"))
    return dst, rows


def write_auto(tree):
    """For netpack install: the tree's own Apps when it is stock, else the GOG reference copy beside the manifest
    (<repo>/original/gog_2.0.949, whose Apps is the untouched install). -> message line, never raises."""
    try:
        dst, rows = write(tree)
        return "overlay_base: %d shadowed file(s) -> %s" % (len(rows), dst)
    except SystemExit as e:
        ref = os.path.dirname(DEFAULT_MANIFEST) if DEFAULT_MANIFEST else None
        if ref and os.path.isdir(os.path.join(ref, "Apps")):
            try:
                dst, rows = write(tree, stock=ref)
                return "overlay_base: the tree's Apps is not stock, base built from %s: %d file(s) -> %s" % (ref, len(rows), dst)
            except SystemExit as e2:
                return "overlay_base: NOT written (%s)" % e2
        return "overlay_base: NOT written (%s)" % e


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tree", required=True)
    ap.add_argument("--stock")
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--allow-nonstock", action="store_true")
    ap.add_argument("--check", action="store_true", help="list shadowed files and whether the tree's Apps copy is stock")
    a = ap.parse_args(argv)
    if a.check:
        man = load_manifest(a.manifest)
        for rel in shadowed(a.tree):
            p = os.path.join(a.tree, rel)
            if not os.path.isfile(p):
                continue
            sha = hashlib.sha256(open(p, "rb").read()).hexdigest().upper()
            print("%-8s %s" % ("stock" if man and man.get(rel.lower()) == sha else "CHANGED" if man else "?", rel))
        return 0
    dst, rows = write(a.tree, a.stock, a.manifest, a.allow_nonstock)
    for rel, kind, n, ok in rows:
        print("  %-5s %5d lines  %s%s" % (kind, n, rel, "" if ok in (True, None) else "  (NOT stock, --allow-nonstock)"))
    print("%d shadowed file(s) -> %s" % (len(rows), dst))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
