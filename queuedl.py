#!/usr/bin/env python3
"""Parallel queue downloader and channel grabber engine (invoked by app.py).

Runs `python -m yt_dlp` in subprocesses and emits flushed stdout protocol lines:
    QLOG <text>
    QITEM <i> START 0 | PROGRESS <pct> | DONE 100 | SKIPPED 100 | FAILED <pct>
    QDONE total=N done=N failed=N skipped=N
    GRABMETA <json>
    GRAB <url>
    GRABDONE <count>
"""
import argparse
import atexit
import concurrent.futures
import json
import os
import re
import signal
import subprocess
import sys
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DOWNLOADS = os.path.join(BASE_DIR, "downloads")
DEFAULT_ARCHIVE = os.path.join(BASE_DIR, "download_archive.txt")
QUALITY_CHOICES = [720, 1080, 1440, 2160]
DEFAULT_QUALITY = 2160
DEFAULT_THREADS = 4
MAX_ATTEMPTS = 2
OUTPUT_TEMPLATE = "%(extractor)s/%(uploader)s/%(title)s [%(id)s].%(ext)s"

_emit_lock = threading.Lock()


def emit(line):
    """Protocol line stdout pe — thread-safe + flush."""
    with _emit_lock:
        print(line, flush=True)


# Child process registry so active yt-dlp processes terminate on parent exit/signal.
_active_procs = set()
_procs_lock = threading.Lock()


def _register_proc(proc):
    with _procs_lock:
        _active_procs.add(proc)


def _unregister_proc(proc):
    with _procs_lock:
        _active_procs.discard(proc)


def _terminate_all():
    with _procs_lock:
        procs = list(_active_procs)
    for p in procs:
        try:
            p.terminate()
        except Exception:  # noqa: BLE001 — band karna hi maqsad hai
            pass


atexit.register(_terminate_all)


def _on_signal(signum, frame):  # noqa: ARG001 — signal signature
    _terminate_all()
    sys.exit(128 + signum if signum else 1)


def build_format(max_height):
    """yt-dlp format string — downloader.py wali hi semantics:
    max_height tak ki best video + best audio, warna best."""
    return f"bestvideo[height<={max_height}]+bestaudio/best[height<={max_height}]/best"


_PROGRESS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def parse_progress_line(line):
    """yt-dlp ki '[download] …%' line se percent (float) — warna None."""
    if not line:
        return None
    m = _PROGRESS_RE.search(str(line))
    if m is None:
        return None
    try:
        pct = float(m.group(1))
    except ValueError:
        return None
    return max(0.0, min(100.0, pct))


def load_queue_text(text):
    """Queue file ka text -> saaf URLs (app.extract_links wali semantics):
    blank + '#' lines skip, sirf http(s) lines, duplicates hata ke order waisa hi."""
    urls, seen = [], set()
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not (line.startswith("http://") or line.startswith("https://")):
            continue
        if line in seen:
            continue
        seen.add(line)
        urls.append(line)
    return urls


def _cookie_args(cookies_from_browser="", cookies_file=""):
    if cookies_from_browser:
        return ["--cookies-from-browser", cookies_from_browser]
    if cookies_file:
        return ["--cookies", cookies_file]
    return []


def _impersonate_args():
    """Use curl_cffi Chrome TLS impersonation if installed (required for TikTok anti-bot)."""
    import importlib.util
    if importlib.util.find_spec("curl_cffi") is not None:
        return ["--impersonate", "chrome"]
    return []


def build_download_cmd(url, quality=DEFAULT_QUALITY, downloads_dir=DEFAULT_DOWNLOADS,
                       archive=DEFAULT_ARCHIVE, cookies_from_browser="",
                       cookies_file="", proxy=""):
    """Aik URL ke liye poora yt-dlp command (subprocess list)."""
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--newline",
        "--no-playlist",
        "-f", build_format(quality),
        "--merge-output-format", "mp4",
        "--retries", "3",
        "--fragment-retries", "3",
        "--concurrent-fragments", "3",
        "--download-archive", archive,
        "-P", downloads_dir,
        "-o", OUTPUT_TEMPLATE,
        "--write-info-json",
        "--windows-filenames",
        "--trim-filenames", "120",
        "--no-warnings",
    ]
    cmd += _impersonate_args()
    cmd += _cookie_args(cookies_from_browser, cookies_file)
    if proxy:
        cmd += ["--proxy", proxy]
    cmd.append(url)
    return cmd


