#!/usr/bin/env python3
r"""netpack_recover.py - rebuild package art sources (png_dir PNGs + anchors.json) from an installed overlay
(2026-10-27, task artrecover).

A package's png_dir art is gitignored, so it can be lost while the INSTALLED output survives. Install is lossless
for art: every PNG becomes one pixel record (sprite_patch.image_to_surface is exactly invertible, NETPACK.md 1) and
one anchor record, and the frame table says which record each frame position draws. This tool reads those records
back and writes, per variant / reskin, the PNGs and anchors.json that make netpack.compile_art produce the same
records again:

  * a frame gets a PNG only where its record differs from the source frame (the stock frame of art.from), so a frame
    that kept the stock art is not re-encoded (a re-encode of a stock record is not always the same bytes);
  * frames that share a stock record and drew the same new art share one record: one PNG, at the first position;
  * a frame that netpack split off a shared record (another PNG than the record's first owner, NETPACK.md 1) gets its
    own PNG; when its pixels and anchor equal the owner's (the original PNG files differed only in bytes) the PNG
    carries a tEXt chunk so the split is kept;
  * anchors.json lists a frame only when its size or anchor differs from the source frame.
Every variant is then compiled again from the written files and compared record by record (`check`).

Recipe art (art.recipe, built by netart at install time) and recolour-only art are not recovered: they come from
tracked files.

  py -3.12 netpack_recover.py --overlay <tree>\mods\netmod\overlay --stock <tree> --examples <examples dir> [pkg ...]
        [--write]          # default: dry run, report only
  py -3.12 netpack_recover.py --compare --overlay <shipped>\overlay --stock <tree> pkg ...   # full merge vs shipped
"""
import argparse
import io
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import netpack as N        # noqa: E402
from PIL import Image, PngImagePlugin   # noqa: E402

import ixf_parse          # noqa: E402
import qfs                # noqa: E402
import sprite_render as sr   # noqa: E402
import newpiece as NP     # noqa: E402


class RecoverError(Exception):
    pass


def load_overlay(ov):
    """-> (dat {(g, i): {type: payload}}, korea {vid: table}, csattrib {file name lower: {(t, g, i): payload}})"""
    spr = os.path.join(ov, "Apps", "Res", "Sprites")
    dat, korea, cs = {}, {}, {}
    for n in sorted(os.listdir(spr)):
        p = os.path.join(spr, n)
        recs, d = ixf_parse.parse(p)
        rows = [(r["group"], r["instance"], r["type"], d[r["offset"]:r["offset"] + r["size"]]) for r in recs]
        if n.upper().endswith("_NETPACK.DAT"):
            for g, i, t, pl in rows:
                dat.setdefault((g, i), {})[t] = pl
        elif n.lower() == os.path.basename(N.CS_KOREA).lower():
            for g, i, t, pl in rows:
                if g == N.KOREA_CS_GROUP and t == N.CS_TYPE:
                    korea[i] = pl
        elif n.lower().startswith("csattrib") and n.lower().endswith(".ixf"):
            cs[n.lower()] = {(t, g, i): pl for g, i, t, pl in rows}
    return dat, korea, cs


def png_bytes(pix, tag=None):
    kind, block, inf = qfs.decode_record(pix)
    if kind != "qfs" or inf["format"] != 1:
        raise RecoverError("record is not a format-1 sprite")
    img = sr.span_to_image(block)
    info = None
    if tag:
        info = PngImagePlugin.PngInfo()
        info.add_text("netpack_recover", tag)
    buf = io.BytesIO()
    img.save(buf, format="PNG", pnginfo=info)
    return buf.getvalue(), img.size


