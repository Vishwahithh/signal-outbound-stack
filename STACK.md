# The data stack: what each tool is for, and what it costs

Prices are list prices from treg and Deepline in October 2026. Re-check before a big run: they change. Every paid
script logs what each call really cost to `runs/<run>/cache/spend.jsonl`.

## The layer: what replaces Clay

| Tool | Role | Why |
|---|---|---|
| **Deepline** | the workflow layer: waterfalls, provider comparison, Plays | runs as local scripts inside the pipeline, pay as you go, credits last 12 months |
| **treg** | one token for thousands of provider endpoints, called by their own id | the cheapest single calls; reports the settled cost per call |
| Clay, hosted all-in-ones | not used | the table lives in their app, priced per month; this kit keeps the table in code |

## By stage

### 1. TAM
| Tool | Cost | Notes |
|---|---|---|
| Icypeas company search (treg) | ~$0.0004 / company | industry, headcount, revenue, type, location, keyword; `count` is free |
| Apollo company search (treg or own key) | $0.026 / page | per page, not per company |
| National registries (e.g. Companies House) | free | good for dated triggers in one country |

### 2. ICP filter
| Layer | Tool | Cost |
|---|---|---|
| Firmographics | comes with the TAM search | free |
| Technographics | read from the homepage (crawl4ai); Tomba via treg on a shortlist | free / ~$0.009 per domain |
| Demographics (who buys) | `contacts.title_include` / `personas` in the config | free |
| Fit | Claude agents reading each company's own site | $0 |

### 3. Signals
| Tool | Cost | Notes |
|---|---|---|
| LinkedIn job postings (Apify harvestapi via treg) | $0.001 / job + $0.001 / title searched | `hiring_signals.py` |
| Explorium events (funding, launches, new execs) | ~2 credits ≈ $0.08 / company | `person_research.py --explorium-events` |
| Funding feed (getleadsio via treg) | free | |
| LinkedIn posts in the buyer's own words | see stage 5 | the strongest signals, segment-specific |

### 4. Company research
crawl4ai (free) -> Tavily (~$0.008 / search) -> Firecrawl (~$0.001 / page) -> Exa (~$0.006 / search), escalating only
on failure. For sites that block everything, a scraping API (ZenRows, Crawlbase) as a last step.

### 5. People
| Job | Tool | Cost |
|---|---|---|
| Who works there, by title | QuickEnrich discovery (treg) | free, no emails |
| By seniority and department | Explorium prospects | ~$0.04 / person |
| Still at the company, same role | HarvestAPI profile (treg) | ~$0.004 / person |
| Their posts | tikhub / fetchin via treg, Bright Data, Apify | ~$0.001-0.002 / call |

### 6. Score and write
Claude. The insight pass scores 3 company and 3 person insights with evidence and confidence; copy is written from the
one chosen. No paid LLM API.

### 7. Contact data
| Order | Tool | Cost per find | Observed hit rate |
|---|---|---|---|
| 1 | Kitt AI (treg) | $0.005, verified | ~39% |
| 2 | QuickEnrich (treg) | ~$0.005 | ~31% |
| 3 | Icypeas (Deepline) | $0.014 | - |
| verify | MillionVerifier | ~$0.002 | drop catch-alls |
| phone | AI Ark ($0.026) / Dropleads ($0.054) via treg | per find | only for people who replied yes |

Hit rates are treg's measured numbers across all its users, not yours. Run the same 50 people through each finder
before trusting any order.

## What 100 companies cost (data only)

Assumptions: pull 1,000 companies to keep 100; the email waterfall finds ~65% (unmeasured until your own test);
Claude work is $0; fixed costs not included.

| Step | 1 person / company | 3 people / company |
|---|---|---|
| TAM + ICP | $0.40 | $0.40 |
| Signals, cheap (jobs + funding feed) | $0.10 | $0.10 |
| Signals, rich (Explorium events) | $8 | $8 |
| Company research | $0-3 | $0-3 |
| Find people | $0 | $0 |
| LinkedIn check + posts | $0.30 | $0.90 |
| Email find | ~$0.50 | ~$1.50 |
| Verify | ~$0.15 | ~$0.45 |
| **Total, cheap signals** | **~$1.50-4.50** | **~$3.50-6.50** |
| Total, rich signals | ~$9.50-12.50 | ~$11.50-26 |
| + phones for everyone | +$3-7 | +$9-21 |
| + phones for yeses only (~10) | +$0.50-1 | +$0.50-1 |

Data is cents per person. Inboxes, the sequencer and the LinkedIn tool are most of the bill.

## Never
- treg's routed `treg.*` endpoints: they try providers in turn and some bill every miss. `providers.py` refuses them.
- PredictLeads, on either layer. `providers.py` refuses it.
- Guessed addresses (first.last@ from a name). No find means no email.
