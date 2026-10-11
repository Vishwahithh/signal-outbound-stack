"""attio_leads.py - Attio as the full lead CRM: every company and person, with grade, signal, verification result and a
cool-down date, so no campaign ever re-contacts someone too soon.

  people:    contact_status, campaign_name, channel, mv_result, last_touch, cooldown_until, do_not_contact
  companies: client, icp_grade, lead_score, lifecycle, last_contacted, cooldown_until, hq_country, revenue_band,
             signal_type, signal_date, signal_fact, signal_url

Cool-down rules (days in config "crm.cooldown_days"):
  sequence finished, no reply -> cooldown (default 90)     not now -> not_now (90)     negative -> negative (365)
  unsubscribed / bounced -> never again (do_not_contact)   positive / question -> engaged (a deal owns them)

    python scripts/attio_leads.py setup
    python scripts/attio_leads.py import-run [--dry-run]           # runs/<run>/leads_master.csv + research + review cuts
    python scripts/attio_leads.py import-csv --file x.csv [--dry-run]
        x.csv columns: email, first, last, title, company, domain, linkedin, campaign, status, last_touch (YYYY-MM-DD)
    python scripts/attio_leads.py customers --file customers.csv   # column domain: flagged customer, never prospected
"""
import argparse, csv, datetime, json, time
from collections import Counter

from attio_crm import api, ensure_fields
from common import config, jl, run_dir

CFG = config()
CRM = CFG.get("crm", {})
CLIENT = CFG["client"]["crm_label"]
SIG = {s["id"]: f"{s['id']} {s['short']}" for s in CFG["signals"]}
STATUSES = ["queued", "in_sequence", "engaged", "cooldown", "not_now", "negative", "unsubscribed", "bounced"]
MV = ["ok", "catch_all", "invalid", "unknown", "not_checked"]
COOL = CRM.get("cooldown_days", {"cooldown": 90, "not_now": 90, "negative": 365})


def setup():
    ensure_fields("people", [("contact_status", "select", STATUSES), ("channel", "select", ["email", "linkedin", "phone"]),
                             ("mv_result", "select", MV), ("campaign_name", "text", None), ("last_touch", "date", None),
                             ("cooldown_until", "date", None), ("do_not_contact", "checkbox", None)])
    ensure_fields("companies", [("client", "select", [CLIENT]), ("icp_grade", "select", ["A", "B", "C", "DROP", "ungraded"]),
                                ("lifecycle", "select", ["prospect", "in_sequence", "engaged", "cooldown", "do_not_contact", "customer"]),
                                ("signal_type", "select", list(SIG.values()) + ["none"]), ("lead_score", "number", None),
                                ("last_contacted", "date", None), ("cooldown_until", "date", None), ("hq_country", "text", None),
                                ("revenue_band", "text", None), ("headcount", "number", None), ("signal_date", "date", None),
                                ("signal_fact", "text", None), ("signal_url", "text", None)])
    print("  setup done")


def until(st, last):
    if st not in COOL or not last:
        return None
    return (datetime.date.fromisoformat(last[:10]) + datetime.timedelta(days=COOL[st])).isoformat()


def lifecycle(st):
    return {"queued": "prospect", "in_sequence": "in_sequence", "engaged": "engaged", "cooldown": "cooldown", "not_now": "cooldown",
            "negative": "cooldown", "unsubscribed": "do_not_contact", "bounced": "do_not_contact"}[st]


def rows_run():
    run = run_dir(CFG)
    res = {x["domain"]: x for x in jl(run / "research" / "out_*.jsonl")}
    p = run / "signal_review_decisions.json"
    cut = set(json.load(open(p, encoding="utf-8")).get("cut", [])) if p.exists() else set()
    for r in csv.DictReader(open(run / "leads_master.csv", encoding="utf-8-sig")):
        x = res.get(r["domain"]) or {}
        b = x.get("best_signal") if r["domain"] not in cut else None
        s = next((y for y in x.get("signals", []) if y.get("type") == b and y.get("verified") == "has"), None) if b and b != "none" else None
        company = {"company": r["company"], "domain": r["domain"], "grade": r["grade"] or "ungraded", "country": r["country"],
                   "revenue": r["revenue_band"], "headcount": r["headcount"],
                   "signal": (SIG.get(b), s.get("date"), s.get("fact"), s.get("url")) if s else None}
        people = [(r["email"], f"{r['first_name']} {r['last_name']}", r["title"], r["linkedin"], r["mv"]),
                  (r["second_email"], r["second_name"], r["second_title"], "", r["second_mv"])]
        for e, name, title, li, mv in people:
            if not e:
                continue
            nm = name.split()
            yield {**company, "email": e.lower(), "first": nm[0] if nm else "", "last": " ".join(nm[1:]), "title": title,
                   "linkedin": li, "campaign": CFG["run"], "status": "queued", "last_touch": None, "cooldown_until": None,
                   "mv": mv if mv in MV else ("not_checked" if not mv else "unknown")}


