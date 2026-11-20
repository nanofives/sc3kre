#!/usr/bin/env python3
r"""rewards.py - task sc4civ (2026-11-19l): when SimCity 4 offers a reward, read from its own Lua scripts.

SC4 keeps the reward conditions in Lua, not in the building exemplars (re/analysis/SC4_FORMATS.md 10). SimCity_1.dat
holds 158 Lua scripts (DBPF type 0xCA63E2A3, group 0x4A5E8EF6, plain Latin-1 text). 60 records there start with
`a = create_reward_<advisor>('<building exemplar instance>')` and hold a `function a.condition()` whose first branch
returns the "not yet" answer when the city falls short, e.g. the Mayor's House:

    if (not missions_completed(...) and game.g_population < tuning_constants.MAYOR_HOUSE_POP) then

`tuning_constants.<NAME> = <number>` lines (one script, unconditional assignments) give the thresholds.

What is taken: every comparison `<population> < <threshold>` in the condition, where <population> is one game
variable whose name ends in `population` or a sum of them with `+`, and <threshold> a tuning constant, a number times
a tuning constant (the Casino: `1.6 * tuning_constants.POPULATION_STEP_6`) or a number. SC3's reward row has one population and one year (CIVIC_REWARD.md 2.1), so a comparison maps to it only when
it counts the whole city: `g_population`, `g_city_r_population` (SC4's residents) or the sum of the three residential
wealths `g_city_r1/r2/r3_population`. The largest such threshold is the SC3 population. Other measures (high-wealth
residents only, jobs, the region) and the other conditions (mayor rating, funds, buildings, missions) have no SC3
column: they go into the note, and a reward without a whole-city population gets the stated default. No SC4 reward
condition reads the year (0 of 60): year 0.

Comments (`--` to the end of the line) are removed first; the scripts use no block comments (0 `--[[` in 158).
The same steps in sc4web.js (luaRewards): plain regular expressions, the same order.
"""
import re

T_LUA = 0xCA63E2A3
FAIR = ('g_population', 'g_city_r_population', 'g_city_r1_population+g_city_r2_population+g_city_r3_population')
COMMENT_RE = re.compile(r'--[^\n]*')
CONST_RE = re.compile(r'(?m)^[ \t]*tuning_constants\.([A-Za-z0-9_]+)[ \t]*=[ \t]*(-?[0-9]+(?:\.[0-9]+)?)')
RECORD_RE = re.compile(r"(?m)^[ \t]*a[ \t]*=[ \t]*create_reward_([A-Za-z_]+)[ \t]*\([ \t]*'([0-9A-Fa-f]{8})'[ \t]*\)")
COND_RE = re.compile(r'function[ \t]+a\.condition[ \t]*\([ \t]*\)(.*?)\nend', re.S)
POPVAR = r'game\.g_[a-z0-9_]*population'
THRESH = r'(?:([0-9]+(?:\.[0-9]+)?)[ \t]*\*[ \t]*)?(tuning_constants\.[A-Za-z0-9_]+)|([0-9]+(?:\.[0-9]+)?)(?![0-9.])'
CMP_RE = re.compile(r'(' + POPVAR + r'(?:[ \t]*\+[ \t]*' + POPVAR + r')*)[ \t]*<[ \t]*(?:' + THRESH + ')')
GAMEVAR_RE = re.compile(r'game\.([A-Za-z0-9_]+)')


def scripts(idx):
    """Lua scripts of the index, in index order: [(instance, text)]."""
    out = []
    for k in idx.of_type(T_LUA):
        try:
            out.append((k[2], idx.read(k).decode('latin-1')))
        except (ValueError, KeyError):
            continue
    return out


def lua_rewards(idx):
    """-> {building instance: {advisor, population (or None), measure, threshold, others [game variables]}}."""
    texts = [COMMENT_RE.sub('', t) for _i, t in scripts(idx)]
    consts = {}
    for t in texts:
        for m in CONST_RE.finditer(t):
            v = float(m.group(2))
            consts[m.group(1)] = int(v) if v == int(v) else v
    out = {}
    for t in texts:
        heads = list(RECORD_RE.finditer(t))
        for n, h in enumerate(heads):
            body = t[h.end():heads[n + 1].start() if n + 1 < len(heads) else len(t)]
            cm = COND_RE.search(body)
            cond = cm.group(1) if cm else ''
            cmps = []
            for m in CMP_RE.finditer(cond):
                var = '+'.join(x.strip()[5:] for x in m.group(1).split('+'))
                fac, th, lit = m.group(2), m.group(3), m.group(4)
                if th:                    # a tuning constant, times a factor (the Casino: 1.6 * POPULATION_STEP_6)
                    val = consts.get(th[17:])
                    if val is not None and fac:
                        val = float(fac) * val
                else:
                    val = float(lit)
                if isinstance(val, float) and val == int(val):
                    val = int(val)
                cmps.append({'measure': var, 'threshold': ((fac + ' * ') if fac else '') + th if th else None,
                             'value': val})
            fair = [c for c in cmps if c['measure'] in FAIR and isinstance(c['value'], int)]
            best = None
            for c in fair:
                if best is None or c['value'] > best['value']:
                    best = c
            pops = set(c['measure'] for c in cmps)
            others = []
            for m in GAMEVAR_RE.finditer(cond):
                v = m.group(1)
                if v not in others and not any(v in p.split('+') for p in pops):
                    others.append(v)
            out[int(h.group(2), 16)] = {
                'advisor': h.group(1), 'population': best['value'] if best else None,
                'measure': best['measure'] if best else None, 'threshold': best['threshold'] if best else None,
                'compares': [[c['measure'], c['value']] for c in cmps], 'others': sorted(others)}
    return out


def main(argv):
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import catalog as C
    idx = C.Index(argv[1])
    for inst, r in sorted(lua_rewards(idx).items()):
        print('%08X %-12s pop %-8s %-30s %s | %s' % (inst, r['advisor'], r['population'], r['measure'],
                                                     r['compares'], ','.join(r['others'])))


if __name__ == '__main__':
    import sys
    main(sys.argv)
