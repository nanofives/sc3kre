"""List every top-level window of the game with class, style and rects.

My WM_NCHITTEST fix verified fine by SendMessage yet the owner still cannot drag - which means the
window I am subclassing and testing is not the frame the user drags. This shows the real hierarchy
so that assumption stops being an assumption.
"""
import ctypes
import subprocess
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

STYLES = [
    (0x80000000, "POPUP"), (0x40000000, "CHILD"), (0x10000000, "VISIBLE"),
    (0x00C00000, "CAPTION"), (0x00080000, "SYSMENU"), (0x00040000, "THICKFRAME"),
    (0x00020000, "MINIMIZEBOX"), (0x00010000, "MAXIMIZEBOX"), (0x00800000, "BORDER"),
    (0x00400000, "DLGFRAME"), (0x08000000, "DISABLED"),
]

out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SC3U.exe", "/FO", "CSV", "/NH"],
                     capture_output=True, text=True).stdout
if "SC3U" not in out:
    print("SC3U not running")
    raise SystemExit(1)
pid = int(out.split(",")[1].strip('" '))
print(f"pid {pid}")

rows = []
CB = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
def cb(h, _l):
    p = wintypes.DWORD()
    user32.GetWindowThreadProcessId(h, ctypes.byref(p))
    if p.value != pid:
        return True
    cls = ctypes.create_unicode_buffer(128)
    user32.GetClassNameW(h, cls, 128)
    txt = ctypes.create_unicode_buffer(128)
    user32.GetWindowTextW(h, txt, 128)
    wr = wintypes.RECT(); cr = wintypes.RECT()
    user32.GetWindowRect(h, ctypes.byref(wr))
    user32.GetClientRect(h, ctypes.byref(cr))
    st = user32.GetWindowLongW(h, -16)
    ex = user32.GetWindowLongW(h, -20)
    parent = user32.GetParent(h)
    rows.append((h, cls.value, txt.value, wr, cr, st, ex, parent,
                 bool(user32.IsWindowVisible(h))))
    return True

user32.EnumWindows(CB(cb), 0)
# EnumWindows is top-level only; also walk children of each
extra = []
CB2 = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
def cb2(h, _l):
    cls = ctypes.create_unicode_buffer(128)
    user32.GetClassNameW(h, cls, 128)
    wr = wintypes.RECT(); cr = wintypes.RECT()
    user32.GetWindowRect(h, ctypes.byref(wr))
    user32.GetClientRect(h, ctypes.byref(cr))
    extra.append((h, cls.value, wr, cr, user32.GetWindowLongW(h, -16), user32.GetParent(h)))
    return True

for r in list(rows):
    user32.EnumChildWindows(r[0], CB2(cb2), 0)

print(f"\n{len(rows)} top-level window(s):")
for h, cls, txt, wr, cr, st, ex, parent, vis in rows:
    names = "|".join(n for m, n in STYLES if st & m)
    print(f"  hwnd 0x{h:X}  class '{cls}'  text '{txt}'  visible={vis}")
    print(f"     window [{wr.left} {wr.top} {wr.right} {wr.bottom}]  "
          f"client {cr.right}x{cr.bottom}  parent 0x{parent or 0:X}")
    print(f"     style 0x{st & 0xFFFFFFFF:08X} = {names}")
    print(f"     exstyle 0x{ex & 0xFFFFFFFF:08X}")

if extra:
    print(f"\n{len(extra)} child window(s):")
    for h, cls, wr, cr, st, parent in extra:
        print(f"  hwnd 0x{h:X} class '{cls}' window [{wr.left} {wr.top} {wr.right} {wr.bottom}] "
              f"client {cr.right}x{cr.bottom} parent 0x{parent or 0:X} style 0x{st & 0xFFFFFFFF:08X}")
