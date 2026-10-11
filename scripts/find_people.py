"""find_people.py - stage 5: the people to contact at each APPROVED company (A/B after grading), free.

QuickEnrich contact discovery via treg returns full names, titles and LinkedIn URLs at no cost (it never returns
emails). For each approved domain it asks for the titles in config "contacts.title_include", drops
"contacts.title_exclude", ranks by "contacts.personas" order and keeps "contacts.per_company" people
(1 = single thread, 3-5 = multithreading on small markets).

    python scripts/find_people.py --approved runs/<run>/approved.csv      # column: domain
Writes runs/<run>/source/people.csv (one row per person, person_id = domain:first-last). Resumes per domain.

Next: clean_people.py names + verify (still at the company? same role?), then find_emails.py on the survivors.
"""
import csv, json, re, sys

from common import config, norm, run_dir
from providers import Budget, treg

CFG = config()
OUT = run_dir(CFG, "source")
RAW = OUT / "people_raw.jsonl"


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def rank(title):
    t = (title or "").lower()
    for i, p in enumerate(CFG["contacts"].get("personas") or CFG["contacts"]["title_include"]):
        if p.lower() in t:
            return i
    return 99


def main():
    c = CFG["contacts"]
    doms = [norm(r["domain"]) for r in csv.DictReader(open(arg("--approved"), encoding="utf-8-sig")) if r.get("domain")]
    done = {json.loads(l)["domain"] for l in open(RAW, encoding="utf-8")} if RAW.exists() else set()
    b = Budget(CFG, max_usd=0.05)                       # discovery is free; this only guards against a price change
    excl = re.compile("|".join(map(re.escape, c.get("title_exclude", []))) or "$^", re.I)
    with open(RAW, "a", encoding="utf-8") as f:
        for d in doms:
            if d in done:
                continue
            st, r = treg(b, "quickenrich.people.search",
                         body={"company_url": {"include": [d]}, "title": {"include": c["title_include"]}, "per_page": 50})
            ppl = (r.get("data") or []) if isinstance(r, dict) else []
            f.write(json.dumps({"domain": d, "http": st, "people": ppl}, ensure_ascii=False) + "\n"); f.flush()
            print(f"  {d}: {len(ppl)} found (http {st})")
    rows = []
    for line in open(RAW, encoding="utf-8"):
        x = json.loads(line)
        keep = [p for p in x["people"] if not excl.search(p.get("title") or "") and norm(p.get("company_url") or x["domain"]) == x["domain"]]
        keep.sort(key=lambda p: rank(p.get("title")))
        for p in keep[: int(c.get("per_company", 1))]:
            fn, ln = (p.get("first_name") or "").strip(), (p.get("last_name") or "").strip()
            rows.append({"person_id": f"{x['domain']}:{fn}-{ln}".lower().replace(" ", "-"), "domain": x["domain"],
                         "company": p.get("company_name"), "first_name": fn, "last_name": ln, "title": p.get("title"),
                         "title_rank": rank(p.get("title")), "linkedin": p.get("employee_linkedin"),
                         "country": p.get("country_code"), "has_email": p.get("has_email")})
    cols = ["person_id", "domain", "company", "first_name", "last_name", "title", "title_rank", "linkedin", "country", "has_email"]
    with open(OUT / "people.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    print(OUT / "people.csv", len(rows), "people at", len({r["domain"] for r in rows}), "companies | spent", f"${b.spent:.4f}")


if __name__ == "__main__":
    main()
