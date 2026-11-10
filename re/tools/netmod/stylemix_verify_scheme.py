r"""Read the live building set of a running SC3 (task stylemix), ReadProcessMemory only.
app = *(SC3U 0x004fa86c) (sc3pause.py); scheme mgr = *(app + 0x108) (cSC3App::CitySchemeManager 0x004063cf:
mov eax,[ecx+0xd8], ecx = cISC3App subobject app+0x30; vtable checked = SIMINIT+0x2f528); +0x50 = current building set id, +0x58 = set archives loaded (SIMINIT SetCityScheme
0x10006589 / FUN_1000641b, BUILDING_PICK.md 3).  py -3.12 stylemix_verify_scheme.py <pid>"""
import os
import sys, ctypes
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sc3pause as P
pid = int(sys.argv[1])
h = P._k32.OpenProcess(0x0410, False, pid)
mods = P._modules(h)
exe, siminit = mods["sc3u.exe"], mods.get("siminit.dll")
app = P._u32(h, exe + (0x004fa86c - 0x00400000))
mgr = P._u32(h, app + 0x108)   # [ecx+0xd8] with ecx = the cISC3App subobject at app+0x30 (found by vtable scan)
vals = [P._u32(h, mgr + o) for o in range(0x40, 0x60, 4)]
vt = P._u32(h, mgr)
print("app 0x%08x mgr 0x%08x vtable 0x%08x = SIMINIT+0x%x (expected +0x2f528, cISC3CitySchemeMgr)" % (app, mgr, vt, vt - siminit))
print("mgr+0x40..0x5c:", " ".join("%08x" % v for v in vals))
print("building set (+0x50) = 0x%08x, loaded flag (+0x58) byte = %d" % (P._u32(h, mgr + 0x50), P._u32(h, mgr + 0x58) & 0xff))
