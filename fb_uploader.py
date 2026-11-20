#!/usr/bin/env python3
"""
Facebook Reels Uploader — Graph API (personal use only)
=========================================================
Aik Facebook Page pe Reel publish karna, official Graph API se.
V2 (YouTube) ka Facebook wala counterpart — multi_upload.py isay
delegate karta hai, lekin ye akela bhi chal sakta hai.

Flow (verified 2026-11-19, Meta docs/guides — LIVE TEST NAHI hua):
  Graph API v21.0, POST /{page-id}/video_reels, 3 phases:
  1. start  — upload_phase=start -> video_id + upload_url milta hai
  2. upload — file ke bytes upload_url (rupload host) pe bhejo:
              Authorization: OAuth <page-token>, offset: 0,
              file_size: <bytes>
  3. finish — upload_phase=finish, video_id,
              video_state=PUBLISHED, description
  Phir aik simple status poll: GET /{video_id}?fields=status
  (max 5 tries, 2s apart) — sirf report ke liye, fail nahi karta.

Page token har page ka alag hota hai: GET /me/accounts se milta hai
(pages_manage_posts permission). Tumhare APNE pages ke liye
Standard Access kaafi hai.

Token KABHI print/log nahi hota — na is file mein, na multi_upload mein.
Token file / pages.json KISI ko mat bhejo, GitHub pe mat daalo.

Sirf stdlib (urllib) — koi extra dependency nahi. Tests ke liye
http_post / http_get injectable hain taake mock ho sakein.

Chalana:
    python fb_uploader.py --check --file reel.mp4 --page-id <PAGE_ID> \
        --token-file tokens/mind-maze-fb.page_token.txt
        # sirf check: file + token file + page-id, NO network
    python fb_uploader.py --file reel.mp4 --page-id <PAGE_ID> \
        --token-file tokens/mind-maze-fb.page_token.txt \
        --description "Mind Maze — can you reverse it?"
        # asal upload (3 phases)

Sirf apne / licensed content ke liye.
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

GRAPH_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"
POLL_TRIES = 5
POLL_SLEEP = 2  # seconds


def log(msg):
    print(msg, flush=True)


# --- Token ---

def read_token(token_file):
    """Token file parho — strip karke return. Token kabhi print nahi hota."""
    if not os.path.exists(token_file):
        raise FileNotFoundError(f"token file nahi mili: {token_file}")
    with open(token_file, encoding="utf-8") as f:
        token = f.read().strip()
    if not token:
        raise ValueError(f"token file khaali hai: {token_file}")
    return token


# --- Default HTTP (urllib only) — tests mein mock inject hota hai ---

def _parse_response(raw):
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}


def _http_post(url, data=None, headers=None, raw_data=None):
    """POST karo, JSON response dict return karo.
    data = form fields (urlencode ho jayenge), raw_data = file bytes."""
    if raw_data is not None:
        body = raw_data
    elif data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
    else:
        body = b""
    req = urllib.request.Request(url, data=body, method="POST")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req) as resp:  # noqa: S310 — fixed Graph/rupload hosts
        return _parse_response(resp.read())


def _http_get(url):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req) as resp:  # noqa: S310
        return _parse_response(resp.read())


def _check_graph_error(resp, phase):
    if isinstance(resp, dict) and resp.get("error"):
        err = resp["error"]
        raise RuntimeError(f"Facebook Graph error ({phase}): "
                           f"{err.get('message', err)}")


# --- 3 phases ---

def start_upload(page_id, token, http_post=None):
    """Phase 1 — start. Returns (video_id, upload_url)."""
    post = http_post or _http_post
    resp = post(f"{GRAPH_BASE}/{page_id}/video_reels",
                data={"upload_phase": "start", "access_token": token})
    _check_graph_error(resp, "start")
    video_id = resp.get("video_id")
    upload_url = resp.get("upload_url")
    if not video_id or not upload_url:
        raise RuntimeError(f"start phase se video_id/upload_url nahi mila: {resp}")
    return str(video_id), upload_url


def upload_bytes(upload_url, token, file_path, http_post=None):
    """Phase 2 — file ke bytes rupload URL pe bhejo."""
    post = http_post or _http_post
    with open(file_path, "rb") as f:
        data = f.read()
    headers = {
        "Authorization": f"OAuth {token}",
        "offset": "0",
        "file_size": str(len(data)),
        "Content-Type": "application/octet-stream",
    }
    resp = post(upload_url, headers=headers, raw_data=data)
    _check_graph_error(resp, "upload")
    return resp


def finish_upload(page_id, token, video_id, description, http_post=None):
    """Phase 3 — finish, video_state=PUBLISHED ke saath."""
    post = http_post or _http_post
    resp = post(f"{GRAPH_BASE}/{page_id}/video_reels",
                data={"upload_phase": "finish",
                      "access_token": token,
                      "video_id": str(video_id),
                      "video_state": "PUBLISHED",
                      "description": description or ""})
    _check_graph_error(resp, "finish")
    return resp


def poll_status(video_id, token, http_get=None, sleep=None, tries=POLL_TRIES):
    """Simple status poll — GET /{video_id}?fields=status.
    Ready ho to True, warna tries ke baad False (upload fail nahi karta).
    Note: URL mein token query param hai — URL kabhi log nahi hota."""
    get = http_get or _http_get
    wait = sleep or time.sleep
    url = (f"{GRAPH_BASE}/{video_id}?fields=status"
           f"&access_token={urllib.parse.quote(token)}")
    for attempt in range(1, tries + 1):
        try:
            resp = get(url)
        except Exception:  # noqa: BLE001 — poll best-effort hai
            resp = {}
        status = resp.get("status") if isinstance(resp, dict) else None
        video_status = ""
        if isinstance(status, dict):
            video_status = str(status.get("video_status", ""))
        elif isinstance(status, str):
            video_status = status
        if video_status.lower() in ("ready", "published"):
            return True
        if attempt < tries:
            wait(POLL_SLEEP)
    return False


def upload_reel(token, page_id, file_path, description,
                http_post=None, http_get=None, sleep=None):
    """Poora flow: start -> upload -> finish -> status poll.
    Returns video_id (str). Token kabhi print nahi hota."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"file nahi mili: {file_path}")
    video_id, upload_url = start_upload(page_id, token, http_post=http_post)
    log(f"  [fb] start OK — video_id {video_id}")
    upload_bytes(upload_url, token, file_path, http_post=http_post)
    log("  [fb] bytes upload OK")
    finish_upload(page_id, token, video_id, description, http_post=http_post)
    log("  [fb] finish OK — PUBLISHED")
    if poll_status(video_id, token, http_get=http_get, sleep=sleep):
        log("  [fb] status: ready")
    else:
        log("  [fb] status: abhi processing — Page pe thodi der mein dikhega")
    return video_id


