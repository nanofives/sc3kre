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
 * Config: overscroll.ini beside the DLL:  [camera] overscroll=75  (50 = stock, max 95), slide=1
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

static void ini_read(void) {
    char path[MAX_PATH];
    self_path(path, sizeof(path), "overscroll.ini");
    if (!path[0]) return;
    g_overscroll = GetPrivateProfileIntA("camera", "overscroll", 75, path);
    if (g_overscroll < 50) g_overscroll = 50;
    if (g_overscroll > 95) g_overscroll = 95;
    g_windowed = GetPrivateProfileIntA("display", "windowed", 1, path) ? 1 : 0;
    g_slide = GetPrivateProfileIntA("camera", "slide", 1, path) ? 1 : 0;
    g_edge = GetPrivateProfileIntA("edge", "enabled", 1, path) ? 1 : 0;
    g_edge_gain = GetPrivateProfileIntA("edge", "gain", 8, path);
    g_edge_max = GetPrivateProfileIntA("edge", "max", 1600, path);
}

/* ============================================================ in-memory code patching */

static int write_code(BYTE *p, const void *src, int n) {
    DWORD old;
    if (!VirtualProtect(p, n, PAGE_EXECUTE_READWRITE, &old)) return 0;
    memcpy(p, src, n);
    VirtualProtect(p, n, old, &old);
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

/* Height of the drawn edge nearest to map cell (tx, ty) (clamped onto the map). */
static int edge_alt(BYTE *cm, int tx, int ty) {
    int W = *(int *)(cm + 0x14), H = *(int *)(cm + 0x18), d[4], e = 0, i;
    if (tx < 0) tx = 0; if (tx > W - 1) tx = W - 1;
    if (ty < 0) ty = 0; if (ty > H - 1) ty = H - 1;
    d[0] = ty; d[1] = H - 1 - ty; d[2] = tx; d[3] = W - 1 - tx;
    for (i = 1; i < 4; i++) if (d[i] < d[e]) e = i;
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
static int __stdcall step_hook(BYTE *view, int x, int y, DWORD *tx, DWORD *ty, int *sdx, int *sdy) {
    void *cm = *(void **)(view + 0x158);
    int w = *(int *)(view + 0x20), h = *(int *)(view + 0x24);
    int vx = *sdx, vy = *sdy, probe;
    if (!cm) return 0;

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
    if (VirtualProtect(p, 1, PAGE_READWRITE, &old)) {
        BYTE before = *p; *p = 1; VirtualProtect(p, 1, old, &old);
        logf("--- WINDOWED: GZGraphicD+0x6cdac = %u -> 1", before);
    } else logf("--- WINDOWED: VirtualProtect failed at +0x6cdac (%lu)", GetLastError());
    if (q[0] == 0xC6 && q[1] == 0x43 && q[2] == 0x48 && q[3] == 0x01) {
        DWORD o2;
        if (VirtualProtect(q, 4, PAGE_EXECUTE_READWRITE, &o2)) {
            q[0] = q[1] = q[2] = q[3] = 0x90; VirtualProtect(q, 4, o2, &o2);
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
    VirtualProtect(site, 10, old, &old);
    FlushInstructionCache(GetCurrentProcess(), site, 10);
    logf("--- FIX16: 16bpp branch injected at 0x19349 -> cave 0x%08lX (5-6-5)", (DWORD)cave);
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
        if (!spr && (spr = GetModuleHandleA("SIMSPR.DLL")) != NULL) ok = patch_translate(spr);
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
        logf("### READY: windowed=%d overscroll=%d%% slide=%d hook=%d edge=%d (gain %d, max %d px/s, tick %d)",
             g_windowed, g_overscroll, g_slide, ok, g_edge, g_edge_gain, g_edge_max, hb);
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
        log_open();
        logf("### sc3overscroll loaded - overscroll %d%%", g_overscroll);
        CreateThread(NULL, 0, watcher, NULL, 0, NULL);
    }
    return TRUE;
}
