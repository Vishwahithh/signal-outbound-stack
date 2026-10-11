"""smartlead.py - small Smartlead API client shared by inbox_health, seed_test, replies and monitor.

Lessons baked in:
- Smartlead answers 403 with no body when the User-Agent header is missing, so every call sends a browser one.
- GET /email-accounts/ ignores `offset` on some accounts: paging stops when a page repeats, not only when it is short.
- warmup_details is empty until warmup has been switched on, so "no warmup data" means "warmup off", not "healthy".
- The warmup endpoint rejects daily_rampup below 5.
"""
import json, sys, time, urllib.error, urllib.request

from common import env

BASE = "https://server.smartlead.ai/api/v1"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36", "Content-Type": "application/json"}


def api(method, path, body=None, fatal=False):
    url = "%s%s%sapi_key=%s" % (BASE, path, "&" if "?" in path else "?", env("SMARTLEAD_API_KEY"))
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA, method=method), timeout=60) as r:
                t = r.read()
                return json.loads(t) if t else {}
        except urllib.error.HTTPError as e:
            msg = "HTTP %s on %s %s: %s" % (e.code, method, path, e.read().decode("utf-8", "replace")[:300])
            if e.code == 429 and attempt < 2:
                time.sleep(10); continue
            if fatal:
                sys.exit(msg)
            return {"_error": msg}
        except Exception as e:
            if attempt < 2:
                time.sleep(5); continue
            if fatal:
                sys.exit(str(e))
            return {"_error": str(e)}


def paged(path, limit=100):
    out, off, seen = [], 0, set()
    while True:
        d = api("GET", "%s%soffset=%d&limit=%d" % (path, "&" if "?" in path else "?", off, limit)) or {}
        rows = d.get("data") if isinstance(d, dict) else d
        rows = [r for r in (rows or []) if isinstance(r, dict)]
        key = json.dumps([r.get("id") or r.get("lead", {}).get("id") or r.get("email_campaign_seq_id") for r in rows[:3]])
        if not rows or key in seen:
            return out
        seen.add(key)
        out += rows
        if len(rows) < limit:
            return out
        off += limit


def accounts():
    return {a["id"]: a for a in paged("/email-accounts/") if "from_email" in a}


def rep(acc):
    """Warmup reputation as a number, or None when warmup is off or has no data yet."""
    try:
        return float(str((acc.get("warmup_details") or {}).get("warmup_reputation") or "").rstrip("%"))
    except ValueError:
        return None


def warmup_status(acc):
    return (acc.get("warmup_details") or {}).get("status") or "OFF"
