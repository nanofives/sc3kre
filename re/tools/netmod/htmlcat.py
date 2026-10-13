"""html.py -- a static, browsable HTML catalog with thumbnails. Output is GAME ART: it goes to a
gitignored folder (default re/netcat_out/html) and must never be committed or published.

index.html: one row per piece (filterable by network / text), thumbnail = zoom 3 rotation 0 frame
(the largest zoom with art for every piece). p/<id>.html: the `netcat show` report, all frames.
"""
import contextlib
import html as _h
import io
import json
import os

from . import pe_tables

THUMB_FRAME_ZOOM = 3


def _thumb_frame(art):
    if not art["csattrib"]:
        return None
    rc = art["csattrib"]["hdr"]["rot_count"] or 4
    want = THUMB_FRAME_ZOOM * rc
    for f in art["frames"]:
        if f["frame"] == want and f["slot"] is not None and f.get("format") == 1:
            return f
    for f in art["frames"]:
        if f["slot"] is not None and f.get("format") == 1:
            return f
    return None


def _png(C, f, path):
    if os.path.exists(path):
        return True
    try:
        C.cont.export_png(f["container"], f["slot"], path)
        return True
    except Exception:  # alpha-mask records (format 0) are refused by sprite_patch
        return False


CSS = """
:root{--bg:#fafaf7;--fg:#1d1d1b;--mut:#6b6b66;--line:#ddd9cf;--chip:#ece8dd;--acc:#2f5d8a}
@media (prefers-color-scheme:dark){:root{--bg:#1a1a18;--fg:#ecebe6;--mut:#a3a29b;--line:#38372f;
--chip:#2b2a25;--acc:#8db7e0}}
body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif}
h1{font-size:20px;margin:0 0 4px} .mut{color:var(--mut)} a{color:var(--acc)}
input,select{font:inherit;padding:4px 6px;background:var(--bg);color:var(--fg);
border:1px solid var(--line);border-radius:4px}
table{border-collapse:collapse;width:100%} td,th{border-bottom:1px solid var(--line);
padding:4px 6px;text-align:left;vertical-align:middle} th{position:sticky;top:0;background:var(--bg)}
img.t{image-rendering:pixelated;max-height:72px;background:repeating-conic-gradient(#0000 0 25%,
#8882 0 50%) 0 0/12px 12px}
.chip{display:inline-block;padding:0 6px;border-radius:9px;background:var(--chip);margin-right:3px;
font-size:12px} pre{white-space:pre-wrap;font:12px/1.4 ui-monospace,Consolas,monospace}
.frames{display:flex;flex-wrap:wrap;gap:8px} .frames figure{margin:0;text-align:center;font-size:11px}
.frames img{image-rendering:pixelated;background:repeating-conic-gradient(#0000 0 25%,#8882 0 50%)
0 0/12px 12px}
.wrap{overflow-x:auto}
"""


