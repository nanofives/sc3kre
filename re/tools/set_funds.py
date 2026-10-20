#!/usr/bin/env python3
r"""set_funds.py - set the running city's funds (test-city tooling, 2026-10-08).

Finds the cSC3BudgetLayer object (vtable SIMMISC .rdata 0x1003c550, GZCOM_INTERFACE_CATALOGUE.md section 11d) by
scanning writable memory for that vtable pointer, then writes the int64 total funds at +0x38 and its mirror at
+0x40 - the two fields SetTotalFunds (slot 3, 0x100051ed) writes. Read-modify of nothing else.

Usage: python set_funds.py <amount>        (needs a running SC3U.exe with a city loaded)
"""
import sys
import frida

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import sc3io
import sc3pause  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)

JS = r"""
var m = Process.getModuleByName('SIMMISC.DLL');
var vt = m.base.add(0x3c550);
var pat = [0, 1, 2, 3].map(function (i) { return ('0' + vt.shr(i * 8).and(0xff).toString(16)).slice(-2); }).join(' ');
var hits = [];
Process.enumerateRanges({ protection: 'rw-', coalesce: true }).forEach(function (r) {
  if (r.size > 512 * 1024 * 1024) return;
  try { Memory.scanSync(r.base, r.size, pat).forEach(function (h) { hits.push(h.address); }); } catch (e) {}
});
rpc.exports = {
  find: function () { return hits.map(function (a) { return [a.toString(), a.add(0x38).readS64().toString()]; }); },
  set: function (amount) {
    hits.forEach(function (a) { a.add(0x38).writeS64(int64(amount)); a.add(0x40).writeS64(int64(amount)); });
    return hits.length;
  }
};
"""


def main():
    amount = sys.argv[1]
    sc3pause.require_running(sc3io.game_pid(), "set_funds")
    s = frida.attach(sc3io.game_pid())
    sc = s.create_script(JS)
    sc.load()
    found = sc.exports_sync.find()
    print("budget layer objects:", found)
    if amount == "check":
        pass
    elif len(found) != 1:
        print("expected exactly one budget layer - not writing")
    else:
        sc.exports_sync.set(amount)
        print("funds set to", amount, "->", sc.exports_sync.find())
    s.detach()


if __name__ == "__main__":
    main()
