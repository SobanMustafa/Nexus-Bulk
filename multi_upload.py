#!/usr/bin/env python3
"""Multi-target uploader for Facebook Pages and YouTube Channels.

Uses pages.json as the destination registry and tracks per-target upload state
in state/uploaded-<target>.csv.
"""
import argparse
import csv
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(BASE_DIR, "state")
DEFAULT_PAGES = os.path.join(BASE_DIR, "pages.json")
DEFAULT_QUEUE = os.path.join(BASE_DIR, "uploads.csv")

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
import fb_uploader  # noqa: E402

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
DEFAULT_CATEGORY = "22"
DEFAULT_PRIVACY_YT = "private"
CHUNK_SIZE = 10 * 1024 * 1024
MAX_RETRIES = 3
SLEEP_BETWEEN = 5
MAX_TITLE = 100
MAX_DESCRIPTION = 5000
MAX_TAGS_LEN = 500
VALID_PRIVACY_YT = ("private", "unlisted", "public")
VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")
PLATFORMS = ("facebook", "youtube")
PLACEHOLDER_MARK = "FILL-IN"


def log(msg):
    print(msg, flush=True)


def load_registry(path):
    """Load and validate pages.json -> (registry, warnings)."""
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"pages.json nahi mili: {path}\n"
            "Pehle pages.example.json ko pages.json naam se copy karo "
            "aur apne page/channel ki details bharo.")
    import json
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"pages.json parh nahi saka: {e}") from e
    entries = data.get("pages") if isinstance(data, dict) else None
    if not entries:
        raise ValueError("pages.json mein 'pages' list khaali hai ya nahi hai.")
    registry, warnings, errors = {}, [], []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"entry #{i + 1}: object hona chahiye")
            continue
        pid = (entry.get("id") or "").strip()
        if not pid:
            errors.append(f"entry #{i + 1}: 'id' khaali hai")
            continue
        if pid in registry:
            errors.append(f"duplicate id: {pid} (har destination ki id alag rakho)")
            continue
        platform = (entry.get("platform") or "").strip().lower()
        if platform not in PLATFORMS:
            errors.append(f"{pid}: platform galat hai '{platform}' "
                          f"(facebook / youtube mein se aik rakho)")
            continue
        entry = dict(entry)
        entry["id"] = pid
        entry["platform"] = platform
        if platform == "facebook":
            page_id = (entry.get("page_id") or "").strip()
            if not page_id:
                errors.append(f"{pid}: facebook entry mein page_id chahiye")
                continue
            if PLACEHOLDER_MARK in page_id:
                warnings.append(
                    f"{pid}: page_id abhi placeholder hai — asal upload se "
                    "pehle GET /me/accounts se asal Page ID bharo")
            entry["page_id"] = page_id
            if not (entry.get("token_file") or "").strip():
                errors.append(f"{pid}: facebook entry mein token_file chahiye")
                continue
        else:
            if not (entry.get("auth_dir") or "").strip():
                errors.append(f"{pid}: youtube entry mein auth_dir chahiye")
                continue
        registry[pid] = entry
    if errors:
        raise ValueError("pages.json ki ghaltiyan:\n  - " + "\n  - ".join(errors))
    if not registry:
        raise ValueError("pages.json mein koi valid entry nahi mili.")
    return registry, warnings


def parse_tags(raw):
    if not raw:
        return []
    return [t.strip() for t in raw.replace(";", "|").split("|") if t.strip()]


def resolve_file(path, base_dir=None):
    """Absolute path, ya script folder ke relative — dono chalte hain."""
    base = base_dir or BASE_DIR
    if os.path.isabs(path):
        return path
    cand = os.path.join(base, path)
    if os.path.exists(cand):
        return cand
    return cand


