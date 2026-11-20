#!/usr/bin/env python3
"""
Bulk Tool — GUI App (buttons wali window, personal use only)
=============================================================
Terminal wale tool (pipeline.py / multi_upload.py) ke upar aik
modern, friendly window: double-click `run.bat` ya `python app.py`
chalao, section mein button dabao, neeche Live Log mein sab output
live nazar aata hai, aur progress bar download ka percent dikhati
hai.

Look: dark theme, teen alag sections (Download / YouTube Upload /
Multi Upload) — har section ka apna rang aur baray saaf buttons,
upar status (Ready / Chal raha hai / Ho gaya / Error).

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
    DOWNLOAD card:
      Download Only            -> python pipeline.py --download-only [--limit N] --quality <quality> [--downloads <folder>]
      Sirf Check               -> python pipeline.py --check [--downloads <folder>]
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

Download Folder (Download card): Browse… se koi bhi folder chun
sakte ho jahan downloads jayengi — default project ka downloads/
folder entry mein pehle se likha hota hai, Reset usay wapas le
aata hai. Ye folder pipeline ke download wale actions aur Check
ko --downloads se pass hota hai; upload flow bhi usi folder se
videos uthata hai (uploads.csv wahi se banti hai). Multi Upload
ko ye pass NAHI hota — wahan queue ki rows hi sab kuch hain.
"""
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRIVACY_CHOICES = ("private", "unlisted", "public")
QUALITY_CHOICES = ("720", "1080", "1440", "2160")  # 1440 = 2K, 2160 = 4K
TARGET_PRESETS = ("mind-maze-yt", "mind-maze-fb", "horror-fb")

# --- Modern dark theme (sirf GUI in ko use karti hai) ---
COL_BG = "#16181d"          # window background
COL_CARD = "#1f222b"        # section cards
COL_BORDER = "#2c303c"      # card / field borders
COL_TEXT = "#e8eaf0"        # primary text
COL_MUTED = "#9aa3b2"       # secondary / hint text
COL_ACCENT = "#4f7cff"      # blue — YouTube pipeline / focus
COL_ACCENT_ACTIVE = "#3d63d6"
COL_GREEN = "#2ea86a"       # download
COL_GREEN_ACTIVE = "#22794d"
COL_PURPLE = "#7c5cff"      # multi upload
COL_PURPLE_ACTIVE = "#6347d6"
COL_RED = "#d9534f"         # stop / error
COL_RED_ACTIVE = "#b93e3a"
COL_BTN = "#2a2e39"         # secondary buttons
COL_BTN_ACTIVE = "#363b49"
COL_INPUT = "#262a35"       # entries / dropdowns
COL_LOG_BG = "#101216"
COL_LOG_FG = "#d6dae3"

FONT_UI = ("Segoe UI", 10)
FONT_TITLE = ("Segoe UI", 21, "bold")
FONT_SECTION = ("Segoe UI", 12, "bold")
FONT_BTN = ("Segoe UI", 11, "bold")
FONT_SMALL = ("Segoe UI", 9)
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


