"""Logic tests for app.py (GUI) — no display, no window, no network.
Run:  python3 tests/test_app.py

Sirf build_command wali pure logic test hoti hai. `import app` headless
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

# (b) download_only — limit ke baghair aur limit ke sath
assert app.build_command("download_only") == [PY, "pipeline.py", "--download-only"]
assert app.build_command("download_only", limit="5") == [
    PY, "pipeline.py", "--download-only", "--limit", "5"]
assert app.build_command("download_only", limit=" 3 ") == [
    PY, "pipeline.py", "--download-only", "--limit", "3"]
print("PASS: (b) download_only with/without limit")

# (c) pipeline_test1 — hamesha limit 1, privacy sath
assert app.build_command("pipeline_test1") == [
    PY, "pipeline.py", "--limit", "1", "--privacy", "private"]
assert app.build_command("pipeline_test1", privacy="unlisted") == [
    PY, "pipeline.py", "--limit", "1", "--privacy", "unlisted"]
print("PASS: (c) pipeline_test1 -> --limit 1 + privacy")

# (d) pipeline — privacy default public bhi, limit optional
assert app.build_command("pipeline") == [PY, "pipeline.py", "--privacy", "private"]
assert app.build_command("pipeline", limit="2", privacy="public") == [
    PY, "pipeline.py", "--privacy", "public", "--limit", "2"]
print("PASS: (d) pipeline with privacy + optional limit")

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

print("ALL LOGIC TESTS PASS")
