"""catalog.py -- join every netmod source into one record per network piece.

Schema: re/analysis/NETMOD_CATALOG.md. `SCHEMA_VERSION` bumps on any field rename/removal.
"""
import datetime
import json
import os

from . import exemplars, names, paths, pe_tables, rules, sprites, trblkatt

SCHEMA_VERSION = 1


class Catalog:
    def __init__(self, game=None, with_dims=True):
        self.game = game or paths.Game()
        g = self.game
        self.rules = rules.Rules(g)
        self.occ = names.occupant_keys(g)
        self.ex = exemplars.load(g)
        self.agent_names, self.agent_parent, self.budget = exemplars.agent_types(g)
        self.lnames = exemplars.localized(g)
        self.cs = sprites.csattrib(g)
        self.cont = sprites.Containers(g)
        self.pe = pe_tables.Simntwrk(g)
        self.hard = pe_tables.hardcoded_refs(self.pe)
        self.trb = trblkatt.index(g)
        self.with_dims = with_dims
        self.ids = self._ids()

    def _ids(self):
        """Every id in a network Set file or DIAG_Set.txt (420 on the stock install)."""
        return self.rules.all_ids()

    # --------------------------------------------------------------------- piece

    def agent_chain(self, t):
        chain, seen = [], set()
        while t is not None and t not in seen:
            seen.add(t)
            nm = self.agent_names.get(t)
            chain.append({"type": t, "name": nm[0] if nm else None,
                          "citysim_line": nm[1] if nm else None})
            t = self.agent_parent.get(t)
        return chain

    def piece(self, pid):
        R = self.rules
        sets_of = R.sets_of(pid)
        kind, why = pe_tables.classify(pid, [s for s in sets_of if s != "DIAG"])
        fac = pe_tables.FACTORY.get(kind)
        rec = {
            "id": pid, "hex": "0x%04X" % pid,
            "sets": sets_of,
            "set_lines": {n: R.set_lines[n][pid] for n in sets_of},
            "save_instance": sorted({rules.SAVE_INSTANCE[n] for n in sets_of if n in
                                     rules.SAVE_INSTANCE}),
            "class_kind": kind, "class_kind_why": why,
            "class_vtables": ({"size": fac[0], "vt1": "0x%08X" % fac[1],
                               "vt2_occupant": "0x%08X" % fac[2],
                               "query_object_class": "SIMNTWRK.DLL+0x%X" % (fac[2] - 0x10000000)}
                              if fac else None),
            "exemplar_key": ["0x%08X" % exemplars.EX_TYPE, "0x%08X" % exemplars.EX_GROUP,
                             "0x%08X" % pid],
            "trblkatt_keys": ["0x%08X" % (pid * 0x100 + s) for s in range(4)],
        }
        o = self.occ.get(pid)
        rec["occupant_ini"] = ({"name": o["name"], "line": o["line"], "text": o["text"]}
                               if o else None)
        ex = self.ex.get(pid)
        if ex:
            p = ex["props"]
            at = p.get(0x65)
            sk = p.get(0x67)
            lk = p.get(0x6D)
            rec["exemplar"] = {
                "file": ex["file"], "group": "0x%08X" % ex["group"], "size": ex["size"],
                "name": p.get(0x64), "agent_type": at,
                "agent_chain": self.agent_chain(at) if at is not None else [],
                "footprint": list(p[0x66]) if isinstance(p.get(0x66), tuple) else p.get(0x66),
                "sprite_key": ["0x%08X" % v for v in sk] if sk else None,
                "lname_key": ["0x%08X" % v for v in lk] if lk else None,
                "raw": {"0x%X" % k: _jsonable(v) for k, v in sorted(p.items())
                        if k not in exemplars.PROP_NAMES},
            }
            if lk:
                rec["names_localized"] = {lang: m.get((lk[1], lk[2]))
                                          for lang, m in self.lnames.items()}
            b = self.budget.get(at) if at is not None else None
            rec["budget"] = ({"value": b[0], "comment": b[1], "line": b[2], "section": b[3]}
                             if b else None)
        else:
            rec["exemplar"] = None
        rec["art"] = self.art(pid, ex)
        rec["rules"] = [r.as_dict() for r in R.refs_of(pid)]
        rec["rule_summary"] = _rule_summary(R.refs_of(pid))
        rec["hardcoded"] = self.hard.get(pid, [])
        rec["trblkatt"] = self.trb.get(pid)
        return rec

    def art(self, pid, ex):
        sk = ex["props"].get(0x67) if ex else None
        key = (sk[0], sk[2]) if sk else (0x6300, pid)
        t = self.cs.get(key)
        if not t:
            return {"csattrib": None, "via": "exemplar 0x67" if sk else "id (no exemplar)",
                    "frames": []}
        rows = sprites.frame_rows(t, self.cont, self.with_dims)
        objs = sorted({(r["container"], r["group"], r["instance"] >> 16) for r in rows},
                      key=lambda x: (x[0] or "", x[1], x[2]))
        return {"csattrib": {"file": t["file"], "type": "0x%04X" % key[0],
                             "instance": key[1], "hdr": t["hdr"]},
                "via": "exemplar 0x67" if sk else "id (no exemplar)",
                "shared_from": key[1] if key[1] != pid else None,
                "objects": [{"container": c, "group": "0x%08X" % g, "object": "0x%04X" % o}
                            for c, g, o in objs],
                "frames": rows}

    # ------------------------------------------------------------------ outputs

    def build(self):
        pieces = [self.piece(i) for i in self.ids]
        return {
            "schema": "netmod.catalog", "schema_version": SCHEMA_VERSION,
            "generated": datetime.datetime.now().isoformat(timespec="seconds"),
            "game_root": self.game.root,
            "simntwrk_sha256": self.pe.sha256,
            "simntwrk_is_stock": self.pe.sha256 == pe_tables.SHA256_STOCK,
            "networks": {n: {"name": rules.NET_LONG[n],
                             "nettype": next((k for k, v in rules.NETTYPE.items() if v == n),
                                             None),
                             "set_size": len(self.rules.sets.get(n, [])),
                             "save_instance": rules.SAVE_INSTANCE.get(n)}
                         for n in rules.NETS + ["DIAG"]},
            "bridges": {n: b for n, b in self.rules.bridges.items()},
            "collapse_groups": self.rules.collapse_groups,
            "tables": pe_tables.dump_tables(self.pe),
            "pieces": pieces,
        }


