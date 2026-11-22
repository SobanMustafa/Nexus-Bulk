#!/usr/bin/env python3
"""
End-to-End Pipeline — Downloader V1 + Uploader V2 (personal use only)
======================================================================
Soban ka glue script: V1 aur V2 alag alag ready thay, beech mein yehi
missing tha. Aik hi command — URL daalo, video upload ho jaye.

Flow:
    urls.txt
      -> yt-dlp download (V1 wali settings: quality selectable,
         default 2160 = 4K; 3 retries, 5s sleep, download_archive)
         + .info.json metadata save
      -> downloads/ scan: har video + uski .info.json se
         title / description / tags / category nikalo
      -> uploads.csv auto-build (uploader V2 ke format mein)
      -> uploader.py chalao (default privacy: private)

Kyun sequential hai (V1 ke 3-parallel ki tarah nahi):
  upload waise bhi aik ke baad aik hota hai, aur aik video download
  karte hi uska metadata pair karna exact rehta hai — parallel mein
  video aur .info.json ka pair ulajh sakta hai.

Chalana (Windows laptop — PowerShell, is folder se):
    pip install -r requirements.txt        # yt-dlp + Google libs
    python pipeline.py --check             # pehle check: downloads/ se
                                           # uploads.csv banao + uploader
                                           # --check chalao (NO upload,
                                           # NO login, NO download)
    python pipeline.py --download-only     # sirf download + uploads.csv
    python pipeline.py --upload-only       # pehle se download hui videos
                                           # se uploads.csv + upload
    python pipeline.py                     # poora end-to-end
    python pipeline.py --limit 1           # pehle sirf 1 video se test
    python pipeline.py --privacy unlisted  # default private hai
    python pipeline.py --quality 1440      # 2K download (default 2160 = 4K hai)

Pehli dafa setup (sirf aik dafa, laptop pe):
  1. README.md ke YouTube setup (7 steps): Google Cloud project +
     YouTube Data API v3 + OAuth client ID (Desktop app) ->
     client_secrets.json isi project folder mein rakho.
  2. FFmpeg chahiye (video+audio merge ke liye): winget install Gyan.FFmpeg
  3. python pipeline.py --limit 1 --download-only se pehla download
     test karo, phir python pipeline.py --limit 1 se pehli upload
     (private) test karo.

Caveats (pehle se verified, 2026-11-18):
  - Quota: videos.insert = 100 uploads/day (Google docs).
  - Unverified API project se upload ki hui videos private hi rehti
    hain jab tak project audit na ho — pipeline ke baad bhi.
  - client_secrets.json / token.json KISI ko mat bhejo, GitHub pe
    mat daalo.
  - Sirf apne / licensed content ke liye — doosron ke videos
    re-upload karne ke liye nahi.
"""
import argparse
import csv
import json
import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Defaults: flat layout — sab kuch project root (isi folder) mein hai.
# Override flags se badal sakte ho.
DEFAULT_URLS = os.path.join(BASE_DIR, "urls.txt")
DEFAULT_DOWNLOADS = os.path.join(BASE_DIR, "downloads")
DEFAULT_UPLOADER_DIR = BASE_DIR
DEFAULT_ARCHIVE = os.path.join(BASE_DIR, "download_archive.txt")

QUALITY_CHOICES = [720, 1080, 1440, 2160]
DEFAULT_QUALITY = 2160  # 4K — selectable: 720 / 1080 / 1440 (2K) / 2160 (4K)
RETRIES = 3
SLEEP_BETWEEN = 5
MAX_TITLE = 100
MAX_DESCRIPTION = 5000
MAX_TAGS_LEN = 500
DEFAULT_CATEGORY = "22"  # People & Blogs (uploader V2 wala default)
DEFAULT_PRIVACY = "private"
VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")

# yt-dlp "categories" (info.json) -> YouTube category_id
CATEGORY_MAP = {
    "Film & Animation": "1",
    "Autos & Vehicles": "2",
    "Music": "10",
    "Pets & Animals": "15",
    "Sports": "17",
    "Travel & Events": "19",
    "Gaming": "20",
    "People & Blogs": "22",
    "Comedy": "23",
    "Entertainment": "24",
    "News & Politics": "25",
    "Howto & Style": "26",
    "Education": "27",
    "Science & Technology": "28",
    "Nonprofits & Activism": "29",
}


def log(msg):
    print(msg, flush=True)


def build_format(max_height):
    """yt-dlp format string — max_height tak ki best video + best audio,
    warna us se neeche ki best. Source me jo best available hai wahi
    milegi (upscale nahi hota)."""
    return f"bestvideo[height<={max_height}]+bestaudio/best[height<={max_height}]/best"


def load_urls(path):
    """urls.txt — blank lines, # comments aur duplicates skip (V1 jaisa)."""
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


