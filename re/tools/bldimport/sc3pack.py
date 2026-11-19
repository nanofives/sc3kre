#!/usr/bin/env python3
r"""sc3pack.py - task sc3compat-b (round 2026-11-19e): read an SC3 building pack as downloaded.

The Python twin of sc3pack.js (the classifier page's pack reader). Both produce the same JSON, byte for byte, which
is what webtest/sc3pack_golden.mjs checks.

  open      a pack as downloaded: a .zip, a folder, a .zip inside a .zip (3 levels), a folder holding .zip files
  sort      every file into one of
              building   a .bld (IXF magic 0x80C381D7 with the BA model record, SC3U version 8 or 1999 version 7)
              part       a Building Architect part: .tga / .bmp images and prop .met files with a valid header,
                         kind (paint / detail / prop) from a Paints / Details / Props folder, else a .met naming the
                         image (prop), else the record 0xE3F87B0D of a .bld in the pack (version 8 only), else unknown
              plugin     the Maxis add-on style: a .pin (ini with [DBSegments]) and the IXF .dat it names (Maxis'
                         landmark packs). Task plop (2026-11-19): install writes the .pin and its .dat files where SC3U
                         loads them by itself, Apps/PlugIn/<the .pin's folder>/ (re/analysis/PLOPPABLES.md), with the
                         2000 art converted (sc3plugin.convert_dat: SC3U does not draw it as shipped)
              readme     .txt .doc .rtf .htm .html .pdf .nfo .wri .md, or a name with "readme"
              other      everything else, with a note (installer file, program, archive that could not be read ...)
  depends   per .bld: every texture name its model uses (record 0xE3F87B0C texture list), resolved as the BA renderer
            does (verify/bldbat/RESULTS.md step 3): color (no file), embedded (the .bld carries the image: the
            renderer uses it), stock (Apps/Res/BA), pack (a part in this pack), custom (Apps/BACustom), missing
            (drawn flat). Same-named files are byte-compared: pack against Apps/BACustom, and pack against pack.
  install   the pack's parts into Apps/BACustom/<Paints|Details|Props>, never over a different file of the same
            name unless that name is passed in `overwrite`; backups and state as bldimport.py
            (mods/netmod/sc3pack/state.json + backup/), link-safe (temp + rename). `remove` puts them back.
            Plugins (task plop): every .pin whose [DBSegments] files are all in the pack and under %PluginDirectory%,
            into Apps/PlugIn/ at the paths the .pin names, the same conflict / overwrite / backup rules

  py -3.12 re/tools/bldimport/sc3pack.py report <pack.zip|folder> [--game <tree>] [--json out.json]
  py -3.12 re/tools/bldimport/sc3pack.py install <pack> --game <tree> [--overwrite "Mariners 02.tga" ...] [--kind path=detail]
  py -3.12 re/tools/bldimport/sc3pack.py remove --game <tree> [--pack <name>]
"""
import argparse
import hashlib
import io
import json
import os
import re
import struct
import sys
import zipfile

VERSION = "2026-11-19e"
MAGIC = 0x80C381D7
B_GROUP = 0xC3F8D4A9
T_MODEL, I_MODEL = 0xE3F87B0C, 0xA3F8D615
T_INFO, I_INFO = 0xE3F87B0F, 0x63FBE1CC
T_TEXINFO, T_TEX = 0xE3F87B0D, 0xE3F87B10
SEP = 0xEAEAEAEA
PART_KIND = {6: "paint", 7: "detail", 16: "prop"}
KIND_DIR = {"paint": "Paints", "detail": "Details", "prop": "Props"}
FOLDER_KIND = {"paints": "paint", "details": "detail", "props": "prop"}
README_EXT = (".txt", ".doc", ".rtf", ".htm", ".html", ".pdf", ".nfo", ".wri", ".md")
INSTALLER_EXT = (".cab", ".hdr", ".ins", ".lid", ".tag", ".inx", ".ex_", ".dl_", ".bin", ".ini", ".dll")
STATE_DIR = "mods/netmod/sc3pack"
MAX_DEPTH = 3
ZIP_BAD = "not a readable .zip"
PLUGIN_ROOT = "Apps/PlugIn/"             # task plop: FS->PlugInDirectory() + "PlugIn\\" (SIMINIT 0x1000583e)


