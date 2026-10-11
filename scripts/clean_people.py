"""clean_people.py - make every contact safe to print and true before copy: clean names, clean titles, and check each
person against their own LinkedIn profile (still at the company? same role the data vendor says?).

Two steps, run in order on the lead master (runs/<run>/leads_master.csv by default). Both add columns and never
overwrite the vendor's originals, so a human can compare.

  names    free, no API. Adds:
           company_clean   name as people say it: no emoji, tagline, "(UK)", "Ltd", ".io" glued on, "| B Corp" badge.
                           CamelCase, lower-case styling, "Group", "UK" and "&" are left alone: they are the real name.
           first_clean / last_clean   "JOHN" -> "John", no "PhD", "MBA", "(he/him)", emoji. "McDonald", "van der" kept.
           title_clean     the role without the LinkedIn banner ("CEO at Acme | Speaker | Investor" -> "CEO")
           name_flag       OK | CHECK (title is not a buyer, e.g. assistant, advisor, board) | DROP (acquisition named in
                           the company name: "Acme - now part of Bigco")
  verify   HarvestAPI LinkedIn profile, ~$0.004 per profile, through treg (--backend treg, default: no 10-item cap) or
           the same scraper on Apify (--backend apify, APIFY_TOKENS rotated, free plans capped at 10 per run). Adds:
           li_title, li_company, li_role_started, company_check (same | different | not_on_linkedin),
           title_check (same | same_role | different | no_current_role), verdict (OK | CHECK | LEFT | NO_PROFILE)
           LEFT means the role at this company has an end date or LinkedIn shows another current employer: do not send.
           Raw responses are cached in runs/<run>/cache/linkedin_profiles.jsonl, so a rerun only pays for new people.

    python scripts/clean_people.py names [--input FILE]
    python scripts/clean_people.py verify [--input FILE] [--max 50] [--backend treg|apify] [--max-usd 1]
"""
import argparse, csv, json, re, time, urllib.error, urllib.request

from common import config, env, run_dir

EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍™®©]")
ACQUIRED_IN_NAME = re.compile(r"\bnow\s+(?:part of\s+)?[A-Z]|\bpart of\b|\ban?\s+[A-Z][\w&'.-]*\s+company\b|\bacquired\b|\bmerged\b", re.I)
CREDENTIALS = re.compile(r",?\s*\b(?:PhD|MBA|CPA|ACA|ACCA|CFA|FCA|MSc|BSc|MA|BA|Dr|Prof|Jr|Sr|II|III)\b\.?", re.I)
PRONOUNS = re.compile(r"\s*\((?:he|she|they)/\w+\)", re.I)
NOT_BUYER = re.compile(r"\bassociate\b|\bassistant\b|\bintern\b|\badvis[eo]r\b|\bboard\b|\binvestor\b|\bformer\b|\bex-|"
                       r"\bretired\b|\btrustee\b|\bmentor\b|\bcoach for\b|\bfractional\b", re.I)
OWNER = re.compile(r"founder|owner|managing director|chief|\bceo\b|\bcfo\b|\bcro\b|\bcoo\b|\bcpo\b|\bcco\b|president", re.I)
STOP = {"ltd", "limited", "plc", "llp", "inc", "llc", "group", "holdings", "uk", "the", "and", "software", "systems", "solutions",
        "technologies", "technology", "services", "international", "company", "co", "global", "digital", "ai", "io", "corp"}
BUCKETS = [("ceo", r"\bceo\b|chief executive|managing director|\bmd\b|\bpresident\b"), ("founder", r"founder|co-?owner|\bowner\b"),
           ("cfo", r"\bcfo\b|chief financial|finance director|head of finance|vp,? finance"),
           ("commercial", r"\bcco\b|\bcro\b|chief (commercial|revenue|sales|customer|growth)|sales director|commercial director|head of sales|vp,? sales"),
           ("coo", r"\bcoo\b|chief operating|operations director"),
           ("product", r"\bcpo\b|chief product|head of product|vp,? product"),
           ("cto", r"\bcto\b|chief (technology|technical|information)|technical director"), ("chair", r"\bchair")]


