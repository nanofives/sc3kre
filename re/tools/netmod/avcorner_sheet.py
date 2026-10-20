#!/usr/bin/env python3
r"""avcorner_sheet.py - owner sheet for the one-way avenue corner (task avcore, 2026-10-19).

Left: the lane diagram of one stock corner pattern (the band's last row, the 2 x 2 block, the other band's first row),
drawn from the compiled lane records (each lane's own curve points, arrow at its end). Right: an in-game shot.

  py -3.12 -m netmod.avcorner_sheet SHOT.png OUT.png        (run from re/tools)
"""
import math
import sys
from PIL import Image, ImageDraw, ImageFont

from netmod import avlanes as A, lanekit as LK, hwlanes as HL

C = 150          # pixels per cell


def main(argv):
    shot, out = argv[1], argv[2]
    game = LK.Game()
    sp = A.specs(game)
    for v in sp.values():
        HL.inject(game, v)
    P = game.paths("ENGLISH")
    pieces = {"S": sp[A.PIECE_STRAIGHT], "U": sp[A.PIECE_UTURN], "K": sp[A.PIECE_CORNER]}
    key = (0, 1, 1)                                   # band along z, forward (S) end, inner bend on the x+ column
    g = A.corner_grid(*key)
    xs, zs = [c[0] for c in g], [c[1] for c in g]
    x0, z0 = min(xs) - 1, min(zs) - 1
    W, H = (max(xs) - x0 + 2) * C, (max(zs) - z0 + 2) * C
    img = Image.new("RGB", (W, H + 60), (236, 236, 228))
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    names = {"S": "21700", "U": "21701", "K": "21726"}
    for (x, z), (role, st) in g.items():
        px, pz = (x - x0) * C, (z - z0) * C
        d.rectangle([px, pz, px + C, pz + C], fill=(120, 120, 120) if role == "S" else (95, 95, 120), outline=(60, 60, 60))
        d.text((px + 6, pz + 6), "%s.%d" % (names[role], st), fill=(255, 255, 255), font=font)
        rec = A._records(pieces[role], st, game, "ENGLISH")
        for n in rec["veh"]:
            for e in n["edges"]:
                if e["to"] is None or not e.get("path") or e["path"] not in P.veh:
                    continue
                pts = [(px + q[0] * C / 255.0, pz + q[2] * C / 255.0) for q in P.veh[e["path"]]["pts"]]
                col = (250, 250, 250)
                d.line(pts, fill=col, width=3)
                (ax, az), (bx, bz) = pts[-2], pts[-1]
                ang = math.atan2(bz - az, bx - ax)
                for s in (2.6, -2.6):
                    d.line([(bx, bz), (bx - 12 * math.cos(ang + s / 2), bz - 12 * math.sin(ang + s / 2))], fill=col, width=3)
    d.text((10, H + 8), "One-way avenue corner, lanes as compiled (ENGLISH). Inner bend 21726 (right turn: median lane on the"
           " wide arc), outer bend 21701", fill=(20, 20, 20), font=font)
    d.text((10, H + 26), "(the U-turn piece, left turn), the two halves 21700. Both bands convert together or stay stock.",
           fill=(20, 20, 20), font=font)
    s = Image.open(shot).convert("RGB")
    s = s.resize((int(s.width * (H + 60) / s.height), H + 60))
    sheet = Image.new("RGB", (img.width + s.width + 10, H + 60), (255, 255, 255))
    sheet.paste(img, (0, 0))
    sheet.paste(s, (img.width + 10, 0))
    sheet.save(out)
    print("wrote", out)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
