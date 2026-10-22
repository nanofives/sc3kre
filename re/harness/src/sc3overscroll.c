/* sc3overscroll.c - let the SimCity 3000 Unlimited camera move past the edge of the map.
 *
 * Stock behaviour: the city view's Translate (SIMSPR FUN_1001d503) moves the camera only if the
 * tile picker (FUN_1000902f) finds a map tile under the NEW screen centre, first with mode 0, then
 * mode 1. If both miss, the whole step is thrown away. So the screen centre can never leave the
 * map, and at most about half the screen can show nothing. There is no other scroll clamp
 * (re/analysis/formats/BIGGER_CITIES.md, "The anchor bug in detail").
 *
 * This mod hooks only the refusal: when the mode-1 pick misses, it probes 8 points around the new
 * centre, (overscroll-50)% of the view width/height away (left, right, up, down, diagonals), with
 * the game's own picker. If any probe lands on the map, the step is accepted and the camera's
 * stored centre tile (+0xb0/+0xb4) is the probe's tile. With the default 75 the camera can go on
 * until about 75% of the screen is past the edge. Rotation, zoom and terrain height are whatever
 * the game's pick does with them.
 *
 * Edge sliding (owner, 2026-10-06): when a push is blocked, the camera keeps moving with the part
 * that can still go: the push turned by the smallest angle (15-degree steps up to 75) that the
 * overscroll rule allows, at the push's speed times the cosine of that angle. Wall sliding: an
 * angled push slides along the edge, a push straight into it stops.
 *
 * Arrow keys, edge scrolling and right-drag all go through Translate, so all of them get it.
 *
 * Arrows (2026-10-07): a held arrow key keeps scrolling when the mouse moves (stock clears it), see patch_arrows.
 *
 * True centre (2026-10-07): steps are judged at the real visible centre, not the view's stale native centre.
 *
 * Config: overscroll.ini beside the DLL:  [camera] overscroll=75  (50 = stock, max 95), slide=1, arrows_keep=1,
 *                                                  true_center=1
 *                                         [display] windowed=1
 * Build: re/harness/build_overscroll.ps1. Launcher: overscroll_launch.exe.
 */

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
double __cdecl sqrt(double);   /* not <math.h>: it declares a logf that clashes with ours */
double __cdecl fabs(double);

/* ============================================================ logging */

static CRITICAL_SECTION g_lock;
static HANDLE g_log = INVALID_HANDLE_VALUE;
static LARGE_INTEGER g_freq, g_t0;
static HMODULE g_self;

static void logf(const char *fmt, ...) {
    char buf[2048];
    char line[2176];
    va_list ap;
    LARGE_INTEGER now;
    double ms;
    DWORD wrote;
    int n;

    va_start(ap, fmt);
    _vsnprintf(buf, sizeof(buf) - 1, fmt, ap);
    buf[sizeof(buf) - 1] = 0;
    va_end(ap);

    QueryPerformanceCounter(&now);
    ms = (double)(now.QuadPart - g_t0.QuadPart) * 1000.0 / (double)g_freq.QuadPart;

    n = _snprintf(line, sizeof(line) - 1, "[%9.3f ms][tid %04lx] %s\r\n",
                  ms, GetCurrentThreadId(), buf);
    if (n < 0) return;
    line[sizeof(line) - 1] = 0;

    EnterCriticalSection(&g_lock);
    if (g_log != INVALID_HANDLE_VALUE)
        WriteFile(g_log, line, (DWORD)n, &wrote, NULL);
    LeaveCriticalSection(&g_lock);
    OutputDebugStringA(line);
}

/* sibling file of this DLL */
static void self_path(char *out, int cap, const char *leaf) {
    char *slash;
    if (!GetModuleFileNameA(g_self, out, cap)) { out[0] = 0; return; }
    slash = strrchr(out, '\\');
    if (slash) slash[1] = 0; else out[0] = 0;
    lstrcatA(out, leaf);
}

static void log_open(void) {
    char path[MAX_PATH];
    /* The game's cwd is Apps\, so a relative default would land there. Default beside the DLL. */
    if (!GetEnvironmentVariableA("SC3OVERSCROLL_LOG", path, sizeof(path)))
        self_path(path, sizeof(path), "sc3overscroll.log");
    g_log = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, NULL,
                        CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
}

/* ============================================================ config */

static int g_overscroll = 75;        /* percent of the screen allowed past the map edge */
static int g_windowed = 1;
static int g_slide = 1;
static int g_edge, g_edge_gain, g_edge_max;   /* defaults set in ini_read */
static int g_arrows = 1;             /* [camera] arrows_keep: a held arrow survives a mouse move */
static int g_truec = 1;              /* [camera] true_center: judge steps at the real visible centre */
static int g_wall = 1;               /* [camera] front_wall: front edges judged at the bottom of the cliff wall */
static int g_camfeel = 1;            /* CAMFEEL block: SC3OVERSCROLL_CAMFEEL=0 keeps the shipped camera constants */
static int g_cam_step = 8, g_cam_div = 4, g_cam_dead = 2;   /* [camera] scroll_step / drag_divisor / drag_deadzone */

static void ini_read(void) {
    char path[MAX_PATH];
    self_path(path, sizeof(path), "overscroll.ini");
    if (!path[0]) return;
    g_overscroll = GetPrivateProfileIntA("camera", "overscroll", 75, path);
    if (g_overscroll < 50) g_overscroll = 50;
    if (g_overscroll > 95) g_overscroll = 95;
    g_windowed = GetPrivateProfileIntA("display", "windowed", 1, path) ? 1 : 0;
    g_slide = GetPrivateProfileIntA("camera", "slide", 1, path) ? 1 : 0;
    g_arrows = GetPrivateProfileIntA("camera", "arrows_keep", 1, path) ? 1 : 0;
    g_truec = GetPrivateProfileIntA("camera", "true_center", 1, path) ? 1 : 0;
    g_wall = GetPrivateProfileIntA("camera", "front_wall", 1, path) ? 1 : 0;
    g_edge = GetPrivateProfileIntA("edge", "enabled", 1, path) ? 1 : 0;
    g_edge_gain = GetPrivateProfileIntA("edge", "gain", 8, path);
    g_edge_max = GetPrivateProfileIntA("edge", "max", 1600, path);
    g_cam_step = GetPrivateProfileIntA("camera", "scroll_step", 8, path);
    g_cam_div = GetPrivateProfileIntA("camera", "drag_divisor", 4, path);
    g_cam_dead = GetPrivateProfileIntA("camera", "drag_deadzone", 2, path);
}

