/* ptrshape: report the mouse pointer exactly as the desktop compositor draws it (DXGI desktop duplication
 * GetFramePointerShape), plus where the real cursor is and which process owns the window under it.
 * Read-only: never moves the cursor, never takes focus. Writes the shape as <out>.bmp (32-bit, alpha kept).
 * build (x64 vcvars, VS2022): cl /nologo /O2 ptrshape.c d3d11.lib dxgi.lib user32.lib
 * usage: ptrshape.exe <out_prefix> [timeout_ms] */
#define COBJMACROS
#include <windows.h>
#include <d3d11.h>
#include <dxgi1_2.h>
#include <stdio.h>

static void save_bmp(const char *path, const BYTE *bgra, int w, int h, int pitch) {
    BITMAPFILEHEADER fh = {0}; BITMAPINFOHEADER ih = {0}; FILE *f; int y;
    ih.biSize = sizeof(ih); ih.biWidth = w; ih.biHeight = -h; ih.biPlanes = 1; ih.biBitCount = 32;
    fh.bfType = 0x4d42; fh.bfOffBits = sizeof(fh) + sizeof(ih); fh.bfSize = fh.bfOffBits + w * h * 4;
    f = fopen(path, "wb"); if (!f) return;
    fwrite(&fh, sizeof(fh), 1, f); fwrite(&ih, sizeof(ih), 1, f);
    for (y = 0; y < h; y++) fwrite(bgra + y * pitch, 4, w, f);
    fclose(f);
}