def build_grab_cmd(target, count=50, cookies_from_browser="",
                   cookies_file="", proxy=""):
    """Channel/profile list nikaalne ka flat-playlist command."""
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--flat-playlist",
        "--print", "url",
        "--playlist-end", str(count),
    ]
    cmd += _impersonate_args()
    cmd += _cookie_args(cookies_from_browser, cookies_file)
    if proxy:
        cmd += ["--proxy", proxy]
    cmd.append(target)
    return cmd


def channel_targets(url, grab_type):
    """Channel URL + type -> asal target URL(s) ki list.

    YouTube: base + /shorts ya /videos (URL pehle se suffixed ho to
    waisa hi). type 'all' -> [videos, shorts] (videos pehle).
    YouTube ke ilawa (Facebook waghera): URL jaisa hai waisa hi.
    """
    u = str(url or "").strip()
    if "youtube.com" not in u:
        return [u]
    base = u.rstrip("/")
    if base.endswith("/shorts") or base.endswith("/videos"):
        return [base]
    if grab_type == "shorts":
        return [base + "/shorts"]
    if grab_type == "all":
        return [base + "/videos", base + "/shorts"]
    return [base + "/videos"]


def popular_target(url):
    """Popular grab ke liye asal target URL.

    Bare YouTube channel URL (@handle, /channel/…, /c/…, /user/…,
    baghair /videos|/shorts|/streams suffix ke) -> +"/videos" (wahan
    saari videos ki list milti hai). Baaki sab — TikTok @account,
    Facebook page, playlist, pehle se suffixed channel — jaisa
    hai waisa hi.
    """
    u = str(url or "").strip()
    if "youtube.com" not in u:
        return u
    base = u.rstrip("/")
    if base.endswith(("/videos", "/shorts", "/streams")):
        return base
    if any(p in base for p in ("/@", "/channel/", "/c/", "/user/")):
        return base + "/videos"
    return u


_FB_SINGLE_RE = re.compile(
    r"/(?:reel|videos|watch|share|story\.php|permalink\.php)(?:/|\?|$)", re.I)


def is_fb_page_url(url):
    """True when url is a Facebook Page/Profile (not a single video/reel/watch/share link)."""
    u = str(url or "").strip().lower()
    if "facebook.com/" not in u and "fb.com/" not in u:
        return False
    return _FB_SINGLE_RE.search(u) is None


def _fb_fetch_html(url, proxy=""):
    """Fetch HTML using curl_cffi (Chrome impersonation) or urllib fallback."""
    try:
        from curl_cffi import requests as cffi_requests
        kwargs = {"impersonate": "chrome", "timeout": 20}
        if proxy:
            kwargs["proxies"] = {"http": proxy, "https": proxy}
        resp = cffi_requests.get(url, **kwargs)
        return resp.text if resp.status_code == 200 else ""
    except Exception:
        return ""


def _fb_extract_video_urls(html):
    """Extract unique Facebook watch URLs from page HTML/JSON."""
    t = (html or "").replace("\\/", "/")
    ids = []
    seen = set()
    for pat in (
        r"facebook\.com/reel/(\d+)",
        r"facebook\.com/[^/\"'?]+/videos/(\d+)",
        r'"video_id":"(\d+)"',
        r"watch/\?v=(\d+)",
    ):
        for vid in re.findall(pat, t):
            if vid not in seen:
                seen.add(vid)
                ids.append(f"https://www.facebook.com/watch/?v={vid}")
    return ids