/* ============================================================ in-memory code patching */

static int write_code(BYTE *p, const void *src, int n) {
    DWORD old;
    if (!VirtualProtect(p, n, PAGE_EXECUTE_READWRITE, &old)) return 0;
    memcpy(p, src, n);
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), p, n);
    return 1;
}

static int write_jmp(BYTE *at, void *to, int len) {
    BYTE b[16];
    int i;
    if (len < 5 || len > 16) return 0;
    b[0] = 0xE9;
    *(DWORD *)(b + 1) = (DWORD)to - (DWORD)(at + 5);
    for (i = 5; i < len; i++) b[i] = 0x90;
    return write_code(at, b, len);
}

/* ============================================================ the Translate hook */

/* SIMSPR FUN_1000902f(this=cellmap, sx, sy, uint *tx, uint *ty, mode, int *hit, int flag): pick
   the tile under view-relative screen point (sx, sy). Returns al != 0 on a hit. ret 0x1c. */
typedef int (__fastcall *PFN_Pick)(void *, void *, int, int, DWORD *, DWORD *, int, int *, int);

static PFN_Pick g_pick;
static DWORD    g_accept;            /* SIMSPR+0x1d596: the accept path (cellmap vt+0x2c move) */
static DWORD    g_refuse;            /* SIMSPR+0x1d5bc: the refusal path */
static volatile LONG g_n_over, g_n_slide, g_n_refused;

/* Reference height. The game draws a tile at altitude a raised by a << cellmap+0x44 on screen
   (FUN_100090ef: (alt << +0x44) - ((u+v) << +0x4c)), alt = cell record byte +0xb.
   v1 projected at altitude 0: the limit sat ~20 tiles off the drawn edge on Europolis (run8.log).
   v2 used ONE height per city (median of all edge cells): on a generated 1024 map the north and
   west edges were much higher than the median (41), so the limit sat inside the drawn land there
   and the camera stopped early (owner, mods_combo run 1).
   v3 (this): each edge has its own height profile, a box average of +-SMOOTH cells along the edge,
   so the limit follows the drawn edge but not single hills. Built once per cell map. */
#define SMOOTH 24
static BYTE *g_prof_cm;
static int   g_prof_w, g_prof_h;
static int  *g_prof[4];              /* 0: ty=0 by tx, 1: ty=H-1 by tx, 2: tx=0 by ty, 3: tx=W-1 by ty */

static int cell_alt(BYTE *cm, int tx, int ty) {
    BYTE **rows = *(BYTE ***)(cm + 0x24);
    return rows[tx][ty * 0x14 + 0x0b];
}

static void build_profiles(BYTE *cm) {
    int W = *(int *)(cm + 0x14), H = *(int *)(cm + 0x18), e, i, j;
    BYTE **rows = *(BYTE ***)(cm + 0x24);
    if (cm == g_prof_cm && W == g_prof_w && H == g_prof_h) return;
    for (e = 0; e < 4; e++) { free(g_prof[e]); g_prof[e] = NULL; }
    g_prof_cm = cm; g_prof_w = W; g_prof_h = H;
    if (!rows || W <= 0 || H <= 0 || IsBadReadPtr(rows, W * 4)) return;
    for (e = 0; e < 4; e++) {
        int n = e < 2 ? W : H, *raw = (int *)malloc(n * sizeof(int)), *out = (int *)malloc(n * sizeof(int));
        if (!raw || !out) { free(raw); free(out); continue; }
        for (i = 0; i < n; i++)
            raw[i] = e == 0 ? cell_alt(cm, i, 0) : e == 1 ? cell_alt(cm, i, H - 1)
                   : e == 2 ? cell_alt(cm, 0, i) : cell_alt(cm, W - 1, i);
        for (i = 0; i < n; i++) {
            int lo = i - SMOOTH < 0 ? 0 : i - SMOOTH, hi = i + SMOOTH >= n ? n - 1 : i + SMOOTH, s = 0;
            for (j = lo; j <= hi; j++) s += raw[j];
            out[i] = s / (hi - lo + 1);
        }
        free(raw);
        g_prof[e] = out;
    }
    logf("### OVERSCROLL: map %dx%d, edge height profiles built (+-%d cells): ends %d/%d %d/%d %d/%d %d/%d",
         W, H, SMOOTH, g_prof[0] ? g_prof[0][0] : -1, g_prof[0] ? g_prof[0][W - 1] : -1,
         g_prof[1] ? g_prof[1][0] : -1, g_prof[1] ? g_prof[1][W - 1] : -1,
         g_prof[2] ? g_prof[2][0] : -1, g_prof[2] ? g_prof[2][H - 1] : -1,
         g_prof[3] ? g_prof[3][0] : -1, g_prof[3] ? g_prof[3][H - 1] : -1);
}

/* Is map edge e (0: ty=0, 1: ty=H-1, 2: tx=0, 3: tx=W-1) a FRONT edge at rotation rot, i.e. does stepping off
   the map across it move DOWN the screen? Screen y grows with raw u+v (flat_tile_at), and the raw (u, v) of a
   tile is the inverse of flat_tile_at's rotation switch:
     rot 0: u = tx, v = ty      rot 1: u = W-1-ty, v = tx      rot 2: u = W-1-tx, v = H-1-ty      rot 3: u = ty, v = H-1-tx
   Front edges draw the terrain's cliff wall below their surface, down to altitude 0 (owner, 2026-10-07: with the
   limit judged at the surface height, the south/east walls filled ~40% of the screen at the limit while the
   north/west edges showed ~87% void). So front edges are judged at altitude 0, the bottom of the wall. */
static int front_edge(int e, int rot) {
    static const int out[4][2] = { {0, -1}, {0, 1}, {-1, 0}, {1, 0} };   /* outward (dtx, dty) */
    int dtx = out[e][0], dty = out[e][1], du, dv;
    switch (rot) {
    case 1:  du = -dty; dv = dtx;  break;
    case 2:  du = -dtx; dv = -dty; break;
    case 3:  du = dty;  dv = -dtx; break;
    default: du = dtx;  dv = dty;  break;
    }
    return du + dv > 0;
}

