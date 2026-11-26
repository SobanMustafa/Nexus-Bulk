#!/usr/bin/env python3
"""YouTube bulk uploader using YouTube Data API v3 (OAuth 2.0, resumable)."""
import argparse
import csv
import json
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE = os.path.join(BASE_DIR, "uploads.csv")
VIDEOS_DIR = os.path.join(BASE_DIR, "videos")
CLIENT_SECRETS = os.path.join(BASE_DIR, "client_secrets.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
UPLOADED_FILE = os.path.join(BASE_DIR, "uploaded.csv")
FAILED_FILE = os.path.join(BASE_DIR, "failed_uploads.csv")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
DEFAULT_CATEGORY = "22"
DEFAULT_PRIVACY = "private"
CHUNK_SIZE = 10 * 1024 * 1024
MAX_RETRIES = 3
SLEEP_BETWEEN = 5
MAX_TITLE = 100
MAX_DESCRIPTION = 5000
MAX_TAGS_LEN = 500
VALID_PRIVACY = ("private", "unlisted", "public")
VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")


def log(msg):
    print(msg, flush=True)


def resolve_file(path):
    """videos/ ke andar relative path, ya poora path — dono chalte hain."""
    if os.path.isabs(path) and os.path.exists(path):
        return path
    cand = os.path.join(BASE_DIR, path)
    if os.path.exists(cand):
        return cand
    cand2 = os.path.join(VIDEOS_DIR, path)
    if os.path.exists(cand2):
        return cand2
    return os.path.join(VIDEOS_DIR, path)


def parse_tags(raw):
    if not raw:
        return []
    return [t.strip() for t in raw.replace(";", "|").split("|") if t.strip()]


def load_queue(path=QUEUE_FILE):
    """uploads.csv parho — # wali lines aur khaali lines skip, duplicates hatao."""
    if not os.path.exists(path):
        sys.exit(f"uploads.csv nahi mili: {path}\nPehle uploads.csv me aik line pe aik video likho.")
    items, seen = [], set()
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.reader(f) if r and not r[0].strip().startswith("#")]
    if not rows:
        sys.exit("uploads.csv khaali hai — koi video nahi mili.")
    header = [h.strip().lower() for h in rows[0]]
    if "file" not in header:
        sys.exit("uploads.csv me 'file' column chahiye — pehli line header honi chahiye.")
    for row in rows[1:]:
        d = dict(zip(header, [c.strip() for c in row]))
        fpath = d.get("file", "")
        if not fpath:
            continue
        if fpath in seen:
            continue
        seen.add(fpath)
        items.append({
            "file": fpath,
            "title": d.get("title", "") or os.path.splitext(os.path.basename(fpath))[0],
            "description": d.get("description", ""),
            "tags": parse_tags(d.get("tags", "")),
            "category_id": d.get("category_id", "") or DEFAULT_CATEGORY,
            "privacy": (d.get("privacy", "") or DEFAULT_PRIVACY).lower(),
        })
    if not items:
        sys.exit("uploads.csv me koi video nahi — sirf header hai?")
    return items


def validate(item):
    """Aik item check karo — (ok, [errors]). File exist + YouTube limits."""
    errors = []
    full = resolve_file(item["file"])
    if not os.path.exists(full):
        errors.append(f"file nahi mili: {item['file']}")
    elif not full.lower().endswith(VIDEO_EXTS):
        errors.append(f"video format nahi lagta: {item['file']} (mp4/mov/mkv/webm)")
    elif os.path.getsize(full) == 0:
        errors.append(f"file khaali hai (0 bytes): {item['file']}")
    if not item["title"]:
        errors.append("title khaali hai")
    elif len(item["title"]) > MAX_TITLE:
        errors.append(f"title {len(item['title'])} chars — max {MAX_TITLE}")
    if len(item["description"]) > MAX_DESCRIPTION:
        errors.append(f"description {len(item['description'])} chars — max {MAX_DESCRIPTION}")
    if sum(len(t) for t in item["tags"]) + max(len(item["tags"]) - 1, 0) > MAX_TAGS_LEN:
        errors.append("tags total 500 chars se zyada")
    if item["privacy"] not in VALID_PRIVACY:
        errors.append(f"privacy galat: {item['privacy']} (private/unlisted/public)")
    if not item["category_id"].isdigit():
        errors.append(f"category_id number honi chahiye: {item['category_id']}")
    return (not errors, errors)


