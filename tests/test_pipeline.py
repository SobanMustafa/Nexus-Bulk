"""Logic tests for pipeline.py — no network, no yt-dlp, no Google login.
Run:  python3 tests/test_pipeline.py
"""
import csv
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# flat layout: pipeline.py aur uploader.py dono project root mein hain
import pipeline  # noqa: E402
import uploader  # noqa: E402


def make_video_with_info(tmp, stem, info):
    vid = os.path.join(tmp, stem + ".mp4")
    with open(vid, "wb") as f:
        f.write(b"\x00" * 1024)
    with open(os.path.join(tmp, stem + ".info.json"), "w", encoding="utf-8") as f:
        json.dump(info, f)
    return vid


def test_info_to_row_limits():
    info = {"title": "T" * 150, "description": "D" * 6000,
            "tags": ["a", "b" * 600, "c"], "categories": ["Entertainment"]}
    row = pipeline.info_to_row(info, "/tmp/Some Video [abc123].mp4", "private")
    assert len(row["title"]) <= 100, row["title"]
    assert len(row["description"]) <= 5000
    assert sum(len(t) for t in row["tags"].split("|")) + row["tags"].count("|") <= 500, row["tags"]
    assert row["category_id"] == "24", row["category_id"]  # Entertainment -> 24
    assert row["privacy"] == "private"
    print("PASS: info_to_row limits (title 100 / desc 5000 / tags 500 / category map)")


def test_info_to_row_defaults():
    info = {"title": "", "description": None, "tags": [], "categories": ["Unknown Cat"]}
    row = pipeline.info_to_row(info, "/tmp/My Video [xyz].mp4", "private")
    assert row["title"] == "My Video", row["title"]
    assert row["category_id"] == "22", row["category_id"]
    assert row["tags"] == ""
    print("PASS: info_to_row defaults (title from filename, category 22)")


def test_build_csv_and_uploader_validate():
    with tempfile.TemporaryDirectory() as tmp:
        dl = os.path.join(tmp, "downloads")
        up = os.path.join(tmp, "uploader")
        os.makedirs(dl)
        os.makedirs(up)
        make_video_with_info(dl, "Maze Day 1 [aqz1]",
                             {"title": "Mind Maze Day 1 | Can you reverse it?",
                              "description": "Stare and reverse it.",
                              "tags": ["illusion", "mindmaze", "shorts"],
                              "categories": ["People & Blogs"]})
        make_video_with_info(dl, "Horror Night 1 [aqz2]",
                             {"title": "100 Nights of Fear — Night 1",
                              "description": "Three doors.",
                              "tags": ["horror", "scary"],
                              "categories": ["Entertainment"]})
        rows, problems = pipeline.build_uploads_csv(dl, "private", up)
        assert len(rows) == 2, f"expected 2 rows, got {len(rows)}: {problems}"
        assert not problems, problems
        q = pipeline.write_uploads_csv(rows, up)
        items = uploader.load_queue(q)
        assert len(items) == 2
        for item in items:
            ok, errs = uploader.validate(item)
            assert ok, f"uploader rejected pipeline row: {errs} — {item}"
        print("PASS: build csv + uploader validate (2 rows, all pass)")


def test_uploaded_skip_and_missing_info():
    with tempfile.TemporaryDirectory() as tmp:
        dl = os.path.join(tmp, "downloads")
        up = os.path.join(tmp, "uploader")
        os.makedirs(dl)
        os.makedirs(up)
        vid = make_video_with_info(dl, "Done Video [d1]",
                                   {"title": "Done", "description": "",
                                    "tags": [], "categories": []})
        # already uploaded (absolute path, jaisa pipeline likhta hai)
        with open(os.path.join(up, "uploaded.csv"), "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["file", "title", "video_id", "url", "privacy"])
            w.writerow([os.path.abspath(vid), "Done", "vid1", "https://youtu.be/vid1", "private"])
        # video without .info.json
        with open(os.path.join(dl, "NoMeta.mp4"), "wb") as f:
            f.write(b"\x00" * 10)
        rows, problems = pipeline.build_uploads_csv(dl, "private", up)
        assert rows == [], f"uploaded video should be skipped, got {rows}"
        assert any("NoMeta" in p for p in problems), problems
        print("PASS: uploaded skip + missing .info.json reported (not silently lost)")


def test_load_urls():
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "urls.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write("# comment\n\nhttps://example.com/a\nhttps://example.com/a\nhttps://example.com/b\n")
        assert pipeline.load_urls(p) == ["https://example.com/a", "https://example.com/b"]
    print("PASS: load_urls (comments / blanks / dupes)")


def test_check_mode_no_login_no_upload():
    """pipeline --check: fake downloads se uploads.csv + uploader --check, no login."""
    with tempfile.TemporaryDirectory() as tmp:
        dl = os.path.join(tmp, "downloads")
        up = os.path.join(tmp, "uploader")
        os.makedirs(dl)
        os.makedirs(up)
        make_video_with_info(dl, "Maze Day 1 [aqz1]",
                             {"title": "Mind Maze Day 1", "description": "d",
                              "tags": ["illusion"], "categories": ["People & Blogs"]})
        # uploader.py ko temp folder mein copy karo taake subprocess usi ko chalaye
        import shutil
        shutil.copy(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 "uploader.py"),
                    os.path.join(up, "uploader.py"))
        rc = pipeline.main(["--check", "--downloads", dl, "--uploader-dir", up])
        assert rc == 0, f"--check should pass, got {rc}"
        assert os.path.exists(os.path.join(up, "uploads.csv"))
        print("PASS: --check end-to-end (csv built + uploader --check, no login/upload)")


if __name__ == "__main__":
    test_info_to_row_limits()
    test_info_to_row_defaults()
    test_build_csv_and_uploader_validate()
    test_uploaded_skip_and_missing_info()
    test_load_urls()
    test_check_mode_no_login_no_upload()
    print("ALL LOGIC TESTS PASS")
