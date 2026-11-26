#!/usr/bin/env python3
"""Bulk downloader using yt-dlp + FFmpeg."""
import argparse
import concurrent.futures
import os
import sys
import threading
import time

try:
    import yt_dlp
except ImportError:
    sys.exit("yt-dlp nahi mila. Pehle chalao:  pip install yt-dlp")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
URLS_FILE = os.path.join(BASE_DIR, "urls.txt")
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
ARCHIVE_FILE = os.path.join(BASE_DIR, "download_archive.txt")

QUALITY_CHOICES = [720, 1080, 1440, 2160]
DEFAULT_QUALITY = 2160
RETRIES = 3
FRAGMENT_RETRIES = 3
CONCURRENT_FRAGMENTS = 3
MAX_WORKERS = 3
SLEEP_BETWEEN = 5

_print_lock = threading.Lock()


def log(msg):
    with _print_lock:
        print(msg, flush=True)


def build_format(max_height):
    """yt-dlp format string — max_height tak ki best video + best audio,
    warna us se neeche ki best. Source me jo best available hai wahi
    milegi (upscale nahi hota)."""
    return f"bestvideo[height<={max_height}]+bestaudio/best[height<={max_height}]/best"


def load_urls(path):
    """urls.txt se queue parho — blank lines aur # comments skip karo, duplicates hatao."""
    if not os.path.exists(path):
        sys.exit(f"urls.txt nahi mili: {path}\nPehle urls.txt me aik line pe aik URL likho.")
    seen, urls = set(), []
    with open(path, encoding="utf-8") as f:
        for line in f:
            url = line.strip()
            if not url or url.startswith("#"):
                continue
            if url not in seen:
                seen.add(url)
                urls.append(url)
    if not urls:
        sys.exit("urls.txt khaali hai — koi URL nahi mila.")
    return urls


def make_progress_hook(tag):
    def hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            done = d.get("downloaded_bytes", 0)
            pct = f"{done * 100 / total:5.1f}%" if total else "  ?  "
            speed = d.get("speed")
            speed_s = f"{speed / 1024:.0f} KiB/s" if speed else ""
            log(f"[{tag}] {pct} {d.get('filename', '')} {speed_s}")
        elif d["status"] == "finished":
            log(f"[{tag}] DONE: {os.path.basename(d.get('filename', ''))}")
        elif d["status"] == "error":
            log(f"[{tag}] ERROR")
    return hook


def download_one(args):
    """Aik URL download karo. Worker index se alag archive file, end pe merge hoti hai."""
    idx, url, dry_run, fmt, downloads_dir = args
    worker = idx % MAX_WORKERS
    archive = os.path.join(BASE_DIR, f".archive_{worker}.txt")
    tag = f"worker-{worker + 1} #{idx + 1}"

    ydl_opts = {
        "format": fmt,
        "outtmpl": os.path.join(downloads_dir, "%(extractor)s", "%(uploader)s",
                                "%(title)s [%(id)s].%(ext)s"),
        "restrictfilenames": False,
        "windowsfilenames": True,
        "trim_file_name": 120,
        "retries": RETRIES,
        "fragment_retries": FRAGMENT_RETRIES,
        "concurrent_fragments": CONCURRENT_FRAGMENTS,
        "sleep_interval": SLEEP_BETWEEN,
        "download_archive": archive,
        "continuedl": True,
        "noplaylist": True,
        "progress_hooks": [make_progress_hook(tag)],
        "quiet": True,
        "no_warnings": True,
    }
    if dry_run:
        ydl_opts["simulate"] = True
        ydl_opts["skip_download"] = True

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=not dry_run)
            title = (info or {}).get("title", url)
        log(f"[{tag}] OK: {title}")
        return (url, True, "")
    except Exception as e:  # noqa: BLE001 — aik video fail ho to baaki chalte rahen
        log(f"[{tag}] FAIL: {url} — {e}")
        return (url, False, str(e))


def merge_archives():
    """Worker archives ko aik download_archive.txt me mila do (unique lines)."""
    seen, lines = set(), []
    for w in range(MAX_WORKERS):
        p = os.path.join(BASE_DIR, f".archive_{w}.txt")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                for line in f:
                    if line not in seen:
                        seen.add(line)
                        lines.append(line)
            os.remove(p)
    if os.path.exists(ARCHIVE_FILE):
        with open(ARCHIVE_FILE, encoding="utf-8") as f:
            for line in f:
                if line not in seen:
                    seen.add(line)
                    lines.append(line)
    if lines:
        with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Apna Bulk Downloader V1")
    parser.add_argument("--dry-run", action="store_true",
                        help="Sirf check karo — kuch download nahi hoga")
    parser.add_argument("--quality", type=int, choices=QUALITY_CHOICES,
                        default=DEFAULT_QUALITY,
                        help="Download quality (max height): 2160=4K (default), "
                             "1440=2K, 1080, 720 — bari quality = bari file, slow download")
    parser.add_argument("--format", default=None,
                        help="yt-dlp format override — ye diya jaye to --quality ignore "
                             "hota hai. Test ke liye 'worst' bhi de sakte ho.")
    parser.add_argument("--urls", default=URLS_FILE, help="Queue file (default: urls.txt)")
    parser.add_argument("--downloads", default=DOWNLOADS_DIR,
                        help="Downloads is folder me jayengi "
                             "(default: project ka downloads/ folder)")
    return parser.parse_args(argv)


def main():
    args = parse_args()

    fmt = args.format if args.format else build_format(args.quality)

    os.makedirs(args.downloads, exist_ok=True)
    urls = load_urls(args.urls)
    log(f"Queue: {len(urls)} URL(s) — max {MAX_WORKERS} concurrent, {RETRIES} retries")
    log(f"Download folder: {args.downloads}")
    if args.format:
        log(f"Quality: custom --format override use ho raha hai: {args.format}")
    else:
        log(f"Quality: {args.quality}p (max height {args.quality})")
    if args.dry_run:
        log("DRY RUN — kuch download nahi hoga")

    t0 = time.time()
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        jobs = [(i, u, args.dry_run, fmt, args.downloads) for i, u in enumerate(urls)]
        results = list(pool.map(download_one, jobs))

    if not args.dry_run:
        merge_archives()

    ok = sum(1 for _, s, _ in results if s)
    failed = [(u, e) for u, s, e in results if not s]
    log(f"\nDone: {ok}/{len(urls)} OK, {len(failed)} fail — {time.time() - t0:.0f}s")
    if failed:
        log("Fail hui URLs (dobara urls.txt me daal ke retry kar sakte ho):")
        for u, e in failed:
            log(f"  - {u}")
        with open(os.path.join(BASE_DIR, "failed.txt"), "w", encoding="utf-8") as f:
            f.writelines(u + "\n" for u, _ in failed)
        log("failed.txt me save kar di hain.")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