def _jsonable(v):
    if isinstance(v, tuple):
        return [_jsonable(x) for x in v]
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    return v


def _rule_summary(refs):
    out = {}
    for r in refs:
        k = "%s %s" % (r.stage, r.role if not r.role.startswith(("bridge", "collapse"))
                       else r.role.split()[0])
        out[k] = out.get(k, 0) + 1
    return out


def write_json(cat, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(cat, fh, indent=1, ensure_ascii=False)


CSV_COLS = ["id", "hex", "sets", "class_kind", "occupant_name", "occupant_line", "exemplar_name",
            "name_es", "name_en", "agent_type", "agent_type_name", "footprint", "csattrib",
            "shared_art_from", "frames", "containers", "first_slot", "n_rule_refs",
            "n_result_refs", "n_condition_refs", "protected", "convert", "bridge", "collapse",
            "hardcoded", "trblkatt_states"]


def write_csv(cat, path):
    import csv
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(CSV_COLS)
        for p in cat["pieces"]:
            ex = p.get("exemplar") or {}
            chain = ex.get("agent_chain") or [{}]
            art = p["art"]
            rs = p["rules"]
            ln = p.get("names_localized") or {}
            w.writerow([
                p["id"], p["hex"], " ".join(p["sets"]), p["class_kind"],
                (p["occupant_ini"] or {}).get("name"), (p["occupant_ini"] or {}).get("line"),
                ex.get("name"), ln.get("ENGLISH"), ln.get("English-UK"),
                ex.get("agent_type"), chain[0].get("name"),
                "x".join(str(v) for v in ex.get("footprint") or []),
                art["csattrib"]["file"] if art["csattrib"] else "",
                art.get("shared_from") or "",
                len(art["frames"]),
                " ".join(sorted({f["container"] for f in art["frames"] if f["container"]})),
                min((f["slot"] for f in art["frames"] if f["slot"] is not None), default=""),
                len(rs),
                sum(1 for r in rs if r["role"] == "RESULT"),
                sum(1 for r in rs if r["role"] == "condition"),
                sum(1 for r in rs if r["role"] == "protected"),
                sum(1 for r in rs if r["role"].startswith("convert")),
                sum(1 for r in rs if r["role"].startswith("bridge")),
                sum(1 for r in rs if r["role"].startswith("collapse")),
                len(p["hardcoded"]),
                " ".join(str(s) for s in (p["trblkatt"] or {}).get("states", [])),
            ])
