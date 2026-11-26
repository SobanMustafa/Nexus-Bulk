#!/usr/bin/env python3
"""
Bulk Tool — GUI App (buttons wali window, personal use only)
=============================================================
Terminal wale tool (pipeline.py / multi_upload.py) ke upar aik
modern, friendly window: double-click `run.bat` ya `python app.py`
chalao, section mein button dabao, neeche Live Log mein sab output
live nazar aata hai, aur progress bar download ka percent dikhati
hai.

Look: SkillNova-style deep navy theme — upar header band (bara
title + orange subtitle + status), panels pe numbered electric-
blue headings (1. LINKS … 5. MULTI-PAGE), green/red bare action
buttons, slate secondary buttons, neeche Live Log.

Andar se ye wahi purane commands chalata hai — koi naya engine
nahi hai. Terminal commands pehle ki tarah chalte rahenge; ye sirf
un ke upar aik aasan chehra hai.

- GUI sirf **tkinter** se bani hai — Python ke standard Windows
  installer (python.org) ke sath free aata hai, kuch alag install
  nahi karna.
- Agar tkinter na mile ya window na khul sake, app traceback ki
  bajaye saaf message de ke band ho jati hai — terminal use karo.

Chalana (Windows laptop):
    run.bat pe double-click          (sab se aasan)
    python app.py                     (ya terminal se)

Sections / buttons aur un ke terminal commands:
    DOWNLOAD card (QUEUE system — SkillNova style, engine queuedl.py):
      Links box + [Links Download Karo (Paste Wale)]
                               -> links QUEUE list mein add, phir DOWNLOAD ALL
      Queue Me Add Karo        -> sirf queue mein add (download abhi nahi)
      Shorts Grab / Videos Grab / Popular Grab
                               -> python queuedl.py --grab <channel> --grab-type shorts|videos|popular --count N
                                  (GRAB lines seedha queue mein jati hain;
                                   popular = sab se zyada views wali top-N)
      DOWNLOAD ALL             -> queue ki Pending/Failed rows gui_queue.txt mein,
                                  python queuedl.py gui_queue.txt --quality Q --threads T [--downloads F] [cookies/proxy]
      Retry Failed / Remove Selected / Clear Finished / Clear All
                               -> sirf queue list ki safai (koi command nahi)
      Advanced toggle ke andar chhoti "Pipeline" row (purana flow,
      urls.txt wala — section default band rehti hai):
      Sirf Check               -> python pipeline.py --check [--downloads <folder>]
      Download Only (urls.txt wali list)
                               -> python pipeline.py --download-only [--limit N] --quality <quality> [--downloads <folder>]
      Test 1 Video / Full Pipeline -> card 2 wale hi pipeline actions
      Update yt-dlp            -> python -m pip install -U yt-dlp
    UPLOAD — YOUTUBE card:
      Pipeline Test (1 video)  -> python pipeline.py --limit 1 --privacy <privacy> --quality <quality>
      Pipeline (Download+Upload) -> python pipeline.py --privacy <privacy> [--limit N] --quality <quality>
    MULTI UPLOAD card (Facebook + YouTube):
      Multi Check              -> python multi_upload.py --check [--target T]
      Multi Upload             -> python multi_upload.py [--target T] [--limit N]
       (multi mein privacy queue ki rows se aati hai, is liye
        wahan --privacy pass nahi hota; quality download ke waqt
        decide hoti hai, upload pe nahi, is liye multi ko --quality
        bhi pass nahi hota)

Quality dropdown: 2160 = 4K (default), 1440 = 2K, 1080, 720 —
sirf download wale actions pe lagti hai.

Threads dropdown (Download card): queue mode mein aik sath kitni
downloads — 1/2/3/4/6/8/12/16, default 4. Zyada threads = tez,
lekin net/CPU pe load bhi zyada.

Cookies dropdown (Download card) + Proxy entry (Advanced toggle
ke andar): SIRF queue wale actions (DOWNLOAD ALL aur Grab) pe
lagte hain — TikTok/Instagram
ki login wali ya block honay wali videos ke liye browser cookies
(Chrome/Edge/Firefox) ya cookies.txt file. Pipeline wale purane
buttons pe cookies/proxy apply NAHI hote.

Download Folder ("Videos kahan save hon:" — 1. LINKS section ki
sab se pehli row, window khulte hi nazar aati hai): Browse… se
koi bhi folder chun sakte ho jahan downloads jayengi — default
project ka downloads/ folder entry mein pehle se likha hota hai,
Folder Kholo us folder ko Explorer mein khol deta hai (na ho to
pehle bana ke), Reset usay wapas le aata hai. Ye folder pipeline
ke download wale actions, Check aur
queue download ko --downloads se pass hota hai; upload flow bhi
usi folder se videos uthata hai (uploads.csv wahi se banti hai).
Multi Upload ko ye pass NAHI hota — wahan queue ki rows hi sab
kuch hain.
"""
import json
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRIVACY_CHOICES = ("private", "unlisted", "public")
QUALITY_CHOICES = ("720", "1080", "1440", "2160")  # 1440 = 2K, 2160 = 4K
TARGET_PRESETS = ("mind-maze-yt", "mind-maze-fb", "horror-fb")
THREADS_CHOICES = ("1", "2", "3", "4", "6", "8", "12", "16")
GRAB_COUNT_CHOICES = ("10", "20", "30", "50")
COOKIE_MODES = ("none", "chrome", "edge", "firefox", "file")
# Queue row ki status values (tree + stats inhi pe chalte hain)
Q_PENDING = "Pending"
Q_DOWNLOADING = "Downloading"
Q_DONE = "Done"
Q_FAILED = "Failed"
Q_SKIPPED = "Skipped"

# --- SkillNova-style deep navy theme (sirf GUI in ko use karti hai) ---
BG = "#0A0E27"              # window background — deep navy
PANEL = "#0F1638"           # section panels
BORDER = "#22306E"          # panel / field borders
TEXT = "#E8ECF8"            # primary text
LABEL = "#D6DBF2"           # normal labels
MUTED = "#8A94B8"           # secondary / hint text
BLUE = "#2E7CF6"            # primary blue — YouTube pipeline / focus / selection
BLUE_ACTIVE = "#1F63CC"
BLUE_BRIGHT = "#4DA3FF"     # section headings / stats line (electric blue)
ORANGE = "#F39C3C"          # header subtitle
GREEN = "#22B14C"           # download
GREEN_ACTIVE = "#1B8C3C"
MULTI = "#2E5BFF"           # multi upload accent
MULTI_ACTIVE = "#2449CC"
RED = "#E63B2E"             # stop / error
RED_ACTIVE = "#C22E23"
SLATE = "#232C52"           # secondary buttons
SLATE_ACTIVE = "#2C3870"
SLATE_BORDER = "#2E3B78"    # secondary button border
INPUT_BG = "#0B1130"        # entries / dropdowns / inputs
TREE_HEAD_BG = "#16225C"    # queue table heading row
LOG_BG = "#070B1F"
LOG_FG = "#C9D4F2"

FONT_UI = ("Segoe UI", 10)
FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_SUBTITLE = ("Segoe UI", 10, "bold")
FONT_SECTION = ("Segoe UI", 11, "bold")
FONT_BTN = ("Segoe UI", 10, "bold")
FONT_SMALL = ("Segoe UI", 9)
FONT_STATS = ("Segoe UI", 9, "bold")
FONT_TREE_HEAD = ("Segoe UI", 10, "bold")
FONT_STATUS = ("Segoe UI", 11, "bold")
FONT_LOG = ("Consolas", 10)

