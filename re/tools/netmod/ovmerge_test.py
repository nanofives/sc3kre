#!/usr/bin/env python3
"""ovmerge_test.py - offline test of sc3netmod's OVMERGE block, plus the hand-made test mods (task overlaymerge
2026-11-21, verify/overlaymerge/RESULTS.md).

The merge code is the DLL's own source (re/harness/src/sc3netmod_ovmerge.c), compiled into ovmerge_host.exe with
stubs. Each case builds a fake game root in a temp folder (EA files stay out of the repo): <root>\\Apps\\... = the
player's files, <root>\\mods\\netmod\\overlay\\... = our overlay, <root>\\mods\\netmod\\overlay_base.txt from the stock
install. Then it runs the host and checks the file the game would be served with ixf_parse / syspak_parse.

  py -3.12 ovmerge_test.py [--stock <GOG install root>] [--overlay <tree with mods\\netmod\\overlay>]
  py -3.12 ovmerge_test.py --make-mods <game root> [--mods farm,pak,rules]   # apply the test mods to a tree's Apps\\
  py -3.12 ovmerge_test.py --undo-mods <game root>                           # put the stock files back

Test mods (what a player's mod would do to the stock files):
  farm   Apps\\Res\\BUILDFAM.IXF family 25 (farms, LandUse 9300): Windmill weight 1 -> 60, Hans Silo weight 1 -> 0,
         Tool Shed line removed and BuildingCount 9 -> 8; a new family record (instance 0x7F, LandUse 9300 copy).
  pak    Apps\\Sys\\SYS.PAK: SC3ZoneLayer.ini [ZoneDeveloperDescriptions] 9= farms up to land value 125 (was 90),
         Default.ini [DBSegments] a new row 0x0FA4A000=...;Res\\FarmMod.IXF, a new member FarmMod.ini.
  rules  Apps\\Res\\TilingRules\\ROAD_GRND_Set.txt: one line appended (not mergeable: must warn).
"""
import argparse
import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.normpath(os.path.join(HERE, ".."))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "harness", "src"))
sys.path.insert(0, TOOLS)
sys.path.insert(0, HERE)
import ixf_parse                                       # noqa: E402
import syspak_parse                                    # noqa: E402
import overlay_base                                    # noqa: E402

BUILDFAM = r"Apps\Res\BUILDFAM.IXF"
SYSPAK = r"Apps\Sys\SYS.PAK"
RULES = r"Apps\Res\TilingRules\ROAD_GRND_Set.txt"
FAM_TYPE, FAM_GROUP = 0x81F53D09, 0x01F58D3D
NEW_FAM = 0x7F
DBROW = r"0x0FA4A000=0x80c381d7;Res\FarmMod.IXF"
FARM_IXF = r"Apps\Res\FarmMod.IXF"


def rd(p):
    with open(p, "rb") as fh:
        return fh.read()


def wr(p, b):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if os.path.lexists(p):
        os.remove(p)                                   # never write through a hard link
    with open(p, "wb") as fh:
        fh.write(b)


def find_main():
    d = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
    for _ in range(5):
        if os.path.isdir(os.path.join(d, "original", "gog_2.0.949")):
            return d
        d = os.path.dirname(d)
    return None


# ------------------------------------------------------------------ IXF helpers
def ixf_records(d):
    recs = ixf_parse.parse_bytes(d) if hasattr(ixf_parse, "parse_bytes") else None
    if recs is None:
        out, n = [], 0
        while 4 + (n + 1) * 20 <= len(d):
            g, i, t, off, size = struct.unpack_from("<5I", d, 4 + n * 20)
            n += 1
            if (g, i, t) == (0, 0, 0):
                break
            if off == 0xFFFFFFFF or size == 0xFFFFFFFF:
                continue
            out.append([g, i, t, d[off:off + size]])
        return out
    return recs


def ixf_slots(d):
    offs = []
    n = 0
    while 4 + (n + 1) * 20 <= len(d):
        g, i, t, off, size = struct.unpack_from("<5I", d, 4 + n * 20)
        n += 1
        if (g, i, t) == (0, 0, 0):
            break
        if off != 0xFFFFFFFF:
            offs.append(off)
    return (min(offs) - 4) // 20 if offs else 1


def ixf_write(recs, slots):
    slots = max(slots, len(recs) + 1)
    out = bytearray(struct.pack("<I", 0x80C381D7))
    off = 4 + slots * 20
    for g, i, t, p in recs:
        out += struct.pack("<5I", g, i, t, off, len(p))
        off += len(p)
    out += b"\0" * 20 * (slots - len(recs))
    for r in recs:
        out += r[3]
    return bytes(out)


