#!/usr/bin/env python3
r"""suite.py - task suitespeed (2026-11-20): the runner behind run_all.sh (every check of the building importer's page
against the Python tools). run_all.sh only calls this; its arguments and env switches are the same as before.

    test-slot bash re/tools/bldimport/webtest/run_all.sh <work dir> <pristine game tree> <stage\kits> \
        [<SC4 .zip> <the same SC4 download unpacked> [<folder with more SC4 zips>]]

Env switches (old ones kept: SC4INSTALL, BLD1999, BLDSIDE, SC3PACK_PACKS, PY):
  SUITE_DEEP=1      releases: the whole SC4 install (113 civic / park / reward / landmark buildings, and the page step
                    with the shops, offices, industry and farms box ticked, 423 cards) instead of the fixed install set
                    of sc4_install_set.json, and a fresh Python reference (as SUITE_REBUILD=1). Every check of the
                    suite before 2026-11-20 runs in this mode.
  SUITE_REBUILD=1   build every Python reference again, even when its key is unchanged
  SUITE_CHANGED=<ref>  run only the steps that the files changed since <ref> can affect (git diff <merge base> +
                    untracked files, ignored new files under re/tools and docs included; SUITE_CHANGED=1 means main).
                    SUITE_CHANGED=files:<path>,<path> gives the changed files by hand. Files the map (RULES) does not
                    know run everything. The skipped steps and why are printed first.
  SUITE_JOBS=<n>    independent groups side by side (default 4; 1 = one after the other, in the old order)
  SUITE_SETUPS=<n>  at most n Python reference builds at the same time (default: no limit beyond SUITE_JOBS)
  SUITE_ONLY=<regex>  debugging: only the steps whose name matches (and their group's setup steps)
  SUITE_LIST=1      print the plan (steps, groups, what a changed-files run skips) and run nothing

The Python reference cache: each setup step (golden_setup.py, sc4_*_setup.py, sc3pack_*.py: the Python side the page
must equal) runs with suite_trace/sitecustomize.py, which records every file its processes read (code and data), every
folder they list, and every file they write. After a passing build, <work>/.suite_cache/<step>.json keeps the step's
command line, a sha256 of every repo file read (size + mtime for files outside the repo: the game tree, the SC4 files,
Python's own library), the listings, and size + mtime of every file it wrote. The next run skips the build when all of
them are unchanged and the outputs are still there as written; the check steps (the page side) always run, byte for
byte as before. Any change, a missing output or SUITE_REBUILD rebuilds.

Output: steps print "[N/M] name (t s) PASS|FAIL" as before, each after its own output, in the same order as the old
run_all.sh whatever the groups' timing (a step's lines are held until the steps before it are printed), then
"<k> of <M> steps passed". Exit code = the number of failed steps.
"""
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BLD = os.path.dirname(HERE)                       # re/tools/bldimport
TOOLS = os.path.dirname(BLD)                      # re/tools
REPO = os.path.dirname(os.path.dirname(TOOLS))
TRACE = os.path.join(HERE, "suite_trace")
SET_FILE = os.path.join(HERE, "sc4_install_set.json")


def winpath(p):
    """'/c/Users/..' (a Git Bash path that reached us unconverted) -> 'C:/Users/..'."""
    if p and re.match(r"^/[a-zA-Z]/", p):
        return p[1].upper() + ":" + p[2:]
    return p


def env_on(k):
    return os.environ.get(k, "") not in ("", "0")


# ------------------------------------------------------------------------------------------------- changed-files map
# (regex on the repo-relative path, tags). First match wins. Tags name the code a step depends on; a step runs when a
# changed file's tags meet its own. "all" runs everything, "none" nothing.
RULES = [
    (r"re/tools/bldimport/webtest/(run_all\.sh|suite\.py|suite_trace/.*|nodefs\.mjs|chrome\.mjs)$", {"all"}),
    (r"re/tools/bldimport/webtest/sc4_set_cover\.py$", {"none"}),          # evidence tool, the suite never runs it
    (r"re/tools/bldimport/webtest/pagetest\.(js|mjs)$", {"page"}),
    (r"re/tools/bldimport/webtest/(golden_setup\.py|golden\.mjs|install_golden\.mjs|zip_golden\.mjs)$", {"bld"}),
    (r"re/tools/bldimport/webtest/(sc3font_check\.py|fonts_inline\.mjs)$", {"fonts"}),
    (r"re/tools/bldimport/webtest/sc3pack_", {"pack"}),
    (r"re/tools/bldimport/webtest/sc4_install", {"install"}),
    (r"re/tools/bldimport/webtest/sc4_", {"sc4"}),
    (r"re/tools/bldimport/classifier\.html$", {"page", "css"}),          # the page, and its copy of sc3ui.css
    (r"re/tools/bldimport/(bldimport\.py|bldrender\.py|bldweb\.js|bldfile\.py|make_testmodels\.py|bld_js_check\.mjs)$",
     {"bld"}),
    (r"re/tools/bldimport/samples/", {"bld"}),
    (r"re/tools/bldimport/sc3plugin\.py$", {"bld", "pack"}),
    (r"re/tools/bldimport/sc3pack\.(py|js)$", {"pack"}),
    (r"re/tools/bldimport/(sc3font\.js|sc3font_test\.html)$", {"fonts"}),
    (r"re/tools/bldimport/sync_css\.py$", {"css"}),
    (r"re/tools/bldimport/check_roundtrip\.py$", {"page"}),
    (r"re/tools/bldimport/sc4web\.js$", {"sc4"}),
    (r"re/tools/sc4conv/", {"sc4"}),
    (r"re/tools/sc3ui/", {"fonts", "css"}),
    (r"re/tools/(batgrow|qfs|qfs_encode|sprite_render|syspak_parse)\.py$", {"bld", "pack"}),
    (r"re/tools/(netmod|bldbat)/", {"bld", "pack"}),
    (r"docs/assets/sc3ui\.css$", {"css"}),
    (r"docs/assets/fonts/", {"fonts"}),
    (r"docs/buildings/", {"css", "fonts"}),                  # the published importer copy (sync_css / sc3font_check)
    (r"docs/", {"none"}),                                    # the gallery, README pictures
    (r"(re/sessions|re/analysis|re/harness|re/community|re/scripts|verify|codemap|log)/", {"none"}),
    (r"[^/]*\.md$", {"none"}),
    (r"functions\.csv$", {"none"}),
]
TAG_TEXT = {"page": "the page (classifier.html, its test hook)", "css": "sc3ui.css and its copies",
            "fonts": "the game fonts (sc3font.js, build_fonts.mjs, docs/assets/fonts)", "pack": "the pack reader",
            "bld": "bldimport.py / bldrender.py / bldweb.js", "sc4": "sc4conv.py / sc4web.js", "install": "the SC4 install"}


