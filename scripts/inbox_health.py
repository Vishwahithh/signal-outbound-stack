"""inbox_health.py - is every sending inbox connected, warming, and healthy enough to send? (stage 7 gate)

Reads every Smartlead email account and prints one line each: warmup status, reputation, daily cap, campaigns.
Flags, worst first:
  OFF       warmup is not running (it was silently off on 10 new inboxes once; never assume it is on)
  NEVER     the domain is on config "sending.never_domains" (burned): must not be in any campaign, whatever its score
  LOW       reputation under config "sending.rep_gate" (default 92): pull from campaigns, keep warmup on
  CONNECT   SMTP or IMAP failing
  OK

    python scripts/inbox_health.py [--domain acme-mail.com]
    python scripts/inbox_health.py --enable-warmup --domain newdomain.com [--apply]
--enable-warmup switches warmup on with config "sending.warmup" (per_day, rampup >= 5, reply_rate); without --apply
it only prints what it would change.
"""
import argparse
from collections import Counter

from common import config
from smartlead import accounts, api, rep, warmup_status


def main():
    cfg = config()
    s = cfg.get("sending") or {}
    gate, never = float(s.get("rep_gate", 92)), tuple(s.get("never_domains") or ())
    w = s.get("warmup") or {}
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain")
    ap.add_argument("--enable-warmup", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--config")
    a = ap.parse_args()
    accs = [x for x in accounts().values() if not a.domain or x["from_email"].lower().endswith("@" + a.domain.lower())]
    rows = []
    for x in accs:
        e, r, ws = x["from_email"], rep(x), warmup_status(x)
        flag = ("NEVER" if never and e.lower().endswith(never) else "CONNECT" if not (x.get("is_smtp_success") and x.get("is_imap_success"))
                else "OFF" if ws != "ACTIVE" else "LOW" if r is not None and r < gate else "OK")
        rows.append((["NEVER", "CONNECT", "OFF", "LOW", "OK"].index(flag), flag, e, ws, r, x.get("message_per_day"), x.get("campaign_count"), x["id"]))
    for _, flag, e, ws, r, cap, nc, _id in sorted(rows):
        print(f"{flag:8} {e:40} warmup {ws:8} rep {'-' if r is None else f'{r:.0f}%':>5}  cap {cap}/day  campaigns {nc}")
    print("\n", dict(Counter(r[1] for r in rows)), f"| gate {gate:.0f}%")
    if a.enable_warmup:
        per_day, ramp, reply = int(w.get("per_day", 20)), max(5, int(w.get("rampup", 5))), int(w.get("reply_rate", 30))
        todo = [r for r in rows if r[1] == "OFF"]
        print(f"\nwarmup on for {len(todo)} inbox(es): up to {per_day}/day, +{ramp}/day, {reply}% replies{'' if a.apply else ' (dry run: add --apply)'}")
        for r in todo:
            if a.apply:
                res = api("POST", f"/email-accounts/{r[7]}/warmup", {"warmup_enabled": True, "total_warmup_per_day": per_day,
                                                                     "daily_rampup": ramp, "reply_rate_percentage": reply})
                print(f"  {r[2]}: {res.get('message') or res.get('_error')}")
            else:
                print(f"  {r[2]}")


if __name__ == "__main__":
    main()
