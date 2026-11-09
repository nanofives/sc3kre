# avdir: cars driving against the painted avenue lanes (owner 2026-11-09)

Owner report (MARIANO-PC, Big One autosave, screenshot): "they are driving on the opposite way of the lane they are driving".

## Cause
The avenue was one AVL leaves two-way (its end under the highway is a ramp piece 21227 + highway crossing 15098, not a
U-turn pair / corner / avlj join). AVP (task avpaint, 2026-10-28) paints such bands with LOOK-ONLY twins (21742 on
straights) that keep the STOCK two-way lanes, and avenue_markings reskins stock 11204 with white dashes. Stock 11204 runs
one lane each way inside EACH half, so one lane per half drives against the painted one-way look.

Measured on the owner's save (hwcars_tracks 100 s, box 604..618 x 128..182): x 608/609 z 135..138 (21742), east half
(rule direction S): 11-14 northbound cars per cell at lane ~80 vs 1-2 southbound. Converted 21700 band beside it
(613/614): every visit in the half's direction, both lanes. Seoul (straight 21700 halves, 120 s): 0 wrong-way road cars.
Owner's lane data = stage/release (VPathAtt/TrBlkAtt md5 identical). Owner log: 27 bands one-way, 23 two-way (172 rows).

## Fix, step 1 (owner: "two-way look now, then convert more avenues")
- sc3netmod: AVP off by default (`SC3NETMOD_AVP=1` brings it back). With AVP off the pass still gives back every twin in
  its box, because a city saved with AVP on restores its twins from the 0x4E56 variant list on load.
  Owner's Big One: load pass `0 cell(s) painted, 326 given back`; (608..609,135..138) read 11204 after load.
- netpack: avenue_markings (11204 white-dash reskin) uninstalled, so a two-way avenue draws the stock yellow centre line.
  Converted pieces keep their own art (avenue_lanes 21700/21701/21726 ship art/11204, art/11203 copies).
  RELEASE STEP: `netpack.py uninstall avenue_markings --tree stage/src` together with this DLL (either alone keeps the lie:
  the old DLL paints twins, the old overlay paints stock 11204 white).
- Seen in game (owner save, zoom 4): x 608/609 two-way stretch draws yellow centre line.
- Open: avjunc's two-way nose pieces (20804/20810/20811, link noses 21775..21778) still draw white dashes on the one cell
  where a two-way avenue meets a junction box. DAVTWO diagonal twins 21830..21835 have the same look-over-two-way-lanes
  problem (white dashes, pre-avdiag two-way lanes); the alternative there is the stock 43/11203 ladder (owner rejected
  "chain of circles" 2026-10-31).

## Step 2 (next): convert more avenues
Refusal kinds on the owner's save: band ends that are not a U-turn pair, corner or avlj join (13 "no 11203 inner bend",
8 "cells beside", 2 "11203/11204 states").
