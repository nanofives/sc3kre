/* sc3netmod_rampfirst.c - the RAMPFIRST block of sc3netmod.dll (task hwtrips, 2026-10-18). #included by
 * sc3netmod_lanes.c above ld_select; it rides on LANEDENSITY's entry detour of SimTransit FUN_1000755e and uses its
 * helpers (ld_flags, ld_mark, ld_close). Evidence: re/analysis/HIGHWAY_TRIPS.md, verify/hwtrips/.
 *
 * Stock: a road (type 1) or bus (0x41) node's ring scan (SimTransit 0x10007a63) keeps the busiest road candidate below
 * TrafficAnnoyanceLevel (keep rule 0x10007db4). A road-side ramp cell (flags +0x5c & 0x41 == 0x41; the 0x40 comes from
 * occupant flag 0x200000 in FUN_10005983) becomes a type-3 / 0x43 node, the only way from a road onto a highway, but it
 * never receives density (route_trip 0x100070d0 has no deposit case for type 3). So it loses to any used road and is
 * taken only after the DFS has used up the busier branches [CONFIRMED @ SimTransit 0x1000755e, 0x100070d0].
 *
 * This block: when a 1x1 road / bus node has an unvisited road-side ramp cell among its ring candidates (the four
 * sides and the centre), every other road candidate gets the node type's bits in the visited grid (+0x78) for this one
 * call (ld_close; ld_select clears the bits it added after the call). The scan then takes the ramp. If the DFS comes
 * back to this node, the ramp is visited and the stock busiest-road order applies. Station candidates are left alone.
 * Only the per-trip visited grid is written (sc3perf traffic_mt workers each have their own).
 *
 * SC3NETMOD_RAMPFIRST=0 turns it off. sc3netmod_rf_set(0|1) switches it live (measurement, hwtrips_probe.py).
 */

static volatile LONG g_rf_on, g_rf_n_offer, g_rf_n_closed;

static void rf_init(void) {
    char v[8];
    DWORD got = GetEnvironmentVariableA("SC3NETMOD_RAMPFIRST", v, sizeof(v));
    g_rf_on = !(got && v[0] == '0');
    logf(g_rf_on ? "rampfirst: on" : "rampfirst: off (SC3NETMOD_RAMPFIRST=0)");
}

static const int g_rf_dx[5] = {-1, 0, 1, 0, 0}, g_rf_dz[5] = {0, -1, 0, 1, 0};

/* close the non-ramp road candidates of a road / bus node that has an open road-side ramp candidate */
static void rf_close(BYTE *layer, BYTE *node, BYTE **added, BYTE *addb, int *nadd) {
    BYTE t = node[0x14];
    DWORD x, z, w, h, cx[5], cz[5];
    int k, ramp = 0, kind[5];
    if (!g_rf_on || (t != 1 && t != 0x41)) return;
    x = *(DWORD *)(node + 4); z = *(DWORD *)(node + 8);
    if (x != *(DWORD *)(node + 0xc) || z != *(DWORD *)(node + 0x10)) return;
    w = *(DWORD *)(layer + 0x14); h = *(DWORD *)(layer + 0x18);
    for (k = 0; k < 5; k++) {
        WORD f;
        kind[k] = 0;
        cx[k] = x + g_rf_dx[k]; cz[k] = z + g_rf_dz[k];
        if (cx[k] >= w || cz[k] >= h) continue;                     /* unsigned: also catches -1 */
        f = ld_flags(layer, cx[k], cz[k]);
        if ((f & 0x11) != 0x01) continue;                            /* road cell, not a station */
        if ((*ld_mark(layer, cx[k], cz[k]) & t) == t) continue;      /* visited by this node type */
        kind[k] = (f & 0x40) ? 2 : 1;
        if (f & 0x40) ramp = 1;
    }
    if (!ramp) return;
    InterlockedIncrement(&g_rf_n_offer);
    for (k = 0; k < 5; k++)
        if (kind[k] == 1) {
            int before = *nadd;
            ld_close(layer, cx[k], cz[k], t, added, addb, nadd);
            if (*nadd > before) InterlockedIncrement(&g_rf_n_closed);
        }
}

__declspec(dllexport) int __cdecl sc3netmod_rf_set(int on) {
    LONG prev;
    if (!g_ld_st || !g_ld_mode) return -1;
    prev = InterlockedExchange(&g_rf_on, on ? 1 : 0);
    logf("rampfirst: live switch %s (was %s)", on ? "ON" : "OFF", prev ? "on" : "off");
    return (int)prev;
}

static void rampfirst_stats(void) {
    logf("rampfirst: %s, ramp offers=%ld, other road candidates closed=%ld", g_rf_on ? "on" : "off", g_rf_n_offer, g_rf_n_closed);
}