def build(C, out, all_frames=False):
    from .netcat import frame_label, show
    os.makedirs(os.path.join(out, "img"), exist_ok=True)
    os.makedirs(os.path.join(out, "p"), exist_ok=True)
    rows = []
    for pid in C.ids:
        p = C.piece(pid)
        ex = p["exemplar"] or {}
        ln = p.get("names_localized") or {}
        name = ex.get("name") or (p["occupant_ini"] or {}).get("name") or ""
        tf = _thumb_frame(p["art"])
        thumb = None
        if tf:
            fn = "img/%05d_t.png" % pid
            if _png(C, tf, os.path.join(out, fn)):
                thumb = fn
        res = sum(1 for r in p["rules"] if r["role"] == "RESULT")
        rows.append({"id": pid, "name": name, "es": ln.get("ENGLISH") or "",
                     "sets": p["sets"], "kind": p["class_kind"], "thumb": thumb,
                     "refs": len(p["rules"]), "results": res,
                     "agent": (ex.get("agent_chain") or [{}])[0].get("name") or "",
                     "hard": len(p["hardcoded"]),
                     "frames": len(p["art"]["frames"])})
        # detail page
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            show(C, pid, frames=True, rules_limit=None)
        figs = []
        art = p["art"]
        if art["csattrib"]:
            h = art["csattrib"]["hdr"]
            for f in art["frames"]:
                if f["slot"] is None or f.get("format") != 1:
                    continue
                z, r, L = frame_label(f["frame"], h)
                if not all_frames and z != THUMB_FRAME_ZOOM:
                    continue
                fn = "img/%05d_f%02d.png" % (pid, f["frame"])
                if _png(C, f, os.path.join(out, fn)):
                    figs.append('<figure><img src="../%s"><figcaption>f%d z%d r%d%s<br>%dx%d'
                                '</figcaption></figure>' % (fn, f["frame"], z, r,
                                                             " L%d" % L if L else "",
                                                             f["w"], f["h"]))
        page = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,"
                "initial-scale=1'><title>piece %d</title><style>%s</style>"
                "<p><a href='../index.html'>&larr; all pieces</a></p><h1>%d %s</h1>"
                "<p class=mut>%s</p><div class=frames>%s</div><div class=wrap><pre>%s</pre></div>"
                % (pid, CSS, pid, _h.escape(name), _h.escape(ln.get("ENGLISH") or ""),
                   "".join(figs) or "<span class=mut>no art</span>", _h.escape(buf.getvalue())))
        with open(os.path.join(out, "p", "%d.html" % pid), "w", encoding="utf-8") as fh:
            fh.write(page)
    nets = ["ROAD", "RAIL", "POWR", "HWAY", "PIPE", "SUBW", "DIAG"]
    index = """<!doctype html><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Network Pieces</title>
<style>%s</style><h1>SC3U network pieces</h1>
<p class=mut>%d pieces from TilingRules *_Set.txt. Generated by re/tools/netmod/netcat.py html.
Game art: keep this folder private.</p>
<p><input id=q placeholder="filter: id, name, agent type" size=30>
<select id=n><option value="">all networks</option>%s</select>
<label><input type=checkbox id=r> produced by a rule</label></p>
<div class=wrap><table><thead><tr><th>art</th><th>id</th><th>name</th><th>networks</th>
<th>kind</th><th>agent type</th><th>rule refs</th><th>results</th><th>hardcoded</th><th>frames</th>
</tr></thead><tbody id=b></tbody></table></div>
<script>
const D=%s;
const b=document.getElementById('b'),q=document.getElementById('q'),n=document.getElementById('n'),
r=document.getElementById('r');
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function draw(){const t=q.value.toLowerCase();b.innerHTML=D.filter(d=>
 (!n.value||d.sets.includes(n.value))&&(!r.checked||d.results>0)&&
 (!t||(d.id+' '+d.name+' '+d.es+' '+d.agent).toLowerCase().includes(t))).map(d=>
 `<tr><td>${d.thumb?`<img class=t src="${d.thumb}">`:''}</td><td><a href="p/${d.id}.html">${d.id}</a></td>
 <td>${esc(d.name)}<br><span class=mut>${esc(d.es)}</span></td>
 <td>${d.sets.map(s=>`<span class=chip>${s}</span>`).join('')}</td><td>${d.kind}</td>
 <td>${esc(d.agent)}</td><td>${d.refs}</td><td>${d.results}</td><td>${d.hard}</td><td>${d.frames}</td></tr>`).join('')}
[q,n,r].forEach(e=>e.addEventListener('input',draw));draw();
</script>""" % (CSS, len(rows), "".join("<option>%s</option>" % x for x in nets),
                json.dumps(rows))
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(index)
    print("wrote %s (%d pieces, %d with a thumbnail)" % (os.path.join(out, "index.html"),
                                                          len(rows),
                                                          sum(1 for x in rows if x["thumb"])))
