"""Scroll the city view under automation, without a cursor and without focus.

WHY THIS IS NEEDED. The city view's arrow-key scroll handler ignores the key code it is handed and
instead asks a keyboard device for the CURRENT PHYSICAL state of each arrow
(`SIMSPR FUN_1004979a` -> `keydev->vt+0xc`), and that device is 19 bytes:

    ushort GZWIND FUN_10025790(int vk) { return GetAsyncKeyState(vk) >> 0xf; }
                                                        [CONFIRMED @ GZWIND 0x10025790]

`GetAsyncKeyState` reads real hardware, which `PostMessage` cannot touch - so posted arrows can
never scroll, by design. Full chain: verify/offscreen/KEY_BINDINGS_RUNTIME.md.

WHAT THIS DOES. Hooks that one function and makes it report the chosen arrows as held, then posts
the arrow key that drives the handler. Nothing else is faked, the cursor is never moved, focus is
never taken, and the hook is removed on exit. This is the narrowest possible intervention: one
19-byte leaf function.

    python re/tools/key_state_spoof.py --dir right --taps 3
    python re/tools/key_state_spoof.py --dir up,left --taps 2 --no-verify
    python re/tools/key_state_spoof.py --probe          # just log what the game asks about

--verify (default) grabs a frame before and after and reports the measured TRANSLATION, because a
changed-pixel count is NOT evidence of a scroll here (a 29k-pixel "pan" once turned out to be a
selection highlight - verify/offscreen/MAP_INPUT.md).
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import time

import frida
import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402

VK = {"up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27}
OUT = pathlib.Path("verify/offscreen/scroll")

JS = r"""
var spoof = {};      /* vk -> true while we want it reported as held */
var seen  = [];      /* diagnostic: what the game actually asks about */
var probeOnly = false;

function mb(w){var m=Process.enumerateModules();
  for(var i=0;i<m.length;i++) if(m[i].name.toLowerCase()===w.toLowerCase()) return m[i].base;
  return null;}

var base = mb("GZWIND.DLL");
/* GZWIND FUN_10025790: ushort f(int vk) { return GetAsyncKeyState(vk) >> 15; }
   Called through the keyboard device's vtable slot +0xc. Ghidra gives it ONE stack parameter and
   no `this`, so args[0] is the vk. */
var target = base.add(0x25790);

Interceptor.attach(target, {
  onEnter: function (args) { this.vk = args[0].toInt32(); },
  onLeave: function (retval) {
    seen.push({vk: this.vk, real: retval.toInt32()});
    if (seen.length > 400) seen.shift();
    if (!probeOnly && spoof[this.vk]) retval.replace(1);
  }
});

