#!/usr/bin/env python3
r"""link_tree.py - make a hard-linked copy of a game install for data-mod tests (CHILD_PROTOCOL section 10).

Every file becomes a hard link (no extra disk), except the release mod files in Apps\ (SC3U loads and frees
every *.dll in Apps, so a second mod copy crashes the game; CHILD_PROTOCOL section 10) and the source tree's
own re\ folder. Never edit a linked file in place: delete it and copy (newpiece.py install does this).

  py -3.12 re/tools/netmod/link_tree.py <src install> <dst>      # dst must not exist
  py -3.12 re/tools/netmod/link_tree.py --verify <src> <dst>     # count linked / de-linked / missing
"""
import os
import sys

# mods_launch.exe is retired (2026-10-25) but still skipped so an old source install does not leak it into a tree.
SKIP_APPS = {"mods_launch.exe", "sc3resize.dll", "sc3bigcity.dll", "sc3overscroll.dll", "sc3simrun.dll",
             "sc3perf.dll", "sc3netmod.dll", "sc3undo.dll", "sc3cartrips.dll", "sc3mods.dll", "perf.ini", "menu_bg.bmp", "sc3mods_readme.txt", "sc3resize.ini"}


def skip(rel):
    parts = rel.replace("\\", "/").split("/")
    if parts[0].lower() == "re":
        return True
    if len(parts) == 2 and parts[0].lower() == "apps":
        n = parts[1].lower()
        return n in SKIP_APPS or n.endswith(".log")
    return False


def walk(src):
    for dp, dns, fns in os.walk(src):
        for fn in fns:
            full = os.path.join(dp, fn)
            yield os.path.relpath(full, src), full


def link(src, dst):
    if os.path.exists(dst):
        sys.exit("%s exists; refusing" % dst)
    n = s = 0
    for rel, full in walk(src):
        if skip(rel):
            s += 1
            continue
        out = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        os.link(full, out)
        n += 1
    print("linked %d files, skipped %d (mods in Apps, re\\)" % (n, s))


def verify(src, dst):
    same = diff = miss = 0
    for rel, full in walk(src):
        if skip(rel):
            continue
        out = os.path.join(dst, rel)
        if not os.path.exists(out):
            miss += 1
        elif os.path.samefile(full, out):
            same += 1
        else:
            diff += 1
            print("de-linked: %s" % rel)
    print("linked %d, de-linked %d, missing %d" % (same, diff, miss))


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--verify":
        verify(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3:
        link(sys.argv[1], sys.argv[2])
    else:
        print(__doc__)
        sys.exit(2)
