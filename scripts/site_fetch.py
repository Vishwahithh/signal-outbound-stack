"""site_fetch.py - cache each company's own pages (homepage, pricing, news, blog, about) so grading and research agents
read saved text instead of browsing: cheaper, repeatable, and every verdict traces back to the text it came from.

Free first (crawl4ai). A site that returns nothing is recorded as could-not-read; pass --paid to rescue those with the
Tavily -> Firecrawl -> Exa ladder (one paid call per tier, homepage only). Keep --workers at 5 or below: at 8 the
headless browsers leaked and every page slowed to ~40 s.

    python scripts/site_fetch.py [--input runs/<run>/source/companies.csv] [--workers 5] [--paid]
Writes runs/<run>/cache/web/<domain>.json and appends a summary line to runs/<run>/cache/web_index.jsonl.
"""
import argparse, csv, json
from concurrent.futures import ProcessPoolExecutor, as_completed

from common import config, run_dir


def one(domain, paid, cache, paths):
    from fetch_pages import fetch_site
    try:
        r = fetch_site(domain, paths=paths, max_pages=len(paths), allow_paid=paid)
    except Exception as e:
        r = {"ok": False, "text": "", "pages": [], "tool": "none", "escalation_reason": f"error {type(e).__name__}"}
    (cache / f"{domain}.json").write_text(json.dumps({"domain": domain, **r}, ensure_ascii=False), encoding="utf-8")
    return {"domain": domain, "ok": r["ok"], "tool": r["tool"], "chars": len(r.get("text") or ""),
            "pages": [p["url"] for p in r.get("pages", [])], "why": r.get("escalation_reason", "")}


def main():
    cfg = config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(run_dir(cfg, "source") / "companies.csv"))
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--paid", action="store_true")
    ap.add_argument("--config")
    a = ap.parse_args()
    cache = run_dir(cfg, "cache", "web")
    index = cache.parent / "web_index.jsonl"
    paths = cfg.get("site_paths", ["", "/pricing", "/news", "/blog", "/about"])
    doms = [r["domain"] for r in csv.DictReader(open(a.input, encoding="utf-8-sig")) if r.get("domain")]
    done = set()
    if index.exists():
        for line in open(index, encoding="utf-8"):
            x = json.loads(line)
            if x["ok"] or not a.paid:
                done.add(x["domain"])
    todo = [d for d in dict.fromkeys(doms) if d not in done]
    print("to fetch", len(todo), "| already cached", len(done))
    ok = 0
    with ProcessPoolExecutor(a.workers) as ex, open(index, "a", encoding="utf-8") as idx:
        futs = [ex.submit(one, d, a.paid, cache, paths) for d in todo]
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            ok += r["ok"]
            idx.write(json.dumps(r) + "\n"); idx.flush()
            if i % 25 == 0:
                print(f"  {i}/{len(todo)} ok {ok}")
    print("done", len(todo), "ok", ok)


if __name__ == "__main__":
    main()