# NOTE: tkinter yahan import NAHI hota — sirf main() ke andar,
# taake `import app` baghair display ke bhi chal jaye (tests ke liye).


def _parse_limit(limit):
    """Limit field -> int ya None. Khaali = None (koi limit nahi)."""
    if limit is None:
        return None
    s = str(limit).strip()
    if not s:
        return None
    try:
        n = int(s)
    except ValueError:
        raise ValueError(
            f"Limit ghalat hai: {limit!r} — sirf number likho (e.g. 1, 5) "
            f"ya khaali chhor do."
        ) from None
    if n <= 0:
        raise ValueError(
            f"Limit ghalat hai: {limit!r} — 1 ya us se bara number likho "
            f"ya khaali chhor do."
        )
    return n


def _parse_privacy(privacy):
    p = (privacy or "private").strip().lower()
    if p not in PRIVACY_CHOICES:
        raise ValueError(
            f"Privacy ghalat hai: {privacy!r} — in mein se aik ho: "
            f"{', '.join(PRIVACY_CHOICES)}"
        )
    return p


def _parse_quality(quality):
    q = str(quality or "2160").strip()
    if q not in QUALITY_CHOICES:
        raise ValueError(
            f"Quality ghalat hai: {quality!r} — in mein se aik ho: "
            f"{', '.join(QUALITY_CHOICES)} (2160=4K, 1440=2K)"
        )
    return q


def _parse_threads(threads):
    t = str(threads or "4").strip()
    if t not in THREADS_CHOICES:
        raise ValueError(
            f"Threads ghalat hai: {threads!r} — in mein se aik ho: "
            f"{', '.join(THREADS_CHOICES)}"
        )
    return t


def _parse_grab_count(count):
    c = str(count or "50").strip()
    if c not in GRAB_COUNT_CHOICES:
        raise ValueError(
            f"Count ghalat hai: {count!r} — in mein se aik ho: "
            f"{', '.join(GRAB_COUNT_CHOICES)}"
        )
    return c


def _cookie_args(cookies):
    """cookies=(mode, path) -> queuedl ke cookie args.

    mode: "none" | "chrome" | "edge" | "firefox" | "file".
    Sirf queue/grab commands mein lagte hain — pipeline wale
    actions in ko ignore karte hain.
    """
    try:
        mode, path = cookies
    except (TypeError, ValueError):
        raise ValueError(
            f"Cookies ghalat hai: {cookies!r} — (mode, path) do, "
            f"mode in mein se: {', '.join(COOKIE_MODES)}"
        ) from None
    mode = str(mode or "none").strip().lower()
    path = str(path or "").strip()
    if mode not in COOKIE_MODES:
        raise ValueError(
            f"Cookies mode ghalat hai: {mode!r} — in mein se aik ho: "
            f"{', '.join(COOKIE_MODES)}"
        )
    if mode == "none":
        return []
    if mode == "file":
        if not path:
            raise ValueError(
                "Cookies file mode hai lekin koi file nahi chuni — "
                "dropdown se cookies.txt wali file select karo."
            )
        return ["--cookies-file", path]
    return ["--cookies-from-browser", mode]


def _proxy_args(proxy):
    p = str(proxy or "").strip()
    return ["--proxy", p] if p else []


def extract_links(text):
    """Paste box ka text -> saaf links ki list. Pure function — koi I/O nahi.

    Aik line = aik link: blank lines aur '#' se shuru hone wali
    lines skip, sirf http:// ya https:// se shuru hone wali lines
    rakho, duplicates hata ke order waisa hi rakho.
    """
    links, seen = [], set()
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not (line.startswith("http://") or line.startswith("https://")):
            continue
        if line in seen:
            continue
        seen.add(line)
        links.append(line)
    return links


def build_command(action, limit="", target="", privacy="private", quality="2160",
                  download_dir="", urls_file="", threads="4",
                  cookies=("none", ""), proxy="", grab_url="",
                  grab_count="50"):
    """Action -> command list. Pure function — koi window, koi subprocess nahi.

    Script names app wale folder ke relative hain; GUI in ko
    cwd=BASE_DIR ke sath chalati hai.

    download_dir: pipeline ke download wale actions (download_only,
    pipeline_test1, pipeline) aur check ko --downloads se pass hota
    hai — check bhi usi folder ko scan karke uploads.csv banata hai.
    Queue download (queue_download) ko bhi pass hota hai. Khaali/
    whitespace ho to pass NAHI hota (script ka apna default
    downloads/ lagta hai). Multi actions ko kabhi pass nahi hota.

    urls_file: download wale pipeline actions (download_only,
    pipeline_test1, pipeline) ko --urls se pass hota hai. Queue
    download ke liye yehi param queue file ka path hai (GUI
    gui_queue.txt deta hai; khaali ho to wahi default lagta hai).
    Check / multi ko kabhi pass nahi hota.

    threads / cookies / proxy: SIRF queue system (queue_download
    aur grab_*) ke liye hain — baaki actions in ko ignore karte
    hain. cookies=(mode, path), dekho _cookie_args.
    """
    py = sys.executable
    lim = _parse_limit(limit)
    tgt = (target or "").strip()
    q = _parse_quality(quality)
    dl = (download_dir or "").strip()
    uf = (urls_file or "").strip()

    if action == "check":
        cmd = [py, "pipeline.py", "--check"]
        if dl:
            cmd += ["--downloads", dl]
        return cmd

    if action == "download_only":
        cmd = [py, "pipeline.py", "--download-only"]
        if lim is not None:
            cmd += ["--limit", str(lim)]
        cmd += ["--quality", q]
        if dl:
            cmd += ["--downloads", dl]
        if uf:
            cmd += ["--urls", uf]
        return cmd

    if action == "pipeline_test1":
        cmd = [py, "pipeline.py", "--limit", "1",
               "--privacy", _parse_privacy(privacy), "--quality", q]
        if dl:
            cmd += ["--downloads", dl]
        if uf:
            cmd += ["--urls", uf]
        return cmd

    if action == "pipeline":
        cmd = [py, "pipeline.py", "--privacy", _parse_privacy(privacy)]
        if lim is not None:
            cmd += ["--limit", str(lim)]
        cmd += ["--quality", q]
        if dl:
            cmd += ["--downloads", dl]
        if uf:
            cmd += ["--urls", uf]
        return cmd

    if action == "queue_download":
        cmd = [py, "queuedl.py", uf or "gui_queue.txt",
               "--quality", q, "--threads", _parse_threads(threads)]
        if dl:
            cmd += ["--downloads", dl]
        cmd += _cookie_args(cookies)
        cmd += _proxy_args(proxy)
        return cmd

    if action in ("grab_shorts", "grab_videos", "grab_popular"):
        url = (grab_url or "").strip()
        if not url:
            raise ValueError(
                "Channel / Profile link khaali hai — pehle upar wale "
                "field mein channel ka link likho."
            )
        grab_type = {"grab_shorts": "shorts", "grab_videos": "videos",
                     "grab_popular": "popular"}[action]
        cmd = [py, "queuedl.py", "--grab", url,
               "--grab-type", grab_type,
               "--count", _parse_grab_count(grab_count)]
        cmd += _cookie_args(cookies)
        cmd += _proxy_args(proxy)
        return cmd

    if action == "update_ytdlp":
        return [py, "-m", "pip", "install", "-U", "yt-dlp"]

    if action == "multi_check":
        cmd = [py, "multi_upload.py", "--check"]
        if tgt:
            cmd += ["--target", tgt]
        return cmd

    if action == "multi_upload":
        # NOTE: multi_upload.py ke paas --privacy flag hai hi nahi —
        # wahan privacy queue ki har row se aati hai.
        cmd = [py, "multi_upload.py"]
        if tgt:
            cmd += ["--target", tgt]
        if lim is not None:
            cmd += ["--limit", str(lim)]
        return cmd

    raise ValueError(
        f"Unknown action: {action!r} — sahi actions: check, download_only, "
        f"pipeline_test1, pipeline, multi_check, multi_upload, "
        f"queue_download, grab_shorts, grab_videos, grab_popular, "
        f"update_ytdlp"
    )


