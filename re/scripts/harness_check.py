#!/usr/bin/env python3
"""
harness_check.py - turn one sc3probe run log into a single PASS / FAIL / HARNESS-FAIL
verdict, so nobody has to grep counters by hand and no broken measurement can pass
for a real zero.

    py -3 re/scripts/harness_check.py re/harness/recover_A.log

Exit codes:
    0  PASS          the run rendered and every integrity check held
    1  FAIL          the measurement is trustworthy but the game did NOT render
    2  HARNESS-FAIL  the measurement itself is broken (a zero here means nothing)

The distinction between FAIL and HARNESS-FAIL is the whole point. Every expensive
dead end this session was a HARNESS-FAIL wearing a FAIL's clothes: a trace table
that never opened, a detour that never installed, a relative log path that wrote
nothing - each produced a plausible zero. Those are integrity failures and must
never be read as "the game drew nothing".

Feature context (fix16 / fitclient / nointro / windowed) is auto-detected from the
probe's own banner lines, so the same script grades every scenario correctly.
"""
import re, sys

MIN_BLT_DISP = 1000        # a real menu composites tens of thousands; 1000 is a floor


def parse(text):
    m = {
        "fnlog_inst": None,          # (got, total)
        "trace_open_fail": False,
        "fix16_ok": False, "fix16_mismatch": False,
        "nointro_ok": False, "nointro_mismatch": False,
        "fitclient_client": None,    # (w, h)
        "windowed": False,
        "hitcounts": {},             # last FNLOG HIT COUNTS block
        "have_hitblock": False,
        "blt_ok": None, "blt_fail": None,
        "suspends": [],              # list of +1 / -1 deltas
        "u037_src_lit": None, "u037_dst_lit": None,
        "tracer_unrecognised": [],
    }
    lines = text.splitlines()

    for ln in lines:
        mm = re.search(r"FNLOG\[[^\]]*\]:\s*(\d+)/(\d+)\s+instrumented", ln)
        if mm:
            m["fnlog_inst"] = (int(mm.group(1)), int(mm.group(2)))
        if "FNLOG" in ln and "cannot open" in ln:
            m["trace_open_fail"] = True
        if "FIX16: 16bpp branch injected" in ln:
            m["fix16_ok"] = True
        if "FIX16:" in ln and "NOT patched" in ln:
            m["fix16_mismatch"] = True
        if "NOINTRO: intro movie start neutralised" in ln:
            m["nointro_ok"] = True
        if "NOINTRO:" in ln and "NOT patched" in ln:
            m["nointro_mismatch"] = True
        mm = re.search(r"FITCLIENT: resulting client = (\d+)x(\d+)", ln)
        if mm:
            m["fitclient_client"] = (int(mm.group(1)), int(mm.group(2)))
        if "WINDOWED: GZGraphicD" in ln:
            m["windowed"] = True
        mm = re.search(r"SUSPEND #\d+\s+delta=([+-]\d+)", ln)
        if mm:
            m["suspends"].append(int(mm.group(1)))
        mm = re.search(r"blt_ok=(\d+).*blt_fail=(\d+)", ln)
        if mm:
            m["blt_ok"], m["blt_fail"] = int(mm.group(1)), int(mm.group(2))
        mm = re.search(r"U-037 blit#\d+:.*SRC .*lit=(-?\d+).*DST .*lit=(-?\d+)", ln)
        if mm:
            s, d = int(mm.group(1)), int(mm.group(2))
            m["u037_src_lit"] = max(m["u037_src_lit"] or 0, s)
            m["u037_dst_lit"] = max(m["u037_dst_lit"] or 0, d)
        mm = re.search(r"(\w+)\s+FUN_\w+:\s+UNRECOGNISED prologue", ln)
        if mm:
            m["tracer_unrecognised"].append(mm.group(1))

    # last FNLOG HIT COUNTS block: name -> count
    idxs = [i for i, ln in enumerate(lines) if "=== FNLOG HIT COUNTS ===" in ln]
    if idxs:
        m["have_hitblock"] = True
        i = idxs[-1]
        for ln in lines[i + 1:i + 40]:
            mm = re.match(r"^\[.*?\]\[tid .{4}\]\s+(\w+)\s+(\d+)\s*$", ln)
            if mm:
                m["hitcounts"][mm.group(1)] = int(mm.group(2))
            elif "===" in ln:
                break
    return m