def git(*a):
    return subprocess.run(["git", "-C", REPO] + list(a), capture_output=True, text=True, check=True,
                          encoding="utf-8", errors="replace").stdout


def changed_files(ref):
    base = git("merge-base", ref, "HEAD").strip()
    files = set(git("diff", "--name-only", base).splitlines())
    files |= set(git("ls-files", "--others", "--exclude-standard").splitlines())
    # the .gitignore is deny-by-default: a new tool file stays ignored until `git add -f`, so look for those too
    files |= {f for f in git("ls-files", "--others", "--ignored", "--exclude-standard", "--", "re/tools", "docs").splitlines()
              if "__pycache__" not in f and not f.endswith(".pyc")}
    return base, sorted(f for f in files if f)


CSS_BLOCK = re.compile(r"/\* ==== sc3ui\.css begin .*?/\* ==== sc3ui\.css end ==== \*/", re.S)


def css_copy_only(path, base):
    """True when the page changed only inside its copy of sc3ui.css (sync_css.py markers): then only the CSS steps."""
    if base is None:
        return False
    try:
        old = git("show", "%s:%s" % (base, path))
        new = open(os.path.join(REPO, path), encoding="utf-8", newline="").read()
    except (subprocess.CalledProcessError, OSError):
        return False
    strip = lambda t: CSS_BLOCK.sub("", t.replace("\r\n", "\n"))
    return CSS_BLOCK.search(new) is not None and strip(old) == strip(new)


def tags_of(path, records, base=None):
    if path in ("re/tools/bldimport/classifier.html", "docs/buildings/importer/index.html") and css_copy_only(path, base):
        return {"css"}, "only its copy of sc3ui.css changed (between the sync_css.py markers)"
    for rx, tags in RULES:
        if re.match(rx, path):
            return tags, "rule " + rx
    if path.startswith("re/tools/") and path.endswith(".py"):
        # any other Python tool: the setup steps' last builds say whether they read it
        if not records:
            return {"all"}, "a Python tool and no Python reference record to look it up in"
        absp = os.path.normcase(os.path.join(REPO, path))
        users = [s for s, r in records.items() if absp in r]
        if users:
            return {"all"}, "read by " + ", ".join(users)
        return {"none"}, "read by none of the %d Python reference builds on record" % len(records)
    return {"all"}, "not in the map"


# ------------------------------------------------------------------------------------------------- the steps
# a group that reads another group's setup output starts once that setup step is done (the page tests of the golden
# cases need golden_setup's folders, not golden.mjs / install_golden.mjs, which run beside them)
AFTER = {"sc3page": "golden_setup"}


class Step:
    def __init__(self, name, lane, tags, cmds, setup=False, key=None):
        self.name, self.lane, self.tags, self.cmds, self.setup = name, lane, set(tags), cmds, setup
        self.key = key or re.sub(r"[^A-Za-z0-9]+", "_", name.split(" (")[0]).strip("_")[:60]
        # the steps that hand the SC4 install's .dat files (0.7 GB) or the BSC pack to Chrome as Blobs are the suite's
        # memory peak (serial runs reached the 6 GB test-slot cap on 2026-11-20): never two of them at once
        flat = " ".join(" ".join(c["cmd"] if isinstance(c, dict) else c) for c in cmds)
        self.heavy = "pagetest.mjs" in flat and any(k in flat for k in ("--sc4install", "--sc4with", "--sc4remember", "--sc4deps"))
        # the page with the whole install AND its 310 growables: Chrome's renderer alone holds 3.7 GB, and beside the
        # other groups the deep run of 2026-11-21 reached the 6 GB cap and the page stalled. It runs alone.
        self.alone = "pagetest.mjs" in flat and "--sc4grow" in flat