def company_clean(n):
    n = EMOJI.sub("", n or "").strip()
    n = re.split(r"\s*[|·•]\s*", n)[0]                 # "Acme | B Corp"
    n = re.sub(r"\s*[:;]\s.*$", "", n)                           # "Acme: the pricing platform"
    n = re.sub(r"\s+[-–—]\s+\S.*$", "", n)             # "Acme - Effective Brand Experience"
    for _ in range(2):                                           # "Acme (UK) Ltd": suffixes in either order
        n = re.sub(r"\s*,?\s*\b(?:Ltd|Limited|LLP|PLC|Inc|LLC|GmbH|Corp)\.?\s*$", "", n, flags=re.I)
        n = re.sub(r"\s*\((?:UK|US|USA|EU|[A-Z]{2,5})\)\s*$", "", n)  # "Acme (UK)"
    n = re.sub(r"\.(?:io|ai|com|co|net|org|co\.uk)$", "", n, flags=re.I)  # a name written as a domain gets auto-linked
    n = re.sub(r"\bUk\b", "UK", n)
    return re.sub(r"\s{2,}", " ", n).strip(" ,-&.")


def person_clean(n):
    n = PRONOUNS.sub("", EMOJI.sub("", n or ""))
    n = CREDENTIALS.sub("", n).strip(" ,.")
    if n.isupper() or n.islower():                               # only fix names typed in one case
        n = "-".join(p[:1].upper() + p[1:].lower() for p in n.split("-"))
        n = re.sub(r"\bMc([a-z])", lambda m: "Mc" + m.group(1).upper(), n)
        n = re.sub(r"\bO'([a-z])", lambda m: "O'" + m.group(1).upper(), n)
    return re.sub(r"\s{2,}", " ", n).strip()


def title_clean(t):
    t = EMOJI.sub("", t or "").strip()
    t = re.split(r"\s*[★☆|•]\s*", t)[0]           # keyword banners
    t = re.sub(r"\s+(?:at|@)\s+\S.*$", "", t)                     # "CEO at Acme"
    t = re.sub(r"\s+[-–—]\s+.{8,}$", "", t)              # "MD, Acme - Engineering Better..."
    t = re.sub(r"\s*/\s*", " / ", t)
    return re.sub(r"\s{2,}", " ", t).strip(" ,-/&|")


def toks(s):
    return {t for t in re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split() if len(t) >= 3 and t not in STOP}


def buckets(t):
    return {b for b, rx in BUCKETS if re.search(rx, (t or "").lower())}


