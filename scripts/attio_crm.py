"""attio_crm.py - Attio API helper plus the deals pipeline (positive replies only).

Stages: Replied yes -> Call booked -> Proposal -> Won / Lost (edit DEAL_STAGES in the config's "crm" block).
Companies are matched on domain and people on email, so re-running never duplicates.

    python scripts/attio_crm.py setup                    # stages + deal fields (safe to re-run)
    python scripts/attio_crm.py deal --json deal.json    # upsert one deal or a list of deals
deal.json: {"company", "domain", "first", "last", "email", "title", "stage", "source", "next_action", "next_action_date"}
"""
import argparse, json, time, urllib.error, urllib.request

from common import config, env

K = env("ATTIO_API_KEY")


def api(method, path, body=None):
    for attempt in range(4):
        req = urllib.request.Request("https://api.attio.com/v2" + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": "Bearer " + K, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                t = r.read()
                return json.loads(t) if t else {}
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 * (attempt + 1)); continue
            raise RuntimeError("%s %s -> %s %s" % (method, path, e.code, e.read().decode("utf-8", "replace")[:300]))
        except urllib.error.URLError:  # network blip: wait and retry instead of killing a long import
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("%s %s -> retries exhausted" % (method, path))


def ensure_fields(obj, fields):
    """fields: [(slug, type, options or None)]. Creates missing attributes and select options."""
    have = {a["api_slug"] for a in api("GET", "/objects/%s/attributes" % obj)["data"]}
    for slug, typ, opts in fields:
        if slug not in have:
            api("POST", "/objects/%s/attributes" % obj, {"data": {"title": slug.replace("_", " ").capitalize(), "api_slug": slug,
                "type": typ, "description": "", "is_required": False, "is_unique": False, "is_multiselect": False, "config": {}}})
            print("  field added: %s.%s" % (obj, slug))
        if opts:
            cur = {o["title"] for o in api("GET", "/objects/%s/attributes/%s/options" % (obj, slug))["data"]}
            for o in opts:
                if o not in cur:
                    api("POST", "/objects/%s/attributes/%s/options" % (obj, slug), {"data": {"title": o}})


def setup(cfg):
    crm = cfg.get("crm", {})
    have = {s["title"] for s in api("GET", "/objects/deals/attributes/stage/statuses")["data"]}
    for s in crm.get("deal_stages", ["Replied yes", "Call booked", "Proposal"]):
        if s not in have:
            api("POST", "/objects/deals/attributes/stage/statuses", {"data": {"title": s}}); print("  stage added:", s)
    ensure_fields("deals", [("source", "select", crm.get("deal_sources", ["Email", "LinkedIn", "Referral", "Other"])),
                            ("next_action", "text", None), ("next_action_date", "date", None), ("thread_link", "text", None),
                            ("last_reply", "text", None)])
    print("  setup done")


def upsert_company(name, domain):
    return api("PUT", "/objects/companies/records?matching_attribute=domains",
               {"data": {"values": {"name": name, "domains": [domain]}}})["data"]["id"]["record_id"]


def upsert_person(first, last, email, title, company_id):
    v = {"name": [{"first_name": first, "last_name": last, "full_name": ("%s %s" % (first, last)).strip()}], "job_title": title,
         "company": [{"target_object": "companies", "target_record_id": company_id}]}
    if email:
        v["email_addresses"] = [email]
        return api("PUT", "/objects/people/records?matching_attribute=email_addresses", {"data": {"values": v}})["data"]["id"]["record_id"]
    return api("POST", "/objects/people/records", {"data": {"values": v}})["data"]["id"]["record_id"]


def upsert_deal(d, owner):
    cid = upsert_company(d["company"], d["domain"])
    pid = upsert_person(d["first"], d.get("last", ""), d.get("email"), d.get("title", ""), cid)
    name = "%s - %s" % (d["company"], d["first"])
    found = api("POST", "/objects/deals/records/query", {"filter": {"name": name}, "limit": 1})["data"]
    v = {"name": name, "stage": d["stage"], "owner": d.get("owner") or owner,
         "associated_company": [{"target_object": "companies", "target_record_id": cid}],
         "associated_people": [{"target_object": "people", "target_record_id": pid}]}
    v.update({f: d[f] for f in ("source", "next_action", "next_action_date", "thread_link", "last_reply") if d.get(f)})
    if found:
        api("PATCH", "/objects/deals/records/%s" % found[0]["id"]["record_id"], {"data": {"values": v}}); act = "updated"
    else:
        api("POST", "/objects/deals/records", {"data": {"values": v}}); act = "created"
    print("  deal %s: %s (%s)" % (act, name, d["stage"]))


if __name__ == "__main__":
    cfg = config()
    a = argparse.ArgumentParser(); a.add_argument("cmd", choices=["setup", "deal"]); a.add_argument("--json"); a.add_argument("--config")
    a = a.parse_args()
    if a.cmd == "setup":
        setup(cfg)
    else:
        data = json.load(open(a.json, encoding="utf-8"))
        for d in (data if isinstance(data, list) else [data]):
            upsert_deal(d, cfg["crm"]["owner_email"])  # Attio deals need an owner: a workspace member's email