def load_uploaded():
    done = set()
    if os.path.exists(UPLOADED_FILE):
        with open(UPLOADED_FILE, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("file"):
                    done.add(row["file"])
    return done


def build_body(item):
    """videos.insert ke liye snippet + status body."""
    body = {
        "snippet": {
            "title": item["title"],
            "description": item["description"],
            "tags": item["tags"],
            "categoryId": item["category_id"],
        },
        "status": {
            "privacyStatus": item["privacy"],
            "selfDeclaredMadeForKids": False,
        },
    }
    return body


# Google libs are imported lazily so --check works without them installed.

def get_youtube_service():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        sys.exit("Google libs nahi mili. Pehle chalao:  pip install -r requirements.txt")
    if not os.path.exists(CLIENT_SECRETS):
        sys.exit("client_secrets.json nahi mili — pehle Google Cloud Console se\n"
                 "OAuth client ID (Desktop app) banao aur file is folder me rakho.\n"
                 "README.md me Step 1-2 dekho.")
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def upload_one(youtube, item):
    """Aik video upload karo — resumable, retries ke saath. Returns video_id."""
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError

    full = resolve_file(item["file"])
    media = MediaFileUpload(full, chunksize=CHUNK_SIZE, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status", body=build_body(item), media_body=media,
        notifySubscribers=False,
    )
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    log(f"  [{item['title'][:40]}] {int(status.progress() * 100)}%")
            return response["id"]
        except HttpError as e:
            last_error = e
            code = getattr(e.resp, "status", "?")
            # Retry transient 5xx/429 errors; fail fast on 4xx quota/auth errors.
            if code in (500, 502, 503, 429) and attempt < MAX_RETRIES:
                wait = 2 ** attempt
                log(f"  retry {attempt}/{MAX_RETRIES} ({code}) — {wait}s ruk ke...")
                time.sleep(wait)
            else:
                raise
    raise last_error


def record_uploaded(item, video_id):
    exists = os.path.exists(UPLOADED_FILE)
    with open(UPLOADED_FILE, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["file", "title", "video_id", "url", "privacy"])
        w.writerow([item["file"], item["title"], video_id,
                    f"https://youtu.be/{video_id}", item["privacy"]])


def record_failed(item, error):
    exists = os.path.exists(FAILED_FILE)
    with open(FAILED_FILE, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["file", "title", "error"])
        w.writerow([item["file"], item["title"], str(error)[:500]])


def main():
    parser = argparse.ArgumentParser(description="Apna Bulk Uploader V2 — YouTube Data API v3")
    parser.add_argument("--check", action="store_true",
                        help="Sirf check karo — files + metadata, NO upload, NO login")
    parser.add_argument("--queue", default=QUEUE_FILE, help="Queue file (default: uploads.csv)")
    parser.add_argument("--force", action="store_true",
                        help="Pehle se upload hui videos bhi dobara upload karo")
    args = parser.parse_args()

    items = load_queue(args.queue)
    done = load_uploaded() if not args.force else set()
    pending = [i for i in items if i["file"] not in done]
    skipped = len(items) - len(pending)
    log(f"Queue: {len(items)} video(s) — {skipped} pehle se uploaded (skip), {len(pending)} baqi")

    all_ok = True
    for item in pending:
        ok, errors = validate(item)
        if not ok:
            all_ok = False
            log(f"FAIL: {item['file']}")
            for e in errors:
                log(f"  - {e}")
    if args.check:
        if all_ok:
            log(f"\nCHECK OK: {len(pending)} video(s) ready — quota ~{len(pending)} upload(s) "
                f"(limit 100/day). Ab `python uploader.py` se upload kar sakte ho.")
        else:
            log("\nCHECK FAIL: upar wali ghaltiyan theek karo, phir dobara --check chalao.")
        return 0 if all_ok else 1
    if not all_ok:
        sys.exit("Validation fail — upload shuru nahi hua. Pehle `python uploader.py --check` chalao.")
    if not pending:
        log("Kuch upload karne ko nahi — sab pehle se uploaded.csv me hain.")
        return 0

    youtube = get_youtube_service()
    ok_count, failed = 0, []
    t0 = time.time()
    for idx, item in enumerate(pending, 1):
        log(f"\n[{idx}/{len(pending)}] {item['title']} ({item['privacy']})")
        try:
            vid = upload_one(youtube, item)
            record_uploaded(item, vid)
            log(f"  OK: https://youtu.be/{vid}")
            ok_count += 1
        except Exception as e:  # noqa: BLE001 — aik fail ho to baaki chalte rahen
            log(f"  FAIL: {e}")
            record_failed(item, e)
            failed.append(item)
        if idx < len(pending):
            time.sleep(SLEEP_BETWEEN)

    log(f"\nDone: {ok_count}/{len(pending)} OK, {len(failed)} fail — {time.time() - t0:.0f}s")
    if failed:
        log("Fail hui videos failed_uploads.csv me save — theek karke dobara chalao.")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
