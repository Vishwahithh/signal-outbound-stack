# Email one, written on the signal

{{SENDER}} writes to the decision-maker at a company right after a dated, reviewed event.
Offer: {{OFFER}}.

Input: {{RUN_DIR}}/copy/batch.csv (company, first_name, title, signal_type, signal_fact, signal_date, what_they_sell).
Only signals that survived human review are in this file.

For each lead write four things and append one JSON line straight away to the output file:
{"domain": "...", "subject": "...", "opener": "...", "question": "...", "proof_id": 0}

1. opener: 12-28 words, the fact and the month, from signal_fact only. Example shape: "Saw that <company> launched
   <product> in <month>."
2. question: ONE sentence, 10-25 words, a genuine question about the specific new thing, naming it, that connects to
   the offer. Shapes that work:
   - launch: "Is <product> meant to pull customers up a tier, or will it be sold as an add-on of its own?"
   - funding: "With the round closed, is growth expected from new logos or from more revenue per existing customer?"
   - new owner: "Is <topic> part of the plan with the new owners, or staying as it is for now?"
   - new leader: "Is <topic> on the list for the first few months in the role?"
   Never imply they are doing something wrong. Never mention a number or detail you were not given. No "I'm curious",
   no "quick question". Do not repeat the opener's wording.
3. proof_id: the ONE proof closest to their business (numbers are fixed, never change them):
{{PROOF}}
4. subject: 2-4 words, lower case except names.

Rules:
{{COPY_RULES}}
Write every line yourself; no script or template code. A sample of the output is read by a prospect-eye reviewer and
by the client before anything is sent.
