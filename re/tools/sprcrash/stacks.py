import ctypes, ctypes.wintypes as wt, struct, sys
k = ctypes.WinDLL('kernel32', use_last_error=True); psapi = ctypes.WinDLL('psapi')
pid = int(sys.argv[1]); depth = int(sys.argv[2]) if len(sys.argv) > 2 else 0x600
hp = k.OpenProcess(0x1F0FFF, False, pid)
# modules
mods = (ctypes.c_void_p * 1024)(); need = wt.DWORD()
psapi.EnumProcessModulesEx(hp, mods, ctypes.sizeof(mods), ctypes.byref(need), 0x01)
ml = []
class MI(ctypes.Structure): _fields_ = [("base", ctypes.c_void_p), ("size", wt.DWORD), ("ep", ctypes.c_void_p)]
for i in range(need.value // ctypes.sizeof(ctypes.c_void_p)):
    nm = ctypes.create_unicode_buffer(260); psapi.GetModuleBaseNameW(hp, ctypes.c_void_p(mods[i]), nm, 260)
    mi = MI(); psapi.GetModuleInformation(hp, ctypes.c_void_p(mods[i]), ctypes.byref(mi), ctypes.sizeof(mi))
    ml.append((mi.base or 0, mi.size, nm.value))
def sym(a):
    for b, s, n in ml:
        if b <= a < b + s: return "%s+0x%X" % (n, a - b)
    return None
# threads
class TE(ctypes.Structure): _fields_ = [("sz", wt.DWORD), ("u", wt.DWORD), ("tid", wt.DWORD), ("pid", wt.DWORD), ("pri", wt.LONG), ("d", wt.LONG), ("f", wt.DWORD)]
snap = k.CreateToolhelp32Snapshot(4, 0); te = TE(); te.sz = ctypes.sizeof(TE); tids = []
ok = k.Thread32First(snap, ctypes.byref(te))
while ok:
    if te.pid == pid: tids.append(te.tid)
    ok = k.Thread32Next(snap, ctypes.byref(te))
class WOW64_CONTEXT(ctypes.Structure):
    _fields_ = [("ContextFlags", wt.DWORD), ("Dr", wt.DWORD * 6), ("Float", ctypes.c_byte * 112),
                ("SegGs", wt.DWORD), ("SegFs", wt.DWORD), ("SegEs", wt.DWORD), ("SegDs", wt.DWORD),
                ("Edi", wt.DWORD), ("Esi", wt.DWORD), ("Ebx", wt.DWORD), ("Edx", wt.DWORD), ("Ecx", wt.DWORD), ("Eax", wt.DWORD),
                ("Ebp", wt.DWORD), ("Eip", wt.DWORD), ("SegCs", wt.DWORD), ("EFlags", wt.DWORD), ("Esp", wt.DWORD), ("SegSs", wt.DWORD),
                ("Ext", ctypes.c_byte * 512)]
only = [int(x) for x in sys.argv[3:]]
for tid in tids[: (len(tids) if not only else 999)]:
    if only and tids.index(tid) not in only: continue
    ht = k.OpenThread(0x1FFFFF, False, tid)
    k.Wow64SuspendThread(ht)
    c = WOW64_CONTEXT(); c.ContextFlags = 0x10007
    k.Wow64GetThreadContext(ht, ctypes.byref(c))
    buf = (ctypes.c_ubyte * depth)(); rd = ctypes.c_size_t()
    k.ReadProcessMemory(hp, ctypes.c_void_p(c.Esp), buf, depth, ctypes.byref(rd))
    k.ResumeThread(ht); k.CloseHandle(ht)
    print("thread #%d tid %d eip %s esp %08X" % (tids.index(tid), tid, sym(c.Eip) or hex(c.Eip), c.Esp))
    n = 0
    for off in range(0, rd.value - 3, 4):
        v = struct.unpack_from("<I", bytes(buf), off)[0]; s = sym(v)
        if s and not s.startswith(("ntdll", "KERNEL", "win32u", "frida")):
            print("   esp+%03X %s" % (off, s)); n += 1
            if n >= 18: break