class PackError(Exception):
    pass


def sha(b):
    return hashlib.sha256(b).hexdigest()


def lkey(s):
    return (s.lower(), s)


# =================================================================== open

def _zip_entries(data, prefix, depth, out):
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        infos = z.infolist()
    except Exception:
        raise PackError(ZIP_BAD)
    for zi in infos:
        if zi.filename.endswith("/"):
            continue
        parts = [p for p in zi.filename.replace("\\", "/").split("/") if p]
        path = prefix + "/".join(parts)
        if zi.flag_bits & 1:
            out.append({"path": path, "error": "encrypted .zip entry"})
            continue
        if zi.compress_type not in (0, 8):
            out.append({"path": path, "error": ".zip method %d is not read" % zi.compress_type})
            continue
        try:
            b = z.read(zi)
        except Exception:
            out.append({"path": path, "error": "broken .zip entry"})
            continue
        _add(path, b, depth, out)


def _add(path, b, depth, out):
    if path.lower().endswith(".zip") and depth < MAX_DEPTH:
        sub = []
        try:
            _zip_entries(b, path + "/", depth + 1, sub)
        except PackError as e:
            out.append({"path": path, "data": b, "error": str(e)})
            return
        out.append({"path": path, "data": b, "archive": True})
        out.extend(sub)
    else:
        out.append({"path": path, "data": b})


def open_pack(src):
    """-> [{path, data, archive?, error?}] sorted by path (case-insensitive). A .zip file opens as its contents."""
    out = []
    if os.path.isdir(src):
        for dp, dn, fn in os.walk(src):
            dn.sort(key=str.lower)
            for f in fn:
                p = os.path.join(dp, f)
                rel = os.path.relpath(p, src).replace(os.sep, "/")
                with open(p, "rb") as fh:
                    _add(rel, fh.read(), 0, out)
    else:
        with open(src, "rb") as fh:
            b = fh.read()
        _zip_entries(b, "", 1, out)
    out.sort(key=lambda e: lkey(e["path"]))
    return out


# =================================================================== file checks

def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def art_1999(b, idx):
    """Task plop: pixel records in the 2000 add-on format (format 1, dword1 0x8000, LZO1X: sc3plugin.py)."""
    n = 0
    for (g, i, t), (off, sz) in idx.items():
        if t == 0 and sz >= 0x18 and (u32(b, off) >> 8) & 0xFF == 1 and u32(b, off + 4) == 0x8000:
            n += 1
    return n


def plugin_targets(pin_path, ini):
    """Task plop: -> ({"pin": rel, "dats": [rel]}, None) or (None, why): where install puts a .pin and its files."""
    dats = []
    for k, v in ini.get("dbsegments", []):
        path = v.split(";", 1)[1].strip() if ";" in v else ""
        if not path.lower().startswith("%plugindirectory%"):
            return None, "a [DBSegments] file is not under %PluginDirectory%: " + v
        rel = path[len("%plugindirectory%"):].replace("\\", "/").strip("/")
        if not rel or any(x in ("", ".", "..") for x in rel.split("/")):
            return None, "a [DBSegments] path is not a plain file path: " + v
        dats.append(PLUGIN_ROOT + rel)
    if not dats:
        return None, "no [DBSegments] file"
    d = dats[0].rsplit("/", 1)[0]
    return {"pin": d + "/" + base(pin_path), "dats": dats}, None


def ixf_index(b):
    """-> {(g, i, t): (off, size)} first wins, or None when b is not an IXF."""
    if len(b) < 24 or u32(b, 0) != MAGIC:
        return None
    out, o = {}, 4
    while o + 20 <= len(b):
        g, i, t, off, sz = struct.unpack_from("<5I", b, o)
        o += 20
        if (g, i, t) == (0, 0, 0):
            return out
        if 0xFFFFFFFF in (t, off, sz):
            continue
        if off + sz > len(b):
            raise PackError("record runs past the end of the file")
        out.setdefault((g, i, t), (off, sz))
    raise PackError("IXF index has no terminator")


