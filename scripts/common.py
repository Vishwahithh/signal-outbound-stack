"""common.py - shared helpers: .env loading, client config, run folder, domain normalising, JSONL reading.

Every script takes --config (default config/client.json, or the SOK_CONFIG environment variable). The config names
the run; all output for that run lives in runs/<run>/ so two clients or two waves never mix.
"""
import glob, json, os, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]


def load_env():
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def env(name, required=True):
    load_env()
    v = os.environ.get(name)
    if required and not v:
        sys.exit(f"{name} missing: copy .env.example to .env and fill it in")
    return v


def config_path():
    if "--config" in sys.argv:
        return Path(sys.argv[sys.argv.index("--config") + 1])
    return Path(os.environ.get("SOK_CONFIG") or ROOT / "config" / "client.json")


def config():
    p = config_path()
    if not p.exists():
        sys.exit(f"config not found: {p}. Copy config/client.example.json to config/client.json and edit it.")
    return json.loads(p.read_text(encoding="utf-8"))


def run_dir(cfg, *sub):
    d = ROOT / "runs" / cfg["run"]
    for s in sub:
        d = d / s
    d.mkdir(parents=True, exist_ok=True)
    return d


def norm(d):
    """Bare lower-case host: 'https://www.Acme.com/pricing' -> 'acme.com'."""
    d = (d or "").strip().lower()
    for p in ("https://", "http://"):
        if d.startswith(p):
            d = d[len(p):]
    d = d.split("/")[0]
    return d[4:] if d.startswith("www.") else d


def jl(pattern):
    """Read every JSON line from files matching a glob, skipping blank or half-written lines."""
    out = []
    for f in sorted(glob.glob(str(pattern))):
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out