rpc.exports = {
  where:  function(){ return target.toString(); },
  set:    function(vks){ spoof = {}; vks.forEach(function(v){ spoof[v] = true; }); return true; },
  clear:  function(){ spoof = {}; return true; },
  probe:  function(on){ probeOnly = on; return true; },
  seen:   function(){ var s = seen; seen = []; return s; }
};
"""


def translation(a: Image.Image, b: Image.Image, hud_w: int = 110, hud_h: int = 62):
    """Measured shift of the CITY AREA, by FFT phase correlation.

    Returns (dx, dy, peak). `peak` near 0 means the two frames share no structure - which happens
    easily here, because ONE key event scrolls ~56 px and a timed burst can leave no overlap at
    all. A weak peak therefore means "scrolled too far to measure", NOT "did not scroll"; the
    caller must not report those as the same thing (an earlier version did, and called a working
    2 s scroll a failure).

    The HUD is excluded: the side panel and bottom bar do not move, and leaving them in pins the
    correlation at zero.
    """
    def prep(im):
        c = im.convert("L").crop((0, 0, max(32, im.width - hud_w), max(32, im.height - hud_h)))
        arr = np.asarray(c, np.float32)
        return arr - arr.mean()

    A, B = prep(a), prep(b)
    if A.shape != B.shape:
        return 0, 0, 0.0
    F = np.fft.fft2(A) * np.conj(np.fft.fft2(B))
    F /= np.abs(F) + 1e-9
    corr = np.abs(np.fft.ifft2(F))
    dy, dx = np.unravel_index(int(np.argmax(corr)), corr.shape)
    if dy > A.shape[0] // 2:
        dy -= A.shape[0]
    if dx > A.shape[1] // 2:
        dx -= A.shape[1]
    return int(dx), int(dy), float(corr.max())


class Spoof:
    """Context manager: hook installed on enter, removed on exit."""

    def __init__(self):
        self.session = None
        self.script = None

    def __enter__(self):
        self.session = frida.attach(sc3io.game_pid())
        self.script = self.session.create_script(JS)
        self.script.load()
        return self

    def __exit__(self, *exc):
        try:
            self.script.exports_sync.clear()
        except Exception:
            pass
        self.session.detach()
        return False

    def hold(self, vks: list[int]) -> None:
        self.script.exports_sync.set(vks)

    def release(self) -> None:
        self.script.exports_sync.clear()

    def seen(self):
        return self.script.exports_sync.seen()


# ⚠️ The view scrolls CONTINUOUSLY while the spoofed flag is set, not by a fixed step per key
# event. The flags latch when a key event arrives and clear on the next event seen with the spoof
# OFF, so distance ~= rate x how long the spoof is held. Measured 2026-09-07 at 800x600: a ~0.12 s
# hold moved ~300 px, i.e. of the order of 2500 px/s. An earlier constant of "56 px per tap" came
# from a single minimal impulse and does NOT generalise - do not rely on it.
SCROLL_RATE_PX_PER_S = 2500   # order of magnitude only, at 800x600


def scroll(hwnd: int, dirs: list[str], taps: int, sp: Spoof, gap: float = 0.12) -> None:
    """Report the arrows as held, then send `taps` discrete key events.

    Discrete taps, not a timed hold: each key event moves the view ~56 px, so a "2 second scroll"
    crosses the whole map. Taps make the distance predictable and keep frames comparable.
    """
    vks = [VK[d] for d in dirs]
    sp.hold(vks)
    for _ in range(max(1, taps)):
        for vk in vks:
            sc3io.key(hwnd, vk, hold=0.02)
        time.sleep(gap)
    sp.release()
    for vk in vks:
        sc3io.key(hwnd, vk, hold=0.02)   # one event with the spoof off, so the flags clear
    time.sleep(0.5)


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", default="right", help="comma list of up,down,left,right")
    ap.add_argument("--taps", type=int, default=1, help="number of key events to send")
    ap.add_argument("--hold", type=float, default=0.12,
                    help="seconds the spoofed key state is held per tap; distance scales with this "
                         f"(order {SCROLL_RATE_PX_PER_S} px/s at 800x600)")
    ap.add_argument("--probe", action="store_true", help="log what the game queries, change nothing")
    ap.add_argument("--no-verify", action="store_true")
    a = ap.parse_args(argv)

    try:
        hwnd = sc3io.game_hwnd()
    except sc3io.CaptureError as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 2
    dirs = [d.strip().lower() for d in a.dir.split(",") if d.strip()]
    for d in dirs:
        if d not in VK:
            print(f"STOP: unknown direction {d!r}; use {sorted(VK)}", file=sys.stderr)
            return 2
    OUT.mkdir(parents=True, exist_ok=True)

    with Spoof() as sp:
        print(f"[*] hooked GZWIND FUN_10025790 at {sp.script.exports_sync.where()}")

        if a.probe:
            sp.script.exports_sync.probe(True)
            print("[*] probing for 3 s - posting arrows, changing nothing")
            for _ in range(6):
                for vk in VK.values():
                    sc3io.key(hwnd, vk, hold=0.02)
                time.sleep(0.4)
            seen = sp.seen()
            print(f"    the game queried the device {len(seen)} time(s)")
            uniq = sorted({s["vk"] for s in seen})
            print(f"    vks asked about: {[hex(v) for v in uniq]}")
            print(f"    real values returned: {sorted({s['real'] for s in seen})}")
            return 0

        before = None
        if not a.no_verify:
            sc3io.grab_to(str(OUT / "before.png"), hwnd, settle=0.4)
            before = Image.open(OUT / "before.png").convert("RGB")

        print(f"[*] scrolling {dirs}, {a.taps} tap(s) x {a.hold}s hold "
              f"(cursor untouched, focus untouched)")
        scroll(hwnd, dirs, a.taps, sp, gap=a.hold)

        seen = sp.seen()
        arrows = [s for s in seen if s["vk"] in VK.values()]
        print(f"[*] the handler queried the arrows {len(arrows)} time(s) during the scroll")

        if before is not None:
            sc3io.grab_to(str(OUT / "after.png"), hwnd, settle=0.4)
            after = Image.open(OUT / "after.png").convert("RGB")
            dx, dy, peak = translation(before, after)
            print(f"[*] measured shift: dx={dx:+d} dy={dy:+d} px  (correlation peak {peak:.3f})")
            if peak < 0.05:
                print("    -> the frames share no structure: it scrolled TOO FAR to measure. "
                      "Use fewer --taps to get a number.")
                return 0
            print("    -> SCROLLED" if (dx or dy) else "    -> did NOT scroll")
            if abs(dy) > (after.height - 62) // 3 or abs(dx) > (after.width - 110) // 3:
                print("    ⚠️ the shift is a large fraction of the frame: phase correlation ALIASES "
                      "there, so the SIGN may be wrong. Use a shorter --hold for a reliable sign.")
            return 0 if (dx or dy) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