/* Height of the drawn edge nearest to map cell (tx, ty) (clamped onto the map). */
static int edge_alt(BYTE *cm, int tx, int ty) {
    int W = *(int *)(cm + 0x14), H = *(int *)(cm + 0x18), d[4], e = 0, i;
    if (tx < 0) tx = 0; if (tx > W - 1) tx = W - 1;
    if (ty < 0) ty = 0; if (ty > H - 1) ty = H - 1;
    d[0] = ty; d[1] = H - 1 - ty; d[2] = tx; d[3] = W - 1 - tx;
    for (i = 1; i < 4; i++) if (d[i] < d[e]) e = i;
    if (g_wall && front_edge(e, *(int *)(cm + 0x2c))) return 0;
    if (!g_prof[e]) return 0;
    return g_prof[e][e < 2 ? tx : ty];
}

/* Flat screen -> tile at altitude alt: the game's own arithmetic, FUN_100090b7 (view -> world:
   + origin +0x54/+0x58), FUN_1000a33a (world -> raw u,v: diamond by tileW +0x30, tileH +0x38,
   zoom +0x28) and FUN_1000a5c6 (rotation +0x2c, map W/H +0x14/+0x18). */
static void flat_tile_at(BYTE *cm, int sx, int sy, int alt, int *tx, int *ty) {
    int wx = *(int *)(cm + 0x54) + sx;
    int wy = *(int *)(cm + 0x58) + sy + (alt << *(int *)(cm + 0x44));
    int sh = *(int *)(cm + 0x28) + 2, W = *(int *)(cm + 0x14), H = *(int *)(cm + 0x18);
    int i2 = wy + *(int *)(cm + 0x38) / 2;
    int i1 = (wx + *(int *)(cm + 0x30) / -2) / 2;
    int u = (i2 - i1) >> sh, v = (i1 + i2) >> sh;
    switch (*(int *)(cm + 0x2c)) {
    case 1:  *tx = v;         *ty = W - u - 1; break;
    case 2:  *tx = W - u - 1; *ty = H - v - 1; break;
    case 3:  *tx = H - v - 1; *ty = u;         break;
    default: *tx = u;         *ty = v;         break;
    }
}

/* The tile under a screen point, projected onto the height of the nearest map edge. Three rounds:
   project, look up the edge height there, re-project. Converges in practice since the profile is
   smoothed. Using the height-aware pick for the LIMIT made its outline follow every hill and the
   camera caught on slopes (owner, 2026-10-06). */
static void flat_tile(BYTE *cm, int sx, int sy, int *tx, int *ty) {
    int alt, k;
    build_profiles(cm);
    alt = edge_alt(cm, *(int *)(cm + 0x14) / 2, 0);
    for (k = 0; k < 3; k++) {
        flat_tile_at(cm, sx, sy, alt, tx, ty);
        alt = edge_alt(cm, *tx, *ty);
    }
    flat_tile_at(cm, sx, sy, alt, tx, ty);
}

static int on_map(BYTE *cm, int tx, int ty) {
    return tx >= 0 && ty >= 0 && tx < *(int *)(cm + 0x14) && ty < *(int *)(cm + 0x18);
}

/* Is a camera whose new screen centre is (cx, cy) allowed? Yes if the centre, or one of 8 points
   (overscroll-50)% of the view away, is over the map (flat). The camera's stored centre tile is
   the centre's tile clamped onto the map, the nearest edge tile when the centre is off it. */
static int allowed(void *cmv, int w, int h, int cx, int cy, DWORD *tx, DWORD *ty, int *probe) {
    static const int dir[8][2] = { {1,0}, {-1,0}, {0,1}, {0,-1}, {1,1}, {1,-1}, {-1,1}, {-1,-1} };
    BYTE *cm = (BYTE *)cmv;
    int dx = w * (g_overscroll - 50) / 100, dy = h * (g_overscroll - 50) / 100, i, ux, uy, px, py;
    int W = *(int *)(cm + 0x14), H = *(int *)(cm + 0x18);
    flat_tile(cm, cx, cy, &ux, &uy);
    *probe = -2;
    if (on_map(cm, ux, uy)) *probe = -1;
    else for (i = 0; i < 8 && *probe == -2; i++) {
        flat_tile(cm, cx + dir[i][0] * dx, cy + dir[i][1] * dy, &px, &py);
        if (on_map(cm, px, py)) *probe = i;
    }
    if (*probe == -2) return 0;
    if (ux < 0) ux = 0; if (ux > W - 1) ux = W - 1;
    if (uy < 0) uy = 0; if (uy > H - 1) uy = H - 1;
    *tx = (DWORD)ux;
    *ty = (DWORD)uy;
    return 1;
}

/* Called after both stock picks missed for the requested step (*sdx, *sdy). view = the
   cISC3CityViewIso (+0x20/+0x24 = view w/h, +0x158 = cellmap). (x, y) = the requested new screen
   centre. On success the step in Translate's frame may be REWRITTEN to the part that can still
   move (edge sliding): Translate reads dx/dy back from [ebp-0xc]/[ebp-4] after this returns. */
/* TRUE CENTRE (2026-10-07). The view's stored size (+0x20/+0x24) is the native visible area, 704x544
   (800x600 minus the 96-px side panel and 56-px bar), and the resize mod never changes it. Measured live
   in a 2560x1322 window: 704x544. Translate tests the new centre at w/2+dx, h/2+dy, so at a large window
   the point it judges sits far up-left of the real screen centre: the north/west limit came early and
   the south/east one late (owner). The visible area is the view size plus however much the client grew
   past 800x600 (the side panel and bar keep their size), measured from the top-level game window. */
static HWND g_gamewnd;
static BOOL CALLBACK find_game_wnd(HWND h, LPARAM lp) {
    DWORD pid = 0;
    (void)lp;
    GetWindowThreadProcessId(h, &pid);
    if (pid == GetCurrentProcessId() && IsWindowVisible(h) && !GetWindow(h, GW_OWNER)) { g_gamewnd = h; return FALSE; }
    return TRUE;
}
static void visible_size(BYTE *view, int *w, int *h) {
    RECT rc;
    *w = *(int *)(view + 0x20);
    *h = *(int *)(view + 0x24);
    if (!g_truec) return;
    if (!g_gamewnd || !IsWindow(g_gamewnd)) { g_gamewnd = NULL; EnumWindows(find_game_wnd, 0); }
    if (g_gamewnd && GetClientRect(g_gamewnd, &rc)) {
        int cw = rc.right - rc.left, ch = rc.bottom - rc.top;
        if (cw > 800) *w += cw - 800;
        if (ch > 600) *h += ch - 600;
    }
    {   /* task cityzoom: sc3resize draws the city view at client / factor past the closest zoom */
        static int (*vf)(void);
        static int looked;
        if (!looked) { HMODULE rm = GetModuleHandleA("sc3resize.dll"); looked = 1;
                       if (rm) vf = (int (*)(void))GetProcAddress(rm, "sc3resize_view_factor"); }
        if (vf) { int f = vf(); if (f > 1) { *w /= f; *h /= f; } }
    }
}