def is_tga(b):
    if len(b) < 18:
        return False
    w, h = struct.unpack_from("<HH", b, 12)
    return b[1] in (0, 1) and b[2] in (1, 2, 3, 9, 10, 11) and w > 0 and h > 0 and b[16] in (8, 15, 16, 24, 32)


def is_bmp(b):
    return len(b) >= 26 and b[:2] == b"BM" and u32(b, 14) in (12, 40, 52, 56, 108, 124)


MET_HEAD = re.compile(r"^[ \t]*[0-9]+[ \t]*,[ \t]*[0-9]+[ \t]*,[ \t]*[0-9]+[ \t]*:")
HEX = re.compile(r"[ \t]*(?:0[xX])?[0-9A-Fa-f]{1,8}[ \t]*")
MET_NAME = re.compile(r'"([^"]+)"')


def met_names(b):
    """A prop .met: lines 'x,y,z:"a 0.bmp","a 1.bmp",...' -> the image names, or None when b is not one."""
    t = b.decode("latin-1")
    lines = [ln for ln in t.splitlines() if ln.strip()]
    if not lines or not MET_HEAD.match(lines[0]):
        return None
    names = []
    for ln in lines:
        for m in MET_NAME.findall(ln):
            if m not in names:
                names.append(m)
    return names


def parse_pin(b):
    """ini text -> {section: [[key, value]]} (sections lowercased, keys as written)."""
    out, cur = {}, None
    for ln in b.decode("latin-1").splitlines():
        s = ln.strip()
        if not s or s.startswith(";"):
            continue
        if s.startswith("[") and s.endswith("]"):
            cur = s[1:-1].strip().lower()
            out.setdefault(cur, [])
        elif "=" in s and cur is not None:
            k, v = s.split("=", 1)
            out[cur].append([k.strip(), v.strip()])
    return out


def _pstr8(p, o):
    if o >= len(p):
        raise PackError("info record too short")
    n = p[o]
    if o + 1 + n > len(p):
        raise PackError("info record too short")
    return p[o + 1:o + 1 + n], o + 1 + n


def read_bld(b, idx):
    """The fields the pack reader needs from a .bld, both versions (8 = SC3U, 7 = the 1999 Building Architect):
    lot, name, architect, model version, texture names (model record list), custom part records (0xE3F87B0D: name at
    61, then the image key; version 8 adds u32 kind after it, version 7 has no kind)."""
    def rec(i, t):
        k = (B_GROUP, i, t)
        if k not in idx:
            return None
        off, sz = idx[k]
        return b[off:off + sz]
    m = rec(I_MODEL, T_MODEL)
    info = rec(I_INFO, T_INFO)
    if m is None:
        raise PackError("no model record")
    if info is None:
        raise PackError("no info record")
    lot = info[0]
    name, o = _pstr8(info, 1)
    arch, o = _pstr8(info, o)
    ver, n = m[0], m[2]
    if ver not in (7, 8) or len(m) < 0x21 or m[4] != 0xEA or u32(m, 0x1D) != n * n * 4:
        raise PackError("model record header is not version 7 or 8")
    o = 0x21 + n * n * 4
    if o + 8 > len(m) or u32(m, o) != SEP:
        raise PackError("model record: no separator after the column table")
    o += 8 + u32(m, o + 4)
    if o + 8 > len(m) or u32(m, o) != SEP:
        raise PackError("model record: no separator after the cell data")
    cnt = u32(m, o + 4)
    o += 8
    tex = []
    for _ in range(cnt):
        if o + 4 > len(m):
            raise PackError("model record: texture list runs past the end")
        ln = u32(m, o)
        if o + 8 + ln > len(m):
            raise PackError("model record: texture list runs past the end")
        tex.append(m[o + 4:o + 4 + ln].decode("cp1252", "replace"))
        o += 8 + ln
    if o + 4 != len(m) or u32(m, o) != SEP:
        raise PackError("model record: texture list does not end the record")
    custom = []
    for (g, i, t) in sorted(idx, key=lambda k: (k[1], k[0], k[2])):
        if t != T_TEXINFO:
            continue
        off, sz = idx[(g, i, t)]
        p = b[off:off + sz]
        if len(p) < 61:
            continue
        nl = u32(p, 57)
        if 61 + nl + 12 > len(p):
            continue
        nm = p[61:61 + nl].decode("cp1252", "replace")
        it, ig, ii = struct.unpack_from("<3I", p, 61 + nl)
        kind = None
        if p[0] >= 8 and 61 + nl + 16 <= len(p):
            k = u32(p, 61 + nl + 12)
            kind = PART_KIND.get(k, "kind %d" % k)
        custom.append({"name": nm, "kind": kind, "embedded": (ig, ii, it) in idx})
    return {"lot": lot, "name": name.decode("cp1252", "replace"), "architect": arch.decode("cp1252", "replace"),
            "version": ver, "textures": tex, "custom": custom}


