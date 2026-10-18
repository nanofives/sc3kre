# Stock highway intersections (measured 2026-10-18, lab city, sc3netmod + 7 avenue packages installed, highways untouched)

Lab: `Simcity_stock_diagave\re\harness\inst_dav\hw_lab.sc3` (copy of dav_lab_orig), Highway tool = menu command
`0x10004301`, drags with rb_lab's road verb (`--alt 82`). Funds: the treasury is an int64 found by memory scan
(two copies 8 bytes apart); writing both took the HUD from $4,937 to $1,998,200.

Shapes (cells x,z; `id.state`):
- Straight highway = 2 cells wide, one cell per direction: along x 15051.2 / 15051.0, along z 73.2 / 73.0, end caps
  15053/15054 (x) and 11235/11237 (z). Slopes put 14094 / 15099..15105 in.
- Diagonal highway = 3-cell band per row like the diagonal avenue: 11223.2 / 11224.0 / 11223.0 (x-z family),
  15052.2 / 15106.0 / 15052.0 (x+z family), end caps 14999 / 15059.
- Straight X on flat ground = 4x4: centre 2x2 15113/15114, x arms 15107/15108, z arms 15150/15153. One highway
  bridges over the other through a short underpass. No ramps between the two highways.
- The same X on sloped ground stayed 2x2 15149 "Highway Construction" through three game years (sim running).
- T: a stem that stops beside the through highway gets its end cap (no connection). A highway that runs into the
  other's side leaves 15149.
- Diagonal x straight: two 2-cell 15149 blocks, the diagonal turns into 73 pieces beside them. Never resolves.
- Diagonal x diagonal: the game makes a straight 4x4 stub (15051 / 73 arms) around a 2x2 15149. Never resolves.
- Shipped cities: Berlin has one 6x6 X with corner ramp pieces 15121..15128 (box 212..217 x 117..122); most other
  "Highway Interchange" ids (15115..15120) sit beside on-ramps. Diagonal highways are common (Sacramento 633 cells);
  they bend into straights through 15026/15027, 15089/15090, 16025/16026, 15076/15077, 14010/14014, 15055/15056.
  A short diagonal drawn across a corner of the lab X did NOT make Berlin's ramps (it ran past the corner and left
  15149), so how Berlin's ramps were made is open.

Owner sheet: `owner_shots/stock_highway_intersections.png` (shots hw_013, hw_022, hw_031, hw_040).
