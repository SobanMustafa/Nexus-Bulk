"""Logic tests for downloader.py — no network, no real download."""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Stub yt_dlp so tests run offline even if yt-dlp is not installed.
sys.modules["yt_dlp"] = types.ModuleType("yt_dlp")

import downloader  # noqa: E402


def test_build_format():
    assert downloader.build_format(2160) == \
        "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best"
    assert "height<=1440" in downloader.build_format(1440)
    assert "height<=1080" in downloader.build_format(1080)
    assert "height<=720" in downloader.build_format(720)
    print("PASS: build_format (2160=4K / 1440=2K / 1080 / 720)")


def test_quality_defaults():
    assert downloader.DEFAULT_QUALITY == 2160
    assert downloader.QUALITY_CHOICES == [720, 1080, 1440, 2160]
    print("PASS: quality defaults (default 2160=4K, choices 720/1080/1440/2160)")


def test_downloads_flag():
    args = downloader.parse_args([])
    assert args.downloads == downloader.DOWNLOADS_DIR, args.downloads
    assert args.quality == downloader.DEFAULT_QUALITY
    args = downloader.parse_args(["--downloads", "/tmp/customdl"])
    assert args.downloads == "/tmp/customdl", args.downloads
    print("PASS: --downloads flag (default = downloads/, override parse hota hai)")


if __name__ == "__main__":
    test_build_format()
    test_quality_defaults()
    test_downloads_flag()
    print("ALL LOGIC TESTS PASS")
