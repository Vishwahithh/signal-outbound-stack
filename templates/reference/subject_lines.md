# Subject lines: patterns to use, and the ones this kit leaves out

The subject line decides whether email one gets opened. These patterns come from a cold-email swipe file, filtered
against this kit's rules: email one states facts and asks one question, never pretends to a relationship that does not
exist, and never reads like marketing. Copy agents pick a pattern here; `copy_check.py` checks the result (1-4 words,
no all-caps word, no sales words).

## Defaults
- **All lower case** (names keep their capitals). Plain often beats flashy: `new project`, `next report`,
  `this forecast`.
- **1-4 words.** A name or company with a question mark counts as one and is fine. It should read like an
  internal email from a colleague, not a newsletter.
- **Tied to this email's insight.** The subject points at the thing the email is about, so the open is not a trick.

## Patterns that fit the rules

| Pattern | Examples | Use when |
|---|---|---|
| Company or name with a question mark | `Acme?` / `Mike?` | short, safe default; works for any insight |
| Company + topic, or two merge fields | `Acme - question` / `{{company}} {{topic}}` / `{{topic}} for {{department}}` | the insight names a specific thing (a launch, a market, a hire) |
| Open loop (curiosity) | `seen this?` / `dealing with this?` / `open to this?` / `know about this?` | the email's first line answers what "this" is, straight away |
| Problem question | `bandwidth in ops?` / `pricing the new tier?` | the insight is a problem they have said or shown, not one you assume |
| The event itself | `the analytics add-on` / `the berlin office` | there is a dated, verified signal |
| Time of year | `q4 plans` / `q1 pricing` | the question is about planning for that quarter |
| Referral | `you or {{referral name}}?` | multithreading: asking who owns the problem |

## Calls to action (end of email, not the subject)
`worth a chat?` / `think this could help?` / `open to a different take on {{process}}?` / `worth exploring, or no?` /
`curious to see how?`. In this kit the close is written from the email's own question, so treat these as shapes, not
lines to paste: a stock closer repeated across emails was the second thing blind reviewers spotted.

## Left out on purpose

| Pattern | Why it is out |
|---|---|
| Cut-off word cliffhangers (`the 3 tips you can steal when g`) | reads as a trick or a broken email; trust lost before the first line |
| `remember us from your Amazon days?` | implies a relationship that does not exist unless it really does; use only for a true past contact |
| Hobby or personal facts from LinkedIn (football team, family) | person research here is professional footprint only; personal details read as surveillance |
| ALL CAPS (`URGENT`) | spam-filter flag |
| Sales words: offer, discount, free, deal, cost | marketing tone; also spam-filter weight. (A pricing consultancy can still say "pricing" when it is the topic.) |
| Emoji, exclamation marks, "Re:" or "Fwd:" on a first email | spam weight, or a fake thread |
