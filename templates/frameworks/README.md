# Frameworks: email shapes written as plain-English slots

A framework is an email written as fixed text plus slots in curly braces. Each slot says, in plain English, what
belongs there:

```
Hi {first name},

{one dated fact about them from the last 90 days, with the month}

{one question about a decision that fact creates, that only this person can answer}
```

Pick one per run in `config/client.json` under `copy.framework` (the file name without `.md`). `render_briefs.py`
puts it into the persona copy brief, and the copy agent writes every email in that shape.

## How slots are filled

1. **From the research only.** Every slot that states a fact takes it from the insights pass (`strategy.use`): the
   fact, its date and its source. Nothing is stated that the research does not hold.
2. **NOT FOUND is a valid answer.** If no fact fits a required slot, the person is skipped, not padded. A guessed
   slot is worse than no email.
3. **The shape guides; the email is written whole.** The agent writes the email in one pass, in the framework's order,
   then reads it aloud. Slots are never filled one at a time and stitched together.
4. **The copy gate still runs.** `scripts/copy_check.py` checks length, banned phrases, proof lines and that every
   dated fact traces back to the research.

## Why rule 3 exists

We tested filling each part separately (trigger, then problem, then ask) against writing the whole email from the
same research. Two blind reviewers, writer hidden, every email fact-checked against the dossier:

| Method | Score |
|---|---|
| Whole email, one pass | 71 to 74 |
| Parts written separately, best of three per part, joined by an editor | 64 |
| Parts written separately, joined as written | 44 |

Each part read well on its own. Joined, the email lost its thread: the fact in line one stopped being the reason for
the question in line two, and the middle filled with general lines that could go to anyone.

## Writing your own

- One fact slot, one question slot, one ask slot is the core. Add slots only when the email needs them.
- Write each slot as an instruction a careful colleague could follow: what to put there, where it comes from, how long.
- Say what the slot must not do ("never describe their pricing", "no number unless the research states it").
- The ask is something the reader can answer with one word. Every positive reply we have recorded was a yes to a
  free, written thing about their company. None was an answer to a question.
- Put a status line at the top of every framework: what evidence it rests on. "Untested" is a valid status.

## The library

| File | Use for | Evidence |
|---|---|---|
| `written_outline.md` | Email one, any segment | Real replies: the only shape with positive replies at volume |
| `their_words.md` | Email one, when the person has posted in the last 90 days | Blind review winner |
| `dated_launch.md` | Email one, when the company shipped or announced something dated | Blind review winner |
| `their_desk.md` | Email one, to someone who shares or does not own the decision | Blind review, tied to the role rule |
| `years_in_business.md` | Email one, owner-run firms 8+ years old with no recent event | Untested |
| `matched_case.md` | Email two | Real replies: one yes came on this touch |
| `second_angle.md` | Email two, when no case fits | Untested |
| `last_note.md` | Final touch | Real data: third touches produced no positive replies in any campaign, so keep it short or skip it |
