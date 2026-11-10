#!/usr/bin/env python3
r"""batslots_lab.py - task batslots (2026-11-10): drive the game's own BAT replacement path, read it back from saves.

Game side (Frida, on the game thread through a DispatchMessageA hook, the zonedemo_probe.py pattern). SC3_PID = the game.
  scheme manager = [app + 0x108]  (CodeView cSC3App::mpCitySchemeMgr; app = [SC3U 0x4fa86c], whose +0x48 is mpCity)
  vt+0xa8 MakeBATReplacement(const cGZResourceKey& building, const cGZResourceKey& bat)   SIMINIT 0x10005b95
  the replacement map sits at +0x8c, its node count at +0x90 (SaveBATReplacementSet SIMINIT 0x10006328 writes it)

  py -3.12 re/tools/batslots_lab.py bats                       BAT buildings in Apps\BARender\BAT.DAT (offline)
  py -3.12 re/tools/batslots_lab.py state                      replacement count + every (building, bat) pair
  py -3.12 re/tools/batslots_lab.py replace <id> <bat-inst>    MakeBATReplacement({0x207EDC0E,0x57E,id}, {0x856CD19A,0xBA1DBF1E,inst})
  py -3.12 re/tools/batslots_lab.py clear <id>                 vt+0xa4 MakeBATReplacement(key, NULL): back to the stock art
  py -3.12 re/tools/batslots_lab.py save <file.sc3> [ids...]   the saved replacement record + occupant counts per id (offline)

The calls go through the scheme manager slot itself, so the same code runs as when the Building Replacement window
commits (that window uses the vt+0xa4 overload with the override object, SIMUI 0x1001b38d; vt+0xa8 fetches the
override by key and calls vt+0xa4, SIMINIT 0x10005b95).
"""
import collections
import ctypes
import glob
import json
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

WM_PROBE = 0x8000 + 0x5CB
BLD = (0x207EDC0E, 0x57E)
BAT_TYPE, BAT_GROUP = 0x856CD19A, 0xBA1DBF1E           # override records in Apps\BARender\BAT.DAT
SAVE_KEY = (0x99F47014, 0x79F4702D, 0)                 # LoadBATReplacementSet SIMINIT 0x100059d7

JS = r"""
var exe = Process.getModuleByName('SC3U.exe').base;
var siminit = Process.getModuleByName('SIMINIT.DLL').base;
var jobs = [], results = [];
function scheme() {
  var app = exe.add(0x4fa86c - 0x400000).readPointer();
  var s = app.add(0x108).readPointer();
  if (!s.readPointer().equals(siminit.add(0x2f528))) throw new Error('scheme vtable ' + s.readPointer());
  return s;
}
function pairs(s) {
  // std::map header at +0x8c (pointer to the header node), count at +0x90. SGI/STLport node: colour +0, parent +4,
  // left +8, right +0xc, value {key +0x10, key +0x1c} (SIMINIT 0x10005bde writes the pair there). root = header->parent.
  var head = s.add(0x8c).readPointer(), n = s.add(0x90).readU32(), out = [];
  if (n > 10000) throw new Error('map count ' + n);
  function walk(node, depth) {
    if (node.isNull() || node.equals(head) || depth > 64) return;
    walk(node.add(8).readPointer(), depth + 1);
    var k = [], b = [];
    for (var i = 0; i < 3; i++) { k.push(node.add(0x10 + 4 * i).readU32()); b.push(node.add(0x1c + 4 * i).readU32()); }
    out.push({building: k, bat: b});
    walk(node.add(0xc).readPointer(), depth + 1);
  }
  walk(head.add(4).readPointer(), 0);
  return {count: n, pairs: out};
}
function job(j) {
  var s = scheme();
  if (j.kind === 'state') return pairs(s);
  if (j.kind === 'replace') {
    var a = Memory.alloc(12), b = Memory.alloc(12);
    [0x207EDC0E, 0x57E, j.id].forEach(function (v, i) { a.add(4 * i).writeU32(v); });
    [0x856CD19A, 0xBA1DBF1E, j.bat].forEach(function (v, i) { b.add(4 * i).writeU32(v >>> 0); });
    var f = s.readPointer().add(0xa8).readPointer();
    var r = new NativeFunction(f, 'uint8', ['pointer', 'pointer', 'pointer'], 'thiscall',
                               {exceptions: 'propagate'})(s, a, b);
    var m = Process.findModuleByAddress(f);
    return {ok: r, slot: m ? m.name + '+0x' + f.sub(m.base).toString(16) : '' + f, after: pairs(s)};
  }
  if (j.kind === 'clear') {           // vt+0xa4 MakeBATReplacement(key, NULL): what the window commits after Revert
    var a = Memory.alloc(12);
    [0x207EDC0E, 0x57E, j.id].forEach(function (v, i) { a.add(4 * i).writeU32(v); });
    var f = s.readPointer().add(0xa4).readPointer();
    var r = new NativeFunction(f, 'uint8', ['pointer', 'pointer', 'pointer'], 'thiscall',
                               {exceptions: 'propagate'})(s, a, ptr(0));
    return {ok: r, after: pairs(s)};
  }
  throw new Error('kind ' + j.kind);
}
Interceptor.attach(Process.getModuleByName('USER32.dll').getExportByName('DispatchMessageA'), {
  onEnter: function (args) {
    if (args[0].add(4).readU32() !== %WM% || jobs.length === 0) return;
    var j = jobs.shift();
    try { results.push(job(j)); } catch (e) { results.push({error: '' + e}); }
  }
});
rpc.exports = {
  queue: function (j) { jobs.push(j); return jobs.length; },
  results: function () { var r = results; results = []; return r; }
};
""".replace("%WM%", str(WM_PROBE))


