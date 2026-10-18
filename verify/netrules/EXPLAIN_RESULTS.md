# netrules explain: two example outputs (2026-10-13)

Command: `py -3 -m netmod.netrules explain <save> <x> <z> --net <NET>` from re/tools, stock rules, default options.
Coordinates: x, z = the save's network grid. Offsets are printed as x+-n / z+-n (the engine has no compass).

## 1. Agreeing tile: Farmsville ROAD x=100 z=128 (the in-game check's road)

```text
Farmsville.sc3 ROAD cell x=100 z=128
saved: 29/0   simulated (from-scratch retile of all 1414 ROAD tiles): 29/0
saved neighbourhood (surface layer):
             x-2       x-1         x       x+1       x+2
   z-2      bldg      bldg      bldg         .         .
   z-1      bldg      bldg      bldg         .         .
     z      29/0      29/0    [29/0]      29/0      29/0
   z+1         .         .         .         .   10037/0
   z+2         .         .         .         .      92/1
events (in engine order):
  [Simple pass 1] here: mask 0x5 (x-1 x+1)
      first match ROAD_GRND_SimpleRules.txt #21 (line 102): selector 0x5 (x-1 x+1), if [-] then [self:29/0]
      committed; this cell is now 29/0
  [Complex pass 1] here: mask 0x0 (none), no rule
      observed: x-2z-2:empty-or-foreign, x-2z-1:empty-or-foreign, x-2:29/0, x-2z+1:empty, x-2z+2:empty, x-1z-2:empty-or-foreign, x-1z-1:empty-or-foreign, x-1:29/0, x-1z+1:empty, x-1z+2:empty, z-2:empty-or-foreign, z-1:empty-or-foreign, self:29/0, z+1:empty, z+2:empty, x+1z-2:empty, x+1z-1:empty, x+1:29/0, x+1z+1:empty, x+1z+2:empty, x+2z-2:empty, x+2z-1:empty, x+2:29/0, x+2z+1:empty-or-foreign, x+2z+2:empty-or-foreign
  [Complex pass 2] here: mask 0x0 (none), no rule
      observed: x-2z-2:empty-or-foreign, x-2z-1:empty-or-foreign, x-2:29/0, x-2z+1:empty, x-2z+2:empty, x-1z-2:empty-or-foreign, x-1z-1:empty-or-foreign, x-1:29/0, x-1z+1:empty, x-1z+2:empty, z-2:empty-or-foreign, z-1:empty-or-foreign, self:29/0, z+1:empty, z+2:empty, x+1z-2:empty, x+1z-1:empty, x+1:29/0, x+1z+1:empty, x+1z+2:empty, x+2z-2:empty, x+2z-1:empty, x+2:29/0, x+2z+1:empty-or-foreign, x+2z+2:empty-or-foreign
verdict: agrees with the save
```r

## 2. Disagreeing tile: Farmsville POWR x=9 z=94 (class pole-phase)

```text
Farmsville.sc3 POWR cell x=9 z=94
saved: 15/0   simulated (from-scratch retile of all 461 POWR tiles): 92/1
saved neighbourhood (surface layer):
             x-2       x-1         x       x+1       x+2
   z-2         .         .      24/2      92/0      92/0
   z-1         .         .      92/1         .         .
     z         .         .    [15/0]         .         .
   z+1         .         .      92/1         .         .
   z+2         .         .      92/1         .         .
events (in engine order):
  [Simple pass 1] here: mask 0xa (z-1 z+1)
      first match POWR_GRND_SIMPLERULES.txt #9 (line 38): selector 0xa (z-1 z+1), if [-] then [self:92/1]
      committed; this cell is now 92/1
  [Complex pass 1] here: mask 0x0 (none), no rule
      observed: x-2z-2:empty, x-2z-1:empty, x-2:empty, x-2z+1:empty, x-2z+2:empty, x-1z-2:empty, x-1z-1:empty, x-1:empty, x-1z+1:empty, x-1z+2:empty, z-2:pending, z-1:92/1, self:92/1, z+1:92/1, z+2:92/1, x+1z-2:92/0, x+1z-1:empty, x+1:empty, x+1z+1:empty, x+1z+2:empty, x+2z-2:92/0, x+2z-1:empty, x+2:empty, x+2z+1:empty, x+2z+2:empty
  [Complex pass 2] here: mask 0x0 (none), no rule
      observed: x-2z-2:empty, x-2z-1:empty, x-2:empty, x-2z+1:empty, x-2z+2:empty, x-1z-2:empty, x-1z-1:empty, x-1:empty, x-1z+1:empty, x-1z+2:empty, z-2:pending, z-1:92/1, self:92/1, z+1:15/0, z+2:92/1, x+1z-2:92/0, x+1z-1:empty, x+1:empty, x+1z+1:empty, x+1z+2:empty, x+2z-2:92/0, x+2z-1:empty, x+2:empty, x+2z+1:empty, x+2z+2:empty
verdict: DISAGREES, class 'pole-phase': POWR pole 14/15 positions differ inside a straight pole run: Complex rules #34/#58 make a pole where the line runs straight 2 cells each way, #20-33/#35-36 and #44-57/#59-60 place the next one 4 cells from any pole or non-straight piece, in work-list order, so the poles record the order and extent of past retiles, which a save does not keep
```r
