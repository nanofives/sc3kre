#!/usr/bin/env python3
"""merge_worker_module.py - land a delegated worker's module analysis on disk.

Workers are read-only, so they return their deliverable as inline markdown. This script:
  1. pulls the fenced markdown block out of the worker's raw output,
  2. writes it to re/analysis/<MODULE>.md,
  3. extracts the `rva,subsystem,confidence,new_name,evidence` classification rows and
     reports them for merging into functions.csv.

The orchestrator remains the SINGLE WRITER of functions.csv -- this script only *reports*
the rows unless --merge is passed.

Usage:
  py -3.12 re/scripts/merge_worker_module.py <worker_output.txt> <MODULE> [--merge]
"""
import csv
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSVP = os.path.join(ROOT, "functions.csv")
ORDER = {"C0": 0, "C1": 1, "C2": 2, "C3": 3, "C4": 4}


def extract_markdown(raw):
    """The deliverable is inside a ```markdown fence.

    CAREFUL: the deliverable itself CONTAINS fenced code blocks, so a non-greedy
    ```markdown\\n(.*?)``` match stops at the first INNER fence and silently truncates
    (this produced a 688-byte SIMNTWRK.md out of a 19.7 KB response). Match to the LAST
    closing fence instead.
    """
    m = re.search(r"```markdown[ \t]*\r?\n", raw)
    if m:
        start = m.end()
        end = raw.rfind("\n```")
        if end > start:
            return raw[start:end]
        return raw[start:]
    # No explicit markdown fence: strip the delegate banner and take the body from the first
    # markdown heading onward. Accept h1-h3 -- workers legitimately start at "## 1. Promoted
    # rows" with no h1, and requiring "^# " silently rejected a perfectly good 11 KB report.
    h = re.search(r"^#{1,3}\s+\S", raw, re.M)
    if h:
        return raw[h.start():]
    return None


# The delegation helper appends a footer naming the raw-output file under the caller's
# %TEMP%, i.e. an absolute path containing the local Windows USERNAME. This repo is public
# (github.com/nanofives/sc3kre), and 17 already-committed analysis docs carried that line
# before it was noticed on 2026-08-16. Strip it here so it can never land again.
FOOTER = re.compile(r"(?m)^\(raw JSON: .*\)\r?\n?")


def scrub(md):
    md = FOOTER.sub("", md)
    leaks = re.findall(r"[A-Za-z]:\\Users\\[^\s`)\"']+", md)
    if leaks:
        print("  ! refusing to write: %d absolute user path(s) remain, e.g. %s"
              % (len(leaks), leaks[0]))
        return None
    return md


def extract_rows(md, module):
    """Pull rva,subsystem,confidence,new_name,evidence rows out of the markdown."""
    rows = []
    for line in md.splitlines():
        s = line.strip()
        if not s.lower().lstrip("|").strip().startswith("0x"):
            continue
        # Rows arrive either as bare CSV or as a markdown table row. Normalise both.
        if s.startswith("|"):
            parts = [c.strip().strip("`") for c in s.strip("|").split("|")]
        else:
            try:
                parts = next(csv.reader([s]))
            except Exception:
                continue
        if len(parts) < 4:
            continue
        rva = parts[0].strip().lower()
        if not re.fullmatch(r"0x[0-9a-f]{8}", rva):
            continue
        conf = parts[2].strip().upper()
        if conf not in ORDER:
            continue
        if conf in ("C3", "C4"):
            # Workers were told not to claim C3+; they cannot run anything or get a
            # second witness. Cap it and say so rather than silently trusting it.
            print("  ! %s claimed %s -- capping to C2 (worker cannot verify)" % (rva, conf))
            conf = "C2"
        rows.append({"rva": rva, "subsystem": parts[1].strip(), "confidence": conf,
                     "new_name": parts[3].strip(),
                     "evidence": parts[4].strip() if len(parts) > 4 else ""})
    return rows


