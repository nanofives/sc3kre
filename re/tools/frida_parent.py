#!/usr/bin/env python3
"""frida_parent.py - read the HUD windows' parent chain DIRECTLY.

`ROOTCAUSE_RESULTS.md` concluded the relocated HUD hangs off a container still sized
`[0 0 800 600]`, from two agreeing indirect observations. This reads the link itself.

parent = `this+0x3c`, byte-proven: the base class `vt+0x2c` is `8b 41 3c c3` =
`mov eax,[ecx+0x3c]; ret` `[CONFIRMED @ GZWIND 0x1001e210]`. Read RAW, never dispatched.
"""
import argparse, json, sys, time
import frida

JS = r"""
'use strict';
function modBase(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)
  if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
function ri(p,o){return p.add(o).readS32();}
function rp(p,o){return p.add(o).readPointer();}
function rect(p){try{return [ri(p,0x14),ri(p,0x18),ri(p,0x1c),ri(p,0x20)];}catch(e){return null;}}
function flags(p){try{return '0x'+p.add(0xa0).readU32().toString(16);}catch(e){return null;}}

function walk(w,d,out,seen){
  if(d>10||out.length>4000)return;
  var head,n;
  try{head=rp(w,0x34);}catch(e){return;}
  if(head===null||head.isNull())return;
  try{n=rp(head,0);}catch(e){return;}
  var g=0;
  while(!n.isNull()&&!n.equals(head)&&g<500){
    g++;
    var cw;try{cw=rp(n,8);}catch(e){break;}
    if(!cw.isNull()&&!seen[cw.toString()]){
      seen[cw.toString()]=1;
      out.push({p:cw.toString(),r:rect(cw),f:flags(cw),depth:d});
      walk(cw,d+1,out,seen);
    }
    try{n=rp(n,0);}catch(e){break;}
  }
}

rpc.exports={
  dump:function(){
    var gz=modBase('GZGraphicD.dll');
    var win=rp(gz.add(0x6cdb8),0), sink=rp(win,0x30), root=rp(sink,0x38);
    var out=[],seen={};
    walk(root,1,out,seen);
    /* parent chain for every window whose rect extends beyond the old 800x600 box */
    var chains=[];
    out.forEach(function(e){
      var r=e.r;
      if(!r||(r[2]<=800&&r[3]<=600))return;
      var chain=[],cur=ptr(e.p),g=0;
      while(g<12){
        g++;
        var par;
        try{par=rp(cur,0x3c);}catch(e2){chain.push({err:'unreadable'});break;}
        if(par.isNull()){chain.push({p:'0x0 (root reached)'});break;}
        chain.push({p:par.toString(),r:rect(par),f:flags(par)});
        cur=par;
      }
      chains.push({win:e.p,rect:r,flags:e.f,depth:e.depth,parents:chain});
    });
    return {root:root.toString(),rootRect:rect(root),total:out.length,chains:chains};
  }
};
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="verify/resize_flaggate/parent.json")
    ap.add_argument("--wait", type=float, default=60.0)
    a = ap.parse_args()
    dev = frida.get_local_device()
    end = time.time() + a.wait
    pid = None
    while time.time() < end and not pid:
        for p in dev.enumerate_processes():
            if p.name.lower() == "sc3u.exe":
                pid = p.pid
        if not pid:
            time.sleep(0.5)
    if not pid:
        print("[-] not found", file=sys.stderr); return 1
    s = dev.attach(pid); sc = s.create_script(JS); sc.load()
    d = sc.exports_sync.dump()
    json.dump(d, open(a.out, "w", encoding="utf-8"), indent=2)
    print(f"[+] root {d['root']} {d['rootRect']}  windows {d['total']}  "
          f"beyond-800x600 {len(d['chains'])}")
    for c in d["chains"]:
        print(f"  win {c['win']} rect={c['rect']} depth={c['depth']}")
        for i, p in enumerate(c["parents"]):
            print(f"      parent[{i}] {p.get('p')} rect={p.get('r')} flags={p.get('f')}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
