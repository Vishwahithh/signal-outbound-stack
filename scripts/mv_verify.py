"""mv_verify.py - MillionVerifier bulk email verification. Only result "ok" is sendable; catch-all is not.

Uploads a deduped email list to the bulk API, polls until finished, downloads full results to
runs/<run>/mv_results_<label>.csv and prints the verdict breakdown. If polling dies after upload, rerun with
--resume <file_id>: never re-upload, that spends the credits twice.

    python scripts/mv_verify.py --input runs/<run>/leads_master.csv --label primary [--max-credits 1600]
    python scripts/mv_verify.py --resume <file_id> --label primary
"""
import argparse, csv, io, json, sys, time, urllib.request, uuid
from collections import Counter

from common import config, env, run_dir

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0"}
BULK = "https://bulkapi.millionverifier.com/bulkapi/v2"
K = env("MILLIONVERIFIER_API_KEY")


def get(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())


def credits():
    try:
        return get(f"https://api.millionverifier.com/api/v3/credits?api={K}").get("credits")
    except Exception:
        return None


def upload(emails, name):
    boundary = uuid.uuid4().hex
    body = io.BytesIO()
    body.write(f"--{boundary}\r\n".encode())
    body.write(f'Content-Disposition: form-data; name="file_contents"; filename="{name}.txt"\r\n'.encode())
    body.write(b"Content-Type: text/plain\r\n\r\n")
    body.write("\n".join(emails).encode())
    body.write(f"\r\n--{boundary}--\r\n".encode())
    req = urllib.request.Request(f"{BULK}/upload?key={K}", data=body.getvalue(),
                                 headers={**UA, "Content-Type": f"multipart/form-data; boundary={boundary}"})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())


def finish(fid, out, c0):
    while True:
        try:
            info = get(f"{BULK}/fileinfo?key={K}&file_id={fid}")
        except Exception as e:  # a DNS blip while polling must not lose a paid upload
            print(f"  poll failed ({str(e)[:60]}), retrying", flush=True); time.sleep(15); continue
        st = info.get("status")
        print(f"  status={st} progress={info.get('percent', '?')}%", flush=True)
        if st in ("finished", "canceled", "error"):
            break
        time.sleep(10)
    if st != "finished":
        sys.exit(f"bulk job ended with status={st}: {info}")
    raw = urllib.request.urlopen(urllib.request.Request(f"{BULK}/download?key={K}&file_id={fid}&filter=all", headers=UA),
                                 timeout=120).read().decode("utf-8", "replace")
    out.write_text(raw, encoding="utf-8")
    rdr = csv.DictReader(io.StringIO(raw))
    col = next((c for c in (rdr.fieldnames or []) if c and c.strip().lower() in ("result", "quality")), None)
    cnt = Counter((r.get(col) or "?").strip().lower() for r in rdr) if col else Counter()
    c1 = credits()
    print(f"-> {out}\ncredits after: {c1} (spent ~{(c0 - c1) if (c0 and c1) else '?'})\nverdicts: {dict(cnt.most_common())}")


def main():
    cfg = config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="CSV with email (and optionally second_email) columns, or one email per line")
    ap.add_argument("--label", required=True)
    ap.add_argument("--max-credits", type=int, default=1600)
    ap.add_argument("--resume")
    ap.add_argument("--config")
    a = ap.parse_args()
    out = run_dir(cfg) / f"mv_results_{a.label}.csv"
    if a.resume:
        return finish(a.resume, out, credits())
    emails, seen = [], set()
    with open(a.input, encoding="utf-8-sig") as f:
        head = f.readline(); f.seek(0)
        rows = csv.DictReader(f) if "email" in head.lower() else ({"email": line.strip()} for line in f)
        for r in rows:
            for col in ("email", "second_email"):
                em = (r.get(col) or "").strip().lower()
                if em and "@" in em and em not in seen:
                    seen.add(em); emails.append(em)
    print(f"emails to verify: {len(emails)} (deduped)")
    if len(emails) > a.max_credits:
        sys.exit(f"ABORT: list ({len(emails)}) exceeds --max-credits {a.max_credits}")
    c0 = credits()
    print(f"credits before: {c0}")
    fid = upload(emails, a.label).get("file_id")
    if not fid:
        sys.exit("upload failed")
    print(f"uploaded, file_id={fid} - polling (if this dies, rerun with --resume {fid})")
    finish(fid, out, c0)


if __name__ == "__main__":
    main()
