# sitecustomize.py - task suitespeed (2026-11-20): the file tracer behind suite.py's Python reference cache.
#
# suite.py puts this folder first on PYTHONPATH and sets SUITE_TRACE=<folder> for a setup step (golden_setup.py,
# sc4_*_setup.py, ...). Every Python process of that step (the setup script and each sc4conv.py / bldimport.py it
# starts) then records, through an audit hook (PEP 578):
#   r <path>   a file opened for reading (the code it imports included: imports open their .py / .pyc through
#              io.open_code, which raises the same "open" event)
#   w <path>   a file opened for writing, created, renamed or copied to
#   l <path>   a folder listed (os.listdir / os.scandir: os.walk, glob)
# one line per path and kind, appended to <SUITE_TRACE>/<pid>.txt as soon as it is seen (a pool worker stopped by
# TerminateProcess still leaves its lines). suite.py turns them into the step's key. Nothing else changes: with
# SUITE_TRACE unset this file does nothing.
import os
import sys

_dir = os.environ.get("SUITE_TRACE")
if _dir:
    _seen = set()
    _fh = [None]
    _busy = [False]
    _own = os.path.normcase(os.path.abspath(_dir))
    _WR = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC

    def _put(kind, p):
        if isinstance(p, int) or p is None:
            return
        try:
            p = os.fsdecode(p)
        except (TypeError, ValueError):
            return
        if _busy[0]:
            return
        _busy[0] = True
        try:
            a = os.path.abspath(p)
            k = (kind, a)
            if k not in _seen and not os.path.normcase(a).startswith(_own):
                _seen.add(k)
                if _fh[0] is None:
                    _fh[0] = open(os.path.join(_dir, "%d.txt" % os.getpid()), "a", encoding="utf-8", buffering=1)
                _fh[0].write("%s %s\n" % (kind, a))
        except Exception:
            pass
        finally:
            _busy[0] = False

    def _hook(ev, args):
        if ev == "open":
            p, mode, flags = args
            if mode is None:
                w = bool(flags & _WR)
            else:
                w = any(c in mode for c in "wax+")
            _put("w" if w else "r", p)
        elif ev in ("os.listdir", "os.scandir"):
            _put("l", args[0] if args and args[0] is not None else ".")
        elif ev in ("os.rename", "shutil.copyfile", "shutil.copymode", "shutil.copystat", "os.link", "os.symlink",
                    "_winapi.CopyFile2"):     # shutil.copy2 / copytree on Windows (3.12) copy with CopyFile2
            if len(args) >= 2:
                _put("r", args[0])
                _put("w", args[1])
        elif ev == "os.mkdir":
            _put("w", args[0])

    sys.addaudithook(_hook)