def steps_for(a, py, node):
    work, game, kits, sc4zip, sc4dir, sc4packs, packs = a
    deep = env_on("SUITE_DEEP")
    inst = winpath(os.environ.get("SC4INSTALL", ""))
    b1999 = winpath(os.environ.get("BLD1999", ""))
    bside = winpath(os.environ.get("BLDSIDE", ""))
    w = lambda *p: os.path.join(work, *p)
    h = lambda *p: os.path.join(HERE, *p)
    S = []
    add = lambda *x, **k: S.append(Step(*x, **k))
    PG = ["bld", "page"]
    add("golden_setup (bldimport.py pack, 10 cases)", "sc3", ["bld"], [py + [h("golden_setup.py"), "--game", game, "--kits", kits, "--out", work]], setup=True)
    add("golden.mjs (bldweb.js vs pack, every file + frame)", "sc3", ["bld"], [node + [h("golden.mjs"), "--golden", work, "--game", game, "--cases", "testmodels,bld,kenney,styles,ports,landmarks,civic,lotshape,sharp", "--frames"]])
    add("install_golden.mjs (install, re-install, restore)", "sc3", ["bld"], [node + [h("install_golden.mjs"), "--golden", work, "--game", game, "--case", "kenney"]])
    add("zip_golden.mjs (.zip route)", "sc3", ["bld"], [node + [h("zip_golden.mjs"), "--golden", work, "--game", game, "--case", "kenney"]])
    for c in ["kenney", "bld", "styles", "ports", "landmarks", "civic", "lotshape"]:
        add("pagetest.mjs %s (the page in headless Chrome)" % c, "sc3page", PG, [node + [h("pagetest.mjs"), "--golden", work, "--game", game, "--case", c]])
    add("pagetest.mjs landmarkdesc (the Description box typed in the page, installed = bldimport.py)", "sc3page", PG,
        [node + [h("pagetest.mjs"), "--golden", work, "--game", game, "--case", "landmarkdesc", "--edit-desc", "obelisk_2x2.obj=Typed in the page, Córdoba"]])
    blds = sorted(glob.glob(os.path.join(game, "Buildings", "*.bld")))
    add("bld_js_check.mjs (.bld reader, game's Buildings)", "bldread", ["bld"],
        [{"quiet": True, "cmd": py + [os.path.join(BLD, "bldfile.py"), "js-expect", "--out", w("bldexp.json"), os.path.join(game, "Buildings")]},
         node + [os.path.join(BLD, "bld_js_check.mjs"), w("bldexp.json")] + blds])
    add("bld_js_check.mjs --reader bldweb (.bld reader of the importer, game's Buildings)", "bldread", ["bld"],
        [node + [os.path.join(BLD, "bld_js_check.mjs"), "--reader", "bldweb", w("bldexp.json")] + blds])
    if b1999:
        b99 = sorted(glob.glob(os.path.join(b1999, "*.bld")))
        add("js-expect 1999 .bld", "bldread", ["bld"], [{"quiet": True, "cmd": py + [os.path.join(BLD, "bldfile.py"), "js-expect", "--out", w("bldexp1999.json"), b1999]}])
        add("bld_js_check.mjs --reader bldweb (1999 .bld)", "bldread", ["bld"], [node + [os.path.join(BLD, "bld_js_check.mjs"), "--reader", "bldweb", w("bldexp1999.json")] + b99])
        add("bld_js_check.mjs --reader page (1999 .bld, classifier.html)", "bldread", PG, [node + [os.path.join(BLD, "bld_js_check.mjs"), "--reader", "page", w("bldexp1999.json")] + b99])
        add("golden_setup bld1999", "sc3", ["bld"], [py + [h("golden_setup.py"), "--game", game, "--kits", kits, "--out", work, "--cases", "bld1999", "--bld1999", b1999]], setup=True)
        add("golden.mjs bld1999", "sc3", ["bld"], [node + [h("golden.mjs"), "--golden", work, "--game", game, "--cases", "bld1999", "--frames"]])
    if bside:
        add("golden_setup bldside", "sc3", ["bld"], [py + [h("golden_setup.py"), "--game", game, "--kits", kits, "--out", work, "--cases", "bldside", "--bldside", bside]], setup=True)
        add("golden.mjs bldside", "sc3", ["bld"], [node + [h("golden.mjs"), "--golden", work, "--game", game, "--cases", "bldside", "--frames"]])
        add("pagetest.mjs bldside (the page installs .bld files with bld_frames.ixf art)", "sc3", PG, [node + [h("pagetest.mjs"), "--golden", work, "--game", game, "--case", "bldside"]])
    add("check_roundtrip.py (models.json round trip in the page)", "page", ["page"], [py + [os.path.join(BLD, "check_roundtrip.py")]])
    add("sync_css.py --check (sc3ui.css copy in classifier.html)", "page", ["css"], [py + [os.path.join(BLD, "sync_css.py"), "--check"]])
    add("sc3font_check.py (game fonts built in the page + published web fonts, pixel for pixel)", "page", ["fonts", "css"], [py + [h("sc3font_check.py"), "--game", game, "--out", w("sc3font")]])
    add("build_fonts.mjs --check (docs/assets/fonts = a fresh build from the game's FBF files)", "page", ["fonts", "css"], [node + [os.path.join(TOOLS, "sc3ui", "build_fonts.mjs"), "--game", game, "--check"]])
    add("fonts_inline.mjs (importer: inline game fonts, light look under OS dark mode)", "page", ["fonts", "css", "page"], [node + [h("fonts_inline.mjs")]])
    tp = os.path.join(packs, "testpacks")
    add("sc3pack_testpacks.py (3 local test packs)", "pack", ["pack"], [py + [h("sc3pack_testpacks.py"), "--game", game, "--batpatch", os.path.join(packs, "maxis_batpatch_1999"), "--addons", os.path.join(packs, "maxis_addons_2000"), "--out", tp]], setup=True)
    add("sc3pack_golden.py (sc3pack.py reports, install, remove)", "pack", ["pack", "bld"],
        [py + [h("sc3pack_golden.py"), "--game", game, "--out", w("sc3pack"), "--install-pack", os.path.join(tp, "bld_parts.zip"), "--plugin-pack", os.path.join(packs, "maxis_addons_2000"),
               os.path.join(tp, "plain_bld.zip"), os.path.join(tp, "bld_parts.zip"), os.path.join(tp, "nested.zip"), os.path.join(packs, "maxis_addons_2000"), os.path.join(packs, "maxis_batpatch_1999"), os.path.join(game, "Buildings")]], setup=True)
    add("sc3pack_golden.mjs (sc3pack.js vs sc3pack.py: reports, install on a file list + a real folder)", "pack", ["pack", "bld"], [node + [h("sc3pack_golden.mjs"), "--golden", w("sc3pack"), "--game", game]])
    add("sc3pack_pagetest.mjs (the pack reader in headless Chrome)", "pack", ["pack", "page"], [node + [h("sc3pack_pagetest.mjs"), "--golden", w("sc3pack"), "--game", game]])
    S4 = ["sc4", "bld"]
    if sc4zip:
        add("golden_setup sc4 (sc4conv.py, rerun, bldimport.py pack)", "sc4dl", S4, [py + [h("golden_setup.py"), "--game", game, "--kits", kits, "--out", work, "--cases", "sc4", "--sc4", sc4dir]], setup=True)
        add("sc4_golden.mjs (sc4web.js: .zip + folder convert, rerun, pack, frames)", "sc4dl", S4, [node + [h("sc4_golden.mjs"), "--golden", work, "--game", game, "--zip", sc4zip, "--folder", sc4dir, "--frames"]])
        add("pagetest.mjs sc4 (the page opens the .zip, converts, installs)", "sc4dl", S4 + ["page"], [node + [h("pagetest.mjs"), "--golden", work, "--game", game, "--case", "sc4", "--sc4zip", sc4zip]])
    if sc4packs:
        add("sc4_packs_setup.py (sc4conv.py on the tower + 2 lot-only packs, bldimport.py pack)", "sc4packs", S4, [py + [h("sc4_packs_setup.py"), "--packs", sc4packs, "--game", game, "--out", w("sc4packs")]], setup=True)
        add("sc4_packs.mjs (sc4web.js: text exemplars, tiled tower, lot-only reports, pack, frames)", "sc4packs", S4, [node + [h("sc4_packs.mjs"), "--golden", w("sc4packs"), "--packs", sc4packs, "--game", game, "--frames"]])
        add("pagetest.mjs sc4empty diego (the page on a lot-only zip)", "sc4packs", S4 + ["page"],
            [node + [h("pagetest.mjs"), "--golden", work, "--game", game, "--case", "sc4empty", "--action", "open", "--no-compare", "--sc4zip", os.path.join(sc4packs, "DiegoDLGrowablePack2019_Vanilla_DN.zip"),
                     "--expect-empty", "555 California Street,Willoughby Tower,Salesforce Tower,https://community.simtropolis.com/files/file/32961-salesforce-tower/"]])
        add("pagetest.mjs sc4empty im (the page on a blank-model zip)", "sc4packs", S4 + ["page"],
            [node + [h("pagetest.mjs"), "--golden", work, "--game", game, "--case", "sc4empty", "--action", "open", "--no-compare", "--sc4zip", os.path.join(sc4packs, "I-M manufacturers lots.zip"),
                     "--expect-empty", "a blank placeholder building,1542-hanjin,1542-uniglory"]])
    bsc = ""
    if sc4packs and sc4zip:
        for f in sorted(glob.glob(os.path.join(sc4packs, "*Common Dependencies*.zip"))):
            bsc = f
    if bsc:
        add("sc4_props_setup.py (sc4conv.py --deps: JMyers lot props from the BSC pack, rerun, --no-props, bldimport.py pack)", "sc4props", S4,
            [py + [h("sc4_props_setup.py"), "--sc4", sc4dir, "--deps", bsc, "--game", game, "--out", w("sc4props")]], setup=True)
        add("sc4_props.mjs (sc4web.js: the BSC zip streamed, props baked, rerun switch, --no-props, pack, frames)", "sc4props", S4,
            [node + [h("sc4_props.mjs"), "--golden", w("sc4props"), "--game", game, "--zip", sc4zip, "--deps", bsc, "--frames"]])
    I4 = S4 + ["install"]
    if inst:
        if deep:
            add("sc4_install_setup.py (sc4conv.py on the SC4 install: civic, parks, rewards, landmarks; rerun; subset packed)", "install", I4,
                [py + [h("sc4_install_setup.py"), "--install", inst, "--game", game, "--out", w("sc4install_all")]], setup=True, key="sc4_install_setup_all")
            add("sc4_install.mjs (sc4web.js on the SC4 install by slices: files, kinds, rerun, subset pack, frames)", "install", I4,
                [node + [h("sc4_install.mjs"), "--golden", w("sc4install_all"), "--install", inst, "--game", game, "--frames"]])
            # sc4ci (2026-11-20): 113 cards, the Large High School converts since flat atlas pieces are left out (off: 6x6)
            # lotshape (2026-11-20): 82 on (73 before): rewards and landmarks keep their SC4 lot up to 5x5, and 5x5 is allowed
            add("pagetest.mjs sc4install (the page opens the install's .dat files: 113 cards, 82 on, read only)", "install", I4 + ["page"],
                [node + [h("pagetest.mjs"), "--golden", work, "--game", game, "--case", "sc4install", "--action", "open", "--sc4install", inst, "--expect-install", "113,82"]])
            # owner 2026-11-20: the page's "with shops, offices, industry and farms" box ticked: 310 more cards, all off
            add("pagetest.mjs sc4install --sc4grow (the box ticked: 423 cards, the 310 growables off, 82 on)", "install", I4 + ["page"],
                [node + [h("pagetest.mjs"), "--golden", work, "--game", game, "--case", "sc4install", "--action", "open", "--sc4install", inst, "--expect-install", "423,82", "--sc4grow", "--expect-grow", "310"]])
        else:
            st = json.load(open(SET_FILE, encoding="utf-8"))
            n, on = st["expect"]["cards"], st["expect"]["on"]
            only = ",".join(b["exemplar"] for b in st["buildings"])
            add("sc4_install_setup.py --set (sc4conv.py on the install set: %d buildings, every path; rerun; subset packed)" % len(st["buildings"]), "install", I4,
                [py + [h("sc4_install_setup.py"), "--install", inst, "--game", game, "--out", w("sc4install"), "--set", SET_FILE]], setup=True)
            add("sc4_install.mjs --set (sc4web.js on the install set by slices: files, kinds, rerun, subset pack, frames)", "install", I4,
                [node + [h("sc4_install.mjs"), "--golden", w("sc4install"), "--install", inst, "--game", game, "--frames", "--set", SET_FILE]])
            add("pagetest.mjs sc4install --set (the page opens the install's .dat files, the set: %d cards, %d on, read only)" % (n, on), "install", I4 + ["page"],
                [node + [h("pagetest.mjs"), "--golden", work, "--game", game, "--case", "sc4install", "--action", "open", "--sc4install", inst, "--expect-install", "%d,%d" % (n, on), "--sc4only", only]])
    if inst and bsc:
        add("sc4_baseprops_setup.py (sc4conv.py --sc4: JMyers with SC4's own props, with and without the BSC pack, bldimport.py pack)", "baseprops", I4,
            [py + [h("sc4_baseprops_setup.py"), "--sc4", sc4dir, "--deps", bsc, "--install", inst, "--game", game, "--out", w("sc4baseprops")]], setup=True)
        add("sc4_baseprops.mjs (sc4web.js: the install picked with the download and remembered, by slices; files, pack, frames)", "baseprops", I4,
            [node + [h("sc4_baseprops.mjs"), "--golden", w("sc4baseprops"), "--game", game, "--zip", sc4zip, "--deps", bsc, "--install", inst, "--frames"]])
        add("pagetest.mjs sc4baseprops_inst --sc4with (the page: the game's .dat files picked with the .zip, installed)", "baseprops", I4 + ["page"],
            [node + [h("pagetest.mjs"), "--golden", w("sc4baseprops"), "--game", game, "--case", "sc4baseprops_inst", "--sc4zip", sc4zip, "--sc4with", inst]])
        add("pagetest.mjs sc4baseprops_inst --sc4remember (the page: Open SC4 game first, then the .zip alone, installed)", "baseprops", I4 + ["page"],
            [node + [h("pagetest.mjs"), "--golden", w("sc4baseprops"), "--game", game, "--case", "sc4baseprops_inst", "--sc4zip", sc4zip, "--sc4remember", inst]])
        add("sc4_lottex_setup.py (sc4conv.py: JMyers lot textures from the download, BSC, install, both; --no-textures; rerun switches; bldimport.py pack)", "lottex", I4,
            [py + [h("sc4_lottex_setup.py"), "--sc4", sc4dir, "--deps", bsc, "--install", inst, "--game", game, "--out", w("sc4lottex")]], setup=True)
        add("sc4_lottex.mjs (sc4web.js: lot textures per source set, every file, --no-textures, rerun switches, pack, frames)", "lottex", I4,
            [node + [h("sc4_lottex.mjs"), "--golden", w("sc4lottex"), "--game", game, "--zip", sc4zip, "--deps", bsc, "--install", inst, "--frames"]])
    return S