def _fb_page_video_urls(url, grab_type="popular", count=50, proxy="", fetch_fn=None):
    """Fetch video/reel URLs from a public Facebook Page/Profile."""
    fetch_fn = fetch_fn or _fb_fetch_html
    base = str(url or "").strip().split("?", 1)[0].rstrip("/")
    if base.endswith("/reels") or base.endswith("/videos"):
        pages = [base + "/"]
    elif grab_type == "shorts":
        pages = [base + "/reels/"]
    elif grab_type == "videos":
        pages = [base + "/videos/", base + "/reels/"]
    else:
        pages = [base + "/reels/", base + "/videos/", base]

    collected, seen = [], set()
    for page in pages:
        html = fetch_fn(page, proxy=proxy)
        for vurl in _fb_extract_video_urls(html):
            if vurl not in seen:
                seen.add(vurl)
                collected.append(vurl)
                if len(collected) >= count:
                    return collected
    return collected


def popular_pool(count):
    """Popular grab kitni bari list uthaye (count se bari, taake
    views ke hisaab se chun sake): count*4, kam az kam 60, zyada
    se zyada 200."""
    return min(max(int(count) * 4, 60), 200)


def build_popular_pool_cmd(target, pool, cookies_from_browser="",
                           cookies_file="", proxy=""):
    """Popular grab step 1: flat-playlist ka single-JSON command
    (entries ke sath view_count bhi aata hai jahan available ho)."""
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--flat-playlist",
        "--dump-single-json",
        "--playlist-end", str(pool),
    ]
    cmd += _impersonate_args()
    cmd += _cookie_args(cookies_from_browser, cookies_file)
    if proxy:
        cmd += ["--proxy", proxy]
    cmd.append(target)
    return cmd


def build_popular_info_cmd(urls, cookies_from_browser="",
                           cookies_file="", proxy=""):
    """Popular grab step 2: chuni hui URLs ka full info (view_count
    ke liye) — aik hi yt-dlp call, har URL ki aik JSON line."""
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--dump-json",
        "--no-playlist",
    ]
    cmd += _impersonate_args()
    cmd += _cookie_args(cookies_from_browser, cookies_file)
    if proxy:
        cmd += ["--proxy", proxy]
    cmd += list(urls)
    return cmd


