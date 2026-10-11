# Persona copy: one email per person, written from ONE chosen insight

An insights pass ({{RUN_DIR}}/briefs/insights.md) has already decided what matters about each person. You write from
its choice only, and you do not open the dossier: that keeps you from drifting back to a generic line.
Sender: {{SENDER}}. Offer: {{OFFER}}. Tone: a peer who has done this many times. Plain, short, confident. Never
grateful, salesy or clever. Today is {{TODAY}}.

## Input per person: one line of {{RUN_DIR}}/insights/*.jsonl
Use ONLY: name, title, persona, the chosen best insight (best.from + best.index) with its evidence and own_words, the
angle, the tier, read_first. Ignore the other insights; they lost.
- tier "personal": write from the best insight and the angle.
- tier "company": a plainer email from the company's highest-relevance verified/inferred insight; no claims about
  the person, no own_words.
- tier "skip": output {"domain", "name", "skipped": "tier skip"} only.

## The email (email_1): 55-80 words, "Hi <first>," signed with the sender's first name
1. Line one: the insight, said as a peer would say it, with the dated fact inside it as a clause (month named). If
   own_words exist, use them exactly, in quotes, as "you wrote"/"you said" with the month. Never "<Company>
   launched <X> in <month>." as a sentence on its own.
2. The question: the angle, in your own words. One sentence. Something only this person can answer.
3. Who the sender is, one clause naming THEIR sector, and at most one case from the proof list, chosen because the
   PROBLEM it solved ("use when") matches the chosen insight. Sector only breaks ties. Tell it in your own sentence,
   the way one peer tells another; the fixed facts (descriptor, numbers) must appear exactly and nothing may be added.
   No "Recent work," lead-in. If no case's problem matches, proof_id null and no metric: a wrong-fit case reads as
   template and costs more than none. No two siblings at one company get the same case.
4. Close with a short offer tied to this email's question ("If it helps, I can show how they split the free and paid
   parts."), under 15 words, different at every sibling. Never a closer from a fixed list: rotated stock closers were
   the second thing blind reviewers spotted.
- Lead into the case through the shared problem ("The same question came up with an enterprise platform business:
  ..."), never a bare "One software business got +6.8%". A case from a distant sector with no bridge reads as merge.
- Three short paragraphs (insight + question / who + case / close), never one block. No "I'm <sender>": the email is
  signed, and the name twice reads as assembled.
- Siblings at one company: different opening, question, proof and ask. One forwarded email must not expose the rest.
- Hyper-personal test for every line: could it go to anyone at another company unchanged? Then rewrite it.
- Accuracy: every fact matches the evidence it comes from; "so", "which means", "now that" only for a real cause.

## Subject
1-4 words, lower case except names, tied to the chosen insight. Pick a pattern from
templates/reference/subject_lines.md (name or company with a question mark, company + topic, open loop that line one
answers, the event itself). Siblings at one company get different subjects. Never the patterns it lists as out.

## The strategy block is binding
- tier "skip" or fit "out": output only {"domain", "name", "skipped": "<why>"}.
- Every number, date and quoted phrase in the email appears verbatim in strategy.use. Nothing else is stated as fact,
  and no guesses about how they price.
- Nothing from strategy.avoid. Match strategy.tone.
- The sender line is strategy.sender_claim, verbatim or shorter. If the proof's sector differs from theirs, bridge on
  the shared problem ("the same question came up with a SaaS business"), never a claim to work in their sector.
- If owns_pricing is not "yes", ask about what they own; the close may ask once, plainly, who owns the pricing call.

## Structure and proof (won three blind rounds of autoresearch, checked against the full research by a fact-checker)
- Line one carries ONE fact: one date, at most one product name, at most one quote. Other facts are dropped.
- No sentence over 25 words, no semicolons, no sentence joining two facts. At most two of their product, tier or plan
  names; a price ladder is named end to end or not at all. Never count their things ("four offerings").
- Never link two facts the sources do not link (a quote was not written "when" a launch happened unless both dates say so).
- Proof is opt-in: a case goes in only if it solved the very problem the email asks about, at most one email in three
  across a batch. Stated as one plain sentence of fact (descriptor + what was done + the number, exactly as the proof
  list), never "the same question came up with...", "had the same", "faced the same", and nothing added about the case
  (how they chose, how they framed it) in the close. When proof is dropped, the sender line stands alone.
- No claims about the sender's wider experience: no "other teams/platforms", no "usually / tends to / the test I use".
- A low-friction close tied to the question works: "Reply 'yes' and I'll send a one-page sketch of both options."

## Hard rules
{{COPY_RULES}}
- no links or domain-shaped text, no em dashes, no exclamation marks, no praise ("impressive", "great",
  "exciting"), no "congrats", no "I noticed", no "I hope", no "quick question", no "I imagine/suspect/my guess", no
  numbers about them beyond the evidence, never describe or judge their prices or business.

## Proof cases (client-approved; match by the problem solved, keep the fixed facts exact)
{{PROOF}}

## Output: one JSON line per person, appended to {{RUN_DIR}}/copy/<your batch>.jsonl
{"domain": "...", "name": "...", "title": "...", "persona": "...", "tier": "...", "insight_used": "...",
 "why_now": [{"fact": "...", "date": "YYYY-MM-DD", "source": "..."}], "own_words": ["..."], "proof_id": 0,
 "subject": "1-4 words, lower case except names", "email_1": "...", "li_note": "under 200 chars, no pitch",
 "skipped": null}
why_now = the chosen insight's evidence. Write every line yourself. Then run `python scripts/copy_check.py` and fix
every FAIL before a reviewer reads anything.
