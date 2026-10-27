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


def wait_city_up(log, since, timeout=110.0, fallback_sleep=60.0, settle=0.0):
    """Return as soon as the city is up. If the log never appears (the mod that writes it is not in
    this arm) fall back to the old fixed sleep so such arms behave as before. If the log exists but
    the signal does not show within `timeout`, raise SystemExit (fail loudly)."""
    t0 = time.time()
    ok, _ = wait_log(log, CITY_UP, timeout, since=since)
    if ok:
        print("city up after %.1f s" % (time.time() - t0), flush=True)
        if settle:
            time.sleep(settle)
        return
    if not os.path.exists(log):
        left = max(0.0, fallback_sleep - (time.time() - t0))
        print("WARN: %s never appeared; fixed %.0f s wait instead" % (log, left), file=sys.stderr, flush=True)
        time.sleep(left)
        return
    raise SystemExit("city never came up: no '%s' in %s after %.0f s" % (CITY_UP, log, timeout))


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


def launch_game(inst, city, env=None, out=None, multi=True, extra_args=(), tree=None):
    r"""Start <tree>\Apps\SC3U.exe directly with the mods of instance folder `inst` (replaces
    `<inst>\mods_launch.exe -multi -- <city>`, retired 2026-10-25). The version.dll / sc3mods.dll loader beside
    the exe reads SC3MODS_DIR (mods + their logs live in `inst`), SC3MODS_LIST (the DLLs present, in the old
    launcher's order) and SC3MODS_MULTI (per-pid single-instance mutex). `tree` defaults to inst\..\..\..
    The launcher no longer enforces the game lease: take it (game_lock.ps1) and export SC3_SESSION yourself.
    Returns (Popen, t_launch); Popen.pid is the game's own pid."""
    import subprocess
    inst = os.path.abspath(inst)
    tree = os.path.abspath(tree or os.path.join(inst, "..", "..", ".."))
    apps = os.path.join(tree, "Apps")
    exe = os.path.join(apps, "SC3U.exe")
    if not os.path.exists(exe):
        raise SystemExit("no SC3U.exe at %s" % exe)
    present = [m for m in MODS if os.path.exists(os.path.join(inst, m))]
    if not present:
        raise SystemExit("no mod DLL in %s" % inst)
    e = dict(os.environ if env is None else env)
    e["SC3MODS_DIR"] = inst
    e["SC3MODS_LIST"] = ";".join(present)
    if multi:
        e["SC3MODS_MULTI"] = "1"
    else:
        e.pop("SC3MODS_MULTI", None)
    if os.path.exists(city):
        city = os.path.abspath(city)      # the game runs with cwd = Apps
    args = [exe, city] + list(extra_args)
    sink = out if out is not None else subprocess.DEVNULL
    t_launch = time.time()
    p = subprocess.Popen(args, cwd=apps, env=e, stdout=sink, stderr=subprocess.STDOUT if out is not None else None)
    return p, t_launch