# --- CLI ---

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Facebook Reels uploader — Graph API v21.0 (1 file)")
    parser.add_argument("--file", required=True, help="Reel video file")
    parser.add_argument("--page-id", required=True, help="Facebook Page ID")
    parser.add_argument("--token-file", required=True,
                        help="Us page ke Page access token wali file")
    parser.add_argument("--description", default="",
                        help="Reel description (khaali ho to filename)")
    parser.add_argument("--check", action="store_true",
                        help="Sirf check: file + token file + page-id, NO network")
    args = parser.parse_args(argv)

    errors = []
    if not os.path.exists(args.file):
        errors.append(f"file nahi mili: {args.file}")
    elif os.path.getsize(args.file) == 0:
        errors.append(f"file khaali hai (0 bytes): {args.file}")
    if not args.page_id or not args.page_id.strip():
        errors.append("page-id khaali hai")
    try:
        token = read_token(args.token_file)
    except (FileNotFoundError, ValueError) as e:
        errors.append(str(e))
        token = None
    if errors:
        for e in errors:
            log(f"FAIL: {e}")
        return 1
    if args.check:
        log("CHECK OK: file + token file + page-id theek hain — "
            "network nahi chalaya, upload nahi hua.")
        return 0

    description = args.description or os.path.splitext(
        os.path.basename(args.file))[0]
    try:
        video_id = upload_reel(token, args.page_id, args.file, description)
    except Exception as e:  # noqa: BLE001
        log(f"FAIL: {e}")
        return 1
    log(f"OK: reel publish ho gayi — video_id {video_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
