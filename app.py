#!/usr/bin/env python3
"""Nexus Bulk GUI (tkinter) — wraps pipeline.py, multi_upload.py, and queuedl.py."""
import json
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
DEFAULT_DOWNLOADS = os.path.join(BASE_DIR, "downloads")
PRIVACY_CHOICES = ("private", "unlisted", "public")
QUALITY_CHOICES = ("720", "1080", "1440", "2160")
TARGET_PRESETS = ("mind-maze-yt", "mind-maze-fb", "horror-fb")
THREADS_CHOICES = ("1", "2", "3", "4", "6", "8", "12", "16")
GRAB_COUNT_CHOICES = ("10", "20", "30", "50")
COOKIE_MODES = ("none", "chrome", "edge", "firefox", "file")
Q_PENDING = "Pending"
Q_DOWNLOADING = "Downloading"
Q_DONE = "Done"
Q_FAILED = "Failed"
Q_SKIPPED = "Skipped"

BG = "#0B1020"
PANEL = "#121A33"
PANEL_ALT = "#16203D"
BORDER = "#243158"
TEXT = "#F1F5F9"
LABEL = "#CBD5E1"
MUTED = "#7C8DB5"
BLUE = "#3B82F6"
BLUE_ACTIVE = "#2563EB"
BLUE_BRIGHT = "#60A5FA"
ORANGE = "#F59E0B"
GREEN = "#10B981"
GREEN_ACTIVE = "#059669"
MULTI = "#6366F1"
MULTI_ACTIVE = "#4F46E5"
RED = "#EF4444"
RED_ACTIVE = "#DC2626"
SLATE = "#1E294B"
SLATE_ACTIVE = "#2A3966"
SLATE_BORDER = "#334477"
INPUT_BG = "#0A0F24"
TREE_HEAD_BG = "#182347"
TREE_ROW_ALT = "#0F162C"
LOG_BG = "#070B19"
LOG_FG = "#CBD5E1"

FONT_UI = ("Segoe UI", 10)
FONT_TITLE = ("Segoe UI", 16, "bold")
FONT_SUBTITLE = ("Segoe UI", 9)
FONT_SECTION = ("Segoe UI", 10, "bold")
FONT_BTN = ("Segoe UI", 9, "bold")
FONT_BTN_MAIN = ("Segoe UI", 10, "bold")
FONT_SMALL = ("Segoe UI", 9)
FONT_STATS = ("Segoe UI", 9, "bold")
FONT_TREE_HEAD = ("Segoe UI", 9, "bold")
FONT_STATUS = ("Segoe UI", 9, "bold")
FONT_LOG = ("Consolas", 9)

