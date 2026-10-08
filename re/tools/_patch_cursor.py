p = "re/harness/src/sc3resize.c"
s = open(p, encoding="utf-8", errors="replace").read()

old = """    if (m == WM_GETMINMAXINFO && g_thickframe && lp) {"""
new = r"""    /* Show the SIZING CURSOR over the frame.
     *
     * The drag itself works once WM_NCHITTEST answers edge codes (verified by driving the real
     * mouse: client 1684x961 -> 1836x961 on a right-edge drag). But the game paints its own cursor
     * and answers WM_SETCURSOR, so the user never sees a resize arrow and cannot tell the border is
     * grabbable - which is indistinguishable from "cannot drag". Set the system sizing cursor
     * whenever the hit code in the low word is a border code, and claim the message. */
    if (m == WM_SETCURSOR && g_thickframe) {
        WORD hit = LOWORD(lp);
        LPCSTR id = NULL;
        switch (hit) {
            case HTLEFT: case HTRIGHT:              id = IDC_SIZEWE;   break;
            case HTTOP:  case HTBOTTOM:             id = IDC_SIZENS;   break;
            case HTTOPLEFT: case HTBOTTOMRIGHT:     id = IDC_SIZENWSE; break;
            case HTTOPRIGHT: case HTBOTTOMLEFT:     id = IDC_SIZENESW; break;
            default: break;
        }
        if (id) {
            SetCursor(LoadCursorA(NULL, id));
            return TRUE;
        }
    }
    if (m == WM_GETMINMAXINFO && g_thickframe && lp) {"""

if old not in s:
    raise SystemExit("anchor not found")
s = s.replace(old, new, 1)
open(p, "w", encoding="utf-8", newline="").write(s)
print("WM_SETCURSOR sizing cursors added")
