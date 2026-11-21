"""Logic tests for queuedl.py — no network, no real subprocess.
Run:  python3 tests/test_queuedl.py

run_one / run_grab ko FAKE popen factory di jati hai — asal yt-dlp
kabhi nahi chalta. Protocol lines emit_fn se capture hoti hain.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import queuedl  # noqa: E402

PY = sys.executable


# (a) build_format — downloader.py wali exact strings (parity)
assert queuedl.build_format(2160) == \
    "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best"
assert queuedl.build_format(720) == \
    "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
print("PASS: (a) build_format parity")

# (b) parse_progress_line
assert queuedl.parse_progress_line(
    "[download]  45.3% of  120.00MiB at  2.00MiB/s ETA 00:30") == 45.3
assert queuedl.parse_progress_line(
    "[download] 100% of  120.00MiB in 00:01:00") == 100.0
assert queuedl.parse_progress_line("[download] 100.0% of  1.00MiB") == 100.0
assert queuedl.parse_progress_line("[download]   0.0% of  10.00MiB") == 0.0
assert queuedl.parse_progress_line("[download] Destination: video.mp4") is None
assert queuedl.parse_progress_line("koi aam line hai") is None
assert queuedl.parse_progress_line("") is None
assert queuedl.parse_progress_line(None) is None
print("PASS: (b) parse_progress_line progress / 100% / non-progress -> None")

# (c) load_queue_text — comments/blanks/duplicates/non-http drop, order same
assert queuedl.load_queue_text("") == []
assert queuedl.load_queue_text(
    "https://www.youtube.com/watch?v=abc\n"
    "\n"
    "# comment line\n"
    "  https://www.tiktok.com/@u/video/1  \n"
    "aam text line\n"
    "www.example.com/no-scheme\n"
    "https://www.youtube.com/watch?v=abc\n"
) == ["https://www.youtube.com/watch?v=abc",
      "https://www.tiktok.com/@u/video/1"]
assert queuedl.load_queue_text(None) == []
print("PASS: (c) load_queue_text comments/blanks/dupes/non-http drop")

# (d) channel_targets
CH = "https://www.youtube.com/@SomeChannel"
assert queuedl.channel_targets(CH, "videos") == [CH + "/videos"]
assert queuedl.channel_targets(CH, "shorts") == [CH + "/shorts"]
assert queuedl.channel_targets(CH, "all") == [CH + "/videos", CH + "/shorts"]
assert queuedl.channel_targets(CH + "/", "videos") == [CH + "/videos"]
assert queuedl.channel_targets(CH + "/shorts", "videos") == [CH + "/shorts"]
assert queuedl.channel_targets(CH + "/videos", "shorts") == [CH + "/videos"]
FB = "https://www.facebook.com/SomePage/reels"
assert queuedl.channel_targets(FB, "shorts") == [FB]
assert queuedl.channel_targets(FB, "all") == [FB]
print("PASS: (d) channel_targets youtube suffix / already-suffixed / facebook passthrough")

# (e) build_download_cmd — archive/format/cookies/proxy/url order
cmd = queuedl.build_download_cmd(
    "https://youtu.be/xyz", quality=1440, downloads_dir="/tmp/dl",
    archive="/tmp/arch.txt")
assert cmd[:3] == [PY, "-m", "yt_dlp"]
assert cmd[-1] == "https://youtu.be/xyz"
assert "--download-archive" in cmd
assert cmd[cmd.index("--download-archive") + 1] == "/tmp/arch.txt"
assert cmd[cmd.index("-f") + 1] == queuedl.build_format(1440)
assert cmd[cmd.index("-P") + 1] == "/tmp/dl"
assert "--merge-output-format" in cmd
assert "--cookies-from-browser" not in cmd and "--cookies" not in cmd
cmd2 = queuedl.build_download_cmd(
    "https://youtu.be/xyz", cookies_from_browser="chrome",
    proxy="http://127.0.0.1:8080")
assert cmd2[cmd2.index("--cookies-from-browser") + 1] == "chrome"
assert cmd2[cmd2.index("--proxy") + 1] == "http://127.0.0.1:8080"
cmd3 = queuedl.build_download_cmd(
    "https://youtu.be/xyz", cookies_file="/tmp/cookies.txt")
assert cmd3[cmd3.index("--cookies") + 1] == "/tmp/cookies.txt"
print("PASS: (e) build_download_cmd archive/format/cookies/proxy")
# (e2) SkillNova wali folder tartib — platform/channel subfolders + info.json
assert queuedl.OUTPUT_TEMPLATE == \
    "%(extractor)s/%(uploader)s/%(title)s [%(id)s].%(ext)s"
assert "-o" in cmd and cmd[cmd.index("-o") + 1] == queuedl.OUTPUT_TEMPLATE
assert "--write-info-json" in cmd
assert "--windows-filenames" in cmd
print("PASS: (e2) build_download_cmd platform/channel folders + write-info-json")

# (f) build_grab_cmd
gcmd = queuedl.build_grab_cmd("https://www.youtube.com/@C/videos", count=25)
assert gcmd[:3] == [PY, "-m", "yt_dlp"]
assert "--flat-playlist" in gcmd
assert gcmd[gcmd.index("--playlist-end") + 1] == "25"
assert gcmd[-1] == "https://www.youtube.com/@C/videos"
print("PASS: (f) build_grab_cmd flat-playlist + count + target")


# --- fake popen -------------------------------------------------------------
class FakeProc:
    def __init__(self, lines, code):
        self.stdout = iter(lines)
        self._code = code
        self.terminated = False

    def wait(self):
        return self._code

    def poll(self):
        return self._code

    def terminate(self):
        self.terminated = True


def make_factory(script):
    """script = [(lines, exit_code), ...] har call pe aik entry."""
    calls = []

    def factory(cmd, **kwargs):
        calls.append(cmd)
        lines, code = script[len(calls) - 1]
        return FakeProc(list(lines), code)

    return factory, calls


# (g) run_one success — progress events + DONE
events = []
factory, calls = make_factory([
    (["[download]  10.0% of  10.00MiB at  1.00MiB/s\n",
      "[download]  50.0% of  10.00MiB at  1.00MiB/s\n",
      "[download] 100% of  10.00MiB in 00:00:10\n"], 0),
])
status, missing = queuedl.run_one(
    0, "https://youtu.be/ok", downloads_dir="/tmp/dl", archive="/tmp/a.txt",
    emit_fn=events.append, popen_factory=factory)
assert status == "DONE" and missing is False
assert events[0] == "QITEM 0 START 0"
assert "QITEM 0 PROGRESS 10" in events
assert "QITEM 0 PROGRESS 50" in events
assert events[-1] == "QITEM 0 DONE 100"
assert len(calls) == 1
print("PASS: (g) run_one success -> progress events + DONE")

# (h) run_one archive line -> SKIPPED
events = []
factory, calls = make_factory([
    (["[download] https://youtu.be/dup has already been recorded "
      "in the archive\n"], 0),
])
status, _ = queuedl.run_one(
    3, "https://youtu.be/dup", downloads_dir="/tmp/dl", archive="/tmp/a.txt",
    emit_fn=events.append, popen_factory=factory)
assert status == "SKIPPED"
assert events[-1] == "QITEM 3 SKIPPED 100"
assert len(calls) == 1
print("PASS: (h) run_one archive line -> SKIPPED")

# (i) run_one fail x2 -> FAILED after exactly 2 attempts
events = []
factory, calls = make_factory([
    (["[download]  30.0% of  10.00MiB\n", "ERROR: network gaya\n"], 1),
    (["[download]  20.0% of  10.00MiB\n", "ERROR: phir gaya\n"], 1),
])
status, _ = queuedl.run_one(
    1, "https://youtu.be/bad", downloads_dir="/tmp/dl", archive="/tmp/a.txt",
    emit_fn=events.append, popen_factory=factory)
assert status == "FAILED"
assert len(calls) == 2, f"2 attempts hone chahiye thay, hue {len(calls)}"
assert events[-1] == "QITEM 1 FAILED 20"
print("PASS: (i) run_one fail -> retry -> FAILED (2 attempts)")

# (j) run_one missing yt-dlp — on_missing callback fire hota hai
events, missing_hits = [], []
factory, calls = make_factory([
    (["/usr/bin/python3: No module named yt_dlp\n"], 1),
    (["/usr/bin/python3: No module named yt_dlp\n"], 1),
])
status, missing = queuedl.run_one(
    2, "https://youtu.be/x", downloads_dir="/tmp/dl", archive="/tmp/a.txt",
    emit_fn=events.append, popen_factory=factory,
    on_missing=lambda: missing_hits.append(1))
assert status == "FAILED" and missing is True
assert missing_hits, "on_missing callback fire nahi hua"
print("PASS: (j) run_one missing yt-dlp -> missing flag + callback")

# (k) run_grab — fake 3 URLs -> 3 GRAB + GRABDONE 3
events = []
factory, calls = make_factory([
    (["https://www.youtube.com/watch?v=a\n",
      "koi garbage line\n",
      "https://www.youtube.com/watch?v=b\n",
      "https://www.youtube.com/watch?v=a\n",
      "https://www.youtube.com/watch?v=c\n"], 0),
])
urls, ok = queuedl.run_grab(
    "https://www.youtube.com/@Chan", grab_type="videos", count=50,
    emit_fn=events.append, popen_factory=factory)
assert ok is True
assert urls == ["https://www.youtube.com/watch?v=a",
                "https://www.youtube.com/watch?v=b",
                "https://www.youtube.com/watch?v=c"]
assert [e for e in events if e.startswith("GRAB ")] == \
    [f"GRAB {u}" for u in urls]
assert events[-1] == "GRABDONE 3"
print("PASS: (k) run_grab 3 URLs -> GRAB lines + GRABDONE 3")

# (l) run_grab failure -> GRABDONE 0, ok False, koi GRAB line nahi
events = []
factory, calls = make_factory([
    (["ERROR: channel nahi mila\n"], 1),
])
urls, ok = queuedl.run_grab(
    "https://www.youtube.com/@Nope", grab_type="shorts", count=10,
    emit_fn=events.append, popen_factory=factory)
assert ok is False and urls == []
assert events[-1] == "GRABDONE 0"
assert not any(e.startswith("GRAB ") for e in events)
print("PASS: (l) run_grab failure -> GRABDONE 0")

print("ALL LOGIC TESTS PASS")
