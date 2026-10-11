"""person_research.py - one dossier per company for research-grounded, persona-level copy: the buying group, the
primary contact's own recent LinkedIn posts, what the company says on its own site, and the signal already verified.

Input: runs/<run>/research/people_companies.json, a list of objects, one per company that survived signal review:
  {"domain", "company", "country", "headcount", "company_linkedin",
   "first_name", "last_name", "title", "email", "linkedin",              <- the primary contact
   "signal_type", "signal_fact", "signal_date", "signal_url"}             <- the reviewed signal
Missing fields are fine; the dossier just has less in it.

Sources:
  cached website pages   runs/<run>/cache/web/<domain>.json (from site_fetch.py)          free
  buying group           Apify harvestapi/linkedin-company-employees, short profiles        ~$0.004 / profile
  LinkedIn posts         Apify harvestapi/linkedin-profile-posts, last 3 months             ~$0.002 / post
                         (primary contact and every c-suite member of the buying group)
  company events         Explorium /v2/businesses/events, optional (--explorium-events)    ~2 credits / company

APIFY_TOKENS in .env can hold several comma-separated tokens; runs rotate across them and skip one that hits a limit.
Save-as-you-go: runs/<run>/dossiers/dossier_<domain>.json; a company already done is skipped, so a rerun resumes.

Scope: professional footprint only (role, company, what they publish under their own name). Do not add personal-life
sources; it is the wrong data for B2B outreach and a legal problem under GDPR/PECR legitimate interest.

    python scripts/person_research.py [--input FILE] [--max-companies 10] [--explorium-events]
"""
import argparse, datetime, json, time, urllib.error, urllib.request

from common import config, env, run_dir

EVENTS = ["new_product", "new_funding_round", "new_investment", "merger_and_acquisitions", "executive_joined_company",
          "hiring_in_sales_department", "hiring_in_finance_department", "new_office", "new_partnership", "ipo_announcement"]
TITLES = ["Chief Executive Officer", "CEO", "Founder", "Chief Revenue Officer", "Chief Financial Officer", "Chief Product Officer",
          "Chief Commercial Officer", "Chief Operating Officer", "VP Sales", "Vice President Sales", "VP Finance", "VP Product",
          "Commercial Director", "Head of Revenue"]
NOT_BUYER = ("investor", "advisor", "adviser", "board", "former", "intern", "assistant", "engineer", "account executive",
             "product manager", "developer", "analyst", "specialist", "coordinator")
SENIOR = ("chief", "ceo", "cfo", "cro", "cpo", "coo", "cco", "founder", "president", "vp", "vice president", "head of", "director")
CSUITE = ("chief", "cfo", "cro", "cpo", "coo", "cco")


def site_pages(cache, domain):
    """Split the cached site text back into its pages: {"/": ..., "/pricing": ...}, 3000 chars each."""
    p = cache / f"{domain}.json"
    if not p.exists():
        return {}
    rec = json.loads(p.read_text(encoding="utf-8"))
    if not rec.get("ok"):
        return {}
    text, out, pos = rec.get("text") or "", {}, 0
    for pg in rec.get("pages", []):
        path = "/" + pg["url"].split("/", 3)[3] if pg["url"].count("/") >= 3 else ""
        out[path.rstrip("/") or "/"] = text[pos:pos + pg["chars"]][:3000]
        pos += pg["chars"] + 3
    return out


def same_company(a, b):
    a, b = a.lower().replace(",", "").replace(".", "").strip(), b.lower().replace(",", "").replace(".", "").strip()
    for suf in (" inc", " ltd", " limited", " llc", " systems", " software", " technologies", " ai", " corp"):
        a, b = a.removesuffix(suf), b.removesuffix(suf)
    return bool(a) and (a == b or a.startswith(b + " ") or b.startswith(a + " "))


TOKENS, _turn = [], [0]


def apify(actor, body):
    """Run one actor on the next token in rotation and return its dataset; on a usage/limit error try the next token."""
    for _ in range(len(TOKENS)):
        tok = TOKENS[_turn[0] % len(TOKENS)]; _turn[0] += 1
        try:
            req = urllib.request.Request(f"https://api.apify.com/v2/acts/{actor}/runs?token={tok}", data=json.dumps(body).encode(),
                                         method="POST", headers={"Content-Type": "application/json"})
            r = json.loads(urllib.request.urlopen(req, timeout=60).read())["data"]
            for _ in range(120):
                time.sleep(5)
                st = json.loads(urllib.request.urlopen(f"https://api.apify.com/v2/actor-runs/{r['id']}?token={tok}", timeout=30).read())["data"]
                if st["status"] in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                    break
            return json.loads(urllib.request.urlopen(f"https://api.apify.com/v2/datasets/{r['defaultDatasetId']}/items?token={tok}&clean=1", timeout=60).read())
        except urllib.error.HTTPError as e:
            print("   apify token skipped:", e.code)
    return []


