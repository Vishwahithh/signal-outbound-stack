---
name: launch
description: Launch a wave safely (stage 7 of PIPELINE.md) - seed-test the real sequence to your own inboxes and read where it lands, write the hypothesis and kill rule, check every lead is verifier-ok, then start on a slow ramp. Use this whenever the user says launch, go live, start the campaign, upload to Smartlead, send the wave, seed test, or "is it ready to send", even if they only say "let's go".
---

# Launch: nothing goes to strangers until a person has seen it land

## Before anything is created
1. Leads: 100% checked by MillionVerifier, only "ok" in the upload, no catch-alls. Lead the checklist with
   "X ok / Y catch-all / Z unchecked". Never call a wave ready with anything unchecked.
2. Copy: `python scripts/copy_check.py` passes; a sample was read by the client and by a prospect-eye reviewer.
3. Inboxes: `python scripts/inbox_health.py` shows every inbox for this wave OK (deliverability skill).
4. Hypothesis and kill rule written before the first send: who, which signal, what result by which date, and the
   number that stops the wave. Without one a dead campaign runs for weeks.

## Seed test (mandatory)
Put the real sequence in a JSON file (`config/sequence.example.json` shows the shape) and run

    python scripts/seed_test.py --sequence config/sequence.json --inboxes <ids>          # dry run + link check
    python scripts/seed_test.py --sequence config/sequence.json --inboxes <ids> --send   # one campaign per inbox

The script refuses any step with a URL, bare domain or image, turns tracking off and sends every step on delay 0 to
`sending.seeds`. A person then opens every seed inbox and notes PRIMARY / PROMOTIONS / SPAM per sending inbox, and
checks threading and the phone view. Mix Gmail, Google Workspace and Outlook / Microsoft 365 seeds. A pass is a smoke
alarm, not a verdict; the operator decides.

## Start
- Campaign settings: open and click tracking off, plain text, stop on reply, plain-text opt-out line.
- Ramp slowly (for example 4 per inbox on day 1, then up to about 10 per inbox) and let the monitor pull weak inboxes.
- Only the operator starts a campaign. A passed checklist is not a go-ahead.

Next: the replies skill, and `python scripts/monitor.py` every weekday morning.
