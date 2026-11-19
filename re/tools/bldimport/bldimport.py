#!/usr/bin/env python3
r"""bldimport.py - task bldrender (2026-11-18): 3D models (OBJ) become zoned buildings that grow next to stock ones.

One command from a folder of models with a models.json (the classifier page's format, sc3models 1):

  py -3.12 re/tools/bldimport/bldimport.py build   <folder> --game <game folder>   render (cached) + pack + install
  py -3.12 re/tools/bldimport/bldimport.py render  <folder>                        frames + preview sheets only
  py -3.12 re/tools/bldimport/bldimport.py pack    <folder> --game <g> [--out DIR] install (or write to DIR only)
  py -3.12 re/tools/bldimport/bldimport.py restore --game <g>                      take the buildings out again
  py -3.12 re/tools/bldimport/bldimport.py list    <folder> --game <g>              what each entry would become
  py -3.12 re/tools/bldimport/bldimport.py calibrate --game <g>                    ground diamond vs stock frames
  py -3.12 re/tools/bldimport/bldimport.py preview <folder> --game <g> --out x.jpg  models next to stock buildings
  py -3.12 re/tools/bldimport/bldimport.py scan    <folder>                        models.json entries for .bld files

Building Architect .bld files (task bldfile, 2026-11-18c) go in the same folder as the models. A .bld with no
models.json entry gets defaults (name, lot and class from the file, bldfile.suggest_class; enabled only when the
file's category is a house, shop or factory). Frames come from bldfile.frames(): the player's BAT.DAT frames when
BAT.DAT holds the same building (all four views), else the file's 200x200 preview (slot 0, mirrored for slots 1
and 3). Per-entry option `x_bld: {"art": "auto" | "bat" | "preview"}`. Format: re/analysis/BLD_FORMAT.md.

Render style per entry: `x_bldrender: {"style": "stock" | "stock_sharp" | "clean"}` (bldrender.STYLES, task
bldlook). OBJ models: unset = $SC3BLD_STYLE, else bldrender.DEFAULT_STYLE. .bld preview art: unset = the BA's own
BAT.DAT look (bldfile.BA_LOOK), a named style applies its zoom-4 and palette steps. Part of the render cache key.

What one enabled growable entry becomes (re/analysis/BUILDING_ART.md 6; recipe of BUILDING_PICK.md 6 C, the same
containers as re/tools/batgrow.py, which is proven in game):

  frames       20 frames rendered by bldrender.py (5 zooms x 4 rotation slots, zoom 4 drawn natively, scale byte 0)
  pixels       20 type-0 records (RGB565, key 0xF81F) + 20 type-1 anchors {0, T, w, h - T}, keys
               (GROUP, id << 16 | frame), in a new container mods\netmod\overlay\Apps\Res\Sprites\B1D10001_bldimport.DAT
  frame table  the class base building's 0x6300 table header, 20 entries (frame k -> (GROUP, id << 16 | k), flag 0),
               key {0x6300, GROUP, id}, in the overlay CSAttrib_Korea.IXF
  exemplar     the base building's TKB1 (same class prop 0x65, same lot size prop 0x66) re-keyed {0x207EDC0E, 0x57E,
               id}: prop 0x67 -> the frame table, prop 0x6D -> the name, prop 0x64 = the name. Overlay
               OccupantAttribs_Korea.IXF ([OccAttribCache] Entry5)
  name         {0x2026960B, 0xA1096A4F, id} in every overlay Res\Text\<lang>\SC3StringsNetpack.IXF
  family line  "Key: 1406,545184782,<id>,<weight>   <name>" first in every family the class grows from
               (batgrow.class_table), BuildingCount raised

Airports and seaports (task airsea, 2026-11-19): `"kind": "airport"` / `"kind": "seaport"` entries grow in airport and
seaport zones (re/analysis/PORT_PICK.md). The target is the family of one rule of SC3ZoneLayer.ini [ZoneDeveloperRules]
instead of a lot class (PORTS below): airport = the airpark rule 0x2207D9EE (family 3), 1x1 only, stats of the first
plain 1x1 building member (Parked Airplane 231); seaport = the dockyard rule 0xE2D3FD92 (family 27), 1x1 or 2x2, stats
of the first member of that size with attrib flag 0x100 clear (Seaport Crane 224, Loading Bay 240). "class" is not
used for them (the exemplar keeps the base's LandUse 12310 / 12330). The airpark's AddFamily (SIMRCI 0x10003022)
pushes each family pair once and ignores the Key weight, so an airport entry's weight is written as that many Key
lines of weight 1 (at most PORT_MAX_COPIES); the dockyard's (0x1002bfec) honours the weight like the RCI rules.

Landmarks (task plop, 2026-11-19): `"kind": "landmark"` entries become new landmarks in the stock landmark dialog
("Elige un Edificio Destacado"), placed with the game's own tool (re/analysis/PLOPPABLES.md). The dialog lists every
occupant exemplar whose type IsA 18000 (SIMADV 0x10008ef2, CitySim.ini [AgentTypeHierarchy]), so a landmark is data
only. It is written the way Maxis shipped its landmark packs, as a plugin the game loads by itself (SIMINIT
cISC3PluginBuildingMgr, sc3plugin.py): Apps\PlugIn\bldimport\bldimport.pin + bldimport.dat, which holds the
exemplar {0x207EDC0E, LM_GROUP, id} (stats of the first stock landmark of that lot, by id: LANDMARK below; prop 0x65 =
18000 "Landmarks"), its name {0x2026960B, LM_TEXT_GROUP, id}, the line under the name in the dialog (prop 0x7C,
{0x2026960B, LM_DESC_GROUP, id}: the entry's "description", else its name; a stock landmark's says where it stands),
the frame table {0x6300, LM_CS_GROUP, id} and the 40 pixel / anchor records (GROUP, id << 16 | frame). No overlay file
and no road mod are needed for a landmark: it works in a stock game. Lots 1x1 to 4x4, weight not used.

Civic looks and new rewards (task civmod, 2026-11-19, re/analysis/CIVIC_REWARD.md): two more plugin kinds (exemplar,
name, line under the name, frame table, pixels as for a landmark). Civic looks go into bldimport.pin / .dat, rewards into
their own plugin Apps\PlugIn\bldimport_rewards (bldimport_rewards.pin / .dat), so sc3mods_patch -Restore can move the
rewards out of PlugIn for the stock game. sc3resize (CIVVAR / NEWREWARD) makes them reachable in game, the mods loader
(sc3mods.dll) declares the reward types. The .ini files below are read only by those two, never by the game.
  "kind": "civic"   a second look for a stock civic button. models.json fields:
                      base         the button: police, jail, fire, hospital, school, college, library, museum, small_park,
                                   big_park, zoo, baseball, playground, pond, fountain, bus_stop, train_station (CIVIC)
                      lot          optional, must be the base's lot (police 3x3, library 2x2, small_park 1x1, ...)
                      description  optional: the line under the name; else the base's own
                    The exemplar is the base's own (same type id, coverage, price, prop 0x65 kept). Each press of the
                    stock button builds the next look: the stock building, then the civic entries of that base in
                    models.json order, then the stock one again. Written to bldimport_civic.ini [Variants] / [Names].
                    Without the plugin a placed look comes back as the stock building of its type (measured).
  "kind": "reward"  a new entry of Rewards and Opportunities. models.json fields:
                      lot          1x1 to 4x4; stats of the first stock reward of that lot (REWARD)
                      population   whole number, default 20000: unlocked once the city has that many people
                      year         whole number, default 0 (any year)
                      description  optional: the line under the name; else the name
                      name         may not hold ; = or line breaks (it goes into the reward row)
                    Its type id = its id (38000-38999, the ids.json block; 38xxx is free in every SYS.PAK ini). Written
                    to bldimport_rewards.ini [REWARD_BUILDINGS] (<type>=<name> ;<population>;<year>;0;0, the stock row
                    format, read with the game's own ini class) and bldimport_types.ini ([AgentTypes] /
                    [AgentTypeHierarchy], the base reward type's CitySim.ini rows with our type): a placed reward of an
                    undeclared type stops the game while the city loads. The loader declares them whenever it runs, mods
                    on or off (owner call "Loader declares"). The bare stock exe does not: sc3mods_patch -Restore moves
                    the rewards plugin to Apps\sc3mods_off\PlugIn, a normal patch run moves it back. `restore` (both
                    plugins gone) loads such a city safely, with empty lots.

Ids 38000-38999, kept per model file in <folder>\sc3build\ids.json so a saved city keeps finding its buildings.
Needs the sc3mods road mod (sc3netmod) installed: the files go into mods\netmod\overlay like bat_growables.ps1's.
Re-runnable: each run first puts back the files it wrote last time (state.json + backups), then installs again; a
record or family line of this tool's ids found in a file that changed since (another tool rewrote it) is replaced,
not duplicated. Run it after bat_growables.ps1 when you use both.
"""
import argparse
import hashlib
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.join(TOOLS, "netmod"))

import batgrow as BG          # noqa: E402  IXF / TKB1 helpers, class table, Game
import bldrender as R         # noqa: E402
import bldfile as BF          # noqa: E402  .bld reader + frames (task bldfile)

