# The pipeline: order, gates, and why each gate exists

One page. Each stage's detail lives in its skill under `.claude/skills/`. Never skip a gate: every one of them was
added after skipping it cost real money or a real domain.

```
0 SPEC        config/client.json: client, archetype, size, geo, disqualifiers, grades, signals + windows
1 SOURCE      companies via the data vendor's NATIVE filters (search is cheap; no emails revealed here)
2 SUPPRESS    customers, competitors, partners, everyone already contacted, CRM cool-down / do-not-contact
3 GRADE       market-map skill: read each company's own website, A / B / C / DROP     <- GATE 1: only A/B continue
4 SIGNAL      signal-research skill: dated, opened, human-reviewed                     <- GATE 2: no signal, no signal campaign
5 CONTACTS    people at A/B only (free discovery) -> LinkedIn check -> email waterfall -> MillionVerifier "ok" only          <- GATE 3: no catch-all, never guess
              small markets (ABM): 3-5 contacts per account (CEO, CRO, CFO, product lead)
6 COPY        opener on the event + one question about the specific new thing + one approved proof
              QA + a prospect-eye review of a sample                                     <- GATE 4: client approves samples
7 LAUNCH      inbox_health.py (warmup ON, reputation >= 92%) -> seed_test.py, read the seeds -> ramp   <- GATE 5
              hypothesis + kill rule written BEFORE the first send
8 CONVERT     booking link at the yes, same day; phone/text within 24h; LinkedIn connect
9 READ        monitor.py every morning + replies.py; hand-classify every reply; yes-rate by segment / signal / size; CRM sync, rescore, re-route
```

## Gates and the lessons behind them

| Gate | Rule | What happened without it |
|---|---|---|
| Spec check | Check the list against the named archetype before any spend | A run drifted to wrong size bands, any company age and PE-owned firms while the brief said otherwise |
| 1 Grade before reveal | No email credits on ungraded companies, even when credits are about to expire | ~1,460 credits spent revealing first: only 17% landed on usable target contacts, 44% on companies outside the market |
| Native filters | Read the vendor's full filter reference first (business model, revenue, headcount, hiring, news) | Broad industry labels were mostly services firms ("IT Services" ~67%) |
| Agents | Judgement work on a strong model, never the cheapest; "read it yourself, no keyword script"; sample-check every batch | A small model wrote a keyword classifier instead of reading the pages |
| Missing data | Verdicts are three-valued: has / has-not / could-not-read. The third is excluded from every percentage | "93% show no price" turned out to be measuring our own crawler |
| 2 Human signal review | A person reads every "verified" signal before copy | 20% of agent-verified signals were useless: absorbed companies, waitlists, integrations, partner "commitments" |
| 3 Contacts | Verifier "ok" only; no catch-all; never build first.last@ from a name | Guessed and catch-all addresses bounce, and bounces burn sending domains |
| Clean + verify people | Names cleaned before they reach a merge field; every contact checked against their own LinkedIn: still at the company, same role. LEFT and NO_PROFILE never get copy | Vendor data said CPO at the company; LinkedIn showed he had left for another firm months earlier, and his email was one of the two best-scored. Taglines and ".io" in names print verbatim and get auto-linked |
| Person research | Professional footprint only (role, company, their own posts); open one dossier by hand before the batch | Copy without the person's own words scored 4.6/10 with a prospect-eye reviewer; with dossiers, gate and a phrase bank it reached 6.3; picking one scored insight before writing raised "feels researched" again (6.6 to 7.1, blind and shuffled); matching proof to the problem and closing on the email's own question raised "sounds human" 5.1 to 6.2 |
| 4 Copy | Facts only; never judge the prospect's business; proof only from the approved list, matched by the problem it solved, not the sector label; no links/pixel in email one | Tracking pixel and auto-linked domains put a seed test in spam |
| Launch | Kill rule written before the first send | Without one, a dead campaign runs for weeks |
| Infra | One inbox belongs to one client; 3 inboxes per domain; domains owned by the operator; warmup checked ON via API | Warmup was silently off on 10 new inboxes |

## Market size decides the motion
- Under ~10k reachable contacts: ABM. Tier the accounts, go deep, multithread, watch for triggers.
- 10k-100k: automated signal-based outbound; cover the whole market on a ~90-day rotation (CRM cool-down = 90 days).

## Cost discipline
- Free first: crawl4ai and free search before Tavily, Firecrawl or Exa; escalate only on failure, one paid call per tier.
- Every paid run has a cap (`--max-credits`, `--min-balance`). Check the balance before and after.
- Before the first paid use of any new tool, read its API and billing docs and run a small test while watching the balance.