# =================================================================== sort

def base(path):
    return path.rsplit("/", 1)[-1]


def ext(path):
    b = base(path)
    return b[b.rfind("."):].lower() if "." in b else ""


def folder_kind(path):
    for d in reversed(path.split("/")[:-1]):
        k = FOLDER_KIND.get(d.lower())
        if k:
            return k
    return None


def other_note(path, b):
    e, bn = ext(path), base(path).lower()
    if "__macosx/" in path.lower() or bn.startswith("._"):
        return "macOS metadata"
    if bn in ("thumbs.db", "desktop.ini", ".ds_store"):
        return "system file"
    if e == ".exe":
        return "Windows program (not run)"
    if e in INSTALLER_EXT:
        return "installer file"
    if e in (".jpg", ".jpeg", ".png", ".gif"):
        return "picture"
    if e in (".tga", ".bmp", ".met"):
        return "not a valid %s file" % e[1:]
    if e == ".sc3":
        return "city save"
    if e == ".dat":
        return "not an IXF file"
    if e == ".pin":
        return "no [DBSegments] section"
    return "unknown"


def sort_pack(entries):
    """-> files (one row per entry) with the per-kind details the report needs."""
    files = []
    bld_kinds = {}                                  # part name (lower) -> kind from a v8 .bld record 0xE3F87B0D
    blds, mets = [], {}
    for e in entries:
        row = {"path": e["path"]}
        if e.get("data") is not None:
            row["size"] = len(e["data"])
            row["sha256"] = sha(e["data"])
        if e.get("archive"):
            row.update(kind="archive", note="opened")
            files.append(row)
            continue
        if e.get("error"):
            row.update(kind="other", note=e["error"])
            files.append(row)
            continue
        b, ex = e["data"], ext(e["path"])
        idx = None
        try:
            idx = ixf_index(b)
        except PackError as err:
            idx = None
            ixf_err = str(err)
        else:
            ixf_err = None
        if idx is not None and (B_GROUP, I_MODEL, T_MODEL) in idx:
            row["kind"] = "building"
            try:
                try:
                    info = read_bld(b, idx)
                except (IndexError, struct.error):
                    raise PackError("unreadable .bld record")
                row["bld"] = info
                for c in info["custom"]:
                    if c["kind"] in KIND_DIR:
                        bld_kinds.setdefault(c["name"].lower(), c["kind"])
            except PackError as err:
                row["error"] = str(err)
            blds.append(row)
        elif ex == ".pin" and "dbsegments" in parse_pin(b):
            row["kind"] = "plugin"
            row["plugin"] = {"type": "pin", "ini": parse_pin(b)}
        elif idx is not None and ex == ".dat":
            row["kind"] = "plugin"
            types = {}
            for (g, i, t) in idx:
                types["0x%08X" % t] = types.get("0x%08X" % t, 0) + 1
            row["plugin"] = {"type": "dat", "records": len(idx), "types": types,
                             "keys": sorted(idx, key=lambda k: (k[2], k[0], k[1])), "art_1999": art_1999(b, idx)}
        elif ex == ".met" and met_names(b) is not None:
            row["kind"] = "part"
            row["met"] = met_names(b)
            mets[e["path"]] = row["met"]
        elif (ex == ".tga" and is_tga(b)) or (ex == ".bmp" and is_bmp(b)):
            row["kind"] = "part"
        elif ex in README_EXT or "readme" in base(e["path"]).lower():
            row["kind"] = "readme"
        else:
            row["kind"] = "other"
            row["note"] = ixf_err if ixf_err else ("IXF file" if idx is not None else other_note(e["path"], b))
        files.append(row)
    met_of = {}
    for mp, names in sorted(mets.items(), key=lambda kv: lkey(kv[0])):
        for n in names:
            met_of.setdefault(n.lower(), mp)
    for row in files:
        if row["kind"] != "part":
            continue
        k, why = folder_kind(row["path"]), "folder"
        if k is None and "met" in row:
            k, why = "prop", "met"
        if k is None and base(row["path"]).lower() in met_of:
            k, why = "prop", "met"
        if k is None and base(row["path"]).lower() in bld_kinds:
            k, why = bld_kinds[base(row["path"]).lower()], "bld"
        if k is None:
            why = None
        row["part_kind"] = k
        row["kind_from"] = why
        if base(row["path"]).lower() in met_of and "met" not in row:
            row["prop_met"] = met_of[base(row["path"]).lower()]
    return files