def module_paths(module):
    """-> (functions.csv module value, export functions dir).

    SC3U is the odd one out: it is the EXE, its functions.csv value is "SC3U.exe" (not
    "SC3U.DLL") and its export dir is plain `ghidra_export` with no module suffix. Getting
    this wrong makes every lookup miss, which then looks like 'these are all new rows'.
    """
    stem = module.lower()
    if stem == "sc3u":
        return "SC3U.exe", os.path.join(ROOT, "re", "ghidra_export", "functions")
    modname = module if stem.endswith(".dll") else module + ".DLL"
    return modname, os.path.join(ROOT, "re", "ghidra_export_%s" % stem, "functions")


def merge(rows, module):
    modname, export = module_paths(module)
    meta = {}
    if os.path.isdir(export):
        for fn in os.listdir(export):
            m = re.match(r"([0-9a-f]{8})_(.+)\.c$", fn)
            if m:
                meta["0x" + m.group(1)] = (m.group(2), fn)

    with open(CSVP, newline="", encoding="utf-8") as fh:
        all_rows = list(csv.DictReader(fh))
    fields = list(all_rows[0].keys())
    idx = {(r["module"].lower(), r["rva"].lower()): r for r in all_rows}

    up = add = skip = 0
    for r in rows:
        key = (modname.lower(), r["rva"])
        if key in idx:
            tgt = idx[key]
            if ORDER.get(r["confidence"], 0) < ORDER.get(tgt["confidence"], 0):
                print("  keeping higher existing %s for %s" % (tgt["confidence"], r["rva"]))
            else:
                tgt["confidence"] = r["confidence"]
            tgt["subsystem"], tgt["new_name"], tgt["notes"] = \
                r["subsystem"], r["new_name"], r["evidence"]
            up += 1
        else:
            if r["rva"] not in meta:
                print("  !! %s has no export file -- SKIPPED (cannot invent a name/size)" % r["rva"])
                skip += 1
                continue
            g, fn = meta[r["rva"]]
            size = ""
            with open(os.path.join(export, fn), encoding="utf-8", errors="replace") as fh:
                m = re.search(r"\((\d+) bytes\)", fh.readline())
                if m:
                    size = m.group(1)
            all_rows.append({"module": modname, "rva": r["rva"], "ghidra_name": g,
                             "size": size, "kind": "fun", "confidence": r["confidence"],
                             "subsystem": r["subsystem"], "new_name": r["new_name"],
                             "notes": r["evidence"]})
            add += 1

    with open(CSVP, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(all_rows)
    print("  merged: %d updated, %d added, %d skipped -> %d rows" % (up, add, skip, len(all_rows)))


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    path, module = argv[1], argv[2].upper().replace(".DLL", "")
    # Follow-up passes are SUPPLEMENTS to the pass-1 doc, not replacements -- writing one to
    # <MODULE>.md would destroy the module map. Each gets its own file.
    #   --pass2            -> <MODULE>_PASS2.md
    #   --suffix _CLUSTER1 -> <MODULE>_CLUSTER1.md
    if "--suffix" in argv:
        suffix = argv[argv.index("--suffix") + 1]
        if not suffix.startswith("_"):
            suffix = "_" + suffix
    else:
        suffix = "_PASS2" if "--pass2" in argv else ""
    raw = open(path, encoding="utf-8", errors="replace").read()
    md = extract_markdown(raw)
    if not md:
        print("no fenced markdown block found in %s" % path)
        return 1
    md = scrub(md)
    if md is None:
        return 1
    out = os.path.join(ROOT, "re", "analysis", "%s%s.md" % (module, suffix))
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(md.rstrip() + "\n")
    print("wrote %s (%d bytes)" % (out, len(md)))
    rows = extract_rows(md, module)
    print("  %d classification rows" % len(rows))
    if "--merge" in argv:
        merge(rows, module)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