static int __stdcall step_hook(BYTE *view, int x, int y, DWORD *tx, DWORD *ty, int *sdx, int *sdy) {
    void *cm = *(void **)(view + 0x158);
    int w0 = *(int *)(view + 0x20), h0 = *(int *)(view + 0x24), w, h;
    int vx = *sdx, vy = *sdy, probe;
    if (!cm) return 0;
    visible_size(view, &w, &h);
    if (g_truec) {
        int hit = 0;
        static LONG logged;
        /* (x, y) came in as w0/2 + dx, h0/2 + dy: move it to the real visible centre */
        x += w / 2 - w0 / 2;
        y += h / 2 - h0 / 2;
        if (!InterlockedExchange(&logged, 1))
            logf("### TRUECENTER: view stores %dx%d, visible %dx%d - steps judged at the visible centre", w0, h0, w, h);
        /* the game's own height-aware pick at the true centre first (mode 0, then 1), as Translate does */
        if (g_pick(cm, NULL, x, y, tx, ty, 0, NULL, 0) & 0xff) return 1;
        if (g_pick(cm, NULL, x, y, tx, ty, 1, NULL, 0) & 0xff) return 1;
        (void)hit;
    }

    if (allowed(cm, w, h, x, y, tx, ty, &probe)) {
        if ((InterlockedIncrement(&g_n_over) & 0x3ff) == 1)
            logf("### OVERSCROLL: past the edge via probe %d (tile %lu,%lu), %ld so far", probe, *tx, *ty, g_n_over);
        return 1;
    }
    if (g_slide && (vx || vy)) {
        /* Wall sliding: the blocked push turned by 15, 30, 45, 60 or 75 degrees, the smallest turn
           that is allowed wins, and its SPEED is the push's component along it (|v| cos angle).
           So a push at an angle to an edge slides at the matching fraction of its speed and a push
           straight into it stops. The side that worked last time is tried first, so near a corner
           the camera does not flip between left and right on alternate frames.
           History: v1 tried the axis parts and the two 2:1 edge directions and stuck in corners
           (run3.log). v2 swept up to 90 degrees at FULL speed, which the owner found sloppy: pushing
           almost straight into an edge sent the camera sideways at full speed (2026-10-06). */
        static const double cs[5][2] = {   /* cos, sin of 15..75 degrees */
            { 0.9659258, 0.2588190 }, { 0.8660254, 0.5 }, { 0.7071068, 0.7071068 },
            { 0.5, 0.8660254 }, { 0.2588190, 0.9659258 } };
        static int last_sgn = 1;
        int k, t;
        for (k = 0; k < 5; k++) {
            for (t = 0; t < 2; t++) {
                int sgn = t == 0 ? last_sgn : -last_sgn;
                double c = cs[k][0], s = sgn * cs[k][1];
                double rx = (vx * c - vy * s) * c, ry = (vx * s + vy * c) * c;   /* turned, times cos */
                int cdx = (int)(rx + (rx >= 0 ? 0.5 : -0.5)), cdy = (int)(ry + (ry >= 0 ? 0.5 : -0.5));
                if (!cdx && !cdy) continue;
                if (allowed(cm, w, h, x - vx + cdx, y - vy + cdy, tx, ty, &probe)) {
                    *sdx = cdx;
                    *sdy = cdy;
                    last_sgn = sgn;
                    if ((InterlockedIncrement(&g_n_slide) & 0x3ff) == 1)
                        logf("### SLIDE: push (%d,%d) blocked, moved (%d,%d) instead (%d deg), %ld so far",
                             vx, vy, cdx, cdy, sgn * 15 * (k + 1), g_n_slide);
                    return 1;
                }
            }
        }
    }
    if ((InterlockedIncrement(&g_n_refused) & 0x3ff) == 1)
        logf("### OVERSCROLL: step (%d,%d) refused, nothing left to slide along (%ld so far)",
             vx, vy, g_n_refused);
    return 0;
}

/* Replaces SIMSPR 0x1001d58d..0x1001d595: call FUN_1000902f (mode 1) ; test al,al ; je refuse.
   The mode-1 call's arguments are already pushed and ecx = cellmap. ebp = Translate's frame:
   [ebp+8] / [ebp+0xc] receive the tile, [ebp-0xc] / [ebp-4] hold the step dx / dy that the accept
   path pushes. esi = view, edi/ebx = new centre x/y. */
__declspec(naked) static void translate_hook(void) {
    __asm {
        call dword ptr [g_pick]
        test al, al
        jnz step_ok
        pushad
        lea eax, [ebp - 4]
        push eax
        lea eax, [ebp - 0xc]
        push eax
        lea eax, [ebp + 0xc]
        push eax
        lea eax, [ebp + 8]
        push eax
        push ebx
        push edi
        push esi
        call step_hook
        mov [esp + 28], eax
        popad
        test eax, eax
        jnz step_ok
        jmp dword ptr [g_refuse]
    step_ok:
        jmp dword ptr [g_accept]
    }
}

/* true_center: replaces SIMSPR 0x1001d56e..0x1001d576 (first pick, mode 0 ; test al,al ; jne accept) so EVERY step
   is decided by step_hook, not only the ones both stock picks refused. The stock call still runs (it consumes its
   pushed args, ret 0x1c) but its answer is ignored. Same register/frame contract as translate_hook. */
__declspec(naked) static void translate_hook_all(void) {
    __asm {
        call dword ptr [g_pick]
        pushad
        lea eax, [ebp - 4]
        push eax
        lea eax, [ebp - 0xc]
        push eax
        lea eax, [ebp + 0xc]
        push eax
        lea eax, [ebp + 8]
        push eax
        push ebx
        push edi
        push esi
        call step_hook
        mov [esp + 28], eax
        popad
        test eax, eax
        jnz all_ok
        jmp dword ptr [g_refuse]
    all_ok:
        jmp dword ptr [g_accept]
    }
}

