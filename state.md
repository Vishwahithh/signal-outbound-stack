# signal-outbound-stack - state log

## 2026-10-11
**what:**     forked signal-outbound-kit onto a pay-per-use stack: providers.py (treg + Deepline, budget caps, spend log), source_companies.py (Icypeas), find_people.py (QuickEnrich discovery), find_emails.py (Kitt -> QuickEnrich -> Icypeas), hiring_signals.py, clean_people verify via treg, merge one row per person, STACK.md with costs per 100 companies
**why:**      Prospeo subscription ended; Deepline replaces Clay, treg gives per-call providers with no subscription
**broke:**    nothing yet; paid calls written from documented request/response shapes, not run end to end
**outcome:**  scripts compile, free steps run on the example config; secret and client-name scans clean
**status:**   in progress (first 5-row paid test per step still to do)
**postable:** yes, "the same outbound pipeline with no data subscriptions: about $5 of data for 300 multithreaded contacts"
