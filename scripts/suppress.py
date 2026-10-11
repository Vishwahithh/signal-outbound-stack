"""suppress.py - every domain this client must never be prospected at: existing customers, competitors, partners,
anyone already contacted, opt-outs. Sources are listed in the config under "suppression".

    python scripts/suppress.py acme.com example.org     -> prints SUPPRESSED/ok per domain, exits 1 on any hit
    from suppress import load; domains = load(cfg)
"""
import csv, sys
from pathlib import Path

from common import ROOT, config, norm


def load(cfg):
    s, sup = set(), cfg.get("suppression", {})
    for f in sup.get("domain_files", []):
        p = ROOT / f
        if p.exists():
            for line in open(p, encoding="utf-8"):
                line = line.split("#")[0].strip()
                if line:
                    s.add(norm(line))
    for spec in sup.get("csv_files", []):
        p = ROOT / spec["path"]
        if not p.exists():
            continue
        for r in csv.DictReader(open(p, encoding="utf-8-sig")):
            v = r.get(spec.get("column", "domain")) or ""
            s.add(norm(v.split("@")[1]) if "@" in v else norm(v))
    s.discard("")
    return s


if __name__ == "__main__":
    S = load(config())
    hit = False
    for d in [a for a in sys.argv[1:] if not a.startswith("--") and not a.endswith(".json")]:
        bad = norm(d) in S
        hit = hit or bad
        print(norm(d), "SUPPRESSED" if bad else "ok")
    sys.exit(1 if hit else 0)  # non-zero so "check && reveal" chains stop on a suppressed domain
