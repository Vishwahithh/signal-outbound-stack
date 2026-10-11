"""find_emails.py - stage 7: verified work emails for approved people, cheapest provider first, pay only for finds.

Waterfall per person (stops at the first email):
  1 kitt        Kitt AI via treg          $0.005 per verified find, miss free     (name + domain)
  2 quickenrich QuickEnrich via treg      ~$0.005 per find, miss free             (LinkedIn URL, else name + domain)
  3 icypeas     Icypeas via Deepline      $0.014 per find, miss free              (name + domain)
Edit the order in config "email_waterfall". Every find still goes through MillionVerifier; only "ok" is sent.
Never build an address from a name pattern: no find means no email.

    python scripts/find_emails.py --input runs/<run>/source/people.csv --max-usd 2 [--only kitt,quickenrich]
Appends runs/<run>/source/emails.jsonl (person_id, email, provider, tried) and resumes from it.
"""
import csv, json, sys

from common import config, run_dir
from providers import Budget, BudgetExceeded, deepline, find_email, treg

CFG = config()
OUT = run_dir(CFG, "source")
EMAILS = OUT / "emails.jsonl"


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def kitt(b, p):
    st, r = treg(b, "trykitt.people.email.find",
                 body={"fullName": f"{p['first_name']} {p['last_name']}", "domain": p["domain"], "realtime": True,
                       **({"linkedinStandardProfileURL": p["linkedin"]} if p.get("linkedin") else {})})
    if isinstance(r, dict) and r.get("validity") == "valid" and "@" in (r.get("email") or ""):
        return r["email"].lower()
    return None


def quickenrich(b, p):
    q = {"linkedin_url": p["linkedin"]} if p.get("linkedin") else {}
    q.update(company_url=p["domain"], first_name=p["first_name"], last_name=p["last_name"])
    st, r = treg(b, "quickenrich.people.email.find", query=q)
    return find_email((r or {}).get("data")) if isinstance(r, dict) else None


def icypeas(b, p):
    r = deepline(b, "icypeas_email_search", {"firstname": p["first_name"], "lastname": p["last_name"],
                                             "domainOrCompany": p["domain"]}, est_usd=0.014)
    return find_email(r)


STEPS = {"kitt": kitt, "quickenrich": quickenrich, "icypeas": icypeas}


def main():
    order = [s for s in (arg("--only") or ",".join(CFG.get("email_waterfall") or ["kitt", "quickenrich", "icypeas"])).split(",") if s]
    b = Budget(CFG, max_usd=float(arg("--max-usd", 2)))
    people = [r for r in csv.DictReader(open(arg("--input", str(OUT / "people.csv")), encoding="utf-8-sig"))
              if r.get("first_name") and r.get("last_name") and r.get("domain")]
    if "verdict" in (people[0] if people else {}):
        people = [r for r in people if r["verdict"] in ("OK", "CHECK")]      # LEFT / NO_PROFILE never get an email
    done = {json.loads(l)["person_id"] for l in open(EMAILS, encoding="utf-8")} if EMAILS.exists() else set()
    found = tried = 0
    with open(EMAILS, "a", encoding="utf-8") as f:
        for p in people:
            if p["person_id"] in done:
                continue
            email, used, path = None, None, []
            try:
                for s in order:
                    path.append(s)
                    email = STEPS[s](b, p)
                    if email:
                        used = s; break
            except BudgetExceeded as e:
                print(" ", e); break
            tried += 1; found += bool(email)
            f.write(json.dumps({"person_id": p["person_id"], "domain": p["domain"], "email": email, "provider": used,
                                "tried": path}) + "\n"); f.flush()
            print(f"  {p['first_name']} {p['last_name']} @ {p['domain']}: {email or 'not found'} ({used or '-'})")
    print(f"{found}/{tried} found | spent ${b.spent:.4f} (treg settled; Deepline at list price)")


if __name__ == "__main__":
    main()