def family(recs, inst):
    for r in recs:
        if r[0] == FAM_GROUP and r[1] == inst and r[2] == FAM_TYPE:
            return r
    raise KeyError(inst)


# ------------------------------------------------------------------ the test mods
def farm_mod(d):
    recs = ixf_records(d)
    r = family(recs, 25)
    t = r[3].decode("latin1")
    t2 = t.replace("Key: 1406,545184782,5000,1 ", "Key: 1406,545184782,5000,60")
    t2 = t2.replace("Key: 1406,545184782,5003,1 ", "Key: 1406,545184782,5003,0 ")
    t2 = re.sub(r"Key: 1406,545184782,5011,1[^\r\n]*\r\n", "", t2)
    t2 = t2.replace("BuildingCount: 9", "BuildingCount: 8")
    assert t2 != t and "5000,60" in t2 and "545184782,5011," not in t2, "farm_mod: family 25 is not the stock one"
    r[3] = t2.encode("latin1")
    newfam = ("TXT! Farm mod test family (ovmerge_test).\r\nLandUse: 9300\r\nBuildingCount: 1\r\n"
              "Key: 1406,545184782,5000,1    Windmill\r\n").encode("latin1")
    recs.append([FAM_GROUP, NEW_FAM, FAM_TYPE, newfam])
    return ixf_write(recs, ixf_slots(d))


def pak_mod(d):
    names, _o, _t, recs = syspak_parse.parse(d)
    lines = [list(r["lines"]) for r in recs]

    def member(n):
        return lines[[x.lower() for x in names].index(n.lower())]
    z = member("SC3ZoneLayer.ini")
    k = [i for i, x in enumerate(z) if x.startswith("9=0xe1a53b30")]
    assert len(k) == 1 and "9300,A,1,90,1" in z[k[0]], "pak_mod: SC3ZoneLayer.ini 9= is not the stock one"
    z[k[0]] = z[k[0]].replace("9300,A,1,90,1", "9300,A,1,125,1")
    df = member("Default.ini")
    end = df.index("[ResourceFactories]")
    df.insert(end, DBROW)
    names.append("FarmMod.ini")
    lines.append(["[Admin]", "Name=Farm mod test", "Enabled=ON"])
    return syspak_parse.build(names, lines)


def rules_mod(d):
    return d + (b"" if d.endswith(b"\n") else b"\r\n") + b"; farm mod test line (ovmerge_test)\r\n"


MODS = {"farm": (BUILDFAM, farm_mod), "pak": (SYSPAK, pak_mod), "rules": (RULES, rules_mod)}


def community_pak(d):
    """The community patch's SYS.PAK lines (community_patch.ps1: PetitionerExtraInfo 0xD9..0xDB, petition count +2)."""
    names, _o, _t, recs = syspak_parse.parse(d)
    lines = [list(r["lines"]) for r in recs]
    pe = lines[[x.lower() for x in names].index("petitionerextrainfo.ini")]
    if "0x000000D9=19,2" not in pe:
        i = max(j for j, x in enumerate(pe) if x.startswith("0x000000")) + 1
        pe[i:i] = ["0x000000D9=19,2", "0x000000DA=19,2", "0x000000DB=19,2"]
        pm = lines[[x.lower() for x in names].index("petitionermanager.ini")]
        k = [j for j, x in enumerate(pm) if x.startswith("NumberOfPetitionerMessages=")][0]
        pm[k] = "NumberOfPetitionerMessages=%d" % (int(pm[k].split("=")[1]) + 2)
    return syspak_parse.build(names, lines)


def bat_like(d):
    """What re/scripts/bat_growables.ps1 does to the OVERLAY BUILDFAM: a Key line first in a family, count + 1."""
    recs = ixf_records(d)
    r = family(recs, 25)
    t = r[3].decode("latin1")
    m = re.search(r"BuildingCount:\s*(\d+)[^\r\n]*\r?\n", t)
    t = t[:m.start()] + "BuildingCount: %d\r\n" % (int(m.group(1)) + 1) + \
        "Key: 1406,545184782,37000,5   BAT test building\r\n" + t[m.end():]
    r[3] = t.encode("latin1")
    return ixf_write(recs, ixf_slots(d))