def posts(url):
    items = apify("harvestapi~linkedin-profile-posts", {"targetUrls": [url], "maxPosts": 10, "postedLimit": "3months", "includeReposts": False})
    out = []
    for p in items:
        pa = p.get("postedAt") or {}
        out.append({"date": (pa.get("date") if isinstance(pa, dict) else str(pa))[:10], "url": p.get("linkedinUrl") or p.get("url"),
                    "likes": (p.get("engagement") or {}).get("likes"), "text": (p.get("content") or "")[:1500]})
    return out


def explorium_events(c):
    k = env("EXPLORIUM_API_KEY")

    def api(path, body):
        req = urllib.request.Request("https://api.explorium.ai" + path, method="POST", data=json.dumps(body).encode(),
                                     headers={"api_key": k, "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
        try:
            return json.loads(urllib.request.urlopen(req, timeout=120).read())
        except urllib.error.HTTPError as e:
            print("   explorium", e.code); return {}

    m = api("/v2/businesses/match", {"businesses_to_match": [{"name": c["company"], "domain": c["domain"]}]})
    bid = ((m.get("matched_businesses") or [{}])[0]).get("business_id")
    if not bid:
        return []
    since = (datetime.date.today() - datetime.timedelta(days=180)).isoformat() + "T00:00:00Z"
    out = []
    for e in api("/v2/businesses/events", {"event_types": EVENTS, "business_ids": [bid], "timestamp_from": since}).get("output_events") or []:
        d = e.get("data") or {}
        out.append({"type": e.get("event_name"), "date": (e.get("event_time") or "")[:10], "title": d.get("title") or d.get("product_name") or d.get("full_name"),
                    "snippet": (d.get("snippet") or "")[:400], "url": d.get("link")})
    return out


def research(c, cache, out_dir, with_events):
    d = c["domain"]
    out = out_dir / f"dossier_{d}.json"
    if out.exists():
        print(" ", d, "already done"); return
    dossier = {"domain": d, "company": c.get("company"), "country": c.get("country"), "headcount": c.get("headcount"),
               "pulled_at": datetime.date.today().isoformat(),
               "verified_signal": {k: c.get(k) for k in ("signal_type", "signal_fact", "signal_date", "signal_url")},
               "primary": {k: c.get(k) for k in ("first_name", "last_name", "title", "email", "linkedin")},
               "site": site_pages(cache, d), "events": [], "buying_group": [], "primary_posts": []}
    if c.get("company_linkedin"):
        for p in apify("harvestapi~linkedin-company-employees", {"companies": [c["company_linkedin"]], "profileScraperMode": "Short ($4 per 1k)",
                                                                 "maxItems": 10, "jobTitles": TITLES}):
            pos = [x for x in (p.get("currentPositions") or []) if same_company(x.get("companyName") or "", c.get("company") or "")]
            pos = [x for x in pos if not any(w in (x.get("title") or "").lower() for w in NOT_BUYER)
                   and any(w in (x.get("title") or "").lower() for w in SENIOR)]
            if pos:
                dossier["buying_group"].append({"name": f"{p.get('firstName', '')} {p.get('lastName', '')}".strip(),
                                                "title": " / ".join(x.get("title") or "" for x in pos), "linkedin": p.get("linkedinUrl"), "posts": []})
    if c.get("linkedin"):
        dossier["primary_posts"] = posts(c["linkedin"])
    first, last = (c.get("first_name") or "").lower(), (c.get("last_name") or "").lower()
    for m in dossier["buying_group"]:
        is_primary = first and last and first in m["name"].lower() and last in m["name"].lower()
        if any(k in m["title"].lower() for k in CSUITE) and not is_primary and m.get("linkedin"):
            m["posts"] = posts(m["linkedin"])
    if with_events:
        dossier["events"] = explorium_events(c)
    out.write_text(json.dumps(dossier, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {d}: buying group {len(dossier['buying_group'])} | primary posts {len(dossier['primary_posts'])} | "
          f"exec posts {sum(len(m['posts']) for m in dossier['buying_group'])} | events {len(dossier['events'])}")


def main():
    cfg = config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--input", default=str(run_dir(cfg, "research") / "people_companies.json"))
    ap.add_argument("--max-companies", type=int, default=10)
    ap.add_argument("--explorium-events", action="store_true")
    a = ap.parse_args()
    TOKENS.extend(t.strip() for t in env("APIFY_TOKENS").split(",") if t.strip())
    comps = json.load(open(a.input, encoding="utf-8"))[: a.max_companies]
    cache, out_dir = run_dir(cfg, "cache", "web"), run_dir(cfg, "dossiers")
    print("companies:", len(comps), "| apify tokens:", len(TOKENS))
    for c in comps:
        research(c, cache, out_dir, a.explorium_events)


if __name__ == "__main__":
    main()
