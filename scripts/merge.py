"""merge.py - join every table of a run into one lead master.

Inputs (runs/<run>/): source/companies.csv (every sourced company), source/people.csv (people found at approved
companies), source/emails.jsonl (emails found), qualify/out_*.jsonl (website grade; qualify/rc_out_*.jsonl re-grades
override), research/out_*.jsonl and mv_results*.csv when they exist. Missing values stay blank. Nothing is guessed.

One row per person once people are found (so a company with three people has three rows: multithreading); a company
with no people yet is one row with the person columns blank, which is what grading needs.

Domain check: databases sometimes hold the wrong website for a company. If the found email's domain differs from the
company domain, the row is flagged domain_mismatch and its grade is not trusted until the domain is re-resolved.

    python scripts/merge.py   -> runs/<run>/leads_master.csv + runs/<run>/approved.csv (A/B domains)
"""
import csv, json
from collections import Counter, defaultdict

from common import config, jl, run_dir


def root(d):
    parts = (d or "").lower().split(".")
    return ".".join(parts[-3:]) if len(parts) > 2 and parts[-2] in ("co", "com", "org", "ac") else ".".join(parts[-2:])


def read_csv(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig"))) if p.exists() else []


def main():
    cfg = config()
    run, src = run_dir(cfg), run_dir(cfg, "source")
    companies = {r["domain"]: r for r in read_csv(src / "companies.csv")}
    people = defaultdict(list)
    for p in read_csv(src / "people.csv"):
        people[p["domain"]].append(p)
    emails = {r["person_id"]: r for r in jl(src / "emails.jsonl")}
    qual = {r["domain"]: r for r in jl(run / "qualify" / "out_*.jsonl")}
    qual.update({r["domain"]: r for r in jl(run / "qualify" / "rc_out_*.jsonl")})
    research = {r["domain"]: r for r in jl(run / "research" / "out_*.jsonl")}
    mv = {}
    for f in run.glob("mv_results*.csv"):
        for r in csv.DictReader(open(f, encoding="utf-8-sig")):
            mv[(r.get("email") or "").lower()] = r.get("result")
    rows = []
    for d, c in companies.items():
        q, rs = qual.get(d) or {}, research.get(d) or {}
        base = {
            "domain": d, "company": c["company"], "country": c["country"], "headcount": c["headcount"],
            "industry": c.get("industry", ""), "linkedin_company": c.get("linkedin_company", ""),
            "revenue_band": "", "last_funding_date": "", "last_funding_stage": "",
            "tier": c.get("tier", ""), "signal_hint": c.get("signal_hint", ""),
            "grade": q.get("qualify", ""), "sells": q.get("sells", ""), "what_they_sell": q.get("what_they_sell", ""),
            "customers": q.get("customers", ""), "pricing_style": q.get("pricing_style", ""),
            "status": q.get("status", ""), "grade_reason": q.get("reason", ""),
            "best_signal": rs.get("best_signal", ""), "signals": json.dumps(rs.get("signals", []), ensure_ascii=False) if rs else "",
            "second_name": "", "second_title": "", "second_email": "", "second_mv": "",
        }
        for p in sorted(people.get(d) or [{}], key=lambda p: int(p.get("title_rank") or 99)):
            e = emails.get(p.get("person_id")) or {}
            email = e.get("email") or ""
            edom = email.split("@")[1].lower() if "@" in email else ""
            rows.append({**base, "person_id": p.get("person_id", ""), "first_name": p.get("first_name", ""),
                         "last_name": p.get("last_name", ""), "title": p.get("title", ""), "linkedin": p.get("linkedin", ""),
                         "email": email, "email_provider": e.get("provider") or "",
                         "email_domain": edom, "domain_mismatch": bool(edom) and root(edom) != root(d),
                         "mv": mv.get(email.lower(), "") if email else ""})
    if not rows:
        print("nothing to merge: run source_companies.py select first"); return
    out = run / "leads_master.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    ab = {r["domain"]: r for r in rows if r["grade"] in ("A", "B")}
    with open(run / "approved.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["domain", "company", "linkedin_company", "grade"], extrasaction="ignore")
        w.writeheader(); w.writerows(ab.values())
    print(out, len(rows), "rows,", len(companies), "companies |", len(ab), "A/B ->", run / "approved.csv")
    print("grades", dict(Counter(r["grade"] or "ungraded" for r in {r["domain"]: r for r in rows}.values())))
    print("people", sum(1 for r in rows if r["person_id"]), "| with email", sum(1 for r in rows if r["email"]),
          "| domain_mismatch", sum(r["domain_mismatch"] for r in rows))


if __name__ == "__main__":
    main()