# ------------------------------------------------------------------------------------------------- the Python reference cache
def norm(p):
    return os.path.normcase(os.path.abspath(p))


REPO_N = norm(REPO) + os.sep


def source_of(p):
    """A module's .pyc stands for its .py: the .pyc on disk is only rewritten when the module is imported again."""
    d, f = os.path.split(p)
    if os.path.basename(d).lower() == "__pycache__" and f.lower().endswith(".pyc"):
        src = os.path.join(os.path.dirname(d), f.split(".")[0] + ".py")
        if os.path.isfile(src):
            return src
    return p


def file_sig(p):
    try:
        st = os.stat(p)
    except OSError:
        return "missing"
    if os.path.isdir(p):
        return "dir"
    if norm(p).startswith(REPO_N):
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for b in iter(lambda: fh.read(1 << 20), b""):
                h.update(b)
        return "sha:" + h.hexdigest()
    return "st:%d:%d" % (st.st_size, st.st_mtime_ns)


def list_sig(p):
    try:
        return "ls:" + hashlib.sha256("\n".join(sorted(os.listdir(p))).encode("utf-8", "surrogatepass")).hexdigest()
    except OSError:
        return "missing"


def out_sig(p):
    try:
        st = os.stat(p)
    except OSError:
        return None
    return [st.st_size, st.st_mtime_ns]


