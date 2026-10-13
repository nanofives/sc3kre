"""paths.py -- where the game files live, for every netmod tool.

Read-only. Nothing in netmod writes under the game install.

Resolution order for the game root (the folder that holds `Apps\\SC3U.exe`):
  1. `$SC3_GAME_ROOT` if set;
  2. walking up from the current directory;
  3. walking up from this file;
  4. the main checkout of this git repo (a worktree has no game files: they are untracked and
     exist only in the main checkout, so `git rev-parse --git-common-dir` points us there).
"""
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)                       # re/tools
REPO = os.path.dirname(os.path.dirname(TOOLS))      # repo root of THIS checkout


def _is_root(d):
    return os.path.isfile(os.path.join(d, "Apps", "SC3U.exe"))


def _walk_up(d):
    d = os.path.abspath(d)
    while True:
        if _is_root(d):
            return d
        up = os.path.dirname(d)
        if up == d:
            return None
        d = up


def _main_checkout():
    try:
        out = subprocess.run(["git", "-C", REPO, "rev-parse", "--git-common-dir"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    if not out:
        return None
    common = out if os.path.isabs(out) else os.path.join(REPO, out)
    return os.path.dirname(os.path.abspath(common))


def game_root():
    env = os.environ.get("SC3_GAME_ROOT")
    if env:
        if not _is_root(env):
            raise SystemExit("SC3_GAME_ROOT=%s has no Apps\\SC3U.exe" % env)
        return os.path.abspath(env)
    for start in (os.getcwd(), HERE):
        r = _walk_up(start)
        if r:
            return r
    m = _main_checkout()
    if m and _is_root(m):
        return m
    raise SystemExit("game root not found: set SC3_GAME_ROOT to the folder holding Apps\\SC3U.exe")


class Game:
    """Every path netmod reads, relative to one game root."""

    def __init__(self, root=None):
        self.root = root or game_root()
        a = os.path.join(self.root, "Apps")
        self.apps = a
        self.res = os.path.join(a, "Res")
        self.tiling = os.path.join(self.res, "TilingRules")
        self.sprites = os.path.join(self.res, "Sprites")
        self.occupant = os.path.join(self.res, "Occupant")
        self.ssimdata = os.path.join(self.res, "SSimData")
        self.simntwrk = os.path.join(a, "SIMNTWRK.DLL")
        self.syspak = os.path.join(a, "Sys", "SYS.PAK")
        # extracted SYS.PAK members (re/tools/syspak_parse.py output), main checkout only
        self.occupant_ini = os.path.join(self.root, "re", "data", "syspak", "Occupant.ini")

    def trblkatt(self, lang="ENGLISH"):
        return os.path.join(self.ssimdata, lang, "TRBLKATT.IXF")

    def trblkatt_langs(self):
        out = []
        for n in sorted(os.listdir(self.ssimdata)):
            p = os.path.join(self.ssimdata, n, "TRBLKATT.IXF")
            if os.path.isfile(p):
                out.append(n)
        return out


def default_out():
    """Generated output (catalog JSON/CSV, PNGs, HTML). `/re/*` in .gitignore covers it."""
    return os.path.join(REPO, "re", "netcat_out")
