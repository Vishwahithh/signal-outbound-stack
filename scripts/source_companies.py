"""source_companies.py - stage 1 (TAM): every company that matches the archetype, from Icypeas company search via treg.
Companies only, no people and no emails: people are found after grading, for A/B companies only.

  count    free size check of the query in config "source.icypeas_query" (one count per geography)
  search   pull rows page by page (0.02 Icypeas credit each, about $0.0004 a company) into
           runs/<run>/source/companies_raw.jsonl; resumes, stops at --max-usd
  select   dedupe by domain, mark suppressed, write runs/<run>/source/companies.csv (input to site_fetch + grading)

    python scripts/source_companies.py count
    python scripts/source_companies.py search --max-usd 1 [--page-size 100]
    python scripts/source_companies.py select

The query uses Icypeas's own filters (industry, location, headcount, revenue, type, keyword, headcountGrowth): read
its filter reference before editing it, and prefer narrow industry labels to broad ones.
"""
import csv, json, sys

from common import config, norm, run_dir
from providers import Budget, BudgetExceeded, treg
from suppress import load as load_suppression

CFG = config()
OUT = run_dir(CFG, "source")
RAW, STATE = OUT / "companies_raw.jsonl", OUT / "state.json"


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def queries():
    q = CFG["source"]["icypeas_query"]
    geos = CFG["archetype"].get("geo") or [None]
    for g in geos:
        qq = json.loads(json.dumps(q))
        if g:
            qq["location"] = {"include": [g]}
        yield (g or "all"), qq


def count():
    b = Budget(CFG, max_usd=0.01)
    for g, q in queries():
        st, r = treg(b, "icypeas.companies.search.count", body={"query": q})
        print(f"  {g}: {r.get('total') if isinstance(r, dict) else r} (http {st})")


def search():
    b = Budget(CFG, max_usd=float(arg("--max-usd", 1)))
    size = int(arg("--page-size", 100))
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    with open(RAW, "a", encoding="utf-8") as f:
        for g, q in queries():
            s = state.get(g, {})
            if s.get("done"):
                continue
            while True:
                pag = {"size": size, **({"token": s["token"]} if s.get("token") else {})}
                try:
                    st, r = treg(b, "icypeas.companies.search", body={"query": q, "pagination": pag})
                except BudgetExceeded as e:
                    print(" ", e); STATE.write_text(json.dumps(state)); return
                rows = (r or {}).get("leads") or [] if isinstance(r, dict) else []
                for x in rows:
                    f.write(json.dumps({"geo": g, **x}, ensure_ascii=False) + "\n")
                f.flush()
                tok = (r.get("token") or (r.get("pagination") or {}).get("token")) if isinstance(r, dict) else None
                s.update(token=tok, pulled=s.get("pulled", 0) + len(rows))
                state[g] = s
                STATE.write_text(json.dumps(state))
                print(f"  {g}: +{len(rows)} (total {s['pulled']} of {r.get('total') if isinstance(r, dict) else '?'}) | spent ${b.spent:.4f}")
                if not rows or not tok or st != 200:
                    s["done"] = True; break
    print(f"spent ${b.spent:.4f}")


def select():
    supp = load_suppression(CFG)
    best = {}
    for line in open(RAW, encoding="utf-8"):
        x = json.loads(line)
        d = norm(x.get("website") or "")
        if not d or d.startswith("buy.") or d in ("linkedin.com", "stripe.com"):
            continue                                   # payment links and profile pages are not company websites
        best.setdefault(d, x)
    cols = ["domain", "company", "country", "headcount", "industry", "founded", "linkedin_company", "tier", "signal_hint",
            "suppressed", "description"]
    with open(OUT / "companies.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for d, x in best.items():
            if d in supp:
                continue
            w.writerow({"domain": d, "company": x.get("name"), "country": x.get("geo"), "headcount": x.get("numberOfEmployees"),
                        "industry": x.get("industry"), "founded": x.get("foundedYear"), "linkedin_company": x.get("url"),
                        "tier": "base", "signal_hint": "", "suppressed": False,
                        "description": (x.get("description") or "").replace("\n", " ")[:1200]})
    n_s = sum(1 for d in best if d in supp)
    print(OUT / "companies.csv", len(best) - n_s, "companies kept |", n_s, "suppressed and left out")


if __name__ == "__main__":
    {"count": count, "search": search, "select": select}[sys.argv[1]]()
