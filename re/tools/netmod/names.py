"""names.py -- piece names from Occupant.ini, read straight out of Apps\\Sys\\SYS.PAK.

`[OccupantKeys]` lines look like `0x207EDC0E,0x0000057E,0x0000001D=(29) Road`. Line numbers are
1-based lines of the Occupant.ini member, i.e. the same numbers as the extracted
`re/data/syspak/Occupant.ini` (line 34 = 29 Road, line 55 = 69 Train Crossing Road).
"""
import sys

from . import paths

sys.path.insert(0, paths.TOOLS)
import syspak_parse  # noqa: E402


def occupant_ini_lines(game):
    with open(game.syspak, "rb") as fh:
        data = fh.read()
    names, _, _, recs = syspak_parse.parse(data)
    for n, r in zip(names, recs):
        if n.lower() == "occupant.ini":
            return r["lines"]
    raise SystemExit("Occupant.ini not found in %s" % game.syspak)


def occupant_keys(game):
    """-> {instance: {"name", "line", "group", "type", "text"}} from [OccupantKeys]."""
    out, section = {}, None
    for ln, raw in enumerate(occupant_ini_lines(game), 1):
        line = raw.strip()
        if line.startswith("["):
            section = line.strip("[]").lower()
            continue
        if section != "occupantkeys" or "=" not in line or line.startswith(";"):
            continue
        key, _, val = line.partition("=")
        parts = key.split(",")
        if len(parts) != 3:
            continue
        try:
            t, g, inst = (int(p, 16) for p in parts)
        except ValueError:
            continue
        name = val.strip()
        if name.startswith("("):
            name = name.partition(")")[2].strip()
        out.setdefault(inst, {"name": name, "line": ln, "type": t, "group": g, "text": line})
    return out