class Cache:
    def __init__(self, work):
        self.dir = os.path.join(work, ".suite_cache")
        os.makedirs(self.dir, exist_ok=True)

    def path(self, step):
        return os.path.join(self.dir, step.key + ".json")

    def records(self):
        """step key -> set of the repo files its last passing build read (for the changed-files map)"""
        out = {}
        for p in glob.glob(os.path.join(self.dir, "*.json")):
            try:
                r = json.load(open(p, encoding="utf-8"))
                out[os.path.basename(p)[:-5]] = {norm(x) for x in r["reads"]}
            except (OSError, ValueError, KeyError):
                pass
        return out

    def check(self, step, cmds):
        """-> (True, note) when the last passing build still stands, else (False, why)"""
        try:
            r = json.load(open(self.path(step), encoding="utf-8"))
        except (OSError, ValueError):
            return False, "no record of a passing build"
        if r.get("cmds") != cmds:
            return False, "the command line changed"
        if r.get("python") != sys.version:
            return False, "another Python"
        for p, s in r["reads"].items():
            now = file_sig(p)
            if now != s:
                return False, "changed: %s (%s -> %s)" % (p, s[:40], now[:40])
        for p, s in r["lists"].items():
            if list_sig(p) != s:
                return False, "folder listing changed: " + p
        for p, s in r["writes"].items():
            if out_sig(p) != s:
                return False, "output changed or gone: " + p
        nrepo = sum(1 for p in r["reads"] if norm(p).startswith(REPO_N))
        return True, ("Python reference unchanged: %d repo files (code + data) by sha256, %d other inputs, %d listings, "
                      "%d outputs as written; key %s, built %s (SUITE_REBUILD=1 builds it again)"
                      % (nrepo, len(r["reads"]) - nrepo, len(r["lists"]), len(r["writes"]), r["key"][:12], r["built"]))

    def trace_env(self, step):
        td = os.path.join(self.dir, "trace_" + step.key)
        shutil.rmtree(td, ignore_errors=True)
        os.makedirs(td)
        env = dict(os.environ, SUITE_TRACE=td, PYTHONPATH=TRACE + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else ""))
        return td, env

    def store(self, step, cmds, td):
        R, W, L = set(), set(), set()
        for f in glob.glob(os.path.join(td, "*.txt")):
            for ln in open(f, encoding="utf-8", errors="replace"):
                k, _, p = ln.rstrip("\n").partition(" ")
                {"r": R, "w": W, "l": L}.get(k, set()).add(p)
        shutil.rmtree(td, ignore_errors=True)
        Wn = {norm(p) for p in W}
        reads = {}
        for p in sorted(R):
            p = source_of(p)
            if norm(p) in Wn or os.path.isdir(p):
                continue
            reads[p] = file_sig(p)
        for c in cmds:                    # the scripts named on the command line, whatever the tracer saw
            for x in (c["cmd"] if isinstance(c, dict) else c)[1:2]:
                if x.endswith(".py"):
                    reads[x] = file_sig(x)
        lists = {p: list_sig(p) for p in sorted(L)}
        writes = {}
        for p in sorted(W):
            s = out_sig(p)
            if s is not None and os.path.isfile(p):
                writes[p] = s
        key = hashlib.sha256(json.dumps([cmds, sys.version, reads, lists], sort_keys=True).encode()).hexdigest()
        rec = {"step": step.name, "cmds": cmds, "python": sys.version, "key": key, "built": time.strftime("%Y-%m-%d %H:%M"),
               "reads": reads, "lists": lists, "writes": writes}
        tmp = self.path(step) + ".tmp"
        json.dump(rec, open(tmp, "w", encoding="utf-8"), indent=0)
        os.replace(tmp, self.path(step))
        nrepo = sum(1 for p in reads if norm(p).startswith(REPO_N))
        return "Python reference built and recorded: %d repo files, %d other inputs, %d listings, %d outputs; key %s" % (
            nrepo, len(reads) - nrepo, len(lists), len(writes), key[:12])

    def drop(self, step):
        try:
            os.remove(self.path(step))
        except OSError:
            pass


