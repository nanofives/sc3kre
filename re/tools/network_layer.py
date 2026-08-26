#!/usr/bin/env python3
r"""network_layer.py - reader for the SIMNTWRK network layer of a saved SimCity 3000 city.

The auto-tiled road/rail/etc. networks are persisted in GZCOM save group 0x2147c2dd as a
*sparse* list of occupied tiles. This decodes them to per-tile (x, y, z, pieceId, state,
network) so a tiling-rule edit can be scored on the SAVED FILE, camera- and pixel-independent
(the piece id at occupant +8 is the rule-resolved render piece, baked at build time).

Format spec (all little-endian), decoded and validated 2026-08-25:
  group 0x2147c2dd, one IXF record per network keyed by IXF *instance*:
    instance 0 = header : 4x u32 (count_net0, count_net1, count_net2, version=1)   [save FUN_10012dff]
    instance 1 = road   : count0 tile records                                       [save FUN_10012fc3]
    instance 2 = rail   : count1 tile records
    instance 3 = net[2] : count2 tile records (omitted if 0 tiles)
  each section is preceded by the 8-byte SIMCITY object frame (u16 ver, u8 flags, u8 extra,
  u32 0xDEADBEEF); the header/tile bytes follow it.
  tile record = 8 bytes = two u32:
    word0 (occupant +4, coord)  [CONFIRMED @0x1000d44f]:
      x = w0 & 0x7ff ; y = (w0>>11) & 0x7ff ; z = (w0>>22) & 0xff ; flg = (w0>>30) & 3
    word1 (occupant +8, piece)  [CONFIRMED @0x1000d594]:
      pieceId = w1 & 0xffff  (prop 0x6355941d) ; state = w1 >> 16 (orientation/variant bits)
  road vs rail is the IXF instance index only; nothing inside a record distinguishes them.

Validation target: Cities\Farmsville.sc3 (N=192) -> road 2232 tiles (1041x id29 straight,
37x id11203 curve), rail 545 tiles. Cross-checked against Apps\Res\TilingRules\*_Set.txt.

Usage:
  py -3.12 network_layer.py <city.sc3>                 # per-network tile count + piece histogram
  py -3.12 network_layer.py <city.sc3> --tiles [--net road|rail|2]   # per-tile CSV to stdout
  py -3.12 network_layer.py --diff <baseline.sc3> <after.sc3>        # tiles added/removed/changed
"""
import struct
import sys
from collections import Counter

import ixf_parse
import city_parse

NET_GROUP = 0x2147c2dd
NET_NAME = {1: "road", 2: "rail", 3: "net2"}
NAME_NET = {v: k for k, v in NET_NAME.items()}


def _decode_tiles(body, ent):
    """-> list of (x, y, z, flg, pieceId, state) for one network section entry."""
    s = ent["abs"] + ent["frame"]["len"]
    end = ent["abs"] + ent["size"]
    n = (end - s) // 8
    out = []
    for i in range(n):
        w0, w1 = struct.unpack_from("<II", body, s + 8 * i)
        x = w0 & 0x7ff
        y = (w0 >> 11) & 0x7ff
        z = (w0 >> 22) & 0xff
        flg = (w0 >> 30) & 3
        piece = w1 & 0xffff
        state = w1 >> 16
        out.append((x, y, z, flg, piece, state))
    return out


def read_networks(path):
    """-> {instance: [(x,y,z,flg,pieceId,state), ...]} for instances 1/2/3, plus 'header'."""
    records, d = ixf_parse.parse(path)
    nets = {}
    header = None
    for r in records:
        raw = d[r["offset"]:r["offset"] + r["size"]]
        if not city_parse.is_compressed_payload(raw):
            continue
        try:
            body, _ = city_parse.parse_payload(raw)
        except city_parse.CityError:
            continue
        _, ents = city_parse.parse_sections(body)
        got = [e for e in ents if e["group"] == NET_GROUP]
        if not got:
            continue
        for e in got:
            inst = e["instance"]
            if inst == 0:
                s = e["abs"] + (e["frame"]["len"] if e["frame"] else 0)
                header = struct.unpack_from("<4I", body, s)
            elif e["frame"]:
                nets[inst] = _decode_tiles(body, e)
    return nets, header


# 4-neighbour mask, final.txt convention: W=bit0, N=bit1, E=bit2, S=bit3.
# World dirs = SIMNTWRK offset table 0x10032134: 0=(-1,0)W 1=(0,-1)N 2=(+1,0)E 3=(0,+1)S
# (state_facing.py:26). Straight positions: 5 = W+E, 10 = N+S.
_DIRS = [(-1, 0), (0, -1), (1, 0), (0, 1)]
STRAIGHT_MASKS = {5, 10}


def tile_masks(tiles):
    """-> {(x,y): mask} over a road tile set (same-network 4-neighbour occupancy)."""
    occ = {(t[0], t[1]) for t in tiles}
    masks = {}
    for (x, y) in occ:
        m = 0
        for i, (dx, dy) in enumerate(_DIRS):
            if (x + dx, y + dy) in occ:
                m |= (1 << i)
        masks[(x, y)] = m
    return masks


