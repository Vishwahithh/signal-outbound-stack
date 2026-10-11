"""render_briefs.py - turn the agent brief templates (templates/briefs/*.md) into this run's briefs, filled from the client
config: client, archetype, grade definitions, signal windows as real dates from today, proof list, copy rules.

Agents are then pointed at runs/<run>/briefs/<name>.md. Re-run whenever the config changes or a day has passed
(signal windows are absolute dates).

    python scripts/render_briefs.py
"""
import datetime, re

from common import ROOT, config, run_dir


def values(cfg):
    today = datetime.date.today()
    a, c = cfg["archetype"], cfg["client"]
    sig = []
    for s in cfg["signals"]:
        since = "open now" if not s["window_days"] else "dated on or after " + (today - datetime.timedelta(days=s["window_days"])).isoformat()
        sig.append(f"- {s['id']} {s['name']}: {since}. Not a signal: {s['not_a_signal']}.")
    return {
        "TODAY": today.isoformat(), "RUN": cfg["run"], "RUN_DIR": f"runs/{cfg['run']}",
        "CLIENT": c["name"], "OFFER": c["offer"], "WHY_SIGNALS": c["why_signals_matter"], "SENDER": c["sender"],
        "ARCHETYPE": f"{a['name']}: {a['description']}",
        "DISQUALIFIERS": "\n".join(f"- {d}" for d in a["disqualifiers"]),
        "GRADES": "\n".join(f"- {k}: {v}" for k, v in cfg["grading"].items()),
        "SIGNALS": "\n".join(sig),
        "SIGNAL_IDS": "|".join(s["id"] for s in cfg["signals"]),
        "PRIORITY": " > ".join(cfg["signal_priority"]),
        "PROOF": "\n".join(f"   {p['id']}: {p['line']}\n      use when the insight is about: {p.get('solves') or p.get('fits', '')}"
                           + (f"\n      fixed, must appear exactly: {', '.join(p['facts'])}" if p.get("facts") else "")
                           for p in cfg["copy"]["proof"]),
        "COPY_RULES": "\n".join(f"- {r}" for r in cfg["copy"]["rules"]),
        "VOC_BANK": cfg["copy"].get("voc_bank", "config/voc_bank.md"),
    }


def main():
    cfg = config()
    v = values(cfg)
    out = run_dir(cfg, "briefs")
    for t in sorted((ROOT / "templates" / "briefs").glob("*.md")):
        text = re.sub(r"\{\{(\w+)\}\}", lambda m: v.get(m.group(1), m.group(0)), t.read_text(encoding="utf-8"))
        left = re.findall(r"\{\{\w+\}\}", text)
        (out / t.name).write_text(text, encoding="utf-8")
        print(out / t.name, "(unfilled: %s)" % ", ".join(left) if left else "")


if __name__ == "__main__":
    main()
