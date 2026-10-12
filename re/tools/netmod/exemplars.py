"""exemplars.py -- the on-disk network-piece exemplar, and what it points at.

A placed piece loads the exemplar `{0xE223741F, 0xA317745F, pieceId}` [CONFIRMED @ SIMNTWRK
0x1000c80b]. Those records are in `Apps\\Res\\Occupant\\OccupantAttribs.IXF` (390 records with
type 0xE223741F, group 0xA317745F, all `TKB1`), found by this tool 2026-10-12. Five more with
type 0xE223741F but group 0x0000057E (the "Bridge Destroyed" pieces) are in OccupantAttribs_2.IXF.

TKB1 property layout: `sprite_patch.parse_tkb1` (`formats/SPRITE_MODDING.md`). Property meanings
below are the ones measured on buildings in SPRITE_MODDING.md, plus two cross-checks made here:
  0x64 name (authored, English)          0x65 agent type id (CitySim.ini [AgentTypes]); 16000 on
                                         road 29 = the query dialog's `object.type_id` 16000
  0x66 footprint (x, height, z)          0x67 sprite-def key {0x6300, 0x6400, n} -> CSATTRIB n
  0x6d localized-name key {0x2026960B, 0xA1096A4F, id} -> Text\\<lang>\\SC3StringsBuildings.IXF
       ("Carretera" for 29 in ENGLISH = the dialog's `object.name`)
Every other property is reported raw.
"""
import os
import sys

from . import paths

sys.path.insert(0, paths.TOOLS)
import ixf_parse  # noqa: E402
import sprite_patch as _sp  # noqa: E402
import syspak_parse  # noqa: E402

EX_TYPE = 0xE223741F
EX_GROUP = 0xA317745F
PROP_NAMES = {0x64: "name", 0x65: "agent_type", 0x66: "footprint", 0x67: "sprite_key",
              0x6D: "lname_key", 0x7C: "catalog_key"}
TEXT_TYPE = 0x2026960B


def load(game):
    """-> {pieceId: {"file", "group", "size", "props": {propId: value}}}."""
    out = {}
    for f in sorted(os.listdir(game.occupant)):
        if not f.lower().startswith("occupantattribs"):
            continue
        recs, d = ixf_parse.parse(os.path.join(game.occupant, f))
        for r in recs:
            if r["type"] != EX_TYPE:
                continue
            b = d[r["offset"]:r["offset"] + r["size"]]
            try:
                props = _sp.parse_tkb1(b)
            except _sp.SpritePatchError:
                props = {}
            out.setdefault(r["instance"], {"file": f, "group": r["group"], "size": r["size"],
                                           "props": props})
    return out


def _syspak_member(game, member):
    with open(game.syspak, "rb") as fh:
        data = fh.read()
    names, _, _, recs = syspak_parse.parse(data)
    for n, r in zip(names, recs):
        if n.lower() == member.lower():
            return r["lines"]
    return []


def agent_types(game):
    """CitySim.ini (SYS.PAK) -> ({typeId: (name, line)}, {typeId: parentId}),
    and SC3BudgetLayer.ini per-type values -> {typeId: (value, comment, line)}."""
    names, parent, section = {}, {}, None
    for ln, raw in enumerate(_syspak_member(game, "CitySim.ini"), 1):
        line = raw.strip()
        if line.startswith("["):
            section = line.strip("[]")
            continue
        if "=" not in line or line.startswith(";"):
            continue
        k, _, v = line.partition("=")
        try:
            k = int(k.strip())
        except ValueError:
            continue
        if section == "AgentTypes":
            names.setdefault(k, (v.split(":")[0].split("=")[0].strip(), ln))
        elif section == "AgentTypeHierarchy":
            try:
                parent[k] = int(v.split()[0])
            except (ValueError, IndexError):
                pass
    budget, section = {}, None
    for ln, raw in enumerate(_syspak_member(game, "SC3BudgetLayer.ini"), 1):
        line = raw.strip()
        if line.startswith("["):
            section = line.strip("[]")
            continue
        k, sep, v = line.partition("=")
        if not sep:
            continue
        try:
            k = int(k.strip())
        except ValueError:
            continue
        parts = v.split(None, 1)
        budget.setdefault(k, (parts[0] if parts else "", parts[1].strip() if len(parts) > 1
                              else "", ln, section))
    return names, parent, budget


def localized(game, langs=("ENGLISH", "English-UK")):
    """-> {lang: {(group, instance): text}} for SC3StringsBuildings.IXF (piece names)."""
    out = {}
    tdir = os.path.join(game.res, "Text")
    for lang in langs:
        d_ = os.path.join(tdir, lang)
        if not os.path.isdir(d_):
            continue
        m = {}
        for f in os.listdir(d_):
            if f.lower() != "sc3stringsbuildings.ixf":
                continue
            recs, d = ixf_parse.parse(os.path.join(d_, f))
            for r in recs:
                if r["type"] == TEXT_TYPE:
                    m[(r["group"], r["instance"])] = ixf_parse.payload_text(r, d)[0]
        out[lang] = m
    return out