# =================================================================== game side

class GameDir:
    """A game folder (the one with Apps). Writes are link-safe: temp + rename."""
    def __init__(self, root):
        self.root = os.path.abspath(root)

    def path(self, rel):
        return os.path.join(self.root, *[p for p in rel.split("/") if p])

    def exists(self, rel):
        return os.path.isfile(self.path(rel))

    def read(self, rel):
        with open(self.path(rel), "rb") as fh:
            return fh.read()

    def listdir(self, rel):
        p = self.path(rel)
        return sorted(os.listdir(p), key=lkey) if os.path.isdir(p) else []

    def write_new(self, rel, data):
        p = self.path(rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".sc3pack-tmp"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, p)

    def remove(self, rel):
        if self.exists(rel):
            os.remove(self.path(rel))


def _walk(game, rel, out):
    for n in game.listdir(rel):
        r = rel + "/" + n
        if game.exists(r):
            out.append(r)
        else:
            _walk(game, r, out)


def game_index(game):
    """-> {"stock": {name lower: [rel]}, "custom": {name lower: [rel]}} over Apps/Res/BA and Apps/BACustom."""
    out = {}
    for key, root in (("stock", "Apps/Res/BA"), ("custom", "Apps/BACustom")):
        rels = []
        _walk(game, root, rels)
        d = {}
        for r in sorted(rels, key=lkey):
            d.setdefault(base(r).lower(), []).append(r)
        out[key] = d
    return out


def _existing(game, d, name):
    for n in game.listdir(d):
        if n.lower() == name.lower() and game.exists(d + "/" + n):
            return d + "/" + n
    return None


def target_of(game, kind, name):
    d = "Apps/BACustom/" + KIND_DIR[kind]
    for n in game.listdir("Apps/BACustom"):
        if n.lower() == KIND_DIR[kind].lower():
            d = "Apps/BACustom/" + n
    return _existing(game, d, name) or d + "/" + name


# =================================================================== report

