"""Logic tests for multi_upload.py + fb_uploader.py — no network, no login.
Run:  python3 tests/test_multi.py
"""
import contextlib
import csv
import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import fb_uploader  # noqa: E402
import multi_upload  # noqa: E402


def write_registry(tmp, pages):
    p = os.path.join(tmp, "pages.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"pages": pages}, f)
    return p


def sample_pages():
    return [
        {"id": "mind-maze-fb", "platform": "facebook", "name": "Mind Maze",
         "page_id": "FILL-IN-FROM-/me/accounts",
         "token_file": "tokens/mind-maze-fb.page_token.txt",
         "default_privacy": "published"},
        {"id": "horror-fb", "platform": "facebook", "name": "100 Nights of Fear",
         "page_id": "FILL-IN-FROM-/me/accounts",
         "token_file": "tokens/horror-fb.page_token.txt",
         "default_privacy": "published"},
        {"id": "mind-maze-yt", "platform": "youtube", "name": "Mind Maze",
         "auth_dir": "auth/mind-maze-yt", "default_privacy": "private"},
    ]


def write_queue(tmp, rows):
    p = os.path.join(tmp, "uploads.csv")
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "title", "description", "tags",
                    "category_id", "privacy", "target"])
        w.writerows(rows)
    return p


def make_video(tmp, name):
    p = os.path.join(tmp, name)
    with open(p, "wb") as f:
        f.write(b"\x00" * 1024)
    return p


def test_registry_load_valid():
    with tempfile.TemporaryDirectory() as tmp:
        p = write_registry(tmp, sample_pages())
        registry, warnings = multi_upload.load_registry(p)
        assert set(registry) == {"mind-maze-fb", "horror-fb", "mind-maze-yt"}, registry
        assert registry["mind-maze-yt"]["platform"] == "youtube"
        # placeholder page_id = warning, error nahi
        assert any("mind-maze-fb" in w for w in warnings), warnings
    print("PASS: (a) registry load valid (3 destinations, placeholder = warning)")


def test_registry_rejects():
    cases = [
        # duplicate id
        [{"id": "x-yt", "platform": "youtube", "auth_dir": "auth/x"},
         {"id": "x-yt", "platform": "youtube", "auth_dir": "auth/y"}],
        # bad platform
        [{"id": "x-tt", "platform": "tiktok", "auth_dir": "auth/x"}],
        # facebook missing page_id
        [{"id": "x-fb", "platform": "facebook", "token_file": "tokens/x.txt"}],
    ]
    for pages in cases:
        with tempfile.TemporaryDirectory() as tmp:
            p = write_registry(tmp, pages)
            try:
                multi_upload.load_registry(p)
            except ValueError:
                pass
            else:
                raise AssertionError(f"registry should reject: {pages}")
    print("PASS: (b) registry rejects duplicate id / bad platform / fb missing page_id")


def test_queue_grouping_and_unknown_target():
    with tempfile.TemporaryDirectory() as tmp:
        registry, _ = multi_upload.load_registry(write_registry(tmp, sample_pages()))
        v1 = make_video(tmp, "a.mp4")
        v2 = make_video(tmp, "b.mp4")
        v3 = make_video(tmp, "c.mp4")
        q = write_queue(tmp, [
            [v1, "A", "", "illusion|shorts", "", "", "mind-maze-yt"],
            [v2, "B", "", "", "", "", "mind-maze-fb"],
            [v3, "C", "", "", "", "", "mind-maze-yt"],
        ])
        items = multi_upload.load_queue(q, registry)
        groups = multi_upload.group_by_target(items)
        assert len(groups["mind-maze-yt"]) == 2, groups
        assert len(groups["mind-maze-fb"]) == 1, groups
        # unknown target = error
        q2 = write_queue(tmp, [[v1, "A", "", "", "", "", "no-such-page"]])
        try:
            multi_upload.load_queue(q2, registry)
        except ValueError as e:
            assert "unknown target" in str(e), e
        else:
            raise AssertionError("unknown target should be an error")
    print("PASS: (c) queue grouping by target + unknown target error")


