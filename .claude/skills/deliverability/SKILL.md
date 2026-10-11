---
name: deliverability
description: Check and fix the sending side before and during outbound - inbox warmup actually on, reputation at the gate (92% default), burned domains kept out, SMTP/IMAP connected, new inboxes warmed slowly. Use this whenever the user asks about inboxes, domains, warmup, reputation, spam placement, "are my inboxes ready", "why are replies down", buying or adding new mailboxes, or before any launch - even if they only say "check the inboxes".
---

# Deliverability: the inboxes decide whether anyone reads the email

The best email scores zero from the junk folder. One early wave sent 619 emails for a single human reply because about
half landed in spam; the copy was never the problem. So the sending side is checked by script, not assumed.

## The rules
- 3 inboxes per domain, domains owned by the operator, neutral names not tied to one client.
- Warmup checked ON through the API. Never trust a dashboard or a vendor's word: it was silently off on 10 new inboxes.
- New inboxes warm 3-4 weeks before any campaign. Start slow (5-10 a day; Smartlead's minimum ramp is 5) and raise it
  week by week only if reputation climbs.
- Reputation gate: under `sending.rep_gate` (92%) an inbox comes out of campaigns, warmup stays on, it goes back at 92%+.
- A burned domain goes on `sending.never_domains` and never sends again, whatever its warmup score says: warmup
  reputation measures the warmup pool, not where your cold email lands.
- Cold email one is words only: no links, no domain in the signature, no tracking pixel, no images.

## Run
    python scripts/inbox_health.py                                  # every inbox, worst first: NEVER / CONNECT / OFF / LOW / OK
    python scripts/inbox_health.py --enable-warmup --domain new.com # dry run; add --apply to switch warmup on

Report counts first ("18 OK, 2 LOW, 0 OFF"), then the inboxes that need action. Switching warmup on is safe when
asked; buying inboxes or domains is always the operator's call and needs their explicit "buy".

Next: the launch skill (seed test, ramp, kill rule).