static int patch_translate(HMODULE m) {
    static const BYTE expect[] = { 0xe8, 0x9d, 0xba, 0xfe, 0xff, 0x84, 0xc0, 0x74, 0x26 };
    BYTE *b = (BYTE *)m, *p = b + 0x1d58d;
    if (memcmp(p, expect, sizeof(expect)) != 0) {
        logf("### OVERSCROLL: SIMSPR+0x1d58d differs from shipped - NOT installed");
        return 0;
    }
    g_pick   = (PFN_Pick)(b + 0x902f);
    g_accept = (DWORD)b + 0x1d596;
    g_refuse = (DWORD)b + 0x1d5bc;
    if (g_truec) {
        BYTE *q = b + 0x1d56e;
        static const BYTE tail[] = { 0x84, 0xc0, 0x75, 0x1f };
        if (q[0] == 0xe8 && (DWORD)(q + 5) + *(DWORD *)(q + 1) == (DWORD)(b + 0x902f) && !memcmp(q + 5, tail, 4)) {
            if (!write_jmp(q, (void *)translate_hook_all, 9)) return 0;
            logf("### OVERSCROLL: true_center on - every step judged at the visible centre (SIMSPR+0x1d56e)");
            return 1;
        }
        logf("### OVERSCROLL: SIMSPR+0x1d56e differs from shipped - true_center OFF, falling back");
        g_truec = 0;
    }
    if (!write_jmp(p, (void *)translate_hook, 9)) return 0;
    logf("### OVERSCROLL: Translate hooked, camera may go until %d%% of the screen is past the edge, slide %d",
         g_overscroll, g_slide);
    return 1;
}

/* ---- windowed mode, carved verbatim from sc3resize.c via sc3bigcity.c */
/* ============================================================ edge scroll while placing
 *
 * Owner, 2026-10-06: the resize mod turns the game's edge scrolling off in windowed mode, but while
 * PLACING (dragging a zone, road, pipe, bulldozer...) the camera should follow a cursor that leaves
 * the window, slowly just past the edge and faster the further out it is.
 *
 * Each tick of the city view itself (SIMSPR FUN_10042a95, the tick that applies the right-drag
 * velocity; detoured at entry, ecx = the view's cIGZWin sub-object, outer = ecx - 4): if the left button is held after a press
 * that started inside the city view, and the cursor is outside the game window's client area, move the
 * camera toward it at gain * (pixels outside) px/s, capped. The move goes through the same call the
 * right-drag uses, outer view vt+0x34 = SIMSPR FUN_1004327d(dx, dy, 1) = Translate + view update,
 * so the overscroll limit and edge sliding apply. A WM_MOUSEMOVE at the cursor is posted at most
 * every 60 ms so the tool's drag preview follows the moved camera.
 *
 * v1 ran from the GZGraphicD blit heartbeat and posted a mouse move on every step: the UI flickered
 * while the camera moved (owner, 2026-10-06). The camera moved in the middle of drawing a frame.
 *
 * City view: the window tree holds the cIGZWin sub-object, vtable SIMSPR+0x676ac; outer = it - 4
 * (vtable SIMSPR+0x67894); the view Translate runs on is *(outer+0xb8) (vtable SIMSPR+0x63390).
 * Verified live 2026-10-06 (Translate's this == *(outer+0xb8)).
 */

/* g_edge ([edge] enabled, default 1), g_edge_gain ([edge] gain, px/s per pixel outside the window,
   default 8), g_edge_max ([edge] max, px/s cap, default 1600) are read in ini_read. */
static HWND  g_hwnd;
static int   g_lb_was, g_drag_ok;
static BYTE *g_drag_outer;
static LARGE_INTEGER g_edge_last;
static double g_acc_x, g_acc_y;
static volatile LONG g_edge_moves;

typedef void  (__fastcall *PFN_Move)(void *, void *, float, float, int);
static DWORD g_last_post;

static void edge_tick(BYTE *outer) {
    LARGE_INTEGER now;
    double dt;
    int lb, x, y, ox = 0, oy = 0;
    POINT pt;
    RECT rc;

    QueryPerformanceCounter(&now);
    dt = (double)(now.QuadPart - g_edge_last.QuadPart) / (double)g_freq.QuadPart;
    g_edge_last = now;
    if (dt > 0.1) dt = 0.1;          /* a stall must not turn into a jump */

    if (!g_hwnd || !IsWindow(g_hwnd)) g_hwnd = FindWindowA("Gonzo", NULL);
    if (!g_hwnd) return;
    lb = (GetAsyncKeyState(GetSystemMetrics(SM_SWAPBUTTON) ? VK_RBUTTON : VK_LBUTTON) & 0x8000) != 0;
    if (!GetCursorPos(&pt) || !ScreenToClient(g_hwnd, &pt) || !GetClientRect(g_hwnd, &rc)) return;
    x = pt.x;
    y = pt.y;

    if (lb && !g_lb_was) {           /* press: only a drag that starts on the city view counts */
        BYTE *win = GetForegroundWindow() == g_hwnd ? outer + 4 : NULL;   /* the cIGZWin sub-object */
        g_drag_ok = 0;
        g_drag_outer = NULL;
        if (win && x >= 0 && y >= 0 && x < rc.right && y < rc.bottom) {
            int *abs = (int *)(win + 0x14);
            if (x >= abs[0] && y >= abs[1] && x < abs[2] && y < abs[3]) {
                g_drag_ok = 1;
                g_drag_outer = win - 4;
                g_acc_x = g_acc_y = 0;
            }
        }
    }
    g_lb_was = lb;
    if (!lb) { g_drag_ok = 0; return; }
    if (!g_drag_ok || g_drag_outer != outer) return;

    if (x < 0) ox = x; else if (x >= rc.right) ox = x - rc.right + 1;
    if (y < 0) oy = y; else if (y >= rc.bottom) oy = y - rc.bottom + 1;
    if (!ox && !oy) { g_acc_x = g_acc_y = 0; return; }

    {
        double sx = (double)g_edge_gain * ox, sy = (double)g_edge_gain * oy;
        double len = sqrt(sx * sx + sy * sy);
        int mx, my;
        if (len > g_edge_max) { sx *= g_edge_max / len; sy *= g_edge_max / len; }
        g_acc_x += sx * dt;
        g_acc_y += sy * dt;
        mx = (int)g_acc_x;
        my = (int)g_acc_y;
        if (!mx && !my) return;
        g_acc_x -= mx;
        g_acc_y -= my;
        __try {
            PFN_Move move = (PFN_Move)(*(void ***)outer)[0x34 / 4];
            move(outer, NULL, (float)mx, (float)my, 1);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            logf("### EDGE: FAULT 0x%08lX moving the camera - edge scroll stopped for this drag", GetExceptionCode());
            g_drag_ok = 0;
            return;
        }
        if (GetTickCount() - g_last_post >= 60) {
            g_last_post = GetTickCount();
            PostMessageA(g_hwnd, WM_MOUSEMOVE, MK_LBUTTON, MAKELPARAM((short)x, (short)y));
        }
        if ((InterlockedIncrement(&g_edge_moves) & 0x3ff) == 1)
            logf("### EDGE: dragging with the cursor %d,%d px outside, camera step (%d,%d), %ld so far",
                 ox, oy, mx, my, g_edge_moves);
    }
}

