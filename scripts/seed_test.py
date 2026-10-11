"""seed_test.py - send the real sequence to your own inboxes and LOOK at it before any wave (stage 7 gate).

A spam-word checker cannot tell you where the email lands, whether a signature domain turns into a blue link, whether
steps 2 and 3 thread, or how it reads on a phone. One early wave sent 619 emails for one human reply because about half
landed in spam; the copy was never the problem. Nothing goes to strangers until this has been read by a person.

What it does
- Checks every step for anything that renders as a link or image (URL, bare domain, <a>, <img>) and REFUSES on a hit,
  on the dry run too: a cold first email is words only.
- One campaign per sending inbox (a single campaign rotates inboxes, so you could not tell which one landed where),
  every step on delay 0, tracking pixel and click tracking OFF, plain text, a plain-text opt-out line.
- The sending address is written into the company field, so each received email says which inbox sent it.

Input: a sequence file (JSON) {"subjects": {"1": "...", "2": "...", "3": "..."}, "bodies": {"1": "...", ...},
"lead": {"first_name": "...", "company": "...", ...}} with {first_name}-style placeholders filled from "lead".
Seeds and the opt-out line come from config "sending.seeds" / "sending.optout_text". Use a mix of Gmail, Google
Workspace and Outlook / Microsoft 365 seeds: an all-Google panel says nothing about Microsoft placement.

    python scripts/seed_test.py --sequence seq.json --inboxes 123,456          # dry run: prints what arrives
    python scripts/seed_test.py --sequence seq.json --inboxes 123,456 --send   # creates and STARTS the campaigns
Then note PRIMARY / PROMOTIONS / SPAM per inbox and per seed, and decide. A pass is a smoke alarm, not a verdict.
"""
import argparse, json, re, sys
from datetime import datetime, timezone

from common import config
from smartlead import accounts, api

LINKISH = re.compile(r"https?://|www[.]|<a[ >]|<img|[a-z0-9-]{2,}[.](?:co[.]uk|com|io|net|org|ai|co|dev|app)\b", re.I)


def no_links(name, text):
    m = LINKISH.search(text)
    if m:
        sys.exit(f"\n  REFUSING: {name} contains something that renders as a link or image: {m.group(0)!r}\n")


def html(body):
    return "".join("<p>%s</p>" % p.replace("\n", "<br>") for p in body.split("\n\n") if p.strip())


def main():
    cfg = config()
    s = cfg.get("sending") or {}
    ap = argparse.ArgumentParser()
    ap.add_argument("--sequence", required=True)
    ap.add_argument("--inboxes", required=True, help="comma-separated Smartlead email account ids")
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--config")
    a = ap.parse_args()
    seq = json.load(open(a.sequence, encoding="utf-8"))
    lead, steps = seq.get("lead") or {}, sorted(seq["bodies"], key=int)
    seeds = s.get("seeds") or []
    if not seeds:
        sys.exit('config "sending.seeds" is empty: list addresses you control')
    filled = {n: seq["bodies"][n].format(**lead) for n in steps}
    for n in steps:
        no_links(f"step {n}", filled[n])
        no_links(f"subject {n}", seq["subjects"].get(n, ""))
    print(f"link check passed on {len(steps)} steps")
    accs = accounts()
    ids = [int(i) for i in a.inboxes.split(",") if i.strip()]
    never = tuple(s.get("never_domains") or ())
    for i in ids:
        if i not in accs:
            sys.exit(f"inbox {i} not found in Smartlead")
        if never and accs[i]["from_email"].lower().endswith(never):
            sys.exit(f"REFUSING: {accs[i]['from_email']} is on sending.never_domains")
    print(f"\nfrom {len(ids)} inbox(es) to {len(seeds)} seeds, {len(steps)} steps each, all on delay 0\n")
    print(f"Subject: {seq['subjects'].get(steps[0], '')}\n\n{filled[steps[0]]}\n")
    if not a.send:
        print("[dry run] nothing created. Add --send to create and start one campaign per inbox."); return
    sequence = [{"seq_number": int(n), "seq_delay_details": {"delay_in_days": 0}, "subject": seq["subjects"].get(n, ""),
                 "email_body": "{{body_%s}}" % n} for n in steps]
    schedule = {"timezone": s.get("timezone", "Europe/London"), "days_of_the_week": [0, 1, 2, 3, 4, 5, 6],
                "start_hour": "00:00", "end_hour": "23:59", "min_time_btw_emails": 5, "max_new_leads_per_day": 50,
                "schedule_start_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    stamp = datetime.now().strftime("%d%b %H:%M")
    for i in ids:
        sender = accs[i]["from_email"]
        cid = api("POST", "/campaigns/create", {"name": f"SEED {sender} {stamp}"}, fatal=True).get("id")
        api("POST", f"/campaigns/{cid}/sequences", {"sequences": sequence}, fatal=True)
        api("POST", f"/campaigns/{cid}/email-accounts", {"email_account_ids": [i]}, fatal=True)
        api("POST", f"/campaigns/{cid}/schedule", schedule, fatal=True)
        # Smartlead adds an open-tracking pixel by default; it arrived as a broken image and the seed landed in spam.
        api("POST", f"/campaigns/{cid}/settings", {"track_settings": ["DONT_TRACK_EMAIL_OPEN", "DONT_TRACK_LINK_CLICK"],
                                                   "stop_lead_settings": "REPLY_TO_AN_EMAIL", "send_as_plain_text": True,
                                                   "unsubscribe_text": s.get("optout_text") or "If you would rather I did not write again, just reply and say so."}, fatal=True)
        leads = [{"email": e, "first_name": lead.get("first_name", ""), "company_name": f"{lead.get('company', '')} | {sender}",
                  "custom_fields": {f"body_{n}": html(filled[n]) for n in steps}} for e in seeds]
        res = api("POST", f"/campaigns/{cid}/leads", {"lead_list": leads}, fatal=True)
        api("POST", f"/campaigns/{cid}/status", {"status": "START"}, fatal=True)
        print(f"  {sender:40} campaign {cid} leads {res.get('upload_count') or res.get('total_leads_added')} STARTED")
    print("\nNow open every seed inbox: note PRIMARY / PROMOTIONS / SPAM per sender, check threading and the phone view.")


if __name__ == "__main__":
    main()