GROUP = 0xB1D10001                       # frame tables + pixels of this tool (no stock or tool container uses it)
ID_FIRST, ID_LAST = 38000, 38999         # brief 2026-11-18b; 36xxx tests/slots, 37xxx BAT conversions
PIX_DAT = "Apps/Res/Sprites/B1D10001_bldimport.DAT"
STATE_DIR = "mods/netmod/bldimport"
BUILD_DIR = "sc3build"
OVL, OCC_KOREA, CS_KOREA, BUILDFAM, NAMES = BG.OVL, BG.OCC_KOREA, BG.CS_KOREA, BG.BUILDFAM, BG.NAMES
BLD_TYPE, BLD_GROUP, CS_TYPE = BG.BLD_TYPE, BG.BLD_GROUP, BG.CS_TYPE
TEXT_TYPE, TEXT_GROUP, FAM_TYPE, FAM_GROUP = BG.TEXT_TYPE, BG.TEXT_GROUP, BG.FAM_TYPE, BG.FAM_GROUP
CELL_M = 16.0                            # metres per lot cell (classifier page convention; BUILDING_ART.md 7)
FRAMES = 20
# task airsea: kind -> the [ZoneDeveloperRules] rule whose families an entry joins (re/analysis/PORT_PICK.md)
#   rule     rule CLSID in SC3ZoneLayer.ini; its families with this LandUse get the Key line
#   sizes    lot sizes the rule can grow: airpark filler list = SizeInCellsX 1 only (SIMRCI 0x10003022); dockyard
#            draws any size that fits its rect (0x1002c12a), stock members are 1x1 and 2x2
#   filler   base = a member with attrib flag 0x100 set (True) / clear (False) / either (None)
#   copies   True = the rule ignores the Key weight: write `weight` lines of weight 1 instead
PORTS = {
    "airport": {"rule": 0x2207D9EE, "landuse": 12310, "sizes": (1,), "filler": None, "copies": True,
                "label": "Airport (airpark filler)"},
    "seaport": {"rule": 0xE2D3FD92, "landuse": 12330, "sizes": (1, 2), "filler": False, "copies": False,
                "label": "Seaport (dockyard)"},
}
PORT_MAX_COPIES = 20
# task plop: a landmark joins the stock landmark dialog (every exemplar whose type IsA 18000); stats of the first stock
# exemplar by id with a type in `types`, a square footprint of that size, a 0x6300 frame table and a name key
LANDMARK = {"landuse": 18000, "types": (18000, 18999), "sizes": (1, 2, 3, 4), "label": "Landmark"}
LM_GROUP, LM_CS_GROUP, LM_TEXT_GROUP, LM_DESC_GROUP = 0xB1D10002, 0xB1D10003, 0xB1D10004, 0xB1D10005
PLUGIN_NAME = "bldimport"
PLUGIN_DIR = "Apps/PlugIn/" + PLUGIN_NAME + "/"
LM_PIN, LM_DAT = PLUGIN_DIR + PLUGIN_NAME + ".pin", PLUGIN_DIR + PLUGIN_NAME + ".dat"
# task civmod (2026-11-19): civic looks and new rewards, also plugin kinds (re/analysis/CIVIC_REWARD.md 3). The two
# files below are read by sc3resize (sc3resize_civic.c); the game's plugin scan reads only *.pin and sprite *.DAT.
CIVIC_INI = PLUGIN_DIR + "bldimport_civic.ini"
# rewards are a plugin of their own (owner call 2026-11-19 "Loader declares"): a placed reward of an undeclared type stops
# the game on load, so sc3mods_patch -Restore takes this one folder out of Apps\PlugIn and the bare stock exe never sees
# a reward exemplar. The type declarations are made by the loader (sc3mods.dll) from TYPES_INI.
RW_PLUGIN_NAME = "bldimport_rewards"
RW_DIR = "Apps/PlugIn/" + RW_PLUGIN_NAME + "/"
RW_PIN, RW_DAT = RW_DIR + RW_PLUGIN_NAME + ".pin", RW_DIR + RW_PLUGIN_NAME + ".dat"
REWARD_INI = RW_DIR + "bldimport_rewards.ini"
TYPES_INI = RW_DIR + "bldimport_types.ini"   # the reward types' [AgentTypes] / [AgentTypeHierarchy] rows
PLUGIN_KINDS = ("landmark", "civic", "reward")
# civic "base" -> the exemplar instance (group 0x57E) the stock button builds: the 17 plain commands of SIMGEOM's command
# factory 0x1000a896 (CIVIC_REWARD.md 1). Marina, subway and rail-to-subway use other tools: not offered.
CIVIC = {"police": 0xD2, "jail": 0x1F41, "fire": 0xD3, "hospital": 0xD1, "school": 0x1F94, "college": 0xD6,
         "library": 0xF5, "museum": 0xD4, "small_park": 0xD, "big_park": 0xD5, "zoo": 0xDA, "baseball": 0xD7,
         "playground": 0x234B, "pond": 0x234C, "fountain": 0x234E, "bus_stop": 0x1F96, "train_station": 0xED}
# reward: stats of the first stock exemplar by id whose type is a [REWARD_BUILDINGS] row of Advisor-CityPlanner.ini, with
# a square lot of that size, a plain 0x6300 frame table and a name key, the 4-piece tool's instances left out (their
# tool is not the plain one). Its own type id = its id (ID_FIRST..ID_LAST): the City Planner keys rewards by type
# (SIMADV FUN_100089e7, the exemplar is the first one of that type), and sc3resize unlocks and moves types in that
# block. Population / year: the row's columns 1 and 2, petition 0 and own-rule 0 (the plain population + year rule).
REWARD = {"sizes": (1, 2, 3, 4), "label": "Reward", "population": 20000, "year": 0,
          "four_piece": set(range(0x1F5D, 0x1F61)) | set(range(0x1F8B, 0x1F8F)) | set(range(0x1F98, 0x1F9C))}


class ImportError_(Exception):
    pass


# =================================================================== models.json

def is_bld(f):
    return f.lower().endswith(".bld")


def bld_entry(folder, f):
    """Default models.json entry for a .bld file (what `scan` writes and what an unlisted .bld gets)."""
    try:
        b = BF.read_bld(os.path.join(folder, f))
    except (BF.BldError, OSError, struct.error) as e:
        return {"file": f, "kind": "growable", "enabled": False, "x_bld": {"error": str(e)}}
    cls = BF.suggest_class(b)
    cat = "0x%X" % b["category"] if b["category"] is not None else None
    e = {"file": f, "name": b["name"], "kind": "growable", "lot": [b["lot"], b["lot"]], "weight": 1,
         "enabled": cls is not None, "x_bld": {"art": "auto", "architect": b["architect"], "category": cat}}
    if cls is not None:
        e["class"] = cls
    return e


def read_models(folder, with_bld=True):
    """models.json entries, plus a default entry for every .bld in the folder that has none."""
    p = os.path.join(folder, "models.json")
    blds = sorted(n for n in os.listdir(folder) if is_bld(n)) if with_bld and os.path.isdir(folder) else []
    if not os.path.isfile(p):
        if blds:
            return [bld_entry(folder, f) for f in blds]
        raise ImportError_("%s has no models.json (make one with classifier.html)" % folder)
    j = json.load(open(p, encoding="utf-8"))
    if j.get("sc3models") != 1:
        raise ImportError_("models.json: sc3models is %r, this tool reads version 1" % j.get("sc3models"))
    models = j.get("models", [])
    have = {m.get("file") for m in models}
    return models + [bld_entry(folder, f) for f in blds if f not in have]


def ids_for(folder, models):
    """file -> id, stable: ids.json keeps every id ever given (a removed model's id is not reused)."""
    p = os.path.join(folder, BUILD_DIR, "ids.json")
    ids = json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else {}
    used = set(ids.values())
    changed = False
    for m in models:
        f = m.get("file")
        if f and f not in ids:
            nid = next((k for k in range(ID_FIRST, ID_LAST + 1) if k not in used), None)
            if nid is None:
                raise ImportError_("no free id left in %d-%d" % (ID_FIRST, ID_LAST))
            ids[f] = nid
            used.add(nid)
            changed = True
    if changed:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(ids, fh, indent=1, sort_keys=True)
    return ids


def lot_of(m):
    lot = m.get("lot", [1, 1])
    if not (isinstance(lot, list) and len(lot) == 2 and all(isinstance(x, int) for x in lot)):
        return None, "lot %r is not [n, n]" % (lot,)
    if lot[0] != lot[1]:
        return None, "lot %dx%d: only square lots grow (every stock base is n x n, batgrow.class_table)" % tuple(lot)
    if not 1 <= lot[0] <= 4:
        return None, "lot %dx%d: growables are 1x1 to 4x4" % tuple(lot)
    return lot[0], None


def rule_families(pak, fams):
    """-> {rule CLSID: [family, ...]} over every [ZoneDeveloperRules] row of SC3ZoneLayer.ini (SYS.PAK), in row
    order, each family once (task airsea)."""
    import syspak_parse
    names, _, _, recs = syspak_parse.parse(pak)
    i = [k for k, n in enumerate(names) if n.lower() == "sc3zonelayer.ini"]
    if len(i) != 1:
        raise ImportError_("SYS.PAK has %d SC3ZoneLayer.ini members" % len(i))
    sec, out = None, {}
    for ln in recs[i[0]]["lines"]:
        s = ln.strip()
        if s.startswith("["):
            sec = s.lower()
            continue
        if sec != "[zonedeveloperrules]" or "=" not in s or s.startswith(";"):
            continue
        left, right = s.split("=", 1)
        m = re.match(r"\s*\d+\s*,\s*0x([0-9a-f]+)\s*$", left, re.I)
        if not m:
            continue
        lst = out.setdefault(int(m.group(1), 16), [])
        for mm in re.finditer(r"0x81f53d09\s*,\s*0x01f58d3d\s*,\s*(\d+)", right, re.I):
            if int(mm.group(1)) not in lst:
                lst.append(int(mm.group(1)))
    return out


