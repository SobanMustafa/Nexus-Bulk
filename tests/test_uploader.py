"""Logic tests for uploader.py — no network, no Google login needed.
Run:  python3 tests/test_uploader.py
"""
import csv
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import uploader  # noqa: E402


def make_video(tmp, name="test1.mp4", size=1024):
    p = os.path.join(tmp, name)
    with open(p, "wb") as f:
        f.write(b"\x00" * size)
    return p


def write_queue(tmp, rows):
    q = os.path.join(tmp, "uploads.csv")
    with open(q, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "title", "description", "tags", "category_id", "privacy"])
        w.writerows(rows)
    return q


def test_queue_parsing():
    with tempfile.TemporaryDirectory() as tmp:
        q = write_queue(tmp, [
            ["videos/a.mp4", "Title A", "desc", "a|b", "22", "private"],
            ["videos/a.mp4", "Title A dup", "desc", "a|b", "22", "private"],  # duplicate skip
            ["videos/b.mp4", "", "desc", "", "", ""],  # title/category/privacy defaults
        ])
        items = uploader.load_queue(q)
        assert len(items) == 2, f"expected 2, got {len(items)}"
        assert items[0]["tags"] == ["a", "b"]
        assert items[1]["title"] == "b", f"title fallback failed: {items[1]['title']}"
        assert items[1]["category_id"] == "22"
        assert items[1]["privacy"] == "private"
    print("PASS: queue parsing (dupes, defaults, tags)")


def test_validation():
    with tempfile.TemporaryDirectory() as tmp:
        vid = make_video(tmp)
        good = {"file": vid, "title": "OK title", "description": "d",
                "tags": ["a"], "category_id": "22", "privacy": "private"}
        ok, errs = uploader.validate(good)
        assert ok, f"good item failed: {errs}"

        bad = dict(good, title="x" * 101, privacy="everyone",
                   description="y" * 5001, category_id="abc")
        ok, errs = uploader.validate(bad)
        assert not ok and len(errs) >= 3, f"bad item passed: {errs}"

        missing = dict(good, file="nope.mp4")
        ok, errs = uploader.validate(missing)
        assert not ok and any("nahi mili" in e for e in errs), errs

        not_video = make_video(tmp, "note.txt")
        ok, errs = uploader.validate(dict(good, file=not_video))
        assert not ok, "non-video extension should fail"
    print("PASS: validation (good / long title+desc / bad privacy / missing / non-video)")


def test_build_body():
    item = {"title": "T", "description": "D", "tags": ["a", "b"],
            "category_id": "24", "privacy": "unlisted"}
    body = uploader.build_body(item)
    assert body["snippet"]["title"] == "T"
    assert body["snippet"]["tags"] == ["a", "b"]
    assert body["snippet"]["categoryId"] == "24"
    assert body["status"]["privacyStatus"] == "unlisted"
    assert body["status"]["selfDeclaredMadeForKids"] is False
    print("PASS: build_body (snippet + status)")


def test_check_mode_end_to_end():
    """--check via main(): valid queue passes, bad queue fails, no Google import."""
    with tempfile.TemporaryDirectory() as tmp:
        make_video(tmp, "a.mp4")
        q = write_queue(tmp, [["a.mp4", "Title A", "desc", "x|y", "22", "private"]])
        # point uploader at temp queue/videos by monkeypatching module constants
        old_base, old_q, old_v = uploader.BASE_DIR, uploader.QUEUE_FILE, uploader.VIDEOS_DIR
        uploader.BASE_DIR, uploader.QUEUE_FILE, uploader.VIDEOS_DIR = tmp, q, tmp
        uploader.UPLOADED_FILE = os.path.join(tmp, "uploaded.csv")
        sys.argv = ["uploader.py", "--check", "--queue", q]
        try:
            rc = uploader.main()
            assert rc == 0, f"--check should pass, got {rc}"
        finally:
            uploader.BASE_DIR, uploader.QUEUE_FILE, uploader.VIDEOS_DIR = old_base, old_q, old_v
    print("PASS: --check end-to-end (no login, no upload)")


if __name__ == "__main__":
    test_queue_parsing()
    test_validation()
    test_build_body()
    test_check_mode_end_to_end()
    print("ALL LOGIC TESTS PASS")
