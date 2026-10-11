"""qualify_batches.py - pack each fetched company's homepage, pricing and about text into compact batch files for the
grading agents, so an agent reads ~5k characters per company instead of 24k.

Pricing pages often open with 2k+ characters of navigation, so the pricing text is windowed to start just before the
first price-like token. Only companies whose site fetch has finished and that are not yet in a batch are packed.

    python scripts/qualify_batches.py [--size 40] [--all]
Writes runs/<run>/qualify/batch_NNN.md (+ the domain list in batch_NNN.txt). Without --all a final partial batch waits.
"""
import argparse, csv, json, re

from common import config, run_dir

CAP = {"": 2500, "/pricing": 2200, "/about": 800}


def price_window(t, cap):
    m = re.search(r"[£$€]\s?\d|per (user|seat|month)|/mo|/month|per year|contact sales|book a demo", t, re.I)
    start = max(0, m.start() - 500) if m else 0
    return t[start:start + cap]


def pages_of(rec):
    """fetch_site joins pages with ' \\n\\n' and records each page's length: split the text back into pages."""
    text, out, pos = rec.get("text") or "", {}, 0
    for p in rec.get("pages", []):
        n = p["chars"]
        path = "/" + p["url"].split("/", 3)[3] if p["url"].count("/") >= 3 else ""
        out[path.rstrip("/")] = text[pos:pos + n]
        pos += n + 3
    return out


def main():
    cfg = config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=40)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--config")
    a = ap.parse_args()
    out = run_dir(cfg, "qualify")
    cache = run_dir(cfg, "cache")
    meta = {r["domain"]: r for r in csv.DictReader(open(run_dir(cfg, "source") / "companies.csv", encoding="utf-8"))}
    packed = set()
    for t in out.glob("batch_*.txt"):
        packed |= set(t.read_text(encoding="utf-8").split())
    ready = []
    for line in open(cache / "web_index.jsonl", encoding="utf-8"):
        d = json.loads(line)["domain"]
        if d in meta and d not in packed and d not in ready:
            ready.append(d)
    start = len(list(out.glob("batch_*.txt")))
    stop = len(ready) if a.all else len(ready) - len(ready) % a.size
    for bi in range(0, stop, a.size):
        doms = ready[bi:bi + a.size]
        n = start + bi // a.size
        parts = []
        for d in doms:
            m = meta[d]
            rec = json.loads((cache / "web" / f"{d}.json").read_text(encoding="utf-8"))
            pg = pages_of(rec) if rec.get("ok") else {}
            body = "".join(f"--- page {p or '/'} ---\n{price_window(pg[p], CAP[p]) if p == '/pricing' else pg[p][:CAP[p]]}\n"
                           for p in CAP if p in pg)
            parts.append(f"=== {d} | {m['company']} | {m['country']} | {m['headcount']} staff | database industry: {m['industry']}\n"
                         f"site_read: {'yes' if rec.get('ok') else 'NO (' + rec.get('escalation_reason', '')[:80] + ')'}\n" + body)
        (out / f"batch_{n:03d}.md").write_text("\n".join(parts), encoding="utf-8")
        (out / f"batch_{n:03d}.txt").write_text("\n".join(doms), encoding="utf-8")
        print("batch", n, len(doms))


if __name__ == "__main__":
    main()
