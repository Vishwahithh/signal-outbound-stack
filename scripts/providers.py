"""providers.py - the two data layers every paid script goes through: treg (one token, per-call providers) and the
Deepline CLI (pay-as-you-go waterfalls). Both log every call to runs/<run>/cache/spend.jsonl with its real cost, and
both refuse to start a call once the run's budget is used up.

    from providers import Budget, treg, deepline
    b = Budget(cfg, max_usd=2.0)                     # hard stop for this script run
    status, data = treg(b, "trykitt.people.email.find", body={...})
    data = deepline(b, "icypeas_email_search", {...}, est_usd=0.014)

Rules baked in:
- Call providers by their own id, never treg's routed "treg.*" ids: routed calls can bill a miss at every provider tried.
- Never route to predictleads, on either layer.
- treg reports the settled cost in the X-Treg-Cost-Micro header; Deepline costs are logged at the listed price (est_usd)
  and are only an estimate until you check `deepline billing balance`.
"""
import json, subprocess, sys, time, urllib.error, urllib.parse, urllib.request, uuid

from common import env, run_dir

BANNED = ("predictleads",)


class Budget:
    def __init__(self, cfg, max_usd):
        self.max, self.spent = float(max_usd), 0.0
        self.log = run_dir(cfg, "cache") / "spend.jsonl"

    def check(self, tool):
        if any(b in tool.lower() for b in BANNED):
            sys.exit(f"refused: {tool} is on the banned provider list")
        if self.spent >= self.max:
            raise BudgetExceeded(f"budget ${self.max:.2f} used (${self.spent:.4f})")

    def add(self, tool, usd, note=""):
        self.spent += usd
        with open(self.log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "tool": tool, "usd": round(usd, 6), "note": note}) + "\n")


class BudgetExceeded(Exception):
    pass


def treg(budget, endpoint, query=None, body=None, method=None, timeout=120):
    """One catalog call. Returns (http_status, parsed JSON or text). Lists in query become repeated keys."""
    budget.check(endpoint)
    if endpoint.startswith("treg."):
        sys.exit(f"refused: {endpoint} is a routed endpoint (bills misses); name the provider's own id")
    url = f"https://treg.to/call/{endpoint}"
    if query:
        url += "?" + urllib.parse.urlencode(query, doseq=True)
    h = {"X-Treg-Token": env("TREG_TOKEN"), "Idempotency-Key": uuid.uuid4().hex, "User-Agent": "signal-outbound-stack"}
    data = None
    if body is not None:
        data, h["Content-Type"] = json.dumps(body).encode(), "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method or ("POST" if body is not None else "GET"))
    for attempt in range(4):
        try:
            r = urllib.request.urlopen(req, timeout=timeout)
            status, raw, hdr = r.status, r.read().decode("utf-8", "replace"), r.headers
        except urllib.error.HTTPError as e:
            status, raw, hdr = e.code, e.read().decode("utf-8", "replace"), e.headers
            if status == 503 and attempt < 3:                      # treg saturated: nothing billed, retry same key
                time.sleep(int(hdr.get("Retry-After") or 5)); continue
            if status == 409 and attempt < 3:                      # same key still running
                time.sleep(5); continue
        except Exception as e:
            if attempt < 3:
                time.sleep(5 * (attempt + 1)); continue
            return 0, {"error": str(e)}
        break
    cost = int(hdr.get("X-Treg-Cost-Micro") or 0) / 1e6
    budget.add(endpoint, cost, f"http {status}")
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, raw


def deepline(budget, tool, payload, est_usd):
    """Run one Deepline tool through its CLI (`deepline auth` must be done once). est_usd = listed price per hit."""
    budget.check(tool)
    cmd = ["deepline", "tools", "execute", tool, "--input", json.dumps(payload), "--json"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=180, shell=sys.platform == "win32")
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    out = p.stdout.strip()
    try:
        data = json.loads(out[out.index("{"):]) if "{" in out else {"error": p.stderr.strip()[:300]}
    except json.JSONDecodeError:
        data = {"error": out[:300]}
    budget.add(tool, est_usd if find_email(data) else 0.0, "deepline estimate")
    return data


def find_email(obj):
    """First plausible email anywhere in a provider response (shapes differ by provider)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in ("email", "work_email", "emailaddress") and isinstance(v, str) and "@" in v and " " not in v:
                return v.strip().lower()
        for v in obj.values():
            e = find_email(v)
            if e:
                return e
    elif isinstance(obj, list):
        for v in obj:
            e = find_email(v)
            if e:
                return e
    return None