# ------------------------------------------------------------------------------------------------- running
HEAVY = threading.Lock()


class Alone:
    """Steps share the machine; a step marked alone waits until no other step runs, and no step starts beside it."""
    def __init__(self):
        self.c, self.n, self.want = threading.Condition(), 0, 0

    def shared(self):
        with self.c:
            while self.want:
                self.c.wait()
            self.n += 1

    def unshare(self):
        with self.c:
            self.n -= 1
            self.c.notify_all()

    def alone(self):
        with self.c:
            self.want += 1
            while self.n:
                self.c.wait()

    def done(self):
        with self.c:
            self.want -= 1
            self.c.notify_all()


ALONE = Alone()
# the Python references use several cores each (numpy, OpenBLAS's own threads, left alone: their count can change the
# summation order the byte-for-byte checks depend on). SUITE_SETUPS=<n> limits how many build at once; default no limit
# beyond SUITE_JOBS (measured 2026-11-20 on a quiet PC: 4 at once, golden_setup 283 s against 207 s alone, a net gain).
SETUPS = threading.Semaphore(max(1, int(os.environ.get("SUITE_SETUPS", "0") or 0) or 64))


def run_step(step, cache, rebuild):
    if step.alone:
        ALONE.alone()
        try:
            return run_step_(step, cache, rebuild)
        finally:
            ALONE.done()
    ALONE.shared()
    try:
        if step.setup:
            with SETUPS:
                return run_step_(step, cache, rebuild)
        if step.heavy:
            with HEAVY:
                return run_step_(step, cache, rebuild)
        return run_step_(step, cache, rebuild)
    finally:
        ALONE.unshare()


