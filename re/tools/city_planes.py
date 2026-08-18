#!/usr/bin/env python3
"""city_planes.py - cross-tabulate the two per-tile PLANES in a SimCity 3000 city file.

WHY THIS EXISTS. Zone-raster value `0x16` (22) has been the city-save format's open question
since the zone layer was decoded. Every previous attempt asked the CODE where 22 comes from
(five recorded sweeps, all negative: no binary writes the literal 22 into the raster). Nobody
asked the CORPUS what a 22 tile *is*.

Two `N*N` one-byte-per-tile planes sit in every one of the 59 shipped city-family files and have
never been compared:

  zone plane   first `N*N` bytes of `{0x206c6e7c, 0x409ff3ba, 0}`   -- zone-developer slot index
                                                                       `[CONFIRMED, 59/59]`
  tile grid    `{0x406b1196, 0x80ab8ab0, 0}` = frame(8) + `N*N` + 8  -- SIMGEOM cell map,
                                                                       saver `0x1000beec`

`city_write.City.n` already reads the tile-grid section -- but only its LENGTH, to derive
`N = isqrt(size - 16)`. It throws the 65,536 payload bytes away. This tool reads them.

WHAT IT DOES NOT ASSUME.

  * **Orientation.** The zone plane's base writer emits rows in REVERSE (`0x1001b4e9`, `n-1`
    down to `0`) while the tile grid is written by unrelated code in another module. So the two
    planes need not agree on row order, and this tool refuses to pick one: it reports the
    contingency under all four orientations (identity / vertical flip / transpose /
    transpose+flip) and lets the numbers choose.
  * **That the relation exists.** "22 is uncorrelated with the tile grid in all 59 files" is a
    real result and this tool is built to be able to report it.
  * **That a sharp conditional means anything on its own.** If the grid plane is 80% one value,
    then `P(grid=v | zone=22)` being high is arithmetic, not evidence. Every conditional is
    therefore reported beside the ENRICHMENT `P(v | zone=22) / P(v)` -- the same measure the
    neighbour analysis used -- and beside the SAME measure computed for every other zone value
    as a control. If R/C/I tiles are equally sharp, the grid is just zone-derived and nothing
    specific to 22 has been found.

METHOD RULES THIS TOOL OBEYS (all earned on this project, see CLAUDE.md / HANDOFF.md):
  - `--selftest` runs against inputs whose answers are written out by hand below. Run it first.
  - The grid plane's start offset is not assumed: the 8-byte section frame is VALIDATED by its
    `0xDEADBEEF` marker before the plane is read, so a wrong offset fails loudly instead of
    silently shifting the whole cross-tab.
  - Every count prints its FILTER (which families, how many files).
  - Nothing is written. This tool opens files read-only and has no save path.

Usage:
  py -3.12 re/tools/city_planes.py --selftest
  py -3.12 re/tools/city_planes.py "Cities"                  # the whole corpus
  py -3.12 re/tools/city_planes.py "Cities" --value 22        # focus one zone value
  py -3.12 re/tools/city_planes.py "Cities/Berlin, Germany.sc3" --full   # per-file detail
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from city_write import City, CityError, GRID_GROUP, SECTION_TYPE

GRID_TYPE = 0x406B1196            # the tile grid's own interface id, NOT 0x206c6e7c
DEADBEEF = 0xDEADBEEF
FAMILIES = (".sc3", ".sct", ".snr", ".st3")

ORIENTATIONS = ("identity", "vflip", "transpose", "transpose+vflip")


# --- plane extraction ---------------------------------------------------------------------


def zone_plane(city):
    """The first N*N bytes of the SC3ZoneLayer instance-0 section."""
    z = city.section(0x409FF3BA, 0, SECTION_TYPE)
    if z is None:
        raise CityError("no SC3ZoneLayer instance-0 section")
    n = city.n
    if len(z.data) < n * n:
        raise CityError("zone section %d bytes < N*N = %d" % (len(z.data), n * n))
    return bytes(z.data[:n * n]), n


def grid_plane(city):
    """The SIMGEOM tile grid's N*N payload, after a VALIDATED 8-byte section frame.

    The frame is `{u16 version, u8 flags, u8 extra, u32 0xDEADBEEF}` `[CONFIRMED @0x10010315]`.
    Checking the marker is what makes the payload offset a measurement rather than an
    assumption -- if this section is not framed the way the format doc says, the caller finds
    out here instead of getting a cross-tab shifted by 8 bytes.
    """
    g = city.section(GRID_GROUP, 0, GRID_TYPE)
    if g is None:
        raise CityError("no tile-grid section {0x406b1196, 0x80ab8ab0}")
    n = city.n
    if len(g.data) != n * n + 16:
        raise CityError("tile grid %d bytes, expected N*N+16 = %d" % (len(g.data), n * n + 16))
    ver, flags, extra, marker = struct.unpack_from("<HBBI", g.data, 0)
    if marker != DEADBEEF:
        raise CityError("tile-grid frame marker is 0x%08x, not 0xDEADBEEF -- the 8-byte frame "
                        "reading is wrong for this file, refusing to guess the plane offset"
                        % marker)
    return bytes(g.data[8:8 + n * n]), n, (ver, flags, extra)


# --- orientation --------------------------------------------------------------------------


def reorient(plane, n, how):
    """Re-index a row-major N*N plane. Returns bytes in the same row-major convention."""
    if how == "identity":
        return plane
    out = bytearray(n * n)
    if how == "vflip":
        for y in range(n):
            out[y * n:(y + 1) * n] = plane[(n - 1 - y) * n:(n - y) * n]
    elif how == "transpose":
        for y in range(n):
            for x in range(n):
                out[y * n + x] = plane[x * n + y]
    elif how == "transpose+vflip":
        for y in range(n):
            for x in range(n):
                out[y * n + x] = plane[x * n + (n - 1 - y)]
    else:
        raise ValueError("unknown orientation %r" % how)
    return bytes(out)


# --- the measurement ----------------------------------------------------------------------


def contingency(zone, grid):
    """{zone_value: {grid_value: count}} plus the two marginals. One pass, no numpy."""
    table = {}
    zmarg = {}
    gmarg = {}
    for zv, gv in zip(zone, grid):
        zmarg[zv] = zmarg.get(zv, 0) + 1
        gmarg[gv] = gmarg.get(gv, 0) + 1
        row = table.get(zv)
        if row is None:
            row = table[zv] = {}
        row[gv] = row.get(gv, 0) + 1
    return table, zmarg, gmarg


def enrichment(table, zmarg, gmarg, total, zv):
    """For zone value `zv`: [(grid_value, count, P(g|zv), P(g), enrichment)] sorted by count."""
    row = table.get(zv, {})
    nz = zmarg.get(zv, 0)
    if not nz:
        return []
    out = []
    for gv, c in row.items():
        p_cond = c / nz
        p_marg = gmarg.get(gv, 0) / total
        out.append((gv, c, p_cond, p_marg, (p_cond / p_marg) if p_marg else float("inf")))
    out.sort(key=lambda r: -r[1])
    return out


def concentration(table, zmarg, zv):
    """max_g P(grid=g | zone=zv) -- how tightly this zone value pins a single grid value."""
    row = table.get(zv, {})
    nz = zmarg.get(zv, 0)
    if not nz:
        return 0.0, None
    gv, c = max(row.items(), key=lambda kv: kv[1])
    return c / nz, gv


# --- per file -----------------------------------------------------------------------------


def analyse(path, value=22, orientations=ORIENTATIONS):
    city = City.load(path)
    zone, n = zone_plane(city)
    grid, n2, frame = grid_plane(city)
    assert n == n2
    res = {"path": path, "n": n, "frame": frame, "total": n * n,
           "zone_hist": {}, "orients": {}}
    for b in zone:
        res["zone_hist"][b] = res["zone_hist"].get(b, 0) + 1
    for how in orientations:
        g = reorient(grid, n, how)
        table, zmarg, gmarg = contingency(zone, g)
        conc, gv = concentration(table, zmarg, value)
        res["orients"][how] = {
            "conc": conc, "conc_grid_value": gv,
            "rows": enrichment(table, zmarg, gmarg, n * n, value),
            "control": {zv: concentration(table, zmarg, zv)[0]
                        for zv in sorted(zmarg) if zv != value},
            "gmarg": gmarg,
        }
    return res


# --- selftest -----------------------------------------------------------------------------


def selftest():
    """Inputs whose answers are worked out by hand, so a green run means something."""
    ok = True

    def check(name, got, want):
        nonlocal ok
        good = got == want
        ok = ok and good
        print("  %-46s %s   got %r" % (name, "PASS" if good else "FAIL", got))
        if not good:
            print("  %-46s      want %r" % ("", want))

    # 1. A 4x4 pair whose contingency table is written out by hand.
    #
    #    zone (row-major)          grid (row-major)
    #      0  0 22 22               5  5  9  9
    #      0  0 22 22               5  5  9  9
    #      1  1  0  0               7  7  5  5
    #      1  1  0  0               7  7  5  5
    #
    #    By hand: zone 22 occurs 4 times, ALL of them where grid == 9.
    #      zone 0  -> 4x grid 5 (top-left) + 4x grid 5 (bottom-right) = 8x grid 5
    #      zone 1  -> 4x grid 7
    #      zone 22 -> 4x grid 9
    #    Marginals: zone {0:8, 1:4, 22:4}; grid {5:8, 7:4, 9:4}; total 16.
    #    Enrichment of grid 9 given zone 22 = (4/4) / (4/16) = 4.0
    zone = bytes([0, 0, 22, 22, 0, 0, 22, 22, 1, 1, 0, 0, 1, 1, 0, 0])
    grid = bytes([5, 5, 9, 9, 5, 5, 9, 9, 7, 7, 5, 5, 7, 7, 5, 5])
    table, zmarg, gmarg = contingency(zone, grid)
    check("4x4 zone marginal", zmarg, {0: 8, 1: 4, 22: 4})
    check("4x4 grid marginal", gmarg, {5: 8, 7: 4, 9: 4})
    check("4x4 row for zone 22", table[22], {9: 4})
    check("4x4 concentration of 22", concentration(table, zmarg, 22), (1.0, 9))
    rows = enrichment(table, zmarg, gmarg, 16, 22)
    check("4x4 enrichment of grid 9 given 22", rows[0], (9, 4, 1.0, 0.25, 4.0))

    # 2. Orientation. A 3x3 plane whose vflip and transpose are written out by hand.
    #      1 2 3          7 8 9          1 4 7
    #      4 5 6  vflip-> 4 5 6  transp-> 2 5 8
    #      7 8 9          1 2 3          3 6 9
    p = bytes([1, 2, 3, 4, 5, 6, 7, 8, 9])
    check("3x3 identity", reorient(p, 3, "identity"), p)
    check("3x3 vflip", reorient(p, 3, "vflip"), bytes([7, 8, 9, 4, 5, 6, 1, 2, 3]))
    check("3x3 transpose", reorient(p, 3, "transpose"), bytes([1, 4, 7, 2, 5, 8, 3, 6, 9]))
    #    transpose+vflip = vflip applied to the transpose: rows (3 6 9)(2 5 8)(1 4 7)
    check("3x3 transpose+vflip", reorient(p, 3, "transpose+vflip"),
          bytes([3, 6, 9, 2, 5, 8, 1, 4, 7]))
    #    Every orientation must be a permutation, i.e. preserve the histogram.
    for how in ORIENTATIONS:
        check("3x3 %s preserves multiset" % how,
              sorted(reorient(p, 3, how)), sorted(p))

    # 3. DISCRIMINATION. The tool must be able to tell a right orientation from a wrong one.
    #
    #    The first attempt at this check was WRONG and it is worth recording why: case 1's grid
    #    is vertically symmetric where the 22 tiles sit (grid rows 0-1 are identical), so its
    #    vflip is ALSO perfectly sharp -- just on a different value. A sharpness score can be
    #    fooled by an accidental alignment. That is exactly why `ctrl-max` exists in the report.
    #
    #    So the discriminating case is built deliberately asymmetric under the 22 region:
    #      zone (as above)          grid2
    #        0  0 22 22               5  5  9  9
    #        0  0 22 22               5  5  9  9
    #        1  1  0  0               7  7  1  2
    #        1  1  0  0               7  7  3  4
    #
    #    By hand: identity puts all four 22 tiles on grid 9  -> conc 1.0
    #             vflip rows become (7 7 3 4)(7 7 1 2)(5 5 9 9)(5 5 9 9), so the four 22 tiles
    #             land on 3, 4, 7... no: on (r0,c2)=3 (r0,c3)=4 (r1,c2)=1 (r1,c3)=2
    #             -> four distinct values, conc = 1/4 = 0.25
    grid2 = bytes([5, 5, 9, 9, 5, 5, 9, 9, 7, 7, 1, 2, 7, 7, 3, 4])
    t2, zm2, _ = contingency(zone, grid2)
    check("grid2 identity is sharp", concentration(t2, zm2, 22), (1.0, 9))
    t3, zm3, _ = contingency(zone, reorient(grid2, 4, "vflip"))
    check("grid2 under the WRONG orientation is blunt", concentration(t3, zm3, 22)[0], 0.25)

    # 4. Invariants against a real shipped file, via an INDEPENDENT path (City.zone_get and
    #    City.n) rather than this module's own plane extraction.
    sample = None
    for cand in ("Cities/Berlin, Germany.sc3",):
        if os.path.exists(cand):
            sample = cand
    if sample is None:
        print("  (no shipped sample file found; file-side invariants SKIPPED)")
    else:
        city = City.load(sample)
        n = city.n
        zp, _ = zone_plane(city)
        gp, _, frame = grid_plane(city)
        check("%s: zone plane length == N*N" % os.path.basename(sample), len(zp), n * n)
        check("%s: grid plane length == N*N" % os.path.basename(sample), len(gp), n * n)
        agree = all(city.zone_get(x, y) == zp[y * n + x]
                    for x, y in ((0, 0), (n // 3, n // 2), (n - 1, n - 1)))
        check("zone_get agrees with the plane at 3 coords", agree, True)
        # The grid frame must have parsed as a real frame, else grid_plane would have raised.
        print("  tile-grid frame: version=%d flags=%d extra=%d (marker validated)" % frame)

    print("\nselftest: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


# --- reporting ----------------------------------------------------------------------------


def city_files(target):
    if os.path.isfile(target):
        return [target]
    out = []
    for name in sorted(os.listdir(target)):
        if name.lower().endswith(FAMILIES):
            out.append(os.path.join(target, name))
    return out


def cmd_report(target, value, full):
    files = city_files(target)
    fam = {}
    for f in files:
        fam[os.path.splitext(f)[1].lower()] = fam.get(os.path.splitext(f)[1].lower(), 0) + 1
    print("FILTER: %d files under %r, by extension: %s"
          % (len(files), target, ", ".join("%s %d" % kv for kv in sorted(fam.items()))))
    print("Cross-tabulating zone plane vs SIMGEOM tile grid; focus zone value %d (0x%02x)\n"
          % (value, value))

    hdr = ("file", "N", "n(%d)" % value, "orient", "conc", "grid", "enrich", "ctrl-max")
    print("%-34s %4s %8s %-16s %6s %5s %8s %9s" % hdr)
    print("-" * 100)
    agg = {how: [] for how in ORIENTATIONS}
    fams = {}
    withval = 0
    for path in files:
        try:
            r = analyse(path, value)
        except CityError as e:
            print("%-34s  ERROR %s" % (os.path.basename(path)[:34], e))
            continue
        nv = r["zone_hist"].get(value, 0)
        if nv:
            withval += 1
        for how in ORIENTATIONS:
            o = r["orients"][how]
            ctrl = max(o["control"].values()) if o["control"] else 0.0
            rows = o["rows"]
            enr = rows[0][4] if rows else 0.0
            agg[how].append((o["conc"], ctrl))
            print("%-34s %4d %8d %-16s %6.3f %5s %8.2f %9.3f"
                  % (os.path.basename(path)[:34], r["n"], nv, how, o["conc"],
                     ("0x%02x" % o["conc_grid_value"]) if o["conc_grid_value"] is not None
                     else "-", enr, ctrl))
        fams.setdefault(os.path.splitext(path)[1].lower(), []).append(
            (nv, r["total"], sum(c for v, c in r["zone_hist"].items() if v)))
        if full:
            print("    zone histogram: %s" % dict(sorted(r["zone_hist"].items())))
            print("    per-zone-value concentration (identity), the CONTROL:")
            for zv, cc in sorted(r["orients"]["identity"]["control"].items()):
                print("        zone %-3d n=%-7d conc=%.3f" % (zv, r["zone_hist"].get(zv, 0), cc))
            for how in ORIENTATIONS:
                print("    [%s] top grid values given zone %d:" % (how, value))
                for gv, c, pc, pm, e in r["orients"][how]["rows"][:8]:
                    print("        grid 0x%02x  n=%-7d P(g|z)=%.4f  P(g)=%.4f  enrich=%.2f"
                          % (gv, c, pc, pm, e))
        print("-" * 100)

    print("\nPER-FAMILY, value %d (filter: every file of that extension in %r)" % (value, target))
    print("%-6s %6s %6s %12s %12s %10s %10s"
          % ("ext", "files", "with", "n(val)", "zoned tiles", "val/zoned", "val/tile"))
    for ext in sorted(fams):
        rows = fams[ext]
        nv = sum(a for a, _, _ in rows)
        tot = sum(b for _, b, _ in rows)
        zoned = sum(c for _, _, c in rows)
        print("%-6s %6d %6d %12d %12d %10s %10.4f"
              % (ext, len(rows), sum(1 for a, _, _ in rows if a), nv, zoned,
                 ("%.4f" % (nv / zoned)) if zoned else "-", nv / tot if tot else 0))

    print("\nSUMMARY over %d files (%d of them contain zone value %d)" % (len(files), withval, value))
    print("%-16s %14s %14s" % ("orientation", "mean conc", "mean ctrl-max"))
    for how in ORIENTATIONS:
        rows = agg[how]
        if not rows:
            continue
        mc = sum(a for a, _ in rows) / len(rows)
        mk = sum(b for _, b in rows) / len(rows)
        print("%-16s %14.4f %14.4f" % (how, mc, mk))
    print("\nREAD THIS BEFORE BELIEVING THE ABOVE: 'conc' is max_g P(grid=g | zone=%d). A high "
          "conc\nis only interesting if it BEATS 'ctrl-max', the same statistic for the "
          "sharpest OTHER\nzone value -- otherwise the tile grid is simply zone-derived and "
          "nothing specific to %d\nhas been shown." % (value, value))
    return 0


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    if argv[0] == "--selftest":
        return selftest()
    target = argv[0]
    value = 22
    full = "--full" in argv
    if "--value" in argv:
        value = int(argv[argv.index("--value") + 1], 0)
    return cmd_report(target, value, full)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
