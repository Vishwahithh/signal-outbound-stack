"""firecrawl_refetch.py - re-read the websites of grade-C ("site not readable") companies with Firecrawl so they can be
graded again on real text instead of a cookie banner or a bot block.

Per domain: scrape the homepage (markdown + links), follow the site's own Pricing/Plans link if there is one and scrape
it too (max 2 Firecrawl calls per company). Overwrites runs/<run>/cache/web/<domain>.json in the shape fetch_pages
writes and logs to cache/refetch_index.jsonl (resumable). Keep --workers at 2: Firecrawl rate-limits (429) above that.

    python scripts/firecrawl_refetch.py [--grade C] [--workers 2]
Then re-pack those domains and re-grade them; write those results to qualify/rc_out_*.jsonl so merge.py prefers them.
"""
import argparse, csv, json, re, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from common import config, env, run_dir

K = env("FIRECRAWL_API_KEY")


def scrape(url, links=False):
    body = {"url": url, "formats": ["markdown"] + (["links"] if links else []), "onlyMainContent": False, "timeout": 45000}
    req = urllib.request.Request("https://api.firecrawl.dev/v1/scrape", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + K})
    for attempt in range(6):
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=90).read()).get("data") or {}
            return (d.get("markdown") or ""), (d.get("links") or []), ""
        except urllib.error.HTTPError as e:
            if e.code == 429:  # plan rate limit: wait it out, do not count the site as unreadable
                time.sleep(15 + attempt * 10); continue
            return "", [], f"error HTTP{e.code}"
        except Exception as e:
            return "", [], f"error {type(e).__name__}"
    return "", [], "error rate-limited"


def one(domain, cache):
    home, links, err = scrape("https://" + domain, links=True)
    pages, text = [], ""
    if len(home) >= 300:
        home = home[:14000]
        pages.append({"url": "https://" + domain, "tool": "firecrawl", "chars": len(home)})
        text = home
        cand = sorted((u for u in links if re.search(r"/(pricing|plans|price)(/|$|\?|-)", u, re.I) and domain.split(".")[0] in u), key=len)
        if cand:
            pr, _, _ = scrape(cand[0])
            if len(pr) >= 200:
                pr = pr[:8000]
                pages.append({"url": cand[0], "tool": "firecrawl", "chars": len(pr)})
                text += " \n\n" + pr
    rec = {"domain": domain, "ok": bool(pages), "text": text, "pages": pages, "tool": "firecrawl",
           "escalation_reason": "" if pages else (err or "firecrawl returned no usable text")}
    (cache / f"{domain}.json").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return {"domain": domain, "ok": rec["ok"], "pricing_found": len(pages) > 1, "why": rec["escalation_reason"]}


def main():
    cfg = config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--grade", default="C")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--config")
    a = ap.parse_args()
    run, cache = run_dir(cfg), run_dir(cfg, "cache", "web")
    idx_path = cache.parent / "refetch_index.jsonl"
    rows = [r for r in csv.DictReader(open(run / "leads_master.csv", encoding="utf-8-sig")) if r["grade"] == a.grade]
    done = set()
    if idx_path.exists():
        done = {x["domain"] for x in (json.loads(line) for line in open(idx_path, encoding="utf-8")) if x["ok"] or not x["why"].startswith("error")}
    todo = [r["domain"] for r in rows if r["domain"] not in done]
    print("to refetch", len(todo))
    ok = 0
    with ThreadPoolExecutor(a.workers) as ex, open(idx_path, "a", encoding="utf-8") as idx:
        for i, f in enumerate(as_completed([ex.submit(one, d, cache) for d in todo]), 1):
            r = f.result(); ok += r["ok"]
            idx.write(json.dumps(r) + "\n"); idx.flush()
            if i % 25 == 0:
                print(f"  {i}/{len(todo)} ok {ok}")
    print("done", len(todo), "ok", ok)


if __name__ == "__main__":
    main()
