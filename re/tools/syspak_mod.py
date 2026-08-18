#!/usr/bin/env python3
"""syspak_mod.py — set one tunable inside a SYS.PAK and prove the edit is surgical.

Read/write of the archive itself lives in `syspak_parse.py`; this is the editing layer on top,
promoted out of a one-off test script so there is one implementation instead of a copy per
experiment (the same debt `.IXF` had before `ixf_parse.py` absorbed the writer).

WHAT IT GUARANTEES. Every write path here asserts, before it will emit a file:
  - the member exists, exactly once
  - the [SECTION] exists, exactly once, and the KEY exists exactly once inside it
  - after rebuilding, re-parsing yields the same member names in the same order
  - EXACTLY ONE member's content differs from the input, checked by comparing all members'
    line lists rather than by trusting a byte diff
A silent no-op edit is the obvious way for this kind of tool to fail, so it refuses instead.

SAME-LENGTH EDITS ARE PREFERRED, and the tool tells you when you got one. If the replacement
value has the same character count as the original, the member's byte length is unchanged, every
record offset stays put, and the archive differs from the input ONLY in the value digits. That
preserves the diagnostic from `verify/loose_file_test/ARM3_RESULTS.md`: when a behavioural test
comes back null, a tight diff proves the archive is sound and forces the finding onto the
consumer instead of the writer. A length-changing edit shifts every subsequent record and every
TOC offset, and the diff stops being evidence about anything.

LEADING ZEROS ARE SAFE for padding a value to length, and this was read rather than assumed:
`FUN_10012ad7` @ `0x10012ad7` is a radix CHOOSER — `0x`/`0X` prefix -> strtoul radix 16; any
`a-f`/`A-F` anywhere in the string -> radix 16; otherwise radix 10. It never uses radix 8.
So `00008` parses as decimal 8, and `--pad` exploits that to keep an edit same-length.

Usage:
  py -3.12 re/tools/syspak_mod.py <pak> --get  FILE:SECTION:KEY
  py -3.12 re/tools/syspak_mod.py <pak> --set  FILE:SECTION:KEY=VALUE --out <newpak> [--pad]
  py -3.12 re/tools/syspak_mod.py <pak> --diff <otherpak>
  py -3.12 re/tools/syspak_mod.py --selftest

  --pad   left-pad a shorter numeric replacement with zeros to the original's length, so the
          edit stays same-length. Refuses if the value is longer than the original.
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import syspak_parse as sp  # noqa: E402


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def diff_runs(a, b):
    """-> list of (start, end) half-open ranges where a and b differ, as maximal runs.

    If the lengths differ, the tail of the longer buffer is reported as a final run.
    """
    runs, n = [], min(len(a), len(b))
    i = 0
    while i < n:
        if a[i] != b[i]:
            j = i
            while j < n and a[j] != b[j]:
                j += 1
            runs.append((i, j))
            i = j
        else:
            i += 1
    if len(a) != len(b):
        runs.append((n, max(len(a), len(b))))
    return runs


def _find_member(names, member):
    hit = [i for i, n in enumerate(names) if n.lower() == member.lower()]
    if len(hit) != 1:
        raise KeyError('%s matched %d members, expected exactly 1' % (member, len(hit)))
    return hit[0]


def _find_key(lines, section, key):
    """-> index into `lines` of the KEY=... line inside [SECTION]. Raises if not exactly one.

    Section membership runs from the [SECTION] header to the next header or end of file.
    Comparison ignores surrounding whitespace on both the section name and the key.
    """
    want = '[%s]' % section.strip().lower()
    starts = [i for i, ln in enumerate(lines) if ln.strip().lower() == want]
    if len(starts) != 1:
        raise KeyError('[%s] matched %d section headers, expected exactly 1' % (section, len(starts)))
    start = starts[0] + 1
    end = len(lines)
    for i in range(start, len(lines)):
        s = lines[i].strip()
        if s.startswith('[') and s.endswith(']'):
            end = i
            break
    hits = []
    for i in range(start, end):
        s = lines[i].strip()
        if '=' in s and s.split('=', 1)[0].strip().lower() == key.strip().lower():
            hits.append(i)
    if len(hits) != 1:
        raise KeyError('%s= matched %d lines inside [%s], expected exactly 1'
                       % (key, len(hits), section))
    return hits[0]


def parse_spec(spec):
    """'FILE:SECTION:KEY' or 'FILE:SECTION:KEY=VALUE' -> (file, section, key, value|None)."""
    value = None
    if '=' in spec:
        spec, value = spec.split('=', 1)
    parts = spec.split(':')
    if len(parts) != 3:
        raise ValueError('expected FILE:SECTION:KEY, got %r' % spec)
    return parts[0], parts[1], parts[2], value


def get_value(data, member, section, key):
    """-> (current_value_string, line_text)."""
    names, offs, toc_end, recs = sp.parse(data)
    idx = _find_member(names, member)
    lines = recs[idx]['lines']
    k = _find_key(lines, section, key)
    return lines[k].split('=', 1)[1].strip(), lines[k]


def set_value(data, member, section, key, value, pad=False):
    """-> (new_bytes, report dict). Rebuilds the archive with one key changed.

    Asserts the edit is confined to exactly one member before returning.
    """
    names, offs, toc_end, recs = sp.parse(data)
    idx = _find_member(names, member)
    base = [r['lines'] for r in recs]
    k = _find_key(base[idx], section, key)

    old_line = base[idx][k]
    old_value = old_line.split('=', 1)[1]
    lhs = old_line.split('=', 1)[0]

    new_value = value
    if pad:
        if len(new_value) > len(old_value.strip()):
            raise ValueError('--pad cannot shorten: %r is longer than %r'
                             % (new_value, old_value.strip()))
        new_value = new_value.rjust(len(old_value.strip()), '0')

    new_line = '%s=%s' % (lhs, new_value)

    lines = [list(r) for r in base]
    lines[idx][k] = new_line
    out = sp.build(names, lines)

    n2, o2, t2, r2 = sp.parse(out)
    if n2 != names:
        raise AssertionError('member names or order changed')
    changed = [i for i in range(len(names)) if r2[i]['lines'] != base[i]]
    if changed != [idx]:
        raise AssertionError('members changed: %s, expected only %d' % (changed, idx))
    if r2[idx]['lines'][k] != new_line:
        raise AssertionError('edited line did not survive the rebuild')

    runs = diff_runs(data, out)
    report = {
        'member': names[idx], 'line_index': k,
        'old_line': old_line, 'new_line': new_line,
        'same_length': len(out) == len(data),
        'delta': len(out) - len(data),
        'runs': runs, 'diff_bytes': sum(e - s for s, e in runs),
        'sha256': sha256(out), 'bytes': len(out),
    }
    return out, report


def print_report(rep, data, out):
    print('  member      %s (line %d)' % (rep['member'], rep['line_index']))
    print('  edit        %r -> %r' % (rep['old_line'], rep['new_line']))
    print('  re-parse    ok, exactly 1 member changed')
    print('  length      %d bytes (%+d)%s'
          % (rep['bytes'], rep['delta'], '  SAME LENGTH' if rep['same_length'] else ''))
    print('  byte diff   %d run(s), %d bytes' % (len(rep['runs']), rep['diff_bytes']))
    for s, e in rep['runs'][:6]:
        print('    [%d, %d) %d B  was %r now %r'
              % (s, e, e - s, data[s:e].decode('latin1'), out[s:e].decode('latin1')))
    if len(rep['runs']) > 6:
        print('    ... %d more run(s)' % (len(rep['runs']) - 6))
    if not rep['same_length']:
        print('  NOTE: length changed, so every subsequent record and TOC offset shifted.')
        print('        The diff is no longer evidence that the edit was surgical -- rely on')
        print('        the re-parse assertion above instead. Consider --pad.')
    print('  sha256      %s' % rep['sha256'])


def selftest():
    """Exercise the editing layer on a synthetic archive whose answers are known by hand."""
    names = ['A.ini', 'B.ini']
    recs = [
        ['[Admin]', 'Name=first', '[Tune]', 'Alpha=11000', 'Beta=7', '[Other]', 'Alpha=999'],
        ['[Admin]', 'Name=second', '[Tune]', 'Alpha=1'],
    ]
    pak = sp.build(names, recs)
    fails = []

    def check(label, cond):
        print('  %-46s %s' % (label, 'ok' if cond else 'FAIL'))
        if not cond:
            fails.append(label)

    n, o, t, r = sp.parse(pak)
    check('synthetic archive round-trips', [x['lines'] for x in r] == recs and n == names)

    v, _ = get_value(pak, 'A.ini', 'Tune', 'Alpha')
    check('get reads the right section (Tune not Other)', v == '11000')

    out, rep = set_value(pak, 'A.ini', 'Tune', 'Alpha', '00008')
    check('same-length set keeps archive length', rep['same_length'])
    check('same-length diff is only the digits', rep['diff_bytes'] <= 4)
    check('other member untouched', sp.parse(out)[3][1]['lines'] == recs[1])
    check('sibling [Other] Alpha untouched',
          sp.parse(out)[3][0]['lines'][6] == 'Alpha=999')

    out2, rep2 = set_value(pak, 'A.ini', 'Tune', 'Alpha', '8', pad=True)
    check('--pad produces the same bytes as explicit 00008', out2 == out)

    out3, rep3 = set_value(pak, 'A.ini', 'Tune', 'Alpha', '8')
    check('unpadded set shortens the archive', rep3['delta'] == -4)
    check('unpadded set still surgical (re-parse)',
          sp.parse(out3)[3][0]['lines'][3] == 'Alpha=8')

    for label, fn in (
        ('missing member raises', lambda: get_value(pak, 'nope.ini', 'Tune', 'Alpha')),
        ('missing section raises', lambda: get_value(pak, 'A.ini', 'Nope', 'Alpha')),
        ('missing key raises', lambda: get_value(pak, 'A.ini', 'Tune', 'Nope')),
        ('--pad refuses to lengthen',
         lambda: set_value(pak, 'A.ini', 'Tune', 'Alpha', '123456', pad=True)),
    ):
        try:
            fn()
            check(label, False)
        except (KeyError, ValueError):
            check(label, True)

    known = [
        (b'abcdef', b'abcdef', []),
        (b'abcdef', b'abXdef', [(2, 3)]),
        (b'abcdef', b'aXcdYf', [(1, 2), (4, 5)]),
        (b'abcd', b'abcdef', [(4, 6)]),
    ]
    for a, b, want in known:
        check('diff_runs %r vs %r' % (a, b), diff_runs(a, b) == want)

    print('syspak_mod selftest: %s' % ('FAILED (%d)' % len(fails) if fails else 'all passed'))
    return 1 if fails else 0


def main():
    argv = sys.argv[1:]
    if not argv or '--selftest' in argv:
        return selftest() if '--selftest' in argv else (print(__doc__) or 0)

    pak = argv[0]
    data = open(pak, 'rb').read()

    if '--get' in argv:
        spec = argv[argv.index('--get') + 1]
        member, section, key, _ = parse_spec(spec)
        value, line = get_value(data, member, section, key)
        print('%s [%s] %s = %s' % (member, section, key, value))
        print('  line: %r' % line)
        return 0

    if '--diff' in argv:
        other = open(argv[argv.index('--diff') + 1], 'rb').read()
        runs = diff_runs(data, other)
        print('%d run(s), %d bytes, lengths %d vs %d'
              % (len(runs), sum(e - s for s, e in runs), len(data), len(other)))
        for s, e in runs[:20]:
            print('  [%d, %d) %d B  %r -> %r'
                  % (s, e, e - s, data[s:e].decode('latin1'), other[s:e].decode('latin1')))
        if len(runs) > 20:
            print('  ... %d more run(s)' % (len(runs) - 20))
        return 0

    if '--set' in argv:
        spec = argv[argv.index('--set') + 1]
        member, section, key, value = parse_spec(spec)
        if value is None:
            print('--set needs FILE:SECTION:KEY=VALUE')
            return 1
        if '--out' not in argv:
            print('--set needs --out <path>')
            return 1
        out_path = argv[argv.index('--out') + 1]
        out, rep = set_value(data, member, section, key, value, pad='--pad' in argv)
        print('%s  ->  %s' % (pak, out_path))
        print_report(rep, data, out)
        with open(out_path, 'wb') as f:
            f.write(out)
        return 0

    print(__doc__)
    return 0


if __name__ == '__main__':
    sys.exit(main())
