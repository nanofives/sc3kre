"""sc3wait.py - wait on a signal the game already logs instead of a fixed sleep (2026-10-27).

Every wait keeps a timeout. Callers that used to `time.sleep(60)` for a city load pass the same
bound (raised to 110 s: zoomband logged loads up to 103 s) and keep the old failure mode when the
signal never shows.
"""
import os
import re
import sys
import time

CITY_UP = r"city HUD became visible|bridge captured"


def _read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def wait_log(log, pattern, timeout, since=None, start=0, poll=0.5, alive=None):
    """Poll `log` for regex `pattern`. Only a log written at/after `since` (epoch) counts, so a stale
    file from a previous run cannot satisfy the wait. Searches from char offset `start`.
    Returns (matched, end_offset); never raises."""
    t0 = time.time()
    rx = re.compile(pattern)
    while True:
        try:
            fresh = os.path.exists(log) and (since is None or os.path.getmtime(log) >= since - 2)
        except OSError:
            fresh = False
        if fresh:
            txt = _read(log)
            m = rx.search(txt, start)
            if m:
                return True, m.end()
        if time.time() - t0 >= timeout or (alive is not None and not alive()):
            return False, start
        time.sleep(poll)


def wait_city_up(log, since, timeout=110.0, fallback_sleep=60.0, settle=0.0, pid=None, keep_paused=False):
    """Return as soon as the city is up. If the log never appears (the mod that writes it is not in
    this arm) fall back to the old fixed sleep so such arms behave as before. If the log exists but
    the signal does not show within `timeout`, raise SystemExit (fail loudly).
    With `pid`, the city is then unpaused (run_after_load) unless `keep_paused` or SC3_KEEP_PAUSED=1."""
    t0 = time.time()
    ok, _ = wait_log(log, CITY_UP, timeout, since=since)
    if ok:
        print("city up after %.1f s" % (time.time() - t0), flush=True)
        if settle:
            time.sleep(settle)
    elif not os.path.exists(log):
        left = max(0.0, fallback_sleep - (time.time() - t0))
        print("WARN: %s never appeared; fixed %.0f s wait instead" % (log, left), file=sys.stderr, flush=True)
        time.sleep(left)
    else:
        raise SystemExit("city never came up: no '%s' in %s after %.0f s" % (CITY_UP, log, timeout))
    if pid is not None:
        run_after_load(pid, keep_paused=keep_paused)


def run_after_load(pid, keep_paused=False, timeout=15.0, hold=1.0):
    """A city opened from a path loads at user-pause depth 1 (city+0x140; BOARD 2026-08-25, the game's own
    behaviour, mods_launch.exe never changed it). Tools that attach Frida need it running (sc3pause: an attach
    while paused, then an unpause, deadlocked the game), so post P (sc3resize PAUSEKEY: depth > 0 -> 0xc2a35d80,
    one level) until the depth reads 0 and stays 0 for `hold` s. The depth is re-read before every press, so this
    never re-pauses a running game. `keep_paused` or SC3_KEEP_PAUSED=1 leaves the load state alone.
    Needs sc3resize in the game (stock games have no P key). Raises SystemExit if still paused after `timeout`."""
    import sc3pause
    if keep_paused or os.environ.get("SC3_KEEP_PAUSED") == "1":
        print("keep paused: %s" % sc3pause.pause_state(pid)[1], flush=True)
        return
    import sc3io
    t0, presses, t_last, t_zero, detail = time.time(), 0, 0.0, None, ""
    hwnd = None
    while time.time() - t0 < timeout:
        paused, detail = sc3pause.pause_state(pid)
        if paused is False:
            t_zero = t_zero or time.time()
            if time.time() - t_zero >= hold:
                print("running after load (%s, %d P press(es), %.1f s)" % (detail, presses, time.time() - t0),
                      flush=True)
                return
        else:
            t_zero = None
            if paused and time.time() - t_last >= 1.5:
                hwnd = hwnd or sc3io.game_hwnd(pid)
                sc3io.key(hwnd, ord("P"))
                presses, t_last = presses + 1, time.time()
        time.sleep(0.25)
    raise SystemExit("game still paused %.0f s after load (%s, %d P press(es); is sc3resize loaded?)"
                     % (timeout, detail, presses))