def rows_csv(path):
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        e = (r.get("email") or "").lower()
        if "@" not in e:
            continue
        st = r.get("status") or "in_sequence"
        st = st if st in STATUSES else "in_sequence"
        yield {"email": e, "first": r.get("first", ""), "last": r.get("last", ""), "title": r.get("title", ""),
               "company": r.get("company") or e.split("@")[1], "domain": r.get("domain") or e.split("@")[1],
               "linkedin": r.get("linkedin", ""), "campaign": r.get("campaign", ""), "status": st,
               "last_touch": r.get("last_touch") or None, "cooldown_until": until(st, r.get("last_touch"))}


def push(r):
    cv = {"domains": [r["domain"]], "client": CLIENT, "lifecycle": lifecycle(r["status"])}
    for k, f in (("grade", "icp_grade"), ("country", "hq_country"), ("revenue", "revenue_band"),
                 ("last_touch", "last_contacted"), ("cooldown_until", "cooldown_until")):
        if r.get(k):
            cv[f] = r[k]
    if str(r.get("headcount") or "").isdigit():
        cv["headcount"] = int(r["headcount"])
    if r.get("signal"):
        cv.update({k: v for k, v in zip(("signal_type", "signal_date", "signal_fact", "signal_url"), r["signal"]) if v})
    if not api("POST", "/objects/companies/records/query", {"filter": {"domains": r["domain"]}, "limit": 1})["data"]:
        cv["name"] = r["company"]
    cid = api("PUT", "/objects/companies/records?matching_attribute=domains", {"data": {"values": cv}})["data"]["id"]["record_id"]
    pv = {"email_addresses": [r["email"]], "company": [{"target_object": "companies", "target_record_id": cid}],
          "contact_status": r["status"], "campaign_name": r["campaign"], "channel": "email",
          "do_not_contact": r["status"] in ("unsubscribed", "bounced")}
    for k, f in (("mv", "mv_result"), ("title", "job_title"), ("linkedin", "linkedin"), ("last_touch", "last_touch"),
                 ("cooldown_until", "cooldown_until")):
        if r.get(k):
            pv[f] = r[k]
    if r["first"] or r["last"]:
        pv["name"] = [{"first_name": r["first"], "last_name": r["last"], "full_name": ("%s %s" % (r["first"], r["last"])).strip()}]
    api("PUT", "/objects/people/records?matching_attribute=email_addresses", {"data": {"values": pv}})


def do_import(rows, dry):
    rows = list(rows)
    print("  %d leads | %s" % (len(rows), dict(Counter(r["status"] for r in rows))))
    if dry:
        return
    for i, r in enumerate(rows, 1):
        try:
            push(r)
        except RuntimeError as e:
            print("  ERR", r["email"], str(e)[:160])
        if i % 100 == 0:
            print("   ", i)
        time.sleep(0.12)  # Attio allows ~25 writes/s; stay far below
    print("  import done")


def customers(path):
    n = 0
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        d = (r.get("domain") or "").strip()
        if "." not in d:
            continue
        try:
            api("PUT", "/objects/companies/records?matching_attribute=domains",
                {"data": {"values": {"domains": [d], "name": r.get("name") or d, "client": CLIENT, "lifecycle": "customer"}}})
            n += 1
        except RuntimeError as e:
            print("  skipped", d, str(e)[-80:])
        time.sleep(0.12)
    print("  customers flagged:", n)


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("cmd", choices=["setup", "import-run", "import-csv", "customers"])
    a.add_argument("--file"); a.add_argument("--dry-run", action="store_true"); a.add_argument("--config")
    a = a.parse_args()
    if a.cmd == "setup":
        setup()
    elif a.cmd == "import-run":
        do_import(rows_run(), a.dry_run)
    elif a.cmd == "import-csv":
        do_import(rows_csv(a.file), a.dry_run)
    else:
        customers(a.file)
