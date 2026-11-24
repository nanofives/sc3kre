#!/usr/bin/env python3
r"""pw1024_lab.py - build a long power line or pipe in YOUR running game (round pw1024, 2026-11-23). sc3io + Frida.

Uses nb_drive.py's game-thread job runner and its build() (SIMNTWRK FUN_10014a23 = manager vt+0xf0), with the
manager pointer given explicitly, so the underground (pipe) manager captured from one posted pipe-tool drag
(`nb_drive.py capture`) can build too.

  py pw1024_lab.py build MGR NETTYPE X0,Z0 X1,Z1 [--chunk 200]   # straight line, built in chunks
  py pw1024_lab.py layers                                        # power / plumbing layer objects (city vt+0x150/0x154)

SC3_PID must be set (nb_drive refuses to guess).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "netmod"))
sys.path.insert(0, HERE)
import nb_drive  # noqa: E402

EXTRA = r"""
function layers() {
  var c = city(), out = {};
  [['power', 0x150], ['plumbing', 0x154]].forEach(function (p) {
    var o = vfn(c, p[1], 'pointer', [])(c);
    out[p[0]] = {obj: '' + o, vt: modname(o.readPointer())};
  });
  out.cells = [vfn(c, 0xcc, 'uint32', [])(c), vfn(c, 0xd0, 'uint32', [])(c)];
  return out;
}
"""


def session():
    js = nb_drive.JS.replace("rpc.exports = {",
                             EXTRA + "rpc.exports = {\n  setmgr: function (p) { MGR = ptr(p); return '' + MGR; },\n"
                             "  layers: function () { return layers(); },")
    nb_drive.JS = js
    return nb_drive.Session()


def main(argv):
    if not os.environ.get("SC3_PID", "").strip().isdigit():
        raise SystemExit("set SC3_PID")
    if argv[1] == "layers":
        s = session()
        print(json.dumps(s.sc.exports_sync.layers()))
        s.close()
        return 0
    if argv[1] == "build":
        mgr, net = argv[2], int(argv[3])
        cells = nb_drive.line(nb_drive.xy(argv[4]), nb_drive.xy(argv[5]))
        chunk = int(argv[argv.index("--chunk") + 1]) if "--chunk" in argv else 200
        s = session()
        if mgr == "surface":
            s.job({"kind": "post4", "w": [0x637C0DAB, 0, 0, 0]})
        else:
            s.sc.exports_sync.setmgr(mgr)
        for k in range(0, len(cells), chunk):
            part = cells[k:k + chunk + 1]
            r = s.job(timeout=300, j={"kind": "build", "net": net, "cost": 10 * len(part),
                                      "cells": [[x, z, 0] for x, z in part], "trace": []})
            print(json.dumps({"from": part[0], "to": part[-1], "r": r}), flush=True)
        s.close()
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
