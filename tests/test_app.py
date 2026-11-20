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

print("ALL LOGIC TESTS PASS")