_QITEM_RE = re.compile(
    r"^QITEM\s+(\d+)\s+(START|PROGRESS|DONE|FAILED|SKIPPED)\s+(\d+)\s*$")
_QDONE_RE = re.compile(
    r"^QDONE\s+total=(\d+)\s+done=(\d+)\s+failed=(\d+)\s+skipped=(\d+)\s*$")


def parse_qitem(line):
    """queuedl ki 'QITEM <i> <STATUS> <pct>' line -> (index, status, pct).

    STATUS: START / PROGRESS / DONE / FAILED / SKIPPED. Line match
    na ho (ya khaali/garbage ho) to None. Pure function.
    """
    if not line:
        return None
    m = _QITEM_RE.match(str(line).strip())
    if m is None:
        return None
    return int(m.group(1)), m.group(2), int(m.group(3))


def parse_grab_line(line):
    """queuedl ki 'GRAB <url>' line -> url, warna None.

    Note: 'GRABDONE 5' is se match NAHI hoti — 'GRAB ' ke baad
    space lazmi hai aur baaki hissa http se shuru hona chahiye.
    """
    if not line:
        return None
    s = str(line).strip()
    if not s.startswith("GRAB "):
        return None
    url = s[len("GRAB "):].strip()
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return None


def parse_grab_meta(line):
    """queuedl ki 'GRABMETA <json>' line -> {"url", "title", "views"}, warna None."""
    if not line:
        return None
    s = str(line).strip()
    if not s.startswith("GRABMETA "):
        return None
    try:
        data = json.loads(s[len("GRABMETA "):])
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    url = str(data.get("url") or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return None
    views = data.get("views")
    if isinstance(views, bool) or not isinstance(views, (int, float)):
        views = None
    return {
        "url": url,
        "title": str(data.get("title") or "").strip(),
        "views": views,
    }


def format_views(views):
    """View count ko short insaani shakal me badlo (e.g. 1.2M, 43.6K, 850, —)."""
    if isinstance(views, bool) or not isinstance(views, (int, float)):
        return "—"
    v = int(views)
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v / 1_000:.1f}K"
    return str(v)


def parse_qdone(line):
    """'QDONE total=N done=N failed=N skipped=N' -> dict, warna None."""
    if not line:
        return None
    m = _QDONE_RE.match(str(line).strip())
    if m is None:
        return None
    return {"total": int(m.group(1)), "done": int(m.group(2)),
            "failed": int(m.group(3)), "skipped": int(m.group(4))}


def queue_stats(rows):
    """Queue rows -> stats dict. Pure function.

    Row = dict jiska 'status' Q_PENDING / Q_DOWNLOADING / Q_DONE /
    Q_FAILED / Q_SKIPPED mein se aik hai. 'remaining' = Pending
    (abhi shuru nahi hue); Downloading alag gina jata hai.
    """
    stats = {"total": len(rows), "downloaded": 0, "remaining": 0,
             "downloading": 0, "failed": 0, "skipped": 0}
    for r in rows:
        st = r.get("status")
        if st == Q_DONE:
            stats["downloaded"] += 1
        elif st == Q_PENDING:
            stats["remaining"] += 1
        elif st == Q_DOWNLOADING:
            stats["downloading"] += 1
        elif st == Q_FAILED:
            stats["failed"] += 1
        elif st == Q_SKIPPED:
            stats["skipped"] += 1
    return stats


def dedupe_new(existing_urls, new_links):
    """new_links mein se sirf wo jo existing mein nahi hain —
    batch ke andar ke duplicates bhi aik dafa. Order waisa hi."""
    seen = set(existing_urls or [])
    out = []
    for link in new_links or []:
        if link in seen:
            continue
        seen.add(link)
        out.append(link)
    return out


_PROGRESS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def parse_progress(line):
    """Aik output line se download percent nikalo — warna None.

    yt-dlp ki progress lines aisi hoti hain:
        [download]  45.3% of  120.00MiB at  2.00MiB/s ETA 00:30
        [download] 100% of  120.00MiB in 00:01:00
    Percent wali koi line na ho (ya khaali/garbage ho) to None.
    Pure function — GUI isay har line pe chala ke progress bar
    update karti hai.
    """
    if not line:
        return None
    m = _PROGRESS_RE.search(str(line))
    if m is None:
        return None
    try:
        pct = float(m.group(1))
    except ValueError:
        return None
    return max(0.0, min(100.0, pct))


TKINTER_MISSING_MSG = (
    "Bulk Tool GUI: Python ka tkinter nahi mila, is liye window nahi khul sakti.\n"
    "Koi baat nahi — tool terminal se bilkul waisa hi chalta hai:\n"
    "  python pipeline.py --check\n"
    "  python pipeline.py --limit 1\n"
    "  python multi_upload.py --check\n"
    "tkinter python.org wale standard Python installer ke sath aata hai —\n"
    "agar custom/minimal Python hai to poora Python dobara install karne se aa jayega."
)

DISPLAY_MISSING_MSG = (
    "Bulk Tool GUI: window nahi khul saki (display nahi mila).\n"
    "Ye aksar headless/remote session mein hota hai — terminal commands use karo:\n"
    "  python pipeline.py --check\n"
    "  python multi_upload.py --check"
)


