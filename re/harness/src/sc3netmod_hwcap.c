/* sc3netmod_hwcap.c - highway arm ends for the interchange blocks (task hwcap, reworked by task hwcap2, highway program
 * 2026-10-18). #included by sc3netmod.c after sc3netmod_hwy.c and before the shape blocks (hwt, hwx, hwdd, hwdx), which
 * call it. It only reads cells: it never writes one.
 *
 * The case (verify/hwcap/RESULTS.md, verify/hwcap2/RESULTS.md): a highway the player drags ends in a stock end cap ON
 * the drag's last cell at one end and one cell PAST the drag at the other (measured in game 2026-10-18, below). An
 * interchange whose joining cells reach the drag's end then finds the cap, or nothing, where it wanted plain highway.
 * Owner decision 2026-10-18 (task hwcap2): "Never extend: only use the end piece where possible." No block adds highway
 * the player did not drag (task hwcap's carry-on is gone). A block now:
 *   - accepts the stock cap as it is on an arm cell no ramp joins (the arm simply ends there),
 *   - accepts nothing on an arm cell past the arm's end when no ramp joins there either,
 *   - writes a CAPPED JOIN (its own piece: the join with the stock end face and a U-turn turn matrix, saved as the stock
 *     cap) where the cap sits on the arm's last joining cell and its package has one for that cell,
 *   - else drops that quadrant / falls back, as before task hwcap.
 *
 * Stock ends (lab, `hw_lab.py cells`, 2026-10-18; sc3netmod loaded, no block touches a lone highway):
 *   straight along x, drag (58,25) -> (66,25): lanes z 24 = 15051.2, z 25 = 15051.0, x 57..66; caps x 57 (one past the
 *     start) 15053.0 / 15054.0 (z 24 / z 25), x 66 (the end cell) 15054.2 / 15053.2
 *   straight along z, drag (70,28) -> (70,38): lanes x 69 = 73.2, x 70 = 73.0; caps z 27 11237.2 / 11235.2 (x 69 / 70),
 *     z 38 11235.0 / 11237.0
 *   diagonal x - z, drag (44,14) -> (52,22): band 11223.2 / 11224.0 / 11223.0 per row; caps on the middle line,
 *     (43,13) 14999.0 with (44,13) 11223.0, (52,22) 14999.2 with (51,22) 11223.2 (the row's outer cell beyond is empty)
 *   diagonal x + z, drag (56,40) -> (64,32): band 15052.2 / 15106.0 / 15052.0; caps (55,40) 15059.2 with (56,40)
 *     15052.0, (64,31) 15059.0 with (63,31) 15052.2
 * So an arm's end is always: the last row, with the cap(s) in it (straight: both lanes; diagonal: the middle cell, the
 * two outer cells between it and the previous middle stay plain, the two beyond it are empty). The cap's (id, state)
 * names the outward direction (hwcap_dir).
 *
 * Helpers:
 *   hwcap_dir(v, &sx, &sz)        v is a stock end cap -> 1 and its outward step
 *   hwcap_is(v)                   v is a stock end cap
 *   hwcap_end(hp, x, z, sx, sz)   cell (x, z) of an arm whose outward step is (sx, sz):
 *                                 1 = it holds that arm's own end cap (the arm ends ON it),
 *                                 2 = it holds no highway and the arm's own cap lies behind it (the arm ended before
 *                                     it: only empty cells between; diagonal: the cap's band row reaches the cell),
 *                                 0 = neither (other highway, or nothing with no cap of this arm behind it)
 *   hwcap_cap_of(sx, sz, lower, &id, &st)   the stock cap of an end with outward step (sx, sz): straight = the lane's
 *                                 (lower = the lane with the lower z along x / the lower x along z), diagonal = the
 *                                 middle cell's
 */

#define HWCAP_REACH 16                       /* cells walked back from a cell to find its arm's cap */

/* a stock end cap -> its outward step (measured, above); 0 = not a cap or a state never seen */
static int hwcap_dir(DWORD v, int *sx, int *sz) {
    WORD id = hwy_id(v);
    int s = hwy_st(v);
    if (!v || (s & 1)) return 0;
    switch (id) {
    case 14999: *sx = *sz = s ? 1 : -1; return 1;
    case 15059: *sx = s ? -1 : 1; *sz = -*sx; return 1;
    case 15053: case 15054: *sx = s ? 1 : -1; *sz = 0; return 1;
    case 11235: case 11237: *sx = 0; *sz = s ? -1 : 1; return 1;
    }
    return 0;
}

static int hwcap_is(DWORD v) { int a, b; return hwcap_dir(v, &a, &b); }

/* the measured caps per outward step (the table above) */
static void hwcap_cap_of(int sx, int sz, int lower, WORD *id, int *st) {
    if (sx && sz) {
        *id = sx == sz ? 14999 : 15059;
        *st = (sx == sz ? sx > 0 : sx < 0) ? 2 : 0;
    } else if (sz == 0) {
        *id = (sx > 0) == (lower != 0) ? 15054 : 15053;
        *st = sx > 0 ? 2 : 0;
    } else {
        *id = (sz > 0) == (lower != 0) ? 11235 : 11237;
        *st = sz > 0 ? 0 : 2;
    }
}

static DWORD hwcap_rd(HwyPass *hp, int x, int z) { return hwy_rd(hp, x, z); }     /* task hwtdel: the shared read */

static int hwcap_end(HwyPass *hp, int x, int z, int sx, int sz) {
    DWORD v = hwcap_rd(hp, x, z);
    int c, k, dx, dz, diag = sx && sz;
    if (v) return hwcap_dir(v, &dx, &dz) && dx == sx && dz == sz;
    /* walk back toward the interchange along the lane (straight) or the middle line (diagonal: from the cell, or from
     * the middle cell before it when the cell is an outer one); only empty cells may lie between */
    for (c = 0; c < (diag ? 3 : 1); c++) {
        int bx = x - (c == 1 ? sx : 0), bz = z - (c == 2 ? sz : 0);
        for (k = 0; k <= HWCAP_REACH; k++) {
            int qx = bx - k * sx, qz = bz - k * sz;
            DWORD w = hwcap_rd(hp, qx, qz);
            if (!w) continue;
            if (hwcap_dir(w, &dx, &dz) && dx == sx && dz == sz) {
                int across = (x - qx) * sx - (z - qz) * sz;          /* diagonal: the cell lies in the cap's band */
                if (!diag || (across >= -1 && across <= 1)) return 2;
            }
            break;
        }
    }
    return 0;
}
