# signal-outbound-stack

The same grade-before-you-pay outbound pipeline as
[signal-outbound-kit](https://github.com/Vishwahithh/signal-outbound-kit), rebuilt on a pay-per-use data stack with no
subscriptions: **treg** and **Deepline** in place of Prospeo and Clay, **Claude** for every judgement call.

A Claude Code kit for signal-based B2B outbound: find the companies that fit, check them on their own websites, find a
dated reason to reach out right now, and only then pay for people and emails. One JSON config per client describes the
target, the signals and the proof; scripts, agent briefs, skills and the CRM all read from it.

## The stack, by stage

| Stage | What happens | Tool | Cost |
|---|---|---|---|
| 0 Layer | waterfalls, provider choice, spend logging | Deepline (Clay replacement) + treg | pay per use |
| 1 TAM | every company matching the archetype | Icypeas company search via treg | ~$0.0004 / company |
| 2 ICP | firmographics from the search, tech stack and fit read from the company's own site | crawl4ai + Claude | free |
| 3 Signals | why now: hiring, funding, launches, new leaders | LinkedIn jobs via treg, Explorium events (optional), Claude research agents | $0.001 / job; ~$0.08 / company for events |
| 4 Company research | homepage, pricing, news, about | crawl4ai, then Tavily -> Firecrawl -> Exa only on failure | mostly free |
| 5 People | who to contact at A/B companies, still there, in that role | QuickEnrich discovery via treg (free), HarvestAPI LinkedIn profile via treg | free / ~$0.004 per person |
| 6 Score + write | 3 company + 3 person insights, one chosen, copy from it | Claude + `copy_check.py` | $0 |
| 7 Contact data | verified work email, cheapest first | Kitt AI -> QuickEnrich (treg) -> Icypeas (Deepline), then MillionVerifier | ~$0.005 per find; misses free |
| 8 Send + CRM | sequencer, inboxes, Attio | your own | fixed monthly |

Data for 100 companies costs roughly **$1.50-4.50** with one person each and **$3.50-6.50** with three people each
(multithreading). The fixed costs (inboxes, sequencer, LinkedIn tool) are most of the bill. See [STACK.md](STACK.md)
for the full cost table and the reasoning behind each choice.

## Why this order
Most outbound burns money in the wrong place: it buys emails for a big list and then discovers most of it was never a
fit. This kit grades first and pays later:

```
spec -> companies (native filters) -> suppress -> grade on own website -> signals + human review
     -> people at A/B only -> clean names + check each on LinkedIn -> emails (waterfall) -> verify
     -> person research -> insights -> copy per person -> gate + blind score -> launch -> CRM cool-down
```

See [PIPELINE.md](PIPELINE.md) for the gates and the lessons behind each one.

## What's inside

| Path | What it is |
|---|---|
| `config/client.example.json` | Everything client-specific: offer, archetype, Icypeas query, contacts and personas, hiring titles, email waterfall, grades, signals, proof, suppression, CRM |
| `scripts/providers.py` | treg and Deepline clients: budget cap per run, every call's real cost logged to `runs/<run>/cache/spend.jsonl`, routed and banned providers refused |
| `scripts/source_companies.py` | Free count, then Icypeas company search page by page under a dollar cap; dedupe and suppression |
| `scripts/site_fetch.py`, `fetch_pages.py` | Free website crawl (crawl4ai), paid ladder (Tavily -> Firecrawl -> Exa) only on failure |
| `scripts/qualify_batches.py` | Pack site text into compact batches for grading agents |
| `scripts/firecrawl_refetch.py` | Re-read sites that blocked the free crawler |
| `scripts/hiring_signals.py` | Open LinkedIn roles per graded company, as dated evidence for the signal agents |
| `scripts/find_people.py` | Free people discovery at approved companies, ranked by persona, `per_company` people each |
| `scripts/clean_people.py` | `names`: names fit to print. `verify`: each person against their own LinkedIn (OK / CHECK / LEFT / NO_PROFILE) via treg or Apify |
| `scripts/find_emails.py` | Email waterfall, pay only for finds, never a guessed address |
| `scripts/mv_verify.py` | MillionVerifier bulk verification with resume |
| `scripts/merge.py` | One lead master per run: one row per person (multithreading), email-domain mismatch flags |
| `scripts/person_research.py` | One dossier per company: buying group, each exec's own LinkedIn posts, the site, the reviewed signal |
| `scripts/copy_check.py` | Deterministic gate on persona copy |
| `scripts/render_briefs.py` | Fill the agent briefs from the config, with signal windows as real dates |
| `scripts/inbox_health.py` | Every sending inbox, worst first: burned domain, connection failing, warmup OFF, reputation under the gate; switches warmup on (dry run by default) |
| `scripts/seed_test.py` | Sends the real sequence to your own inboxes first: refuses links and images, tracking off, one campaign per inbox, all steps same day |
| `scripts/replies.py` | Every reply sorted (positive / other / opt-out / out-of-office / departed / auto), quote stripped, bounces caught, unblocked opt-outs flagged, positives to Attio |
| `scripts/monitor.py` | Morning check: bounce guard, 92% inbox gate (never pulls more than half), replies that need a person; report only unless `--act` |
| `scripts/attio_*.py` | Attio as the CRM: fields, import, cool-down, nightly score and route, deals |
| `templates/reference/subject_lines.md` | Subject-line patterns that fit the rules (lower case, question-mark, open loop, event, problem, quarter) and the ones left out on purpose |
| `templates/frameworks/` | Email shapes as plain-English slots (`{one dated fact ...}`), each with the evidence it rests on; pick one with `copy.framework` |
| `templates/briefs/` | Agent briefs: grading, signal research, insights, persona copy |
| `.claude/skills/` | `market-map`, `signal-research`, `person-copy`, `deliverability`, `launch` and `replies` skills for Claude Code |

## Setup

```bash
git clone <this repo> && cd signal-outbound-stack
python -m pip install -r requirements.txt && python -m crawl4ai.install  # or: crawl4ai-setup
npm install -g deepline && deepline setup                            # Deepline CLI (pay as you go)
cp .env.example .env                                                  # add your own keys (TREG_TOKEN at minimum)
cp config/client.example.json config/client.json                      # describe your client
python scripts/render_briefs.py
```

Open the folder in Claude Code and ask for what you want ("build a list for the new client", "find signals for these
companies"). The skills load on their own and run the scripts in order.

## A run, by hand

```bash
python scripts/source_companies.py count                     # free: how big is the market?
python scripts/source_companies.py search --max-usd 1
python scripts/source_companies.py select
python scripts/site_fetch.py --workers 5
python scripts/qualify_batches.py --all                      # then grading agents on runs/<run>/briefs/qualify.md
python scripts/merge.py                                      # A/B domains -> runs/<run>/approved.csv
python scripts/hiring_signals.py --input runs/<run>/approved.csv --max-usd 0.5
# signal-research agents on runs/<run>/briefs/research.md, then a human reviews every signal
python scripts/find_people.py --approved runs/<run>/approved.csv
python scripts/merge.py
python scripts/clean_people.py names && python scripts/clean_people.py verify --max-usd 1   # drop LEFT / NO_PROFILE
python scripts/find_emails.py --input runs/<run>/leads_master.csv --max-usd 2
python scripts/merge.py && python scripts/mv_verify.py --input runs/<run>/leads_master.csv --label primary
python scripts/person_research.py                            # dossiers for reviewed companies
# insight agents, then persona copy agents, then:
python scripts/copy_check.py
python scripts/attio_leads.py setup && python scripts/attio_leads.py import-run && python scripts/attio_score.py
python scripts/inbox_health.py                               # every inbox OK before launch
python scripts/seed_test.py --sequence config/sequence.json --inboxes <ids> --send   # then LOOK at the seeds
python scripts/monitor.py --act                              # every weekday morning, before the send window
python scripts/replies.py --attio                            # replies that need a person; positives to the CRM
```

All output for a run goes to `runs/<run>/`, which is git-ignored, as are `.env` and your client configs.

## Rules the kit enforces or assumes
- Grade before you pay for people or emails. No credits on a company nobody has looked at.
- Every paid script takes a dollar cap and logs what each call actually cost.
- Name the provider; never use a "routed" endpoint that can bill a miss at every provider it tries.
- Only verifier "ok" emails are sent. No catch-alls. Never guess an address from a name pattern.
- A signal is real only if someone opened the page and saw the date. A person reviews every signal before copy.
- Could-not-read is its own verdict, never counted as "no".
- Copy states facts and asks one question. It never judges the prospect's business.

## Status
Scripts compile and the free steps run on the example config. The paid calls are written against each provider's
documented request and response shapes but have not yet been run end to end; run each paid step on 5 rows first and
open the output before a full run.

## Requirements
Python 3.10+, crawl4ai, Node (for the Deepline CLI). Keys: treg (required), MillionVerifier; optional Explorium,
Apify, Tavily, Firecrawl, Exa, Attio.

## License
MIT
