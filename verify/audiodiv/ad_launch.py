"""Start SC3U.exe from the audiodiv test tree with the instance mods, windowed, and print its pid.

Usage: py -3.12 ad_launch.py <tag> [--city "Europolis 1024"] [--env K=V ...]
Logs land in <inst>/ (the mods write beside the DLL); they are copied to data/<tag>/ by ad_collect.py.
Posted input only, nothing here touches the cursor or focus.
"""
import argparse
import os
import subprocess
import sys

TREE = r"C:\Users\maria\Desktop\Proyectos\Simcity_audiodiv_t"
INST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "re", "harness", "inst_ad")

ap = argparse.ArgumentParser()
ap.add_argument("tag")
ap.add_argument("--city", default="Europolis 1024")
ap.add_argument("--env", action="append", default=[])
a = ap.parse_args()
inst = os.path.abspath(INST)
for f in os.listdir(inst):
    if f.endswith(".log"):
        os.remove(os.path.join(inst, f))
env = dict(os.environ)
env.update({"SC3MODS_DIR": inst, "SC3MODS_MULTI": "1", "SC3RESIZE_WINMEM": "0"})
for kv in a.env:
    k, v = kv.split("=", 1)
    env[k] = v
apps = os.path.join(TREE, "Apps")
city = os.path.join(TREE, "Cities", a.city + ".sc3")
p = subprocess.Popen([os.path.join(apps, "SC3U.exe"), "-intro:off", city], cwd=apps, env=env,
                     creationflags=0x00000008 | 0x00000200)   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
print(p.pid, flush=True)