def recover_art(src, table, piece, dat, where):
    """src: netpack.compile_art of the art spec WITHOUT png_dir; table: the shipped frame table.
    -> ({png name: (png bytes, anchor or None)}, stats)"""
    n, sh = NP.cs_frames(table)
    frames = src["frames"]
    if n != len(frames):
        raise RecoverError("%s: shipped table has %d frames, source %d" % (where, n, len(frames)))
    keys = [k for k in src["keys"]]
    nst = len(keys)
    by_j, rec_of = {}, {}
    for pos, (_, _, g, i, _) in enumerate(frames):
        sg, si = sh[pos][2], sh[pos][3]
        if si >> 16 != piece:
            raise RecoverError("%s: frame %d points at (0x%08X, 0x%08X), not a record of piece %d"
                               % (where, pos, sg, si, piece))
        j = si & 0xFFFF
        if j < nst and keys[j] != (g, i):
            raise RecoverError("%s: frame %d record ordinal %d is source record %r, the frame's source is %r"
                               % (where, pos, j, keys[j], (g, i)))
        r = dat.get((sg, si))
        if r is None or 0 not in r or 1 not in r:
            raise RecoverError("%s: record (0x%08X, 0x%08X) missing from the overlay DATs" % (where, sg, si))
        by_j.setdefault(j, []).append(pos)
        rec_of[j] = (r[0], r[1])
    splits = sorted(j for j in by_j if j >= nst)
    if splits != list(range(nst, nst + len(splits))):
        raise RecoverError("%s: split record ordinals %s are not consecutive from %d" % (where, splits, nst))
    split_pos = []
    for j in splits:
        if len(by_j[j]) != 1:
            raise RecoverError("%s: split record %d is used by frames %s" % (where, j, by_j[j]))
        split_pos.append(by_j[j][0])
    if split_pos != sorted(split_pos):
        raise RecoverError("%s: split records are not in frame order: %s" % (where, split_pos))
    split_keys = {(frames[p][2], frames[p][3]) for p in split_pos}
    out, stats = {}, {"frames": n, "png": 0, "anchors": 0, "split": len(splits), "tagged": 0}

    def emit(pos, j, owner_rec=None):
        k = (frames[pos][2], frames[pos][3])
        pix, anc = rec_of[j]
        tag = None
        if owner_rec is not None and owner_rec == (pix, anc):
            tag = "split frame %d" % pos
            stats["tagged"] += 1
        data, (w, h) = png_bytes(pix, tag)
        src_pix, src_anc = src["pix"][k], src["anchor"][k]
        if N.sprite_size(src_pix) == (w, h) and anc == src_anc:
            a = None
        else:
            L, T = struct.unpack_from("<2h", anc, 0)
            if N.sprite_patch.anchor_payload(L, T, w, h) != anc:
                raise RecoverError("%s: frame %d anchor %r is not {L, T, w-L, h-T} for %dx%d: anchors.json cannot "
                                   "express it" % (where, pos, struct.unpack("<4h", anc), w, h))
            a = [L, T]
            stats["anchors"] += 1
        out[N.frame_png_name(pos)] = (data, a)
        stats["png"] += 1

    for j in range(nst):
        if j not in by_j:
            continue                                   # every frame of that record was split off: none points at it
        k = keys[j]
        if rec_of[j] != (src["pix"][k], src["anchor"][k]) or k in split_keys:
            emit(by_j[j][0], j)
    for j, pos in zip(splits, split_pos):
        k = (frames[pos][2], frames[pos][3])
        jo = keys.index(k)
        emit(pos, j, rec_of.get(jo))
    return out, stats


def check_art(stock, pack_dir, art, default_piece, table, piece, dat, where):
    """compile the art from the written png_dir and compare every frame's record with the shipped one."""
    got = N.compile_art(stock, pack_dir, art, default_piece, where)
    n, sh = NP.cs_frames(table)
    bad = []
    for pos, k in enumerate(got["pos_keys"]):
        j = got["keys"].index(k)
        sg, si = sh[pos][2], sh[pos][3]
        if si & 0xFFFF != j:
            bad.append("frame %d: ordinal %d, shipped %d" % (pos, j, si & 0xFFFF))
            continue
        r = dat[(sg, si)]
        if got["pix"][k] != r[0]:
            bad.append("frame %d: pixel record differs" % pos)
        if got["anchor"][k] != r[1]:
            bad.append("frame %d: anchor differs" % pos)
    if len(got["keys"]) != len({si & 0xFFFF for _, _, _, si, _ in sh}):
        bad.append("%d records, shipped %d" % (len(got["keys"]), len({si & 0xFFFF for _, _, _, si, _ in sh})))
    return bad


