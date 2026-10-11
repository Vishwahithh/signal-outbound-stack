---
name: market-map
description: Build and grade a target company list for outbound (stages 0-3 of PIPELINE.md) - write the client spec, source companies with Icypeas's native filters via treg, suppress everyone already contacted, crawl each company's own website for free and have agents grade it A/B/C/DROP before any email credit is spent. Use this whenever the user wants a new lead list, a new wave or campaign, a market map, TAM sizing, "find companies like X", or wants to spend data credits before they expire - even if they only say "get me more leads" or "pull companies for the new client".
---

# Market map: spec, source, suppress, grade (before paying for emails)

This stage decides which companies are worth money before any money is spent on them. The costly mistakes in this
kind of work come from skipping or reordering it (revealing emails first, or drifting from the agreed target), so the
order matters more than speed.

## 0. Spec first
Copy `config/client.example.json` to `config/client.json` (or a per-client file passed with `--config`) and fill in:
client and offer, archetype (description, geo, industries, headcount ranges), disqualifiers, grade definitions, signal
windows, suppression sources. Then re-read the archetype against what the user actually asked for. If they disagree,
stop and ask: a list built on the wrong spec is the most expensive output this kit can produce.

Run `python scripts/render_briefs.py` so the agent briefs carry this client's definitions and today's signal dates.

## 1. Source with native filters
Companies only at this stage: no people, no emails. Read Icypeas's company filter reference before editing
`source.icypeas_query` (industry, location, headcount, revenue, type, keyword, headcountGrowth). Prefer narrow
industry labels; broad ones such as "IT Services and IT Consulting" are mostly services firms.

    python scripts/source_companies.py count               # free: size of the market per geography
    python scripts/source_companies.py search --max-usd 1  # ~$0.0004 a company
    python scripts/source_companies.py select              # dedupe + suppression -> source/companies.csv

## 2. Suppress
List every source in the config's `suppression` block: customers, competitors, partners, past campaigns, opt-outs.
`source_companies.py select` leaves suppressed companies out; `python scripts/suppress.py <domain>` checks one by hand (exit 1 on a hit).
If the CRM is set up, also drop anyone whose Attio route is `never` or `cooldown`.

## 3. Grade from the company's own website
1. `python scripts/site_fetch.py --workers 5` - free crawl of homepage, pricing, news, blog, about. More than 5
   workers leaks headless browsers and slows everything down.
2. `python scripts/qualify_batches.py --size 40 --all` - compact batches (pricing text windowed to the priced part).
3. Grade with capable agents (not the cheapest model), about 4 batches per agent, each pointed at
   `runs/<run>/briefs/qualify.md` and one batch file, writing `runs/<run>/qualify/out_NNN.jsonl`. Tell every agent to
   read each company itself and never write a keyword script.
4. Sample-check each returned batch: open 3-5 cached pages and compare with the verdicts before anything downstream
   uses them.
5. `python scripts/merge.py`, then re-read the unreadable ones: `python scripts/firecrawl_refetch.py --workers 2`,
   re-pack and re-grade those into `qualify/rc_out_NNN.jsonl`, and merge again. Re-reading is worth it: sites that
   block a local browser skew towards larger, better-run companies.

## Output and hand-off
- `runs/<run>/leads_master.csv`: grade, what they sell, pricing style, headcount, revenue, country per company.
- Report the funnel to the user: found -> suppressed -> graded A / B / C / DROP -> by size band.
- Only A/B go on: `merge.py` writes their domains to `runs/<run>/approved.csv`. Then
  `python scripts/find_people.py --approved runs/<run>/approved.csv` (free), `clean_people.py names` and
  `verify`, `find_emails.py --max-usd 2`, a fresh `merge.py` and
  `python scripts/mv_verify.py --input runs/<run>/leads_master.csv --label primary`. Only MillionVerifier "ok" is sendable.
- Next: the signal-research skill.
