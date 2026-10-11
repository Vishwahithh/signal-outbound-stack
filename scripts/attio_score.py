"""attio_score.py - nightly lead score (companies) and route (people) in Attio.

Score 0-100 per company (weights in config "crm.score"):
  website grade      A 40, B 25 (C, DROP, ungraded 0)
  signal recency     <=30 days 30, <=90 days 20, <=180 days 10   (hiring signal with no date: 15)
  size band          +15 if headcount inside crm.score.headcount [min, max]
  verified email     +10 if any person at the company has mv_result = ok

Route per person (field `route`), checked in this order:
  never             do_not_contact, company is a customer, grade DROP, bounced/unsubscribed
  engaged           a deal owns them
  cooldown          cooldown_until in the future
  regrade           grade C or ungraded
  linkedin_only     grade A/B but email is not MillionVerifier ok
  signal_campaign   score >= 70 and email ok and a signal on the company
  standard_campaign score >= 50 and email ok
  watch_list        good fit, no signal yet: re-check monthly
A route is advice for the next campaign build; nothing here sends or changes a campaign.

    python scripts/attio_score.py [--dry-run]
"""
import argparse, datetime, time
from collections import Counter

from attio_crm import api, ensure_fields
from common import config

ROUTES = ["never", "engaged", "cooldown", "regrade", "linkedin_only", "signal_campaign", "standard_campaign", "watch_list"]


def all_records(obj):
    out, off = [], 0
    while True:
        d = api("POST", "/objects/%s/records/query" % obj, {"limit": 500, "offset": off})["data"]
        out += d
        if len(d) < 500:
            return out
        off += 500


def val(v, k, kind="value"):
    x = (v.get(k) or [{}])[0]
    if kind == "option":
        return (x.get("option") or {}).get("title")
    if kind == "ref":
        return x.get("target_record_id")
    return x.get("value")


def main(dry=False):
    sc = config().get("crm", {}).get("score", {})
    lo, hi = sc.get("headcount", [11, 200])
    if not dry:
        ensure_fields("people", [("route", "select", ROUTES)])
    today = datetime.date.today()
    comps = {c["id"]["record_id"]: c["values"] for c in all_records("companies")}
    people = all_records("people")
    ok_at = {val(p["values"], "company", "ref") for p in people if val(p["values"], "mv_result", "option") == "ok"}
    score = {}
    for cid, v in comps.items():
        s = {"A": 40, "B": 25}.get(val(v, "icp_grade", "option"), 0)
        sd, st = val(v, "signal_date"), val(v, "signal_type", "option") or ""
        if sd:
            age = (today - datetime.date.fromisoformat(sd[:10])).days
            s += 30 if age <= 30 else 20 if age <= 90 else 10 if age <= 180 else 0
        elif "hiring" in st.lower():
            s += 15
        hc = val(v, "headcount")
        if hc and lo <= float(hc) <= hi:
            s += 15
        if cid in ok_at:
            s += 10
        score[cid] = s
    routes = Counter()
    for p in people:
        v = p["values"]; cid = val(v, "company", "ref"); cv = comps.get(cid, {})
        grade = val(cv, "icp_grade", "option") or "ungraded"
        cs, mv, cu = val(v, "contact_status", "option"), val(v, "mv_result", "option"), val(v, "cooldown_until")
        if val(v, "do_not_contact") or val(cv, "lifecycle", "option") == "customer" or grade == "DROP" or cs in ("bounced", "unsubscribed"):
            r = "never"
        elif cs == "engaged":
            r = "engaged"
        elif cu and datetime.date.fromisoformat(cu[:10]) > today:
            r = "cooldown"
        elif grade in ("C", "ungraded"):
            r = "regrade"
        elif mv != "ok":
            r = "linkedin_only"
        elif score.get(cid, 0) >= 70 and val(cv, "signal_type", "option") not in (None, "none"):
            r = "signal_campaign"
        elif score.get(cid, 0) >= 50:
            r = "standard_campaign"
        else:
            r = "watch_list"
        routes[r] += 1
        if not dry and val(v, "route", "option") != r:
            api("PATCH", "/objects/people/records/%s" % p["id"]["record_id"], {"data": {"values": {"route": r}}}); time.sleep(0.06)
    if not dry:
        for cid, s in score.items():
            if val(comps[cid], "lead_score") != s:
                api("PATCH", "/objects/companies/records/%s" % cid, {"data": {"values": {"lead_score": s}}}); time.sleep(0.06)
    print("companies %d | people %d" % (len(comps), len(people)))
    print("score bands:", dict(Counter("70+" if s >= 70 else "50-69" if s >= 50 else "<50" for s in score.values())))
    print("routes:", dict(routes))


if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("--dry-run", action="store_true"); a.add_argument("--config")
    main(a.parse_args().dry_run)
