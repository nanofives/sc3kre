r"""stylemix_build.py - writes the style_mix netpack package (task stylemix, 2026-11-10).

The package makes the two stock building sets grow next to the base North American style, at random, in one city.
Everything it adds is computed at install time by netpack from the set archives of the tree it is installed into
(netpack_stylesets.py), so the manifest is all there is and no game art is stored in the package.

  py -3.12 re/tools/netmod/stylemix_build.py [--euro 1] [--asian 1] [--out <dir>]

--euro / --asian are integer multipliers on each copied member's stock weight. The base style keeps its stock
weights (the stock lines are never edited, so other packages' line inserts keep working), so 1 / 1 is an equal
three-way mix for buildings both sets re-skin, and 2 / 2 makes each set style twice as likely as the base.
"""
import argparse
import json
import os

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples", "style_mix")
EURO, ASIAN = "e523f3fb", "6523f3d5"      # set names from SC3MBEStringsBuildings.IXF (verify/stylemix/RESULTS.md)


def manifest(euro=1, asian=1):
    return {
        "netpack": 1,
        "name": "style_mix",
        "version": "1.0.0",
        "author": "sc3kre",
        "description": "All three building styles grow side by side at random: every European (set e523f3fb) and "
                       "Asian (set 6523f3d5) building that re-skins a zoned building is added as a NEW building "
                       "(id + 400000 / id + 1500000) next to the North American one, so nothing stock is replaced. "
                       "Keep the in-game building style at the default.",
        "style_sets": [
            {"set": EURO, "offset": 400000, "weight": euro},
            {"set": ASIAN, "offset": 1500000, "weight": asian},
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--euro", type=int, default=1)
    ap.add_argument("--asian", type=int, default=1)
    ap.add_argument("--out", default=HERE)
    a = ap.parse_args(argv)
    if a.euro < 1 or a.asian < 1:
        ap.error("weights are positive integers")
    os.makedirs(a.out, exist_ok=True)
    p = os.path.join(a.out, "manifest.json")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest(a.euro, a.asian), f, indent=2)
        f.write("\n")
    print("wrote " + p)


if __name__ == "__main__":
    main()