def check(m):
    """Return (verdict, rows) where verdict in {PASS, FAIL, HARNESS-FAIL}."""
    rows = []          # (level, ok, text)  level in {I, R}
    def integ(ok, t): rows.append(("I", ok, t))
    def rend(ok, t):  rows.append(("R", ok, t))

    # ---- integrity: is the measurement itself trustworthy? ----
    if m["fnlog_inst"] is None:
        integ(False, "no 'FNLOG N/N instrumented' line - the trace table never loaded")
    else:
        g, t = m["fnlog_inst"]
        integ(g == t, "FNLOG detours installed %d/%d" % (g, t))
    integ(not m["trace_open_fail"], "trace table opened" if not m["trace_open_fail"]
          else "trace table 'cannot open' - counters will be MISSING not zero")
    if m["fix16_mismatch"]:
        integ(False, "FIX16 pattern mismatch - the 16bpp branch was NOT injected")
    if m["nointro_mismatch"]:
        integ(False, "NOINTRO pattern mismatch - the movie-skip was NOT applied")

    # a counter of 0 is only meaningful if its detour installed; guard blt_disp_1
    fnlog_full = m["fnlog_inst"] is not None and m["fnlog_inst"][0] == m["fnlog_inst"][1]

    # ---- render: did the game actually draw? (only trust once integrity holds) ----
    # Primary witness is the blt_disp_1 counter (needs a HIT COUNTS report block).
    # If the run ended before a report block but pixel evidence (U-037 dst lit) exists,
    # that is stronger proof of rendering than the counter - accept it as the witness.
    bd = m["hitcounts"].get("blt_disp_1")
    rh = m["hitcounts"].get("raster_blit_hw")
    if bd is not None:
        rend(bd > MIN_BLT_DISP, "blt_disp_1 = %d (need > %d)" % (bd, MIN_BLT_DISP))
        if rh is not None and bd > 0:
            ratio = rh / bd
            rend(0.5 < ratio < 1.5, "raster_blit_hw %d tracks blt_disp_1 (ratio %.2f)" % (rh, ratio))
    elif m["u037_dst_lit"] is not None:
        rend(m["u037_dst_lit"] > 0,
             "no counter block, but dest surface lit = %d (pixel witness)" % m["u037_dst_lit"])
    else:
        rend(False, "no render evidence: neither a HIT COUNTS block nor U-037 lit "
                    "(run too short? use a fixed -kill and do not close the window)")

    if m["blt_fail"] is not None:
        rend(m["blt_fail"] == 0, "present blt_fail = %d (need 0)" % m["blt_fail"])

    if m["fix16_ok"]:
        if m["u037_dst_lit"] is not None:
            rend(m["u037_dst_lit"] > 0, "fix16: dest surface lit = %d (need > 0)" % m["u037_dst_lit"])
        if m["u037_src_lit"] is not None:
            rend(m["u037_src_lit"] > 0, "fix16: source surface lit = %d (need > 0)" % m["u037_src_lit"])

    # suspend expectations depend on nointro
    total = sum(m["suspends"])
    if m["nointro_ok"]:
        rend(len(m["suspends"]) == 0,
             "nointro: no renderer SUSPEND (%d seen)" % len(m["suspends"]))
    elif m["suspends"]:
        rend(total == 0, "suspend/resume paired (net delta %+d over %d events)"
             % (total, len(m["suspends"])))

    # rasthw_throw: with fix16 the color-key blit must succeed
    rt = m["hitcounts"].get("rasthw_throw")
    if rt is not None and m["fix16_ok"]:
        rend(rt <= 1, "rasthw_throw = %d (fix16: color-key blits must succeed, need <= 1)" % rt)

    integrity_ok = all(ok for lvl, ok, _ in rows if lvl == "I")
    render_ok = all(ok for lvl, ok, _ in rows if lvl == "R")
    if not integrity_ok:
        return "HARNESS-FAIL", rows
    if not render_ok:
        return "FAIL", rows
    return "PASS", rows


def main(argv):
    if len(argv) < 2:
        print("usage: harness_check.py <run.log> [more.log ...]")
        return 2
    worst = 0
    for path in argv[1:]:
        try:
            text = open(path, "r", errors="replace").read()
        except OSError as e:
            print("HARNESS-FAIL: cannot read %s (%s)" % (path, e))
            worst = max(worst, 2); continue
        verdict, rows = check(parse(text))
        print("\n=== %s : %s ===" % (path, verdict))
        for lvl, ok, t in rows:
            tag = "INTEG" if lvl == "I" else "render"
            print("  [%s] %-5s %s" % ("ok" if ok else "XX", tag, t))
        worst = max(worst, {"PASS": 0, "FAIL": 1, "HARNESS-FAIL": 2}[verdict])
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv))