def report(entries, game=None, kinds=None):
    """The JSON both twins write. kinds: {pack path: kind} chosen by the player for parts of unknown kind."""
    kinds = kinds or {}
    files = sort_pack(entries)
    data = {e["path"]: e.get("data") for e in entries}
    gi = game_index(game) if game is not None else None
    parts = [f for f in files if f["kind"] == "part"]
    for p in parts:
        if p["path"] in kinds:
            p["part_kind"], p["kind_from"] = kinds[p["path"]], "chosen"
    by_name = {}
    for p in parts:
        by_name.setdefault(base(p["path"]).lower(), []).append(p)
    # pack parts against the game's BACustom (same name: byte-compare) and against each other
    for p in parts:
        same = by_name[base(p["path"]).lower()]
        p["pack_twins"] = [q["path"] for q in same if q is not p]
        p["pack_differ"] = sorted({q["sha256"] for q in same}) != [p["sha256"]]
        if gi is None:
            p["state"] = "no game"
            continue
        if p["part_kind"] is None:
            p["state"] = "kind unknown"
        else:
            tgt = target_of(game, p["part_kind"], base(p["path"]))
            p["target"] = tgt
            if game.exists(tgt):
                p["state"] = "installed" if sha(game.read(tgt)) == p["sha256"] else "conflict"
            else:
                p["state"] = "new"
        p["custom_same_name"] = []
        for r in gi["custom"].get(base(p["path"]).lower(), []):
            p["custom_same_name"].append({"rel": r, "same": sha(game.read(r)) == p["sha256"]})
    blds = []
    for f in files:
        if f["kind"] != "building":
            continue
        row = {"path": f["path"]}
        if "error" in f:
            row["error"] = f["error"]
            blds.append(row)
            continue
        info = f["bld"]
        row.update(name=info["name"], architect=info["architect"], lot=info["lot"], version=info["version"])
        emb = {}
        for c in info["custom"]:
            emb.setdefault(c["name"].lower(), c)
        rows, seen, counts = [], set(), {}
        for nm in info["textures"]:
            k = nm.lower()
            if not nm or k in seen:
                continue
            seen.add(k)
            r = {"name": nm}
            c = emb.get(k)
            if c is not None and c["kind"]:
                r["kind"] = c["kind"]
            pk = by_name.get(k, [])
            if pk:
                r["pack"] = [q["path"] for q in pk]
                r["pack_state"] = ("pack files differ" if pk[0]["pack_differ"] else pk[0].get("state"))
            if re.search(r"~\d", nm):
                r["note"] = "8.3 short name"
            if nm.startswith("color "):
                r["status"] = "color"
            elif c is not None and c["embedded"]:
                r["status"] = "embedded"
            elif gi is not None and k in gi["stock"]:
                r.update(status="stock", where=gi["stock"][k][0])
            elif pk:
                r["status"] = "pack"
            elif gi is not None and k in gi["custom"]:
                r.update(status="custom", where=gi["custom"][k][0])
            elif gi is None:
                r["status"] = "not checked"
            else:
                r["status"] = "missing"
            counts[r["status"]] = counts.get(r["status"], 0) + 1
            rows.append(r)
        row["parts"] = rows
        row["counts"] = counts
        row["missing"] = [r["name"] for r in rows if r["status"] == "missing"]
        row["needs_install"] = [r["name"] for r in rows if r["status"] == "pack" and r.get("pack_state") != "installed"]
        blds.append(row)
    # plugins: each .pin with the .dat files it names, and its occupant keys checked in them
    plugins = []
    dats = {base(f["path"]).lower(): f for f in files if f["kind"] == "plugin" and f["plugin"]["type"] == "dat"}
    used = set()
    for f in files:
        if f["kind"] != "plugin" or f["plugin"]["type"] != "pin":
            continue
        ini = f["plugin"]["ini"]
        segs = []
        for k, v in ini.get("dbsegments", []):
            fn = base(v.replace("\\", "/"))
            d = dats.get(fn.lower())
            segs.append({"file": fn, "found": d["path"] if d else None})
            if d:
                used.add(d["path"])
        keys, keyset = [], set()
        for s in segs:
            if s["found"]:
                keyset.update(tuple(k) for k in dats[base(s["found"]).lower()]["plugin"]["keys"])
        for k, v in ini.get("occupantkeys", []):
            xs = k.split(",")
            if len(xs) == 3 and all(HEX.fullmatch(x) for x in xs):
                t, g, i = (int(x.strip(" 	"), 16) for x in xs)
                ok = (g, i, t) in keyset
            else:
                ok = False
            keys.append({"key": k, "label": v, "in_dat": ok})
        tg, why = plugin_targets(f["path"], ini)
        if tg is not None and not all(s["found"] for s in segs):
            tg, why = None, "a [DBSegments] file is not in the pack"
        art = sum(dats[base(s["found"]).lower()]["plugin"]["art_1999"] for s in segs if s["found"])
        plugins.append({"pin": f["path"], "enabled": dict((k.lower(), v) for k, v in ini.get("admin", [])).get("enabled"),
                        "segments": segs, "occupants": keys,
                        "sprites": [k for k, v in ini.get("spritesegments", [])],
                        "install": tg, "not_installable": why, "art_1999": art})
    for f in files:
        if f["kind"] == "plugin" and f["plugin"]["type"] == "dat" and f["path"] not in used:
            plugins.append({"dat": f["path"], "pin": None})
    out_files = []
    for f in files:
        r = {k: f[k] for k in ("path", "kind", "size", "sha256", "note", "error") if k in f}
        if f["kind"] == "part":
            for k in ("part_kind", "kind_from", "prop_met", "met", "target", "state", "pack_twins", "pack_differ",
                      "custom_same_name"):
                if k in f:
                    r[k] = f[k]
        if f["kind"] == "plugin":
            r["plugin"] = f["plugin"]["type"]
            if f["plugin"]["type"] == "dat":
                r["records"] = f["plugin"]["records"]
                r["types"] = f["plugin"]["types"]
        out_files.append(r)
    counts = {}
    for f in files:
        counts[f["kind"]] = counts.get(f["kind"], 0) + 1
    return {"version": VERSION, "counts": counts, "files": out_files, "buildings": blds, "plugins": plugins,
            "game": game is not None}