def find_video_for_info(info_path, downloads_dir):
    """<name>.info.json ke saath wali video file dhoondo (.mp4 pehle)."""
    base = info_path[: -len(".info.json")]
    for ext in VIDEO_EXTS:
        cand = base + ext
        if os.path.exists(cand):
            return cand
    # Fallback: .info.json wali folder mein same stem se shuru hone wali koi video file
    stem = os.path.basename(base)
    info_dir = os.path.dirname(info_path)
    for name in sorted(os.listdir(info_dir)):
        if name.startswith(stem) and name.lower().endswith(VIDEO_EXTS):
            return os.path.join(info_dir, name)
    return None


def clean_tags(raw_tags):
    """info.json tags -> 'a|b|c', total max 500 chars (uploader limit)."""
    tags = []
    for t in (raw_tags or []):
        t = str(t).strip()
        if t and t not in tags:
            tags.append(t)
    out = []
    total = 0
    for t in tags:
        add = len(t) + (1 if out else 0)
        if total + add > MAX_TAGS_LEN:
            break
        out.append(t)
        total += add
    return "|".join(out)


def map_category(categories):
    for c in (categories or []):
        if c in CATEGORY_MAP:
            return CATEGORY_MAP[c]
    return DEFAULT_CATEGORY


def info_to_row(info, video_path, privacy):
    """Aik .info.json + video -> uploads.csv ki aik row (uploader limits mein)."""
    title = (info.get("title") or "").strip()
    if not title:
        title = os.path.splitext(os.path.basename(video_path))[0]
        # V1 outtmpl "... [id].ext" se [id] hata do
        if " [" in title and title.endswith("]"):
            title = title[: title.rfind(" [")]
    if len(title) > MAX_TITLE:
        title = title[:MAX_TITLE].rstrip()
    description = (info.get("description") or "").strip()[:MAX_DESCRIPTION]
    return {
        "file": os.path.abspath(video_path),
        "title": title,
        "description": description,
        "tags": clean_tags(info.get("tags")),
        "category_id": map_category(info.get("categories")),
        "privacy": privacy,
    }


def load_uploaded_set(uploader_dir):
    """uploaded.csv mein pehle se upload hui files — dobara upload nahi."""
    done = set()
    path = os.path.join(uploader_dir, "uploaded.csv")
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("file"):
                    done.add(row["file"])
                    done.add(os.path.abspath(row["file"]))
                    done.add(os.path.basename(row["file"]))
    return done


def build_uploads_csv(downloads_dir, privacy, uploader_dir):
    """downloads/ mein har video + .info.json -> uploads.csv rows."""
    if not os.path.isdir(downloads_dir):
        return [], [f"downloads folder nahi mila: {downloads_dir}"]
    done = load_uploaded_set(uploader_dir)
    rows, problems = [], []
    # Recursive scan — downloads ab <platform>/<channel>/ subfolders mein
    # hote hain (SkillNova wali tartib), sirf top level nahi.
    infos = sorted(
        os.path.join(root, f)
        for root, _dirs, files in os.walk(downloads_dir)
        for f in files if f.endswith(".info.json")
    )
    for info_path in infos:
        name = os.path.basename(info_path)
        try:
            with open(info_path, encoding="utf-8") as f:
                info = json.load(f)
        except Exception as e:  # noqa: BLE001 — kharab json wali entry skip
            problems.append(f"{name}: info.json parh nahi saka — {e}")
            continue
        video = find_video_for_info(info_path, downloads_dir)
        if not video:
            problems.append(f"{name}: video file nahi mili (sirf .info.json hai)")
            continue
        if video in done or os.path.abspath(video) in done or os.path.basename(video) in done:
            continue  # pehle se uploaded — skip
        rows.append(info_to_row(info, video, privacy))
    # Videos jin ki .info.json hi nahi — user ko batao, silently skip nahi
    known = {os.path.splitext(os.path.basename(n)[: -len(".info.json")])[0]
             for n in infos}
    for root, _dirs, files in os.walk(downloads_dir):
        for name in sorted(files):
            if name.lower().endswith(VIDEO_EXTS):
                stem = os.path.splitext(name)[0]
                if stem not in known and not any(
                    r["file"].endswith(name) for r in rows
                ):
                    problems.append(
                        f"{name}: .info.json nahi mili — dobara download karo "
                        f"ya --upload-only se pehle metadata banao"
                    )
    return rows, problems


