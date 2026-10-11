"""copy_check.py - deterministic gate for persona copy before any human reads it.

Reads runs/<run>/copy/*.jsonl (one JSON line per person, the shape in templates/briefs/persona_copy.md) and the
dossiers in runs/<run>/dossiers/. Checks per email: 55-90 words; no links or domains, em dashes, exclamation marks or
banned phrases; the chosen proof line present verbatim (proof list from the client config); every why_now fact has a
date and a source; a month name or one of the person's own quoted phrases actually appears in the email; subject 2-4
words; LinkedIn note under 200 characters with no pitch words; the person exists in the dossier; greeting "Hi <name>,".

    python scripts/copy_check.py ["*.jsonl"]     -> PASS/FAIL per person, writes runs/<run>/copy/copy_check.csv
"""
import csv, json, re, sys

from common import config, jl, run_dir

BANNED = ["congrat", "impressive", "great ", "exciting", "i hope this", "quick question", "i imagine", "i suspect", "my guess",
          "hope you", "just checking", "reaching out", "touch base", "leverage", "synerg", "i'm curious", "i am curious", "i noticed"]
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
PITCH = ["call", "outline", "help you", "offer", "sent you", "my email", "free"]


def words(s):
    return re.findall(r"[A-Za-z0-9'+%.]+", s or "")


def check(r, dossier, proof):
    f = []
    e = r.get("email_1") or ""
    n = len(words(e))
    if not 55 <= n <= 90:
        f.append(f"length {n}")
    if re.search(r"https?://|www\.|\.(com|io|ai|co\.uk|co)\b", e):
        f.append("link/domain")
    if "—" in e or "–" in e or "!" in e:
        f.append("dash/exclamation")
    low = e.lower()
    f += [f"banned '{b.strip()}'" for b in BANNED if b in low]
    pid = r.get("proof_id")
    if pid is not None:
        if pid not in proof:
            f.append("proof_id")
        elif proof[pid].get("facts"):
            miss = [x for x in proof[pid]["facts"] if x.lower() not in low]   # wording free, facts exact
            if miss:
                f.append("proof facts missing: " + ", ".join(miss))
        elif proof[pid]["line"] not in e:
            f.append("proof not verbatim")
    wn = r.get("why_now") or []
    if not wn or any(not (x.get("date") and x.get("source")) for x in wn):
        f.append("why_now undated/unsourced")
    if not any(m in low for m in MONTHS) and not any(q and q.lower() in low for q in (r.get("own_words") or [])):
        f.append("no dated fact or quote in email")
    sw = len(words(r.get("subject") or ""))
    if not 2 <= sw <= 4:
        f.append(f"subject {sw} words")
    li = r.get("li_note") or ""
    if len(li) >= 200 or any(p in li.lower() for p in PITCH):
        f.append("li_note length/pitch")
    pr = dossier.get("primary") or {}
    names = {f"{pr.get('first_name') or ''} {pr.get('last_name') or ''}".strip()} | {p["name"] for p in dossier.get("buying_group", [])}
    who = str(r.get("name") or "").lower().strip()
    if not who or not any(n and (who in n.lower() or n.lower() in who) for n in names):
        f.append("person not in dossier")
    if not re.match(r"Hi [A-Z][\w'.-]+,", e):
        f.append("greeting")
    return f


def main():
    cfg = config()
    proof = {p["id"]: p for p in cfg["copy"]["proof"]}
    copy_dir, dossiers = run_dir(cfg, "copy"), run_dir(cfg, "dossiers")
    pattern = next((a for a in sys.argv[1:] if not a.startswith("--") and not a.endswith(".json")), "*.jsonl")
    rows = []
    for r in jl(copy_dir / pattern):
        if r.get("skipped"):
            rows.append({"domain": r.get("domain"), "name": r.get("name"), "result": "SKIP", "issues": r["skipped"]}); continue
        dp = dossiers / f"dossier_{r.get('domain')}.json"
        if not dp.exists():
            rows.append({"domain": r.get("domain"), "name": r.get("name"), "result": "FAIL", "issues": "no dossier"}); continue
        issues = check(r, json.loads(dp.read_text(encoding="utf-8")), proof)
        rows.append({"domain": r["domain"], "name": r.get("name"), "result": "PASS" if not issues else "FAIL", "issues": "; ".join(issues)})
    with open(copy_dir / "copy_check.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["domain", "name", "result", "issues"]); w.writeheader(); w.writerows(rows)
    for r in rows:
        print(f"{r['result']:4} {str(r['domain']):24} {str(r['name']):26} {r['issues']}")
    print(f"\n{sum(r['result'] == 'PASS' for r in rows)} pass / {sum(r['result'] == 'FAIL' for r in rows)} fail / "
          f"{sum(r['result'] == 'SKIP' for r in rows)} skipped")


if __name__ == "__main__":
    main()
