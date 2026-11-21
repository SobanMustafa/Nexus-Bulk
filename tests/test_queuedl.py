"""Logic tests for queuedl.py — no network, no actual subprocess.
Run:  python tests/test_queuedl.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import queuedl  # noqa: E402

PY = sys.executable


# 1. build_format
def test_build_format():
    assert queuedl.build_format(2160) == "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best"
    assert "height<=1440" in queuedl.build_format(1440)
    assert "height<=1080" in queuedl.build_format(1080)
    assert "height<=720" in queuedl.build_format(720)
    print("PASS: build_format (2160=4K / 1440=2K / 1080 / 720)")


# 2. parse_progress_line
def test_parse_progress_line():
    assert queuedl.parse_progress_line("[download]  45.2% of 10.00MiB at 2.00MiB/s") == 45.2
    assert queuedl.parse_progress_line("[download] 100% of 5.00MiB") == 100.0
    assert queuedl.parse_progress_line("[download]   0.0% of 1.00MiB") == 0.0
    assert queuedl.parse_progress_line("Just some log text") is None
    assert queuedl.parse_progress_line("") is None
    print("PASS: parse_progress_line (pct extract, bounds, non-matches)")


# 3. load_queue_text
def test_load_queue_text():
    sample = """
    # comment line
    https://www.youtube.com/watch?v=aaa
    https://www.youtube.com/watch?v=bbb

    # duplicate
    https://www.youtube.com/watch?v=aaa
    invalid-url-line
    http://example.com/video
    """
    urls = queuedl.load_queue_text(sample)
    assert urls == [
        "https://www.youtube.com/watch?v=aaa",
        "https://www.youtube.com/watch?v=bbb",
        "http://example.com/video",
    ]
    print("PASS: load_queue_text (comments, blanks, dupes, non-http)")


# 4. _cookie_args and _impersonate_args
def test_cookie_and_impersonate_args():
    assert queuedl._cookie_args("chrome", "") == ["--cookies-from-browser", "chrome"]
    assert queuedl._cookie_args("", "cookies.txt") == ["--cookies", "cookies.txt"]
    assert queuedl._cookie_args("", "") == []

    imp = queuedl._impersonate_args()
    assert isinstance(imp, list)
    if imp:
        assert imp == ["--impersonate", "chrome"]
    print("PASS: _cookie_args and _impersonate_args")


# 5. build_download_cmd and build_grab_cmd
def test_build_cmds():
    dl_cmd = queuedl.build_download_cmd(
        "https://example.com/v1", quality=1080,
        downloads_dir="C:/downloads", archive="C:/archive.txt",
        cookies_from_browser="chrome", proxy="http://proxy:8080"
    )
    assert dl_cmd[0] == PY
    assert dl_cmd[1:3] == ["-m", "yt_dlp"]
    assert "-P" in dl_cmd and "C:/downloads" in dl_cmd
    assert "--download-archive" in dl_cmd and "C:/archive.txt" in dl_cmd
    assert "--cookies-from-browser" in dl_cmd and "chrome" in dl_cmd
    assert "--proxy" in dl_cmd and "http://proxy:8080" in dl_cmd
    assert dl_cmd[-1] == "https://example.com/v1"

    grab_cmd = queuedl.build_grab_cmd("https://www.tiktok.com/@eyedrills", count=10)
    assert grab_cmd[0] == PY
    assert "--flat-playlist" in grab_cmd
    assert "--print" in grab_cmd and "url" in grab_cmd
    assert "--playlist-end" in grab_cmd and "10" in grab_cmd
    assert grab_cmd[-1] == "https://www.tiktok.com/@eyedrills"
    print("PASS: build_download_cmd and build_grab_cmd structure")


# 6. channel_targets and popular_target
def test_targets():
    # YouTube channel targets
    assert queuedl.channel_targets("https://www.youtube.com/@channel", "videos") == [
        "https://www.youtube.com/@channel/videos"
    ]
    assert queuedl.channel_targets("https://www.youtube.com/@channel", "shorts") == [
        "https://www.youtube.com/@channel/shorts"
    ]
    assert queuedl.channel_targets("https://www.youtube.com/@channel", "all") == [
        "https://www.youtube.com/@channel/videos",
        "https://www.youtube.com/@channel/shorts",
    ]
    # Non-YouTube targets preserved as-is
    assert queuedl.channel_targets("https://www.tiktok.com/@eyedrills", "videos") == [
        "https://www.tiktok.com/@eyedrills"
    ]
    assert queuedl.channel_targets("https://www.tiktok.com/@eyedrills", "shorts") == [
        "https://www.tiktok.com/@eyedrills"
    ]

    # popular_target
    assert queuedl.popular_target("https://www.youtube.com/@channel") == "https://www.youtube.com/@channel/videos"
    assert queuedl.popular_target("https://www.tiktok.com/@eyedrills") == "https://www.tiktok.com/@eyedrills"

    # popular_pool
    assert queuedl.popular_pool(10) == 60   # min 60
    assert queuedl.popular_pool(30) == 120  # 30 * 4
    assert queuedl.popular_pool(100) == 200 # max 200
    print("PASS: channel_targets, popular_target, and popular_pool")


# 7. rank_popular and parse_flat_entries
def test_popular_ranking():
    entries_json = json.dumps({
        "entries": [
            {"webpage_url": "https://v/1", "view_count": 500},
            {"webpage_url": "https://v/2", "view_count": 2500},
            {"webpage_url": "https://v/3", "view_count": 1000},
            {"webpage_url": "https://v/2", "view_count": 3000},  # duplicate, higher views
            {"webpage_url": "https://v/4", "view_count": None},  # no view count
            {"webpage_url": "invalid", "view_count": 9999},      # non-http
        ]
    })
    parsed = queuedl.parse_flat_entries(entries_json)
    assert len(parsed) == 5
    ranked = queuedl.rank_popular(parsed, count=3)
    assert ranked == ["https://v/2", "https://v/3", "https://v/1"]
    print("PASS: rank_popular and parse_flat_entries (views desc, dedupe, invalid filter)")


# 8. Fake runner tests (run_grab, run_popular)
class FakeProcess:
    def __init__(self, stdout_lines, returncode=0):
        self.stdout = stdout_lines
        self.returncode = returncode

    def wait(self):
        return self.returncode

    def terminate(self):
        pass


def test_run_grab_fake():
    emitted = []

    def fake_popen(cmd, **kwargs):
        return FakeProcess([
            "https://www.tiktok.com/@eyedrills/video/1\n",
            "https://www.tiktok.com/@eyedrills/video/2\n",
        ], returncode=0)

    urls, ok = queuedl.run_grab(
        "https://www.tiktok.com/@eyedrills",
        count=2, emit_fn=emitted.append, popen_factory=fake_popen
    )
    assert ok is True
    assert len(urls) == 2
    assert "GRAB https://www.tiktok.com/@eyedrills/video/1" in emitted
    assert "GRABDONE 2" in emitted

    # Failure case
    emitted_fail = []

    def fake_popen_fail(cmd, **kwargs):
        return FakeProcess(["ERROR: something failed\n"], returncode=1)

    urls, ok = queuedl.run_grab(
        "https://www.tiktok.com/@eyedrills",
        count=2, emit_fn=emitted_fail.append, popen_factory=fake_popen_fail
    )
    assert ok is False
    assert len(urls) == 0
    assert "GRABDONE 0" in emitted_fail
    assert any("yt-dlp: ERROR: something failed" in line for line in emitted_fail)
    print("PASS: run_grab fake runner (success + error logging)")


def test_run_popular_fake():
    emitted = []
    pool_json = json.dumps({
        "entries": [
            {"webpage_url": "https://v/low", "view_count": 100},
            {"webpage_url": "https://v/high", "view_count": 99999},
        ]
    })

    def fake_popen(cmd, **kwargs):
        return FakeProcess([pool_json], returncode=0)

    ranked, ok = queuedl.run_popular(
        "https://www.tiktok.com/@eyedrills",
        count=2, emit_fn=emitted.append, popen_factory=fake_popen
    )
    assert ok is True
    assert ranked == ["https://v/high", "https://v/low"]
    assert "GRAB https://v/high" in emitted
    assert "GRABDONE 2" in emitted
    print("PASS: run_popular fake runner (pool ranking and emit)")


if __name__ == "__main__":
    test_build_format()
    test_parse_progress_line()
    test_load_queue_text()
    test_cookie_and_impersonate_args()
    test_build_cmds()
    test_targets()
    test_popular_ranking()
    test_run_grab_fake()
    test_run_popular_fake()
    print("ALL LOGIC TESTS PASS")