int main(int argc, char **argv) {
    const char *out = argc > 1 ? argv[1] : "ptr";
    DWORD timeout = argc > 2 ? (DWORD)atoi(argv[2]) : 3000, t0;
    IDXGIFactory1 *fac; IDXGIAdapter1 *ad; UINT ai, oi;
    POINT cp; HWND under; DWORD pid = 0;
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    GetCursorPos(&cp); under = WindowFromPoint(cp); GetWindowThreadProcessId(under, &pid);
    printf("cursor at screen (%ld,%ld), window 0x%p pid %lu\n", cp.x, cp.y, under, pid);
    if (FAILED(CreateDXGIFactory1(&IID_IDXGIFactory1, (void **)&fac))) { printf("no factory\n"); return 1; }
    for (ai = 0; IDXGIFactory1_EnumAdapters1(fac, ai, &ad) == S_OK; ai++) {
        ID3D11Device *dev = NULL; ID3D11DeviceContext *ctx = NULL; IDXGIOutput *o;
        if (FAILED(D3D11CreateDevice((IDXGIAdapter *)ad, D3D_DRIVER_TYPE_UNKNOWN, NULL, 0, NULL, 0, D3D11_SDK_VERSION, &dev, NULL, &ctx))) continue;
        for (oi = 0; IDXGIAdapter1_EnumOutputs(ad, oi, &o) == S_OK; oi++) {
            IDXGIOutput1 *o1; IDXGIOutputDuplication *dup; DXGI_OUTPUT_DESC od;
            IDXGIOutput_GetDesc(o, &od);
            if (cp.x < od.DesktopCoordinates.left || cp.x >= od.DesktopCoordinates.right ||
                cp.y < od.DesktopCoordinates.top || cp.y >= od.DesktopCoordinates.bottom) continue;
            printf("output %u.%u [%ld %ld %ld %ld]\n", ai, oi, od.DesktopCoordinates.left, od.DesktopCoordinates.top,
                   od.DesktopCoordinates.right, od.DesktopCoordinates.bottom);
            if (FAILED(IDXGIOutput_QueryInterface(o, &IID_IDXGIOutput1, (void **)&o1))) continue;
            if (FAILED(IDXGIOutput1_DuplicateOutput(o1, (IUnknown *)dev, &dup))) { printf("DuplicateOutput failed\n"); continue; }
            t0 = GetTickCount();
            while (GetTickCount() - t0 < timeout) {
                DXGI_OUTDUPL_FRAME_INFO fi; IDXGIResource *res = NULL;
                HRESULT hr = IDXGIOutputDuplication_AcquireNextFrame(dup, 200, &fi, &res);
                if (hr == DXGI_ERROR_WAIT_TIMEOUT) continue;
                if (FAILED(hr)) { printf("AcquireNextFrame 0x%08lx\n", hr); break; }
                if (fi.PointerShapeBufferSize) {
                    BYTE *buf = (BYTE *)malloc(fi.PointerShapeBufferSize); UINT need; DXGI_OUTDUPL_POINTER_SHAPE_INFO si;
                    if (SUCCEEDED(IDXGIOutputDuplication_GetFramePointerShape(dup, fi.PointerShapeBufferSize, buf, &need, &si))) {
                        int h = si.Type == DXGI_OUTDUPL_POINTER_SHAPE_TYPE_MONOCHROME ? si.Height / 2 : si.Height;
                        int x, y, minx = 9999, miny = 9999, maxx = -1, maxy = -1;
                        printf("shape type %u (1 mono, 2 color, 4 masked) %ux%u pitch %u hotspot %ld,%ld visible %d pos (%ld,%ld)\n",
                               si.Type, si.Width, h, si.Pitch, si.HotSpot.x, si.HotSpot.y, fi.PointerPosition.Visible,
                               fi.PointerPosition.Position.x, fi.PointerPosition.Position.y);
                        if (si.Type != DXGI_OUTDUPL_POINTER_SHAPE_TYPE_MONOCHROME) {
                            for (y = 0; y < h; y++) for (x = 0; x < (int)si.Width; x++) {
                                BYTE *p = buf + y * si.Pitch + x * 4;
                                if (p[3] || p[0] || p[1] || p[2]) { if (x < minx) minx = x; if (y < miny) miny = y; if (x > maxx) maxx = x; if (y > maxy) maxy = y; }
                            }
                            { char pth[MAX_PATH]; _snprintf(pth, sizeof(pth), "%s.bmp", out); save_bmp(pth, buf, si.Width, h, si.Pitch); }
                        } else {
                            /* AND mask rows 0..h-1, XOR rows h..2h-1, 1 bpp. Saved as BGRA: transparent = magenta,
                             * black/white as drawn, inverted = grey. */
                            BYTE *img = (BYTE *)malloc(si.Width * h * 4);
                            for (y = 0; y < h; y++) for (x = 0; x < (int)si.Width; x++) {
                                int a = (buf[y * si.Pitch + x / 8] >> (7 - x % 8)) & 1;
                                int xr = (buf[(y + h) * si.Pitch + x / 8] >> (7 - x % 8)) & 1;
                                BYTE *q = img + (y * si.Width + x) * 4;
                                if (a && !xr) { q[0] = 255; q[1] = 0; q[2] = 255; }
                                else if (a && xr) { q[0] = q[1] = q[2] = 128; }
                                else { q[0] = q[1] = q[2] = xr ? 255 : 0; }
                                q[3] = 255;
                                if (!a || xr) { if (x < minx) minx = x; if (y < miny) miny = y; if (x > maxx) maxx = x; if (y > maxy) maxy = y; }
                            }
                            { char pth[MAX_PATH]; _snprintf(pth, sizeof(pth), "%s.bmp", out); save_bmp(pth, img, si.Width, h, si.Width * 4); }
                            free(img);
                        }
                        printf("non-transparent box [%d %d %d %d] = %dx%d px\n", minx, miny, maxx + 1, maxy + 1, maxx + 1 - minx, maxy + 1 - miny);
                        free(buf); IDXGIOutputDuplication_ReleaseFrame(dup); return 0;
                    }
                    free(buf);
                }
                if (res) IUnknown_Release(res);
                IDXGIOutputDuplication_ReleaseFrame(dup);
            }
            printf("no pointer shape within %lu ms\n", timeout);
        }
    }
    return 2;
}