def shipped_reskin_table(cs, src):
    rec = cs.get(os.path.basename(src["cs_rel"]).lower(), {}).get(src["cs_key"])
    return rec


def plain_art(art):
    return {k: v for k, v in (art or {}).items() if k not in ("png_dir", "recipe")}


def run(a):
    stock = N.Stock(a.stock)
    dat, korea, cs = load_overlay(a.overlay)
    names = a.packages or sorted(d for d in os.listdir(a.examples)
                                 if os.path.isfile(os.path.join(a.examples, d, "manifest.json")))
    summary = {}
    for name in names:
        pack_dir = os.path.join(a.examples, name)
        man = N.load_manifest(pack_dir)
        items = [("variant", v["id"], v["base"], v) for v in man.get("variants", [])] + \
                [("reskin", r["piece"], r["piece"], r) for r in man.get("reskins", [])]
        if not items:
            continue
        present = [it for it in items if (it[0] == "variant" and it[1] in korea) or it[0] == "reskin"]
        if not present:
            continue
        dirs, ps = {}, {"items": 0, "png": 0, "anchors": 0, "split": 0, "tagged": 0, "same_as_source": 0,
                        "recipe": 0, "plain_ok": 0, "missing": [], "errors": []}
        jobs = []
        for kind, piece, default, it in items:
            where = "%s %s %d" % (name, kind, piece)
            art = it.get("art") or {}
            src = N.compile_art(stock, pack_dir, plain_art(art), default, where)
            if kind == "variant":
                table = korea.get(piece)
            else:
                table = shipped_reskin_table(cs, src)
                if table == src["cs"]:
                    table = None                        # the reskin's table is unchanged: package not installed
            if table is None:
                ps["missing"].append(piece)
                continue
            ps["items"] += 1
            if art.get("recipe"):
                ps["recipe"] += 1
                continue
            try:
                files, st = recover_art(src, table, piece, dat, where)
            except RecoverError as e:
                ps["errors"].append(str(e))
                continue
            if not art.get("png_dir"):
                if files:
                    ps["errors"].append("%s: no png_dir in the manifest but %d frame(s) differ from the source"
                                        % (where, len(files)))
                else:
                    ps["plain_ok"] += 1
                continue
            if not files:
                ps["same_as_source"] += 1
            for k in ("png", "anchors", "split", "tagged"):
                ps[k] += st[k]
            d = dirs.setdefault(art["png_dir"], {})
            for fn, val in files.items():
                if fn in d and d[fn] != val:
                    ps["errors"].append("%s: png_dir %s/%s is claimed with other content by another item"
                                        % (where, art["png_dir"], fn))
                d[fn] = val
            jobs.append((kind, piece, default, art, table, where))
        if a.write and not ps["errors"]:
            for rel, files in sorted(dirs.items()):
                d = os.path.join(pack_dir, rel)
                if os.path.isdir(d) and os.listdir(d):
                    raise RecoverError("%s exists and is not empty; refusing to overwrite" % d)
                os.makedirs(d, exist_ok=True)
                for fn, (data, _) in sorted(files.items()):
                    with open(os.path.join(d, fn), "wb") as fh:
                        fh.write(data)
                anc = {fn: v for fn, (_, v) in sorted(files.items()) if v is not None}
                if anc:
                    with open(os.path.join(d, N.ANCHOR_FILE), "w", encoding="utf-8", newline="\n") as fh:
                        json.dump(dict({"_": "recovered by netpack_recover.py from the installed overlay"}, **anc),
                                  fh, indent=1)
                        fh.write("\n")
            for kind, piece, default, art, table, where in jobs:
                bad = check_art(stock, pack_dir, art, default, table, piece, dat, where)
                if bad:
                    ps["errors"].append("%s: check after write: %s" % (where, "; ".join(bad[:4])))
            ps["checked"] = len(jobs)
        ps["png_dirs"] = len(dirs)
        summary[name] = ps
        print("%-28s items %3d  png_dirs %3d  png %5d  anchors %4d  split %3d (tagged %d)  unchanged %d  recipe %d  "
              "plain %d  missing %s  errors %d%s" % (name, ps["items"], ps["png_dirs"], ps["png"], ps["anchors"],
                                                    ps["split"], ps["tagged"], ps["same_as_source"], ps["recipe"],
                                                    ps["plain_ok"], ps["missing"] or "-", len(ps["errors"]),
                                                    ("  checked %d" % ps["checked"]) if "checked" in ps else ""),
              flush=True)
        for e in ps["errors"][:6]:
            print("    ERROR " + e)
    if a.json:
        with open(a.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(summary, fh, indent=1, sort_keys=True)
    return 1 if any(s["errors"] for s in summary.values()) else 0


def compare(a):
    """merge the named packages from their folders exactly as install does and diff every output with the shipped
    overlay + tables (byte for byte; a file on one side only counts as a difference)"""
    import hashlib
    stock = N.Stock(a.stock)
    packs = [(os.path.join(a.examples, n), N.load_manifest(os.path.join(a.examples, n))) for n in a.packages]
    for _, m in packs:
        N.check_anchors(stock, m)
    files, tables, report = N.merge(stock, packs)
    got = {"overlay/" + rel: data for rel, data in files.items()}
    got.update({"tables/%s.txt" % n: b for n, b in tables.items()})
    got.update({"cross/%s.txt" % n: b for n, b in report.get("cross", {}).items()})
    want = {}
    base = os.path.dirname(os.path.abspath(a.overlay))
    for sub in ("overlay", "tables", "cross"):
        for dp, _, fns in os.walk(os.path.join(base, sub)):
            for fn in fns:
                p = os.path.join(dp, fn)
                want[N.norm(os.path.relpath(p, base))] = N.rd(p)
    lw = {k.lower(): k for k in want}
    rows, same = [], 0
    for rel in sorted(set(k.lower() for k in got) | set(lw)):
        g = next((got[k] for k in got if k.lower() == rel), None)
        w = want.get(lw.get(rel))
        st = "IDENTICAL" if g == w else ("ONLY_REBUILT" if w is None else "ONLY_SHIPPED" if g is None else "DIFFERS")
        same += st == "IDENTICAL"
        rows.append((lw.get(rel, rel), st, len(g) if g is not None else -1, len(w) if w is not None else -1,
                     hashlib.sha256(g).hexdigest()[:16] if g is not None else "-"))
    for i, (rel, st, lg, lw_, h) in enumerate(rows):
        print("[%d/%d] %s %s (rebuilt %d, shipped %d, sha %s)" % (i + 1, len(rows), rel, st, lg, lw_, h))
    print("%d of %d files identical" % (same, len(rows)))
    for w in report["warnings"][:5]:
        print("  WARNING " + w)
    if a.json:
        with open(a.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump([dict(zip(("file", "status", "rebuilt_bytes", "shipped_bytes", "sha256_16"), r)) for r in rows],
                      fh, indent=1)
    return 0 if same == len(rows) else 1


def main(argv):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--overlay", required=True, help="installed overlay root (<tree>\\mods\\netmod\\overlay)")
    p.add_argument("--stock", required=True, help="game root with the stock files the packages were built against")
    p.add_argument("--examples", default=os.path.join(HERE, "examples"))
    p.add_argument("--write", action="store_true", help="write the png_dirs (refuses a non-empty one) and check them")
    p.add_argument("--json", help="summary as JSON")
    p.add_argument("--compare", action="store_true", help="merge the packages and diff with the shipped overlay + "
                   "tables next to --overlay (no writes)")
    p.add_argument("packages", nargs="*")
    a = p.parse_args(argv)
    try:
        return compare(a) if a.compare else run(a)
    except (RecoverError, N.NetpackError) as e:
        print("netpack_recover: " + str(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
