"""Verify that the city view's tool delegate forwards keys back to the city view itself.

The claim under test, from `SIMRCI FUN_1003f308` (the delegate's `vt+0x18`, OnKeyDown, 19 bytes):

    void FUN_1003f308(void *this, uint vk, uint mods) {
        (**(code **)(**(int **)(this + 8) + 100))(vk, mods);   // 100 = 0x64
    }

i.e. it forwards to `(delegate+8)->vt+0x64`. If `delegate+8` is the city-view OUTER object, then
`vt+0x64` is `SIMSPR FUN_1004979a` - the arrow-scroll handler - and the delegate adds no bindings
of its own. That is the last open question in verify/offscreen/KEY_BINDINGS_RUNTIME.md.

⚠️ WHY THIS TOOL EXISTS RATHER THAN A ONE-LINER. `winmgr+0x2c` is whatever window has ENGINE focus
*right now*, and it changes on almost any click. The field at `+0x224` is only meaningful for the
city-view class, so reading it off an arbitrary focus window returns garbage - a previous attempt
read `0x12` and briefly looked like a real delegate pointer. So:

  * every read is GUARDED on the focus window's vtable being the city view's, and
  * the probe runs at load, BEFORE any click, because focus is the city view then and the delegate
    is already installed. Clicking a tool button both moves focus and clears the delegate.

There is also a second, click-free confirmation path: hook `SIMSPR FUN_10048a2d` (the sole writer of
the field) and compare `delegate+8` against the `this` it was installed on. That needs no focus
assumption at all, and is used as the cross-check.

    python re/tools/tool_delegate_probe.py [--watch SECONDS]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import frida

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402

CITY_VIEW_VTABLE_RVA = 0x100676AC     # SIMSPR; the class that owns the +0x224 delegate field

JS = r"""
var CITY_VT_RVA = 0x676ac;            /* offset form of SIMSPR RVA 0x100676ac */
var installs = [];

function mods(){ return Process.enumerateModules(); }
function mb(w){ var m=mods();
  for (var i=0;i<m.length;i++) if (m[i].name.toLowerCase()===w.toLowerCase()) return m[i].base;
  return null; }
function rp(p,o){ return p.add(o).readPointer(); }
function whereis(p){ var m=mods();
  for (var i=0;i<m.length;i++){ var b=m[i].base, e=b.add(m[i].size);
    if (p.compare(b)>=0 && p.compare(e)<0)
      return m[i].name+" RVA 0x1"+("0000000"+p.sub(b).toString(16)).slice(-7); }
  return p.toString(); }
function sink(){ var gz=mb("GZGraphicD.dll"); return rp(rp(gz.add(0x6cdb8),0),0x30); }

var simspr = mb("SIMSPR.DLL");
var cityVt = simspr.add(CITY_VT_RVA);

/* Cross-check that needs no focus: watch the sole writer of the delegate field. `this` is the
   city-view OUTER object, and the field is at outer+0x228 == subobject+0x224. */
Interceptor.attach(simspr.add(0x48a2d), {
  onEnter: function (a) { this.outer = a[0]; },
  onLeave: function () {
    try {
      var d = rp(this.outer, 0x228);
      if (d.isNull()) return;
      var inner = rp(d, 8);
      installs.push({
        outer: this.outer.toString(),
        delegate: d.toString(),
        delegate_vtable: whereis(rp(d, 0)),
        vt18: whereis(rp(rp(d, 0), 0x18)),
        inner: inner.toString(),
        inner_is_this_outer: inner.equals(this.outer),
        inner_vt64: whereis(rp(rp(inner, 0), 0x64))
      });
      if (installs.length > 24) installs.shift();
    } catch (e) { /* mid-update state; ignore */ }
  }
});

rpc.exports = {
  /* GUARDED read of the focus window. Refuses unless the focus window IS the city view. */
  focus: function () {
    var f = rp(sink(), 0x2c);
    if (f.isNull()) return { ok:false, why:"engine focus is NULL" };
    var vt = rp(f, 0);
    var out = { focus: f.toString(), focus_vtable: whereis(vt) };
    if (!vt.equals(cityVt)) {
      out.ok = false;
      out.why = "focus window is NOT the city view - refusing to read +0x224 off it "
              + "(that is how a bogus 0x12 'delegate' was produced before)";
      return out;
    }
    out.ok = true;
    var outer = f.sub(4);
    out.outer = outer.toString();
    out.outer_vt64 = whereis(rp(rp(outer, 0), 0x64));
    var d = rp(f, 0x224);
    out.delegate = d.isNull() ? "NULL" : d.toString();
    if (d.isNull()) { out.verdict = "no delegate installed right now"; return out; }
    out.delegate_vtable = whereis(rp(d, 0));
    out.delegate_vt18_OnKeyDown = whereis(rp(rp(d, 0), 0x18));
    out.delegate_vt1c_OnKeyUp   = whereis(rp(rp(d, 0), 0x1c));
    var inner = rp(d, 8);
    out.delegate_plus8 = inner.toString();
    out.delegate_plus8_IS_cityview_outer = inner.equals(outer);
    out.delegate_plus8_vt64 = whereis(rp(rp(inner, 0), 0x64));
    return out;
  },
  installs: function () { var i = installs; installs = []; return i; }
};
"""


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--watch", type=float, default=0.0,
                    help="also watch the writer for N seconds and report installs")
    a = ap.parse_args(argv)

    try:
        pid = sc3io.game_pid()
    except sc3io.CaptureError as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 2

    sess = frida.attach(pid)
    sc = sess.create_script(JS)
    sc.load()

    print("=== guarded read of the engine focus window ===")
    r = sc.exports_sync.focus()
    print(json.dumps(r, indent=2))

    verdict = None
    if r.get("ok") and r.get("delegate") not in (None, "NULL"):
        same = r.get("delegate_plus8_IS_cityview_outer")
        print(f"\n>>> delegate+8 IS the city-view outer object: {same}")
        print(f">>> delegate+8 -> vt+0x64 = {r.get('delegate_plus8_vt64')}")
        print(f">>> city view    vt+0x64 = {r.get('outer_vt64')}")
        verdict = bool(same) and r.get("delegate_plus8_vt64") == r.get("outer_vt64")
        print(f">>> PASS - the delegate is a pass-through to the city view's own key handler"
              if verdict else ">>> the delegate does NOT forward to the city view")

    if a.watch > 0:
        print(f"\n=== watching the writer (SIMSPR FUN_10048a2d) for {a.watch}s ===")
        time.sleep(a.watch)
        ins = sc.exports_sync.installs()
        if not ins:
            print("  no installs observed (nothing changed the tool delegate)")
        for i in ins:
            print(f"  install: delegate={i['delegate']} vt18={i['vt18']}")
            print(f"           delegate+8={i['inner']} is-the-outer-it-was-installed-on="
                  f"{i['inner_is_this_outer']}  vt+0x64={i['inner_vt64']}")

    sess.detach()
    if verdict is None:
        return 3
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