def test_per_target_uploaded_skip():
    with tempfile.TemporaryDirectory() as tmp:
        state = os.path.join(tmp, "state")
        item_a = {"file": "v.mp4", "title": "V", "description": "",
                  "tags": [], "category_id": "22", "privacy": "private",
                  "target": "mind-maze-yt"}
        item_b = dict(item_a, target="horror-fb")
        multi_upload.record_uploaded(item_a, "vid1", "https://youtu.be/vid1",
                                     state_dir=state)
        pending = multi_upload.pending_items([item_a, item_b], state_dir=state)
        assert pending == [item_b], pending  # A skip, B (same file) pending
    print("PASS: (d) per-target uploaded-skip (same file, second target not skipped)")


def test_fb_three_phase_mocked():
    with tempfile.TemporaryDirectory() as tmp:
        vid_file = make_video(tmp, "reel.mp4")
        calls = []

        def mock_post(url, data=None, headers=None, raw_data=None):
            if raw_data is not None:
                calls.append(("upload", url, headers))
                return {"success": True}
            phase = (data or {}).get("upload_phase")
            calls.append((phase, url, data))
            if phase == "start":
                return {"video_id": "vid123",
                        "upload_url": "https://rupload.facebook.com/up/vid123"}
            return {"success": True}

        def mock_get(url):
            calls.append(("poll", url, None))
            return {"status": {"video_status": "ready"}}

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            video_id = fb_uploader.upload_reel(
                "SECRET_TOKEN_XYZ", "999", vid_file, "My reel",
                http_post=mock_post, http_get=mock_get, sleep=lambda s: None)
        assert video_id == "vid123", video_id
        order = [c[0] for c in calls]
        assert order[:3] == ["start", "upload", "finish"], order
        finish_data = calls[2][2]
        assert finish_data["video_state"] == "PUBLISHED", finish_data
        assert finish_data["video_id"] == "vid123"
        upload_headers = calls[1][2]
        assert upload_headers["Authorization"] == "OAuth SECRET_TOKEN_XYZ"
        assert upload_headers["file_size"] == "1024"
        assert "SECRET_TOKEN_XYZ" not in out.getvalue(), "token print ho gaya!"
    print("PASS: (e) fb 3-phase flow start>upload>finish, PUBLISHED, token never printed")


def test_metadata_validation_limits():
    with tempfile.TemporaryDirectory() as tmp:
        registry, _ = multi_upload.load_registry(write_registry(tmp, sample_pages()))
        good_file = make_video(tmp, "good.mp4")
        good = {"file": good_file, "title": "Theek title", "description": "short",
                "tags": ["a", "b"], "category_id": "22", "privacy": "private",
                "target": "mind-maze-yt"}
        ok, errs = multi_upload.validate_item(good, registry)
        assert ok, errs
        bad = dict(good, title="T" * 150, description="D" * 6000,
                   tags=["x" * 600], privacy="bogus", category_id="abc")
        ok, errs = multi_upload.validate_item(bad, registry)
        assert not ok and len(errs) >= 4, errs
    print("PASS: (f) metadata validation limits (title/desc/tags/privacy/category)")


def test_check_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        pages_path = write_registry(tmp, sample_pages())
        v1 = make_video(tmp, "maze.mp4")
        v2 = make_video(tmp, "horror.mp4")
        queue_path = write_queue(tmp, [
            [v1, "Mind Maze Day 1", "Stare.", "illusion|shorts", "", "", "mind-maze-yt"],
            [v2, "Horror Night 1", "Three doors.", "horror", "", "", "horror-fb"],
        ])
        old_state = multi_upload.STATE_DIR
        multi_upload.STATE_DIR = os.path.join(tmp, "state")
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = multi_upload.main(["--check", "--pages", pages_path,
                                        "--queue", queue_path])
        finally:
            multi_upload.STATE_DIR = old_state
        text = out.getvalue()
        assert rc == 0, f"--check should pass, got {rc}:\n{text}"
        assert "CHECK OK" in text, text
        assert "mind-maze-yt" in text and "horror-fb" in text, text
    print("PASS: (g) --check end-to-end (temp registry+queue, groups correctly, exit 0)")


if __name__ == "__main__":
    test_registry_load_valid()
    test_registry_rejects()
    test_queue_grouping_and_unknown_target()
    test_per_target_uploaded_skip()
    test_fb_three_phase_mocked()
    test_metadata_validation_limits()
    test_check_end_to_end()
    print("ALL LOGIC TESTS PASS")
