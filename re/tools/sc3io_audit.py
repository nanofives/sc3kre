"""Audit every tool and driver for cursor-moving / focus-stealing / second-capture-method code.

The point of `sc3io` is that there is exactly ONE way to see the game and ONE way to drive it. That
guarantee is only worth something if no sibling script quietly does it another way - and this repo
accumulated 19 such scripts before the consolidation. This is the regression check.

Three classes are reported:

  BANNED     - moves the physical cursor or steals foreground. Must not exist outside an
               explicitly opted-in RE control arm (marked by a `require_cursor_optin` call in the
               same function).
  2ND-CAPTURE- an independent capture path (CopyFromScreen / PrintWindow / a raw BitBlt / mss),
               i.e. a fallback that could return untrustworthy pixels without the sc3io gate.
  ACTIVATING - ShowWindow with a show-command that activates the window (SW_MAXIMIZE / SW_RESTORE
               / 3 / 9), which takes focus. Use sc3io.maximize_without_focus / restore_without_focus.

    python re/tools/sc3io_audit.py            # exit 1 if anything is flagged
    python re/tools/sc3io_audit.py --quiet    # only the verdict
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

# Files that are ALLOWED to contain the pattern, with the reason.
ALLOWED = {
    "re/tools/sc3io.py": "the single implementation; banned names appear in prose only",
    "re/tools/sc3io_audit.py": "this file lists the patterns",
    "re/tools/sc3io_selftest.py": "poisons the banned names in order to prove they are unused",
}

BANNED = re.compile(
    r"\b(?:SetCursorPos|mouse_event|SendInput|keybd_event|SetForegroundWindow"
    r"|BringWindowToTop|SetActiveWindow|SwitchToThisWindow|AttachThreadInput)\s*\(")
SECOND_CAPTURE = re.compile(
    r"\b(?:CopyFromScreen|PrintWindow|mss\s*\(|BitBlt\s*\()")
ACTIVATING = re.compile(
    r"ShowWindow\s*\(\s*[^,]+,\s*(?:SW_MAXIMIZE|SW_RESTORE|SW_SHOW\b|3|9)\s*\)")

SCAN = [
    ("re/tools", "*.py"),
    ("verify", "*.ps1"),
    ("re/scripts", "*.ps1"),
    ("re/harness", "*.ps1"),
]


DOC_QUOTES = ('"""', "'" * 3)


def code_lines(text: str, suffix: str):
    """Yield (lineno, line) for CODE only - comments and docstring bodies are prose.

    A naive "does the line start with #" test flagged this repo's own explanatory docstrings:
    restore_down.py's header describes the ShowWindow call it replaced. Triple-quoted blocks are
    therefore tracked across lines.
    """
    in_doc = None
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if suffix == ".py":
            if in_doc:
                if in_doc in s:
                    in_doc = None
                continue
            for q in DOC_QUOTES:
                if s.startswith(q):
                    if not (len(s) > 2 * len(q) and s.endswith(q)):
                        in_doc = q      # multi-line docstring opens here
                    s = ""
                    break
        if not s or s.startswith("#"):
            continue
        yield i, line


def opted_in(text: str, idx: int) -> bool:
    """True if a `require_*_optin` guard appears in the enclosing block above this line.

    Two guards exist: `require_cursor_optin` (the arm needs the physical cursor) and
    `require_focus_optin` (the arm needs foreground). Both make an invasive RE control arm
    unreachable without an explicit env opt-in, which is what earns the exemption here.
    """
    window = text.splitlines()[max(0, idx - 14):idx]
    return any(("require_cursor_optin" in w) or ("require_focus_optin" in w) for w in window)


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)

    findings: list[tuple[str, str, int, str]] = []
    scanned = 0
    for sub, pat in SCAN:
        base = ROOT / sub
        if not base.exists():
            continue
        for f in sorted(base.rglob(pat)):
            rel = f.relative_to(ROOT).as_posix()
            if rel in ALLOWED:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            scanned += 1
            for i, line in code_lines(text, f.suffix):
                if BANNED.search(line) and not opted_in(text, i):
                    findings.append(("BANNED", rel, i, line.strip()))
                if SECOND_CAPTURE.search(line):
                    findings.append(("2ND-CAPTURE", rel, i, line.strip()))
                if ACTIVATING.search(line):
                    findings.append(("ACTIVATING", rel, i, line.strip()))

    if not a.quiet:
        print(f"scanned {scanned} file(s) under {', '.join(s for s, _ in SCAN)}\n")
        for kind in ("BANNED", "2ND-CAPTURE", "ACTIVATING"):
            group = [f for f in findings if f[0] == kind]
            print(f"== {kind} ({len(group)}) ==")
            if not group:
                print("   none")
            for _, rel, i, line in group:
                print(f"   {rel}:{i}")
                print(f"      {line[:120]}")
            print()

    if findings:
        print(f"AUDIT FAILED: {len(findings)} finding(s). "
              "Route these through re/tools/sc3io.py, or mark a genuine cursor-only RE control "
              "arm with sc3io.require_cursor_optin().")
        return 1
    print("AUDIT CLEAN: one capture path, one input path, nothing touches the cursor or focus.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