def load_queue(path, registry, default_target=None, base_dir=None):
    """uploads.csv parho — target ke saath. Unknown target = ValueError.
    Returns items list (queue order). Dedupe (file,target) pair pe hai —
    aik file do targets pe ja sakti hai."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"uploads.csv nahi mili: {path}")
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.reader(f) if r and not r[0].strip().startswith("#")]
    if not rows:
        raise ValueError("uploads.csv khaali hai — koi video nahi mili.")
    header = [h.strip().lower() for h in rows[0]]
    if "file" not in header:
        raise ValueError("uploads.csv mein 'file' column chahiye — pehli line header honi chahiye.")
    items, seen, errors = [], set(), []
    for row in rows[1:]:
        d = dict(zip(header, [c.strip() for c in row]))
        fpath = d.get("file", "")
        if not fpath:
            continue
        target = d.get("target", "") or (default_target or "")
        if not target:
            errors.append(f"{fpath}: target khaali hai — target likho ya "
                          "--default-target do")
            continue
        if target not in registry:
            errors.append(f"{fpath}: unknown target '{target}' — "
                          "pages.json mein ye id nahi hai")
            continue
        key = (fpath, target)
        if key in seen:
            continue
        seen.add(key)
        entry = registry[target]
        if entry["platform"] == "youtube":
            default_privacy = (entry.get("default_privacy")
                               or DEFAULT_PRIVACY_YT).lower()
            if default_privacy not in VALID_PRIVACY_YT:
                default_privacy = DEFAULT_PRIVACY_YT
        else:
            default_privacy = entry.get("default_privacy") or "published"
        items.append({
            "file": fpath,
            "title": d.get("title", "") or os.path.splitext(os.path.basename(fpath))[0],
            "description": d.get("description", ""),
            "tags": parse_tags(d.get("tags", "")),
            "category_id": d.get("category_id", "") or DEFAULT_CATEGORY,
            "privacy": (d.get("privacy", "") or default_privacy).lower(),
            "target": target,
        })
    if errors:
        raise ValueError("uploads.csv ki ghaltiyan:\n  - " + "\n  - ".join(errors))
    if not items:
        raise ValueError("uploads.csv mein koi video nahi — sirf header hai?")
    return items


def group_by_target(items):
    """Items ko target ke hisaab se group karo (order preserved)."""
    groups = {}
    for item in items:
        groups.setdefault(item["target"], []).append(item)
    return groups


def validate_item(item, registry, base_dir=None):
    """Aik item check karo — (ok, [errors]). File exist + metadata limits.
    YouTube limits sirf YouTube targets pe sakhti se lagte hain;
    Facebook pe title/category/privacy use nahi hote."""
    errors = []
    full = resolve_file(item["file"], base_dir)
    if not os.path.exists(full):
        errors.append(f"file nahi mili: {item['file']}")
    elif not full.lower().endswith(VIDEO_EXTS):
        errors.append(f"video format nahi lagta: {item['file']} (mp4/mov/mkv/webm)")
    elif os.path.getsize(full) == 0:
        errors.append(f"file khaali hai (0 bytes): {item['file']}")
    entry = registry[item["target"]]
    if entry["platform"] == "youtube":
        if not item["title"]:
            errors.append("title khaali hai")
        elif len(item["title"]) > MAX_TITLE:
            errors.append(f"title {len(item['title'])} chars — max {MAX_TITLE}")
        if len(item["description"]) > MAX_DESCRIPTION:
            errors.append(f"description {len(item['description'])} chars — max {MAX_DESCRIPTION}")
        if sum(len(t) for t in item["tags"]) + max(len(item["tags"]) - 1, 0) > MAX_TAGS_LEN:
            errors.append("tags total 500 chars se zyada")
        if item["privacy"] not in VALID_PRIVACY_YT:
            errors.append(f"privacy galat: {item['privacy']} (private/unlisted/public)")
        if not item["category_id"].isdigit():
            errors.append(f"category_id number honi chahiye: {item['category_id']}")
    else:  # facebook — description Reel pe jati hai, bohat lambi na ho
        if len(item["description"]) > MAX_DESCRIPTION:
            errors.append(f"description {len(item['description'])} chars — max {MAX_DESCRIPTION}")
    return (not errors, errors)


def _state_path(target_id, kind, state_dir=None):
    return os.path.join(state_dir or STATE_DIR, f"{kind}-{target_id}.csv")


def load_uploaded(target_id, state_dir=None):
    done = set()
    path = _state_path(target_id, "uploaded", state_dir)
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("file"):
                    done.add(row["file"])
    return done


def pending_items(items, state_dir=None, force=False):
    """Pehle se (usi target pe) upload hui videos hata do.
    Aik video doosre target pe phir bhi pending rahegi."""
    if force:
        return list(items)
    done_by_target = {}
    out = []
    for item in items:
        t = item["target"]
        if t not in done_by_target:
            done_by_target[t] = load_uploaded(t, state_dir)
        if item["file"] not in done_by_target[t]:
            out.append(item)
    return out


def record_uploaded(item, result_id, url, state_dir=None):
    path = _state_path(item["target"], "uploaded", state_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    exists = os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["file", "title", "result_id", "url", "target"])
        w.writerow([item["file"], item["title"], result_id, url, item["target"]])


def record_failed(item, error, state_dir=None):
    path = _state_path(item["target"], "failed", state_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    exists = os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["file", "title", "target", "error"])
        w.writerow([item["file"], item["title"], item["target"], str(error)[:500]])


def auth_paths(entry, base_dir=None):
    auth_dir = resolve_file(entry["auth_dir"], base_dir)
    return (auth_dir,
            os.path.join(auth_dir, "client_secrets.json"),
            os.path.join(auth_dir, "token.json"))


def get_youtube_service(entry, base_dir=None):
    """Google libs are imported lazily so --check works without them."""
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        sys.exit("Google libs nahi mili. Pehle chalao:  pip install -r requirements.txt")
    _, secrets, token_file = auth_paths(entry, base_dir)
    if not os.path.exists(secrets):
        sys.exit(f"client_secrets.json nahi mili ({entry['id']}): {secrets}\n"
                 "Us channel ke Google Cloud OAuth (Desktop app) ki file "
                 "auth folder mein rakho — README dekho.")
    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(secrets, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def build_body(item):
    return {
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


def upload_one_youtube(youtube, item, base_dir=None):
    """Aik video upload — resumable, retries ke saath (V2 jaisa). Returns video_id."""
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError

    full = resolve_file(item["file"], base_dir)
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
                    log(f"    [{item['title'][:40]}] {int(status.progress() * 100)}%")
            return response["id"]
        except HttpError as e:
            last_error = e
            code = getattr(e.resp, "status", "?")
            if code in (500, 502, 503, 429) and attempt < MAX_RETRIES:
                wait = 2 ** attempt
                log(f"    retry {attempt}/{MAX_RETRIES} ({code}) — {wait}s ruk ke...")
                time.sleep(wait)
            else:
                raise
    raise last_error


def upload_one_facebook(entry, item, base_dir=None):
    """fb_uploader ko delegate. Returns facebook video_id.
    Description = item description, khaali ho to title."""
    token_file = resolve_file(entry["token_file"], base_dir)
    token = fb_uploader.read_token(token_file)
    description = item["description"] or item["title"]
    full = resolve_file(item["file"], base_dir)
    return fb_uploader.upload_reel(token, entry["page_id"], full, description)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Multi-page uploader — Facebook Pages + YouTube channels")
    parser.add_argument("--pages", default=DEFAULT_PAGES,
                        help="Registry file (default: pages.json)")
    parser.add_argument("--queue", default=DEFAULT_QUEUE,
                        help="Queue CSV (default: uploads.csv)")
    parser.add_argument("--check", action="store_true",
                        help="Sirf check — registry + queue + files + limits, "
                             "NO network, NO login, NO upload")
    parser.add_argument("--target", default=None,
                        help="Sirf is target (page/channel id) pe chalao")
    parser.add_argument("--default-target", default=None,
                        help="Jis row mein target khaali ho, us ke liye default")
    parser.add_argument("--limit", type=int, default=0,
                        help="Total sirf N videos (pehle test ke liye, e.g. --limit 1)")
    parser.add_argument("--force", action="store_true",
                        help="Pehle se uploaded (usi target pe) bhi dobara upload karo")
    args = parser.parse_args(argv)

    try:
        registry, warnings = load_registry(args.pages)
    except (FileNotFoundError, ValueError) as e:
        log(f"FAIL: {e}")
        return 1
    for w in warnings:
        log(f"WARNING: {w}")

    if args.target and args.target not in registry:
        log(f"FAIL: --target '{args.target}' pages.json mein nahi hai. "
            f"Available: {', '.join(registry)}")
        return 1

    try:
        items = load_queue(args.queue, registry,
                           default_target=args.default_target)
    except (FileNotFoundError, ValueError) as e:
        log(f"FAIL: {e}")
        return 1

    if args.target:
        items = [i for i in items if i["target"] == args.target]
        if not items:
            log(f"Queue mein '{args.target}' ke liye koi video nahi hai.")
            return 1

    pending = pending_items(items, force=args.force)
    skipped = len(items) - len(pending)
    if args.limit:
        pending = pending[: args.limit]
    groups = group_by_target(pending)

    log(f"Queue: {len(items)} row(s) — {skipped} pehle se uploaded (per-target skip), "
        f"{len(pending)} pending")
    for tid, gitems in groups.items():
        entry = registry[tid]
        log(f"  [{tid}] {entry['platform']} — {entry.get('name', '')}: "
            f"{len(gitems)} video(s)")

    all_ok = True
    for item in pending:
        ok, errors = validate_item(item, registry)
        if not ok:
            all_ok = False
            log(f"FAIL: {item['file']} (target={item['target']})")
            for e in errors:
                log(f"  - {e}")

    if args.check:
        for tid in groups:
            entry = registry[tid]
            if entry["platform"] == "youtube":
                _, secrets, _ = auth_paths(entry)
                if not os.path.exists(secrets):
                    log(f"WARNING: [{tid}] client_secrets.json abhi nahi hai "
                        f"({secrets}) — asal upload se pehle chahiye hoga")
            else:
                tf = resolve_file(entry["token_file"])
                if not os.path.exists(tf):
                    log(f"WARNING: [{tid}] token file abhi nahi hai ({tf}) — "
                        "asal upload se pehle chahiye hogi")
        if all_ok:
            log(f"\nCHECK OK: {len(pending)} video(s) ready, "
                f"{len(groups)} target(s). Upload nahi hua, login nahi manga.")
        else:
            log("\nCHECK FAIL: upar wali ghaltiyan theek karo, phir dobara --check chalao.")
        return 0 if all_ok else 1

    if not all_ok:
        log("Validation fail — upload shuru nahi hua. Pehle --check chalao.")
        return 1
    for tid in groups:
        entry = registry[tid]
        if entry["platform"] == "facebook" and PLACEHOLDER_MARK in entry["page_id"]:
            log(f"FAIL: [{tid}] page_id abhi placeholder hai — asal Page ID "
                "bharo (GET /me/accounts se milegi), phir chalao.")
            return 1
    if not pending:
        log("Kuch upload karne ko nahi — sab pehle se uploaded hain (per target).")
        return 0

    ok_count, fail_count = 0, 0
    t0 = time.time()
    for tid, gitems in groups.items():
        entry = registry[tid]
        log(f"\n=== [{tid}] {entry['platform']} — {entry.get('name', '')} "
            f"({len(gitems)} video) ===")
        youtube = None  # Lazily initialized on the first video for this target.
        for idx, item in enumerate(gitems, 1):
            log(f"[{idx}/{len(gitems)}] {item['title']}")
            try:
                if entry["platform"] == "youtube":
                    if youtube is None:
                        youtube = get_youtube_service(entry)
                    vid = upload_one_youtube(youtube, item)
                    record_uploaded(item, vid, f"https://youtu.be/{vid}")
                    log(f"  OK: https://youtu.be/{vid}")
                else:
                    vid = upload_one_facebook(entry, item)
                    record_uploaded(item, vid, "")
                    log(f"  OK: facebook video_id {vid}")
                ok_count += 1
            except SystemExit:
                raise
            except Exception as e:  # noqa: BLE001 — aik fail ho to baaki chalte rahen
                log(f"  FAIL: {e}")
                record_failed(item, e)
                fail_count += 1
            if idx < len(gitems):
                time.sleep(SLEEP_BETWEEN)

    log(f"\nDone: {ok_count} OK, {fail_count} fail — {time.time() - t0:.0f}s")
    if fail_count:
        log("Fail hui videos state/failed-<target>.csv mein save hain.")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
