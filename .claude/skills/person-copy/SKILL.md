---
name: person-copy
description: Research each decision-maker's professional footprint (buying group, their own recent LinkedIn posts, the company's own site, the reviewed signal) and write hyper-personal, research-grounded copy per person - email one, a LinkedIn note and a call opener - then gate it with a deterministic checker and a blind prospect-eye score. Use this whenever the user wants persona-level or multithreaded copy, "Twain-style" research-to-copy, emails to several people at one company, copy that uses what the prospect has said or posted, or asks to make outbound feel researched rather than templated.
---

# Person research to copy

Stage 6 of PIPELINE.md, after signal review and email verification. Signal copy (templates/briefs/copy.md) writes one
email per company on the event; this writes one per PERSON, grounded in what that person has said and in the decision
they now own.

## 0. Clean and verify people first
`python scripts/clean_people.py names` then `python scripts/clean_people.py verify`. Only verdict OK (and CHECK rows a
human has read) go on. A person who has left is the most expensive mistake in persona copy: the best-researched
email in the test went to someone who had moved company.

## 1. Dossiers
- Build `runs/<run>/research/people_companies.json` from the reviewed signals and verified contacts (fields in the
  docstring of `scripts/person_research.py`; `company_linkedin` is the `linkedin_company` column of leads_master.csv, from the company source).
- `python scripts/person_research.py --max-companies 3` first and open one dossier yourself: is the buying group the
  right company, are the posts theirs? Then run the rest. Cost is cents per company; it resumes if stopped.
- Professional footprint only. Never add personal-life sources (family, home, personal social accounts): wrong data
  for B2B and outside legitimate interest.

## 2. Phrase bank (once per client)
`config/voc_bank.md`, format in `config/voc_bank.example.md`. It is what makes the question sound like a peer; build
it before the first copy run and reuse it.

## 3. Insights, then copy (two separate passes)
- `python scripts/render_briefs.py`.
- Insight agents on `runs/<run>/briefs/insights.md`, about 5 companies each, writing `runs/<run>/insights/<batch>.jsonl`:
  3 company + 3 person insights, each with dated evidence, confidence (verified / inferred / guess) and relevance
  0-10, then one chosen insight, one angle and a tier per person (personal / company / skip). No emails here.
- Copy agents on `runs/<run>/briefs/persona_copy.md`, reading ONLY the insights file (not the dossiers), writing
  `runs/<run>/copy/<batch>.jsonl`. Keeping the writer away from the raw research stops it drifting to stock lines.
- `python scripts/copy_check.py` and send every FAIL back to its agent. Common fails: subject over 4 words, an
  undated fact, a proof whose fixed facts were changed.
- The insights file doubles as the call prep sheet for whoever takes the meeting.

## 4. Blind score before anyone sends
Give a reviewer agent each email plus only what the recipient knows (their company, role, posts) and ask, as the
recipient: does it feel researched by a person (0-10), does it sound human, would you reply, which line gives it away.
Rewrite anything under 6. Lessons from scoring rounds:
- Opening on the company's own press release reads as a news feed. Open on the implication or the person's own words.
- Mechanics questions (tiers, discounts, margins) are either public or confidential; ask about the decision instead.
- Same four beats for everyone at one company: one forwarded email exposes the rest.
- The best-scoring emails asked a question only someone doing that job would ask, in their own words.
- Insight-first (v4) beat writing straight from the dossier (v3) in a shuffled blind test of the same 29 people:
  researched 7.1 vs 6.6, "would not reply" 7 vs 12. Human-sounding stayed level (5.5): the remaining template
  tells are the fixed proof sentence and rotating closers, so vary those next.
- Then proof matched to the problem it solved, told in the writer's own words with the facts fixed, and a close
  drawn from the email's own question (v4.1) beat v4 on the same 27 people: human 5.1 -> 6.2, "would not reply"
  11 -> 4, won 16 / lost 5 / tied 6, both reviewers agreeing. What still reads as merge: a case from a distant
  sector with no bridge sentence, one-block emails, and the sender's name twice.

Then the client reads a sample before launch, as with every other stage.
