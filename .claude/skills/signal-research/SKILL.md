---
name: signal-research
description: Find and verify a dated "why now" event for each graded company (stage 4 of PIPELINE.md) - product or AI launches, new markets, pricing changes, funding, new owners, new commercial leaders, relevant hiring - using agents that must open the source page, then a human review pass that cuts weak signals. Use this whenever the user asks for signals, triggers, intent, "reasons to reach out", why-now research, signal-based outbound, or which accounts to contact first, even if they just say "research these companies" or "what happened at these companies lately".
---

# Signal research: dated, opened, reviewed

A signal is only useful if it is true, recent, and a real reason for the company to think about the client's offer.
Agents are good at finding candidates and poor at judging usefulness, so this skill has two halves: agent research,
then a human review that is not optional.

## Signal definitions
They live in the client config (`signals`, `signal_priority`): id, name, window in days, and what does NOT count.
`python scripts/render_briefs.py` turns the windows into absolute dates in `runs/<run>/briefs/research.md`; re-render
on the day you run. Edit the definitions per client: a security consultancy cares about breaches and compliance
deadlines, a pricing consultancy about launches and new owners.

## 1. Agent research
- Input: A/B companies with a verified email, split into CSV batches of ~15 in `runs/<run>/research/batch_NNN.csv`
  (A first). Columns: domain, company, country, headcount, grade, pricing_style, what_they_sell, signal_hint,
  last_funding_date, email_domain, domain_mismatch (all in leads_master.csv).
- Agents: capable models, ~3 batches each, at most 3 running at once (more hits session/rate limits and stalls them
  all). Each writes one JSON line per company to `research/out_NNN.jsonl` as it goes, so a stall loses nothing.
- Search ladder, free first, going down only on failure: TinyFish -> Tavily (news) -> Firecrawl (news, last 6 months)
  -> Exa (best for LinkedIn posts). Fetch ladder the same way.
- A signal counts only if the agent opened the page and the page shows the fact and a date inside the window.
  Search-snippet dates are often wrong; data-vendor funding/news fields can lag by months.
- Pilot one batch first and open two of its source URLs yourself before launching the rest.

## 2. Human review (required)
Put every verified best signal in one table and read all of them. Cut, with a reason, into
`runs/<run>/signal_review_decisions.json` as `{"cut": ["domain", ...], "reasons": {"domain": "why"}}`:
- the company is being absorbed into its buyer (product folded in, rebranded under the buyer)
- waitlist, beta, "coming soon", limited preview
- an integration, a connector, a single feature, a point release, a dataset
- a partner "commitment" or unfinished bid presented as funding
- vague posts ("next chapter"), wrong HQ country, a contact who is not a decision-maker
Where the agent picked a weak signal but the page shows a stronger one (a market expansion behind a connector
announcement), switch to the stronger one. Expect to cut around a fifth. Skipping this step means emails that open on
a non-event, which reads worse than no personalisation at all.

## 3. Output
- `python scripts/merge.py` picks up the research. Hand the user the surviving signal leads: company, contact, signal,
  one-sentence fact, date, source URL.
- With the CRM: `python scripts/attio_leads.py import-run` then `python scripts/attio_score.py` - leads with a recent
  reviewed signal route to `signal_campaign`.
- Next: copy from `runs/<run>/briefs/copy.md` (opener on the event + one question about the specific new thing + one
  approved proof). Copy never judges the prospect's business; scraped pricing stays internal.

## Keeping it fresh
One-off research goes stale in weeks. The always-on version re-crawls news, blog, pricing and careers pages weekly
for the watch list and classifies only what changed.
