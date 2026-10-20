#!/usr/bin/env python3
r"""hwcars_mode.py - switch sc3cartrips live: 1 capture only (stock random cars), 2 replace (route cars only),
3 filler (route cars + stock cars up to the stock count). Calls the DLL's export sc3cartrips_mode (sc3cartrips_cars.c).

  py -3.12 hwcars_mode.py 1|2|3        SC3_PID = the game; prints the previous mode
"""
import os, sys
import frida
import os as _os  # noqa: E402
sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import sc3pause  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)

sc3pause.require_running(int(os.environ["SC3_PID"]), "hwcars_mode")
s = frida.attach(int(os.environ["SC3_PID"]))
sc = s.create_script("""
var f = new NativeFunction(Process.getModuleByName('sc3cartrips.dll').getExportByName('sc3cartrips_mode'), 'int', ['int'], 'mscdecl');
rpc.exports = { set: function (m) { return f(m); } };
""")
sc.load()
print("previous mode", sc.exports_sync.set(int(sys.argv[1])), "-> now", sys.argv[1])
s.detach()