def build_command(action, limit="", target="", privacy="private", quality="2160",
                  download_dir=""):
    """Action -> command list. Pure function — koi window, koi subprocess nahi.

    Script names app wale folder ke relative hain; GUI in ko
    cwd=BASE_DIR ke sath chalati hai.

    download_dir: pipeline ke download wale actions (download_only,
    pipeline_test1, pipeline) aur check ko --downloads se pass hota
    hai — check bhi usi folder ko scan karke uploads.csv banata hai.
    Khaali/whitespace ho to pass NAHI hota (pipeline ka apna default
    downloads/ lagta hai). Multi actions ko kabhi pass nahi hota.
    """
    py = sys.executable
    lim = _parse_limit(limit)
    tgt = (target or "").strip()
    q = _parse_quality(quality)
    dl = (download_dir or "").strip()

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
        return cmd

    if action == "pipeline_test1":
        cmd = [py, "pipeline.py", "--limit", "1",
               "--privacy", _parse_privacy(privacy), "--quality", q]
        if dl:
            cmd += ["--downloads", dl]
        return cmd

    if action == "pipeline":
        cmd = [py, "pipeline.py", "--privacy", _parse_privacy(privacy)]
        if lim is not None:
            cmd += ["--limit", str(lim)]
        cmd += ["--quality", q]
        if dl:
            cmd += ["--downloads", dl]
        return cmd

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
        f"pipeline_test1, pipeline, multi_check, multi_upload"
    )


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
    root.geometry("900x720")
    root.minsize(820, 660)
    root.configure(bg=COL_BG)

    # ttk styles — clam theme pe progress bar / combobox ke rang lagte hain
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(
        "Modern.Horizontal.TProgressbar",
        troughcolor=COL_CARD, background=COL_ACCENT,
        bordercolor=COL_BG, lightcolor=COL_ACCENT, darkcolor=COL_ACCENT,
        thickness=14,
    )
    style.configure(
        "Dark.TCombobox",
        fieldbackground=COL_INPUT, background=COL_BTN,
        foreground=COL_TEXT, arrowcolor=COL_TEXT,
        bordercolor=COL_BORDER, lightcolor=COL_BORDER, darkcolor=COL_BORDER,
        padding=4,
    )
    root.option_add("*TCombobox*Listbox.background", COL_INPUT)
    root.option_add("*TCombobox*Listbox.foreground", COL_TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", COL_ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    state = {"proc": None, "running": False, "stopped": False}
    out_queue = queue.Queue()
    buttons = []

    main = tk.Frame(root, bg=COL_BG)
    main.pack(fill="both", expand=True, padx=14, pady=12)

    # ---------- chhote widget helpers ----------
    def field_label(parent, text):
        return tk.Label(parent, text=text, font=FONT_UI,
                        bg=COL_CARD, fg=COL_MUTED)

    def hint_label(parent, text):
        return tk.Label(parent, text=text, font=FONT_SMALL,
                        bg=COL_CARD, fg=COL_MUTED)

    def dark_entry(parent, var, width):
        return tk.Entry(
            parent, textvariable=var, width=width, bg=COL_INPUT,
            fg=COL_TEXT, insertbackground=COL_TEXT, relief="flat",
            font=FONT_UI, highlightthickness=1,
            highlightbackground=COL_BORDER, highlightcolor=COL_ACCENT)

    def dark_option_menu(parent, var, values, width=8):
        om = tk.OptionMenu(parent, var, *values)
        om.config(bg=COL_INPUT, fg=COL_TEXT,
                  activebackground=COL_BTN_ACTIVE, activeforeground=COL_TEXT,
                  relief="flat", bd=0, highlightthickness=1,
                  highlightbackground=COL_BORDER, font=FONT_UI,
                  cursor="hand2", width=width)
        try:
            om["menu"].config(bg=COL_INPUT, fg=COL_TEXT,
                              activebackground=COL_ACCENT,
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
            parent, text=text, command=command, bg=COL_BTN, fg=COL_TEXT,
            activebackground=COL_BTN_ACTIVE, activeforeground=COL_TEXT,
            relief="flat", bd=0, font=FONT_BTN, padx=14, pady=10,
            cursor="hand2", disabledforeground=COL_MUTED)

    def small_btn(parent, text, command):
        return tk.Button(
            parent, text=text, command=command, bg=COL_BTN, fg=COL_TEXT,
            activebackground=COL_BTN_ACTIVE, activeforeground=COL_TEXT,
            relief="flat", bd=0, font=FONT_UI, padx=10, pady=5,
            cursor="hand2", disabledforeground=COL_MUTED)

    def make_card(title, accent):
        card = tk.Frame(main, bg=COL_CARD, padx=14, pady=12,
                        highlightthickness=1, highlightbackground=COL_BORDER)
        card.pack(fill="x", pady=(0, 10))
        head = tk.Frame(card, bg=COL_CARD)
        head.pack(fill="x", pady=(0, 8))
        tk.Frame(head, bg=accent, width=4).pack(side="left", fill="y")
        tk.Label(head, text=title, font=FONT_SECTION,
                 bg=COL_CARD, fg=COL_TEXT).pack(side="left", padx=(8, 0))
        return card

    # ---------- header ----------
    header = tk.Frame(main, bg=COL_BG)
    header.pack(fill="x", pady=(0, 10))
    head_left = tk.Frame(header, bg=COL_BG)
    head_left.pack(side="left")
    tk.Label(head_left, text="Bulk Tool", font=FONT_TITLE,
             bg=COL_BG, fg=COL_TEXT).pack(anchor="w")
    tk.Label(head_left,
             text="Bulk Downloader • YouTube Uploader • "
                  "Multi-Page (Facebook + YouTube)",
             font=FONT_SMALL, bg=COL_BG, fg=COL_MUTED).pack(anchor="w")
    status_var = tk.StringVar(value="● Ready")
    status_lbl = tk.Label(header, textvariable=status_var, font=FONT_STATUS,
                          bg=COL_BG, fg=COL_MUTED)
    status_lbl.pack(side="right", anchor="n", pady=8)

    def set_status(text, color):
        status_var.set(text)
        status_lbl.config(fg=color)

    # ---------- card 1: DOWNLOAD ----------
    quality_var = tk.StringVar(value="2160")
    limit_var = tk.StringVar()
    card1 = make_card("DOWNLOAD", COL_GREEN)
    row1 = tk.Frame(card1, bg=COL_CARD)
    row1.pack(fill="x", pady=(0, 8))
    field_label(row1, "Quality:").pack(side="left")
    dark_option_menu(row1, quality_var, ("2160", "1440", "1080", "720")).pack(
        side="left", padx=(6, 4))
    hint_label(row1, "(2160 = 4K, 1440 = 2K)").pack(side="left", padx=(0, 18))
    field_label(row1, "Limit (optional):").pack(side="left")
    dark_entry(row1, limit_var, 8).pack(side="left", padx=(6, 0))
    hint_label(row1, "khaali = saari videos").pack(side="left", padx=(6, 0))
    # Download Folder row — default project ka downloads/ entry mein
    # pehle se likha hai taake user ko pata ho files kahan jati hain.
    default_downloads = os.path.join(BASE_DIR, "downloads")
    download_dir_var = tk.StringVar(value=default_downloads)

    def browse_folder():
        chosen = filedialog.askdirectory(
            initialdir=download_dir_var.get() or BASE_DIR,
            title="Download folder chuno")
        if chosen:
            download_dir_var.set(chosen)

    def reset_folder():
        download_dir_var.set(default_downloads)

    row1b = tk.Frame(card1, bg=COL_CARD)
    row1b.pack(fill="x", pady=(0, 8))
    field_label(row1b, "Download Folder:").pack(side="left")
    dark_entry(row1b, download_dir_var, 52).pack(
        side="left", fill="x", expand=True, padx=(6, 6))
    small_btn(row1b, "Browse…", browse_folder).pack(side="left", padx=(0, 6))
    small_btn(row1b, "Reset", reset_folder).pack(side="left")
    btns1 = tk.Frame(card1, bg=COL_CARD)
    btns1.pack(fill="x")
    b_download = primary_btn(btns1, "Download Only", COL_GREEN,
                             COL_GREEN_ACTIVE,
                             lambda: run_action("download_only"))
    b_download.pack(side="left", fill="x", expand=True, padx=(0, 6))
    b_check = secondary_btn(btns1, "Sirf Check",
                            lambda: run_action("check"))
    b_check.pack(side="left")
    buttons += [b_download, b_check]

    # ---------- card 2: UPLOAD — YOUTUBE ----------
    privacy_var = tk.StringVar(value="private")
    card2 = make_card("UPLOAD — YOUTUBE", COL_ACCENT)
    row2 = tk.Frame(card2, bg=COL_CARD)
    row2.pack(fill="x", pady=(0, 8))
    field_label(row2, "Privacy:").pack(side="left")
    dark_option_menu(row2, privacy_var, PRIVACY_CHOICES, width=10).pack(
        side="left", padx=(6, 4))
    hint_label(row2, "Pipeline = pehle download, phir YouTube upload. "
                     "Quality / Limit upar wale Download card se lagte hain."
               ).pack(side="left", padx=(8, 0))
    btns2 = tk.Frame(card2, bg=COL_CARD)
    btns2.pack(fill="x")
    b_test1 = secondary_btn(btns2, "Pipeline Test — Pehli 1 Video",
                            lambda: run_action("pipeline_test1"))
    b_test1.pack(side="left", padx=(0, 6))
    b_pipeline = primary_btn(btns2, "Pipeline — Download + Upload",
                             COL_ACCENT, COL_ACCENT_ACTIVE,
                             lambda: run_action("pipeline"))
    b_pipeline.pack(side="left", fill="x", expand=True)
    buttons += [b_test1, b_pipeline]

    # ---------- card 3: MULTI UPLOAD — FACEBOOK + YOUTUBE ----------
    target_var = tk.StringVar()
    card3 = make_card("MULTI UPLOAD — FACEBOOK + YOUTUBE", COL_PURPLE)
    row3 = tk.Frame(card3, bg=COL_CARD)
    row3.pack(fill="x", pady=(0, 8))
    field_label(row3, "Target:").pack(side="left")
    target_box = ttk.Combobox(row3, textvariable=target_var,
                              values=TARGET_PRESETS, style="Dark.TCombobox",
                              width=20, font=FONT_UI)
    target_box.pack(side="left", padx=(6, 4))
    hint_label(row3, "preset chuno ya khud likho — khaali = saare targets"
               ).pack(side="left", padx=(8, 0))
    btns3 = tk.Frame(card3, bg=COL_CARD)
    btns3.pack(fill="x")
    b_mcheck = secondary_btn(btns3, "Multi Check",
                             lambda: run_action("multi_check"))
    b_mcheck.pack(side="left", padx=(0, 6))
    b_multi = primary_btn(btns3, "Multi Upload", COL_PURPLE,
                          COL_PURPLE_ACTIVE,
                          lambda: run_action("multi_upload"))
    b_multi.pack(side="left", fill="x", expand=True)
    buttons += [b_mcheck, b_multi]

    # ---------- progress bar ----------
    prow = tk.Frame(main, bg=COL_BG)
    prow.pack(fill="x", pady=(2, 8))
    progress = ttk.Progressbar(prow, style="Modern.Horizontal.TProgressbar",
                               mode="indeterminate")
    progress.pack(side="left", fill="x", expand=True)
    progress_text = tk.StringVar(value="")
    tk.Label(prow, textvariable=progress_text, font=FONT_SMALL,
             bg=COL_BG, fg=COL_MUTED, width=16, anchor="e").pack(
        side="right", padx=(8, 0))

    # ---------- live log ----------
    tk.Label(main, text="Live Log", font=FONT_SECTION,
             bg=COL_BG, fg=COL_TEXT).pack(anchor="w")
    log = scrolledtext.ScrolledText(
        main, wrap="word", height=12, bg=COL_LOG_BG, fg=COL_LOG_FG,
        insertbackground=COL_LOG_FG, font=FONT_LOG, relief="flat",
        highlightthickness=1, highlightbackground=COL_BORDER)
    log.pack(fill="both", expand=True, pady=(4, 10))
    try:
        log.vbar.config(bg=COL_BTN, troughcolor=COL_CARD,
                        activebackground=COL_BTN_ACTIVE, relief="flat")
    except (tk.TclError, AttributeError):
        pass

    def write_log(text):
        log.insert("end", text)
        log.see("end")

    # ---------- bottom bar ----------
    bottom = tk.Frame(main, bg=COL_BG)
    bottom.pack(fill="x")
    stop_btn = tk.Button(
        bottom, text="Stop", command=lambda: stop_proc(),
        bg=COL_RED, fg="#ffffff", activebackground=COL_RED_ACTIVE,
        activeforeground="#ffffff", relief="flat", bd=0, font=FONT_BTN,
        padx=16, pady=8, cursor="hand2", state="disabled",
        disabledforeground="#e8b4b1")
    stop_btn.pack(side="left")
    folder_btn = tk.Button(
        bottom, text="Project Folder Kholo", command=lambda: open_folder(),
        bg=COL_BTN, fg=COL_TEXT, activebackground=COL_BTN_ACTIVE,
        activeforeground=COL_TEXT, relief="flat", bd=0, font=FONT_BTN,
        padx=14, pady=8, cursor="hand2")
    folder_btn.pack(side="left", padx=(8, 0))
    tk.Label(bottom,
             text="Tip: pehle Check, phir Test (1 video), phir Full.",
             font=FONT_SMALL, bg=COL_BG, fg=COL_MUTED).pack(side="right")

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

    def poll_queue():
        try:
            while True:
                item = out_queue.get_nowait()
                if isinstance(item, tuple) and item and item[0] == "__EXIT__":
                    code = item[1]
                    was_stopped = state["stopped"]
                    state["running"] = False
                    state["proc"] = None
                    set_buttons(True)
                    stop_btn.config(state="disabled")
                    progress.stop()
                    if was_stopped:
                        progress.config(mode="determinate", value=0)
                        progress_text.set("Ruk gaya")
                        set_status("● Ruk gaya", COL_RED)
                    elif code == 0:
                        progress.config(mode="determinate", value=100)
                        progress_text.set("100%")
                        set_status("● Ho gaya ✓", COL_GREEN)
                    else:
                        progress.config(mode="determinate", value=0)
                        progress_text.set("Error")
                        set_status("● Error", COL_RED)
                    write_log(f"\nKHATAM — exit code {code}\n")
                else:
                    write_log(item)
                    pct = parse_progress(item)
                    if pct is not None and state["running"]:
                        progress.stop()
                        progress.config(mode="determinate", value=pct)
                        progress_text.set(f"{pct:g}%")
        except queue.Empty:
            pass
        root.after(100, poll_queue)

    def run_action(action):
        if state["running"]:
            return
        try:
            cmd = build_command(
                action,
                limit=limit_var.get(),
                target=target_var.get(),
                privacy=privacy_var.get(),
                quality=quality_var.get(),
                download_dir=download_dir_var.get(),
            )
        except ValueError as e:
            write_log(f"\nERROR: {e}\n")
            return
        write_log(f"\n>>> {' '.join(cmd)}\n")
        popen_kwargs = dict(
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
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
            set_status("● Error", COL_RED)
            return
        state["proc"] = proc
        state["running"] = True
        state["stopped"] = False
        set_buttons(False)
        stop_btn.config(state="normal")
        set_status("● Chal raha hai…", COL_ACCENT)
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

    def open_folder():
        try:
            startfile = getattr(os, "startfile", None)
            if startfile is not None:
                startfile(BASE_DIR)  # Windows
            elif sys.platform == "darwin":
                subprocess.Popen(["open", BASE_DIR])
            else:
                subprocess.Popen(["xdg-open", BASE_DIR])
        except Exception as e:  # noqa: BLE001 — GUI ko crash nahi karna
            write_log(f"\nFolder khul nahi saka — {e}\nPath: {BASE_DIR}\n")

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