/* ---- the view tick detour at SIMSPR 0x10042a95 (mov eax, imm32 ; call _EH_prolog ...).
   Installer copied from sc3bigcity.c's heartbeat (sc3probe.c). The stub saves pushfd/pushad and
   hands the saved frame to view_tick: f[0] = eflags, f[1..8] = edi esi ebp esp ebx edx ecx eax. */

static int modrm_len(const BYTE *p) {
    BYTE m = p[0];
    int mod = m >> 6, rm = m & 7, n = 1;
    if (mod == 3) return n;
    if (rm == 4) { BYTE sib = p[1]; n++; if (mod == 0 && (sib & 7) == 5) n += 4; }
    else if (mod == 0 && rm == 5) n += 4;
    if (mod == 1) n += 1; else if (mod == 2) n += 4;
    return n;
}

static int insn_len(const BYTE *p, int *is_rel32) {
    BYTE op = p[0];
    *is_rel32 = 0;
    if (op == 0x66 || op == 0xF2 || op == 0xF3) { int r, l = insn_len(p + 1, &r); *is_rel32 = 0; return l ? l + 1 : 0; }
    if (op >= 0x50 && op <= 0x5F) return 1;
    if (op == 0x90 || op == 0xC3 || op == 0xC9) return 1;
    if (op == 0x6A) return 2;
    if (op == 0x68) return 5;
    if (op >= 0xB8 && op <= 0xBF) return 5;
    if (op >= 0xA0 && op <= 0xA3) return 5;
    if (op == 0xE8 || op == 0xE9) { *is_rel32 = 1; return 5; }
    if (op == 0xEB) return 2;
    if (op == 0xC2) return 3;
    if (op == 0x83 || op == 0x80) return 1 + modrm_len(p + 1) + 1;
    if (op == 0x81) return 1 + modrm_len(p + 1) + 4;
    if (op == 0xC6) return 1 + modrm_len(p + 1) + 1;
    if (op == 0xC7) return 1 + modrm_len(p + 1) + 4;
    switch (op) {
    case 0x00: case 0x01: case 0x02: case 0x03: case 0x08: case 0x09: case 0x0A: case 0x0B:
    case 0x20: case 0x21: case 0x22: case 0x23: case 0x28: case 0x29: case 0x2A: case 0x2B:
    case 0x30: case 0x31: case 0x32: case 0x33: case 0x38: case 0x39: case 0x3A: case 0x3B:
    case 0x84: case 0x85: case 0x88: case 0x89: case 0x8A: case 0x8B: case 0x8D: case 0x8F:
    case 0xFF:
        return 1 + modrm_len(p + 1);
    }
    return 0;
}

static DWORD g_outer_vt;             /* SIMSPR+0x67894, the outer city view class */

static void __stdcall heartbeat(int idx, DWORD *f) {
    /* FUN_10042a95 is called with ecx = the cIGZWin sub-object (vtable SIMSPR+0x676ac); the outer
       city view (vtable +0x67894) is 4 bytes before it. Measured run13.log. */
    BYTE *win = (BYTE *)f[7];
    (void)idx;
    if (g_edge && win && !IsBadReadPtr(win - 4, 0xc0)
        && *(DWORD *)win == g_outer_vt - 0x67894 + 0x676ac && *(DWORD *)(win - 4) == g_outer_vt)
        edge_tick(win - 4);
}

static int install_heartbeat(BYTE *t) {
    int relofs[4], nrel = 0, k, len = 0;
    BYTE *tr, *stub;
    while (len < 5) {
        int r, l = insn_len(t + len, &r);
        if (!l || len + l > 24) return 0;
        if (r && nrel < 4) relofs[nrel++] = len;
        len += l;
    }
    tr = (BYTE *)VirtualAlloc(NULL, 4096, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!tr) return 0;
    stub = tr + 64;
    memcpy(tr, t, len);
    for (k = 0; k < nrel; k++) {
        int o = relofs[k];
        DWORD abs_target = (DWORD)(t + o + 5) + *(DWORD *)(t + o + 1);
        *(DWORD *)(tr + o + 1) = abs_target - (DWORD)(tr + o + 5);
    }
    tr[len] = 0xE9;
    *(DWORD *)(tr + len + 1) = (DWORD)(t + len) - (DWORD)(tr + len + 5);
    stub[0] = 0x60; stub[1] = 0x9C; stub[2] = 0x8B; stub[3] = 0xC4; stub[4] = 0x50;
    stub[5] = 0x68; *(DWORD *)(stub + 6) = 0;
    stub[10] = 0xE8; *(DWORD *)(stub + 11) = (DWORD)heartbeat - (DWORD)(stub + 15);
    stub[15] = 0x9D; stub[16] = 0x61;
    stub[17] = 0xE9; *(DWORD *)(stub + 18) = (DWORD)tr - (DWORD)(stub + 22);
    return write_jmp(t, stub, len);
}

