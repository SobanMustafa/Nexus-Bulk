"""Logic tests for downloader.py — no network, no asal download.
Run:  python3 tests/test_downloader.py

downloader.py import pe yt-dlp mangta hai (top-level import + sys.exit).
Test environment me yt-dlp ho ya na ho, yahan sys.modules me aik khaali
stub daal ke import karte hain — sirf pure logic (build_format, defaults)
test hoti hai, download wala hissa bilkul nahi chalta. Import ke
wapas aa jane se hi saabit hai ke __main__ guard ki wajah se import
pe koi download shuru nahi hua.
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# yt-dlp stub — asal library ho to bhi yehi stub use hoga is test me,
# taake test hamesha offline aur halka rahe.
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
    assert downloader.DEFAULT_QUALITY == 2160  # default 4K
    assert downloader.QUALITY_CHOICES == [720, 1080, 1440, 2160]
    print("PASS: quality defaults (default 2160=4K, choices 720/1080/1440/2160)")


if __name__ == "__main__":
    test_build_format()
    test_quality_defaults()
    print("ALL LOGIC TESTS PASS")
