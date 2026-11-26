"""Logic tests for app.py (GUI) — no display, no window, no network.
Run:  python3 tests/test_app.py

Sirf build_command / parse_progress wali pure logic test hoti hai.
`import app` headless
chalna chahiye kyunke app.py tkinter ko module level pe import NAHI karta
(lazy import sirf main() ke andar hai).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import app  # noqa: E402

PY = sys.executable


def expect_value_error(fn, label):
    try:
        fn()
    except ValueError:
        return
    raise AssertionError(f"{label}: ValueError ana chahiye tha, nahi aya")


# (0) import app headless — tkinter module level pe load nahi hona chahiye
assert "tkinter" not in sys.modules, "app.py ne tkinter top-level import kar liya"
print("PASS: (0) import app headless OK, tkinter lazy hai")

# (a) check
assert app.build_command("check") == [PY, "pipeline.py", "--check"]
print("PASS: (a) check -> pipeline.py --check")

# (b) download_only — limit ke baghair aur limit ke sath (quality default 2160)
assert app.build_command("download_only") == [
    PY, "pipeline.py", "--download-only", "--quality", "2160"]
assert app.build_command("download_only", limit="5") == [
    PY, "pipeline.py", "--download-only", "--limit", "5", "--quality", "2160"]
assert app.build_command("download_only", limit=" 3 ") == [
    PY, "pipeline.py", "--download-only", "--limit", "3", "--quality", "2160"]
print("PASS: (b) download_only with/without limit + default quality")

# (c) pipeline_test1 — hamesha limit 1, privacy + quality sath
assert app.build_command("pipeline_test1") == [
    PY, "pipeline.py", "--limit", "1", "--privacy", "private", "--quality", "2160"]
assert app.build_command("pipeline_test1", privacy="unlisted") == [
    PY, "pipeline.py", "--limit", "1", "--privacy", "unlisted", "--quality", "2160"]
print("PASS: (c) pipeline_test1 -> --limit 1 + privacy + quality")

# (d) pipeline — privacy default public bhi, limit optional, quality default 2160
assert app.build_command("pipeline") == [
    PY, "pipeline.py", "--privacy", "private", "--quality", "2160"]
assert app.build_command("pipeline", limit="2", privacy="public") == [
    PY, "pipeline.py", "--privacy", "public", "--limit", "2", "--quality", "2160"]
print("PASS: (d) pipeline with privacy + optional limit + default quality")

# (e) multi_check / multi_upload — target/limit, aur --privacy KABHI nahi
assert app.build_command("multi_check") == [PY, "multi_upload.py", "--check"]
assert app.build_command("multi_check", target="mind-maze-yt") == [
    PY, "multi_upload.py", "--check", "--target", "mind-maze-yt"]
assert app.build_command("multi_upload") == [PY, "multi_upload.py"]
assert app.build_command(
    "multi_upload", target="horror-fb", limit="1", privacy="public") == [
    PY, "multi_upload.py", "--target", "horror-fb", "--limit", "1"]
for a in ("multi_check", "multi_upload"):
    cmd = app.build_command(a, target="mind-maze-fb", limit="2", privacy="public")
    assert "--privacy" not in cmd, f"{a} ko --privacy pass ho gaya: {cmd}"
print("PASS: (e) multi commands with target/limit, --privacy kabhi nahi")

# (f) ghalat limit / ghalat privacy / unknown action -> ValueError
expect_value_error(lambda: app.build_command("pipeline", limit="abc"), "limit abc")
expect_value_error(lambda: app.build_command("pipeline", limit="0"), "limit 0")
expect_value_error(lambda: app.build_command("pipeline", limit="-3"), "limit -3")
expect_value_error(lambda: app.build_command("multi_upload", limit="1.5"), "limit 1.5")
expect_value_error(lambda: app.build_command("pipeline", privacy="friends"), "privacy")
expect_value_error(lambda: app.build_command("bogus_action"), "unknown action")
print("PASS: (f) invalid limit/privacy + unknown action -> ValueError")

# (g) quality — download wale teeno actions pe pass hoti hai,
# check/multi pe KABHI nahi, aur ghalat quality -> ValueError
assert app.build_command("download_only", quality="1440") == [
    PY, "pipeline.py", "--download-only", "--quality", "1440"]
assert app.build_command("pipeline_test1", quality="720") == [
    PY, "pipeline.py", "--limit", "1", "--privacy", "private", "--quality", "720"]
assert app.build_command("pipeline", quality="1080") == [
    PY, "pipeline.py", "--privacy", "private", "--quality", "1080"]
for a in ("check", "multi_check", "multi_upload"):
    cmd = app.build_command(a, target="mind-maze-yt", limit="2", quality="1440")
    assert "--quality" not in cmd, f"{a} ko --quality pass ho gaya: {cmd}"
expect_value_error(lambda: app.build_command("pipeline", quality="999"), "quality 999")
expect_value_error(lambda: app.build_command("pipeline", quality="4K"), "quality 4K")
# khaali quality -> default 2160 (privacy wali house style: khaali = default)
assert app.build_command("pipeline", quality="")[-2:] == ["--quality", "2160"]
print("PASS: (g) quality pass-through (3 download actions), check/multi exclude, invalid -> ValueError")

# (h) parse_progress — yt-dlp progress lines se percent, warna None
assert app.parse_progress(
    "[download]  45.3% of  120.00MiB at  2.00MiB/s ETA 00:30") == 45.3
assert app.parse_progress("[download]   0.0% of  10.00MiB at  1.00MiB/s") == 0.0
assert app.parse_progress("[download] 100% of  120.00MiB in 00:01:00") == 100.0
assert app.parse_progress("[download] 100.0% of  120.00MiB") == 100.0
assert app.parse_progress("[download] Destination: video.mp4") is None
assert app.parse_progress("CHECK OK: 1 video(s) ready") is None
assert app.parse_progress("kuch bhi garbage line hai") is None
assert app.parse_progress("") is None
assert app.parse_progress(None) is None
print("PASS: (h) parse_progress yt-dlp lines / 100% / no-percent -> None")

# (i) download_dir — pipeline ke download wale actions + check pe
# --downloads pass hoti hai (check bhi usi folder ko scan karta hai),
# multi pe KABHI nahi, khaali/whitespace = pass nahi hoti, strip hoti hai
DL = "/tmp/custom downloads"
assert app.build_command("download_only", download_dir=DL) == [
    PY, "pipeline.py", "--download-only", "--quality", "2160", "--downloads", DL]
assert app.build_command("pipeline_test1", download_dir=DL) == [
    PY, "pipeline.py", "--limit", "1", "--privacy", "private",
    "--quality", "2160", "--downloads", DL]
assert app.build_command("pipeline", download_dir=DL) == [
    PY, "pipeline.py", "--privacy", "private", "--quality", "2160",
    "--downloads", DL]
assert app.build_command("check", download_dir=DL) == [
    PY, "pipeline.py", "--check", "--downloads", DL]
for a in ("multi_check", "multi_upload"):
    cmd = app.build_command(a, target="mind-maze-yt", limit="2", download_dir=DL)
    assert "--downloads" not in cmd, f"{a} ko --downloads pass ho gaya: {cmd}"
for a in ("check", "download_only", "pipeline_test1", "pipeline"):
    assert "--downloads" not in app.build_command(a, download_dir="")
    assert "--downloads" not in app.build_command(a, download_dir="   ")
assert app.build_command("check", download_dir="  /tmp/x  ")[-2:] == \
    ["--downloads", "/tmp/x"]
print("PASS: (i) download_dir -> --downloads (download actions + check), multi exclude, empty exclude")

# (j) extract_links — paste box ka text saaf links me badlo:
# blanks + # comments skip, non-http lines drop, duplicates aik dafa, order waisa hi
assert app.extract_links("") == []
assert app.extract_links("\n\n   \n") == []
assert app.extract_links(
    "https://www.youtube.com/watch?v=abc\n"
    "\n"
    "# ye comment hai\n"
    "  https://www.tiktok.com/@user/video/123  \n"
    "koi aam text line\n"
    "www.example.com/no-scheme\n"
    "ftp://example.com/file\n"
    "https://www.youtube.com/watch?v=abc\n"
    "http://example.com/plain-http\n"
) == [
    "https://www.youtube.com/watch?v=abc",
    "https://www.tiktok.com/@user/video/123",
    "http://example.com/plain-http",
]
assert app.extract_links(None) == []
print("PASS: (j) extract_links blanks/comments/duplicates/non-http drop, order preserved")

# (k) urls_file — sirf download wale teeno actions ko --urls pass hoti hai,
# check/multi ko KABHI nahi, khaali/whitespace = pass nahi hoti
UF = "paste_links.txt"
assert app.build_command("download_only", urls_file=UF) == [
    PY, "pipeline.py", "--download-only", "--quality", "2160", "--urls", UF]
assert app.build_command("pipeline_test1", urls_file=UF) == [
    PY, "pipeline.py", "--limit", "1", "--privacy", "private",
    "--quality", "2160", "--urls", UF]
assert app.build_command("pipeline", limit="2", urls_file=UF) == [
    PY, "pipeline.py", "--privacy", "private", "--limit", "2",
    "--quality", "2160", "--urls", UF]
assert app.build_command("download_only", download_dir="/tmp/dl", urls_file=UF) == [
    PY, "pipeline.py", "--download-only", "--quality", "2160",
    "--downloads", "/tmp/dl", "--urls", UF]
for a in ("check", "multi_check", "multi_upload"):
    cmd = app.build_command(a, target="mind-maze-yt", limit="2", urls_file=UF)
    assert "--urls" not in cmd, f"{a} ko --urls pass ho gaya: {cmd}"
for a in ("download_only", "pipeline_test1", "pipeline"):
    assert "--urls" not in app.build_command(a, urls_file="")
    assert "--urls" not in app.build_command(a, urls_file="   ")
print("PASS: (k) urls_file -> --urls (3 download actions), check/multi exclude, empty exclude")

# (l) parse_qitem — queuedl ki QITEM lines, valid + invalid
assert app.parse_qitem("QITEM 0 START 0") == (0, "START", 0)
assert app.parse_qitem("QITEM 3 PROGRESS 45") == (3, "PROGRESS", 45)
assert app.parse_qitem("QITEM 12 DONE 100") == (12, "DONE", 100)
assert app.parse_qitem("QITEM 2 FAILED 30") == (2, "FAILED", 30)
assert app.parse_qitem("QITEM 1 SKIPPED 100") == (1, "SKIPPED", 100)
assert app.parse_qitem("QITEM x DONE 100") is None
assert app.parse_qitem("QITEM 1 BOGUS 5") is None
assert app.parse_qitem("QITEM 1 DONE") is None
assert app.parse_qitem("QITEM 1 DONE 100 extra") is None
assert app.parse_qitem("hello world") is None
assert app.parse_qitem("") is None
assert app.parse_qitem(None) is None
print("PASS: (l) parse_qitem valid/invalid")

# (m) parse_grab_line — 'GRAB <url>' sirf; GRABDONE match NAHI hoti
assert app.parse_grab_line("GRAB https://www.youtube.com/watch?v=a") == \
    "https://www.youtube.com/watch?v=a"
assert app.parse_grab_line("GRAB http://example.com/x") == "http://example.com/x"
assert app.parse_grab_line("GRABDONE 5") is None
assert app.parse_grab_line("GRAB notaurl") is None
assert app.parse_grab_line("GRAB ") is None
assert app.parse_grab_line("") is None
assert app.parse_grab_line(None) is None
print("PASS: (m) parse_grab_line GRAB only, GRABDONE excluded")

# (n) parse_qdone
assert app.parse_qdone("QDONE total=5 done=3 failed=1 skipped=1") == \
    {"total": 5, "done": 3, "failed": 1, "skipped": 1}
assert app.parse_qdone("QDONE total=0 done=0 failed=0 skipped=0") == \
    {"total": 0, "done": 0, "failed": 0, "skipped": 0}
assert app.parse_qdone("QDONE kuch aur") is None
assert app.parse_qdone("") is None
print("PASS: (n) parse_qdone")

# (o) queue_stats — status counts
rows = [
    {"url": "a", "status": "Pending", "pct": 0},
    {"url": "b", "status": "Pending", "pct": 0},
    {"url": "c", "status": "Downloading", "pct": 40},
    {"url": "d", "status": "Done", "pct": 100},
    {"url": "e", "status": "Failed", "pct": 20},
    {"url": "f", "status": "Skipped", "pct": 100},
]
assert app.queue_stats(rows) == {"total": 6, "downloaded": 1, "remaining": 2,
                                 "downloading": 1, "failed": 1, "skipped": 1}
assert app.queue_stats([]) == {"total": 0, "downloaded": 0, "remaining": 0,
                               "downloading": 0, "failed": 0, "skipped": 0}
print("PASS: (o) queue_stats counts")

# (p) dedupe_new — existing + batch ke andar ke dupes, order same
assert app.dedupe_new(["a", "b"], ["b", "c", "c", "d", "a"]) == ["c", "d"]
assert app.dedupe_new([], ["x", "x", "y"]) == ["x", "y"]
assert app.dedupe_new(["a"], []) == []
assert app.dedupe_new([], []) == []
print("PASS: (p) dedupe_new existing/batch dupes drop")

# (q) queue_download command — threads/quality/downloads/cookies/proxy
assert app.build_command("queue_download", urls_file="gui_queue.txt") == [
    PY, "queuedl.py", "gui_queue.txt", "--quality", "2160", "--threads", "4"]
assert app.build_command("queue_download") == [
    PY, "queuedl.py", "gui_queue.txt", "--quality", "2160", "--threads", "4"]
assert app.build_command(
    "queue_download", urls_file="/tmp/q.txt", quality="1080", threads="8",
    download_dir="/tmp/dl") == [
    PY, "queuedl.py", "/tmp/q.txt", "--quality", "1080", "--threads", "8",
    "--downloads", "/tmp/dl"]
qcmd = app.build_command("queue_download", cookies=("chrome", ""))
assert qcmd[qcmd.index("--cookies-from-browser") + 1] == "chrome"
qcmd = app.build_command("queue_download", cookies=("file", "C:/cookies.txt"))
assert qcmd[qcmd.index("--cookies-file") + 1] == "C:/cookies.txt"
qcmd = app.build_command("queue_download", proxy="http://127.0.0.1:8080")
assert qcmd[qcmd.index("--proxy") + 1] == "http://127.0.0.1:8080"
qcmd = app.build_command("queue_download")
assert "--cookies-from-browser" not in qcmd and "--cookies-file" not in qcmd
assert "--proxy" not in qcmd and "--downloads" not in qcmd
expect_value_error(
    lambda: app.build_command("queue_download", threads="5"), "threads 5")
expect_value_error(
    lambda: app.build_command("queue_download", cookies=("opera", "")),
    "cookies opera")
expect_value_error(
    lambda: app.build_command("queue_download", cookies=("file", "")),
    "cookies file khaali")
print("PASS: (q) queue_download command shape + cookies/proxy/threads validation")

# (r) grab commands — shorts/videos, count, cookies/proxy; khaali URL -> error
CH = "https://www.youtube.com/@SomeChannel"
assert app.build_command("grab_shorts", grab_url=CH) == [
    PY, "queuedl.py", "--grab", CH, "--grab-type", "shorts", "--count", "50"]
assert app.build_command("grab_videos", grab_url=CH, grab_count="20") == [
    PY, "queuedl.py", "--grab", CH, "--grab-type", "videos", "--count", "20"]
gcmd = app.build_command("grab_videos", grab_url=CH, cookies=("edge", ""),
                         proxy="socks5://127.0.0.1:1080")
assert gcmd[gcmd.index("--cookies-from-browser") + 1] == "edge"
assert gcmd[gcmd.index("--proxy") + 1] == "socks5://127.0.0.1:1080"
expect_value_error(lambda: app.build_command("grab_shorts", grab_url=""),
                   "grab khaali url")
expect_value_error(lambda: app.build_command("grab_shorts", grab_url="  "),
                   "grab whitespace url")
expect_value_error(
    lambda: app.build_command("grab_videos", grab_url=CH, grab_count="99"),
    "grab count 99")
print("PASS: (r) grab_shorts/grab_videos command shape + validation")

# (s) update_ytdlp + cookies/threads/proxy doosre actions pe IGNORE hote hain
assert app.build_command("update_ytdlp") == [
    PY, "-m", "pip", "install", "-U", "yt-dlp"]
for a in ("check", "download_only", "pipeline_test1", "pipeline",
          "multi_check", "multi_upload"):
    cmd = app.build_command(a, target="mind-maze-yt", threads="8",
                            cookies=("chrome", ""), proxy="http://x:1")
    assert "--cookies-from-browser" not in cmd, f"{a} ko cookies lag gaye: {cmd}"
    assert "--proxy" not in cmd, f"{a} ko proxy lag gaya: {cmd}"
    assert "--threads" not in cmd, f"{a} ko threads lag gaye: {cmd}"
print("PASS: (s) update_ytdlp + cookies/threads/proxy queue/grab only")

# (t) grab_popular — popular type, count, cookies/proxy; khaali URL -> error
TT = "https://www.tiktok.com/@someuser"
assert app.build_command("grab_popular", grab_url=TT) == [
    PY, "queuedl.py", "--grab", TT, "--grab-type", "popular", "--count", "50"]
assert app.build_command("grab_popular", grab_url=TT, grab_count="10") == [
    PY, "queuedl.py", "--grab", TT, "--grab-type", "popular", "--count", "10"]
gcmd = app.build_command("grab_popular", grab_url=TT,
                         cookies=("chrome", ""), proxy="http://127.0.0.1:8080")
assert gcmd[gcmd.index("--cookies-from-browser") + 1] == "chrome"
assert gcmd[gcmd.index("--proxy") + 1] == "http://127.0.0.1:8080"
gcmd = app.build_command("grab_popular", grab_url=TT,
                         cookies=("file", "C:/cookies.txt"))
assert gcmd[gcmd.index("--cookies-file") + 1] == "C:/cookies.txt"
expect_value_error(lambda: app.build_command("grab_popular", grab_url=""),
                   "grab_popular khaali url")
expect_value_error(lambda: app.build_command("grab_popular", grab_url="  "),
                   "grab_popular whitespace url")
print("PASS: (t) grab_popular command shape + cookies/proxy + validation")

# (u) parse_grab_meta + format_views
gm = app.parse_grab_meta('GRABMETA {"url": "https://youtu.be/1", "title": "My Video", "views": 43600}')
assert gm == {"url": "https://youtu.be/1", "title": "My Video", "views": 43600}
assert app.parse_grab_meta("GRAB https://youtu.be/1") is None
assert app.parse_grab_meta("GRABMETA {bad json") is None
assert app.format_views(1_500_000) == "1.5M"
assert app.format_views(43_600) == "43.6K"
assert app.format_views(850) == "850"
assert app.format_views(None) == "—"
assert app.format_views(True) == "—"
print("PASS: (u) parse_grab_meta + format_views")

print("ALL LOGIC TESTS PASS")