def wait_file_saved(path, since, timeout=30.0, stable=1.0, poll=0.25):
    """Wait until `path` was rewritten after `since` (epoch) and its size has held for `stable` s.
    Replaces the fixed post-Save sleep. Raises SystemExit if no write shows up within `timeout`."""
    t0 = time.time()
    last = None
    t_same = None
    while time.time() - t0 < timeout:
        try:
            st = os.stat(path)
            cur = (st.st_mtime, st.st_size)
            if st.st_mtime >= since - 2:
                if cur != last:
                    last, t_same = cur, time.time()
                elif time.time() - t_same >= stable:
                    print("saved after %.1f s (%d bytes)" % (time.time() - since, st.st_size), flush=True)
                    return
        except OSError:
            pass
        time.sleep(poll)
    raise SystemExit("save never landed: %s not rewritten within %.0f s" % (path, timeout))


def wait_layout(log, start, timeout=60.0, settle=1.0):
    """After a resize/maximize: wait for the next `RZ   TIMING pass` line past char offset `start`
    (the mod logs it when the re-layout is finished). Prints a loud WARN and returns False on timeout,
    so the caller carries on exactly as it did after the old blind sleep."""
    t0 = time.time()
    ok, _ = wait_log(log, r"RZ\s+TIMING pass", timeout, start=start)
    if ok:
        print("layout done after %.1f s" % (time.time() - t0), flush=True)
        time.sleep(settle)
    else:
        print("WARN: no 'RZ TIMING pass' in %s within %.0f s" % (log, timeout), file=sys.stderr, flush=True)
    return ok


# Mod DLLs in the order the retired mods_launch.exe loaded them; only the ones present in the instance load.
MODS = ["sc3resize.dll", "sc3bigcity.dll", "sc3overscroll.dll", "sc3simrun.dll", "sc3startsize.dll", "sc3perf.dll",
        "sc3netmod.dll", "sc3cartrips.dll", "sc3undo.dll", "sc3autosave.dll"]


def launch_game(inst, city, env=None, out=None, multi=True, extra_args=(), tree=None, pre_args=(), off=False):
    r"""Start <tree>\Apps\SC3U.exe directly with the mods of instance folder `inst` (replaces
    `<inst>\mods_launch.exe -multi -- <city>`, retired 2026-10-25). The version.dll / sc3mods.dll loader beside
    the exe reads SC3MODS_DIR (mods + their logs live in `inst`), SC3MODS_LIST (the DLLs present, in the old
    launcher's order) and SC3MODS_MULTI (per-pid single-instance mutex). `tree` defaults to inst\..\..\..
    The launcher no longer enforces the game lease: take it (game_lock.ps1) and export SC3_SESSION yourself.
    `city=None` starts the game with no city (intro / menu path). `pre_args` go before the city (e.g.
    ["-intro:off"]), `extra_args` after it. `off=True` sets SC3MODS_OFF=1: stock game, no mod DLL needed.
    Returns (Popen, t_launch); Popen.pid is the game's own pid."""
    import subprocess
    inst = os.path.abspath(inst)
    tree = os.path.abspath(tree or os.path.join(inst, "..", "..", ".."))
    apps = os.path.join(tree, "Apps")
    exe = os.path.join(apps, "SC3U.exe")
    if not os.path.exists(exe):
        raise SystemExit("no SC3U.exe at %s" % exe)
    present = [m for m in MODS if os.path.exists(os.path.join(inst, m))]
    if not present and not off:
        raise SystemExit("no mod DLL in %s" % inst)
    e = dict(os.environ if env is None else env)
    if off:
        e["SC3MODS_OFF"] = "1"
    else:
        e.pop("SC3MODS_OFF", None)
        e["SC3MODS_DIR"] = inst
        e["SC3MODS_LIST"] = ";".join(present)
        # as mods_launch.exe did: a mod built with sc3mods_guard.h (2026-10-27) stays inert under a version.dll
        # older than its sc3mods_loading export (the main tree's Apps\version.dll is 10-21) unless this is set
        e["SC3MODS_ANYLOAD"] = "1"
    if multi:
        e["SC3MODS_MULTI"] = "1"
    else:
        e.pop("SC3MODS_MULTI", None)
    if city and os.path.exists(city):
        city = os.path.abspath(city)      # the game runs with cwd = Apps
    args = [exe] + list(pre_args) + ([city] if city else []) + list(extra_args)
    sink = out if out is not None else subprocess.DEVNULL
    t_launch = time.time()
    p = subprocess.Popen(args, cwd=apps, env=e, stdout=sink, stderr=subprocess.STDOUT if out is not None else None)
    return p, t_launch
