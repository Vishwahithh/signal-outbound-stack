"""monitor.py - the morning check on live campaigns: inbox gate, bounce guard, replies. Run it before the send window.

WHAT IT DOES, IN ORDER
  1. Bounce guard. Smartlead auto-pauses at its own threshold; as a backstop, an ACTIVE campaign with 50+ sends and a
     bounce rate at or above config "sending.bounce_pause_pct" (default 3) is paused and alerted.
  2. Inbox gate. Any inbox in an ACTIVE campaign with warmup reputation under "sending.rep_gate" (default 92) is taken
     out of that campaign; warmup stays on so it can recover, and it goes back in once it is at the gate again.
     Inboxes on "sending.never_domains" are always taken out. If the gate would remove more than half of a campaign's
     inboxes it removes none and alerts: that is a domain, DNS or provider problem, not one bad inbox.
  3. Replies. Runs replies.py and lists the ones that need a person (and opt-outs that are not blocked yet).
  4. Writes runs/<run>/sending/monitor/<date>.md and .json; with TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID set, sends a
     short summary.

WHAT IT NEVER DOES
  start a campaign, un-pause one it did not pause, send or answer any email, edit copy or leads, delete anything, spend
  credits. Those stay with the operator.

    python scripts/monitor.py            # report only: changes nothing (default)
    python scripts/monitor.py --act      # also pauses / pulls / re-adds as described above
Schedule it on weekdays about 20 minutes before the send window (cron or Windows Task Scheduler).
"""
import argparse, datetime as dt, json, os, urllib.parse, urllib.request

from common import config, env, run_dir
from smartlead import accounts, api, rep
import replies


def telegram(text):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return
    data = urllib.parse.urlencode({"chat_id": chat, "text": text[:3900]}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data=data), timeout=20)
    except Exception:
        pass


def main():
    cfg = config()
    s = cfg.get("sending") or {}
    gate, bounce_max, never = float(s.get("rep_gate", 92)), float(s.get("bounce_pause_pct", 3)), tuple(s.get("never_domains") or ())
    ap = argparse.ArgumentParser()
    ap.add_argument("--act", action="store_true")
    ap.add_argument("--config")
    a = ap.parse_args()
    env("SMARTLEAD_API_KEY")
    out = run_dir(cfg, "sending", "monitor")
    state_p = out / "state.json"
    state = json.loads(state_p.read_text(encoding="utf-8")) if state_p.exists() else {"pulled": {}, "paused": []}
    today = str(dt.date.today())
    accs = accounts()
    by_email = {x["from_email"]: x for x in accs.values()}
    actions, alerts, report = [], [], {"date": today, "campaigns": {}}
    for c in replies.campaigns(cfg):
        cid, name, status = c["id"], c.get("name"), c.get("status")
        an = api("GET", f"/campaigns/{cid}/analytics") or {}
        sent, bounced = int(an.get("sent_count") or 0), int(an.get("bounce_count") or 0)
        info = {"name": name, "status": status, "sent": sent, "bounced": bounced,
                "bounce_pct": round(100 * bounced / sent, 2) if sent else 0.0, "reply_count_incl_ooo": int(an.get("reply_count") or 0)}
        report["campaigns"][cid] = info
        if status == "ACTIVE" and sent >= 50 and info["bounce_pct"] >= bounce_max:
            alerts.append(f"{name}: bounce {info['bounce_pct']}% ({bounced}/{sent}) - {'PAUSED' if a.act else 'would pause'}")
            if a.act:
                api("POST", f"/campaigns/{cid}/status", {"status": "PAUSED"})
                state["paused"].append({"campaign": cid, "on": today})
                actions.append(f"paused {name}")
            continue
        if status != "ACTIVE":
            continue
        attached = [x for x in (api("GET", f"/campaigns/{cid}/email-accounts") or []) if isinstance(x, dict)]
        ids = {x["id"] for x in attached}
        burned = [accs[i] for i in ids if i in accs and never and accs[i]["from_email"].lower().endswith(never)]
        low = [accs[i] for i in ids if i in accs and accs[i] not in burned and rep(accs[i]) is not None and rep(accs[i]) < gate]
        if low and len(low) > len(ids) / 2:
            alerts.append(f"{name}: {len(low)} of {len(ids)} inboxes under {gate:.0f}% - not pulling, looks systemic (domains/DNS/provider)")
            low = []
        for x in burned + low:
            actions.append(f"{'pulled' if a.act else 'would pull'} {x['from_email']} from {name} (rep {rep(x)}%, warmup stays on)")
            state["pulled"][x["from_email"]] = {"campaign": cid, "on": today, "rep": rep(x)}
        if a.act and (burned or low):
            api("DELETE", f"/campaigns/{cid}/email-accounts", {"email_account_ids": [x["id"] for x in burned + low]})
        back = [e for e, p in state["pulled"].items() if p["campaign"] == cid and e in by_email
                and not (never and e.lower().endswith(never)) and (rep(by_email[e]) or 0) >= gate]
        for e in back:
            actions.append(f"{'re-added' if a.act else 'would re-add'} {e} to {name} (rep {rep(by_email[e])}%)")
        if a.act and back:
            api("POST", f"/campaigns/{cid}/email-accounts", {"email_account_ids": [by_email[e]["id"] for e in back]})
            for e in back:
                state["pulled"].pop(e)
        info["inboxes"] = {x["from_email"]: rep(accs.get(x["id"], x)) for x in attached}
    try:
        need = replies.run(cfg, quiet=True)
    except Exception as e:
        need = [f"replies failed: {str(e)[:200]}"]
    md = [f"# Monitor {today}{'' if a.act else ' (report only)'}", ""]
    for cid, i in report["campaigns"].items():
        md += [f"## {i['name']} ({cid}) - {i['status']}",
               f"- sent {i['sent']}, bounces {i['bounced']} ({i['bounce_pct']}%), Smartlead reply count {i['reply_count_incl_ooo']} (includes out-of-office)", ""]
    md += ["## Actions"] + ([f"- {x}" for x in actions] or ["- none"]) + ["", "## Alerts"] + ([f"- {x}" for x in alerts] or ["- none"])
    md += ["", "## Replies needing a person"] + ([f"- {x}" for x in need] or ["- none"])
    text = "\n".join(md)
    print(text)
    (out / f"{today}.md").write_text(text, encoding="utf-8")
    (out / f"{today}.json").write_text(json.dumps({**report, "actions": actions, "alerts": alerts, "replies": need}, indent=1, default=str), encoding="utf-8")
    if a.act:
        state_p.write_text(json.dumps(state, indent=1), encoding="utf-8")
    telegram("\n".join([f"Monitor {today}"] + [f"ALERT {x}" for x in alerts] + actions + need[:10]))


if __name__ == "__main__":
    main()
