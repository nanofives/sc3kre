#!/usr/bin/env python3
r"""ct_run.py - one cartrips arm (verify/cartrips/PRE.md): pt_run.py's launcher, key driver and schedule, with the
cartrips probe (ct_probe.py) in place of the pausetrips one.

  py -3.12 ct_run.py --inst <instance folder> --city <src.sc3> --arm NAME --schedule "s3:60,P:60,..." [--safe]

Same schedule tokens as pt_run.py (sN, P, PW, H, PH). Output <inst>\<arm>.jsonl, one line per second.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pt_run  # noqa: E402
from ct_probe import CSRC, JS  # noqa: E402

# CT_GROUPS (env): comma list of hook groups (trip, ag, acc, spawn, path, view, rem) or "all"
pt_run.JS = "var CSRC = " + json.dumps(CSRC) + ";\n" + JS.replace("__CT_GROUPS__", os.environ.get("CT_GROUPS", "all"))

if __name__ == "__main__":
    sys.exit(pt_run.main())
