# signal-outbound-stack - state log

## 2026-10-11
**what:**     forked signal-outbound-kit onto a pay-per-use stack: providers.py (treg + Deepline, budget caps, spend log), source_companies.py (Icypeas), find_people.py (QuickEnrich discovery), find_emails.py (Kitt -> QuickEnrich -> Icypeas), hiring_signals.py, clean_people verify via treg, merge one row per person, STACK.md with costs per 100 companies
**why:**      Prospeo subscription ended; Deepline replaces Clay, treg gives per-call providers with no subscription
**broke:**    nothing yet; paid calls written from documented request/response shapes, not run end to end
**outcome:**  scripts compile, free steps run on the example config; secret and client-name scans clean
**status:**   in progress (first 5-row paid test per step still to do)
**postable:** yes, "the same outbound pipeline with no data subscriptions: about $5 of data for 300 multithreaded contacts"

## 2026-10-11
**what:**     sending side added: smartlead.py client, inbox_health.py (OFF / LOW / NEVER / CONNECT flags, warmup switch-on), seed_test.py (link/image guard, tracking off, one campaign per inbox), replies.py (quote-stripped buckets, bounce senders, unblocked opt-outs, Attio deals), monitor.py (bounce guard, 92% gate with the half-fleet rule, report only unless --act); deliverability, launch and replies skills
**why:**      the kit stopped at copy; the sending-side tools only existed in a private, client-specific form
**broke:**    an "Inbox Zero" cold-email filter notice was sorted OTHER; added to the auto-reply rule
**outcome:**  read-only live test on a real account: inbox_health listed 57 inboxes (42 OK, 10 CONNECT, 5 NEVER), monitor + replies ran report-only, seed_test dry run passed and refused a bare domain
**status:**   shipped
**postable:** yes, "the morning script that pulls a weak inbox before it burns the domain"

## 2026-10-11
**what:**     subject-line guide (templates/reference/subject_lines.md): patterns that fit the rules (lower case, name/company?, company + topic, open loop answered in line one, the event, problem, quarter, referral) and the ones left out on purpose (cut-off cliffhangers, fake familiarity, LinkedIn hobbies, caps, sales words); wired into both copy briefs; copy_check now fails all-caps and sales words in subjects and allows 1-word subjects
**why:**      Vish shared a subject-line swipe file to add to the system
**broke:**    the gate's 2-word minimum rejected the guide's own "Acme?" pattern; now 1-4 words
**outcome:**  gate tested: "URGENT offer!" fails 4 ways, "acme?" passes
**status:**   shipped
**postable:** no
