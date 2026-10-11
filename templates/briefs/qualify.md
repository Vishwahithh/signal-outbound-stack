# Grade companies from their own website (no web searching)

Client: {{CLIENT}}, which sells {{OFFER}}.
Target: {{ARCHETYPE}}
This step decides who is worth researching and paying to contact. Today is {{TODAY}}.

## Input
A batch file (path in your prompt): {{RUN_DIR}}/qualify/batch_NNN.md. Each company block has the domain, name, country,
headcount, the database's industry label, the contact's title, and the text of its homepage, pricing and about pages.
`site_read: NO` means we could not read the site.

READ THE TEXT. Do not write a script that matches keywords: every verdict must come from you reading that company's
pages. A keyword classifier is the one failure this step exists to prevent. Do not browse the web in this step.

## Output
For EACH company append ONE JSON line to the output file straight away (save as you go, never buffer):

{"domain": "...",
 "sells": "B2B_SOFTWARE|B2B_TECH_PRODUCT_PLUS_SERVICES|AGENCY_DEVSHOP_RESELLER|B2C|NOT_TECH|COULD_NOT_READ",
 "what_they_sell": "<= 15 words, plain, from the page",
 "customers": "B2B|MIXED|B2C",
 "pricing_style": "PUBLIC_TIERS|PER_USER|USAGE_OR_CREDITS|CONTACT_SALES_ONLY|NO_PRICING_PAGE|ONE_OFF_OR_PROJECT|COULD_NOT_READ",
 "status": "ACTIVE|ABSORBED|DEAD",
 "qualify": "A|B|C|DROP",
 "reason": "<= 20 words"}

## Grades
{{GRADES}}

Disqualifiers (grade DROP):
{{DISQUALIFIERS}}

- "Acquired by" or "backed by" a private-equity firm or a larger group while the company still sells its own product
  under its own brand is NOT a drop: it is a new-owner signal. Set status ACTIVE, grade the product as usual, and put
  "acquired by X" in the reason.
- COULD_NOT_READ sites get qualify "C" and reason "site not readable" (they are re-read with paid tools later).
  A site we could not read is not evidence of anything; never grade it DROP for that.

When the batch is done, reply only with counts per qualify grade and per pricing_style.