def run_step_(step, cache, rebuild):
    t0 = time.time()
    out = []
    ok = True
    td = None
    env = None
    if step.setup and cache is not None:
        if not rebuild:
            hit, note = cache.check(step, step.cmds)
            if hit:
                return True, ("  cached: " + note + "\n").encode("utf-8"), time.time() - t0
            out.append(("  rebuild: " + note + "\n").encode("utf-8"))
        else:
            out.append(b"  rebuild: SUITE_REBUILD / SUITE_DEEP\n")
        cache.drop(step)
        td, env = cache.trace_env(step)
    for c in step.cmds:
        quiet = isinstance(c, dict) and c.get("quiet")
        argv = c["cmd"] if isinstance(c, dict) else c
        try:
            # output to a file, not a pipe: a pipe is only done when every holder closed it, and a Chrome child of a
            # page test can hold it after its parent exited (steps of 2 s took 200 s that way); like bash, only the
            # process's own exit counts
            with tempfile.TemporaryFile() as fh:
                rc = subprocess.run(argv, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env).returncode
                fh.seek(0)
                text = fh.read()                 # bytes, passed through as bash did
        except OSError as e:
            text, rc = ("  %s: %s\n" % (argv[0], e)).encode("utf-8"), 1
        if quiet:
            # the old step sent this command's stdout to /dev/null; keep its error lines when it fails
            text = text if rc else b""
        out.append(text.replace(b"\r\n", b"\n"))
        if rc:
            ok = False
            break
    if td is not None:
        if ok:
            try:
                out.append(("  " + cache.store(step, step.cmds, td) + "\n").encode("utf-8"))
            except Exception as e:     # a record that cannot be written only costs a rebuild next time
                out.append(("  cache record not written: %s\n" % e).encode("utf-8"))
                cache.drop(step)
        else:
            shutil.rmtree(td, ignore_errors=True)
    return ok, b"".join(out), time.time() - t0


