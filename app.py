#!/usr/bin/env python3
"""
Bulk Tool — GUI App (buttons wali window, personal use only)
=============================================================
Terminal wale tool (pipeline.py / multi_upload.py) ke upar aik
saadi si window: double-click `run.bat` ya `python app.py` chalao,
button dabao, neeche log mein sab output live nazar aata hai.

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

Buttons aur un ke terminal commands:
    1. Sirf Check (Pipeline)   -> python pipeline.py --check
    2. Download Only           -> python pipeline.py --download-only [--limit N] --quality <quality>
    3. Pipeline Test (1 video) -> python pipeline.py --limit 1 --privacy <privacy> --quality <quality>
    4. Pipeline Chalao         -> python pipeline.py --privacy <privacy> [--limit N] --quality <quality>
    5. Multi Upload Check      -> python multi_upload.py --check [--target T]
    6. Multi Upload Chalao     -> python multi_upload.py [--target T] [--limit N]
       (multi mein privacy queue ki rows se aati hai, is liye
        wahan --privacy pass nahi hota; quality download ke waqt
        decide hoti hai, upload pe nahi, is liye multi ko --quality
        bhi pass nahi hota)

Quality dropdown: 2160 = 4K (default), 1440 = 2K, 1080, 720 —
sirf download wale buttons (2, 3, 4) pe lagti hai.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRIVACY_CHOICES = ("private", "unlisted", "public")
QUALITY_CHOICES = ("720", "1080", "1440", "2160")  # 1440 = 2K, 2160 = 4K

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


def build_command(action, limit="", target="", privacy="private", quality="2160"):
    """Action -> command list. Pure function — koi window, koi subprocess nahi.

    Script names app wale folder ke relative hain; GUI in ko
    cwd=BASE_DIR ke sath chalati hai.
    """
    py = sys.executable
    lim = _parse_limit(limit)
    tgt = (target or "").strip()
    q = _parse_quality(quality)

    if action == "check":
        return [py, "pipeline.py", "--check"]

    if action == "download_only":
        cmd = [py, "pipeline.py", "--download-only"]
        if lim is not None:
            cmd += ["--limit", str(lim)]
        cmd += ["--quality", q]
        return cmd

    if action == "pipeline_test1":
        return [py, "pipeline.py", "--limit", "1",
                "--privacy", _parse_privacy(privacy), "--quality", q]

    if action == "pipeline":
        cmd = [py, "pipeline.py", "--privacy", _parse_privacy(privacy)]
        if lim is not None:
            cmd += ["--limit", str(lim)]
        cmd += ["--quality", q]
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

    root = tk.Tk()
    root.title("Bulk Tool")
    root.geometry("760x560")

    state = {"proc": None, "running": False}
    out_queue = queue.Queue()

    # --- upar wale fields ---
    fields = tk.Frame(root)
    fields.pack(fill="x", padx=10, pady=(10, 0))

    tk.Label(fields, text="Limit (optional):").grid(row=0, column=0, sticky="w")
    limit_var = tk.StringVar()
    tk.Entry(fields, textvariable=limit_var, width=8).grid(
        row=0, column=1, padx=(4, 16), sticky="w")

    tk.Label(fields, text="Target (optional):").grid(row=0, column=2, sticky="w")
    target_var = tk.StringVar()
    tk.Entry(fields, textvariable=target_var, width=18).grid(
        row=0, column=3, padx=(4, 16), sticky="w")

    tk.Label(fields, text="Privacy:").grid(row=0, column=4, sticky="w")
    privacy_var = tk.StringVar(value="private")
    tk.OptionMenu(fields, privacy_var, *PRIVACY_CHOICES).grid(
        row=0, column=5, padx=(4, 16), sticky="w")

    tk.Label(fields, text="Quality:").grid(row=0, column=6, sticky="w")
    quality_var = tk.StringVar(value="2160")
    tk.OptionMenu(fields, quality_var, "2160", "1440", "1080", "720").grid(
        row=0, column=7, padx=(4, 0), sticky="w")

    tk.Label(
        root,
        text="Target ki misaal: mind-maze-yt / mind-maze-fb / horror-fb "
             "— khaali chhor do to saare targets.",
        anchor="w",
    ).pack(fill="x", padx=10)

    tk.Label(
        root,
        text="Quality: 2160 = 4K, 1440 = 2K — sirf download wale "
             "buttons (2, 3, 4) pe lagti hai.",
        anchor="w",
    ).pack(fill="x", padx=10)

    # --- log area ---
    log = scrolledtext.ScrolledText(root, wrap="word", height=22)
    log.pack(fill="both", expand=True, padx=10, pady=10)

    def write_log(text):
        log.insert("end", text)
        log.see("end")

    # --- buttons ---
    btn_frame = tk.Frame(root)
    btn_frame.pack(fill="x", padx=10, pady=(0, 10))

    buttons = []

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
                    state["running"] = False
                    state["proc"] = None
                    set_buttons(True)
                    write_log(f"\nKHATAM — exit code {item[1]}\n")
                else:
                    write_log(item)
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
            return
        state["proc"] = proc
        state["running"] = True
        set_buttons(False)
        threading.Thread(target=reader, args=(proc,), daemon=True).start()

    def stop_proc():
        proc = state.get("proc")
        if proc is not None and state["running"]:
            write_log("\n--- Stop dabya — process band kar raha hoon... ---\n")
            try:
                proc.terminate()
            except Exception:  # noqa: BLE001
                pass

    specs = [
        ("1. Sirf Check (Pipeline)", "check"),
        ("2. Download Only", "download_only"),
        ("3. Pipeline — Pehli 1 Video (Test)", "pipeline_test1"),
        ("4. Pipeline Chalao (Download + Upload)", "pipeline"),
        ("5. Multi Upload — Check", "multi_check"),
        ("6. Multi Upload Chalao (FB + YT)", "multi_upload"),
    ]
    for i, (label, action) in enumerate(specs):
        b = tk.Button(
            btn_frame, text=label, width=38,
            command=lambda a=action: run_action(a),
        )
        b.grid(row=i // 2, column=i % 2, padx=4, pady=3, sticky="ew")
        buttons.append(b)
    tk.Button(
        btn_frame, text="Stop", width=38, command=stop_proc,
    ).grid(row=3, column=0, columnspan=2, padx=4, pady=3, sticky="ew")
    btn_frame.columnconfigure(0, weight=1)
    btn_frame.columnconfigure(1, weight=1)

    write_log("Bulk Tool ready hai. Pehle '1. Sirf Check' dabao.\n")
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
