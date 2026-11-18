"""Writes the sample OBJs (units: meters, Y up). Run: py -3.12 make_samples.py"""
import os
here = os.path.dirname(os.path.abspath(__file__))

class M:
    def __init__(s, name): s.name = name; s.v = []; s.f = []
    def box(s, x0, y0, z0, x1, y1, z1):
        b = len(s.v)
        s.v += [(x0,y0,z0),(x1,y0,z0),(x1,y0,z1),(x0,y0,z1),(x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1)]
        for q in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):
            s.f.append(tuple(b+i+1 for i in q))
    def roof(s, x0, y0, z0, x1, z1, h):
        b = len(s.v); xm = (x0+x1)/2
        s.v += [(x0,y0,z0),(x1,y0,z0),(x1,y0,z1),(x0,y0,z1),(xm,y0+h,z0),(xm,y0+h,z1)]
        s.f += [(b+1,b+2,b+5),(b+3,b+4,b+6),(b+1,b+5,b+6,b+4),(b+2,b+3,b+6,b+5)]
    def save(s):
        with open(os.path.join(here, s.name), 'w', newline='\n') as fh:
            fh.write('# %s, meters, Y up\n' % s.name)
            for v in s.v: fh.write('v %.3f %.3f %.3f\n' % v)
            for f in s.f: fh.write('f ' + ' '.join(map(str, f)) + '\n')

m = M('house_a.obj'); m.box(-4,0,-3,4,5,3); m.roof(-4.5,5,-3.5,4.5,3.5,4); m.save()
m = M('shop_a.obj'); m.box(-7,0,-6,7,6,6); m.box(-7.5,6,-6.5,7.5,6.6,6.5); m.save()
m = M('factory_a.obj'); m.box(-14,0,-10,14,11,10); m.box(8,11,-4,11,26,-1); m.box(-14,11,-10,14,12,10); m.save()
