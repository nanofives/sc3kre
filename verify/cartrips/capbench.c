/* capbench.c - cost per router node of the capture a cartrips mod would run in the final-path pop loop:
   rect test, append (x, z, type) to a thread-local buffer, at the origin node commit 1 in K viewport trips to a ring.
   Measured with the same compiler flags as the harness mods (cl /O2, x86). */
#include <windows.h>
#include <stdio.h>
#include <string.h>

typedef struct { int x0, z0, x1, z1; unsigned char ty; } Node;
typedef struct { int n, nin; short xs[256], zs[256]; unsigned char ts[256]; } Trip;
static __declspec(thread) Trip t_trip;
static volatile int g_rect[4] = { 64, 97, 96, 124 };
static Trip g_ring[64]; static volatile LONG g_w; static volatile LONG g_vp; static int g_every = 5;

__declspec(noinline) void __cdecl on_pop(const Node *nd) {
  Trip *t = &t_trip;
  if (nd->x1 >= g_rect[0] && nd->x0 <= g_rect[2] && nd->z1 >= g_rect[1] && nd->z0 <= g_rect[3]) t->nin++;
  if (t->n < 256) { t->xs[t->n] = (short)nd->x0; t->zs[t->n] = (short)nd->z0; t->ts[t->n] = nd->ty; }
  t->n++;
  if (nd->ty == 0x80) {                       /* origin = last popped node: trip complete */
    if (t->nin && (InterlockedIncrement(&g_vp) % g_every) == 0) {
      LONG w = InterlockedIncrement(&g_w) & 63;
      memcpy(&g_ring[w], t, sizeof(Trip));
    }
    t->n = 0; t->nin = 0;
  }
}

int main(void) {
  enum { NN = 1 << 20 };
  static Node nodes[NN];
  LARGE_INTEGER f, a, b; int i, r, len = 0;
  unsigned s = 12345;
  for (i = 0; i < NN; i++) {                  /* paths of 41 nodes (S1 mean 38-43), random walk over a 256 map */
    s = s * 1103515245 + 12345;
    nodes[i].x0 = nodes[i].x1 = (s >> 8) & 255; nodes[i].z0 = nodes[i].z1 = (s >> 16) & 255;
    nodes[i].ty = (++len == 41) ? (len = 0, 0x80) : 1;
  }
  QueryPerformanceFrequency(&f);
  for (r = 0; r < 5; r++) {
    QueryPerformanceCounter(&a);
    for (i = 0; i < 50; i++) { int k; for (k = 0; k < NN; k++) on_pop(&nodes[k]); }
    QueryPerformanceCounter(&b);
    printf("run %d: %.2f ns per node (%d nodes), viewport trips %ld\n", r,
           (double)(b.QuadPart - a.QuadPart) * 1e9 / f.QuadPart / (50.0 * NN), 50 * NN, g_vp);
  }
  return 0;
}
