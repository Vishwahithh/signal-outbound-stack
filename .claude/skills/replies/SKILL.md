---
name: replies
description: Run the daily campaign check and handle replies (stages 8-9 of PIPELINE.md) - bounce guard, inbox reputation gate, every reply sorted into positive / question / opt-out / out-of-office / departed, opt-outs blocked, positives turned into CRM deals and answered fast. Use this whenever the user asks about replies, "any responses", how a campaign is doing, the morning check, monitoring, yes-rate, or what to do with a reply, even if they only say "update" or "check the campaigns".
---

# Replies: the leak is between the yes and the call

Across real waves most positives never became calls, because the answer went out a day later with homework attached.
A healthy programme books 40-50% of positives by replying within the hour with a time and calling the same day.

## Every morning
    python scripts/monitor.py          # report only
    python scripts/monitor.py --act    # also pauses on bounces and pulls / re-adds inboxes at the gate

It never starts a campaign, never sends or answers an email, never deletes. Schedule it before the send window.

## Replies
    python scripts/replies.py [--attio]

- Read every POSITIVE and OTHER yourself. The rules sort; a person decides. Nothing is assumed positive.
- Smartlead's reply count includes out-of-office: report human replies only, hand-classified, per segment.
- OPT_OUT: confirm the lead is blocked; the script flags any that can still be emailed.
- POSITIVE: reply within the hour with two concrete times, then phone or text the same day if a number exists.
- DEPARTED: note who replaced them; that is a new contact, not a dead account.
- Draft replies for the operator; send only on their explicit go-ahead.

## Reading results
Yes-rate per person contacted, by segment, signal and size, against the hypothesis and kill rule written at launch.
Feed real replies back into the voice-of-customer bank and the CRM cool-down.