def port_table(game):
    """-> {kind: {"families", "bases" {size: (id, file)}, "landuse", "copies", "label"}} for PORTS (task airsea).
    Families: the rule's families whose LandUse is the kind's. Base per size: the first member, in family order, of
    type 0x207EDC0E with a plain 0x6300 frame table, a name key, prop 0x65 == the LandUse, a square footprint of that
    size and the kind's filler flag (prop 0xCA & 0x100), as batgrow.class_table picks lot-class bases."""
    fams = BG.family_records(game.read(BUILDFAM))
    rules = rule_families(game.read("Apps/Sys/SYS.PAK"), fams)
    bld = BG.stock_buildings(game)
    out = {}
    for kind, pt in PORTS.items():
        fl = [f for f in rules.get(pt["rule"], []) if f in fams and BG.family_landuse(fams[f]) == pt["landuse"]]
        if not fl:
            raise ImportError_("%s: rule 0x%08X has no family with LandUse %d" % (kind, pt["rule"], pt["landuse"]))
        bases = {}
        for f in fl:
            for m in BG.KEY_RE.finditer(fams[f]):
                if int(m.group(1)) != BLD_GROUP or int(m.group(2)) != BLD_TYPE:
                    continue
                bid = int(m.group(3))
                if bid not in bld:
                    continue
                p = bld[bid][1]
                fp, cs, fl_ = BG.tkb1_get(p, 0x66), BG.tkb1_get(p, 0x67), BG.tkb1_get(p, 0xCA)
                if not fp or fp[0] != fp[2] or fp[0] not in pt["sizes"] or fp[0] in bases:
                    continue
                flag = bool(fl_ and fl_[0] & 0x100)
                if not cs or cs[0] != CS_TYPE or (pt["filler"] is not None and flag != pt["filler"]):
                    continue
                if BG.tkb1_get(p, 0x65) != (pt["landuse"],) or BG.tkb1_get(p, 0x6D) is None:
                    continue
                bases[fp[0]] = (bid, bld[bid][0])
        miss = [n for n in pt["sizes"] if n not in bases]
        if miss:
            raise ImportError_("%s: no stock base building for lot %s in families %s" % (
                kind, ", ".join("%dx%d" % (n, n) for n in miss), fl))
        out[kind] = {"families": fl, "bases": dict(sorted(bases.items())), "landuse": pt["landuse"],
                     "copies": pt["copies"], "label": pt["label"]}
    return out


def landmark_table(game):
    """-> {"landmark": {"families": [], "bases" {size: (id, file)}, "landuse", "copies", "label"}} (task plop). Base per
    size: the first stock exemplar by id of type 0x207EDC0E whose prop 0x65 is in LANDMARK["types"], with a square
    footprint of that size, a 0x6300 frame table and a name key."""
    bld = BG.stock_buildings(game)
    lo, hi = LANDMARK["types"]
    bases = {}
    for bid in sorted(bld):
        f, p = bld[bid]
        lu, fp, cs = BG.tkb1_get(p, 0x65), BG.tkb1_get(p, 0x66), BG.tkb1_get(p, 0x67)
        if not lu or not lo <= lu[0] <= hi or not fp or fp[0] != fp[2] or fp[0] not in LANDMARK["sizes"]:
            continue
        if fp[0] in bases or not cs or cs[0] != CS_TYPE or BG.tkb1_get(p, 0x6D) is None:
            continue
        bases[fp[0]] = (bid, f)
    miss = [n for n in LANDMARK["sizes"] if n not in bases]
    if miss:
        raise ImportError_("landmark: no stock base landmark for lot %s" % ", ".join("%dx%d" % (n, n) for n in miss))
    return {"landmark": {"families": [], "bases": dict(sorted(bases.items())), "landuse": LANDMARK["landuse"],
                         "copies": False, "label": LANDMARK["label"]}}


def civic_table(game):
    """-> {"civic:<base>": {"bases" {size: (instance, file)}, "landuse", "label", ...}} for every CIVIC base (task civmod).
    One size per base: the base's own square lot (a copy keeps the base's coverage, so it keeps its lot too)."""
    bld = BG.stock_buildings(game)
    out = {}
    for name, inst in CIVIC.items():
        if inst not in bld:
            raise ImportError_("civic %s: stock exemplar 0x%X not found" % (name, inst))
        f, p = bld[inst]
        fp, lu, cs = BG.tkb1_get(p, 0x66), BG.tkb1_get(p, 0x65), BG.tkb1_get(p, 0x67)
        if not fp or fp[0] != fp[2] or not lu or not cs or cs[0] != CS_TYPE:
            raise ImportError_("civic %s: stock exemplar 0x%X is not a square plain building" % (name, inst))
        out["civic:" + name] = {"families": [], "bases": {fp[0]: (inst, f)}, "landuse": lu[0], "copies": False,
                                "label": "Civic look of %s" % BG.tkb1_get(p, 0x64).decode("cp1252")}
    return out


def syspak_sections(game, member):
    """-> {"[section]" (lower case): [(key, value), ...]} of one SYS.PAK ini member, rows in file order."""
    import syspak_parse
    names, _, _, recs = syspak_parse.parse(game.read("Apps/Sys/SYS.PAK"))
    i = [k for k, n in enumerate(names) if n.lower() == member.lower()]
    if len(i) != 1:
        raise ImportError_("SYS.PAK has %d %s members" % (len(i), member))
    sec, out = None, {}
    for ln in recs[i[0]]["lines"]:
        s = ln.strip()
        if s.startswith("["):
            sec = s.lower()
            out.setdefault(sec, [])
        elif sec and "=" in s and not s.startswith(";"):
            k, v = s.split("=", 1)
            out[sec].append((k.strip(), v.strip()))
    return out


def reward_types(game):
    """[REWARD_BUILDINGS] type ids of SYS.PAK's Advisor-CityPlanner.ini, in row order."""
    return [int(k, 0) for k, _ in syspak_sections(game, "Advisor-CityPlanner.ini").get("[reward_buildings]", [])]


def agent_type_rows(game, base_type, nid):
    """-> ([AgentTypes] value, [AgentTypeHierarchy] parent) for a new reward type (task civmod): the base reward type's
    CitySim.ini rows with our own name token. A type that is not declared has no agent type object, and placing it
    faults the City Planner (SIMADV 0x1000b392); sc3resize NEWREWARD passes these rows to the game's own registry
    callbacks right after CitySim.ini's (SC3U cSC3App::LoadRegistry 0x0040bc80 / 0x0040bccb)."""
    cs = syspak_sections(game, "CitySim.ini")
    at = {int(k, 0): v for k, v in cs.get("[agenttypes]", [])}
    hi = {int(k, 0): v for k, v in cs.get("[agenttypehierarchy]", [])}
    if base_type not in at or base_type not in hi:
        raise ImportError_("CitySim.ini has no [AgentTypes] / [AgentTypeHierarchy] row for type %d" % base_type)
    name, _, key = at[base_type].partition(":")
    return ("bldimport%d:%s" % (nid, key)).encode("ascii"), hi[base_type].encode("ascii")


def reward_table(game):
    """-> {"reward": {"bases" {size: (id, file)}, ...}} (task civmod), the base rule in REWARD above."""
    bld = BG.stock_buildings(game)
    types = set(reward_types(game))
    bases = {}
    for bid in sorted(bld):
        f, p = bld[bid]
        lu, fp, cs = BG.tkb1_get(p, 0x65), BG.tkb1_get(p, 0x66), BG.tkb1_get(p, 0x67)
        if bid in REWARD["four_piece"] or not lu or lu[0] not in types or not fp or fp[0] != fp[2]:
            continue
        if fp[0] not in REWARD["sizes"] or fp[0] in bases or not cs or cs[0] != CS_TYPE or BG.tkb1_get(p, 0x6D) is None:
            continue
        bases[fp[0]] = (bid, f)
    miss = [n for n in REWARD["sizes"] if n not in bases]
    if miss:
        raise ImportError_("reward: no stock base reward for lot %s" % ", ".join("%dx%d" % (n, n) for n in miss))
    return {"reward": {"families": [], "bases": dict(sorted(bases.items())), "landuse": None, "copies": False,
                       "label": REWARD["label"]}}


def target_of(e):
    """Key of an entry's target in plan()'s table: the lot class (growable), the kind (airport / seaport / landmark /
    reward) or "civic:<base>"."""
    if e["kind"] == "civic":
        return "civic:" + e["base"]
    return e["kind"] if e["kind"] in PORTS or e["kind"] in PLUGIN_KINDS else e["class"]


def tkb1_set_u32(buf, prop, v):
    """Set a one-value type-3 prop (task plop: prop 0x65 of a landmark copy)."""
    b = bytearray(buf)
    for p, t, n, off, ln in BG.tkb1_props(buf):
        if p == prop:
            if t != 3 or n != 1:
                raise ImportError_("prop 0x%x is not one number" % prop)
            struct.pack_into("<I", b, off, v)
            return bytes(b)
    raise ImportError_("prop 0x%x not present" % prop)


