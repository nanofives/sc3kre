"""spr47b70: drive the right-drag anchor marker draw without a mouse (child spr47b70, 2026-10-25).

At SIMSPR+0x42aac inside the city view tick FUN_10042a95 (main thread, every frame, esi = sub-object, view = esi-4;
sc3overscroll detours the entry) this sets the drag flag
+0x1e6 and the anchor +0x1ec/+0x1ee for N passes, the fields SetDragMode FUN_10042cfe writes for a right-drag, then
clears them. Used to run the SHAREREAD draw guard (SIMSPR+0x4407c) with a null anchor sprite. The game must be running
(not paused): a Frida attach to a paused game deadlocks (memory project-frida-paused-attach-deadlock).

    py re/tools/spr47b70_markerdraw.py --pid PID [--passes 60] [--x 350 --y 300]
"""

from __future__ import annotations

import argparse
import sys
import time

import frida

JS = r"""
const ss = Process.getModuleByName('SIMSPR.DLL').base;
let left = %d, set = 0, cleared = false, esiSeen = null, ends = 0, draws = 0;
// marker draw reached: +0x44085 runs only with a non-null sprite (the guard jumps from +0x4407c straight to +0x440a2)
Interceptor.attach(ss.add(0x440a2), function () { ends++; });
Interceptor.attach(ss.add(0x44092), function () { draws++; });
// the tick then calls the scroll step FUN_10043daf, whose drag branch draws the marker (SIMSPR+0x4407c)
const h = Interceptor.attach(ss.add(0x42aac), function () {
  const esi = this.context.esi.sub(4);
  if (left > 0) {
    if (esiSeen === null) { esiSeen = esi; send('view ' + esi + ' sprite +0x1fc = ' + esi.add(0x1fc).readPointer() + ' flag ' + esi.add(0x1e6).readU8()); }
    esi.add(0x1ec).writeS16(%d); esi.add(0x1ee).writeS16(%d); esi.add(0x1e6).writeU8(1);
    left--; set++;
  } else if (!cleared) {
    esi.add(0x1e6).writeU8(0); esi.add(0x1ec).writeS16(0); esi.add(0x1ee).writeS16(0);
    cleared = true; send('cleared after ' + set + ' marker passes: marker block ended ' + ends + 'x, sprite drawn ' + draws + 'x');
  }
});
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--passes", type=int, default=60)
    ap.add_argument("--x", type=int, default=350)
    ap.add_argument("--y", type=int, default=300)
    ap.add_argument("--seconds", type=float, default=20)
    a = ap.parse_args()
    sess = frida.attach(a.pid)
    done = []

    def on(m, d):
        print(m.get("payload") if m["type"] == "send" else m, flush=True)
        if m["type"] == "send" and str(m["payload"]).startswith("cleared"):
            done.append(1)

    sc = sess.create_script(JS % (a.passes, a.x, a.y))
    sc.on("message", on)
    sc.load()
    t0 = time.time()
    while not done and time.time() - t0 < a.seconds:
        time.sleep(0.1)
    time.sleep(0.3)
    sc.unload()
    sess.detach()
    print("done" if done else "TIMEOUT (marker draw site not reached)")
    return 0 if done else 1


if __name__ == "__main__":
    sys.exit(main())
