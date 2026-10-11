"""replies.py - pull every reply on the live campaigns, sort it into a bucket, and say which ones need a person.

Buckets: POSITIVE / OTHER (a person reads it now) | OPT_OUT | OUT_OF_OFFICE | DEPARTED | AUTO_EMPTY

- Only the text the person wrote is classified. The thread quotes OUR email ("Not interested? Just say..."), and
  matching on the quote once turned every reply into an opt-out, so the quote is cut off first.
- A reply from mailer-daemon / postmaster / no-reply is a bounce whatever its text says (one was once filed as a yes).
- Nothing is assumed positive: anything that fits no rule is OTHER and goes to a person. Smartlead's own reply count
  includes out-of-office, so never report it as replies.
- An opt-out whose lead can still be emailed is flagged until it is blocked.
- With --attio, a new POSITIVE becomes an Attio deal at the first stage (config "crm.deal_stages"[0]).

Campaigns: config "sending.campaigns" (ids), else every ACTIVE / PAUSED / COMPLETED campaign whose name does not
contain SEED or TEST.

    python scripts/replies.py [--quiet] [--attio]
Writes runs/<run>/sending/reply_inbox.csv (all replies) and reply_state.json (seen replies, written atomically).
"""
import argparse, csv, json, os, re
from collections import Counter

from common import config, run_dir
from smartlead import api, paged

QUOTE_CUT = re.compile(r"\n\s*(from:|sent:|on .{5,90} wrote:|-{2,}\s*original message|>\s)|"
                       r"\bon (mon|tue|wed|thu|fri|sat|sun)\w*,? .{3,40} at \d", re.I)
OPT_OUT = re.compile(r"^\W*(stop|unsubscribe|remove)\b|\bstop (please|emailing|sending|contacting|now)\b|\bunsubscribe\b|"
                     r"\bremove me\b|\btake me off\b|\bdo not (contact|email)\b|\bdon'?t (contact|email)\b|\bnot interested\b|"
                     r"\bno thanks\b|\bno thank you\b|\bplease stop\b|\bopt[- ]out\b|\bnever email\b", re.I)
DEPARTED = re.compile(r"no longer (works|with|employed|at|connected)|has (now )?left (the )?(company|business|organi[sz]ation)|"
                      r"(have|has) left\b|mailbox is now closed|is not monitored|address is no longer|left the company", re.I)
OOO = re.compile(r"out of (the )?office|currently away|on (annual )?leave|on holiday|away from (my|the) (desk|office)|"
                 r"limited access to (my )?email|back in the office|will (be )?return|returning (on|monday|tuesday|wednesday|"
                 r"thursday|friday)|automatic reply|auto[- ]?reply|autoreply|on maternity|on paternity", re.I)
AUTOBOT = re.compile(r"received your request|answer bot|ticket (has been|number)|thank you for (contacting|your enquiry)|"
                     r"we will (get back|respond) to you within|"
                     r"identified as unsolicited|filter(s|ed)? cold emails|inbox zero", re.I)
POSITIVE = re.compile(r"happy to (receive|hear|see|take a look|chat|talk|have a look)|interested|send (it|me|over|across)|"
                      r"sounds (good|interesting)|tell me more|more (info|information|details)|let'?s (talk|chat|speak)|"
                      r"book(ed| a| some)? (a )?(call|time|slot|meeting)|call me|free (on|this|next|tomorrow)|"
                      r"how (much|does)|can you (send|share|explain)|\byes\b|please do\b|go ahead", re.I)
SYSTEM = ("mailer-daemon", "postmaster", "no-reply", "noreply")
LIVE = ("NOT_STARTED", "STARTED", "INPROGRESS", "IN_PROGRESS")