def plugin_pin(keys, name=PLUGIN_NAME):
    """The .pin of a plugin (landmarks + civic looks: bldimport; rewards: bldimport_rewards), in the Maxis landmark packs'
    layout (sc3plugin.py). keys: [(id, name bytes)]."""
    nm = name.encode()
    out = (b"[Admin]\r\nEnabled=ON\r\n\r\n[DBSegments]\r\n0x00000001=0x80C381D7;%PluginDirectory%" + nm + b"\\" + nm +
           b".dat\r\n\r\n[SpriteSegments]\r\n" + nm + b"=addon-enabled\r\n\r\n[OccupantKeys]\r\n")
    for nid, name in keys:
        out += b"0x%08X,0x%08X,0x%08X=%d %s\r\n" % (BLD_TYPE, LM_GROUP, nid, nid, name)
    return out


def civic_ini(lines, names):
    """bldimport_civic.ini (task civmod): [Variants] <base instance>=<ids in group LM_GROUP, models.json order> and
    [Names] <id>=<name>, read by sc3resize CIVVAR (each press of the stock button: stock look, then each variant)."""
    out = (b"; bldimport civic looks (task civmod), read by sc3resize CIVVAR. Each press of the stock button builds the\r\n"
           b"; next look: the stock building, then these, in order. Variants are instances in group 0x%08X.\r\n"
           b"[Variants]\r\n" % LM_GROUP)
    for b in sorted(lines):
        out += b"0x%08X=%s\r\n" % (b, b",".join(b"0x%08X" % i for i in lines[b]))
    out += b"\r\n[Names]\r\n" + b"".join(b"0x%08X=%s\r\n" % (i, nm) for i, nm in names)
    return out


def opts(m):
    x = m.get("x_bldrender") or {}
    return {"shadow": bool(x.get("shadow", True)), "ground": x.get("ground", "grass"),
            "cell_m": float(x.get("cell_m", CELL_M)), "style": style_name(m)}


def style_name(m):
    """bldrender style of an entry: x_bldrender.style, else $SC3BLD_STYLE, else bldrender.DEFAULT_STYLE (task
    bldlook). Resolved here so the render cache key changes with it."""
    return R.style_of((m.get("x_bldrender") or {}).get("style"))[0]


def bld_style(m):
    """.bld preview art: only a style named in the entry (x_bldrender.style), checked; None = the BA's own BAT.DAT
    look (bldfile.BA_LOOK: zoom 4 doubled, no palette cut). $SC3BLD_STYLE is for bldrender's renders only."""
    s = (m.get("x_bldrender") or {}).get("style")
    return R.style_of(s)[0] if s else None


# =================================================================== render (cached)

def _sha_file(p, h):
    with open(p, "rb") as fh:
        h.update(fh.read())


def model_files(folder, m):
    """The OBJ plus every MTL and texture it names (for the cache key)."""
    obj = os.path.join(folder, m["file"])
    out = [obj]
    if is_bld(m["file"]):
        return out
    for ln in open(obj, encoding="utf-8", errors="replace"):
        p = ln.split()
        if p[:1] == ["mtllib"]:
            for n in p[1:]:
                mp = os.path.join(os.path.dirname(obj), n)
                if os.path.isfile(mp):
                    out.append(mp)
                    for l2 in open(mp, encoding="utf-8", errors="replace"):
                        q = l2.split()
                        if q[:1] and q[0].lower() == "map_kd" and len(q) > 1:
                            tp = os.path.join(os.path.dirname(mp), q[-1])
                            if os.path.isfile(tp):
                                out.append(tp)
    return out


def bld_art(m):
    return (m.get("x_bld") or {}).get("art", "auto")


def render_key(folder, m, n, game=None):
    h = hashlib.sha256()
    for p in model_files(folder, m):
        _sha_file(p, h)
    for p in (os.path.join(HERE, "bldrender.py"), os.path.join(HERE, "bldfile.py")):
        _sha_file(p, h)
    if is_bld(m["file"]):
        if game is not None and bld_art(m) != "preview" and game.exists(BG.BAT_REL):
            h.update(game.read(BG.BAT_REL))
        side = os.path.join(os.path.dirname(os.path.join(folder, m["file"])), BF.SIDE_NAME)
        if bld_art(m) != "preview" and os.path.isfile(side):        # sc3compat-a: the player's BA render beside it
            _sha_file(side, h)
        h.update(json.dumps([n, bld_art(m), game is not None, bld_style(m)]).encode())
    else:
        h.update(json.dumps([n, m.get("scale", 1.0), m.get("rotate_deg", 0), opts(m)], sort_keys=True).encode())
    return h.hexdigest()


def frame_dir(folder, m):
    return os.path.join(folder, BUILD_DIR, os.path.splitext(m["file"])[0])


def render_one(folder, m, n, force=False, log=print, game=None):
    """-> (frames {(z, r): (image, (L, T))}, info). Cached in sc3build/<stem>/ (PNG + anchors.json + meta.json).
    game: the game folder (batgrow.Game); a .bld entry looks its building up in that game's BAT.DAT."""
    from PIL import Image
    d = frame_dir(folder, m)
    key = render_key(folder, m, n, game)
    meta_p = os.path.join(d, "meta.json")
    if not force and os.path.isfile(meta_p):
        meta = json.load(open(meta_p, encoding="utf-8"))
        if meta.get("key") == key:
            anc = json.load(open(os.path.join(d, "anchors.json"), encoding="utf-8"))
            fr = {}
            for z in range(R.ZOOMS):
                for r in range(R.ROTS):
                    nm = "z%d_r%d.png" % (z, r)
                    fr[(z, r)] = (Image.open(os.path.join(d, nm)).convert("RGBA"), tuple(anc[nm]))
            return fr, meta["info"]
    if is_bld(m["file"]):
        b = BF.read_bld(os.path.join(folder, m["file"]))
        fr, src, where = BF.frames_from(b, game, bld_art(m), style=bld_style(m))
        info = {"bld": True, "art": src, "from": where, "style": bld_style(m) or "ba", "lot": b["lot"], "architect": b["architect"], "ident": "%08X" % b["ident"],
                "grid": b["model"]["grid"], "height": b["model"]["height"]}
        return _cache_frames(d, fr, key, info, n, m), info
    o = opts(m)
    mesh = R.load_obj(os.path.join(folder, m["file"]))
    mt, info = R.place(mesh, n, cell_m=o["cell_m"], scale=float(m.get("scale", 1.0)),
                       rotate_deg=float(m.get("rotate_deg", 0)))
    info["triangles"] = int(len(mesh["tri"]))
    hm = m.get("height_m")
    if isinstance(hm, (int, float)) and hm > 0 and abs(info["size_m"][1] - hm) > 0.1 * hm:
        log("  note: %s is %.1f m tall after scale, models.json says height_m %.1f (scale wins)"
            % (m["file"], info["size_m"][1], hm))
    if not info["fits"]:
        log("  note: %s is %.1f x %.1f m, larger than its %dx%d lot (%.0f m): it will overhang the neighbours"
            % (m["file"], info["size_m"][0], info["size_m"][2], n, n, info["lot_m"]))
    info["style"] = o["style"]
    fr = R.render_model(mt, n, ground=None if o["ground"] == "none" else o["ground"], shadows=o["shadow"],
                        style=o["style"])
    return _cache_frames(d, fr, key, info, n, m), info


