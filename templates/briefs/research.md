# Company research: website truth check + dated signals

Client: {{CLIENT}}, which sells {{OFFER}}.
Target: {{ARCHETYPE}}
We contact a company ONLY when something has just happened that makes the client's offer a live question:
{{WHY_SIGNALS}}. Today is {{TODAY}}.

## Input
A CSV batch (path in your prompt) from {{RUN_DIR}}/research/: domain, company, country, headcount, grade,
pricing_style, what_they_sell, signal_hint, last_funding_date, email_domain, domain_mismatch.
Each company's own pages are cached at {{RUN_DIR}}/cache/web/<domain>.json ("text" = the pages joined in order;
"ok": false = we could not read it).

## For EACH company, in order
0. If domain_mismatch is true, confirm which site is really this company (the email domain is often the true one) and
   use that site from here on; put it in "site_used".
0b. If pricing_style is NO_PRICING_PAGE or COULD_NOT_READ, open the homepage and follow any "Pricing" / "Plans" link
   in the menu. Many companies keep pricing at /plans, /pricing-plans or a subdomain.
1. Read the cached JSON. If "ok" is false, fetch the homepage once before deciding COULD_NOT_READ. Decide from the
   WEBSITE (it beats the database when they disagree): sells, b2b, status (ACTIVE | ABSORBED | DEAD), final_grade.
2. Signals. Look for events inside these windows:
{{SIGNALS}}
   Where to look: (a) the cached news and blog text; (b) at most 3 web searches per company, going down this ladder
   ONLY when the step above returned nothing useful: free search first (TinyFish), then Tavily news, then Firecrawl
   news (last 6 months), then Exa (best for LinkedIn posts: new leaders, AI launches). (c) signal_hint is the
   database's guess and is ONLY a lead to check, never evidence.
   A signal counts ONLY if you OPENED the source page and the page itself shows the fact and a date inside the window.
   Search-snippet dates are NOT evidence: they are wrong often enough to matter. If the page will not open, record
   verified "could-not-read". Never infer.
3. Append ONE JSON line to the output file immediately (save as you go):

{"domain": "...", "site_used": "...", "final_grade": "A|B|DROP", "pricing_url": "... or null", "sells": "...",
 "b2b": "B2B|MIXED|B2C", "status": "...", "hq_seen": "<country>|unknown",
 "signals": [{"type": "{{SIGNAL_IDS}}", "fact": "one plain sentence, facts only", "date": "YYYY-MM-DD", "url": "...",
              "verified": "has|has-not|could-not-read"}],
 "best_signal": "<id>|none", "reason": "<= 20 words on the fit verdict"}

## Rules
- Facts only. Never judge the company's pricing or strategy as good or bad.
- A few minutes per company. If nothing qualifies inside the window, signals = [] and best_signal = "none": that is a
  normal, useful answer.
- Priority if several: {{PRIORITY}}.
- When the batch is done, reply only with counts per sells verdict and per best_signal.