# =================================================================== install / remove

def _state(game):
    p = STATE_DIR + "/state.json"
    return json.loads(game.read(p).decode()) if game.exists(p) else {"files": {}}


def _save_state(game, st):
    game.write_new(STATE_DIR + "/state.json", json.dumps(st, indent=1, sort_keys=True).encode())


def install(game, entries, pack, overwrite=(), kinds=None):
    """Write the pack's parts into Apps/BACustom. -> {"log": [[path, what]], "state": state}.
    overwrite: part names (any case) the player agreed to put over a different same-named file."""
    rep = report(entries, game, kinds)
    data = {e["path"]: e.get("data") for e in entries}
    ow = {n.lower() for n in overwrite}
    st = _state(game)
    log, done = [], set()
    for f in rep["files"]:
        if f["kind"] != "part":
            continue
        nm = base(f["path"]).lower()
        if f["part_kind"] is None:
            log.append([f["path"], "skipped: kind unknown"])
            continue
        if f["pack_differ"]:
            log.append([f["path"], "skipped: the pack has different files with this name"])
            continue
        if nm in done:
            log.append([f["path"], "skipped: same file as " + f["pack_twins"][0]])
            continue
        done.add(nm)
        tgt, b = f["target"], data[f["path"]]
        now = game.read(tgt) if game.exists(tgt) else None
        if now == b:
            log.append([f["path"], "already installed"])
            continue
        if now is not None and nm not in ow:
            log.append([f["path"], "conflict: a different " + base(tgt) + " is in " + tgt.rsplit("/", 1)[0]])
            continue
        ent = st["files"].get(tgt)
        if ent is None:
            if now is not None:
                game.write_new(STATE_DIR + "/backup/" + tgt, now)
            ent = {"existed": now is not None}
        ent.update(written=sha(b), pack=pack, source=f["path"])
        st["files"][tgt] = ent
        game.write_new(tgt, b)
        log.append([f["path"], "replaced " + tgt if now is not None else "installed " + tgt])
    # task plop: plugins (.pin + its .dat files, the 2000 art converted)
    for p in rep["plugins"]:
        if not p.get("pin"):
            continue
        if p["install"] is None:
            log.append([p["pin"], "skipped: " + p["not_installable"]])
            continue
        todo = [(p["pin"], p["install"]["pin"], data[p["pin"]])]
        for sg, tgt in zip(p["segments"], p["install"]["dats"]):
            b = data[sg["found"]]
            idx = ixf_index(b)
            if art_1999(b, idx):
                import sc3plugin
                b = sc3plugin.convert_dat(b)[0]
            todo.append((sg["found"], tgt, b))
        for srcp, tgt, b in todo:
            nm = base(tgt).lower()
            now = game.read(tgt) if game.exists(tgt) else None
            if now == b:
                log.append([srcp, "already installed"])
                continue
            if now is not None and nm not in ow:
                log.append([srcp, "conflict: a different " + base(tgt) + " is in " + tgt.rsplit("/", 1)[0]])
                continue
            ent = st["files"].get(tgt)
            if ent is None:
                if now is not None:
                    game.write_new(STATE_DIR + "/backup/" + tgt, now)
                ent = {"existed": now is not None}
            ent.update(written=sha(b), pack=pack, source=srcp)
            st["files"][tgt] = ent
            game.write_new(tgt, b)
            log.append([srcp, "replaced " + tgt if now is not None else "installed " + tgt])
    _save_state(game, st)
    return {"log": log, "state": st}


