# signal-outbound-stack

Signal-based B2B outbound. Read PIPELINE.md first: the order and the gates are the product.

- Client specifics live only in the config (`config/client.json` or `--config <file>`). Scripts and skills stay generic;
  never hard-code a client, a person or a key in them.
- Keys come from `.env` (see `.env.example`). Never print, log or commit them.
- Run output goes to `runs/<run>/` (git-ignored). Briefs for agents: `python scripts/render_briefs.py`.
- Judgement work (grading, signal research, copy) is done by agents reading the text, never by keyword scripts.
  Sample-check every agent batch before using it.
- Paid calls go through scripts/providers.py (treg or Deepline) with a --max-usd cap; never a routed treg.* endpoint,
  never PredictLeads.
- Grade before paying for people or emails. Verifier "ok" only. Never guess emails. A person reviews every signal before copy.
- Nothing is sent to a prospect without the operator's explicit go-ahead.