static void patch_windowed(HMODULE gz) {
    BYTE *p = (BYTE *)gz + 0x6cdac;         /* the windowed flag Init reads */
    BYTE *q = (BYTE *)gz + 0x117d6;         /* the fullscreen re-force store */
    DWORD old;
    if (VirtualProtect(p, 1, PAGE_EXECUTE_READWRITE, &old)) {
        BYTE before = *p; *p = 1; (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
        logf("--- WINDOWED: GZGraphicD+0x6cdac = %u -> 1", before);
    } else logf("--- WINDOWED: VirtualProtect failed at +0x6cdac (%lu)", GetLastError());
    if (q[0] == 0xC6 && q[1] == 0x43 && q[2] == 0x48 && q[3] == 0x01) {
        DWORD o2;
        if (VirtualProtect(q, 4, PAGE_EXECUTE_READWRITE, &o2)) {
            q[0] = q[1] = q[2] = q[3] = 0x90; (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
            FlushInstructionCache(GetCurrentProcess(), q, 4);
            logf("--- WINDOWED: GZGraphicD+0x117D6 'mov [ebx+0x48],1' -> nop x4");
        }
    } else {
        logf("--- WINDOWED: 0x117D6 pattern mismatch (%02X %02X %02X %02X)", q[0], q[1], q[2], q[3]);
    }
}

static void patch_surfacefmt(HMODULE gz) {
    BYTE *site = (BYTE *)gz + 0x19349;
    static const BYTE orig[10] = { 0xF6,0xDB, 0x1B,0xDB, 0x81,0xE3,0xC0,0x0F,0x00,0x00 };
    BYTE *cave;
    DWORD old;
    int n = 0, jne_fixup, block_start;
    if (memcmp(site, orig, sizeof(orig)) != 0) {
        logf("--- FIX16: 0x19349 pattern mismatch (%02X %02X %02X %02X), NOT patched",
             site[0], site[1], site[2], site[3]);
        return;
    }
    cave = (BYTE *)VirtualAlloc(NULL, 256, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!cave) { logf("--- FIX16: VirtualAlloc failed (%lu)", GetLastError()); return; }
    cave[n++] = 0x50;
    cave[n++]=0x83;cave[n++]=0xBE;cave[n++]=0x10;cave[n++]=0;cave[n++]=0;cave[n++]=0;cave[n++]=0x07;
    cave[n++] = 0x75; jne_fixup = n; cave[n++] = 0x00;
    block_start = n;
    #define MOV_D(off,imm) do{ cave[n++]=0xC7;cave[n++]=0x86; \
        cave[n++]=(BYTE)(off);cave[n++]=(BYTE)((off)>>8);cave[n++]=0;cave[n++]=0; \
        cave[n++]=(BYTE)(imm);cave[n++]=(BYTE)((imm)>>8);cave[n++]=(BYTE)((imm)>>16);cave[n++]=(BYTE)((imm)>>24);}while(0)
    MOV_D(0x10, 0x1007);
    MOV_D(0x54, 0x20);
    cave[n++]=0x83;cave[n++]=0x8E;cave[n++]=0x58;cave[n++]=0;cave[n++]=0;cave[n++]=0;cave[n++]=0x40;
    MOV_D(0x60, 0x10);
    MOV_D(0x64, 0xF800);
    MOV_D(0x68, 0x07E0);
    MOV_D(0x6C, 0x001F);
    #undef MOV_D
    cave[jne_fixup] = (BYTE)(n - block_start);
    cave[n++] = 0x58;
    memcpy(cave + n, orig, sizeof(orig)); n += sizeof(orig);
    cave[n++] = 0xE9;
    { DWORD tgt = (DWORD)((BYTE *)gz + 0x19353);
      DWORD rel = tgt - (DWORD)(cave + n + 4); memcpy(cave + n, &rel, 4); n += 4; }
    FlushInstructionCache(GetCurrentProcess(), cave, n);
    if (!VirtualProtect(site, 10, PAGE_EXECUTE_READWRITE, &old)) {
        logf("--- FIX16: VirtualProtect failed (%lu)", GetLastError()); return;
    }
    site[0] = 0xE9;
    { DWORD rel = (DWORD)cave - (DWORD)(site + 5); memcpy(site + 1, &rel, 4); }
    site[5]=site[6]=site[7]=site[8]=site[9]=0x90;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), site, 10);
    logf("--- FIX16: 16bpp branch injected at 0x19349 -> cave 0x%08lX (5-6-5)", (DWORD)cave);
}


/* ============================================================ arrows survive a mouse move */

/* Stock (re/analysis/formats/CAMERA_OVERSCROLL.md, "Arrow scrolling stops when the mouse moves"): the arrow keys
   and the mouse edge scroll share four latch bytes on the city view (outer +0x1e1 up, +0x1e2 down, +0x1e3 right,
   +0x1e4 left). The edge handler vt+0x40 = FUN_10043a38(x, y) clears all four whenever the cursor is inside the
   view's inner rect, so a held arrow dies on any mouse move and nothing re-reads the keys until the next key
   event. This wraps that slot: after the stock handler, any arrow still held (read through the view's own
   key-state object +0x210, vt+0xc(vk)) is latched again. Edge scrolling is untouched. Not in right-drag mode
   (+0x1e6) or with scrolling disabled (+0x177 = 0), where the stock handler does not touch the latches. */
typedef void (__fastcall *PFN_Edge)(void *, void *, int, int);
typedef char (__fastcall *PFN_KeyDown)(void *, void *, int);
static PFN_Edge g_edge_orig;
static volatile LONG g_n_rearm;

static void __fastcall edge_wrap(void *self, void *edx, int x, int y) {
    BYTE *v = (BYTE *)self;
    void *keys;
    g_edge_orig(self, edx, x, y);
    if (!v[0x177] || v[0x1e6]) return;
    keys = *(void **)(v + 0x210);
    if (!keys || IsBadReadPtr(keys, 4)) return;
    {   PFN_KeyDown down = (PFN_KeyDown)(*(DWORD **)keys)[0xc / 4];
        int any = 0;
        if (down(keys, NULL, 0x26)) { v[0x1e1] = 1; any = 1; }
        if (down(keys, NULL, 0x28)) { v[0x1e2] = 1; any = 1; }
        if (down(keys, NULL, 0x27)) { v[0x1e3] = 1; any = 1; }
        if (down(keys, NULL, 0x25)) { v[0x1e4] = 1; any = 1; }
        if (any) InterlockedIncrement(&g_n_rearm);
    }
}

static int patch_arrows(HMODULE spr) {
    DWORD *slot = (DWORD *)((BYTE *)spr + 0x678d4), old;      /* outer vtable 0x10067894, slot +0x40 */
    if (IsBadReadPtr(slot, 4) || *slot != (DWORD)spr + 0x43a38) {
        logf("### ARROWS: vtable slot SIMSPR+0x678d4 differs from shipped - NOT installed");
        return 0;
    }
    if (!VirtualProtect(slot, 4, PAGE_EXECUTE_READWRITE, &old)) return 0;
    g_edge_orig = (PFN_Edge)*slot;
    *slot = (DWORD)edge_wrap;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    return 1;
}

