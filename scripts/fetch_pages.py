"""fetch_pages.py - read a company's website, free tool first, paid only on failure.

Two kinds of failure look the same and only one is real:
  dead domain    the host does not resolve. No tool fixes this, so we never pay to confirm it.
  bot-blocked    the site is fine but refused a local headless browser. Tavily / Firecrawl / Exa fetch from their own
                 infrastructure and usually get through. These skew towards larger, better-run companies, so writing
                 them off is the expensive mistake.

Ladder (stop at the first usable result; escalate only on failure, never for quality; at most ONE paid call per tier):
    1. crawl4ai   free   local headless browser
    2. Tavily     paid   /extract
    3. Firecrawl  paid   /v1/scrape
    4. Exa        paid   /contents

    from fetch_pages import fetch_site
    site = fetch_site("example.com", paths=["", "/pricing"])
    # {"ok": True, "text": ..., "pages": [{"url", "tool", "chars"}], "tool": "crawl4ai", "escalation_reason": ""}

    python scripts/fetch_pages.py --domains example.com [--no-paid]
"""
import argparse, asyncio, json, re, socket, sys, urllib.parse, urllib.request

from common import env

DEFAULT_PATHS = ["", "/about", "/pricing"]
MIN_CHARS = 220  # below this a "200 OK" is a soft-404, a cookie wall or a splash page


def _clean(md):
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", md or "")          # images
    md = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", md)              # link -> its text
    md = re.sub(r"(?i)\b(accept|manage) (all )?cookies?\b.{0,120}", " ", md)
    return re.sub(r"\s+", " ", md).strip()


def _resolves(host):
    if not host:
        return False
    for h in (host, host[4:] if host.startswith("www.") else "www." + host):
        try:
            socket.getaddrinfo(h, 443)
            return True
        except OSError:
            continue
    return False


async def _crawl4ai_many(urls, timeout_ms=15000):
    from crawl4ai import AsyncWebCrawler
    out = {}
    async with AsyncWebCrawler(verbose=False) as c:
        for u in urls:
            try:
                r = await c.arun(url=u, page_timeout=timeout_ms)
                t = _clean(str(getattr(r, "markdown", "") or ""))
                if len(t) >= MIN_CHARS:
                    out[u] = t
            except Exception:
                pass
    return out


def _post(url, body, headers, timeout=60):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _tavily(url):
    k = env("TAVILY_API_KEY", required=False)
    if not k:
        return ""
    for res in _post("https://api.tavily.com/extract", {"urls": [url]}, {"Authorization": "Bearer " + k}).get("results") or []:
        t = _clean(res.get("raw_content") or "")
        if len(t) >= MIN_CHARS:
            return t
    return ""


def _firecrawl(url):
    k = env("FIRECRAWL_API_KEY", required=False)
    if not k:
        return ""
    j = _post("https://api.firecrawl.dev/v1/scrape", {"url": url, "formats": ["markdown"], "onlyMainContent": True},
              {"Authorization": "Bearer " + k})
    t = _clean((j.get("data") or {}).get("markdown") or "")
    return t if len(t) >= MIN_CHARS else ""


def _exa(url):
    k = env("EXA_API_KEY", required=False)
    if not k:
        return ""
    for res in _post("https://api.exa.ai/contents", {"urls": [url], "text": True}, {"x-api-key": k}).get("results") or []:
        t = _clean(res.get("text") or "")
        if len(t) >= MIN_CHARS:
            return t
    return ""


PAID = [("tavily", _tavily), ("firecrawl", _firecrawl), ("exa", _exa)]


def fetch_site(domain, paths=None, max_pages=5, allow_paid=True, timeout_ms=15000):
    """crawl4ai for every path first; escalate per SITE (homepage only) only if crawl4ai got nothing at all."""
    paths = paths or DEFAULT_PATHS
    base = domain if domain.startswith("http") else "https://" + domain.strip().rstrip("/")
    urls = [base + p for p in paths][:max_pages]
    got = asyncio.run(_crawl4ai_many(urls, timeout_ms))
    pages = [{"url": u, "tool": "crawl4ai", "chars": len(got[u])} for u in urls if u in got]
    text = " \n\n".join(got[u] for u in urls if u in got)[:24000]
    if len(text) >= MIN_CHARS:
        return {"ok": True, "text": text, "pages": pages, "tool": "crawl4ai", "escalation_reason": ""}
    if not allow_paid:
        return {"ok": False, "text": "", "pages": [], "tool": "none", "escalation_reason": "crawl4ai empty; paid disabled"}
    host = urllib.parse.urlparse(base).hostname or ""
    if not _resolves(host):
        return {"ok": False, "text": "", "pages": [], "tool": "none",
                "escalation_reason": "dns: %s does not resolve (no paid calls made)" % host}
    why = "crawl4ai returned <%d chars across %d urls" % (MIN_CHARS, len(urls))
    for name, fn in PAID:
        try:
            t = fn(base)
        except Exception as e:
            why += "; %s error %s" % (name, type(e).__name__)
            continue
        if t:
            return {"ok": True, "text": t[:24000], "pages": [{"url": base, "tool": name, "chars": len(t)}],
                    "tool": name, "escalation_reason": why}
        why += "; %s empty" % name
    return {"ok": False, "text": "", "pages": [], "tool": "none", "escalation_reason": why}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--domains", nargs="+", required=True)
    ap.add_argument("--no-paid", action="store_true")
    ap.add_argument("--config")
    a = ap.parse_args()
    for d in a.domains:
        r = fetch_site(d, allow_paid=not a.no_paid)
        print("  %-28s %-10s %5d chars  %s" % (d[:27], r["tool"], len(r["text"]), r["escalation_reason"][:60]))
