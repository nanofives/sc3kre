"""query.py -- read the in-game "Copiar ID" block (`SC3 query id v1`, re/analysis/QUERY_ID.md)."""
import re

HEADER = "SC3 query id v1"


def parse(text):
    """-> dict of key -> value string for the first block in `text`. Raises ValueError."""
    i = text.find(HEADER)
    if i < 0:
        raise ValueError("no '%s' block found" % HEADER)
    out = {}
    for line in text[i + len(HEADER):].splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(HEADER):
            break
        k, sep, v = line.partition(":")
        if not sep:
            continue
        out[k.strip().rstrip("?")] = v.strip()
    return out


def piece_of(block):
    """-> (pieceId, state or None, how) from a parsed block, or (None, None, why)."""
    if "network.piece_id" in block:
        pid = int(block["network.piece_id"].split()[0], 0)
        st = block.get("network.state")
        return pid, int(st.split()[0], 0) if st else None, "network.piece_id"
    key = block.get("object.key", "")
    parts = key.split()
    if len(parts) == 3 and parts[0].upper() == "0XE223741F" and parts[1].upper() == "0XA317745F":
        return int(parts[2], 16), None, "object.key (network exemplar)"
    return None, None, "block has no network.piece_id and object.key is not a network exemplar"


def clipboard_text():
    """Windows clipboard as text (CF_UNICODETEXT), via ctypes. Read-only."""
    import ctypes
    from ctypes import wintypes
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    u32.GetClipboardData.restype = wintypes.HANDLE
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    if not u32.OpenClipboard(None):
        raise OSError("OpenClipboard failed")
    try:
        h = u32.GetClipboardData(13)          # CF_UNICODETEXT
        if not h:
            return ""
        p = k32.GlobalLock(h)
        try:
            return ctypes.wstring_at(p)
        finally:
            k32.GlobalUnlock(h)
    finally:
        u32.CloseClipboard()


def ids_in_text(text):
    """Loose fallback: a bare number or 0x number."""
    m = re.fullmatch(r"\s*(0x[0-9a-fA-F]+|\d+)\s*", text)
    return int(m.group(1), 0) if m else None