/* ⭐ CAMFEEL (child windowed, 2026-10-12, verify/windowed/).
 *
 * The owner's camera feel lives on disk on the dev PC only: MAIN\Apps\SIMSPR.DLL carries the pe_patch.py recipes
 * scroll_speed=8 + drag_divisor=4 + drag_deadzone=2 (owner ruling 2026-08-26, re/sessions/STATUS_camera.md). A stock
 * install (the owner's laptop) has the shipped 32 / 2 / 12. Same bytes, in memory, from here:
 *   SIMSPR 0x10067690..0x100676a0  five per-zoom keyboard scroll steps, 32.0f   -> scroll_step
 *   SIMSPR 0x10043a5d / 0x10043a67 `push -2`, the right-drag divisor X / Y      -> -drag_divisor
 *   SIMSPR 0x100676a4              right-drag dead zone, 12.0f                  -> drag_deadzone
 * [CONFIRMED @ 0x10043a38] (drag branch), none of the bytes is under a base relocation. All-or-nothing: bytes already
 * at the target (the dev PC's on-disk build) are logged and left alone, anything else is refused.
 * overscroll.ini [camera] scroll_step=32 drag_divisor=2 drag_deadzone=12 is the shipped feel. */
static void patch_camfeel(HMODULE spr) {
    float *step = (float *)((BYTE *)spr + 0x67690), *dead = (float *)((BYTE *)spr + 0x676a4);
    BYTE *dx = (BYTE *)spr + 0x43a5d, *dy = (BYTE *)spr + 0x43a67;
    static const BYTE ctx_x[6] = { 0x6a, 0xfe, 0x99, 0x59, 0xf7, 0xf9 }, ctx_y[4] = { 0x6a, 0xfe, 0x8b, 0xf8 };
    float want_step = (float)g_cam_step, want_dead = (float)g_cam_dead;
    BYTE want_div = (BYTE)(-g_cam_div);
    int i, stock = 1, done = 1;
    if (g_cam_step < 1 || g_cam_step > 256 || g_cam_div < 1 || g_cam_div > 128 || g_cam_dead < 0 || g_cam_dead > 79) {
        logf("### CAMFEEL: overscroll.ini values out of range (scroll_step 1..256, drag_divisor 1..128, drag_deadzone 0..79)"
             " - NOT patched"); return; }
    for (i = 0; i < 5; i++) { if (step[i] != 32.0f) stock = 0; if (step[i] != want_step) done = 0; }
    if (*dead != 12.0f) stock = 0;
    if (*dead != want_dead) done = 0;
    if (memcmp(dx + 2, ctx_x + 2, 4) || memcmp(dy + 2, ctx_y + 2, 2) || dx[0] != 0x6a || dy[0] != 0x6a) stock = done = 0;
    if (dx[1] != 0xfe || dy[1] != 0xfe) stock = 0;
    if (dx[1] != want_div || dy[1] != want_div) done = 0;
    if (done) { logf("### CAMFEEL: SIMSPR already at scroll %d, drag divisor %d, dead zone %d (on-disk camera build) - left alone",
                     g_cam_step, g_cam_div, g_cam_dead); return; }
    if (!stock) { logf("### CAMFEEL: SIMSPR camera bytes are neither shipped nor the target - NOT patched"); return; }
    {   float st[5];
        for (i = 0; i < 5; i++) st[i] = want_step;
        if (!write_code((BYTE *)step, st, sizeof(st)) || !write_code((BYTE *)dead, &want_dead, 4)
            || !write_code(dx + 1, &want_div, 1) || !write_code(dy + 1, &want_div, 1)) {
            logf("### CAMFEEL: VirtualProtect failed (%lu) - camera bytes may be partly written", GetLastError()); return; } }
    logf("### CAMFEEL: SIMSPR scroll step 32 -> %d, drag divisor 2 -> %d, drag dead zone 12 -> %d (dev PC camera build)",
         g_cam_step, g_cam_div, g_cam_dead);
}

/* ================================================================ boot */

static DWORD WINAPI watcher(LPVOID param) {
    HMODULE gz = NULL, spr = NULL;
    int ok = 0, ms = 0;
    (void)param;
    while (ms < 300000 && !(gz && spr)) {
        if (!gz && (gz = GetModuleHandleA("GZGraphicD.dll")) != NULL && g_windowed) {
            patch_windowed(gz);
            patch_surfacefmt(gz);
        }
        if (!spr && (spr = GetModuleHandleA("SIMSPR.DLL")) != NULL) {
            ok = patch_translate(spr);
            if (g_camfeel) patch_camfeel(spr);
            if (g_arrows) g_arrows = patch_arrows(spr) ? 1 : 0;
        }
        Sleep(1);
        ms++;
    }
    {   /* edge scroll while placing needs a per-frame tick */
        int hb = 0;
        if (spr && g_edge) {
            static const BYTE expect[] = { 0xb8, 0x14, 0xee, 0x05, 0x10, 0xe8 };   /* with SIMSPR at its preferred base */
            BYTE *t = (BYTE *)spr + 0x42a95;
            g_outer_vt = (DWORD)spr + 0x67894;
            if (t[0] == expect[0] && t[5] == expect[5]
                && *(DWORD *)(t + 1) == (DWORD)spr + 0x5ee14)                        /* relocated imm32 */
                hb = install_heartbeat(t);
            else logf("### EDGE: SIMSPR+0x42a95 differs from shipped - edge scroll NOT installed");
        }
        QueryPerformanceCounter(&g_edge_last);
        logf("### READY: windowed=%d overscroll=%d%% slide=%d hook=%d edge=%d (gain %d, max %d px/s, tick %d) arrows_keep=%d",
             g_windowed, g_overscroll, g_slide, ok, g_edge, g_edge_gain, g_edge_max, hb, g_arrows);
    }
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        g_self = (HMODULE)inst;
        DisableThreadLibraryCalls(inst);
        InitializeCriticalSection(&g_lock);
        QueryPerformanceFrequency(&g_freq);
        QueryPerformanceCounter(&g_t0);
        ini_read();
        {   char v[8];
            if (GetEnvironmentVariableA("SC3OVERSCROLL_CAMFEEL", v, sizeof(v))) g_camfeel = atoi(v); }
        log_open();
        logf("### sc3overscroll loaded - overscroll %d%%", g_overscroll);
        CreateThread(NULL, 0, watcher, NULL, 0, NULL);
    }
    return TRUE;
}
