#!/usr/bin/env python3
r"""sim_status.py - read the running city's pause counter, clock pause count and funds (2026-10-08).

city = *(*(SC3U 0x004fa86c) + 0x48) (vtable SIMCITY 0x10013260, also the sim coordinator).
city+0x140 = user-pause depth (each 0xc2a35d80 message releases one level, sc3simrun RESUME),
city+0x144 = camera/UI hold, city+0x148 = periodic bracket (SIM_WHILE_SCROLLING.md).
Usage: python sim_status.py
"""
import os
import sys

import frida

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sc3io

JS = r"""
var exe = Process.getModuleByName('SC3U.exe').base;
var app = exe.add(0x4fa86c - 0x400000).readPointer();
var c = app.add(0x48).readPointer();
var bud = new NativeFunction(c.readPointer().add(0x15c).readPointer(), 'pointer', ['pointer'], 'thiscall')(c);
send({pause: c.add(0x140).readU32(), hold: c.add(0x144).readU32(), bracket: c.add(0x148).readU32(),
      funds: bud.add(0x38).readS64().toString()});
"""

s = frida.attach(sc3io.game_pid())
sc = s.create_script(JS)
out = []
sc.on("message", lambda m, d: out.append(m.get("payload")))
sc.load()
s.detach()
print(out[0] if out else "no reply")