def _views_or_none(value):
    """view_count sirf asal number ho to rakho (bool/string nahi)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def parse_flat_entries(json_text):
    """--dump-single-json ka text -> [{"url":…, "views":…|None}].

    Har entry: url = webpage_url ya url (http se shuru hona
    chahiye, warna entry skip); views = view_count number ho to
    wo, warna None. Malformed JSON / entries na hon -> [].
    """
    try:
        data = json.loads(json_text or "")
    except (ValueError, TypeError):
        return []
    if not isinstance(data, dict):
        return []
    entries = data.get("entries")
    if not isinstance(entries, list):
        return []
    out = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        url = str(e.get("webpage_url") or e.get("url") or "").strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            continue
        out.append({"url": url, "views": _views_or_none(e.get("view_count"))})
    return out


def rank_popular(entries, count):
    """Entries ko views ke hisaab se rank karke top-count URLs do.

    Dedupe: aik URL kai dafa aye to SAB SE ZYADA views wala
    record jeet-ta hai. Sort views desc (None = -1, sab se
    neeche); barabar views pe pehle aya hua pehle (stable).
    """
    best, order = {}, []
    for e in entries or []:
        if not isinstance(e, dict):
            continue
        url = e.get("url")
        if not url:
            continue
        v = _views_or_none(e.get("views"))
        key = v if v is not None else -1
        if url not in best:
            best[url] = key
            order.append(url)
        elif key > best[url]:
            best[url] = key
    ranked = sorted(order, key=lambda u: -best[u])
    return ranked[:max(0, int(count))]


def parse_info_counts(text):
    """--dump-json (multi-URL) ka stdout -> {url: view_count}.

    Har line aik JSON object hoti hai; junk lines skip. URL
    webpage_url ya url se; view_count number lazmi. Duplicate
    URL pe sab se zyada views rakho.
    """
    counts = {}
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if not isinstance(data, dict):
            continue
        url = str(data.get("webpage_url") or data.get("url") or "").strip()
        views = _views_or_none(data.get("view_count"))
        if not url.startswith("http") or views is None:
            continue
        if url not in counts or views > counts[url]:
            counts[url] = views
    return counts


def parse_flat_meta(json_text):
    """--dump-single-json ka text -> {url: {"title": str, "views": int|float|None}}."""
    try:
        data = json.loads(json_text or "")
    except (ValueError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    entries = data.get("entries")
    if not isinstance(entries, list):
        return {}
    meta = {}
    for e in entries:
        if not isinstance(e, dict):
            continue
        url = str(e.get("webpage_url") or e.get("url") or "").strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            continue
        title = str(e.get("title") or "").strip()
        views = _views_or_none(e.get("view_count"))
        prev = meta.get(url)
        if prev is None:
            meta[url] = {"title": title, "views": views}
        else:
            if not prev["title"] and title:
                prev["title"] = title
            if views is not None and (prev["views"] is None or views > prev["views"]):
                prev["views"] = views
    return meta


def parse_info_meta(text):
    """--dump-json (multi-URL) ka stdout -> {url: {"title": str, "views": int|float|None}}."""
    meta = {}
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if not isinstance(data, dict):
            continue
        url = str(data.get("webpage_url") or data.get("url") or "").strip()
        if not url.startswith("http"):
            continue
        title = str(data.get("title") or "").strip()
        views = _views_or_none(data.get("view_count"))
        prev = meta.get(url)
        if prev is None:
            meta[url] = {"title": title, "views": views}
        else:
            if not prev["title"] and title:
                prev["title"] = title
            if views is not None and (prev["views"] is None or views > prev["views"]):
                prev["views"] = views
    return meta


def run_one(index, url, quality=DEFAULT_QUALITY, downloads_dir=DEFAULT_DOWNLOADS,
            archive=DEFAULT_ARCHIVE, cookies_from_browser="", cookies_file="",
            proxy="", emit_fn=None, popen_factory=None, on_missing=None):
    """Aik URL download karo (2 attempts tak). Returns (status, missing_module).

    status: "DONE" / "FAILED" / "SKIPPED". Protocol lines emit_fn se
    jati hain (default: module wali emit). popen_factory default
    subprocess.Popen hai — tests fake de sakte hain.
    """
    emit_fn = emit_fn or emit
    popen_factory = popen_factory or subprocess.Popen
    emit_fn(f"QITEM {index} START 0")
    missing = False
    last_pct = 0
    for attempt in range(MAX_ATTEMPTS):
        cmd = build_download_cmd(
            url, quality=quality, downloads_dir=downloads_dir, archive=archive,
            cookies_from_browser=cookies_from_browser,
            cookies_file=cookies_file, proxy=proxy)
        proc = popen_factory(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, encoding="utf-8", errors="replace")
        _register_proc(proc)
        skipped = False
        reported = -1
        attempt_pct = 0
        errors = []
        try:
            for line in proc.stdout:
                if "has already been recorded in the archive" in line:
                    skipped = True
                if "No module named yt_dlp" in line:
                    missing = True
                    if on_missing is not None:
                        on_missing()
                s_line = line.strip()
                if s_line.startswith("ERROR:"):
                    errors.append(s_line)
                pct = parse_progress_line(line)
                if pct is not None:
                    attempt_pct = max(attempt_pct, int(pct))
                    ipct = int(pct)
                    if ipct - reported >= 5 or (ipct == 100 and ipct != reported):
                        emit_fn(f"QITEM {index} PROGRESS {ipct}")
                        reported = ipct
            rc = proc.wait()
        finally:
            _unregister_proc(proc)
        last_pct = attempt_pct
        if skipped:
            emit_fn(f"QITEM {index} SKIPPED 100")
            return "SKIPPED", missing
        if rc == 0:
            emit_fn(f"QITEM {index} DONE 100")
            return "DONE", missing
        for err in errors[-2:]:
            emit_fn(f"QLOG yt-dlp: {err}")
        if attempt + 1 < MAX_ATTEMPTS:
            emit_fn(f"QLOG Item {index + 1}: pehli koshish fail — "
                    f"dobara try kar raha hoon ({url})")
    emit_fn(f"QITEM {index} FAILED {last_pct}")
    return "FAILED", missing


def run_grab(url, grab_type="videos", count=50, cookies_from_browser="",
             cookies_file="", proxy="", emit_fn=None, popen_factory=None):
    """Channel/profile se links nikaalo. Returns (urls, ok).

    Saare targets kamyab hon tab hi GRAB lines emit hoti hain —
    koi target fail ho to GRABDONE 0 + QLOG error, ok=False.
    """
    emit_fn = emit_fn or emit
    popen_factory = popen_factory or subprocess.Popen
    count = max(1, min(500, int(count)))
    collected, seen = [], set()
    errors = []
    for target in channel_targets(url, grab_type):
        cmd = build_grab_cmd(
            target, count=count,
            cookies_from_browser=cookies_from_browser,
            cookies_file=cookies_file, proxy=proxy)
        proc = popen_factory(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, encoding="utf-8", errors="replace")
        _register_proc(proc)
        try:
            for line in proc.stdout:
                s = line.strip()
                if s.startswith("http") and s not in seen:
                    seen.add(s)
                    collected.append(s)
                elif "ERROR:" in s or "Could not copy" in s:
                    errors.append(s)
            rc = proc.wait()
        finally:
            _unregister_proc(proc)
        if rc != 0:
            if is_fb_page_url(url):
                fb_urls = _fb_page_video_urls(
                    url, grab_type="popular" if grab_type == "all" else grab_type,
                    count=count, proxy=proxy)
                if fb_urls:
                    for u in fb_urls:
                        emit_fn(f"GRAB {u}")
                    emit_fn(f"GRABDONE {len(fb_urls)}")
                    return fb_urls, True
            for err in errors[-3:]:
                emit_fn(f"QLOG yt-dlp: {err}")
            if any("Could not copy" in e and "cookie" in e for e in errors):
                emit_fn("QLOG Tip: Browser (Chrome/Edge) khula hua hai — browser band karo ya Cookies dropdown ko 'None' pe rakho.")
            if "facebook.com" in target.lower() and any("Unsupported URL" in e for e in errors):
                emit_fn("QLOG Facebook Page/Profile ki video list yt-dlp support nahi karta (sirf direct Facebook video/reel links download hoti hain — Section 1 me paste karo).")
            emit_fn(f"QLOG Grab fail ho gaya: {target} "
                    f"(yt-dlp exit {rc}) — link check karo, ya cookies try karo.")
            emit_fn("GRABDONE 0")
            return [], False
    for u in collected:
        emit_fn(f"GRAB {u}")
    emit_fn(f"GRABDONE {len(collected)}")
    return collected, True


def run_popular(url, count=50, cookies_from_browser="", cookies_file="",
                proxy="", emit_fn=None, popen_factory=None):
    """Popular grab: account/channel ki SAB SE ZYADA views wali
    top-count videos. Returns (urls, ok).

    Step 1: bari flat list (pool) + view_count. Views mil jayein
    to unhi se rank. Na milen to step 2: pehli 40 videos ka full
    info le ke views wahan se. Phir bhi na milen to pehli count
    videos asal order mein (warning QLOG ke sath). Step 1 hi
    fail/empty ho to GRABDONE 0, ok=False.
    """
    emit_fn = emit_fn or emit
    popen_factory = popen_factory or subprocess.Popen
    count = max(1, min(500, int(count)))
    target = popular_target(url)

    def _run_collect(cmd):
        proc = popen_factory(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, encoding="utf-8", errors="replace")
        _register_proc(proc)
        chunks = []
        errors = []
        try:
            for line in proc.stdout:
                chunks.append(line)
                s = line.strip()
                if "ERROR:" in s or "Could not copy" in s:
                    errors.append(s)
            rc = proc.wait()
        finally:
            _unregister_proc(proc)
        return "".join(chunks), rc, errors

    # Step 1: fetch flat playlist pool with view counts where available.
    pool_cmd = build_popular_pool_cmd(
        target, popular_pool(count),
        cookies_from_browser=cookies_from_browser,
        cookies_file=cookies_file, proxy=proxy)
    text, rc, errors = _run_collect(pool_cmd)
    entries = parse_flat_entries(text)
    meta_map = parse_flat_meta(text)
    if (rc != 0 or not entries) and is_fb_page_url(url):
        fb_urls = _fb_page_video_urls(
            url, grab_type="popular", count=popular_pool(count), proxy=proxy)
        if fb_urls:
            entries = [{"url": u, "views": None} for u in fb_urls]
            meta_map = {}
            rc = 0
    if rc != 0 or not entries:
        for err in errors[-3:]:
            emit_fn(f"QLOG yt-dlp: {err}")
        if any("Could not copy" in e and "cookie" in e for e in errors):
            emit_fn("QLOG Tip: Browser (Chrome/Edge) khula hua hai — browser band karo ya Cookies dropdown ko 'None' pe rakho.")
        if "facebook.com" in target.lower() and any("Unsupported URL" in e for e in errors):
            emit_fn("QLOG Facebook Page/Profile ki video list yt-dlp support nahi karta (sirf direct Facebook video/reel links download hoti hain — Section 1 me paste karo).")
        emit_fn(f"QLOG Popular grab fail ho gaya: {target} "
                f"(yt-dlp exit {rc}) — link check karo, ya cookies try karo.")
        emit_fn("GRABDONE 0")
        return [], False

    def _emit_ranked(ranked, note):
        for u in ranked:
            m = meta_map.get(u)
            if m and (m.get("title") or m.get("views") is not None):
                emit_fn("GRABMETA " + json.dumps(
                    {"url": u, "title": m.get("title", ""),
                     "views": m.get("views")}, ensure_ascii=False))
            emit_fn(f"GRAB {u}")
        emit_fn(note)
        emit_fn(f"GRABDONE {len(ranked)}")
        return ranked, True

    if any(e["views"] is not None for e in entries):
        ranked = rank_popular(entries, count)
        return _emit_ranked(
            ranked,
            f"QLOG Popular: kul {len(entries)} videos mili, "
            f"top {len(ranked)} views ke hisaab se queue me")

    # Step 2: flat listing lacked view counts; fetch full info for the first 40 URLs.
    first_urls = []
    seen = set()
    for e in entries:
        if e["url"] not in seen:
            seen.add(e["url"])
            first_urls.append(e["url"])
    info_cmd = build_popular_info_cmd(
        first_urls[:40],
        cookies_from_browser=cookies_from_browser,
        cookies_file=cookies_file, proxy=proxy)
    info_text, _info_rc, _info_errors = _run_collect(info_cmd)
    counts = parse_info_counts(info_text)
    for u, im in parse_info_meta(info_text).items():
        cur = meta_map.setdefault(u, {"title": "", "views": None})
        if not cur["title"] and im.get("title"):
            cur["title"] = im["title"]
        if im.get("views") is not None and (cur["views"] is None or im["views"] > cur["views"]):
            cur["views"] = im["views"]
    if counts:
        ranked = rank_popular(
            [{"url": u, "views": v} for u, v in counts.items()], count)
        return _emit_ranked(
            ranked,
            f"QLOG Popular: views dusri koshish me mile, "
            f"top {len(ranked)} queue me")

    # Fallback: no view counts available anywhere; preserve original order.
    fallback = first_urls[:count]
    if "facebook.com" in url.lower():
        note = "QLOG FB pe views nahi mile, latest videos liye hain"
    else:
        note = (f"QLOG Views ka data nahi mila — pehli {len(fallback)} "
                f"videos asal order me queue me")
    return _emit_ranked(fallback, note)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Parallel queue downloader + channel grabber "
                    "(GUI ka engine — protocol lines stdout pe)")
    parser.add_argument("queue_file", nargs="?", default=None,
                        help="Queue file (aik line = aik URL) — queue mode ke liye")
    parser.add_argument("--quality", type=int, choices=QUALITY_CHOICES,
                        default=DEFAULT_QUALITY,
                        help="2160=4K (default), 1440=2K, 1080, 720")
    parser.add_argument("--threads", type=int, default=DEFAULT_THREADS,
                        help="Aik sath kitni downloads (1-16, default 4)")
    parser.add_argument("--downloads", default=DEFAULT_DOWNLOADS,
                        help="Downloads is folder mein (default: project downloads/)")
    parser.add_argument("--archive", default=DEFAULT_ARCHIVE,
                        help="download_archive file (jo ho gaya wo dobara nahi)")
    parser.add_argument("--cookies-file", default="",
                        help="cookies.txt ka path (login wali videos ke liye)")
    parser.add_argument("--cookies-from-browser", default="",
                        help="chrome / edge / firefox — browser ke cookies use karo")
    parser.add_argument("--proxy", default="", help="Proxy URL (optional)")
    parser.add_argument("--grab", default="",
                        help="Grab mode: channel/profile ka URL do")
    parser.add_argument("--grab-type", default="videos",
                        choices=["shorts", "videos", "all", "popular"],
                        help="YouTube channel pe konsi list (default videos); "
                             "popular = sab se zyada views wali top-N")
    parser.add_argument("--count", type=int, default=50,
                        help="Grab mode: zyada se zyada kitne links (1-500, default 50)")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _on_signal)
        except (ValueError, OSError):
            pass  # Fails if not called on the main thread.

    common = dict(
        cookies_from_browser=args.cookies_from_browser,
        cookies_file=args.cookies_file, proxy=args.proxy)

    if args.grab:
        if args.grab_type == "popular":
            _, ok = run_popular(args.grab, count=args.count, **common)
        else:
            _, ok = run_grab(args.grab, grab_type=args.grab_type,
                             count=args.count, **common)
        return 0 if ok else 1

    if not args.queue_file:
        emit("QLOG Queue file nahi di — queuedl.py QUEUE_FILE ya --grab URL do.")
        emit("QDONE total=0 done=0 failed=0 skipped=0")
        return 1
    if not os.path.exists(args.queue_file):
        emit(f"QLOG Queue file nahi mili: {args.queue_file}")
        emit("QDONE total=0 done=0 failed=0 skipped=0")
        return 1
    with open(args.queue_file, encoding="utf-8") as f:
        urls = load_queue_text(f.read())
    threads = max(1, min(16, args.threads))
    os.makedirs(args.downloads, exist_ok=True)
    emit(f"QLOG Queue: {len(urls)} link(s), threads={threads}")

    missing_state = {"announced": False}
    missing_lock = threading.Lock()

    def announce_missing():
        with missing_lock:
            if missing_state["announced"]:
                return
            missing_state["announced"] = True
        emit("QLOG yt-dlp nahi mila. Pehle chalao: pip install -r requirements.txt")

    done = failed = skipped = 0
    if urls:
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as pool:
            futures = [
                pool.submit(
                    run_one, i, url, quality=args.quality,
                    downloads_dir=args.downloads, archive=args.archive,
                    on_missing=announce_missing, **common)
                for i, url in enumerate(urls)
            ]
            for fut in concurrent.futures.as_completed(futures):
                status, _ = fut.result()
                if status == "DONE":
                    done += 1
                elif status == "SKIPPED":
                    skipped += 1
                else:
                    failed += 1
    emit(f"QDONE total={len(urls)} done={done} failed={failed} skipped={skipped}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
