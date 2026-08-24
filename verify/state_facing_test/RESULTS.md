# RESULTS — U-078 `state` rotation sense

**Run 2026-08-24.** Verdict: **H+** — a piece's canonical edge `c` presents at world dir
`(c + state) mod 4`. Every witness agrees, zero counterexamples. Full write-up and the caveats:
`re/analysis/NETWORK_RULE_ENGINE.md` §13 (and §14 for the blind code-side confirmation).

Reproduce with `python re/tools/state_facing.py`.

> **Reading the WITNESS 1 block below:** rows for `state 0` and `state 2` are tagged `-> H-` in the
> per-row output, which is a **display artifact, not evidence for H-**. A half turn is its own
> inverse, so those eight rows satisfy H+ and H- equally and the printer simply names one. The
> counts underneath are the real result: **H+ 16/16, H- 8/16**, i.e. all eight *discriminating*
> rows pick H+.

```
================================================================================
WITNESS 1  --  SIMNTWRK FUN_1000d73d @ 0x1000d73d, table DAT_1003123c @ 0x1003123c
================================================================================
  bit index = 4*edge + lane.  Row (state, dir) holds the four bit indices the engine
  probes when asked 'does this piece connect at world dir <dir>' for a piece at <state>.

  state 0  dir 0 (-1, 0) : bits [0, 1, 2, 3]      edge 0 == (dir+state) mod 4   -> H-
  state 0  dir 1 ( 0,-1) : bits [4, 5, 6, 7]      edge 1 == (dir+state) mod 4   -> H-
  state 0  dir 2 (+1, 0) : bits [8, 9, 10, 11]    edge 2 == (dir+state) mod 4   -> H-
  state 0  dir 3 ( 0,+1) : bits [12, 13, 14, 15]  edge 3 == (dir+state) mod 4   -> H-
  state 1  dir 0 (-1, 0) : bits [15, 12, 13, 14]  edge 3 == (dir-state) mod 4   -> H+
  state 1  dir 1 ( 0,-1) : bits [3, 0, 1, 2]      edge 0 == (dir-state) mod 4   -> H+
  state 1  dir 2 (+1, 0) : bits [7, 4, 5, 6]      edge 1 == (dir-state) mod 4   -> H+
  state 1  dir 3 ( 0,+1) : bits [11, 8, 9, 10]    edge 2 == (dir-state) mod 4   -> H+
  state 2  dir 0 (-1, 0) : bits [10, 11, 8, 9]    edge 2 == (dir+state) mod 4   -> H-
  state 2  dir 1 ( 0,-1) : bits [14, 15, 12, 13]  edge 3 == (dir+state) mod 4   -> H-
  state 2  dir 2 (+1, 0) : bits [2, 3, 0, 1]      edge 0 == (dir+state) mod 4   -> H-
  state 2  dir 3 ( 0,+1) : bits [6, 7, 4, 5]      edge 1 == (dir+state) mod 4   -> H-
  state 3  dir 0 (-1, 0) : bits [5, 6, 7, 4]      edge 1 == (dir-state) mod 4   -> H+
  state 3  dir 1 ( 0,-1) : bits [9, 10, 11, 8]    edge 2 == (dir-state) mod 4   -> H+
  state 3  dir 2 (+1, 0) : bits [13, 14, 15, 12]  edge 3 == (dir-state) mod 4   -> H+
  state 3  dir 3 ( 0,+1) : bits [1, 2, 3, 0]      edge 0 == (dir-state) mod 4   -> H+

  rows consistent with H+ : 16 / 16
  rows consistent with H- :  8 / 16

  Read the winning form the other way round: a canonical edge c of the piece is
  answered when the world dir queried is d with (d - state) == c, i.e. edge c PRESENTS
  AT world dir (c + state) mod 4.
  Full closed form  row(s,d)[k] == 4*((d-s) mod 4) + ((k-s) mod 4) holds for all 16 rows: True
  (both indices of the 4x4 bit field turn together -- a rigid quarter turn, not a relabelling)

================================================================================
WITNESS 2  --  *_final.txt : occupied orthogonal neighbours -> (pieceId, state)
================================================================================
  95 rules across 6 files, 40 (file,id) families
  HWAY_GRND_final.txt      id 73      s0={W,N,S}  s2={N,E,S}
  HWAY_GRND_final.txt      id 15051   s0={W,N,E}  s2={W,E,S}
  HWAY_GRND_final.txt      id 15149   s0={W,N,E,S}
  PIPE_GRND_final.txt      id 334     s0={N,S}
  PIPE_GRND_final.txt      id 335     s0={W,E}
  PIPE_GRND_final.txt      id 344     s0={W,N,S}  s2={N,E,S}
  PIPE_GRND_final.txt      id 347     s0={W,N,E}  s2={W,E,S}
  PIPE_GRND_final.txt      id 348     s0={W,N,E,S}
  PIPE_GRND_final.txt      id 11606   s0={W,S}  s2={N,E}
  PIPE_GRND_final.txt      id 11607   s0={W,N}  s2={E,S}
  PIPE_GRND_final.txt      id 18012   s0={S}  s2={N}
  PIPE_GRND_final.txt      id 18016   s0={W}  s2={E}
  POWR_GRND_final.txt      id 20      s0={W,S}  s2={N,E}
  POWR_GRND_final.txt      id 23      s0={W,N}  s2={E,S}
  POWR_GRND_final.txt      id 24      s0={W,N,S}  s2={N,E,S}
  POWR_GRND_final.txt      id 26      s0={W,N,E}  s2={W,E,S}
  POWR_GRND_final.txt      id 28      s0={W,N,E,S}
  POWR_GRND_final.txt      id 92      s0={W,E}  s1={N,S}
  POWR_GRND_final.txt      id 10036   s0={W}  s2={E}
  POWR_GRND_final.txt      id 10037   s0={S}  s2={N}
  RAIL_GRND_final.txt      id 44      s0={W,E}  s1={N,S}
  RAIL_GRND_final.txt      id 54      s0={W,N,S}  s1={W,N,E}  s2={N,E,S}  s3={W,E,S}
  RAIL_GRND_final.txt      id 58      s0={W,N,E,S}
  RAIL_GRND_final.txt      id 16036   s0={W,S}  s1={W,N}  s2={N,E}  s3={E,S}
  RAIL_GRND_final.txt      id 18000   s0={S}  s2={N}
  RAIL_GRND_final.txt      id 18002   s0={W}  s2={E}
  ROAD_GRND_final.txt      id 29      s0={W,E}  s1={N,S}
  ROAD_GRND_final.txt      id 39      s0={W,N,S}  s1={W,N,E}  s2={N,E,S}  s3={W,E,S}
  ROAD_GRND_final.txt      id 43      s0={W,N,E,S}
  ROAD_GRND_final.txt      id 11203   s0={W,S}  s1={W,N}  s2={N,E}  s3={E,S}
  ROAD_GRND_final.txt      id 11225   s0={S}  s1={W}  s2={N}  s3={E}
  SUBW_GRND_final.txt      id 329     s0={W,N,S}  s2={N,E,S}
  SUBW_GRND_final.txt      id 332     s0={W,N,E}  s2={W,E,S}
  SUBW_GRND_final.txt      id 333     s0={W,N,E,S}
  SUBW_GRND_final.txt      id 11605   s0={W,S}  s2={N,E}
  SUBW_GRND_final.txt      id 11611   s0={W,E}
  SUBW_GRND_final.txt      id 11612   s0={N,S}
  SUBW_GRND_final.txt      id 11613   s0={W,N}  s2={E,S}
  SUBW_GRND_final.txt      id 18010   s0={S}  s2={N}
  SUBW_GRND_final.txt      id 18014   s0={W}  s2={E}

  ----------------------------------------------------------------------------
  EQUIVARIANCE.  A family is consistent with H(sign) iff one canonical set explains
  every state it appears in: canonical(s) = rot(observed(s), -sign*s) is constant.
  Only families that appear at state 1 or 3 can tell H+ from H- at all (a half turn
  is its own inverse), and a rotationally symmetric shape cannot either.  Those are
  counted separately as DISCRIMINATING.
  ----------------------------------------------------------------------------

  H+ : 80 rules explained, 0 contradicted   (40 families clean, 0 broken)

  H- : 70 rules explained, 10 contradicted   (35 families clean, 5 broken)
     COUNTEREXAMPLE RAIL_GRND_final.txt      id 54     s0={W,N,S}->canon {W,N,S}  s1={W,N,E}->canon {N,E,S}  s2={N,E,S}->canon {W,N,S}  s3={W,E,S}->canon {N,E,S}
     COUNTEREXAMPLE RAIL_GRND_final.txt      id 16036  s0={W,S}->canon {W,S}  s1={W,N}->canon {N,E}  s2={N,E}->canon {W,S}  s3={E,S}->canon {N,E}
     COUNTEREXAMPLE ROAD_GRND_final.txt      id 39     s0={W,N,S}->canon {W,N,S}  s1={W,N,E}->canon {N,E,S}  s2={N,E,S}->canon {W,N,S}  s3={W,E,S}->canon {N,E,S}
     COUNTEREXAMPLE ROAD_GRND_final.txt      id 11203  s0={W,S}->canon {W,S}  s1={W,N}->canon {N,E}  s2={N,E}->canon {W,S}  s3={E,S}->canon {N,E}
     COUNTEREXAMPLE ROAD_GRND_final.txt      id 11225  s0={S}->canon {S}  s1={W}->canon {N}  s2={N}->canon {S}  s3={E}->canon {N}

  DISCRIMINATING families (H+ and H- actually differ): 5
     RAIL_GRND_final.txt      id 54     states [0, 1, 2, 3]   -> H+
     RAIL_GRND_final.txt      id 16036  states [0, 1, 2, 3]   -> H+
     ROAD_GRND_final.txt      id 39     states [0, 1, 2, 3]   -> H+
     ROAD_GRND_final.txt      id 11203  states [0, 1, 2, 3]   -> H+
     ROAD_GRND_final.txt      id 11225  states [0, 1, 2, 3]   -> H+
     rows in discriminating families: 20, all favouring H+

  ----------------------------------------------------------------------------
  THE ABSOLUTE ZERO, under H+ : the connection set a piece has at state 0.
  ----------------------------------------------------------------------------
  HWAY_GRND_final.txt      id 73     T-junction       state0 = {W,N,S}       states seen [0, 2]
  HWAY_GRND_final.txt      id 15051  T-junction       state0 = {W,N,E}       states seen [0, 2]
  HWAY_GRND_final.txt      id 15149  crossroads       state0 = {W,N,E,S}     states seen [0]
  PIPE_GRND_final.txt      id 334    2-arm            state0 = {N,S}         states seen [0]
  PIPE_GRND_final.txt      id 335    2-arm            state0 = {W,E}         states seen [0]
  PIPE_GRND_final.txt      id 344    T-junction       state0 = {W,N,S}       states seen [0, 2]
  PIPE_GRND_final.txt      id 347    T-junction       state0 = {W,N,E}       states seen [0, 2]
  PIPE_GRND_final.txt      id 348    crossroads       state0 = {W,N,E,S}     states seen [0]
  PIPE_GRND_final.txt      id 11606  2-arm            state0 = {W,S}         states seen [0, 2]
  PIPE_GRND_final.txt      id 11607  2-arm            state0 = {W,N}         states seen [0, 2]
  PIPE_GRND_final.txt      id 18012  STUB (dead end)  state0 = {S}           states seen [0, 2]
  PIPE_GRND_final.txt      id 18016  STUB (dead end)  state0 = {W}           states seen [0, 2]
  POWR_GRND_final.txt      id 20     2-arm            state0 = {W,S}         states seen [0, 2]
  POWR_GRND_final.txt      id 23     2-arm            state0 = {W,N}         states seen [0, 2]
  POWR_GRND_final.txt      id 24     T-junction       state0 = {W,N,S}       states seen [0, 2]
  POWR_GRND_final.txt      id 26     T-junction       state0 = {W,N,E}       states seen [0, 2]
  POWR_GRND_final.txt      id 28     crossroads       state0 = {W,N,E,S}     states seen [0]
  POWR_GRND_final.txt      id 92     2-arm            state0 = {W,E}         states seen [0, 1]
  POWR_GRND_final.txt      id 10036  STUB (dead end)  state0 = {W}           states seen [0, 2]
  POWR_GRND_final.txt      id 10037  STUB (dead end)  state0 = {S}           states seen [0, 2]
  RAIL_GRND_final.txt      id 44     2-arm            state0 = {W,E}         states seen [0, 1]
  RAIL_GRND_final.txt      id 54     T-junction       state0 = {W,N,S}       states seen [0, 1, 2, 3]
  RAIL_GRND_final.txt      id 58     crossroads       state0 = {W,N,E,S}     states seen [0]
  RAIL_GRND_final.txt      id 16036  2-arm            state0 = {W,S}         states seen [0, 1, 2, 3]
  RAIL_GRND_final.txt      id 18000  STUB (dead end)  state0 = {S}           states seen [0, 2]
  RAIL_GRND_final.txt      id 18002  STUB (dead end)  state0 = {W}           states seen [0, 2]
  ROAD_GRND_final.txt      id 29     2-arm            state0 = {W,E}         states seen [0, 1]
  ROAD_GRND_final.txt      id 39     T-junction       state0 = {W,N,S}       states seen [0, 1, 2, 3]
  ROAD_GRND_final.txt      id 43     crossroads       state0 = {W,N,E,S}     states seen [0]
  ROAD_GRND_final.txt      id 11203  2-arm            state0 = {W,S}         states seen [0, 1, 2, 3]
  ROAD_GRND_final.txt      id 11225  STUB (dead end)  state0 = {S}           states seen [0, 1, 2, 3]
  SUBW_GRND_final.txt      id 329    T-junction       state0 = {W,N,S}       states seen [0, 2]
  SUBW_GRND_final.txt      id 332    T-junction       state0 = {W,N,E}       states seen [0, 2]
  SUBW_GRND_final.txt      id 333    crossroads       state0 = {W,N,E,S}     states seen [0]
  SUBW_GRND_final.txt      id 11605  2-arm            state0 = {W,S}         states seen [0, 2]
  SUBW_GRND_final.txt      id 11611  2-arm            state0 = {W,E}         states seen [0]
  SUBW_GRND_final.txt      id 11612  2-arm            state0 = {N,S}         states seen [0]
  SUBW_GRND_final.txt      id 11613  2-arm            state0 = {W,N}         states seen [0, 2]
  SUBW_GRND_final.txt      id 18010  STUB (dead end)  state0 = {S}           states seen [0, 2]
  SUBW_GRND_final.txt      id 18014  STUB (dead end)  state0 = {W}           states seen [0, 2]

  Grouped by state-0 set -- the shipped art uses TWO zeros, one quarter turn apart:
    state0 {W}          (deg 1) : PIPE/18016, POWR/10036, RAIL/18002, SUBW/18014
    state0 {S}          (deg 1) : PIPE/18012, POWR/10037, RAIL/18000, ROAD/11225, SUBW/18010
    state0 {W,N}        (deg 2) : PIPE/11607, POWR/23, SUBW/11613
    state0 {W,E}        (deg 2) : PIPE/335, POWR/92, RAIL/44, ROAD/29, SUBW/11611
    state0 {W,S}        (deg 2) : PIPE/11606, POWR/20, RAIL/16036, ROAD/11203, SUBW/11605
    state0 {N,S}        (deg 2) : PIPE/334, SUBW/11612
    state0 {W,N,E}      (deg 3) : HWAY/15051, PIPE/347, POWR/26, SUBW/332
    state0 {W,N,S}      (deg 3) : HWAY/73, PIPE/344, POWR/24, RAIL/54, ROAD/39, SUBW/329
    state0 {W,N,E,S}    (deg 4) : HWAY/15149, PIPE/348, POWR/28, RAIL/58, ROAD/43, SUBW/333

  Selector 0 (isolated tile, no facing constraint) rules, excluded from the fit:
    PIPE_GRND_final.txt      selector 0 -> id 348 state 0
    POWR_GRND_final.txt      selector 0 -> id 28 state 0
    RAIL_GRND_final.txt      selector 0 -> id 58 state 0
    ROAD_GRND_final.txt      selector 0 -> id 43 state 0
    SUBW_GRND_final.txt      selector 0 -> id 333 state 0

================================================================================
WIDENED SAMPLE  --  stage 1 (*SIMPLERULES*.txt, mode 8), subset test
================================================================================
  HWAY_GRND_SIMPLERULES.txt    {'unknown': 122, 'both': 36}
  PIPE_GRND_SIMPLERULES.txt    {'both': 70, 'unknown': 272}
  POWR_GRND_SIMPLERULES.txt    {'both': 54}
  RAIL_GRND_SIMPLERULES.txt    {'both': 190, 'H+ only': 8, 'unknown': 136}
  ROAD_GRND_SimpleRules.txt    {'both': 60, 'H+ only': 18, 'unknown': 352}
  SUBW_GRND_SIMPLERULES.txt    {'both': 70, 'unknown': 272}

  centre results 1660   (shape unknown 1154)
  satisfied by BOTH signs (non-discriminating) : 480
  satisfied by H+ ONLY                          : 26
  satisfied by H- ONLY                          : 0
  satisfied by NEITHER                          : 0

================================================================================
CROSS-CHECK  --  *_Convert.txt / *_Complex_Convert.txt state equivariance
================================================================================
  HWAY_GRND_Complex_Convert.txt     28 id-pairs with >=2 states :  28 equivariant,   0 not
  HWAY_GRND_Convert.txt             36 id-pairs with >=2 states :  36 equivariant,   0 not
  PIPE_GRND_Complex_Convert.txt     12 id-pairs with >=2 states :  12 equivariant,   0 not
  PIPE_GRND_Convert.txt             12 id-pairs with >=2 states :  12 equivariant,   0 not
  POWR_GRND_Complex_Convert.txt      2 id-pairs with >=2 states :   2 equivariant,   0 not
  POWR_GRND_Convert.txt              6 id-pairs with >=2 states :   6 equivariant,   0 not
  RAIL_GRND_Complex_Convert.txt     16 id-pairs with >=2 states :  16 equivariant,   0 not
  RAIL_GRND_Convert.txt             16 id-pairs with >=2 states :  16 equivariant,   0 not
  ROAD_GRND_Complex_Convert.txt     45 id-pairs with >=2 states :  45 equivariant,   0 not
  ROAD_GRND_Convert.txt             46 id-pairs with >=2 states :  46 equivariant,   0 not
  SUBW_GRND_Complex_Convert.txt      7 id-pairs with >=2 states :   7 equivariant,   0 not
  SUBW_GRND_Convert.txt             23 id-pairs with >=2 states :  23 equivariant,   0 not

  TOTAL 249 id-pairs : 249 equivariant, 0 not

================================================================================
NOT EVIDENCE-GRADE PROBE -- TrBlkAtt.IXF exemplar blobs
================================================================================
  337 piece ids carry a {0x625c6226,0x825c6289,id*0x100+state} record here.
  Looking for any byte that steps by a constant multiple of 8 (mod 32) as state
  advances 0->1->2->3.  8/32 of a turn == 90 degrees.

  step histogram: {8: 25, 24: 2}   (+8 = the H+ sense, +24 = -8 = the H- sense)

  step +8, 25 (piece, offset) hits:
     id 35     off 0x05a vals [0, 8, 16, 24]       record lens [281, 281, 281, 281]
     id 35     off 0x064 vals [24, 0, 8, 16]       record lens [281, 281, 281, 281]
     id 9051   off 0x05a vals [0, 8, 16, 24]       record lens [281, 281, 281, 281]
     id 9051   off 0x064 vals [24, 0, 8, 16]       record lens [281, 281, 281, 281]
     id 11203  off 0x064 vals [24, 0, 8, 16]       record lens [281, 281, 281, 281]
     id 11208  off 0x0aa vals [16, 24, 0, 8]       record lens [463, 463, 463, 463]
     id 11208  off 0x0b4 vals [0, 8, 16, 24]       record lens [463, 463, 463, 463]
     id 11210  off 0x0aa vals [16, 24, 0, 8]       record lens [463, 463, 463, 463]
     id 11210  off 0x0b4 vals [16, 24, 0, 8]       record lens [463, 463, 463, 463]
     id 11225  off 0x03c vals [24, 0, 8, 16]       record lens [179, 179, 179, 179]
     id 11225  off 0x064 vals [24, 0, 8, 16]       record lens [179, 179, 179, 179]
     id 14094  off 0x098 vals [0, 8, 16, 24]       record lens [161, 161, 161, 161]
     id 15099  off 0x098 vals [8, 16, 24, 0]       record lens [161, 161, 161, 161]
     id 15100  off 0x079 vals [16, 24, 0, 8]       record lens [161, 161, 161, 161]
     id 15101  off 0x079 vals [24, 0, 8, 16]       record lens [161, 161, 161, 161]
     id 15102  off 0x098 vals [0, 8, 16, 24]       record lens [161, 161, 161, 161]
     id 15103  off 0x098 vals [8, 16, 24, 0]       record lens [161, 161, 161, 161]
     id 15104  off 0x079 vals [16, 24, 0, 8]       record lens [161, 161, 161, 161]
     id 15105  off 0x079 vals [24, 0, 8, 16]       record lens [161, 161, 161, 161]
     id 16046  off 0x098 vals [8, 16, 24, 0]       record lens [161, 161, 161, 161]
     id 16047  off 0x079 vals [24, 0, 8, 16]       record lens [161, 161, 161, 161]
     id 16054  off 0x098 vals [16, 24, 0, 8]       record lens [161, 161, 161, 161]
     id 16055  off 0x079 vals [0, 8, 16, 24]       record lens [161, 161, 161, 161]
     id 18004  off 0x03c vals [16, 24, 0, 8]       record lens [179, 179, 179, 179]
     id 18004  off 0x064 vals [16, 24, 0, 8]       record lens [179, 179, 179, 179]

  step +24, 2 (piece, offset) hits:
     id 14013  off 0x064 vals [24, 16, 8, 0]       record lens [281, 281, 281, 281]
     id 14030  off 0x064 vals [16, 8, 0, 24]       record lens [322, 322, 322, 322]

  READ THIS CAREFULLY: the two step -8 hits sit at offset 0x64 in records of length
  281 and 322, while the step +8 hits at 0x64 are in records of length 179.  Different
  lengths mean offset 0x64 is not known to be the same field, so these are NOT
  counterexamples to H+ -- they are an artefact of probing an unparsed format.
  Closing this properly needs the BIN
 property-blob format decoded.  Until then this
  section supports nothing and refutes nothing.
```