def write_uploads_csv(rows, uploader_dir):
    """Rows -> project root ki uploads.csv (uploader ka format, header same)."""
    path = os.path.join(uploader_dir, "uploads.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "title", "description", "tags", "category_id", "privacy"])
        for r in rows:
            w.writerow([r["file"], r["title"], r["description"],
                        r["tags"], r["category_id"], r["privacy"]])
    return path


def download_urls(urls, downloads_dir, archive, dry_run=False,
                  max_height=DEFAULT_QUALITY):
    """yt-dlp se download + .info.json save. Returns (ok_urls, failed)."""
    try:
        import yt_dlp
    except ImportError:
        sys.exit("yt-dlp nahi mila. Pehle chalao:  pip install -r requirements.txt")
    os.makedirs(downloads_dir, exist_ok=True)
    log(f"Quality: {max_height}p (max height {max_height})")
    ydl_opts = {
        "format": build_format(max_height),
        # SkillNova wali folder tartib: downloads/<platform>/<channel>/Title [id].ext
        "outtmpl": os.path.join(downloads_dir, "%(extractor)s", "%(uploader)s",
                                "%(title)s [%(id)s].%(ext)s"),
        "restrictfilenames": False,
        "windowsfilenames": True,
        "retries": RETRIES,
        "fragment_retries": RETRIES,
        "concurrent_fragments": 3,
        "sleep_interval": SLEEP_BETWEEN,
        "download_archive": archive,
        "continuedl": True,
        "noplaylist": True,
        "writeinfojson": True,   # <-- yehi V1 se farq hai: metadata save hoti hai
        "writethumbnail": True,  # thumbnail bhi save (uploader V2 abhi use
                                 # nahi karta — agle step ke liye ready)
        "quiet": True,
        "no_warnings": True,
    }
    if dry_run:
        ydl_opts["simulate"] = True
        ydl_opts["skip_download"] = True
    ok, failed = [], []
    for idx, url in enumerate(urls, 1):
        log(f"[{idx}/{len(urls)}] {url}")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=not dry_run)
            log("  OK")
            ok.append(url)
        except Exception as e:  # noqa: BLE001 — aik fail ho to baaki chalte rahen
            log(f"  FAIL: {e}")
            failed.append(url)
    if failed:
        with open(os.path.join(BASE_DIR, "failed.txt"), "w", encoding="utf-8") as f:
            f.writelines(u + "\n" for u in failed)
        log("Fail hui URLs failed.txt me save kar di hain.")
    return ok, failed


def run_uploader(uploader_dir, queue_path, check_only=False):
    """uploader.py subprocess mein chalao — uska apna folder uska cwd hai."""
    cmd = [sys.executable, "uploader.py", "--queue", queue_path]
    if check_only:
        cmd.append("--check")
    log(f"Uploader chala raha hoon: {' '.join(cmd)}  (folder: {uploader_dir})")
    return subprocess.run(cmd, cwd=uploader_dir).returncode


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="End-to-end pipeline: urls.txt -> download -> uploads.csv -> upload")
    parser.add_argument("--urls", default=DEFAULT_URLS)
    parser.add_argument("--downloads", default=DEFAULT_DOWNLOADS)
    parser.add_argument("--uploader-dir", default=DEFAULT_UPLOADER_DIR)
    parser.add_argument("--archive", default=DEFAULT_ARCHIVE)
    parser.add_argument("--privacy", default=DEFAULT_PRIVACY,
                        choices=["private", "unlisted", "public"],
                        help="Default private — pehli video check karke phir public karo")
    parser.add_argument("--quality", type=int, default=DEFAULT_QUALITY,
                        choices=QUALITY_CHOICES,
                        help="2160=4K (default), 1440=2K, 1080, 720 — "
                             "bari quality = bari file, slow download")
    parser.add_argument("--limit", type=int, default=0,
                        help="Sirf pehli N URLs (test ke liye, e.g. --limit 1)")
    parser.add_argument("--download-only", action="store_true",
                        help="Sirf download + uploads.csv, upload nahi")
    parser.add_argument("--upload-only", action="store_true",
                        help="Download skip — pehle se download hui videos upload karo")
    parser.add_argument("--check", action="store_true",
                        help="Sirf check: uploads.csv banao + uploader --check "
                             "(NO download, NO upload, NO login)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Sirf URLs check karo, kuch download nahi")
    args = parser.parse_args(argv)

    downloads_dir = os.path.normpath(args.downloads)
    uploader_dir = os.path.normpath(args.uploader_dir)

    if args.check or args.upload_only:
        urls = []
    else:
        urls = load_urls(args.urls)
        if args.limit:
            urls = urls[: args.limit]
        log(f"Queue: {len(urls)} URL(s)")

    failed = []
    if not args.check and not args.upload_only:
        _, failed = download_urls(urls, downloads_dir, args.archive,
                                  dry_run=args.dry_run, max_height=args.quality)
        if args.dry_run:
            return 0 if not failed else 1

    rows, problems = build_uploads_csv(downloads_dir, args.privacy, uploader_dir)
    for p in problems:
        log(f"NOTE: {p}")
    if not rows:
        log("uploads.csv ke liye koi video tayyar nahi — "
            "pehle download karo ya downloads/ mein video + .info.json check karo.")
        return 1 if failed else 1
    queue_path = write_uploads_csv(rows, uploader_dir)
    log(f"uploads.csv ban gayi: {len(rows)} video(s) -> {queue_path}")

    if args.download_only:
        log("Download-only: upload nahi chalaya. "
            "Upload ke liye: python pipeline.py --upload-only")
        return 0 if not failed else 1

    rc = run_uploader(uploader_dir, queue_path, check_only=args.check)
    if args.check:
        log("CHECK done — upload nahi hua, login nahi manga.")
    elif rc == 0:
        log(f"\nDone: {len(rows)} video(s) upload queue se guzar gayi.")
    else:
        log("\nUploader ne kuch videos fail ki — failed_uploads.csv dekho "
            "(isi project folder mein).")
    if failed:
        return 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
