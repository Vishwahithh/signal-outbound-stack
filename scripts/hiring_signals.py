"""hiring_signals.py - stage 3 helper: open LinkedIn roles per graded company, as dated evidence for the signal agents.

Uses the harvestapi LinkedIn job search on Apify via treg ($0.001 a job + $0.001 per title searched). Searches the
titles in config "signals_feed.hiring_titles" at each company in the input, newest first, posted within
"signals_feed.posted" (24h | week | month). This is a hint, not a verdict: the signal-research agents open each
posting, check it is still live and dated inside the window, and a person reviews it before copy.

    python scripts/hiring_signals.py --input runs/<run>/approved.csv --max-usd 0.5
Writes runs/<run>/research/hiring.jsonl (one line per company: the postings found).
"""
import csv, json, sys

from common import config, norm, run_dir
from providers import Budget, BudgetExceeded, treg

CFG = config()
OUT = run_dir(CFG, "research") / "hiring.jsonl"


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main():
    sf = CFG.get("signals_feed") or {}
    titles, posted, per = sf.get("hiring_titles") or [], sf.get("posted", "month"), int(sf.get("max_jobs_per_company", 5))
    if not titles:
        sys.exit("config signals_feed.hiring_titles is empty")
    b = Budget(CFG, max_usd=float(arg("--max-usd", 0.5)))
    rows = list(csv.DictReader(open(arg("--input"), encoding="utf-8-sig")))
    done = {json.loads(l)["domain"] for l in open(OUT, encoding="utf-8")} if OUT.exists() else set()
    with open(OUT, "a", encoding="utf-8") as f:
        for r in rows:
            d = norm(r.get("domain"))
            name = r.get("company_clean") or r.get("company")
            if not d or not name or d in done:
                continue
            cap = round(0.001 * (per + len(titles)) + 0.002, 3)       # Apify enforces this per call
            try:
                st, jobs = treg(b, "apify.linkedin.search.jobs", query={"maxItems": per, "maxTotalChargeUsd": cap, "timeout": 90},
                                body={"jobTitles": titles, "company": [r.get("linkedin_company") or name],
                                      "postedLimit": posted, "maxItems": per})
            except BudgetExceeded as e:
                print(" ", e); break
            jobs = jobs if isinstance(jobs, list) else []
            keep = [{"title": j.get("title"), "posted": (j.get("postedDate") or "")[:10], "url": j.get("linkedinUrl"),
                     "company": (j.get("company") or {}).get("name") if isinstance(j.get("company"), dict) else None}
                    for j in jobs]
            f.write(json.dumps({"domain": d, "company": name, "http": st, "jobs": keep}, ensure_ascii=False) + "\n"); f.flush()
            print(f"  {name}: {len(keep)} postings")
    print(f"spent ${b.spent:.4f}")


if __name__ == "__main__":
    main()
