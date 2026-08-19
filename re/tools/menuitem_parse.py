#!/usr/bin/env python3
"""MenuItem.INI -- the SimCity 3000 UI command table (member of Apps/Sys/SYS.PAK).

Maps every in-game UI command id to its English name, its localized-text key and the
GZCOM command GUID it dispatches. This is what turns a raw command id read off a live
`cIGZWin` button (`vt+0x214`) into something a human can read, and what lets the harness
drive gameplay by name instead of by magic number.

See re/analysis/formats/MENUITEM_INI.md for the record spec and the provenance chain, and
re/analysis/LAUNCH_CONTROL.md section 31 for how the ids are obtained from the running game.

Framing is NOT re-derived here: SYS.PAK is parsed by the validated re/tools/syspak_parse.py
(round-trips the shipped archive byte for byte).

Usage:
    python re/tools/menuitem_parse.py                 # table to stdout
    python re/tools/menuitem_parse.py --json out.json
    python re/tools/menuitem_parse.py --selftest
    python re/tools/menuitem_parse.py --name 0x10006602
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import syspak_parse  # noqa: E402

DEFAULT_PAK = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..', 'Apps', 'Sys', 'SYS.PAK')
MEMBER = 'menuitem.ini'

# 0x10006602=1,0x225872FE,0x00000034,0x225872FE,0x00000034,COMM,0x22ff0548,0,0,0,END  ; Big Park
RECORD = re.compile(
    r'^(?P<cmd>0x[0-9A-Fa-f]{8})='
    r'(?P<enabled>[^,]*),'
    r'(?P<grp>0x[0-9A-Fa-f]+),(?P<inst>0x[0-9A-Fa-f]+),'      # display text key
    r'(?P<grp2>0x[0-9A-Fa-f]+),(?P<inst2>0x[0-9A-Fa-f]+),'    # second (tooltip/help) key
    r'(?P<kind>\w+),'                                          # COMM | PMSG
    r'(?P<guid>0x[0-9A-Fa-f]+),'                               # command / message GUID
    r'(?P<param>[^,]*),'
    r'[^;]*?END\s*;\s*(?P<name>.*)$')


def load_member(pak_path=DEFAULT_PAK, member=MEMBER):
    """Return the member's lines, using the validated SYS.PAK parser for framing."""
    data = open(pak_path, 'rb').read()
    names, _offs, _toc_end, recs = syspak_parse.parse(data)
    for name, rec in zip(names, recs):
        if name.lower() == member:
            return rec['lines']
    raise KeyError('%s not found in %s (members: %d)' % (member, pak_path, len(names)))


def parse_commands(lines):
    """-> {cmd_id:int -> dict(name, ltext_group, ltext_instance, kind, guid, param)}"""
    out = {}
    for line in lines:
        m = RECORD.match(line.strip())
        if not m:
            continue
        out[int(m.group('cmd'), 16)] = {
            'name': m.group('name').strip(),
            'ltext_group': m.group('grp'),
            'ltext_instance': m.group('inst'),
            'help_group': m.group('grp2'),
            'help_instance': m.group('inst2'),
            'kind': m.group('kind'),          # COMM = command, PMSG = posted message
            'guid': m.group('guid'),
            'param': m.group('param'),
        }
    return out


def selftest(pak_path=DEFAULT_PAK):
    """Fail loudly rather than silently mis-parse. Anchors are values confirmed live:
    0x10006602 is 'Big Park', and firing it in a loaded city showed a $1,000 cost readout
    (LAUNCH_CONTROL.md section 31.7)."""
    lines = load_member(pak_path)
    cmds = parse_commands(lines)
    checks = [
        ('every line accounted for',
         len(lines) == 251),
        ('90 command records',
         len(cmds) == 90),
        ('0x10006602 is Big Park',
         cmds.get(0x10006602, {}).get('name') == 'Big Park'),
        ('0x10004001 is Roads',
         cmds.get(0x10004001, {}).get('name') == 'Roads'),
        ('kinds are only COMM/PMSG',
         {c['kind'] for c in cmds.values()} <= {'COMM', 'PMSG'}),
        ('display-text group is the menu LTEXT group',
         {c['ltext_group'].lower() for c in cmds.values()} <= {'0x225872fe', '0x041f2625'}),
        ('no name is empty',
         all(c['name'] for c in cmds.values())),
        ('ids are all in the 0x1000xxxx UI-command space',
         all(0x10000000 <= k <= 0x1000FFFF for k in cmds)),
    ]
    ok = True
    for label, passed in checks:
        print('  [%s] %s' % ('ok' if passed else 'FAIL', label))
        ok &= passed
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--pak', default=DEFAULT_PAK)
    ap.add_argument('--json', metavar='PATH', help='write the mapping as JSON')
    ap.add_argument('--name', metavar='CMDID', help='look up one command id, e.g. 0x10006602')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()

    if a.selftest:
        return 0 if selftest(a.pak) else 1

    cmds = parse_commands(load_member(a.pak))

    if a.name:
        cid = int(a.name, 0)
        c = cmds.get(cid)
        print('0x%08X  %s' % (cid, c['name']) if c else '0x%08X  (not in MenuItem.INI)' % cid)
        return 0

    if a.json:
        json.dump({('0x%08X' % k): cmds[k] for k in sorted(cmds)},
                  open(a.json, 'w'), indent=1)
        print('wrote %d commands -> %s' % (len(cmds), a.json))
        return 0

    for k in sorted(cmds):
        c = cmds[k]
        print('0x%08X  %-24s %-4s guid=%s' % (k, c['name'], c['kind'], c['guid']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
