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


class ImportError_(Exception):
    pass


# =================================================================== models.json

def read_models(folder):
    p = os.path.join(folder, "models.json")
    if not os.path.isfile(p):
        raise ImportError_("%s has no models.json (make one with classifier.html)" % folder)
    j = json.load(open(p, encoding="utf-8"))
    if j.get("sc3models") != 1:
        raise ImportError_("models.json: sc3models is %r, this tool reads version 1" % j.get("sc3models"))
    return j.get("models", [])


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


def opts(m):
    x = m.get("x_bldrender") or {}
    return {"shadow": bool(x.get("shadow", True)), "ground": x.get("ground", "grass"),
            "cell_m": float(x.get("cell_m", CELL_M))}


# =================================================================== render (cached)

def _sha_file(p, h):
    with open(p, "rb") as fh:
        h.update(fh.read())


def model_files(folder, m):
    """The OBJ plus every MTL and texture it names (for the cache key)."""
    obj = os.path.join(folder, m["file"])
    out = [obj]
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


def render_key(folder, m, n):
    h = hashlib.sha256()
    for p in model_files(folder, m):
        _sha_file(p, h)
    for p in (os.path.join(HERE, "bldrender.py"),):
        _sha_file(p, h)
    h.update(json.dumps([n, m.get("scale", 1.0), m.get("rotate_deg", 0), opts(m)], sort_keys=True).encode())
    return h.hexdigest()


def frame_dir(folder, m):
    return os.path.join(folder, BUILD_DIR, os.path.splitext(m["file"])[0])


def render_one(folder, m, n, force=False, log=print):
    """-> (frames {(z, r): (image, (L, T))}, info). Cached in sc3build/<stem>/ (PNG + anchors.json + meta.json)."""
    from PIL import Image
    d = frame_dir(folder, m)
    key = render_key(folder, m, n)
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
    fr = R.render_model(mt, n, ground=None if o["ground"] == "none" else o["ground"], shadows=o["shadow"])
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
    return fr, info


# =================================================================== validate

def plan(folder, game, log=print):
    """-> (entries to install, report lines). game None = render-only checks (no class table)."""
    models = read_models(folder)
    ids = ids_for(folder, models)
    table = BG.class_table(game) if game else None
    out, rep = [], []
    for m in models:
        f = m.get("file", "?")
        nid = ids.get(f)
        name = (m.get("name") or os.path.splitext(f)[0]).strip()
        why = None
        n, lot_err = lot_of(m)
        cls = m.get("class")
        w = m.get("weight", 1)
        if not m.get("enabled", True):
            why = "enabled is false"
        elif m.get("kind", "growable") != "growable":
            why = "kind %r: only growable buildings this round" % m.get("kind")
        elif not os.path.isfile(os.path.join(folder, f)):
            why = "file not in the folder"
        elif not f.lower().endswith(".obj"):
            why = "only .obj models this round"
        elif lot_err:
            why = lot_err
        elif not isinstance(w, int) or not 1 <= w <= 1000:
            why = "weight %r is not a whole number from 1 to 1000" % (w,)
        elif table is not None and cls not in table:
            why = "class %r is not a growable class (%s)" % (cls, ", ".join(map(str, sorted(table))))
        elif table is not None and n not in table[cls]["bases"]:
            why = "class %d has no %dx%d lot (it has %s)" % (cls, n, n, ", ".join(
                "%dx%d" % (s, s) for s in table[cls]["bases"]))
        else:
            try:
                name.encode("cp1252")
            except UnicodeEncodeError:
                why = "name %r has characters the game's text files cannot hold (cp1252)" % name
        if why:
            rep.append("skip  [%s] %s: %s" % (nid, f, why))
            continue
        out.append({"id": nid, "file": f, "name": name, "lot": n, "class": cls, "weight": w, "model": m})
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