def run(job):
    import frida
    import sc3io
    import sc3pause
    pid = sc3io.game_pid()
    sc3pause.require_running(pid, "batslots_lab")
    s = frida.attach(pid)
    sc = s.create_script(JS)
    sc.load()
    sc.exports_sync.queue(job)
    hwnd = sc3io.game_hwnd(pid)
    res = []
    for i in range(400):
        if i % 10 == 0:
            ctypes.windll.user32.PostMessageA(hwnd, WM_PROBE, 0, 0)
        time.sleep(0.05)
        res += sc.exports_sync.results()
        if res:
            break
    s.detach()
    return res[0] if res else {"error": "the game did not dispatch the message"}


def bats(root):
    import ixf_parse
    recs, d = ixf_parse.parse(os.path.join(root, "Apps", "BARender", "BAT.DAT"))
    out = []
    for r in recs:
        if r["type"] != BAT_TYPE:
            continue
        p = d[r["offset"]:r["offset"] + r["size"]]
        size = p[0]                                        # GetLotSize (override vt+0x2c, read as a byte)
        o = 1 + 12                                         # + sprite attrib key {0x6300, 0xBA1DBF1E, inst}
        n = struct.unpack_from("<I", p, o)[0]
        name = p[o + 4:o + 4 + n].decode("cp1252")
        o += 4 + n
        n = struct.unpack_from("<I", p, o)[0]
        arch = p[o + 4:o + 4 + n].decode("cp1252")
        out.append((r["instance"], size, name, arch))
    return out


def save_report(path, ids):
    import occupant_layer
    import ixf_parse
    c, s0, s1, cnt, ver, recs = occupant_layer.parse(path)
    out = {"file": os.path.basename(path), "occupants_total": len(recs), "replacement_set": None}
    # The set is a record of the .sc3 container itself (not of the city blob): {0x99F47014, 0x79F4702D, 0} =
    # 12-byte zero key, u32 count, then count x (building key, BAT key), 3 x u32 each (SIMINIT 0x10006328 writes it,
    # 0x100059d7 reads it). The shipped cities carry the 16-byte empty form.
    crecs, d = ixf_parse.parse(path)
    for r in crecs:
        if (r["type"], r["group"], r["instance"]) == SAVE_KEY:
            p = d[r["offset"]:r["offset"] + r["size"]]
            n = struct.unpack_from("<I", p, 12)[0]
            pairs = [(struct.unpack_from("<3I", p, 16 + 24 * k), struct.unpack_from("<3I", p, 28 + 24 * k))
                     for k in range(n)]
            out["replacement_set"] = {"bytes": len(p), "count": n,
                                      "pairs": [["%08x:%x:%d" % a, "%08x:%08x:%08x" % b] for a, b in pairs]}
    by = collections.Counter(x["key"][2] for x in recs if tuple(x["key"][:2]) == BLD)
    out["occupants"] = {str(i): by.get(i, 0) for i in ids}
    out["cells"] = {str(i): [(x["a"], x["b"]) for x in recs if tuple(x["key"][:2]) == BLD and x["key"][2] == i][:40]
                    for i in ids if i >= 36000}
    out["t18"] = {}
    for i in ids:                                         # LandUse of the id's family, for the stock-still-grows check
        lus = collections.Counter(x["t18"] for x in recs if tuple(x["key"][:2]) == BLD and x["key"][2] == i)
        if lus:
            out["t18"][str(i)] = dict(lus)
    out["by_t18"] = {str(k): v for k, v in sorted(collections.Counter(x["t18"] for x in recs).items())
                     if 3000 <= k < 10000}
    return out


def main(a):
    if len(a) < 2:
        print(__doc__)
        return 2
    verb = a[1]
    if verb == "bats":
        root = os.environ.get("SC3_TREE", os.path.join(HERE, "..", ".."))
        for inst, size, name, arch in bats(root):
            print("0x%08x  %dx%d  %-26s %s" % (inst, size, size, name, arch))
        return 0
    if verb == "state":
        print(json.dumps(run({"kind": "state"}), indent=1))
        return 0
    if verb == "replace":
        print(json.dumps(run({"kind": "replace", "id": int(a[2], 0), "bat": int(a[3], 0)}), indent=1))
        return 0
    if verb == "clear":
        print(json.dumps(run({"kind": "clear", "id": int(a[2], 0)}), indent=1))
        return 0
    if verb == "save":
        print(json.dumps(save_report(a[2], [int(x) for x in a[3:]]), indent=1))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