def main(argv):
    sys.stdout.reconfigure(errors="replace")
    if len(argv) < 4:
        print(__doc__)
        return 2
    work, game, kits = (os.path.abspath(winpath(x)) for x in argv[1:4])
    sc4zip, sc4dir, sc4packs = (os.path.abspath(winpath(x)) if x else "" for x in (argv[4:] + ["", "", ""])[:3])
    packs = winpath(os.environ.get("SC3PACK_PACKS", "")) or os.path.join(REPO, "stage", "st_packs")
    if not os.environ.get("SC3PACK_PACKS") and not os.path.isdir(packs):
        # in a dev worktree (dev\<name>\wt) the default is dev\<name>\wt\stage, which never exists: the main checkout's
        # stage, found through git's common dir (MAIN\.git)
        try:
            common = subprocess.run(["git", "-C", HERE, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                    capture_output=True, text=True).stdout.strip()
            if common and os.path.isdir(os.path.join(os.path.dirname(common), "stage", "st_packs")):
                packs = os.path.join(os.path.dirname(common), "stage", "st_packs")
        except OSError:
            pass
    os.makedirs(work, exist_ok=True)
    py = [sys.executable]                 # run_all.sh starts this file with its $py (py -3.12): the same Python
    node = ["node"]
    deep = env_on("SUITE_DEEP")
    rebuild = deep or env_on("SUITE_REBUILD")
    if os.environ.get("SUITE_REBUILD") == "0":
        rebuild = False
    steps = steps_for((work, game, kits, sc4zip, sc4dir, sc4packs, packs), py, node)
    cache = Cache(work)
    t_all = time.time()
    mode = ["deep (whole SC4 install, fresh Python reference)" if deep else "normal (the SC4 install set)"]
    if rebuild and not deep:
        mode.append("Python reference rebuilt")
    run = steps
    ch = os.environ.get("SUITE_CHANGED", "")
    if ch and ch != "0":
        if ch.startswith("files:"):        # the changed files given by hand (comma list, repo-relative), against HEAD
            ref, base = "HEAD (files given)", git("rev-parse", "HEAD").strip()
            files = sorted(x.strip().replace("\\", "/") for x in ch[6:].split(",") if x.strip())
        else:
            ref = "main" if ch == "1" else ch
            base, files = changed_files(ref)
        recs = cache.records()
        want, why = set(), []
        for f in files:
            t, how = tags_of(f, recs, base)
            want |= t
            why.append("  changed %s -> %s (%s)" % (f, ",".join(sorted(t)), how))
        mode.append("changed files since %s (merge base %s): %d files" % (ref, base[:9], len(files)))
        print("[suite] " + "; ".join(mode))
        for ln in why:
            print(ln)
        if "all" in want:
            print("  a file outside the map or one that every step uses: every step runs")
        else:
            run = [s for s in steps if s.tags & want]
            # a check runs on its group's setup output: keep that setup step too (it is skipped by its cache when
            # nothing it reads changed)
            lanes_run = {s.lane for s in run}
            need = {AFTER[l] for l in lanes_run if l in AFTER}
            run = [s for s in steps if s in run or (s.setup and (s.lane in lanes_run or s.key in need))]
            for s in steps:
                if s not in run:
                    print("  skipped: %s  (uses %s; none of them changed)" % (s.name, ", ".join(TAG_TEXT.get(t, t) for t in sorted(s.tags))))
    else:
        print("[suite] " + "; ".join(mode))
    if os.environ.get("SUITE_ONLY"):      # debugging: the steps whose name matches, with their group's setup steps
        rx = re.compile(os.environ["SUITE_ONLY"])
        pick = [s for s in run if rx.search(s.name)]
        need = {AFTER[p.lane] for p in pick if p.lane in AFTER}
        run = [s for s in run if s in pick or (s.setup and (s.lane in {p.lane for p in pick} or s.key in need))]
        print("[suite] SUITE_ONLY=%s: %d steps" % (rx.pattern, len(run)))
    if deep and float(os.environ.get("PROYECTOS_TEST_MEM_GB", "8") or 8) < 8:
        # the page with the whole install + 310 growables peaks at 5.3-5.4 GB on its own (serial run 2026-11-20 5.33 GB,
        # alone 2026-11-21 5.36 GB): under a 6 GB cap it fails when Chrome's peak drifts up (2026-11-21 04:24, CAP)
        print("[suite] warning: SUITE_DEEP with PROYECTOS_TEST_MEM_GB=%s; the --sc4grow page step alone peaks at 5.4 GB, "
              "give a deep run PROYECTOS_TEST_MEM_GB=8" % os.environ.get("PROYECTOS_TEST_MEM_GB"))
    jobs = int(os.environ.get("SUITE_JOBS", "4") or 4)
    M = len(run)
    if env_on("SUITE_LIST"):              # the plan only: which steps would run, in which group, nothing is run
        for i, s in enumerate(run, 1):
            print("  %2d %-9s %-6s %s" % (i, s.lane, "setup" if s.setup else "check", s.name))
        return 0
    print("[suite] %d steps in %d groups, %d side by side, work %s" % (M, len({s.lane for s in run}), jobs, work), flush=True)
    lanes = []
    for s in run:
        if s.lane not in [l for l, _ in lanes]:
            lanes.append((s.lane, []))
        dict(lanes)[s.lane].append(s)
    if jobs > 1:                          # the longest groups start first (wall times of the 2026-11-20 runs)
        est = {"install": 9, "sc3": 8, "sc3page": 7, "baseprops": 6, "lottex": 5, "sc4props": 5, "sc4packs": 4, "sc4dl": 3, "page": 2, "pack": 1, "bldread": 0}
        lanes.sort(key=lambda x: -est.get(x[0], 5))
    res = {}
    lane_t = {}
    cond = threading.Condition()
    queue = list(lanes)

    def worker():
        while True:
            with cond:
                if not queue:
                    return
                lane, ss = queue.pop(0)
                dep = next((x for x in run if x.key == AFTER.get(lane)), None)
                while dep is not None and dep not in res:
                    cond.wait()
            t0 = time.time()
            for s in ss:
                r = run_step(s, cache, rebuild)
                with cond:
                    res[s] = r
                    cond.notify_all()
            with cond:
                lane_t[lane] = time.time() - t0
    th = [threading.Thread(target=worker, daemon=True) for _ in range(max(1, min(jobs, len(lanes))))]
    for t in th:
        t.start()
    bad = 0
    for i, s in enumerate(run, 1):
        with cond:
            while s not in res:
                cond.wait()
            ok, text, secs = res[s]
        sys.stdout.flush()
        sys.stdout.buffer.write(text)
        if text and not text.endswith(b"\n"):
            sys.stdout.buffer.write(b"\n")
        sys.stdout.buffer.flush()
        print("[%d/%d] %s (%d s) %s" % (i, M, s.name, round(secs), "PASS" if ok else "FAIL"), flush=True)
        bad += not ok
    for t in th:
        t.join()
    print("[suite] wall %d s; groups: %s" % (round(time.time() - t_all), ", ".join("%s %d s" % (l, round(lane_t.get(l, 0))) for l, _ in lanes)))
    print("%d of %d steps passed" % (M - bad, M))
    return bad


if __name__ == "__main__":
    sys.exit(main(sys.argv))