# ------------------------------------------------------------------ host
def build_host(out_dir):
    exe = os.path.join(out_dir, "ovmerge_host.exe")
    src = os.path.join(HERE, "ovmerge_host.c")
    bat = os.path.join(out_dir, "build_host.bat")      # a .bat: cmd /c with nested quotes is mangled by subprocess
    with open(bat, "w") as fh:
        fh.write('@echo off\r\nset CL=\r\ncall "%s" >nul\r\ncl /nologo /O2 /W3 /D_CRT_SECURE_NO_WARNINGS /Fe"%s" /Fo"%s\\\\" "%s" '
                 'kernel32.lib\r\n' % (vcvars(), exe, out_dir, src))
    r = subprocess.run(["cmd", "/c", bat], capture_output=True, text=True, cwd=out_dir)
    if r.returncode or not os.path.isfile(exe):
        raise SystemExit("host build failed:\n" + r.stdout + r.stderr)
    warn = [l for l in r.stdout.splitlines() if "warning" in l]
    return exe, warn


def vcvars():
    vswhere = r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
    root = subprocess.run([vswhere, "-latest", "-products", "*", "-property", "installationPath"],
                          capture_output=True, text=True).stdout.strip().splitlines()[0]
    return os.path.join(root, "VC", "Auxiliary", "Build", "vcvars32.bat")


def run_host(exe, root, env=None):
    e = dict(os.environ)
    e.update(env or {})
    r = subprocess.run([exe, root], capture_output=True, text=True, env=e)
    served = {}
    status = None
    for ln in r.stdout.splitlines():
        if ln.startswith("SERVED "):
            _, rel, path = ln.split(" ", 2)
            served[rel.lower()] = path
        elif ln.startswith("STATUS "):
            p = ln.split(" ", 2)
            status = (int(p[1]), p[2] if len(p) > 2 else "")
    return r.stdout, served, status


# ------------------------------------------------------------------ cases
def make_root(base, name, stock, overlay_src, player=None, ours=None, rels=(BUILDFAM, SYSPAK, RULES)):
    root = os.path.join(base, name)
    if os.path.isdir(root):
        shutil.rmtree(root)
    for rel in rels:
        sb = rd(os.path.join(stock, rel))
        ob = rd(os.path.join(overlay_src, "mods", "netmod", "overlay", rel))
        pb = sb
        for f in (player or {}).get(rel, []):
            pb = f(pb)
        for f in (ours or {}).get(rel, []):
            ob = f(ob)
        wr(os.path.join(root, rel), pb)
        wr(os.path.join(root, "mods", "netmod", "overlay", rel), ob)
    overlay_base.write(root, stock=stock)
    return root


def served_bytes(root, served, rel):
    p = served.get(rel.lower())
    return rd(p) if p else rd(os.path.join(root, "mods", "netmod", "overlay", rel))


def fam_text(d, inst):
    return family(ixf_records(d), inst)[3].decode("latin1")


def pak_member(d, name):
    names, _o, _t, recs = syspak_parse.parse(d)
    low = [x.lower() for x in names]
    return recs[low.index(name.lower())]["lines"] if name.lower() in low else None