def _cache_frames(d, fr, key, info, n, m):
    """Write the frames, anchors.json, sheet.png and meta.json into the cache folder d; -> fr."""
    meta_p = os.path.join(d, "meta.json")
    os.makedirs(d, exist_ok=True)
    anc = {}
    for (z, r), (im, LT) in fr.items():
        nm = "z%d_r%d.png" % (z, r)
        im.save(os.path.join(d, nm))
        anc[nm] = list(LT)
    with open(os.path.join(d, "anchors.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(anc, fh, indent=1, sort_keys=True)
    R.sheet(fr, os.path.join(d, "sheet.png"), scale=2)
    with open(meta_p, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"key": key, "info": info, "lot": n, "file": m["file"]}, fh, indent=1)
    return fr


# =================================================================== validate

def plan(folder, game, log=print):
    """-> (entries to install, report lines). game None = render-only checks (no class table)."""
    models = read_models(folder)
    ids = ids_for(folder, models)
    table = BG.class_table(game) if game else None
    ports = port_table(game) if game else None
    civic = civic_table(game) if game else None
    out, rep = [], []
    for m in models:
        f = m.get("file", "?")
        nid = ids.get(f)
        name = (m.get("name") or os.path.splitext(f)[0]).strip()
        why = None
        kind0 = m.get("kind", "growable")
        base = m.get("base")
        if kind0 == "civic" and "lot" not in m and civic and isinstance(base, str) and "civic:" + base in civic:
            m = dict(m, lot=[next(iter(civic["civic:" + base]["bases"]))] * 2)   # civic: the base's lot by default
        n, lot_err = lot_of(m)
        if is_bld(f) and os.path.isfile(os.path.join(folder, f)) and not lot_err:
            try:
                bl = BF.read_bld(os.path.join(folder, f))["lot"]
            except (BF.BldError, OSError, struct.error) as e:
                lot_err = "not a readable .bld file (%s)" % e
            else:
                if "lot" in m and n != bl:
                    lot_err = "lot %dx%d in models.json, the .bld file is %dx%d" % (n, n, bl, bl)
                n = bl
        cls = m.get("class")
        w = m.get("weight", 1)
        kind = m.get("kind", "growable")
        port = PORTS.get(kind) if isinstance(kind, str) else None
        lm = kind in PLUGIN_KINDS                     # a plugin building: landmark, civic look or reward (no class)
        pop, year = m.get("population", REWARD["population"]), m.get("year", REWARD["year"])
        if not m.get("enabled", True):
            why = "enabled is false"
        elif kind != "growable" and port is None and not lm:
            why = "kind %r: only growable, airport, seaport, landmark, civic and reward buildings" % (kind,)
        elif kind == "civic" and not (isinstance(base, str) and base in CIVIC):
            why = "civic base %r: one of %s" % (base, ", ".join(sorted(CIVIC)))
        elif kind == "civic" and civic is not None and not lot_err and n not in civic["civic:" + base]["bases"]:
            why = "civic lot %dx%d: a %s look keeps the stock lot, %s" % (n, n, base, " ".join(
                "%dx%d" % (s, s) for s in civic["civic:" + base]["bases"]))
        elif kind == "reward" and not (isinstance(pop, int) and 0 <= pop <= 100000000):
            why = "population %r is not a whole number from 0 to 100000000" % (pop,)
        elif kind == "reward" and not (isinstance(year, int) and 0 <= year <= 9999):
            why = "year %r is not a whole number from 0 to 9999 (0 = any year)" % (year,)
        elif kind == "reward" and any(c in name for c in ";=\r\n"):
            why = "reward name %r: the reward row cannot hold ; = or line breaks" % name
        elif not os.path.isfile(os.path.join(folder, f)):
            why = "file not in the folder"
        elif not (f.lower().endswith(".obj") or is_bld(f)):
            why = "only .obj models and .bld files"
        elif cls is None and is_bld(f) and port is None and not lm:
            why = "no class: its category (%s) is not a house, shop or factory, set one in models.json" % (
                (m.get("x_bld") or {}).get("category"))
        elif lot_err:
            why = lot_err
        elif not isinstance(w, int) or not 1 <= w <= 1000:
            why = "weight %r is not a whole number from 1 to 1000" % (w,)
        elif port is not None and port["copies"] and w > PORT_MAX_COPIES:
            why = ("weight %d: an %s's weight is the number of copies in the airpark's list (the rule ignores Key "
                   "weights), at most %d" % (w, kind, PORT_MAX_COPIES))
        elif kind in ("landmark", "reward") and n not in LANDMARK["sizes"]:
            why = "%s lot %dx%d: %ss are %s" % (kind, n, n, kind, ", ".join("%dx%d" % (s, s) for s in LANDMARK["sizes"]))
        elif port is not None and n not in port["sizes"]:
            why = "%s lot %dx%d: the %s grows %s" % (kind, n, n, port["label"].lower(), " and ".join(
                "%dx%d" % (s, s) for s in port["sizes"]))
        elif port is None and not lm and table is not None and cls not in table:
            why = "class %r is not a growable class (%s)" % (cls, ", ".join(map(str, sorted(table))))
        elif port is None and not lm and table is not None and n not in table[cls]["bases"]:
            why = "class %d has no %dx%d lot (it has %s)" % (cls, n, n, ", ".join(
                "%dx%d" % (s, s) for s in table[cls]["bases"]))
        else:
            try:
                name.encode("cp1252")
            except UnicodeEncodeError:
                why = "name %r has characters the game's text files cannot hold (cp1252)" % name
        desc = None
        if not why and lm:
            desc = m.get("description")
            desc = desc.strip() if isinstance(desc, str) and desc.strip() else (None if kind == "civic" else name)
            try:
                (desc or "").encode("cp1252")
            except UnicodeEncodeError:
                why = "description %r has characters the game's text files cannot hold (cp1252)" % desc
        if why:
            rep.append("skip  [%s] %s: %s" % (nid, f, why))
            continue
        if port is not None:
            cls = port["landuse"]                       # the base's LandUse; models.json "class" is not used
        if kind == "landmark":
            cls = LANDMARK["landuse"]
        elif kind == "civic":
            cls = civic["civic:" + base]["landuse"] if civic else None   # the base's type id (police 13130, ...)
        elif kind == "reward":
            cls = nid                                                   # its own type id = its id
        out.append({"id": nid, "file": f, "name": name, "lot": n, "class": cls, "weight": w, "model": m,
                    "kind": kind if (port is not None or lm) else "growable"})
        if lm:
            out[-1]["desc"] = desc
        if kind == "civic":
            out[-1]["base"] = base
        if kind == "reward":
            out[-1]["population"], out[-1]["year"] = pop, year
    if table is not None:
        table = dict(table)
        table.update(ports)
        table.update(landmark_table(game))
        table.update(civic)
        if any(e["kind"] == "reward" for e in out):
            table.update(reward_table(game))
    return out, rep, table


# =================================================================== pack

def frame_table(base_tab, nid):
    """Base table header (BIN\\r v1, ZoomCount 5, RotCount 4, ...) + 20 entries pointing at this id's records."""
    if base_tab[:4] != b"BIN\r" or len(base_tab) < 0x18:
        raise ImportError_("base frame table is not a BIN\\r table")
    hdr = bytearray(base_tab[:0x18])
    struct.pack_into("<H", hdr, 0x16, FRAMES)
    ents = b"".join(struct.pack("<HIIBHH", k, GROUP, (nid << 16) | k, 0, 0, 0) for k in range(FRAMES))
    return bytes(hdr) + ents


def stock_table_and_template(game, ex):
    """-> (frame table bytes, a format-1 pixel payload to take the key / pixel format from) of a base exemplar."""
    key = BG.tkb1_get(ex, 0x67)
    if not key or key[0] != CS_TYPE:
        raise ImportError_("base exemplar prop 0x67 is not a 0x6300 frame table key")
    tab = None
    for n in game.listdir("Apps/Res/Sprites"):
        if n.lower().startswith("csattrib") and n.lower().endswith(".ixf"):
            idx, _ = BG.records(game.read("Apps/Res/Sprites/" + n))
            tab = idx.get((key[1], key[2], key[0]))
            if tab:
                break
    if tab is None:
        raise ImportError_("frame table {0x%X,0x%X,0x%X} not found in Apps\\Res\\Sprites\\CSATTRIB*.IXF" % key)
    g, i = struct.unpack_from("<II", tab, 0x18 + 2)
    for n in game.listdir("Apps/Res/Sprites"):
        if n.lower().endswith(".dat"):
            try:
                idx, _ = BG.records(game.read("Apps/Res/Sprites/" + n))
            except BG.BatError:
                continue
            p = idx.get((g, i, 0))
            if p:
                return tab, p
    raise ImportError_("pixel record (0x%X, 0x%X) of the base frame table not found" % (g, i))


def upsert(d, recs):
    """Replace the records whose key exists, append the rest."""
    have = {s[:3] for s in BG.slots(d)[:-1]}
    old = [r for r in recs if (r[0], r[1], r[2]) in have]
    new = [r for r in recs if (r[0], r[1], r[2]) not in have]
    if old:
        d = BG.replace(d, old)
    if new:
        d = BG.append(d, new)
    return d


KEY_LINE = re.compile(rb"Key:\s*1406,545184782,(\d+),\d+[^\r\n]*\r?\n")


def buildfam_lines(bf, lines):
    """Strip this tool's id range from every family, then put `lines` {family: [line]} first, counts fixed."""
    fams = BG.family_records(bf)
    new = []
    for f, text in fams.items():
        drop = [mm for mm in KEY_LINE.finditer(text) if ID_FIRST <= int(mm.group(1)) <= ID_LAST]
        add = lines.get(f, [])
        if not drop and not add:
            continue
        for mm in reversed(drop):
            text = text[:mm.start()] + text[mm.end():]
        mc = re.search(rb"BuildingCount:\s*(\d+)[^\r\n]*\r?\n", text)
        if not mc:
            raise ImportError_("BUILDFAM family %d has no BuildingCount line" % f)
        cnt = int(mc.group(1)) - len(drop) + len(add)
        text = text[:mc.start()] + b"BuildingCount: %d\r\n" % cnt + b"".join(add) + text[mc.end():]
        new.append((FAM_GROUP, f, FAM_TYPE, text))
    return BG.replace(bf, new) if new else bf


def describe(info):
    if info.get("bld"):
        return "%s art from %s (id %s, by %s)%s" % (
            info["art"], info.get("from", "the .bld"), info["ident"], info["architect"],
            ", style %s" % info.get("style", "ba") if info["art"] == "preview" else "")
    return "%d tris, %.1f x %.1f x %.1f m, style %s" % (info["triangles"], info["size_m"][0], info["size_m"][2],
                                                       info["size_m"][1], info.get("style", "?"))


def build_files(folder, game, src, log=print, force_render=False):
    """-> (files {rel: bytes}, report lines)."""
    from sprite_patch import record_from_image, anchor_payload

    def cur(rel):
        if rel in src:
            return src[rel]
        return game.read(rel) if game.exists(rel) else None

    entries, rep, table = plan(folder, game, log)
    # the overlay (road mod) only for growables / ports, or to put back what an earlier run wrote there (task plop)
    need_ovl = any(e["kind"] not in PLUGIN_KINDS for e in entries) or any(r.startswith(OVL) for r in src)
    langs = []
    if need_ovl:
        for rel in (OVL + OCC_KOREA, OVL + CS_KOREA):
            if cur(rel) is None:
                raise ImportError_("%s not found: the road mod (sc3netmod, mods\\netmod) must be installed" % rel)
        langs = [n for n in game.listdir(OVL + "Apps/Res/Text") if cur(OVL + "Apps/Res/Text/%s/%s" % (n, NAMES))]
        if not langs:
            raise ImportError_("no mods\\netmod\\overlay\\Apps\\Res\\Text\\<language>\\%s found" % NAMES)
    occ, cs, pix, names, lines = [], [], [], [], {}
    lm_recs, lm_keys = [], []
    rw_recs, rw_keys = [], []                       # task civmod: the reward plugin's records and keys
    civ_lines, civ_names, rw_rows = {}, [], []      # task civmod: base -> [id], (id, name), reward rows
    rw_types, rw_hier = [], []                      # task civmod: the reward types' CitySim.ini-format declarations
    bld = BG.stock_buildings(game)
    for e in entries:
        nid, n, lu = e["id"], e["lot"], e["class"]
        tg = table[target_of(e)]
        if nid in bld:
            raise ImportError_("id %d already has a stock building exemplar" % nid)
        frames, info = render_one(folder, e["model"], n, force=force_render, log=log, game=game)
        base, bfile = tg["bases"][n]
        ex = BG.base_exemplar(game, base, bfile)
        tab, tmpl = stock_table_and_template(game, ex)
        nm = e["name"].encode("cp1252")
        lm = e["kind"] in PLUGIN_KINDS
        base_type = BG.tkb1_get(ex, 0x65)[0]
        ex = BG.tkb1_set_key(ex, 0x67, (CS_TYPE, LM_CS_GROUP if lm else GROUP, nid))
        ex = BG.tkb1_set_key(ex, 0x6D, (TEXT_TYPE, LM_TEXT_GROUP if lm else TEXT_GROUP, nid))
        ex = BG.tkb1_set_text(ex, 0x64, nm)
        if e["kind"] in ("landmark", "reward"):
            ex = tkb1_set_u32(ex, 0x65, lu)     # landmark 18000, reward its own type; a civic look keeps the base's
        if lm and e["desc"] is not None:
            ex = BG.tkb1_set_key(ex, 0x7C, (TEXT_TYPE, LM_DESC_GROUP, nid))
        BG.tkb1_props(ex)
        if lm:
            precs, pkeys = (rw_recs, rw_keys) if e["kind"] == "reward" else (lm_recs, lm_keys)
            precs.append((LM_GROUP, nid, BLD_TYPE, ex))
            precs.append((LM_TEXT_GROUP, nid, TEXT_TYPE, struct.pack("<I", len(nm)) + nm))
            if e["desc"] is not None:
                dsc = e["desc"].encode("cp1252")
                precs.append((LM_DESC_GROUP, nid, TEXT_TYPE, struct.pack("<I", len(dsc)) + dsc))
            precs.append((LM_CS_GROUP, nid, CS_TYPE, frame_table(tab, nid)))
            pkeys.append((nid, nm))
            if e["kind"] == "civic":
                civ_lines.setdefault(base, []).append(nid)
                civ_names.append((nid, nm))
            elif e["kind"] == "reward":
                rw_rows.append(b"%d=%s ;%d;%d;0;0\r\n" % (nid, nm, e["population"], e["year"]))
                at_v, at_p = agent_type_rows(game, base_type, nid)
                rw_types.append(b"%d=%s\r\n" % (nid, at_v))
                rw_hier.append(b"%d=%s\r\n" % (nid, at_p))
        else:
            occ.append((BLD_GROUP, nid, BLD_TYPE, ex))
            cs.append((GROUP, nid, CS_TYPE, frame_table(tab, nid)))
        epix = (rw_recs if e["kind"] == "reward" else lm_recs) if lm else pix
        nudged = 0
        for k in range(FRAMES):
            z, r = (k % 20) // 4, k % 4
            im, (L, T) = frames[(z, r)]
            p0, (w, h), nd = record_from_image(tmpl, im)
            nudged += nd
            epix.append((GROUP, (nid << 16) | k, 0, p0))
            epix.append((GROUP, (nid << 16) | k, 1, anchor_payload(L, T, w, h)))
        if lm:
            extra = (", type %d, unlocks at population %d%s" % (nid, e["population"], ", year %d" % e["year"] if e["year"]
                     else "") if e["kind"] == "reward" else ", type %d, look %d of the button" % (
                     lu, len(civ_lines[base]) + 1) if e["kind"] == "civic" else "")
            rep.append("plop  [%d] %s: \"%s\", %s, %dx%d, stats of stock %d%s, in %s, %s%s" % (
                nid, e["file"], e["name"], tg["label"], n, n, base, extra, RW_PIN if e["kind"] == "reward" else LM_PIN, describe(info),
                ", %d magenta px nudged" % nudged if nudged else ""))
            continue
        names.append((TEXT_GROUP, nid, TEXT_TYPE, struct.pack("<I", len(nm)) + nm))
        copies = tg.get("copies", False)
        for f in tg["families"]:
            if copies:                       # airpark: weight ignored by the rule, one line per copy (PORTS)
                lines.setdefault(f, []).extend([b"Key: 1406,545184782,%d,1   %s\r\n" % (nid, nm)] * e["weight"])
            else:
                lines.setdefault(f, []).append(b"Key: 1406,545184782,%d,%d   %s\r\n" % (nid, e["weight"], nm))
        what = ("%s, %dx%d, %d %s" % (tg["label"], n, n, e["weight"], "copy" if e["weight"] == 1 else "copies")
                if copies else "%s, %dx%d, weight %d" % (
                    tg["label"] if e["kind"] in PORTS else "class %d (%s)" % (lu, BG.CLASS_LABEL[lu]), n, n, e["weight"]))
        rep.append("grow  [%d] %s: \"%s\", %s, stats of stock %d, families %s, %s%s" % (
            nid, e["file"], e["name"], what, base,
            ",".join(map(str, tg["families"])), describe(info),
            ", %d magenta px nudged" % nudged if nudged else ""))
    files = {}
    keep = set(e["id"] for e in entries)
    if lm_recs:
        files[LM_PIN] = plugin_pin(lm_keys)
        files[LM_DAT] = BG.new_container(lm_recs)
    if rw_recs:
        files[RW_PIN] = plugin_pin(rw_keys, RW_PLUGIN_NAME)
        files[RW_DAT] = BG.new_container(rw_recs)
    if civ_lines:
        files[CIVIC_INI] = civic_ini(civ_lines, civ_names)
    if rw_rows:
        files[REWARD_INI] = (b"; bldimport rewards (task civmod), read by sc3resize NEWREWARD with the game's own ini class.\r\n"
                             b"; <type>=<name> ;<population>;<year>;<petition 0>;<own rule 0>, the stock row format.\r\n"
                             b"[REWARD_BUILDINGS]\r\n" + b"".join(rw_rows))
        files[TYPES_INI] = (b"; bldimport reward types (task civmod), declared as CitySim.ini declares the base reward's type.\r\n"
                            b"; The mods loader (sc3mods.dll) passes these rows to the game's own registry callbacks after\r\n"
                            b"; CitySim.ini's, with every mod on or off: a placed reward of an undeclared type stops the game on load.\r\n"
                            b"[AgentTypes]\r\n" + b"".join(rw_types) + b"\r\n[AgentTypeHierarchy]\r\n" + b"".join(rw_hier))
    if need_ovl and (entries or src):
        files[OVL + OCC_KOREA] = upsert(cur(OVL + OCC_KOREA), occ) if occ else cur(OVL + OCC_KOREA)
        files[OVL + CS_KOREA] = upsert(cur(OVL + CS_KOREA), cs) if cs else cur(OVL + CS_KOREA)
        if pix:
            files[OVL + PIX_DAT] = BG.new_container(pix)
        for lang in langs:
            rel = OVL + "Apps/Res/Text/%s/%s" % (lang, NAMES)
            files[rel] = upsert(cur(rel), names) if names else cur(rel)
        bf = cur(OVL + BUILDFAM)
        if bf is None:
            bf = game.read(BUILDFAM)
        files[OVL + BUILDFAM] = buildfam_lines(bf, lines)
    rep.append("%d building(s) to install: %s" % (len(keep), ", ".join(map(str, sorted(keep))) or "none"))
    return files, rep


# =================================================================== install / restore (batgrow's scheme)

def sha(b):
    return hashlib.sha256(b).hexdigest()


def sources(game):
    st_path = STATE_DIR + "/state.json"
    state = json.loads(game.read(st_path)) if game.exists(st_path) else {"files": {}}
    src = {}
    for rel, ent in state["files"].items():
        c = game.read(rel) if game.exists(rel) else None
        if c is not None and sha(c) == ent["written"]:
            src[rel] = game.read(STATE_DIR + "/backup/" + rel) if ent["existed"] else None
        else:
            src[rel] = c
    return src, state


def write_new(game, rel, data):
    """temp + rename: never writes through a hard link (test trees are hard-linked), never half a file."""
    p = game.path(rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".bldimport-tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, p)


def running(game):
    try:
        import subprocess
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Get-Process -Name SC3U -ErrorAction SilentlyContinue | ForEach-Object { $_.Path }"],
                             capture_output=True, text=True, timeout=30).stdout
    except (OSError, ValueError):
        return False
    apps = os.path.normcase(os.path.abspath(game.path("Apps")))
    return any(os.path.normcase(os.path.dirname(x.strip())) == apps for x in out.splitlines() if x.strip())


def apply(game, files, src, state):
    """Put back the last run's files, then write `files`; state.json records what was written."""
    new_state = {"files": {}}
    for rel, b in state["files"].items():                       # restore everything the last run touched
        orig = src.get(rel)
        if orig is None:
            if game.exists(rel) and rel not in files:
                os.remove(game.path(rel))
        elif rel not in files:
            write_new(game, rel, orig)
    for rel, b in sorted(files.items()):
        if b is None:
            continue
        orig = src[rel] if rel in src else (game.read(rel) if game.exists(rel) else None)
        now = game.read(rel) if game.exists(rel) else None
        if orig == b:                                          # nothing of ours left in this file
            if now != b:
                write_new(game, rel, b)
            continue
        if orig is not None:
            write_new(game, STATE_DIR + "/backup/" + rel, orig)
        if now != b:
            write_new(game, rel, b)
        new_state["files"][rel] = {"existed": orig is not None, "written": sha(b)}
    write_new(game, STATE_DIR + "/state.json", json.dumps(new_state, indent=1, sort_keys=True).encode())
    return new_state


def cmd_build(a, render_only=False):
    folder = os.path.abspath(a.folder)
    if render_only:
        entries, rep, _ = plan(folder, None)
        for r in rep:
            print(r)
        game = BG.Game(a.game) if getattr(a, "game", None) else None
        for e in entries:
            fr, info = render_one(folder, e["model"], e["lot"], force=a.force, game=game)
            print("render [%s] %s -> %s (%s)" % (
                e["id"], e["file"], os.path.join(frame_dir(folder, e["model"]), "sheet.png"), describe(info)))
        return 0
    game = BG.Game(a.game)
    if not game.exists("Apps/Sys/SYS.PAK"):
        raise ImportError_("%s has no Apps\\Sys\\SYS.PAK: pass the game folder with --game" % a.game)
    src, state = sources(game)
    files, rep = build_files(folder, game, src, force_render=getattr(a, "force", False))
    for r in rep:
        print(r)
    if getattr(a, "out", None):
        for rel, b in sorted(files.items()):
            p = os.path.join(a.out, *rel.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as fh:
                fh.write(b)
            print("wrote %-70s %9d" % (rel, len(b)))
        return 0
    if running(game):
        raise ImportError_("SimCity 3000 is running from this folder: close it first")
    st = apply(game, files, src, state)
    for rel in sorted(st["files"]):
        print("installed %s" % rel)
    return 0


def cmd_scan(a):
    """Add a models.json entry for every .bld in the folder that has none (other entries kept as they are)."""
    folder = os.path.abspath(a.folder)
    p = os.path.join(folder, "models.json")
    j = json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else {"sc3models": 1, "models": []}
    if j.get("sc3models") != 1:
        raise ImportError_("models.json: sc3models is %r, this tool reads version 1" % j.get("sc3models"))
    have = {m.get("file") for m in j["models"]}
    added = [bld_entry(folder, f) for f in sorted(os.listdir(folder)) if is_bld(f) and f not in have]
    j["models"] += added
    for e in added:
        print("added %s: \"%s\" %s, class %s%s" % (e["file"], e.get("name", "?"), "x".join(map(str, e.get("lot", []))),
                                              e.get("class"), "" if e["enabled"] else " (disabled: set a class)"))
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(j, fh, indent=1)
    print("%s: %d added, %d entries" % (p, len(added), len(j["models"])))
    return 0


def cmd_restore(a):
    game = BG.Game(a.game)
    if running(game):
        raise ImportError_("SimCity 3000 is running from this folder: close it first")
    src, state = sources(game)
    apply(game, {}, src, state)
    print("restored %d file(s)" % len(state["files"]))
    return 0


def cmd_list(a):
    folder = os.path.abspath(a.folder)
    game = BG.Game(a.game)
    entries, rep, table = plan(folder, game)
    for r in rep:
        print(r)
    for e in entries:
        base = table[target_of(e)]["bases"][e["lot"]][0]
        kd = "class %d" % e["class"] if e["kind"] == "growable" else "%s (LandUse %d)" % (e["kind"], e["class"])
        print("ok    [%d] %s: %s %dx%d weight %d (stats of stock %d)" % (e["id"], e["file"], kd,
                                                                    e["lot"], e["lot"], e["weight"], base))
    return 0


# =================================================================== calibrate / preview

def stock_building_frames(game, bid):
    """-> {(z, r): (image, (L, T))} of a stock building, z 0..3 (zoom 4 = zoom 3 at scale 2 in stock)."""
    import qfs
    import sprite_render as sr
    bld = BG.stock_buildings(game)
    ex = bld[bid][1]
    tab, _ = stock_table_and_template(game, ex)
    want = {}
    for k in range(16):
        g, i = struct.unpack_from("<II", tab, 0x18 + 15 * k + 2)
        want[(g, i)] = k
    out = {}
    for n in game.listdir("Apps/Res/Sprites"):
        if not n.lower().endswith(".dat"):
            continue
        try:
            idx, _ = BG.records(game.read("Apps/Res/Sprites/" + n))
        except BG.BatError:
            continue
        for (g, i), k in want.items():
            if (g, i, 0) in idx and k not in out:
                kind, block, inf = qfs.decode_record(idx[(g, i, 0)])
                L, T, _r, _b = struct.unpack("<4h", idx[(g, i, 1)])
                out[k] = (sr.span_to_image(block), (L, T))
        if len(out) == 16:
            break
    return {(k // 4, k % 4): v for k, v in out.items()}


def cmd_calibrate(a):
    """Ground diamond of an empty lot vs the stock frames below the registration row (always ground)."""
    import numpy as np
    game = BG.Game(a.game)
    empty = {"tri": np.zeros((0, 3, 3)), "uv": np.zeros((0, 3, 2)), "has_uv": np.zeros(0, bool),
             "mat": np.zeros(0, np.int32), "mats": [{"kd": (1, 1, 1), "tex": None}]}
    bad = 0
    for bid in a.ids:
        fp = BG.tkb1_get(BG.stock_buildings(game)[bid][1], 0x66)
        n = fp[0]
        fr = stock_building_frames(game, bid)
        line = []
        for (z, r), (im, (L, T)) in sorted(fr.items()):
            sm = (np.asarray(im)[..., 3] >= 128)[T:]
            f, (L2, T2) = R.render_frame(empty, n, z, r, ss=8, shadows=False)
            m = (np.asarray(f)[..., 3] >= 128)[T2:]
            hh = min(sm.shape[0], m.shape[0])
            x = int((sm[:hh] ^ m[:hh]).sum()) + 1000 * (sm.shape != m.shape)
            bad += x > 0
            line.append("z%dr%d %d/%d" % (z, r, x, int(m[:hh].sum())))
        print("%d (%dx%d): %s" % (bid, n, n, " ".join(line)))
    print("calibrate: %d frame(s) differ" % bad)
    return 1 if bad else 0


def cmd_preview(a):
    """Each model next to its class's stock base building, at one zoom, every slot; JPEG for phones (<= 1400 px)."""
    from PIL import Image, ImageDraw
    folder = os.path.abspath(a.folder)
    game = BG.Game(a.game)
    entries, rep, table = plan(folder, game)
    z = a.zoom
    rows = []
    for e in entries:
        fr, _ = render_one(folder, e["model"], e["lot"], game=game)
        base = table[target_of(e)]["bases"][e["lot"]][0]
        st = stock_building_frames(game, base)
        sz = min(z, 3)
        sc = 2 if z == 4 else 1
        stock = []
        for r in range(4):
            im, LT = st[(sz, r)]
            if sc != 1:
                im = im.resize((im.width * sc, im.height * sc), Image.NEAREST)
            stock.append(im)
        rows.append(("%s (%d) vs stock %d" % (e["name"], e["id"], base), [fr[(z, r)][0] for r in range(4)] + stock))
    pad = 10
    W = max(sum(i.width for i in rw) + pad * (len(rw) + 2) for _, rw in rows)
    H = sum(max(i.height for i in rw) + pad + 16 for _, rw in rows) + pad
    im = Image.new("RGB", (W, H), (60, 100, 60))
    d = ImageDraw.Draw(im)
    y = pad
    for label, rw in rows:
        d.text((pad, y), label, fill=(255, 255, 255))
        y += 16
        x = pad
        for k, f in enumerate(rw):
            if k == 4:
                x += pad
            im.paste(f, (x, y), f)
            x += f.width + pad
        y += max(i.height for i in rw) + pad
    if im.width > 1400:
        im = im.resize((1400, round(im.height * 1400 / im.width)), Image.LANCZOS)
    im.save(a.out, quality=90)
    print("wrote", a.out, im.size)
    return 0


def cmd_check(a):
    """Read the installed (or --root) files back: every id's exemplar -> frame table -> 20 pixel + anchor records,
    decoded pixels == the rendered PNGs (5/6/5), anchors == anchors.json, name record, family lines."""
    import numpy as np
    import qfs
    import sprite_render as sr
    from PIL import Image
    folder = os.path.abspath(a.folder)
    game = BG.Game(a.game)
    root = BG.Game(a.root) if a.root else game
    entries, rep, table = plan(folder, game)

    def rd(rel):
        return root.read(rel) if root.exists(rel) else game.read(rel) if game.exists(rel) else None

    grow = [e for e in entries if e["kind"] not in PLUGIN_KINDS]
    plug = [e for e in entries if e["kind"] in PLUGIN_KINDS]
    occ = cs = px = fams = {}
    langs = []
    if grow:
        occ, _ = BG.records(rd(OVL + OCC_KOREA))
        cs, _ = BG.records(rd(OVL + CS_KOREA))
        px, _ = BG.records(rd(OVL + PIX_DAT))
        fams = BG.family_records(rd(OVL + BUILDFAM))
        langs = [n for n in game.listdir(OVL + "Apps/Res/Text") if game.exists(OVL + "Apps/Res/Text/%s/%s" % (n, NAMES))]
    # task civmod: plugin kinds read the plugin .dat (exemplar, name, frame table and pixels together), the .pin's
    # [OccupantKeys] line, and for civic / reward the sc3resize ini lines
    pdat, rdat, pin, rpin, civ, rwi, tyi = {}, {}, b"", b"", b"", b"", b""
    if plug:
        d, d2 = rd(LM_DAT), rd(RW_DAT)
        pdat = BG.records(d)[0] if d else {}
        rdat = BG.records(d2)[0] if d2 else {}
        pin, rpin = rd(LM_PIN) or b"", rd(RW_PIN) or b""
        civ, rwi, tyi = rd(CIVIC_INI) or b"", rd(REWARD_INI) or b"", rd(TYPES_INI) or b""
    bad = 0
    ldat, lpin = pdat, pin
    for e in entries:
        nid, errs = e["id"], []
        pk = e["kind"] in PLUGIN_KINDS
        pdat, pin = (rdat, rpin) if e["kind"] == "reward" else (ldat, lpin)   # rewards: their own plugin
        ex = (pdat if pk else occ).get((LM_GROUP if pk else BLD_GROUP, nid, BLD_TYPE))
        if ex is None:
            print("FAIL [%d] no exemplar" % nid)
            bad += 1
            continue
        key = BG.tkb1_get(ex, 0x67)
        if tuple(key) != (CS_TYPE, LM_CS_GROUP if pk else GROUP, nid):
            errs.append("0x67 = %r" % (key,))
        if BG.tkb1_get(ex, 0x65) != (e["class"],):
            errs.append("0x65 = %r" % (BG.tkb1_get(ex, 0x65),))
        fp = BG.tkb1_get(ex, 0x66)
        if fp[0] != e["lot"] or fp[2] != e["lot"]:
            errs.append("0x66 = %r" % (fp,))
        if BG.tkb1_get(ex, 0x64) != e["name"].encode("cp1252"):
            errs.append("0x64 name")
        tab = pdat.get((LM_CS_GROUP, nid, CS_TYPE)) if pk else cs.get((GROUP, nid, CS_TYPE))
        if tab is None:
            print("FAIL [%d] no frame table" % nid)
            bad += 1
            continue
        anc = json.load(open(os.path.join(frame_dir(folder, e["model"]), "anchors.json"), encoding="utf-8"))
        same = 0
        for k in range(FRAMES):
            idx, g, i, fl, u1, u2 = struct.unpack_from("<HIIBHH", tab, 0x18 + 15 * k)
            z, r = (k % 20) // 4, k % 4
            p0, p1 = (pdat if pk else px).get((g, i, 0)), (pdat if pk else px).get((g, i, 1))
            if idx != k or fl != 0 or p0 is None or p1 is None:
                errs.append("frame %d entry" % k)
                continue
            kind, block, inf = qfs.decode_record(p0)
            got = np.asarray(sr.span_to_image(block))
            want = np.asarray(Image.open(os.path.join(frame_dir(folder, e["model"]), "z%d_r%d.png" % (z, r)))
                              .convert("RGBA"))
            L, T, Rr, Bb = struct.unpack("<4h", p1)
            if got.shape != want.shape or (L, T) != tuple(anc["z%d_r%d.png" % (z, r)]) or                     Rr != got.shape[1] - L or Bb != got.shape[0] - T:
                errs.append("frame %d size/anchor" % k)
                continue
            ma, mb = got[..., 3] >= 128, want[..., 3] >= 128
            q = lambda x: (x[..., 0] >> 3, x[..., 1] >> 2, x[..., 2] >> 3)  # noqa: E731
            eq = (ma == mb) & (~ma | np.all(np.stack(q(got.astype(int))) == np.stack(q(want.astype(int))), 0))
            if eq.all():
                same += 1
            else:
                errs.append("frame %d pixels (%d differ)" % (k, int((~eq).sum())))
        for lang in ([] if pk else langs):
            nr, _ = BG.records(rd(OVL + "Apps/Res/Text/%s/%s" % (lang, NAMES)))
            if (TEXT_GROUP, nid, TEXT_TYPE) not in nr:
                errs.append("no name in %s" % lang)
        if pk:
            if (LM_TEXT_GROUP, nid, TEXT_TYPE) not in pdat:
                errs.append("no name record")
            if b"0x%08X,0x%08X,0x%08X=%d " % (BLD_TYPE, LM_GROUP, nid, nid) not in pin:
                errs.append("no [OccupantKeys] line in %s" % (RW_PIN if e["kind"] == "reward" else LM_PIN))
            if e["kind"] == "civic":
                base = table[target_of(e)]["bases"][e["lot"]][0]
                m = re.search(rb"^0x%08X=([^\r\n]*)" % base, civ, re.M | re.I)
                if not m or nid not in [int(x, 0) for x in m.group(1).split(b",") if x.strip()]:
                    errs.append("not in %s [Variants] of base 0x%X" % (CIVIC_INI, base))
            if e["kind"] == "reward":
                row = b"%d=%s ;%d;%d;0;0" % (nid, e["name"].encode("cp1252"), e["population"], e["year"])
                if row not in rwi:
                    errs.append("no row %r in %s" % (row, REWARD_INI))
                if b"\n%d=bldimport%d:" % (nid, nid) not in tyi or len(re.findall(rb"(?m)^%d=" % nid, tyi)) != 2:
                    errs.append("no [AgentTypes] / [AgentTypeHierarchy] rows for type %d in %s" % (nid, TYPES_INI))
        tg = table[target_of(e)]
        for f in tg["families"]:
            ws = [int(mm.group(1)) for mm in re.finditer(rb"Key:\s*1406,545184782,%d,(\d+)" % nid, fams[f])]
            if ws != ([1] * e["weight"] if tg.get("copies") else [e["weight"]]):
                errs.append("family %d line(s) %r" % (f, ws))
            mc = re.search(rb"BuildingCount:\s*(\d+)", fams[f])
            keys = [mm for mm in BG.KEY_RE.finditer(fams[f])]
            if not mc or int(mc.group(1)) > len(keys):
                errs.append("family %d count %s > %d Key lines" % (f, mc and mc.group(1), len(keys)))
        bad += bool(errs)
        print("%s [%d] %s: %d/20 frames equal%s" % ("FAIL" if errs else "ok  ", nid, e["file"], same,
                                                    ("; " + "; ".join(errs[:6])) if errs else ""))
    print("check: %d of %d building(s) failed" % (bad, len(entries)))
    return 1 if bad else 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("build")
    s.add_argument("folder")
    s.add_argument("--game", required=True)
    s.add_argument("--force", action="store_true", help="render again even when the cache is current")
    s = sub.add_parser("pack")
    s.add_argument("folder")
    s.add_argument("--game", required=True)
    s.add_argument("--out", help="write the files here instead of installing them")
    s = sub.add_parser("render")
    s.add_argument("folder")
    s.add_argument("--force", action="store_true")
    s.add_argument("--game", help=".bld files: look the building up in this game's BAT.DAT")
    s = sub.add_parser("scan")
    s.add_argument("folder")
    s = sub.add_parser("restore")
    s.add_argument("--game", required=True)
    s = sub.add_parser("list")
    s.add_argument("folder")
    s.add_argument("--game", required=True)
    s = sub.add_parser("calibrate")
    s.add_argument("--game", required=True)
    s.add_argument("ids", nargs="*", type=int, default=[115, 3065, 126, 3077, 3020, 141])
    s = sub.add_parser("preview")
    s.add_argument("folder")
    s.add_argument("--game", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--zoom", type=int, default=4)
    s = sub.add_parser("check")
    s.add_argument("folder")
    s.add_argument("--game", required=True)
    s.add_argument("--root", help="read the written files from here (a pack --out folder) instead of the game")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "render":
            return cmd_build(a, render_only=True)
        return {"build": cmd_build, "pack": cmd_build, "restore": cmd_restore, "list": cmd_list, "scan": cmd_scan,
                "calibrate": cmd_calibrate, "preview": cmd_preview, "check": cmd_check}[a.cmd](a) or 0
    except (ImportError_, BG.BatError, R.RenderError, BF.BldError) as e:
        print("bldimport: %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