def _build_gui(tk, scrolledtext):
    """Window banao aur mainloop chalao. tkinter pehle se import shuda ho."""
    import queue
    import subprocess
    import threading
    from tkinter import filedialog, ttk

    root = tk.Tk()
    root.title("Bulk Tool")
    root.geometry("940x760")
    root.minsize(860, 680)
    root.configure(bg=BG)

    # ttk styles — clam theme pe progress bar / combobox ke rang lagte hain
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(
        "Modern.Horizontal.TProgressbar",
        troughcolor=INPUT_BG, background=GREEN,
        bordercolor=BG, lightcolor=GREEN, darkcolor=GREEN,
        thickness=14,
    )
    style.configure(
        "Dark.TCombobox",
        fieldbackground=INPUT_BG, background=SLATE,
        foreground=TEXT, arrowcolor=TEXT,
        bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
        padding=4,
    )
    root.option_add("*TCombobox*Listbox.background", INPUT_BG)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", BLUE)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    style.configure(
        "Dark.Treeview",
        background=PANEL, fieldbackground=PANEL,
        foreground=TEXT, bordercolor=BORDER,
        lightcolor=BORDER, darkcolor=BORDER, rowheight=22,
        font=FONT_SMALL,
    )
    style.configure(
        "Dark.Treeview.Heading",
        background=TREE_HEAD_BG, foreground="#ffffff",
        bordercolor=BORDER, font=FONT_TREE_HEAD,
    )
    style.map("Dark.Treeview",
              background=[("selected", BLUE)],
              foreground=[("selected", "#ffffff")])
    style.configure(
        "Dark.Vertical.TScrollbar",
        background=SLATE, troughcolor=BG, bordercolor=BORDER,
        arrowcolor=TEXT, lightcolor=BORDER, darkcolor=BORDER,
    )

    state = {"proc": None, "running": False, "stopped": False,
             "run_kind": None, "run_row_ids": []}
    out_queue = queue.Queue()
    buttons = []

    main = tk.Frame(root, bg=BG)
    main.pack(fill="both", expand=True, padx=14, pady=12)

    # ---------- chhote widget helpers ----------
    def field_label(parent, text):
        return tk.Label(parent, text=text, font=FONT_UI,
                        bg=PANEL, fg=LABEL)

    def hint_label(parent, text):
        return tk.Label(parent, text=text, font=FONT_SMALL,
                        bg=PANEL, fg=MUTED)

    def dark_entry(parent, var, width):
        return tk.Entry(
            parent, textvariable=var, width=width, bg=INPUT_BG,
            fg=TEXT, insertbackground=TEXT, relief="flat",
            font=FONT_UI, highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=BLUE)

    def dark_option_menu(parent, var, values, width=8):
        om = tk.OptionMenu(parent, var, *values)
        om.config(bg=INPUT_BG, fg=TEXT,
                  activebackground=SLATE_ACTIVE, activeforeground=TEXT,
                  relief="flat", bd=0, highlightthickness=1,
                  highlightbackground=BORDER, font=FONT_UI,
                  cursor="hand2", width=width)
        try:
            om["menu"].config(bg=INPUT_BG, fg=TEXT,
                              activebackground=BLUE,
                              activeforeground="#ffffff")
        except tk.TclError:
            pass
        return om

    def primary_btn(parent, text, color, active, command):
        return tk.Button(
            parent, text=text, command=command, bg=color, fg="#ffffff",
            activebackground=active, activeforeground="#ffffff",
            relief="flat", bd=0, font=FONT_BTN, padx=14, pady=12,
            cursor="hand2", disabledforeground="#cfd4de")

    def secondary_btn(parent, text, command):
        return tk.Button(
            parent, text=text, command=command, bg=SLATE, fg=TEXT,
            activebackground=SLATE_ACTIVE, activeforeground=TEXT,
            relief="flat", bd=0, font=FONT_BTN, padx=14, pady=10,
            cursor="hand2", disabledforeground=MUTED,
            highlightthickness=1, highlightbackground=SLATE_BORDER,
            highlightcolor=SLATE_BORDER)

    def small_btn(parent, text, command):
        return tk.Button(
            parent, text=text, command=command, bg=SLATE, fg=TEXT,
            activebackground=SLATE_ACTIVE, activeforeground=TEXT,
            relief="flat", bd=0, font=FONT_UI, padx=10, pady=5,
            cursor="hand2", disabledforeground=MUTED,
            highlightthickness=1, highlightbackground=SLATE_BORDER,
            highlightcolor=SLATE_BORDER)

    def section_heading(parent, text):
        """SkillNova-style numbered heading: electric-blue caps text
        + neeche patli divider line."""
        tk.Label(parent, text=text, font=FONT_SECTION,
                 bg=PANEL, fg=BLUE_BRIGHT).pack(anchor="w")
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", pady=(4, 8))

    def make_card(heading=None):
        card = tk.Frame(content, bg=PANEL, padx=14, pady=12,
                        highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", pady=(0, 10))
        if heading:
            section_heading(card, heading)
        return card

    # ---------- header band ----------
    header = tk.Frame(main, bg=PANEL, padx=14, pady=10,
                      highlightthickness=1, highlightbackground=BORDER)
    header.pack(fill="x", pady=(0, 10))
    head_left = tk.Frame(header, bg=PANEL)
    head_left.pack(side="left")
    tk.Label(head_left, text="Bulk Tool", font=FONT_TITLE,
             bg=PANEL, fg="#ffffff").pack(anchor="w")
    tk.Label(head_left, text="Downloader • Uploader • Multi-Page",
             font=FONT_SUBTITLE, bg=PANEL, fg=ORANGE).pack(anchor="w")
    status_var = tk.StringVar(value="● Ready")
    status_lbl = tk.Label(header, textvariable=status_var, font=FONT_STATUS,
                          bg=PANEL, fg=MUTED)
    status_lbl.pack(side="right", anchor="n", pady=8)

    def set_status(text, color):
        status_var.set(text)
        status_lbl.config(fg=color)

    # ---------- scrollable content ----------
    # Header band FIXED rehta hai; us ke neeche ki saari cards is
    # canvas ke andar scroll hoti hain — laptop ki chhoti screen pe
    # bhi koi hissa hamesha ke liye ghayab nahi hota.
    canvas = tk.Canvas(main, bg=BG, highlightthickness=0, bd=0,
                       relief="flat")
    canvas_scroll = ttk.Scrollbar(main, orient="vertical",
                                  command=canvas.yview,
                                  style="Dark.Vertical.TScrollbar")
    canvas.configure(yscrollcommand=canvas_scroll.set)
    canvas_scroll.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    content = tk.Frame(canvas, bg=BG)
    content_win = canvas.create_window((0, 0), window=content, anchor="nw")
    content.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind(
        "<Configure>",
        lambda e: canvas.itemconfigure(content_win, width=e.width))

    def _mousewheel(event):
        if getattr(event, "num", None) == 4:
            canvas.yview_scroll(-1, "units")
        elif getattr(event, "num", None) == 5:
            canvas.yview_scroll(1, "units")
        elif getattr(event, "delta", 0):
            steps = int(-event.delta / 120)
            if steps:
                canvas.yview_scroll(steps, "units")

    root.bind_all("<MouseWheel>", _mousewheel)
    root.bind_all("<Button-4>", _mousewheel)
    root.bind_all("<Button-5>", _mousewheel)

    # ---------- card 1: DOWNLOAD (queue system) ----------
    quality_var = tk.StringVar(value="2160")
    limit_var = tk.StringVar()
    threads_var = tk.StringVar(value="4")
    channel_var = tk.StringVar()
    grab_count_var = tk.StringVar(value="10")
    cookies_var = tk.StringVar(value="None")
    cookies_file = {"path": ""}  # cookies.txt mode mein chuni hui file
    cookies_file_var = tk.StringVar(value="")
    proxy_var = tk.StringVar()
    default_downloads = os.path.join(BASE_DIR, "downloads")
    download_dir_var = tk.StringVar(value=default_downloads)
    card1 = make_card()

    def browse_folder():
        chosen = filedialog.askdirectory(
            initialdir=download_dir_var.get() or BASE_DIR,
            title="Download folder chuno")
        if chosen:
            download_dir_var.set(chosen)

    def reset_folder():
        download_dir_var.set(default_downloads)

    def open_download_folder():
        path = download_dir_var.get().strip() or default_downloads
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            write_log(f"\nFolder ban nahi saka — {e}\nPath: {path}\n")
            return
        open_folder(path)

    section_heading(card1, "1. LINKS")
    # 0) Download Folder — section ki SAB SE PEHLI row, taake window
    # khulte hi saaf pata ho downloads kahan jati hain. (Pehle ye
    # window ke bilkul neeche thi — laptop pe nazar hi nahi aati thi.)
    tk.Label(card1, text="Videos kahan save hon:", font=FONT_BTN,
             bg=PANEL, fg=TEXT).pack(anchor="w", pady=(0, 4))
    dlrow = tk.Frame(card1, bg=PANEL)
    dlrow.pack(fill="x")
    dark_entry(dlrow, download_dir_var, 52).pack(
        side="left", fill="x", expand=True, padx=(0, 6))
    small_btn(dlrow, "Browse…", browse_folder).pack(side="left", padx=(0, 6))
    small_btn(dlrow, "Folder Kholo", open_download_folder).pack(
        side="left", padx=(0, 6))
    small_btn(dlrow, "Reset", reset_folder).pack(side="left")
    hint_label(card1, "Is folder ke andar platform / channel ke "
                      "subfolder ban ke videos save hongi.").pack(
        anchor="w", pady=(4, 10))
    # 1) Paste links box — links seedha yahan paste karo, urls.txt
    # edit karne ki zaroorat nahi.
    tk.Label(card1,
             text="Video Links — yahan paste karo "
                  "(aik line = aik link: YouTube / TikTok / Facebook…)",
             font=FONT_UI, bg=PANEL, fg=TEXT).pack(
        anchor="w", pady=(0, 4))
    links_frame = tk.Frame(card1, bg=PANEL)
    links_frame.pack(fill="x", pady=(0, 8))
    links_text = tk.Text(
        links_frame, height=4, bg=INPUT_BG, fg=TEXT,
        insertbackground=TEXT, relief="flat", font=("Segoe UI", 10),
        highlightthickness=1, highlightbackground=BORDER,
        highlightcolor=BLUE, wrap="word")
    links_scroll = tk.Scrollbar(links_frame, orient="vertical",
                                command=links_text.yview,
                                bg=SLATE, troughcolor=PANEL,
                                activebackground=SLATE_ACTIVE,
                                relief="flat", bd=0)
    links_text.config(yscrollcommand=links_scroll.set)
    links_scroll.pack(side="right", fill="y")
    links_text.pack(side="left", fill="x", expand=True)
    btns0 = tk.Frame(card1, bg=PANEL)
    btns0.pack(fill="x", pady=(0, 10))
    b_paste = primary_btn(btns0, "Links Download Karo (Paste Wale)",
                          GREEN, GREEN_ACTIVE,
                          lambda: on_paste_download())
    b_paste.pack(side="left", fill="x", expand=True, padx=(0, 6))
    b_add_queue = secondary_btn(btns0, "Queue Me Add Karo",
                                lambda: on_add_to_queue())
    b_add_queue.pack(side="left")
    # 2) Channel / Profile grab row
    section_heading(card1, "2. CHANNEL / PROFILE")
    grow = tk.Frame(card1, bg=PANEL)
    grow.pack(fill="x", pady=(0, 6))
    field_label(grow, "Channel / Profile link:").pack(side="left")
    dark_entry(grow, channel_var, 40).pack(
        side="left", fill="x", expand=True, padx=(6, 0))
    grow2 = tk.Frame(card1, bg=PANEL)
    grow2.pack(fill="x", pady=(0, 10))
    b_grab_p = primary_btn(grow2, "Top Videos Grab Karo", BLUE, BLUE_ACTIVE,
                           lambda: on_grab("popular"))
    b_grab_p.pack(side="left", padx=(0, 10))
    field_label(grow2, "Count:").pack(side="left")
    dark_option_menu(grow2, grab_count_var, GRAB_COUNT_CHOICES,
                     width=5).pack(side="left", padx=(6, 12))
    b_grab_v = small_btn(grow2, "Videos", lambda: on_grab("videos"))
    b_grab_v.pack(side="left", padx=(0, 6))
    b_grab_s = small_btn(grow2, "Shorts", lambda: on_grab("shorts"))
    b_grab_s.pack(side="left", padx=(0, 8))
    hint_label(grow2, "Top = highest views pehle").pack(side="left")
    # 3) QUEUE list — har link aik row: status live update hota hai
    section_heading(card1, "3. QUEUE")
    tree_frame = tk.Frame(card1, bg=PANEL)
    tree_frame.pack(fill="x", pady=(0, 6))
    tree = ttk.Treeview(tree_frame, columns=("num", "video", "views", "status"),
                        show="headings", height=6, style="Dark.Treeview",
                        selectmode="extended")
    tree.heading("num", text="#")
    tree.heading("video", text="Video / Link")
    tree.heading("views", text="Views")
    tree.heading("status", text="Status")
    tree.column("num", width=38, minwidth=32, stretch=False, anchor="center")
    tree.column("video", width=430, minwidth=180, stretch=True)
    tree.column("views", width=85, minwidth=65, stretch=False, anchor="e")
    tree.column("status", width=170, minwidth=130, stretch=False)
    tree_scroll = tk.Scrollbar(tree_frame, orient="vertical",
                               command=tree.yview,
                               bg=SLATE, troughcolor=PANEL,
                               activebackground=SLATE_ACTIVE,
                               relief="flat", bd=0)
    tree.config(yscrollcommand=tree_scroll.set)
    tree_scroll.pack(side="right", fill="y")
    tree.pack(side="left", fill="x", expand=True)
    # 4) Queue buttons
    qbtns = tk.Frame(card1, bg=PANEL)
    qbtns.pack(fill="x", pady=(0, 6))
    b_dl_all = primary_btn(qbtns, "DOWNLOAD ALL", GREEN,
                           GREEN_ACTIVE,
                           lambda: start_download_all())
    b_dl_all.pack(side="left", fill="x", expand=True, padx=(0, 6))
    b_stop_all = tk.Button(
        qbtns, text="STOP ALL", command=lambda: stop_proc(),
        bg=RED, fg="#ffffff", activebackground=RED_ACTIVE,
        activeforeground="#ffffff", relief="flat", bd=0, font=FONT_BTN,
        padx=16, pady=12, cursor="hand2")
    b_stop_all.pack(side="left")
    qbtns2 = tk.Frame(card1, bg=PANEL)
    qbtns2.pack(fill="x", pady=(0, 6))
    b_retry = small_btn(qbtns2, "Retry Failed",
                        lambda: start_download_all(only_failed=True))
    b_retry.pack(side="left", padx=(0, 6))
    b_remove = small_btn(qbtns2, "Remove Selected",
                         lambda: on_remove_selected())
    b_remove.pack(side="left", padx=(0, 6))
    b_clear_fin = small_btn(qbtns2, "Clear Finished",
                            lambda: on_clear_finished())
    b_clear_fin.pack(side="left", padx=(0, 6))
    b_clear_all = small_btn(qbtns2, "Clear All",
                            lambda: on_clear_all())
    b_clear_all.pack(side="left")
    # 5) Stats label
    stats_var = tk.StringVar(
        value="Total: 0 | Downloaded: 0 | Remaining: 0 | "
              "Downloading: 0 | Failed: 0")
    tk.Label(card1, textvariable=stats_var, font=FONT_STATS,
             bg=PANEL, fg=BLUE_BRIGHT).pack(anchor="w", pady=(0, 8))
    # ---------- queue state + helpers (DOWNLOAD card) ----------
    queue_rows = []          # [{"url", "title", "views", "status", "pct", "iid"}]
    queue_ids = {"next": 0}  # tree item ids ka counter
    pending_meta = {}        # url -> {"title", "views"} from GRABMETA

    def row_status_text(row):
        st = row["status"]
        if st == Q_DOWNLOADING:
            return f"Downloading… {row['pct']}%"
        if st == Q_DONE:
            return "Done ✓"
        if st == Q_FAILED:
            return "Failed ✗"
        if st == Q_SKIPPED:
            return "Skipped (pehle se hai)"
        return "Pending"

    def update_stats():
        s = queue_stats(queue_rows)
        stats_var.set(
            f"Total: {s['total']} | Downloaded: {s['downloaded']} | "
            f"Remaining: {s['remaining']} | "
            f"Downloading: {s['downloading']} | Failed: {s['failed']}")

    def row_display_values(num, row):
        label = row.get("title") or row["url"]
        return (num, label, format_views(row.get("views")),
                row_status_text(row))

    def refresh_queue_view():
        for iid in tree.get_children():
            tree.delete(iid)
        for n, row in enumerate(queue_rows, 1):
            tree.insert("", "end", iid=row["iid"],
                        values=row_display_values(n, row))
        update_stats()

    def add_links_to_queue(links, announce=True, meta_map=None):
        """Links queue mein add karo (dedupe ke sath). Naye add hue gin ke do."""
        new = dedupe_new([r["url"] for r in queue_rows], links)
        meta_map = meta_map or {}
        for url in new:
            queue_ids["next"] += 1
            iid = f"q{queue_ids['next']}"
            m = meta_map.get(url) or {}
            row = {
                "url": url,
                "title": m.get("title", ""),
                "views": m.get("views"),
                "status": Q_PENDING,
                "pct": 0,
                "iid": iid,
            }
            queue_rows.append(row)
            tree.insert("", "end", iid=iid,
                        values=row_display_values(len(queue_rows), row))
        if new:
            update_stats()
        if announce:
            write_log(f"Queue me {len(new)} naye link(s) add hue "
                      f"(kul {len(queue_rows)})\n")
        return len(new)

    def update_run_row(index, status, pct):
        """QITEM line -> chal rahi run ki row ka status + overall progress."""
        ids = state.get("run_row_ids") or []
        if index < 0 or index >= len(ids):
            return
        iid = ids[index]
        row = next((r for r in queue_rows if r["iid"] == iid), None)
        if row is None:
            return
        if status in ("START", "PROGRESS"):
            row["status"] = Q_DOWNLOADING
            row["pct"] = pct
        elif status == "DONE":
            row["status"] = Q_DONE
            row["pct"] = 100
        elif status == "FAILED":
            row["status"] = Q_FAILED
            row["pct"] = pct
        elif status == "SKIPPED":
            row["status"] = Q_SKIPPED
            row["pct"] = 100
        try:
            tree.set(iid, "status", row_status_text(row))
        except tk.TclError:
            pass
        update_stats()
        run_rows = [r for r in queue_rows if r["iid"] in ids]
        if run_rows:
            avg = sum(r["pct"] for r in run_rows) / len(run_rows)
            progress.stop()
            progress.config(mode="determinate", value=avg)
            progress_text.set(f"{avg:g}%")

    def on_add_to_queue():
        links = extract_links(links_text.get("1.0", "end"))
        if not links:
            write_log("\nPehle box me kam az kam aik link paste karo.\n")
            return
        add_links_to_queue(links)

    def on_paste_download():
        """Paste wale links queue mein add + (kuch na chal raha ho to)
        DOWNLOAD ALL shuru. Chal rahi run mein naye links NAHI jate —
        wo agli DOWNLOAD ALL mein ayenge."""
        links = extract_links(links_text.get("1.0", "end"))
        if links:
            add_links_to_queue(links)
        if state["running"]:
            if links:
                write_log("Chal rahi download me ye nahi aayenge — "
                          "agli DOWNLOAD ALL me aayenge.\n")
            return
        if not any(r["status"] in (Q_PENDING, Q_FAILED) for r in queue_rows):
            write_log("\nPehle box me kam az kam aik link paste karo.\n")
            set_status("● Error", RED)
            return
        start_download_all()

    def start_download_all(only_failed=False):
        """Pending (ya sirf Failed) rows -> gui_queue.txt -> queuedl run."""
        if state["running"]:
            return
        if only_failed:
            targets = [r for r in queue_rows if r["status"] == Q_FAILED]
            for r in targets:
                r["status"] = Q_PENDING
                r["pct"] = 0
            if targets:
                refresh_queue_view()
        else:
            targets = [r for r in queue_rows
                       if r["status"] in (Q_PENDING, Q_FAILED)]
        if not targets:
            write_log("Queue me download ke liye koi Pending link "
                      "nahi hai.\n")
            return
        queue_path = os.path.join(BASE_DIR, "gui_queue.txt")
        try:
            with open(queue_path, "w", encoding="utf-8") as f:
                f.write("\n".join(r["url"] for r in targets) + "\n")
        except OSError as e:
            write_log(f"\nERROR: gui_queue.txt likh nahi saka — {e}\n")
            set_status("● Error", RED)
            return
        state["run_row_ids"] = [r["iid"] for r in targets]
        state["run_kind"] = "queue"
        run_action("queue_download", urls_file=queue_path)

    def on_grab(kind):
        url = channel_var.get().strip()
        if not url:
            write_log("\nPehle Channel / Profile link likho.\n")
            set_status("● Error", RED)
            return
        if state["running"]:
            return
        state["run_kind"] = "grab"
        run_action({"shorts": "grab_shorts", "videos": "grab_videos",
                    "popular": "grab_popular"}[kind],
                   grab_url=url)

    def on_remove_selected():
        if state["running"]:
            write_log("Download chal rahi hai — pehle Stop karo.\n")
            return
        sel = set(tree.selection())
        if not sel:
            write_log("Pehle queue me se koi row select karo.\n")
            return
        queue_rows[:] = [r for r in queue_rows if r["iid"] not in sel]
        refresh_queue_view()
        write_log("Selected row(s) queue se hata diye.\n")

    def on_clear_finished():
        if state["running"]:
            write_log("Download chal rahi hai — pehle Stop karo.\n")
            return
        queue_rows[:] = [r for r in queue_rows
                         if r["status"] not in (Q_DONE, Q_SKIPPED)]
        refresh_queue_view()

    def on_clear_all():
        if state["running"]:
            write_log("Download chal rahi hai — pehle Stop karo.\n")
            return
        queue_rows.clear()
        refresh_queue_view()

    def on_cookies_change(choice):
        if choice.startswith("cookies.txt"):
            path = filedialog.askopenfilename(
                title="cookies.txt file chuno",
                filetypes=[("Text files", "*.txt"),
                           ("All files", "*.*")])
            if path:
                cookies_file["path"] = path
                cookies_file_var.set(os.path.basename(path))
            else:  # cancel -> wapas None
                cookies_var.set("None")
                cookies_file["path"] = ""
                cookies_file_var.set("")
        else:
            cookies_file["path"] = ""
            cookies_file_var.set("")

    def current_cookies():
        label = cookies_var.get()
        if label == "Chrome":
            return ("chrome", "")
        if label == "Edge":
            return ("edge", "")
        if label == "Firefox":
            return ("firefox", "")
        if label.startswith("cookies.txt"):
            return ("file", cookies_file["path"])
        return ("none", "")

    # 6) Fields rows: Quality / Threads / Limit
    row1 = tk.Frame(card1, bg=PANEL)
    row1.pack(fill="x", pady=(0, 8))
    field_label(row1, "Quality:").pack(side="left")
    dark_option_menu(row1, quality_var, ("2160", "1440", "1080", "720")).pack(
        side="left", padx=(6, 4))
    hint_label(row1, "(2160 = 4K, 1440 = 2K)").pack(side="left", padx=(0, 14))
    field_label(row1, "Threads:").pack(side="left")
    dark_option_menu(row1, threads_var, THREADS_CHOICES, width=4).pack(
        side="left", padx=(6, 4))
    hint_label(row1, "aik sath kitni downloads").pack(
        side="left", padx=(0, 14))
    field_label(row1, "Limit (optional):").pack(side="left")
    dark_entry(row1, limit_var, 8).pack(side="left", padx=(6, 0))
    hint_label(row1, "sirf purani pipeline pe").pack(side="left", padx=(6, 0))
    # Cookies row — sirf queue + grab pe lagti hai (Proxy Advanced me hai)
    row1c = tk.Frame(card1, bg=PANEL)
    row1c.pack(fill="x", pady=(0, 8))
    field_label(row1c, "Cookies:").pack(side="left")
    cookies_menu = tk.OptionMenu(
        row1c, cookies_var, "None", "Chrome", "Edge", "Firefox",
        "cookies.txt file…", command=on_cookies_change)
    cookies_menu.config(bg=INPUT_BG, fg=TEXT,
                        activebackground=SLATE_ACTIVE,
                        activeforeground=TEXT, relief="flat", bd=0,
                        highlightthickness=1, highlightbackground=BORDER,
                        font=FONT_UI, cursor="hand2", width=16)
    try:
        cookies_menu["menu"].config(bg=INPUT_BG, fg=TEXT,
                                    activebackground=BLUE,
                                    activeforeground="#ffffff")
    except tk.TclError:
        pass
    cookies_menu.pack(side="left", padx=(6, 4))
    tk.Label(row1c, textvariable=cookies_file_var, font=FONT_SMALL,
             bg=PANEL, fg=MUTED).pack(side="left")
    # 7) Advanced — Proxy + purana pipeline flow (urls.txt wala
    # tareeqa). Default BAND (collapsed) rehta hai — roz ke kaam ke
    # liye zaroori nahi, is liye window saaf aur friendly rehti hai.
    adv_state = {"open": False}
    adv_frame = tk.Frame(card1, bg=PANEL)

    def toggle_advanced():
        if adv_state["open"]:
            adv_frame.pack_forget()
            adv_state["open"] = False
            adv_btn.config(text="▸ Advanced (Proxy, Pipeline, Update)")
        else:
            adv_frame.pack(fill="x")
            adv_state["open"] = True
            adv_btn.config(text="▾ Advanced (Proxy, Pipeline, Update)")

    adv_btn = small_btn(card1, "▸ Advanced (Proxy, Pipeline, Update)",
                        toggle_advanced)
    adv_btn.pack(anchor="w", pady=(2, 4))
    # Proxy row (Advanced ke andar) — sirf queue + grab pe lagta hai
    adv_proxy = tk.Frame(adv_frame, bg=PANEL)
    adv_proxy.pack(fill="x", pady=(2, 8))
    field_label(adv_proxy, "Proxy (optional):").pack(side="left")
    dark_entry(adv_proxy, proxy_var, 22).pack(
        side="left", fill="x", expand=True, padx=(6, 0))
    # Purana pipeline flow — chhoti row (urls.txt wala tareeqa)
    tk.Frame(adv_frame, bg=BORDER, height=1).pack(fill="x", pady=(4, 8))
    tk.Label(adv_frame,
             text="Pipeline (urls.txt → download + YouTube upload CSV):",
             font=FONT_SMALL, bg=PANEL, fg=MUTED).pack(
        anchor="w", pady=(0, 6))
    btns1 = tk.Frame(adv_frame, bg=PANEL)
    btns1.pack(fill="x")
    b_check = small_btn(btns1, "Sirf Check",
                        lambda: run_action("check"))
    b_check.pack(side="left", padx=(0, 6))
    b_download = small_btn(btns1, "Download Only (urls.txt wali list)",
                           lambda: run_action("download_only"))
    b_download.pack(side="left", padx=(0, 6))
    b_test1_small = small_btn(btns1, "Test 1 Video",
                              lambda: run_action("pipeline_test1"))
    b_test1_small.pack(side="left", padx=(0, 6))
    b_pipeline_small = small_btn(btns1, "Full Pipeline",
                                 lambda: run_action("pipeline"))
    b_pipeline_small.pack(side="left", padx=(0, 6))
    b_update = small_btn(btns1, "Update yt-dlp",
                         lambda: run_action("update_ytdlp"))
    b_update.pack(side="left")
    buttons += [b_paste, b_add_queue, b_grab_s, b_grab_v, b_grab_p,
                b_dl_all,
                b_retry, b_remove, b_clear_fin, b_clear_all,
                b_check, b_download, b_test1_small, b_pipeline_small,
                b_update]

    # ---------- card 2: UPLOAD — YOUTUBE ----------
    privacy_var = tk.StringVar(value="private")
    card2 = make_card("4. UPLOAD — YOUTUBE")
    row2 = tk.Frame(card2, bg=PANEL)
    row2.pack(fill="x", pady=(0, 8))
    field_label(row2, "Privacy:").pack(side="left")
    dark_option_menu(row2, privacy_var, PRIVACY_CHOICES, width=10).pack(
        side="left", padx=(6, 4))
    hint_label(row2, "Pipeline = pehle download, phir YouTube upload. "
                     "Quality / Limit upar wale Download card se lagte hain."
               ).pack(side="left", padx=(8, 0))
    btns2 = tk.Frame(card2, bg=PANEL)
    btns2.pack(fill="x")
    b_test1 = secondary_btn(btns2, "Pipeline Test — Pehli 1 Video",
                            lambda: run_action("pipeline_test1"))
    b_test1.pack(side="left", padx=(0, 6))
    b_pipeline = primary_btn(btns2, "Pipeline — Download + Upload",
                             BLUE, BLUE_ACTIVE,
                             lambda: run_action("pipeline"))
    b_pipeline.pack(side="left", fill="x", expand=True)
    buttons += [b_test1, b_pipeline]

    # ---------- card 3: MULTI UPLOAD — FACEBOOK + YOUTUBE ----------
    target_var = tk.StringVar()
    card3 = make_card("5. MULTI-PAGE (FACEBOOK + YOUTUBE)")
    row3 = tk.Frame(card3, bg=PANEL)
    row3.pack(fill="x", pady=(0, 8))
    field_label(row3, "Target:").pack(side="left")
    target_box = ttk.Combobox(row3, textvariable=target_var,
                              values=TARGET_PRESETS, style="Dark.TCombobox",
                              width=20, font=FONT_UI)
    target_box.pack(side="left", padx=(6, 4))
    hint_label(row3, "preset chuno ya khud likho — khaali = saare targets"
               ).pack(side="left", padx=(8, 0))
    btns3 = tk.Frame(card3, bg=PANEL)
    btns3.pack(fill="x")
    b_mcheck = secondary_btn(btns3, "Multi Check",
                             lambda: run_action("multi_check"))
    b_mcheck.pack(side="left", padx=(0, 6))
    b_multi = primary_btn(btns3, "Multi Upload", MULTI,
                          MULTI_ACTIVE,
                          lambda: run_action("multi_upload"))
    b_multi.pack(side="left", fill="x", expand=True)
    buttons += [b_mcheck, b_multi]

    # ---------- progress bar ----------
    prow = tk.Frame(content, bg=BG)
    prow.pack(fill="x", pady=(2, 8))
    progress = ttk.Progressbar(prow, style="Modern.Horizontal.TProgressbar",
                               mode="indeterminate")
    progress.pack(side="left", fill="x", expand=True)
    progress_text = tk.StringVar(value="")
    tk.Label(prow, textvariable=progress_text, font=FONT_SMALL,
             bg=BG, fg=MUTED, width=16, anchor="e").pack(
        side="right", padx=(8, 0))

    # ---------- live log ----------
    tk.Label(content, text="Live Log", font=FONT_SECTION,
             bg=BG, fg=BLUE_BRIGHT).pack(anchor="w")
    log = scrolledtext.ScrolledText(
        content, wrap="word", height=6, bg=LOG_BG, fg=LOG_FG,
        insertbackground=LOG_FG, font=FONT_LOG, relief="flat",
        highlightthickness=1, highlightbackground=BORDER)
    log.pack(fill="both", expand=True, pady=(4, 10))
    try:
        log.vbar.config(bg=SLATE, troughcolor=PANEL,
                        activebackground=SLATE_ACTIVE, relief="flat")
    except (tk.TclError, AttributeError):
        pass

    def write_log(text):
        log.insert("end", text)
        log.see("end")

    # ---------- bottom bar ----------
    bottom = tk.Frame(content, bg=BG)
    bottom.pack(fill="x")
    stop_btn = tk.Button(
        bottom, text="Stop", command=lambda: stop_proc(),
        bg=RED, fg="#ffffff", activebackground=RED_ACTIVE,
        activeforeground="#ffffff", relief="flat", bd=0, font=FONT_BTN,
        padx=16, pady=8, cursor="hand2", state="disabled",
        disabledforeground="#e8b4b1")
    stop_btn.pack(side="left")
    folder_btn = tk.Button(
        bottom, text="Project Folder Kholo",
        command=lambda: open_folder(BASE_DIR),
        bg=SLATE, fg=TEXT, activebackground=SLATE_ACTIVE,
        activeforeground=TEXT, relief="flat", bd=0, font=FONT_BTN,
        padx=14, pady=8, cursor="hand2",
        highlightthickness=1, highlightbackground=SLATE_BORDER,
        highlightcolor=SLATE_BORDER)
    folder_btn.pack(side="left", padx=(8, 0))
    tk.Label(bottom,
             text="Tip: pehle Check, phir Test (1 video), phir Full.",
             font=FONT_SMALL, bg=BG, fg=MUTED).pack(side="right")

    # ---------- run / stop logic ----------
    def set_buttons(enabled):
        st = "normal" if enabled else "disabled"
        for b in buttons:
            b.config(state=st)

    def reader(proc):
        try:
            for line in proc.stdout:
                out_queue.put(line)
        except Exception:  # noqa: BLE001 — reader thread chup chaap band ho
            pass
        out_queue.put(("__EXIT__", proc.wait()))

    def handle_output_line(line):
        """Aik output line ka faisla: queuedl protocol lines (QITEM /
        GRAB / GRABDONE / QDONE / QLOG) queue ko update karti hain —
        un ki raw shakal log mein NAHI ati. Baaki sab pehle ki tarah
        log + progress bar."""
        s = line.rstrip("\r\n")
        if s.startswith("QITEM "):
            parsed = parse_qitem(s)
            if parsed is not None:
                update_run_row(*parsed)
            return
        if s.startswith("GRABDONE "):
            n = s[len("GRABDONE "):].strip()
            write_log(f"Channel se {n} link(s) queue me aa gaye\n")
            return
        meta = parse_grab_meta(s)
        if meta is not None:
            pending_meta[meta["url"]] = meta
            return
        grabbed = parse_grab_line(s)
        if grabbed is not None:
            m = pending_meta.pop(grabbed, None)
            add_links_to_queue([grabbed], announce=False,
                               meta_map={grabbed: m} if m else None)
            return
        qd = parse_qdone(s)
        if qd is not None:
            write_log(f"Queue khatam: Done {qd['done']}, "
                      f"Failed {qd['failed']}, Skipped {qd['skipped']}\n")
            write_log("Videos is folder me hain: "
                      f"{download_dir_var.get()}\n")
            return
        if s.startswith("QLOG "):
            write_log(s[len("QLOG "):] + "\n")
            return
        write_log(line)
        pct = parse_progress(line)
        if pct is not None and state["running"]:
            progress.stop()
            progress.config(mode="determinate", value=pct)
            progress_text.set(f"{pct:g}%")

    def poll_queue():
        try:
            while True:
                item = out_queue.get_nowait()
                if isinstance(item, tuple) and item and item[0] == "__EXIT__":
                    code = item[1]
                    was_stopped = state["stopped"]
                    state["running"] = False
                    state["proc"] = None
                    # Queue run adhoori ruk jaye (Stop/error) to jo rows
                    # "Downloading" reh gayi hain wo Pending wapas —
                    # warna stats hamesha ke liye atak jayenge.
                    if state.get("run_kind") == "queue":
                        stuck = False
                        for r in queue_rows:
                            if r["status"] == Q_DOWNLOADING:
                                r["status"] = Q_PENDING
                                r["pct"] = 0
                                stuck = True
                        if stuck:
                            refresh_queue_view()
                    state["run_kind"] = None
                    state["run_row_ids"] = []
                    set_buttons(True)
                    stop_btn.config(state="disabled")
                    progress.stop()
                    if was_stopped:
                        progress.config(mode="determinate", value=0)
                        progress_text.set("Ruk gaya")
                        set_status("● Ruk gaya", RED)
                    elif code == 0:
                        progress.config(mode="determinate", value=100)
                        progress_text.set("100%")
                        set_status("● Ho gaya ✓", GREEN)
                    else:
                        progress.config(mode="determinate", value=0)
                        progress_text.set("Error")
                        set_status("● Error", RED)
                    write_log(f"\nKHATAM — exit code {code}\n")
                else:
                    handle_output_line(item)
        except queue.Empty:
            pass
        root.after(100, poll_queue)

    def run_action(action, urls_file="", use_limit=True, grab_url=""):
        if state["running"]:
            return
        try:
            cmd = build_command(
                action,
                limit=limit_var.get() if use_limit else "",
                target=target_var.get(),
                privacy=privacy_var.get(),
                quality=quality_var.get(),
                download_dir=download_dir_var.get(),
                urls_file=urls_file,
                threads=threads_var.get(),
                cookies=current_cookies(),
                proxy=proxy_var.get(),
                grab_url=grab_url,
                grab_count=grab_count_var.get(),
            )
        except ValueError as e:
            write_log(f"\nERROR: {e}\n")
            state["run_kind"] = None
            state["run_row_ids"] = []
            return
        write_log(f"\n>>> {' '.join(cmd)}\n")
        popen_kwargs = dict(
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
        )
        # Windows pe alag console window na khule (doosre OS pe ye flag
        # hota hi nahi, is liye getattr se guard).
        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if no_window:
            popen_kwargs["creationflags"] = no_window
        try:
            proc = subprocess.Popen(cmd, **popen_kwargs)
        except Exception as e:  # noqa: BLE001 — GUI ko crash nahi karna
            write_log(f"ERROR: command chal nahi saka — {e}\n")
            set_status("● Error", RED)
            state["run_kind"] = None
            state["run_row_ids"] = []
            return
        state["proc"] = proc
        state["running"] = True
        state["stopped"] = False
        set_buttons(False)
        stop_btn.config(state="normal")
        set_status("● Chal raha hai…", BLUE)
        progress.config(mode="indeterminate")
        progress.start(12)
        progress_text.set("Chal raha hai…")
        threading.Thread(target=reader, args=(proc,), daemon=True).start()

    def stop_proc():
        proc = state.get("proc")
        if proc is not None and state["running"]:
            state["stopped"] = True
            write_log("\n--- Stop dabya — process band kar raha hoon... ---\n")
            try:
                proc.terminate()
            except Exception:  # noqa: BLE001
                pass

    def open_folder(path):
        try:
            startfile = getattr(os, "startfile", None)
            if startfile is not None:
                startfile(path)  # Windows
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:  # noqa: BLE001 — GUI ko crash nahi karna
            write_log(f"\nFolder khul nahi saka — {e}\nPath: {path}\n")

    write_log("Bulk Tool ready hai. Pehle kisi bhi card se 'Check' dabao.\n")
    write_log(f"Folder: {BASE_DIR}\n")
    root.after(100, poll_queue)
    root.mainloop()


def main():
    try:
        import tkinter as tk
        from tkinter import scrolledtext
    except ImportError:
        print(TKINTER_MISSING_MSG)
        return 1
    try:
        _build_gui(tk, scrolledtext)
    except tk.TclError:
        print(DISPLAY_MISSING_MSG)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