def mask_piece_xtab(tiles):
    """-> {mask: Counter(pieceId)} for a road tile set."""
    masks = tile_masks(tiles)
    piece = {(t[0], t[1]): t[4] for t in tiles}
    xtab = {}
    for xy, m in masks.items():
        xtab.setdefault(m, Counter())[piece[xy]] += 1
    return xtab


def cmd_masks(path, net="road"):
    nets, _ = read_networks(path)
    inst = NAME_NET.get(net, 1)
    tiles = nets.get(inst, [])
    xtab = mask_piece_xtab(tiles)
    print(f"# {path}  [{net}]  mask -> pieceId histogram (straight masks 5,10 flagged)")
    for m in sorted(xtab):
        tag = "  <-- STRAIGHT" if m in STRAIGHT_MASKS else ""
        top = ", ".join(f"{p}x{c}" for p, c in xtab[m].most_common(4))
        print(f"  mask {m:>2} (0b{m:04b}): {top}{tag}")


def _fmt_hist(tiles, top=None):
    h = Counter(t[4] for t in tiles)
    items = sorted(h.items(), key=lambda kv: -kv[1])
    if top:
        items = items[:top]
    return h, items


def cmd_summary(path):
    nets, header = read_networks(path)
    print(f"# {path}")
    print(f"header (count_road, count_rail, count_net2, version) = {header}")
    for inst in sorted(nets):
        tiles = nets[inst]
        name = NET_NAME.get(inst, f"inst{inst}")
        xs = [t[0] for t in tiles]; ys = [t[1] for t in tiles]
        uniq = len({(t[0], t[1]) for t in tiles})
        _, items = _fmt_hist(tiles, top=12)
        print(f"\n== {name} (instance {inst}): {len(tiles)} tiles, "
              f"{uniq} unique (x,y), x[{min(xs)}..{max(xs)}] y[{min(ys)}..{max(ys)}] ==")
        for pid, c in items:
            print(f"   piece {pid:>6} (0x{pid:04x}) : {c}")


def cmd_tiles(path, net=None):
    nets, _ = read_networks(path)
    print("net,x,y,z,pieceId,state")
    for inst in sorted(nets):
        name = NET_NAME.get(inst, f"inst{inst}")
        if net and name != net:
            continue
        for (x, y, z, flg, piece, state) in sorted(nets[inst]):
            print(f"{name},{x},{y},{z},{piece},{state}")


def cmd_diff(base_path, after_path):
    nb, _ = read_networks(base_path)
    na, _ = read_networks(after_path)
    for inst in sorted(set(nb) | set(na)):
        name = NET_NAME.get(inst, f"inst{inst}")
        base = {(t[0], t[1]): t for t in nb.get(inst, [])}
        after = {(t[0], t[1]): t for t in na.get(inst, [])}
        added = sorted(set(after) - set(base))
        removed = sorted(set(base) - set(after))
        changed = sorted(k for k in (set(after) & set(base))
                         if after[k][4] != base[k][4] or after[k][5] != base[k][5])
        if not (added or removed or changed):
            continue
        print(f"\n== {name} (instance {inst}) : +{len(added)} -{len(removed)} ~{len(changed)} ==")
        if added:
            ph = Counter(after[k][4] for k in added)
            print(f"  ADDED tiles piece histogram: {dict(sorted(ph.items()))}")
            # classify each added tile by its 4-neighbour mask over the AFTER road set,
            # so straight-position tiles (mask 5/10) can be checked against their piece
            masks = tile_masks(na.get(inst, []))
            straight = [(k, after[k][4]) for k in added if masks.get(k) in STRAIGHT_MASKS]
            if straight:
                sph = Counter(p for _, p in straight)
                print(f"  ADDED STRAIGHT-mask (5/10) tiles: {len(straight)}, "
                      f"piece histogram {dict(sorted(sph.items()))}")
            for k in added:
                x, y, z, flg, piece, state = after[k]
                m = masks.get(k)
                st = " STRAIGHT" if m in STRAIGHT_MASKS else ""
                print(f"    +({x:>3},{y:>3}) mask {m:>2}{st:9} piece {piece:>6} (0x{piece:04x}) "
                      f"state 0x{state:x} z{z}")
        for k in changed:
            x, y = k
            print(f"    ~({x:>3},{y:>3}) piece {base[k][4]} -> {after[k][4]}")
        if removed:
            print(f"  REMOVED {len(removed)} tiles")


def main(argv):
    if "--diff" in argv:
        i = argv.index("--diff")
        cmd_diff(argv[i + 1], argv[i + 2])
        return 0
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = argv[1]
    if "--tiles" in argv:
        net = argv[argv.index("--net") + 1] if "--net" in argv else None
        cmd_tiles(path, net)
    elif "--masks" in argv:
        net = argv[argv.index("--net") + 1] if "--net" in argv else "road"
        cmd_masks(path, net)
    else:
        cmd_summary(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