def main(argv):
    ap = argparse.ArgumentParser()
    main_dir = find_main()
    ap.add_argument("--stock", default=os.path.join(main_dir, "original", "gog_2.0.949") if main_dir else None)
    ap.add_argument("--overlay", default=os.path.join(main_dir, "dev", "overlaymerge", "tree") if main_dir else None)
    ap.add_argument("--overlay-unpatched", default=os.path.join(main_dir, "stage", "src") if main_dir else None)
    ap.add_argument("--work", default=os.path.join(tempfile.gettempdir(), "ovmerge_test"))
    ap.add_argument("--make-mods")
    ap.add_argument("--undo-mods")
    ap.add_argument("--mods", default="farm,pak,rules")
    a = ap.parse_args(argv)

    if a.make_mods or a.undo_mods:
        tree = a.make_mods or a.undo_mods
        for m in a.mods.split(","):
            rel, f = MODS[m]
            dst = os.path.join(tree, rel)
            keep = dst + ".ovmerge-orig"                 # the tree's own file, put back by --undo-mods
            extra = os.path.join(tree, FARM_IXF) if m == "pak" else None
            if a.undo_mods:
                if os.path.isfile(keep):
                    wr(dst, rd(keep))
                    os.remove(keep)
                    print("%-5s %s put back" % (m, rel))
                if extra and os.path.isfile(extra):
                    os.remove(extra)
                continue
            if not os.path.isfile(keep):
                wr(keep, rd(dst))
            new = f(rd(keep))
            wr(dst, new)
            print("%-5s %s written (%d bytes, sha256 %s)" % (m, rel, len(new), hashlib.sha256(new).hexdigest()[:16]))
            if extra:                                    # the file the new [DBSegments] row names, so the game opens it
                wr(extra, ixf_write([[0x0FA4A000, 1, 0x2026960B, struct.pack("<I", 13) + b"ovmerge test!"]], 8))
                print("      %s written (the new [DBSegments] row's segment)" % FARM_IXF)
        return 0

    os.makedirs(a.work, exist_ok=True)
    exe, warn = build_host(a.work)
    results = []

    def check(name, ok, detail=""):
        results.append((name, ok))
        print("[%d/%d] %s %s%s" % (len(results), NCHECKS, name, "PASS" if ok else "FAIL", "" if ok else "  " + detail))

    print("host built: %s%s" % (exe, ("  warnings: %s" % warn) if warn else ""))
    st = a.stock
    ov = a.overlay
    stock_fam = fam_text(rd(os.path.join(st, BUILDFAM)), 25)
    our_fam = fam_text(rd(os.path.join(ov, "mods", "netmod", "overlay", BUILDFAM)), 25)
    our_count = int(re.search(r"BuildingCount: (\d+)", our_fam).group(1))
    our_pak = rd(os.path.join(ov, "mods", "netmod", "overlay", SYSPAK))

    # 1. stock game files: nothing merged, overlay served as before
    root = make_root(a.work, "c1_stock", st, ov)
    log, served, status = run_host(exe, root)
    check("stock: nothing merged", not served and status == (0, ""), log[-600:])
    check("stock: log says 3 stock", "3 stock, 0 merged" in log, log[-400:])

    # 2. farm mod on BUILDFAM
    root = make_root(a.work, "c2_farm", st, ov, player={BUILDFAM: [farm_mod]})
    log, served, status = run_host(exe, root)
    d = served_bytes(root, served, BUILDFAM)
    t = fam_text(d, 25)
    ok = (BUILDFAM.lower() in served and "Key: 1406,545184782,5000,60" in t and "5003,0" in t and "545184782,5011," not in t
          and "BuildingCount: %d" % (our_count - 1) in t and t.count("[set ") == our_fam.count("[set "))
    check("farm: family 25 = ours + the farm edits, count %d" % (our_count - 1), ok, t)
    check("farm: new family record added", NEW_FAM in [r[1] for r in ixf_records(d) if r[0] == FAM_GROUP], "")
    others = [r for r in ixf_records(d) if r[0] == FAM_GROUP and r[1] not in (25, NEW_FAM)]
    our_others = [r for r in ixf_records(rd(os.path.join(ov, "mods", "netmod", "overlay", BUILDFAM)))
                  if r[0] == FAM_GROUP and r[1] not in (25,)]
    check("farm: the other 30 families are ours byte for byte", [r[3] for r in others] == [r[3] for r in our_others])
    check("farm: no warning", status == (0, ""), str(status))
    # order: the windmill line sits where the stock one was (after the style-mix lines, before Hans Silo)
    i60, i03 = t.find("5000,60"), t.find("5003,0")
    check("farm: changed lines keep their place", 0 < i60 and 0 < i03 and t.find("1505063") < t.find("545184782,5063,1"), t)

    # 3. SYS.PAK ini edits
    root = make_root(a.work, "c3_pak", st, ov, player={SYSPAK: [pak_mod]})
    log, served, status = run_host(exe, root)
    d = served_bytes(root, served, SYSPAK)
    z = pak_member(d, "SC3ZoneLayer.ini")
    df = pak_member(d, "Default.ini")
    od = pak_member(our_pak, "Default.ini")
    check("pak: zone line from theirs", z is not None and any("9300,A,1,125,1" in x for x in z), str(z and z[:12]))
    check("pak: DBSegments row added, ours kept",
          df is not None and DBROW in df and all(x in df for x in od) and df.index(DBROW) < df.index("[ResourceFactories]"),
          str(df and df[-30:]))
    check("pak: new member added", pak_member(d, "FarmMod.ini") == ["[Admin]", "Name=Farm mod test", "Enabled=ON"])
    names_o = syspak_parse.parse(our_pak)[0]
    names_d = syspak_parse.parse(d)[0]
    same = all(pak_member(d, n) == pak_member(our_pak, n) for n in names_o if n not in ("SC3ZoneLayer.ini", "Default.ini"))
    check("pak: every other member is ours", same and len(names_d) == len(names_o) + 1)
    check("pak: rebuilt archive round-trips", syspak_parse.build(names_d, [r["lines"] for r in syspak_parse.parse(d)[3]]) == d)

    # 4. community patch: both copies patched (what community_patch.ps1 does) -> nothing to merge, no warning
    root = make_root(a.work, "c4_community", st, ov, player={SYSPAK: [community_pak]}, ours={SYSPAK: [community_pak]})
    log, served, status = run_host(exe, root)
    check("community: overlay served, no warning", SYSPAK.lower() not in served and status == (0, ""), log[-600:])
    check("community: logged as already in the overlay", "already has it" in log, log[-600:])

    # 5. community patched Apps only (a player ran an OLD community_patch.ps1 that only knew Apps\Sys\SYS.PAK), against
    #    the overlay as the release zip ships it (stage\src, no community lines)
    root = make_root(a.work, "c5_community_apps_only", st, a.overlay_unpatched, player={SYSPAK: [community_pak]})
    log, served, status = run_host(exe, root)
    d = served_bytes(root, served, SYSPAK)
    pe = pak_member(d, "PetitionerExtraInfo.ini")
    pm = pak_member(d, "PetitionerManager.ini")
    ok_pe = pe is not None and all(x in pe for x in ("0x000000D9=19,2", "0x000000DA=19,2", "0x000000DB=19,2"))
    base_pm = [x for x in pak_member(rd(os.path.join(st, SYSPAK)), "PetitionerManager.ini") if x.startswith("NumberOf")][0]
    want_pm = "NumberOfPetitionerMessages=%d" % (int(base_pm.split("=")[1]) + 2)
    check("community (Apps only, zip overlay): petition lines + count merged", SYSPAK.lower() in served and ok_pe
          and want_pm in pm and status == (0, ""), str(status) + " " + str(pm))

    # 6. overlay already patched by us (bat_growables-like line in family 25) + the farm mod
    root = make_root(a.work, "c6_ours_patched", st, ov, player={BUILDFAM: [farm_mod]}, ours={BUILDFAM: [bat_like]})
    log, served, status = run_host(exe, root)
    t = fam_text(served_bytes(root, served, BUILDFAM), 25)
    check("ours patched + farm: both kept, count %d" % our_count,
          "37000,5" in t and "5000,60" in t and "545184782,5011," not in t and "BuildingCount: %d" % our_count in t, t)

    # 7. a conflict: theirs and ours change the same line differently
    def conflict(d):
        r = ixf_records(d)
        f = family(r, 25)
        f[3] = f[3].replace(b"5062,1 ", b"5062,7 ")
        return ixf_write(r, ixf_slots(d))

    def conflict_ours(d):
        r = ixf_records(d)
        f = family(r, 25)
        f[3] = f[3].replace(b"5062,1 ", b"5062,3 ")
        return ixf_write(r, ixf_slots(d))
    root = make_root(a.work, "c7_conflict", st, ov, player={BUILDFAM: [conflict]}, ours={BUILDFAM: [conflict_ours]})
    log, served, status = run_host(exe, root)
    t = fam_text(served_bytes(root, served, BUILDFAM), 25)
    check("conflict: ours kept, warned", "5062,3" in t and "5062,7" not in t and t.count("545184782,5062,") == 1 and status and status[0] == 1
          and "BUILDFAM.IXF" in status[1], str(status))

    # 8. TilingRules edit: not mergeable, warned
    root = make_root(a.work, "c8_rules", st, ov, player={RULES: [rules_mod]})
    log, served, status = run_host(exe, root)
    check("rules: warned, overlay served", RULES.lower() not in served and status == (1, "ROAD_GRND_Set.txt"), str(status))

    # 9. all three at once
    root = make_root(a.work, "c9_all", st, ov, player={BUILDFAM: [farm_mod], SYSPAK: [pak_mod], RULES: [rules_mod]})
    log, served, status = run_host(exe, root)
    check("all: 2 merged, 1 warned", len(served) == 2 and status == (1, "ROAD_GRND_Set.txt"), str(status))

    # 10. switch off
    log, served, status = run_host(exe, root, {"SC3NETMOD_OVMERGE": "0"})
    check("SC3NETMOD_OVMERGE=0: nothing merged, nothing checked", not served and status == (0, "") and "off" in log)

    # 11. no base file: nothing checked
    os.remove(os.path.join(root, "mods", "netmod", "overlay_base.txt"))
    log, served, status = run_host(exe, root)
    check("no overlay_base.txt: not checked", not served and status == (0, "") and "not checked" in log)

    bad = [n for n, ok in results if not ok]
    print("%d/%d passed%s" % (len(results) - len(bad), len(results), "" if not bad else "; FAILED: " + ", ".join(bad)))
    return 1 if bad else 0


NCHECKS = 21

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
