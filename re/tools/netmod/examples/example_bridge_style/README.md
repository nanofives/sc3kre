# example_bridge_style

Test fixture for netbridge: a new road bridge style. The six pieces of the stock plain bridge (87, 88, 11265, 11271
and the ramps 18050, 18051) are cloned as variants 20087, 20088, 21265, 21271, 28050, 28051 with the `red` recolour
(no art stored here), and two records are inserted into `ROAD_GRND_Bridges.txt` before stock record 6 (the plain
bridge, minLen 1). The road builder takes the first record whose axis matches and whose minLen is at most the
crossing length, so crossings of 1..5 cells use the red style and longer ones keep the stock styles (Harbour from 6,
layered from 10, suspension from 18). `netpack.py validate` prints that table. Results: `verify/netbridge/RESULTS.md`.