# tkinter is imported lazily inside main() so `import app` works headless in tests.


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

    Blank lines aur '#' se shuru hone wali lines skip; har line mein
    http:// ya https:// se shuru hone wale URLs (chahe space se ya
    concatenated hon) nikaal ke duplicates hata ke order waisa hi rakho.
    """
    links, seen = [], set()
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not (line.startswith("http://") or line.startswith("https://")):
            continue
        # Split multiple URLs on the same line (space-separated or concatenated).
        for token in line.split():
            for part in re.split(r"(?=https?://)", token):
                url = part.strip()
                if not (url.startswith("http://") or url.startswith("https://")):
                    continue
                if url in seen:
                    continue
                seen.add(url)
                links.append(url)
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
        # multi_upload.py has no --privacy flag; privacy comes from each queue row.
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


def load_settings(settings_path=SETTINGS_FILE):
    if not settings_path or not os.path.exists(settings_path):
        return {}
    try:
        with open(settings_path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data, settings_path=SETTINGS_FILE):
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def resolve_download_dir(settings_path=SETTINGS_FILE,
                         default_dir=DEFAULT_DOWNLOADS):
    """Return (download_dir, warning_or_none), falling back to default if missing."""
    data = load_settings(settings_path)
    saved = str(data.get("download_dir") or "").strip()
    if not saved:
        return default_dir, None
    if os.path.isdir(saved):
        return saved, None
    return default_dir, (
        f"Saved download folder nahi mila ({saved}) — "
        f"default folder use ho raha hai: {default_dir}"
    )


def save_download_dir(path, settings_path=SETTINGS_FILE):
    data = load_settings(settings_path)
    data["download_dir"] = str(path or "").strip()
    save_settings(data, settings_path)


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
    "Nexus Bulk GUI: Python ka tkinter nahi mila, is liye window nahi khul sakti.\n"
    "Koi baat nahi — tool terminal se bilkul waisa hi chalta hai:\n"
    "  python pipeline.py --check\n"
    "  python pipeline.py --limit 1\n"
    "  python multi_upload.py --check\n"
    "tkinter python.org wale standard Python installer ke sath aata hai —\n"
    "agar custom/minimal Python hai to poora Python dobara install karne se aa jayega."
)

DISPLAY_MISSING_MSG = (
    "Nexus Bulk GUI: window nahi khul saki (display nahi mila).\n"
    "Ye aksar headless/remote session mein hota hai — terminal commands use karo:\n"
    "  python pipeline.py --check\n"
    "  python multi_upload.py --check"
)


def _build_gui(tk, scrolledtext):
    """Build and run the Nexus Bulk desktop UI. tkinter must already be imported."""
    import queue
    import subprocess
    import threading
    from tkinter import filedialog, ttk

    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    root = tk.Tk()
    root.title("Nexus Bulk")
    root.geometry("1080x790")
    root.minsize(940, 700)
    root.configure(bg=BG)

    # Use clam theme so custom ttk colors apply cleanly on Windows.
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(
        "Modern.Horizontal.TProgressbar",
        troughcolor=INPUT_BG, background=GREEN,
        bordercolor=BORDER, lightcolor=GREEN, darkcolor=GREEN,
        thickness=10,
    )
    style.configure(
        "Dark.TCombobox",
        fieldbackground=INPUT_BG, background=SLATE,
        foreground=TEXT, arrowcolor=TEXT,
        bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
        padding=(6, 4),
    )
    style.map(
        "Dark.TCombobox",
        fieldbackground=[("readonly", INPUT_BG), ("disabled", PANEL)],
        foreground=[("readonly", TEXT), ("disabled", MUTED)],
        selectbackground=[("readonly", INPUT_BG)],
        selectforeground=[("readonly", TEXT)],
    )
    root.option_add("*TCombobox*Listbox.background", INPUT_BG)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", BLUE)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    root.option_add("*TCombobox*Listbox.font", FONT_UI)

    style.configure(
        "Dark.TNotebook",
        background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0),
    )
    style.configure(
        "Dark.TNotebook.Tab",
        background=SLATE, foreground=MUTED,
        padding=(18, 8), font=FONT_BTN, borderwidth=0,
    )
    style.map(
        "Dark.TNotebook.Tab",
        background=[("selected", PANEL), ("active", SLATE_ACTIVE)],
        foreground=[("selected", "#ffffff"), ("active", TEXT)],
        expand=[("selected", [0, 0, 0, 0])],
    )

    style.configure(
        "Dark.Treeview",
        background=PANEL, fieldbackground=PANEL,
        foreground=TEXT, bordercolor=BORDER,
        lightcolor=BORDER, darkcolor=BORDER,
        rowheight=26, font=FONT_SMALL,
    )
    style.configure(
        "Dark.Treeview.Heading",
        background=TREE_HEAD_BG, foreground="#ffffff",
        bordercolor=BORDER, relief="flat",
        padding=(6, 5), font=FONT_TREE_HEAD,
    )
    style.map(
        "Dark.Treeview.Heading",
        background=[("active", SLATE_ACTIVE)],
    )
    style.map(
        "Dark.Treeview",
        background=[("selected", BLUE_ACTIVE)],
        foreground=[("selected", "#ffffff")],
    )
    style.configure(
        "Dark.Vertical.TScrollbar",
        background=SLATE, troughcolor=INPUT_BG, bordercolor=BORDER,
        arrowcolor=TEXT, lightcolor=SLATE, darkcolor=SLATE,
        gripcount=0,
    )
    style.map(
        "Dark.Vertical.TScrollbar",
        background=[("active", SLATE_ACTIVE)],
    )

    state = {"proc": None, "running": False, "stopped": False,
             "run_kind": None, "run_row_ids": []}
    out_queue = queue.Queue()
    buttons = []

    main = tk.Frame(root, bg=BG)
    main.pack(fill="both", expand=True, padx=14, pady=12)

    def bind_hover(btn, normal_bg, hover_bg):
        def on_enter(_):
            if str(btn["state"]) != "disabled":
                btn.config(bg=hover_bg)

        def on_leave(_):
            btn.config(bg=normal_bg)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)

    def field_label(parent, text):
        return tk.Label(parent, text=text, font=FONT_UI, bg=PANEL, fg=LABEL)

    def hint_label(parent, text):
        return tk.Label(parent, text=text, font=FONT_SMALL, bg=PANEL, fg=MUTED)

    def dark_entry(parent, var, width=20):
        return tk.Entry(
            parent, textvariable=var, width=width, bg=INPUT_BG,
            fg=TEXT, insertbackground=TEXT, relief="flat",
            font=FONT_UI, highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=BLUE,
        )

    def dark_combobox(parent, var, values, width=10, readonly=True):
        cb = ttk.Combobox(
            parent, textvariable=var, values=values,
            style="Dark.TCombobox", width=width, font=FONT_UI,
            state="readonly" if readonly else "normal",
        )
        return cb

    def primary_btn(parent, text, color, active, command, pad_x=16, pad_y=7):
        btn = tk.Button(
            parent, text=text, command=command, bg=color, fg="#ffffff",
            activebackground=active, activeforeground="#ffffff",
            relief="flat", bd=0, font=FONT_BTN_MAIN, padx=pad_x, pady=pad_y,
            cursor="hand2", disabledforeground="#94A3B8",
        )
        bind_hover(btn, color, active)
        return btn

    def secondary_btn(parent, text, command, pad_x=12, pad_y=6):
        btn = tk.Button(
            parent, text=text, command=command, bg=SLATE, fg=TEXT,
            activebackground=SLATE_ACTIVE, activeforeground="#ffffff",
            relief="flat", bd=0, font=FONT_BTN, padx=pad_x, pady=pad_y,
            cursor="hand2", disabledforeground=MUTED,
            highlightthickness=1, highlightbackground=SLATE_BORDER,
            highlightcolor=SLATE_BORDER,
        )
        bind_hover(btn, SLATE, SLATE_ACTIVE)
        return btn

    def small_btn(parent, text, command, pad_x=10, pad_y=4):
        btn = tk.Button(
            parent, text=text, command=command, bg=SLATE, fg=TEXT,
            activebackground=SLATE_ACTIVE, activeforeground="#ffffff",
            relief="flat", bd=0, font=FONT_SMALL, padx=pad_x, pady=pad_y,
            cursor="hand2", disabledforeground=MUTED,
            highlightthickness=1, highlightbackground=SLATE_BORDER,
            highlightcolor=SLATE_BORDER,
        )
        bind_hover(btn, SLATE, SLATE_ACTIVE)
        return btn

    def section_heading(parent, text, pad_top=0):
        tk.Label(
            parent, text=text, font=FONT_SECTION, bg=PANEL, fg=BLUE_BRIGHT,
        ).pack(anchor="w", pady=(pad_top, 0))
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", pady=(4, 8))

    def make_card(parent, heading=None, fill="x", expand=False, pady=(0, 10)):
        card = tk.Frame(
            parent, bg=PANEL, padx=14, pady=12,
            highlightthickness=1, highlightbackground=BORDER,
        )
        card.pack(fill=fill, expand=expand, pady=pady)
        if heading:
            section_heading(card, heading)
        return card

    # ── Header Bar ──────────────────────────────────────────────────────────
    header = tk.Frame(
        main, bg=PANEL, padx=16, pady=10,
        highlightthickness=1, highlightbackground=BORDER,
    )
    header.pack(fill="x", pady=(0, 10))
    header.columnconfigure(1, weight=1)

    head_left = tk.Frame(header, bg=PANEL)
    head_left.grid(row=0, column=0, sticky="w")
    title_row = tk.Frame(head_left, bg=PANEL)
    title_row.pack(anchor="w")
    tk.Label(
        title_row, text="Nexus Bulk", font=FONT_TITLE,
        bg=PANEL, fg="#ffffff",
    ).pack(side="left")
    tk.Label(
        title_row, text="  VIDEO DOWNLOADER & UPLOADER", font=("Segoe UI", 8, "bold"),
        bg=PANEL, fg=BLUE_BRIGHT,
    ).pack(side="left", pady=(4, 0))
    tk.Label(
        head_left, text="Powered by Soban Mustafa",
        font=FONT_SUBTITLE, bg=PANEL, fg=MUTED,
    ).pack(anchor="w", pady=(2, 0))

    head_mid = tk.Frame(header, bg=PANEL)
    head_mid.grid(row=0, column=1, padx=12)
    tk.Label(
        head_mid, text="For contact: ",
        font=FONT_SMALL, bg=PANEL, fg=LABEL,
    ).pack(side="left")

    def open_linkedin(_event=None):
        import webbrowser
        webbrowser.open_new_tab("https://www.linkedin.com/in/soban-mustafa")

    linkedin_lbl = tk.Label(
        head_mid, text="linkedin.com/in/soban-mustafa",
        font=("Segoe UI", 9, "underline"), bg=PANEL, fg=BLUE_BRIGHT,
        cursor="hand2",
    )
    linkedin_lbl.pack(side="left")
    linkedin_lbl.bind("<Button-1>", open_linkedin)
    linkedin_lbl.bind("<Enter>", lambda _: linkedin_lbl.config(fg="#93C5FD"))
    linkedin_lbl.bind("<Leave>", lambda _: linkedin_lbl.config(fg=BLUE_BRIGHT))

    head_right = tk.Frame(header, bg=PANEL)
    head_right.grid(row=0, column=2, sticky="e")
    status_pill = tk.Frame(
        head_right, bg=INPUT_BG, padx=12, pady=5,
        highlightthickness=1, highlightbackground=BORDER,
    )
    status_pill.pack(side="right")
    status_var = tk.StringVar(value="● Ready")
    status_lbl = tk.Label(
        status_pill, textvariable=status_var, font=FONT_STATUS,
        bg=INPUT_BG, fg=MUTED,
    )
    status_lbl.pack()

    proj_folder_btn = small_btn(
        head_right, "Project Folder", lambda: open_folder(BASE_DIR),
    )
    proj_folder_btn.pack(side="right", padx=(0, 10))

    def set_status(text, color):
        status_var.set(text)
        status_lbl.config(fg=color)

    # ── Shared State Variables ──────────────────────────────────────────────
    quality_var = tk.StringVar(value="2160")
    limit_var = tk.StringVar()
    threads_var = tk.StringVar(value="4")
    channel_var = tk.StringVar()
    grab_count_var = tk.StringVar(value="10")
    cookies_var = tk.StringVar(value="None")
    cookies_file = {"path": ""}
    cookies_file_var = tk.StringVar(value="")
    proxy_var = tk.StringVar()
    privacy_var = tk.StringVar(value="private")
    target_var = tk.StringVar()
    default_downloads = DEFAULT_DOWNLOADS
    initial_downloads, dl_warn = resolve_download_dir()
    download_dir_var = tk.StringVar(value=initial_downloads)

    def browse_folder():
        chosen = filedialog.askdirectory(
            initialdir=download_dir_var.get() or BASE_DIR,
            title="Select Download Folder",
        )
        if chosen:
            download_dir_var.set(chosen)
            save_download_dir(chosen)
            write_log(f"Download folder saved: {chosen}\n")

    def reset_folder():
        download_dir_var.set(default_downloads)
        save_download_dir(default_downloads)
        write_log(f"Download folder reset to default: {default_downloads}\n")

    def open_download_folder():
        path = download_dir_var.get().strip() or default_downloads
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            write_log(f"\nCould not create folder — {e}\nPath: {path}\n")
            return
        open_folder(path)

    # ── Tabbed Workspace ────────────────────────────────────────────────────
    notebook = ttk.Notebook(main, style="Dark.TNotebook")
    notebook.pack(fill="both", expand=True, pady=(0, 10))

    tab_dl = tk.Frame(notebook, bg=BG)
    tab_up = tk.Frame(notebook, bg=BG)
    notebook.add(tab_dl, text="  Download & Queue  ")
    notebook.add(tab_up, text="  YouTube & Multi-Upload  ")

    # ════════════════════════════════════════════════════════════════════════
    # TAB 1: DOWNLOAD & QUEUE
    # ════════════════════════════════════════════════════════════════════════
    dl_inner = tk.Frame(tab_dl, bg=BG)
    dl_inner.pack(fill="both", expand=True, pady=(8, 0))

    # ── Card 1: Sources (Save Folder + Paste Links + Channel Grab) ──────────
    src_card = make_card(dl_inner, pady=(0, 10))

    # Row 0: Save Location (aligned grid)
    loc_grid = tk.Frame(src_card, bg=PANEL)
    loc_grid.pack(fill="x", pady=(0, 10))
    loc_grid.columnconfigure(1, weight=1)

    tk.Label(
        loc_grid, text="Save Folder:", font=FONT_BTN, bg=PANEL, fg=LABEL,
        width=13, anchor="w",
    ).grid(row=0, column=0, sticky="w", padx=(0, 8))
    dark_entry(loc_grid, download_dir_var, 40).grid(
        row=0, column=1, sticky="ew", ipady=4, padx=(0, 8),
    )
    loc_btns = tk.Frame(loc_grid, bg=PANEL)
    loc_btns.grid(row=0, column=2, sticky="e")
    small_btn(loc_btns, "Browse…", browse_folder).pack(side="left", padx=(0, 5))
    small_btn(loc_btns, "Open Folder", open_download_folder).pack(
        side="left", padx=(0, 5),
    )
    small_btn(loc_btns, "Default", reset_folder).pack(side="left")

    tk.Frame(src_card, bg=BORDER, height=1).pack(fill="x", pady=(0, 10))

    # Paste Links Section
    paste_hdr = tk.Frame(src_card, bg=PANEL)
    paste_hdr.pack(fill="x", pady=(0, 4))
    tk.Label(
        paste_hdr, text="Paste Video Links", font=FONT_SECTION,
        bg=PANEL, fg=BLUE_BRIGHT,
    ).pack(side="left")
    hint_label(
        paste_hdr, "  (one URL per line: YouTube, TikTok, Facebook…)",
    ).pack(side="left")

    link_count_var = tk.StringVar(value="0 links")
    tk.Label(
        paste_hdr, textvariable=link_count_var, font=FONT_SMALL,
        bg=PANEL, fg=MUTED,
    ).pack(side="right", padx=(8, 0))

    def update_link_count(*_):
        n = len(extract_links(links_text.get("1.0", "end")))
        link_count_var.set(f"{n} link" if n == 1 else f"{n} links")

    def paste_from_clipboard():
        try:
            clip = root.clipboard_get()
        except tk.TclError:
            return
        if clip:
            cur = links_text.get("1.0", "end-1c")
            if cur and not cur.endswith("\n"):
                links_text.insert("end", "\n")
            links_text.insert("end", clip.strip() + "\n")
            update_link_count()

    def clear_links_box():
        links_text.delete("1.0", "end")
        update_link_count()

    small_btn(paste_hdr, "Clear", clear_links_box, pad_x=8, pad_y=2).pack(
        side="right", padx=(4, 0),
    )
    small_btn(paste_hdr, "Paste", paste_from_clipboard, pad_x=8, pad_y=2).pack(
        side="right",
    )

    links_frame = tk.Frame(src_card, bg=PANEL)
    links_frame.pack(fill="x", pady=(0, 8))
    links_text = tk.Text(
        links_frame, height=3, bg=INPUT_BG, fg=TEXT,
        insertbackground=TEXT, relief="flat", font=FONT_UI,
        highlightthickness=1, highlightbackground=BORDER,
        highlightcolor=BLUE, wrap="word", padx=6, pady=4,
    )
    links_scroll = ttk.Scrollbar(
        links_frame, orient="vertical", command=links_text.yview,
        style="Dark.Vertical.TScrollbar",
    )
    links_text.config(yscrollcommand=links_scroll.set)
    links_scroll.pack(side="right", fill="y")
    links_text.pack(side="left", fill="x", expand=True)
    links_text.bind("<KeyRelease>", update_link_count)

    paste_actions = tk.Frame(src_card, bg=PANEL)
    paste_actions.pack(fill="x", pady=(0, 10))
    b_paste = primary_btn(
        paste_actions, "Download Pasted Links", GREEN, GREEN_ACTIVE,
        lambda: on_paste_download(),
    )
    b_paste.pack(side="left", fill="x", expand=True, padx=(0, 8))
    b_add_queue = primary_btn(
        paste_actions, "+ Add to Queue", BLUE, BLUE_ACTIVE,
        lambda: on_add_to_queue(), pad_x=20, pad_y=7,
    )
    b_add_queue.pack(side="left")

    tk.Frame(src_card, bg=BORDER, height=1).pack(fill="x", pady=(0, 10))

    # Channel / Profile Grab (aligned grid)
    grab_grid = tk.Frame(src_card, bg=PANEL)
    grab_grid.pack(fill="x")
    grab_grid.columnconfigure(1, weight=1)

    tk.Label(
        grab_grid, text="Channel / Profile:", font=FONT_BTN, bg=PANEL, fg=LABEL,
        width=13, anchor="w",
    ).grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 6))
    dark_entry(grab_grid, channel_var, 40).grid(
        row=0, column=1, sticky="ew", ipady=4, padx=(0, 10), pady=(0, 6),
    )
    cnt_frame = tk.Frame(
        grab_grid, bg=PANEL_ALT, padx=10, pady=4,
        highlightthickness=1, highlightbackground=BLUE_BRIGHT,
    )
    cnt_frame.grid(row=0, column=2, sticky="e", pady=(0, 6))
    tk.Label(
        cnt_frame, text="Count:", font=FONT_BTN, bg=PANEL_ALT, fg=BLUE_BRIGHT,
    ).pack(side="left", padx=(0, 6))
    dark_combobox(cnt_frame, grab_count_var, GRAB_COUNT_CHOICES, width=6).pack(
        side="left",
    )

    grab_btns = tk.Frame(grab_grid, bg=PANEL)
    grab_btns.grid(row=1, column=1, columnspan=2, sticky="ew")
    b_grab_p = primary_btn(
        grab_btns, "Grab Top Videos", BLUE, BLUE_ACTIVE,
        lambda: on_grab("popular"), pad_x=14, pad_y=5,
    )
    b_grab_p.pack(side="left", padx=(0, 8))
    b_grab_v = secondary_btn(
        grab_btns, "Latest Videos", lambda: on_grab("videos"), pad_x=12, pad_y=5,
    )
    b_grab_v.pack(side="left", padx=(0, 6))
    b_grab_s = secondary_btn(
        grab_btns, "Shorts", lambda: on_grab("shorts"), pad_x=12, pad_y=5,
    )
    b_grab_s.pack(side="left", padx=(0, 10))
    hint_label(grab_btns, "Top = highest views first").pack(side="left")

    # ── Card 2: Download Queue & Settings ───────────────────────────────────
    q_card = make_card(dl_inner, fill="both", expand=True, pady=(0, 0))

    # Queue Header + Download Settings Bar (aligned)
    q_top = tk.Frame(q_card, bg=PANEL)
    q_top.pack(fill="x", pady=(0, 8))
    tk.Label(
        q_top, text="DOWNLOAD QUEUE", font=FONT_SECTION,
        bg=PANEL, fg=BLUE_BRIGHT,
    ).pack(side="left")

    stats_var = tk.StringVar(
        value="Total: 0  •  Done: 0  •  Pending: 0  •  Active: 0  •  Failed: 0",
    )
    tk.Label(
        q_top, textvariable=stats_var, font=FONT_STATS,
        bg=PANEL, fg=BLUE_BRIGHT,
    ).pack(side="right")

    def on_cookies_change(_event=None):
        choice = cookies_var.get()
        if choice.startswith("cookies.txt"):
            path = filedialog.askopenfilename(
                title="Select cookies.txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            )
            if path:
                cookies_file["path"] = path
                cookies_file_var.set(os.path.basename(path))
            else:
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

    settings_bar = tk.Frame(
        q_card, bg=PANEL_ALT, padx=10, pady=7,
        highlightthickness=1, highlightbackground=BORDER,
    )
    settings_bar.pack(fill="x", pady=(0, 8))

    tk.Label(
        settings_bar, text="Quality:", font=FONT_SMALL, bg=PANEL_ALT, fg=LABEL,
    ).pack(side="left", padx=(0, 5))
    dark_combobox(
        settings_bar, quality_var, ("2160", "1440", "1080", "720"), width=6,
    ).pack(side="left", padx=(0, 14))

    tk.Label(
        settings_bar, text="Threads:", font=FONT_SMALL, bg=PANEL_ALT, fg=LABEL,
    ).pack(side="left", padx=(0, 5))
    dark_combobox(
        settings_bar, threads_var, THREADS_CHOICES, width=4,
    ).pack(side="left", padx=(0, 14))

    tk.Label(
        settings_bar, text="Cookies:", font=FONT_SMALL, bg=PANEL_ALT, fg=LABEL,
    ).pack(side="left", padx=(0, 5))
    cookies_cb = dark_combobox(
        settings_bar, cookies_var,
        ("None", "Chrome", "Edge", "Firefox", "cookies.txt file…"),
        width=15,
    )
    cookies_cb.pack(side="left", padx=(0, 6))
    cookies_cb.bind("<<ComboboxSelected>>", on_cookies_change)
    tk.Label(
        settings_bar, textvariable=cookies_file_var, font=FONT_SMALL,
        bg=PANEL_ALT, fg=BLUE_BRIGHT,
    ).pack(side="left", padx=(0, 10))

    tk.Label(
        settings_bar, text="Proxy:", font=FONT_SMALL, bg=PANEL_ALT, fg=LABEL,
    ).pack(side="left", padx=(0, 5))
    dark_entry(settings_bar, proxy_var, 18).pack(
        side="left", fill="x", expand=True, ipady=2,
    )

    # Queue Treeview
    tree_frame = tk.Frame(q_card, bg=PANEL)
    tree_frame.pack(fill="both", expand=True, pady=(0, 8))
    tree = ttk.Treeview(
        tree_frame, columns=("num", "video", "views", "status"),
        show="headings", height=5, style="Dark.Treeview",
        selectmode="extended",
    )
    tree.heading("num", text="#")
    tree.heading("video", text="Video / Link")
    tree.heading("views", text="Views")
    tree.heading("status", text="Status")
    tree.column("num", width=42, minwidth=36, stretch=False, anchor="center")
    tree.column("video", width=520, minwidth=200, stretch=True)
    tree.column("views", width=90, minwidth=70, stretch=False, anchor="e")
    tree.column("status", width=165, minwidth=130, stretch=False, anchor="w")

    tree.tag_configure("odd", background=PANEL)
    tree.tag_configure("even", background=TREE_ROW_ALT)
    tree.tag_configure("done", foreground=GREEN)
    tree.tag_configure("failed", foreground=RED)
    tree.tag_configure("downloading", foreground=BLUE_BRIGHT)
    tree.tag_configure("skipped", foreground=ORANGE)

    tree_scroll = ttk.Scrollbar(
        tree_frame, orient="vertical", command=tree.yview,
        style="Dark.Vertical.TScrollbar",
    )
    tree.config(yscrollcommand=tree_scroll.set)
    tree_scroll.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)

    # Queue Action Bar
    qbtns = tk.Frame(q_card, bg=PANEL)
    qbtns.pack(fill="x")
    b_dl_all = primary_btn(
        qbtns, "Download All", GREEN, GREEN_ACTIVE,
        lambda: start_download_all(), pad_x=20, pad_y=6,
    )
    b_dl_all.pack(side="left", padx=(0, 8))

    b_retry = secondary_btn(
        qbtns, "Retry Failed", lambda: start_download_all(only_failed=True),
        pad_x=10, pad_y=5,
    )
    b_retry.pack(side="left", padx=(0, 5))
    b_remove = secondary_btn(
        qbtns, "Remove Selected", lambda: on_remove_selected(),
        pad_x=10, pad_y=5,
    )
    b_remove.pack(side="left", padx=(0, 5))
    b_clear_fin = secondary_btn(
        qbtns, "Clear Finished", lambda: on_clear_finished(),
        pad_x=10, pad_y=5,
    )
    b_clear_fin.pack(side="left", padx=(0, 5))
    b_clear_all = secondary_btn(
        qbtns, "Clear All", lambda: on_clear_all(),
        pad_x=10, pad_y=5,
    )
    b_clear_all.pack(side="left")

    # ════════════════════════════════════════════════════════════════════════
    # TAB 2: YOUTUBE & MULTI-UPLOAD
    # ════════════════════════════════════════════════════════════════════════
    up_inner = tk.Frame(tab_up, bg=BG)
    up_inner.pack(fill="both", expand=True, pady=(8, 0))

    # Card A: YouTube Pipeline
    yt_card = make_card(up_inner, "YOUTUBE PIPELINE  (urls.txt → Download + Upload CSV)")
    yt_grid = tk.Frame(yt_card, bg=PANEL)
    yt_grid.pack(fill="x", pady=(0, 10))
    yt_grid.columnconfigure(2, weight=1)

    field_label(yt_grid, "Privacy:").grid(
        row=0, column=0, sticky="w", padx=(0, 10), pady=(0, 8),
    )
    dark_combobox(yt_grid, privacy_var, PRIVACY_CHOICES, width=14).grid(
        row=0, column=1, sticky="w", pady=(0, 8),
    )
    hint_label(
        yt_grid, "Applied to YouTube uploads in Pipeline & Test 1 Video",
    ).grid(row=0, column=2, sticky="w", padx=(12, 0), pady=(0, 8))

    field_label(yt_grid, "Limit:").grid(
        row=1, column=0, sticky="w", padx=(0, 10),
    )
    dark_entry(yt_grid, limit_var, 16).grid(
        row=1, column=1, sticky="w", ipady=3,
    )
    hint_label(
        yt_grid, "Optional max videos (leave blank for all). Quality uses Download tab setting.",
    ).grid(row=1, column=2, sticky="w", padx=(12, 0))

    yt_btns = tk.Frame(yt_card, bg=PANEL)
    yt_btns.pack(fill="x")
    b_check = secondary_btn(
        yt_btns, "Check Readiness", lambda: run_action("check"),
    )
    b_check.pack(side="left", padx=(0, 6))
    b_download = secondary_btn(
        yt_btns, "Download Only (urls.txt)", lambda: run_action("download_only"),
    )
    b_download.pack(side="left", padx=(0, 6))
    b_test1 = secondary_btn(
        yt_btns, "Test 1 Video", lambda: run_action("pipeline_test1"),
    )
    b_test1.pack(side="left", padx=(0, 8))
    b_pipeline = primary_btn(
        yt_btns, "Run Full Pipeline (Download + Upload)", BLUE, BLUE_ACTIVE,
        lambda: run_action("pipeline"),
    )
    b_pipeline.pack(side="left", fill="x", expand=True)

    # Card B: Multi-Page Upload
    multi_card = make_card(up_inner, "MULTI-PAGE UPLOAD  (Facebook + YouTube)")
    multi_grid = tk.Frame(multi_card, bg=PANEL)
    multi_grid.pack(fill="x", pady=(0, 10))
    multi_grid.columnconfigure(2, weight=1)

    field_label(multi_grid, "Target:").grid(
        row=0, column=0, sticky="w", padx=(0, 10),
    )
    target_box = dark_combobox(
        multi_grid, target_var, TARGET_PRESETS, width=22, readonly=False,
    )
    target_box.grid(row=0, column=1, sticky="w")
    hint_label(
        multi_grid, "Select a preset or type custom target — leave blank for all targets",
    ).grid(row=0, column=2, sticky="w", padx=(12, 0))

    multi_btns = tk.Frame(multi_card, bg=PANEL)
    multi_btns.pack(fill="x")
    b_mcheck = secondary_btn(
        multi_btns, "Check Targets", lambda: run_action("multi_check"),
    )
    b_mcheck.pack(side="left", padx=(0, 8))
    b_multi = primary_btn(
        multi_btns, "Run Multi-Upload", MULTI, MULTI_ACTIVE,
        lambda: run_action("multi_upload"),
    )
    b_multi.pack(side="left", fill="x", expand=True)

    # Card C: Maintenance & Tools
    tools_card = make_card(up_inner, "MAINTENANCE", pady=(0, 0))
    tools_row = tk.Frame(tools_card, bg=PANEL)
    tools_row.pack(fill="x")
    b_update = secondary_btn(
        tools_row, "Update yt-dlp", lambda: run_action("update_ytdlp"),
    )
    b_update.pack(side="left", padx=(0, 12))
    hint_label(
        tools_row,
        "Updates yt-dlp via pip to keep YouTube, TikTok, and Facebook extraction working.",
    ).pack(side="left")

    buttons += [
        b_paste, b_add_queue, b_grab_s, b_grab_v, b_grab_p,
        b_dl_all, b_retry, b_remove, b_clear_fin, b_clear_all,
        b_check, b_download, b_test1, b_pipeline,
        b_mcheck, b_multi, b_update,
    ]

    # ════════════════════════════════════════════════════════════════════════
    # BOTTOM ACTIVITY PANEL (Always Visible: Progress + Stop + Live Log)
    # ════════════════════════════════════════════════════════════════════════
    prow = tk.Frame(main, bg=BG)
    prow.pack(fill="x", pady=(0, 8))

    progress = ttk.Progressbar(
        prow, style="Modern.Horizontal.TProgressbar", mode="determinate",
        value=0,
    )
    progress.pack(side="left", fill="x", expand=True)

    progress_text = tk.StringVar(value="Idle")
    tk.Label(
        prow, textvariable=progress_text, font=FONT_SMALL,
        bg=BG, fg=MUTED, width=14, anchor="e",
    ).pack(side="left", padx=(10, 10))

    stop_btn = tk.Button(
        prow, text="Stop", command=lambda: stop_proc(),
        bg=RED, fg="#ffffff", activebackground=RED_ACTIVE,
        activeforeground="#ffffff", relief="flat", bd=0, font=FONT_BTN,
        padx=14, pady=4, cursor="hand2", state="disabled",
        disabledforeground="#FCA5A5",
    )
    bind_hover(stop_btn, RED, RED_ACTIVE)
    stop_btn.pack(side="right")

    log_card = tk.Frame(
        main, bg=PANEL, padx=12, pady=8,
        highlightthickness=1, highlightbackground=BORDER,
    )
    log_card.pack(fill="x")

    log_hdr = tk.Frame(log_card, bg=PANEL)
    log_hdr.pack(fill="x", pady=(0, 6))
    tk.Label(
        log_hdr, text="LIVE LOG", font=FONT_SECTION,
        bg=PANEL, fg=BLUE_BRIGHT,
    ).pack(side="left")

    def copy_log():
        text = log.get("1.0", "end-1c")
        if text:
            root.clipboard_clear()
            root.clipboard_append(text)
            write_log("Log copied to clipboard.\n")

    def clear_log():
        log.delete("1.0", "end")

    small_btn(log_hdr, "Clear", clear_log, pad_x=8, pad_y=2).pack(side="right")
    small_btn(log_hdr, "Copy", copy_log, pad_x=8, pad_y=2).pack(
        side="right", padx=(0, 5),
    )

    log = scrolledtext.ScrolledText(
        log_card, wrap="word", height=7, bg=LOG_BG, fg=LOG_FG,
        insertbackground=LOG_FG, font=FONT_LOG, relief="flat",
        highlightthickness=1, highlightbackground=BORDER,
        padx=8, pady=6,
    )
    log.pack(fill="both", expand=True)
    try:
        log.vbar.config(
            bg=SLATE, troughcolor=PANEL,
            activebackground=SLATE_ACTIVE, relief="flat",
        )
    except (tk.TclError, AttributeError):
        pass

    def write_log(text):
        log.insert("end", text)
        log.see("end")

    # ── Queue & Runner Logic ────────────────────────────────────────────────
    queue_rows = []          # [{"url", "title", "views", "status", "pct", "iid"}]
    queue_ids = {"next": 0}
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
            return "Skipped (exists)"
        return "Pending"

    def row_tags(num, row):
        stripe = "even" if num % 2 == 0 else "odd"
        st = row["status"]
        if st == Q_DONE:
            return (stripe, "done")
        if st == Q_FAILED:
            return (stripe, "failed")
        if st == Q_DOWNLOADING:
            return (stripe, "downloading")
        if st == Q_SKIPPED:
            return (stripe, "skipped")
        return (stripe,)

    def update_stats():
        s = queue_stats(queue_rows)
        stats_var.set(
            f"Total: {s['total']}  •  Done: {s['downloaded']}  •  "
            f"Pending: {s['remaining']}  •  Active: {s['downloading']}  •  "
            f"Failed: {s['failed']}"
        )

    def row_display_values(num, row):
        label = row.get("title") or row["url"]
        return (num, label, format_views(row.get("views")),
                row_status_text(row))

    def refresh_queue_view():
        for iid in tree.get_children():
            tree.delete(iid)
        for n, row in enumerate(queue_rows, 1):
            tree.insert(
                "", "end", iid=row["iid"],
                values=row_display_values(n, row),
                tags=row_tags(n, row),
            )
        update_stats()

    def add_links_to_queue(links, announce=True, meta_map=None):
        """Add links to queue (deduplicated). Returns count of newly added links."""
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
            num = len(queue_rows)
            tree.insert(
                "", "end", iid=iid,
                values=row_display_values(num, row),
                tags=row_tags(num, row),
            )
        if new:
            update_stats()
        if announce:
            write_log(
                f"Added {len(new)} new link(s) to queue (total {len(queue_rows)})\n",
            )
        return len(new)

    def update_run_row(index, status, pct):
        """Update queue row status and overall progress from QITEM line."""
        ids = state.get("run_row_ids") or []
        if index < 0 or index >= len(ids):
            return
        iid = ids[index]
        row_idx = next(
            (i for i, r in enumerate(queue_rows) if r["iid"] == iid), None,
        )
        if row_idx is None:
            return
        row = queue_rows[row_idx]
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
            tree.item(iid, tags=row_tags(row_idx + 1, row))
        except tk.TclError:
            pass
        update_stats()
        run_rows = [r for r in queue_rows if r["iid"] in ids]
        if run_rows:
            avg = sum(r["pct"] for r in run_rows) / len(run_rows)
            progress.stop()
            progress.config(mode="determinate", value=avg)
            progress_text.set(f"{avg:.0f}%")

    def on_add_to_queue():
        links = extract_links(links_text.get("1.0", "end"))
        if not links:
            write_log("\nPlease paste at least one valid URL first.\n")
            return
        add_links_to_queue(links)

    def on_paste_download():
        """Add pasted links to queue and start Download All if idle."""
        links = extract_links(links_text.get("1.0", "end"))
        if links:
            add_links_to_queue(links)
        if state["running"]:
            if links:
                write_log(
                    "A download is already running — new links will run on the next Download All.\n",
                )
            return
        if not any(r["status"] in (Q_PENDING, Q_FAILED) for r in queue_rows):
            write_log("\nPlease paste at least one valid URL first.\n")
            set_status("● Error", RED)
            return
        start_download_all()

    def start_download_all(only_failed=False):
        """Write pending (or only failed) rows to gui_queue.txt and start queuedl."""
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
            targets = [
                r for r in queue_rows if r["status"] in (Q_PENDING, Q_FAILED)
            ]
        if not targets:
            write_log("No pending links in the queue to download.\n")
            return
        queue_path = os.path.join(BASE_DIR, "gui_queue.txt")
        try:
            with open(queue_path, "w", encoding="utf-8") as f:
                f.write("\n".join(r["url"] for r in targets) + "\n")
        except OSError as e:
            write_log(f"\nERROR: Could not write gui_queue.txt — {e}\n")
            set_status("● Error", RED)
            return
        state["run_row_ids"] = [r["iid"] for r in targets]
        state["run_kind"] = "queue"
        run_action("queue_download", urls_file=queue_path)

    def on_grab(kind):
        url = channel_var.get().strip()
        if not url:
            write_log("\nPlease enter a Channel / Profile URL first.\n")
            set_status("● Error", RED)
            return
        if state["running"]:
            return
        state["run_kind"] = "grab"
        run_action(
            {"shorts": "grab_shorts", "videos": "grab_videos",
             "popular": "grab_popular"}[kind],
            grab_url=url,
        )

    def on_remove_selected():
        if state["running"]:
            write_log("Download is running — please Stop first.\n")
            return
        sel = set(tree.selection())
        if not sel:
            write_log("Select one or more rows in the queue first.\n")
            return
        queue_rows[:] = [r for r in queue_rows if r["iid"] not in sel]
        refresh_queue_view()
        write_log(f"Removed {len(sel)} selected row(s) from queue.\n")

    def on_clear_finished():
        if state["running"]:
            write_log("Download is running — please Stop first.\n")
            return
        queue_rows[:] = [
            r for r in queue_rows if r["status"] not in (Q_DONE, Q_SKIPPED)
        ]
        refresh_queue_view()

    def on_clear_all():
        if state["running"]:
            write_log("Download is running — please Stop first.\n")
            return
        queue_rows.clear()
        refresh_queue_view()

    def set_buttons(enabled):
        st = "normal" if enabled else "disabled"
        for b in buttons:
            b.config(state=st)

    def reader(proc):
        try:
            for line in proc.stdout:
                out_queue.put(line)
        except Exception:  # noqa: BLE001
            pass
        out_queue.put(("__EXIT__", proc.wait()))

    def handle_output_line(line):
        """Parse queuedl protocol lines (QITEM / GRAB / GRABDONE / QDONE / QLOG)."""
        s = line.rstrip("\r\n")
        if s.startswith("QITEM "):
            parsed = parse_qitem(s)
            if parsed is not None:
                update_run_row(*parsed)
            return
        if s.startswith("GRABDONE "):
            n = s[len("GRABDONE "):].strip()
            write_log(f"Grabbed {n} link(s) from channel into queue.\n")
            return
        meta = parse_grab_meta(s)
        if meta is not None:
            pending_meta[meta["url"]] = meta
            return
        grabbed = parse_grab_line(s)
        if grabbed is not None:
            m = pending_meta.pop(grabbed, None)
            add_links_to_queue(
                [grabbed], announce=False,
                meta_map={grabbed: m} if m else None,
            )
            return
        qd = parse_qdone(s)
        if qd is not None:
            write_log(
                f"Queue finished: Done {qd['done']}, "
                f"Failed {qd['failed']}, Skipped {qd['skipped']}\n",
            )
            write_log(f"Saved in: {download_dir_var.get()}\n")
            return
        if s.startswith("QLOG "):
            write_log(s[len("QLOG "):] + "\n")
            return
        write_log(line)
        pct = parse_progress(line)
        if pct is not None and state["running"]:
            progress.stop()
            progress.config(mode="determinate", value=pct)
            progress_text.set(f"{pct:.0f}%")

    def poll_queue():
        try:
            while True:
                item = out_queue.get_nowait()
                if isinstance(item, tuple) and item and item[0] == "__EXIT__":
                    code = item[1]
                    was_stopped = state["stopped"]
                    state["running"] = False
                    state["proc"] = None
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
                        progress_text.set("Stopped")
                        set_status("● Stopped", RED)
                    elif code == 0:
                        progress.config(mode="determinate", value=100)
                        progress_text.set("100%")
                        set_status("● Completed ✓", GREEN)
                    else:
                        progress.config(mode="determinate", value=0)
                        progress_text.set("Error")
                        set_status("● Error", RED)
                    write_log(f"\nFINISHED — exit code {code}\n")
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
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        popen_kwargs = dict(
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if no_window:
            popen_kwargs["creationflags"] = no_window
        try:
            proc = subprocess.Popen(cmd, **popen_kwargs)
        except Exception as e:  # noqa: BLE001
            write_log(f"ERROR: Could not start command — {e}\n")
            set_status("● Error", RED)
            state["run_kind"] = None
            state["run_row_ids"] = []
            return
        state["proc"] = proc
        state["running"] = True
        state["stopped"] = False
        set_buttons(False)
        stop_btn.config(state="normal")
        set_status("● Running…", BLUE_BRIGHT)
        progress.config(mode="indeterminate")
        progress.start(12)
        progress_text.set("Running…")
        threading.Thread(target=reader, args=(proc,), daemon=True).start()

    def stop_proc():
        proc = state.get("proc")
        if proc is not None and state["running"]:
            state["stopped"] = True
            write_log("\n--- Stop requested — terminating process... ---\n")
            try:
                proc.terminate()
            except Exception:  # noqa: BLE001
                pass

    def open_folder(path):
        try:
            startfile = getattr(os, "startfile", None)
            if startfile is not None:
                startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:  # noqa: BLE001
            write_log(f"\nCould not open folder — {e}\nPath: {path}\n")

    write_log("Nexus Bulk ready. Paste links, grab from a channel, or run a check.\n")
    write_log(f"Workspace: {BASE_DIR}\n")
    if dl_warn:
        write_log(f"WARNING: {dl_warn}\n")
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
