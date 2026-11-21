#!/usr/bin/env python3
"""
Queue Downloader + Channel Grabber — SkillNova style (personal use only)
=========================================================================
GUI (app.py) ke naye queue system ka engine. Do kaam:

1. QUEUE MODE — aik queue file se saari videos PARALLEL download:
       python queuedl.py gui_queue.txt --quality 2160 --threads 4 \
           --downloads <folder> --archive download_archive.txt
   Har video ka apna `python -m yt_dlp` subprocess chalta hai
   (yt-dlp import NAHI hota — is liye ye script baghair yt-dlp ke
   bhi start ho jati hai aur saaf error deti hai).

2. GRAB MODE — channel/profile se video links nikaal ke stdout pe:
       python queuedl.py --grab https://www.youtube.com/@channel \
           --grab-type shorts --count 50
   YouTube channel pe /shorts ya /videos list uthata hai
   (--grab-type all = dono, pehle videos phir shorts). Doosri
   sites (Facebook page waghera) pe URL jaisa hai waisa use hota hai.
   --grab-type popular: pehle bari list (pool) uthata hai, har
   video ke views gin ke SIRF sab se zyada views wali top-N
   queue mein deta hai (TikTok account ke liye khaas taur pe).

Machine-readable protocol (har line flush hoti hai, GUI yehi parhti hai):
    QLOG <text>                    insaani log line
    QITEM <i> START 0              item i shuru
    QITEM <i> PROGRESS <pct>       progress (har >=5% change ya 100 pe)
    QITEM <i> DONE 100             ho gaya
    QITEM <i> SKIPPED 100          archive mein pehle se tha
    QITEM <i> FAILED <last pct>    2 koshishon ke baad bhi fail
    QDONE total=N done=N failed=N skipped=N
    GRAB <url>                     grab mode: aik link mila
    GRABDONE <count>               grab khatam

Cookies / proxy (login wali ya mushkil sites ke liye):
    --cookies-from-browser chrome|edge|firefox
    --cookies-file cookies.txt
    --proxy http://host:port

Sirf apne / licensed content ke liye.
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
MAX_ATTEMPTS = 2  # har URL: pehli koshish + aik retry
# SkillNova wali folder tartib (transcript [06:18-06:51]: pehle platform ka
# folder, phir us ke andar channel/page ke naam ka folder):
#   downloads/youtube/<channel>/Title [id].mp4
#   downloads/TikTok/<account>/Title [id].mp4
# %(extractor)s = youtube / TikTok / Facebook / Instagram waghera,
# %(uploader)s = channel ya page ka naam. --windows-filenames naam ko
# Windows-safe rakhta hai. --write-info-json se pipeline --check in
# downloads ko bhi upload queue mein le sakta hai.
OUTPUT_TEMPLATE = "%(extractor)s/%(uploader)s/%(title)s [%(id)s].%(ext)s"

_emit_lock = threading.Lock()


def emit(line):
    """Protocol line stdout pe — thread-safe + flush."""
    with _emit_lock:
        print(line, flush=True)


# ---------------------------------------------------------------------------
# Child process registry — parent band ho to bachay bhi band
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Pure helpers (tests inhi ko check karte hain — koi network/subprocess nahi)
# ---------------------------------------------------------------------------
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
        "--no-warnings",
    ]
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

    Bare YouTube channel URL (@handle ya /channel/…, baghair
    /videos|/shorts|/streams suffix ke) -> +"/videos" (wahan
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
    if "/@" in base or "/channel/" in base:
        return base + "/videos"
    return u


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


# ---------------------------------------------------------------------------
# Runners (popen_factory injectable hai — tests fake laga sakte hain)
# ---------------------------------------------------------------------------
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
            text=True, bufsize=1)
        _register_proc(proc)
        skipped = False
        reported = -1  # is attempt mein aakhri report shuda pct
        attempt_pct = 0
        try:
            for line in proc.stdout:
                if "has already been recorded in the archive" in line:
                    skipped = True
                if "No module named yt_dlp" in line:
                    missing = True
                    if on_missing is not None:
                        on_missing()
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
    for target in channel_targets(url, grab_type):
        cmd = build_grab_cmd(
            target, count=count,
            cookies_from_browser=cookies_from_browser,
            cookies_file=cookies_file, proxy=proxy)
        proc = popen_factory(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1)
        _register_proc(proc)
        try:
            for line in proc.stdout:
                s = line.strip()
                if s.startswith("http") and s not in seen:
                    seen.add(s)
                    collected.append(s)
            rc = proc.wait()
        finally:
            _unregister_proc(proc)
        if rc != 0:
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
            text=True, bufsize=1)
        _register_proc(proc)
        chunks = []
        try:
            for line in proc.stdout:
                chunks.append(line)
            rc = proc.wait()
        finally:
            _unregister_proc(proc)
        return "".join(chunks), rc

    # ---- step 1: pool + flat view_count ----
    pool_cmd = build_popular_pool_cmd(
        target, popular_pool(count),
        cookies_from_browser=cookies_from_browser,
        cookies_file=cookies_file, proxy=proxy)
    text, rc = _run_collect(pool_cmd)
    entries = parse_flat_entries(text)
    if rc != 0 or not entries:
        emit_fn(f"QLOG Popular grab fail ho gaya: {target} "
                f"(yt-dlp exit {rc}) — link check karo, ya cookies try karo.")
        emit_fn("GRABDONE 0")
        return [], False

    def _emit_ranked(ranked, note):
        for u in ranked:
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

    # ---- step 2: pehli 40 ka full info (view_count ke liye) ----
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
    info_text, _info_rc = _run_collect(info_cmd)
    counts = parse_info_counts(info_text)
    if counts:
        ranked = rank_popular(
            [{"url": u, "views": v} for u, v in counts.items()], count)
        return _emit_ranked(
            ranked,
            f"QLOG Popular: views dusri koshish me mile, "
            f"top {len(ranked)} queue me")

    # ---- fallback: views ka data hi nahi — asal order ----
    fallback = first_urls[:count]
    return _emit_ranked(
        fallback,
        f"QLOG Views ka data nahi mila — pehli {len(fallback)} "
        f"videos asal order me queue me")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
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
            pass  # main thread na ho to signal nahi lag sakta — koi baat nahi

    common = dict(
        cookies_from_browser=args.cookies_from_browser,
        cookies_file=args.cookies_file, proxy=args.proxy)

    # ---- grab mode ----
    if args.grab:
        if args.grab_type == "popular":
            _, ok = run_popular(args.grab, count=args.count, **common)
        else:
            _, ok = run_grab(args.grab, grab_type=args.grab_type,
                             count=args.count, **common)
        return 0 if ok else 1

    # ---- queue mode ----
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