def norm(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


ABBR = [(r"\bsvp\b", "senior vice president"), (r"\bevp\b", "executive vice president"), (r"\bvp\b", "vice president"),
        (r"\bceo\b", "chief executive officer"), (r"\bcfo\b", "chief financial officer"), (r"\bcro\b", "chief revenue officer"),
        (r"\bcpo\b", "chief product officer"), (r"\bcoo\b", "chief operating officer"), (r"\bcco\b", "chief commercial officer"),
        (r"\bmd\b", "managing director"), (r"\bmgmt\b", "management"), (r"\bco founder\b", "cofounder"), (r"\band\b", " ")]


def tnorm(t):
    """Title compare: 'SVP, Product Management' == 'Senior vice president, product management'."""
    t = norm(t).replace("-", " ")
    for rx, full in ABBR:
        t = re.sub(rx, full, t)
    return " ".join(t.split())


def read(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write(path, rows):
    tmp = path.with_suffix(".csv.tmp")
    cols = list(dict.fromkeys(k for r in rows for k in r))
    with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    tmp.replace(path)


def names(rows):
    changed = 0
    for r in rows:
        raw = r.get("company") or ""
        r["company_clean"] = company_clean(raw)
        r["first_clean"], r["last_clean"] = person_clean(r.get("first_name")), person_clean(r.get("last_name"))
        r["title_clean"] = title_clean(r.get("title"))
        if ACQUIRED_IN_NAME.search(raw):
            r["name_flag"] = "DROP"
        elif NOT_BUYER.search(r["title_clean"]) and not (OWNER.search(r["title_clean"]) and not re.search(r"associate|assistant|deputy|former|ex-", r["title_clean"], re.I)):
            r["name_flag"] = "CHECK"
        else:
            r["name_flag"] = "OK"
        if (r["company_clean"], r["first_clean"], r["last_clean"], r["title_clean"]) != (raw, r.get("first_name"), r.get("last_name"), r.get("title")):
            changed += 1
            print(f"  {raw[:30]:30} -> {r['company_clean'][:24]:24} | {(r.get('title') or '')[:34]:34} -> {r['title_clean'][:28]:28} {r['name_flag']}")
    print(f"\n{len(rows)} contacts, {changed} changed, {sum(r['name_flag'] == 'CHECK' for r in rows)} CHECK, {sum(r['name_flag'] == 'DROP' for r in rows)} DROP")


def apify_profiles(tokens, urls):
    body = json.dumps({"profileScraperMode": "Profile details no email ($4 per 1k)", "queries": urls}).encode()
    for tok in tokens:
        try:
            req = urllib.request.Request(f"https://api.apify.com/v2/acts/harvestapi~linkedin-profile-scraper/runs?token={tok}",
                                         data=body, method="POST", headers={"Content-Type": "application/json"})
            run = json.loads(urllib.request.urlopen(req, timeout=60).read())["data"]
            for _ in range(180):
                time.sleep(5)
                st = json.loads(urllib.request.urlopen(f"https://api.apify.com/v2/actor-runs/{run['id']}?token={tok}", timeout=30).read())["data"]
                if st["status"] in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                    break
            return json.loads(urllib.request.urlopen(f"https://api.apify.com/v2/datasets/{run['defaultDatasetId']}/items?token={tok}&clean=1", timeout=120).read())
        except urllib.error.HTTPError as e:
            print("  apify token skipped:", e.code)
    return []


def treg_profiles(cfg, urls, max_usd):
    """Same HarvestAPI profile data the Apify actor returns, one call per person, via treg."""
    from providers import Budget, BudgetExceeded, treg
    b, out = Budget(cfg, max_usd=max_usd), []
    for u in urls:
        try:
            st, r = treg(b, "harvestapi.linkedin.user.profile.main", query={"url": u, "main": "true"})
        except BudgetExceeded as e:
            print(" ", e); break
        el = (r.get("element") or (r.get("elements") or [None])[0]) if isinstance(r, dict) else None
        out.append({**el, "_query": u} if isinstance(el, dict) else {"error": f"http {st}", "_query": u})
    print(f"  treg spent ${b.spent:.4f}")
    return out


def slug(u):
    m = re.search(r"linkedin\.com/in/([^/?#]+)", u or "")
    return m.group(1).lower().rstrip("/") if m else ""


def keys(it):
    """Every handle a profile can be found by: the URL we sent, the vanity slug, the internal id."""
    q = (it.get("originalQuery") or {}).get("query") or it.get("_query") or ""
    return {k for k in (slug(q), (it.get("publicIdentifier") or "").lower(), slug(it.get("linkedinUrl")), (it.get("id") or "").lower()) if k}


def check(r, prof):
    out = {"li_title": "", "li_company": "", "li_role_started": "", "company_check": "", "title_check": "", "verdict": "", "verdict_why": ""}
    if not prof:
        out.update(company_check="not_on_linkedin", verdict="NO_PROFILE", verdict_why="no LinkedIn profile returned")
        return out
    ours_t = toks(r.get("company")) | toks(r.get("company_clean")) | toks((r.get("domain") or "").split(".")[0])
    exp = prof.get("experience") or []
    ours = [e for e in exp if ours_t & toks(e.get("companyName"))]
    open_roles = [e for e in ours if ((e.get("endDate") or {}).get("text") or "Present") == "Present"]
    cur = (prof.get("currentPosition") or [{}])[0]
    if open_roles:
        cur = open_roles[0]
    title, company = cur.get("position") or cur.get("title") or "", cur.get("companyName") or ""
    sd = cur.get("startDate") or {}
    out.update(li_title=title, li_company=company, li_role_started=f"{sd.get('year', '')}-{sd.get('month', '')}".strip("-") if isinstance(sd, dict) else str(sd))
    if ours and not open_roles:
        out.update(company_check="different", verdict="LEFT", verdict_why=f"role at {ours[0].get('companyName')} ended {(ours[0].get('endDate') or {}).get('text')}")
        return out
    if not company:
        out["company_check"] = "not_on_linkedin"
    elif ours_t & toks(company) or norm((r.get("domain") or "").split(".")[0]) in norm(company).replace(" ", ""):
        out["company_check"] = "same"
    else:
        out.update(company_check="different", verdict="LEFT", verdict_why=f"LinkedIn current employer is {company}")
        return out
    vt = r.get("title_clean") or r.get("title")
    out["title_check"] = ("no_current_role" if not title.strip() else "same" if tnorm(vt) == tnorm(title)
                          else "same_role" if buckets(vt) & buckets(title) else "different")
    why = [w for w, bad in (("title differs from vendor", out["title_check"] == "different"),
                            ("no current role on LinkedIn", out["title_check"] == "no_current_role"),
                            ("no current employer on LinkedIn", out["company_check"] == "not_on_linkedin")) if bad]
    out.update(verdict="CHECK" if why else "OK", verdict_why="; ".join(why))
    return out


def verify(rows, cfg, max_new, backend="treg", max_usd=1.0):
    cache_p = run_dir(cfg, "cache") / "linkedin_profiles.jsonl"
    cache = {}
    if cache_p.exists():
        for line in open(cache_p, encoding="utf-8"):
            if line.strip():
                x = json.loads(line)
                if not x.get("error"):
                    cache.update({k: x for k in keys(x)})
    need = [r["linkedin"] for r in rows if slug(r.get("linkedin")) and slug(r["linkedin"]) not in cache][:max_new]
    if need:
        print(f"fetching {len(need)} profiles via {backend} (~${0.004 * len(need):.2f})")
        with open(cache_p, "a", encoding="utf-8") as f:
            if backend == "treg":
                batches = [treg_profiles(cfg, need, max_usd)]
            else:
                tokens = [t.strip() for t in env("APIFY_TOKENS").split(",") if t.strip()]
                batches = (apify_profiles(tokens, need[i:i + 10]) for i in range(0, len(need), 10))  # free plans: 10 per run
            for batch in batches:
                for it in batch:
                    if it.get("error"):
                        print(f"  {backend}:", str(it["error"])[:100]); continue
                    cache.update({k: it for k in keys(it)})
                    f.write(json.dumps(it, ensure_ascii=False) + "\n")
    by_name = {norm(f"{x.get('firstName', '')} {x.get('lastName', '')}"): x for x in cache.values()}
    for r in rows:
        # the URL we hold is often an internal ACoAA... id the actor answers under a vanity slug; fall back to the name
        prof = cache.get(slug(r.get("linkedin"))) or by_name.get(norm(f"{r.get('first_name', '')} {r.get('last_name', '')}"))
        r.update(check(r, prof))
    from collections import Counter
    print("verdicts:", dict(Counter(r["verdict"] for r in rows)))
    for r in rows:
        if r["verdict"] != "OK":
            print(f"  {r['verdict']:10} {r.get('first_name', '')} {r.get('last_name', '')} @ {r.get('company')}: {r['verdict_why']}"
                  f" (vendor: {r.get('title')} | LinkedIn: {r['li_title']} at {r['li_company']})")


def main():
    cfg = config()
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["names", "verify"])
    ap.add_argument("--config")
    ap.add_argument("--input", default=str(run_dir(cfg) / "leads_master.csv"))
    ap.add_argument("--max", type=int, default=200, help="most new profiles to pay for in one run")
    ap.add_argument("--backend", choices=["treg", "apify"], default="treg")
    ap.add_argument("--max-usd", type=float, default=1.0, help="treg spend cap for this run")
    a = ap.parse_args()
    from pathlib import Path
    p = Path(a.input)
    rows = read(p)
    if a.step == "names":
        names(rows)
    else:
        verify(rows, cfg, a.max, a.backend, a.max_usd)
    write(p, rows)


if __name__ == "__main__":
    main()