def to_text(h):
    t = re.sub(r"<style[^>]*>.*?</style>", "", h or "", flags=re.S | re.I)
    t = re.sub(r"<(br|/p|/div|/tr)[^>]*>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"[ \t]+", " ", t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">"))


def own_words(body):
    t = "\n" + to_text(body).strip()
    m = QUOTE_CUT.search(t)
    return re.sub(r"\s+", " ", t[:m.start()] if m else t).strip()


def classify(t):
    if len(t.strip()) < 3:
        return "AUTO_EMPTY"
    for name, rx, window in (("OPT_OUT", OPT_OUT, 300), ("DEPARTED", DEPARTED, None), ("OUT_OF_OFFICE", OOO, None),
                             ("AUTO_EMPTY", AUTOBOT, None), ("POSITIVE", POSITIVE, 400)):
        if rx.search(t[:window] if window else t):
            return name
    return "OTHER"


def campaigns(cfg):
    ids = (cfg.get("sending") or {}).get("campaigns") or []
    camps = [c for c in (api("GET", "/campaigns") or []) if isinstance(c, dict)]
    if ids:
        return [c for c in camps if c["id"] in ids]
    return [c for c in camps if c.get("status") in ("ACTIVE", "PAUSED", "COMPLETED")
            and not re.search(r"seed|test", c.get("name") or "", re.I)]


def collect(cfg):
    rows = []
    for c in campaigns(cfg):
        cid = c["id"]
        leads = {}
        for x in paged(f"/campaigns/{cid}/leads"):
            l = x.get("lead") or {}
            leads[(l.get("email") or "").lower()] = {"id": l.get("id"), "status": x.get("status"), "company": l.get("company_name") or "",
                                                      "name": f"{l.get('first_name') or ''} {l.get('last_name') or ''}".strip()}
        replied = {}
        for r in paged(f"/campaigns/{cid}/statistics"):
            if r.get("reply_time"):
                replied.setdefault(r["lead_email"].lower(), r["reply_time"])
        for email, rtime in replied.items():
            info, text, sender = leads.get(email, {}), "", ""
            if info.get("id"):
                h = api("GET", f"/campaigns/{cid}/leads/{info['id']}/message-history") or {}
                reps = [m for m in h.get("history", []) if m.get("type") == "REPLY"]
                if reps:
                    text, sender = own_words(reps[-1].get("email_body")), (reps[-1].get("from") or "").lower()
            bucket = "AUTO_EMPTY" if sender.split("@")[0] in SYSTEM else classify(text)
            rows.append({"campaign": c.get("name"), "campaign_id": cid, "email": email, "name": info.get("name", ""),
                         "company": info.get("company", ""), "reply_time": rtime, "bucket": bucket,
                         "lead_status": info.get("status") or "", "text": text[:400]})
    order = ["POSITIVE", "OTHER", "OPT_OUT", "OUT_OF_OFFICE", "DEPARTED", "AUTO_EMPTY"]
    return sorted(rows, key=lambda r: (order.index(r["bucket"]), r["reply_time"]))


def run(cfg, quiet=False, attio=False):
    out = run_dir(cfg, "sending")
    state_p = out / "reply_state.json"
    state = json.loads(state_p.read_text(encoding="utf-8")) if state_p.exists() else {}
    rows = collect(cfg)
    if rows:
        with open(out / "reply_inbox.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    new = [r for r in rows if f"{r['email']}|{r['reply_time']}" not in state]
    needs = [r for r in new if r["bucket"] in ("POSITIVE", "OTHER")]
    unblocked = [r for r in rows if r["bucket"] == "OPT_OUT" and r["lead_status"] in LIVE]
    if attio:
        from attio_crm import upsert_deal
        stage = ((cfg.get("crm") or {}).get("deal_stages") or ["Replied yes"])[0]
        for r in [x for x in needs if x["bucket"] == "POSITIVE"]:
            nm = (r["name"] or r["email"].split("@")[0]).split()
            upsert_deal({"company": r["company"] or r["email"].split("@")[1], "domain": r["email"].split("@")[1], "first": nm[0],
                         "last": " ".join(nm[1:]), "email": r["email"], "stage": stage, "source": "Email",
                         "next_action": "Reply within the hour with a time", "next_action_date": r["reply_time"][:10]},
                        (cfg.get("crm") or {}).get("owner_email"))
    for r in rows:
        state[f"{r['email']}|{r['reply_time']}"] = r["bucket"]
    tmp = state_p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1), encoding="utf-8")
    os.replace(tmp, state_p)                                   # atomic: an overlapping run never reads a half file
    lines = [f"NEW {r['bucket']}: {r['name']} <{r['email']}> {r['company']} | {r['text'][:200]}" for r in needs]
    lines += [f"OPT-OUT NOT BLOCKED: {r['email']} (status {r['lead_status']})" for r in unblocked]
    if not quiet:
        print(f"{len(rows)} replies: " + ", ".join(f"{k} {v}" for k, v in Counter(r["bucket"] for r in rows).most_common()))
    print("\n".join(lines) if lines else "no new replies need a person")
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--attio", action="store_true")
    ap.add_argument("--config")
    a = ap.parse_args()
    run(config(), a.quiet, a.attio)


if __name__ == "__main__":
    main()