def remove(game, pack=None):
    """Put back what install wrote (all, or one pack's). A file changed since the install is left, and said so."""
    st = _state(game)
    log = []
    for rel in sorted(st["files"], key=lkey):
        ent = st["files"][rel]
        if pack is not None and ent.get("pack") != pack:
            continue
        now = game.read(rel) if game.exists(rel) else None
        if now is not None and sha(now) != ent["written"]:
            log.append([rel, "left: changed since the install"])
            del st["files"][rel]
            continue
        if ent["existed"]:
            bk = STATE_DIR + "/backup/" + rel
            game.write_new(rel, game.read(bk))
            game.remove(bk)
            log.append([rel, "put back"])
        else:
            game.remove(rel)
            log.append([rel, "removed"])
        del st["files"][rel]
    _save_state(game, st)
    return {"log": log, "state": st}


def dumps(obj):
    return json.dumps(obj, indent=1, sort_keys=True)


# =================================================================== CLI

def _kinds(a):
    out = {}
    for s in a.kind or []:
        p, k = s.rsplit("=", 1)
        out[p] = k
    return out


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report")
    r.add_argument("pack")
    r.add_argument("--game")
    r.add_argument("--json")
    r.add_argument("--kind", action="append")
    i = sub.add_parser("install")
    i.add_argument("pack")
    i.add_argument("--game", required=True)
    i.add_argument("--name", help="pack name in state.json (default: the pack's file name)")
    i.add_argument("--overwrite", action="append", default=[])
    i.add_argument("--kind", action="append")
    d = sub.add_parser("remove")
    d.add_argument("--game", required=True)
    d.add_argument("--pack")
    a = ap.parse_args(argv)
    if a.cmd == "report":
        rep = report(open_pack(a.pack), GameDir(a.game) if a.game else None, _kinds(a))
        txt = dumps(rep)
        if a.json:
            with open(a.json, "w", encoding="ascii", newline="\n") as fh:
                fh.write(txt)
        print_report(rep)
        return 0
    if a.cmd == "install":
        res = install(GameDir(a.game), open_pack(a.pack), a.name or os.path.basename(os.path.normpath(a.pack)),
                      a.overwrite, _kinds(a))
    else:
        res = remove(GameDir(a.game), a.pack)
    for p, w in res["log"]:
        print("%s: %s" % (p, w))
    return 0


def print_report(rep):
    print("files: " + ", ".join("%d %s" % (v, k) for k, v in sorted(rep["counts"].items())))
    for f in rep["files"]:
        extra = f.get("part_kind") or f.get("note") or f.get("plugin") or ""
        st = f.get("state", "")
        print("  %-8s %-10s %-10s %s" % (f["kind"], extra if isinstance(extra, str) else "", st, f["path"]))
    for b in rep["buildings"]:
        if "error" in b:
            print("%s: %s" % (b["path"], b["error"]))
            continue
        print("%s (v%d, %s): %s" % (b["path"], b["version"], b["name"],
                                     ", ".join("%d %s" % (v, k) for k, v in sorted(b["counts"].items()))))
        for r in b["parts"]:
            if r["status"] in ("pack", "custom", "missing"):
                print("    %-8s %-30s %s %s" % (r["status"], r["name"], r.get("pack_state", ""), r.get("where", "")))
    for p in rep["plugins"]:
        if p.get("pin"):
            print("plugin %s: %s, %d occupants (%d in the .dat), %s" % (
                p["pin"], ", ".join(s["file"] + ("" if s["found"] else " (not in the pack)") for s in p["segments"]),
                len(p["occupants"]), sum(o["in_dat"] for o in p["occupants"]),
                "install: " + p["install"]["pin"] + (", %d 2000-format pictures converted" % p["art_1999"]
                                                     if p["art_1999"] else "")
                if p["install"] else "not installable: " + p["not_installable"]))
        else:
            print("plugin .dat without a .pin: %s" % p["dat"])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