def build_files(folder, game, src, log=print, force_render=False):
    """-> (files {rel: bytes}, report lines)."""
    from sprite_patch import record_from_image, anchor_payload

    def cur(rel):
        if rel in src:
            return src[rel]
        return game.read(rel) if game.exists(rel) else None

    for rel in (OVL + OCC_KOREA, OVL + CS_KOREA):
        if cur(rel) is None:
            raise ImportError_("%s not found: the road mod (sc3netmod, mods\\netmod) must be installed" % rel)
    langs = [n for n in game.listdir(OVL + "Apps/Res/Text") if cur(OVL + "Apps/Res/Text/%s/%s" % (n, NAMES))]
    if not langs:
        raise ImportError_("no mods\\netmod\\overlay\\Apps\\Res\\Text\\<language>\\%s found" % NAMES)
    entries, rep, table = plan(folder, game, log)
    occ, cs, pix, names, lines = [], [], [], [], {}
    bld = BG.stock_buildings(game)
    for e in entries:
        nid, n, lu = e["id"], e["lot"], e["class"]
        if nid in bld:
            raise ImportError_("id %d already has a stock building exemplar" % nid)
        frames, info = render_one(folder, e["model"], n, force=force_render, log=log)
        base, bfile = table[lu]["bases"][n]
        ex = BG.base_exemplar(game, base, bfile)
        tab, tmpl = stock_table_and_template(game, ex)
        nm = e["name"].encode("cp1252")
        ex = BG.tkb1_set_key(ex, 0x67, (CS_TYPE, GROUP, nid))
        ex = BG.tkb1_set_key(ex, 0x6D, (TEXT_TYPE, TEXT_GROUP, nid))
        ex = BG.tkb1_set_text(ex, 0x64, nm)
        BG.tkb1_props(ex)
        occ.append((BLD_GROUP, nid, BLD_TYPE, ex))
        cs.append((GROUP, nid, CS_TYPE, frame_table(tab, nid)))
        nudged = 0
        for k in range(FRAMES):
            z, r = (k % 20) // 4, k % 4
            im, (L, T) = frames[(z, r)]
            p0, (w, h), nd = record_from_image(tmpl, im)
            nudged += nd
            pix.append((GROUP, (nid << 16) | k, 0, p0))
            pix.append((GROUP, (nid << 16) | k, 1, anchor_payload(L, T, w, h)))
        names.append((TEXT_GROUP, nid, TEXT_TYPE, struct.pack("<I", len(nm)) + nm))
        for f in table[lu]["families"]:
            lines.setdefault(f, []).append(b"Key: 1406,545184782,%d,%d   %s\r\n" % (nid, e["weight"], nm))
        rep.append("grow  [%d] %s: \"%s\", class %d (%s), %dx%d, weight %d, stats of stock %d, families %s, %d tris, "
                   "%.1f x %.1f x %.1f m%s" % (nid, e["file"], e["name"], lu, BG.CLASS_LABEL[lu], n, n, e["weight"],
                                               base, ",".join(map(str, table[lu]["families"])), info["triangles"],
                                               info["size_m"][0], info["size_m"][2], info["size_m"][1],
                                               ", %d magenta px nudged" % nudged if nudged else ""))
    files = {}
    keep = set(e["id"] for e in entries)
    if entries or src:
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
        for e in entries:
            fr, info = render_one(folder, e["model"], e["lot"], force=a.force)
            print("render [%s] %s -> %s (%d tris, %.1f x %.1f x %.1f m)" % (
                e["id"], e["file"], os.path.join(frame_dir(folder, e["model"]), "sheet.png"), info["triangles"],
                info["size_m"][0], info["size_m"][2], info["size_m"][1]))
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
        base = table[e["class"]]["bases"][e["lot"]][0]
        print("ok    [%d] %s: class %d %dx%d weight %d (stats of stock %d)" % (e["id"], e["file"], e["class"],
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
        fr, _ = render_one(folder, e["model"], e["lot"])
        base = table[e["class"]]["bases"][e["lot"]][0]
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
        return root.read(rel) if root.exists(rel) else game.read(rel)

    occ, _ = BG.records(rd(OVL + OCC_KOREA))
    cs, _ = BG.records(rd(OVL + CS_KOREA))
    px, _ = BG.records(rd(OVL + PIX_DAT))
    fams = BG.family_records(rd(OVL + BUILDFAM))
    langs = [n for n in game.listdir(OVL + "Apps/Res/Text") if game.exists(OVL + "Apps/Res/Text/%s/%s" % (n, NAMES))]
    bad = 0
    for e in entries:
        nid, errs = e["id"], []
        ex = occ.get((BLD_GROUP, nid, BLD_TYPE))
        if ex is None:
            print("FAIL [%d] no exemplar" % nid)
            bad += 1
            continue
        key = BG.tkb1_get(ex, 0x67)
        if tuple(key) != (CS_TYPE, GROUP, nid):
            errs.append("0x67 = %r" % (key,))
        if BG.tkb1_get(ex, 0x65) != (e["class"],):
            errs.append("0x65 = %r" % (BG.tkb1_get(ex, 0x65),))
        fp = BG.tkb1_get(ex, 0x66)
        if fp[0] != e["lot"] or fp[2] != e["lot"]:
            errs.append("0x66 = %r" % (fp,))
        if BG.tkb1_get(ex, 0x64) != e["name"].encode("cp1252"):
            errs.append("0x64 name")
        tab = cs.get((GROUP, nid, CS_TYPE))
        anc = json.load(open(os.path.join(frame_dir(folder, e["model"]), "anchors.json"), encoding="utf-8"))
        same = 0
        for k in range(FRAMES):
            idx, g, i, fl, u1, u2 = struct.unpack_from("<HIIBHH", tab, 0x18 + 15 * k)
            z, r = (k % 20) // 4, k % 4
            p0, p1 = px.get((g, i, 0)), px.get((g, i, 1))
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
        for lang in langs:
            nr, _ = BG.records(rd(OVL + "Apps/Res/Text/%s/%s" % (lang, NAMES)))
            if (TEXT_GROUP, nid, TEXT_TYPE) not in nr:
                errs.append("no name in %s" % lang)
        for f in table[e["class"]]["families"]:
            m = re.search(rb"Key:\s*1406,545184782,%d,(\d+)" % nid, fams[f])
            if not m or int(m.group(1)) != e["weight"]:
                errs.append("family %d line" % f)
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
        return {"build": cmd_build, "pack": cmd_build, "restore": cmd_restore, "list": cmd_list,
                "calibrate": cmd_calibrate, "preview": cmd_preview, "check": cmd_check}[a.cmd](a) or 0
    except (ImportError_, BG.BatError, R.RenderError) as e:
        print("bldimport: %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
