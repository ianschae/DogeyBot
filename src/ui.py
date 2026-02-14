"""UI for the Doge bot: GUI (tkinter) by default; optional terminal UI (rich)."""
import json
import time
from pathlib import Path

from . import config

ASSETS_DIR = Path(__file__).resolve().parent / "assets"


def _read_status() -> dict:
    """Read status.json; return defaults if missing or invalid."""
    default = {
        "doge": 0,
        "usd": 0,
        "in_position": False,
        "signal": "hold",
        "portfolio_value": 0,
        "gain_usd": 0,
        "gain_pct": 0,
        "price": 0,
        "rsi": None,
        "rsi_entry": 30,
        "rsi_exit": 50,
        "timestamp_utc": None,
        "next_check_seconds": config.POLL_INTERVAL_SECONDS,
        "last_learn_timestamp_utc": None,
        "learn_interval_seconds": config.LEARN_INTERVAL_SECONDS,
        "dry_run": config.DRY_RUN,
        "allow_live": config.ALLOW_LIVE,
    }
    if not config.STATUS_FILE.exists():
        return default
    try:
        with open(config.STATUS_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else default
    except (json.JSONDecodeError, OSError):
        return default


def _make_display(s: dict, countdown_sec: int | None):
    """Build the rich layout for one frame."""
    from rich.console import Group
    from rich.panel import Panel
    from rich.text import Text
    from rich.table import Table

    def num(n):
        if n is None:
            return "—"
        return f"{n:,.2f}" if isinstance(n, (int, float)) else str(n)

    def doge_num(n):
        if n is None:
            return "—"
        x = float(n)
        return f"{x:,.0f}" if x >= 1000 else f"{x:,.2f}" if x >= 1 else f"{x:.4f}"

    pv = s.get("portfolio_value") or 0
    gu = s.get("gain_usd") or 0
    gp = s.get("gain_pct") or 0
    sig = (s.get("signal") or "hold").lower()

    # Header — Doge meme style (such/much/very/wow)
    title = Text()
    title.append("🐕 ", style="bold")
    title.append("Such Trade. Very Strategy. Wow.", style="bold yellow")
    title.append("  ·  much RSI  ·  many candle  ·  so profit", style="dim")

    # Stats table — Doge speak labels
    table = Table.grid(expand=True)
    table.add_column(justify="center", style="cyan")
    table.add_column(justify="center", style="magenta")
    table.add_column(justify="center", style="green")
    table.add_column(justify="center", style="yellow")
    table.add_column(justify="center", style="blue")
    table.add_column(justify="center", style="white")

    move_text = "BUY" if sig == "buy" else "SELL" if sig == "sell" else "HODL"
    move_style = "bold green" if sig == "buy" else "bold red" if sig == "sell" else "bold yellow"

    table.add_row(
        "[dim]much portfolio[/]\n" + f"${num(pv)}",
        "[dim]very gain[/]\n" + f"${num(gu)} ({num(gp)}%)",
        "[dim]many DOGE[/]\n" + doge_num(s.get("doge")),
        "[dim]such USD[/]\n" + f"${num(s.get('usd'))}",
        "[dim]very RSI[/]\n" + (num(s.get("rsi")) if s.get("rsi") is not None else "—"),
        "[dim]wow move[/]\n" + f"[{move_style}]{move_text}[/]",
    )

    cd = f"many seconds {countdown_sec}" if countdown_sec is not None else "Waiting..."
    mode = "[dim]such dry run. no order. wow.[/]" if s.get("dry_run") else "[green]very live. much trade.[/]" if s.get("allow_live") else "[dim]live off. such safe.[/]"

    content = Group(
        Panel(title, border_style="yellow"),
        Panel(table, title="[bold]Stats[/]", border_style="yellow"),
        Text.from_markup(f"  [dim]{cd}[/]  ·  {mode}"),
    )
    return content


def _countdown_sec(s: dict) -> int | None:
    """Seconds until next check from status timestamp."""
    ts = s.get("timestamp_utc")
    next_sec = s.get("next_check_seconds") or config.POLL_INTERVAL_SECONDS
    if not ts or not next_sec:
        return None
    try:
        from datetime import datetime
        then = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        elapsed = time.time() - then
        return max(0, int(next_sec - elapsed))
    except Exception:
        return None


def _countdown_learn_sec(s: dict) -> int | None:
    """Seconds until next backtest/learn run."""
    ts = s.get("last_learn_timestamp_utc")
    interval = s.get("learn_interval_seconds") or config.LEARN_INTERVAL_SECONDS
    if not ts or not interval:
        return None
    try:
        from datetime import datetime
        then = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        elapsed = time.time() - then
        return max(0, int(interval - elapsed))
    except Exception:
        return None


def _load_doge_images(max_size=120, small_size=56):
    """Load doge images from assets/ or return placeholder. Returns list of (PhotoImage, size)."""
    import tkinter as tk
    try:
        from PIL import Image, ImageTk
    except ImportError:
        return []

    def load(path, size):
        try:
            img = Image.open(path).convert("RGBA")
            img = img.resize((size, size), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    # Look for dogey.png (or .jpg, .jpeg, .gif) — use same image everywhere
    exts = (".png", ".jpg", ".jpeg", ".gif")
    dogey_path = None
    for ext in exts:
        p = ASSETS_DIR / f"dogey{ext}"
        if p.exists():
            dogey_path = p
            break

    def make_placeholder(sz):
        from PIL import ImageDraw
        img = Image.new("RGBA", (sz, sz), (255, 251, 240, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([4, max(4, sz // 8), sz - 4, sz - 4], fill="#f0c14b", outline="#c9a227", width=max(1, sz // 50))
        d.polygon([2, 2, sz // 6, sz // 4, sz // 8, sz // 3], fill="#e6b800", outline="#c9a227")
        d.polygon([sz - 2, 2, sz - sz // 6, sz // 4, sz - sz // 8, sz // 3], fill="#e6b800", outline="#c9a227")
        d.ellipse([sz // 4 - 2, sz // 2 - sz // 12, sz // 4 + sz // 8, sz // 2 + sz // 12], fill="#3d2914")
        d.ellipse([3 * sz // 4 - sz // 8, sz // 2 - sz // 12, 3 * sz // 4 + 2, sz // 2 + sz // 12], fill="#3d2914")
        d.ellipse([sz // 2 - sz // 12, sz // 2 + sz // 6, sz // 2 + sz // 12, sz // 2 + sz // 4], fill="#3d2914")
        return ImageTk.PhotoImage(img)

    if not dogey_path:
        return [(make_placeholder(max_size), max_size)] + [(make_placeholder(small_size), small_size) for _ in range(3)]

    # Use dogey.png for all 4 slots: one large, three small
    out = []
    ph_main = load(dogey_path, max_size)
    if ph_main is not None:
        out.append((ph_main, max_size))
    for _ in range(3):
        ph_small = load(dogey_path, small_size)
        if ph_small is not None:
            out.append((ph_small, small_size))
    return out


def _load_coin_image(size=48):
    """Load dogecoin.png (or dogey.png) for the click-to-spawn coins. Keep ref."""
    try:
        from PIL import Image, ImageTk
    except ImportError:
        return None
    for name in ("dogecoin", "dogey"):
        for ext in (".png", ".jpg", ".jpeg", ".gif"):
            p = ASSETS_DIR / f"{name}{ext}"
            if p.exists():
                try:
                    img = Image.open(p).convert("RGBA")
                    img = img.resize((size, size), Image.Resampling.LANCZOS)
                    return ImageTk.PhotoImage(img)
                except Exception:
                    pass
    # Placeholder: simple gold circle
    from PIL import ImageDraw
    img = Image.new("RGBA", (size, size), (255, 251, 240, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([2, 2, size - 2, size - 2], fill="#f0c14b", outline="#c9a227", width=2)
    return ImageTk.PhotoImage(img)


def run_gui(shutdown_event) -> None:
    """Run the desktop GUI: big clicker-game style, all numbers from real status."""
    import tkinter as tk
    from tkinter import font as tkfont
    from tkinter import ttk

    root = tk.Tk()
    root.title("Doge. Such Trade. Wow.")
    root.minsize(520, 720)
    root.resizable(True, True)
    root.configure(bg="#fffbf0", padx=24, pady=24)

    # Load and show multiple Doge images (keep refs so they aren’t GC’d)
    doge_photos = _load_doge_images(max_size=200, small_size=72)
    photo_refs = [p[0] for p in doge_photos]
    try:
        font_title = tkfont.Font(family="Comic Sans MS", size=22, weight="bold")
        font_score = tkfont.Font(family="Comic Sans MS", size=36, weight="bold")
        font_stat = tkfont.Font(family="Comic Sans MS", size=16, weight="bold")
        font_label = tkfont.Font(family="Comic Sans MS", size=12)
    except tk.TclError:
        font_title = tkfont.Font(family="Helvetica", size=22, weight="bold")
        font_score = tkfont.Font(family="Helvetica", size=36, weight="bold")
        font_stat = tkfont.Font(family="Helvetica", size=16, weight="bold")
        font_label = tkfont.Font(family="Helvetica", size=12)

    tk.Label(root, text="Such Trade. Very Strategy. Wow.", font=font_title, bg="#fffbf0", fg="#c9a227").pack(pady=(0, 4))
    tk.Label(root, text="much RSI  ·  many candle  ·  so profit", font=font_label, bg="#fffbf0", fg="#8b7355").pack(pady=(0, 12))

    center_f = tk.Frame(root, bg="#fffbf0")
    center_f.pack(pady=(8, 4))
    if doge_photos:
        tk.Label(center_f, image=doge_photos[0][0], bg="#fffbf0").pack()
        if len(doge_photos) > 1:
            row_small = tk.Frame(center_f, bg="#fffbf0")
            row_small.pack(pady=(6, 0))
            for (ph, _) in doge_photos[1:4]:
                tk.Label(row_small, image=ph, bg="#fffbf0").pack(side=tk.LEFT, padx=6)
    else:
        tk.Label(center_f, text="\ud83d\udc15", font=("Helvetica", 72), bg="#fffbf0", fg="#c9a227").pack()

    score_label = tk.Label(root, text="$—", font=font_score, bg="#fffbf0", fg="#3d2914")
    score_label.pack(pady=(12, 4))
    tk.Label(root, text="much portfolio (live)", font=font_label, bg="#fffbf0", fg="#8b7355").pack(pady=(0, 16))

    stats_f = tk.Frame(root, bg="#fffbf0")
    stats_f.pack(fill=tk.X, pady=(0, 16))
    for col in range(4):
        stats_f.columnconfigure(col, weight=1)
    stat_names = ("many DOGE", "such USD", "very gain", "wow move")
    stat_keys = ("doge", "usd", "gain", "move")
    stat_labels = {}
    for col, (name, key) in enumerate(zip(stat_names, stat_keys)):
        f = tk.Frame(stats_f, bg="#f0e6d0", relief=tk.RAISED, borderwidth=2, padx=12, pady=10)
        f.grid(row=0, column=col, padx=6, sticky="nsew")
        tk.Label(f, text=name, font=font_label, bg="#f0e6d0", fg="#8b7355").pack()
        lbl = tk.Label(f, text="—", font=font_stat, bg="#f0e6d0", fg="#3d2914")
        lbl.pack()
        stat_labels[key] = lbl

    tk.Label(root, text="very RSI", font=font_label, bg="#fffbf0", fg="#8b7355").pack(anchor=tk.W, pady=(8, 2))
    rsi_bar = ttk.Progressbar(root, length=400, mode="determinate", maximum=100)
    rsi_bar.pack(fill=tk.X, pady=(0, 2))
    rsi_value_label = tk.Label(root, text="—", font=font_label, bg="#fffbf0", fg="#3d2914")
    rsi_value_label.pack(anchor=tk.W, pady=(0, 12))

    tk.Label(root, text="many seconds until next check", font=font_label, bg="#fffbf0", fg="#8b7355").pack(anchor=tk.W, pady=(4, 2))
    next_bar = ttk.Progressbar(root, length=400, mode="determinate", maximum=100)
    next_bar.pack(fill=tk.X, pady=(0, 2))
    next_value_label = tk.Label(root, text="—", font=font_label, bg="#fffbf0", fg="#3d2914")
    next_value_label.pack(anchor=tk.W, pady=(0, 8))

    tk.Label(root, text="many seconds until next backtest", font=font_label, bg="#fffbf0", fg="#8b7355").pack(anchor=tk.W, pady=(4, 2))
    learn_bar = ttk.Progressbar(root, length=400, mode="determinate", maximum=100)
    learn_bar.pack(fill=tk.X, pady=(0, 2))
    learn_value_label = tk.Label(root, text="—", font=font_label, bg="#fffbf0", fg="#3d2914")
    learn_value_label.pack(anchor=tk.W, pady=(0, 12))

    # Coin rain canvas (coins fall from top)
    coin_canvas = tk.Canvas(root, width=480, height=160, bg="#fffbf0", highlightthickness=0)
    coin_canvas.pack(pady=(8, 4))
    coin_photo = _load_coin_image(size=44)
    coin_refs = [coin_photo] if coin_photo else []
    FALL_SPEED = 6
    COIN_FALL_MS = 35

    def fall_step(cid):
        try:
            coin_canvas.move(cid, 0, FALL_SPEED)
            x, y = coin_canvas.coords(cid)
            if y < 180:
                root.after(COIN_FALL_MS, lambda c=cid: fall_step(c))
            else:
                coin_canvas.delete(cid)
        except tk.TclError:
            pass

    def spawn_coin():
        if not coin_photo:
            return
        import random
        x = random.randint(30, 450)
        cid = coin_canvas.create_image(x, -22, image=coin_photo, tags="coin")
        root.after(COIN_FALL_MS, lambda: fall_step(cid))

    # Rounded, high-visibility button (Canvas with rounded rect + text)
    btn_canvas = tk.Canvas(root, width=320, height=56, bg="#fffbf0", highlightthickness=0, cursor="hand2")
    btn_canvas.pack(pady=(6, 8))

    def draw_rounded_rect(c, x1, y1, x2, y2, r, fill, outline, width=2):
        c.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, fill=fill, outline=outline, width=width)
        c.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, fill=fill, outline=outline, width=width)
        c.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, fill=fill, outline=outline, width=width)
        c.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, fill=fill, outline=outline, width=width)
        c.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline=fill)
        c.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline=fill)

    draw_rounded_rect(btn_canvas, 4, 4, 316, 52, 14, "#e6b800", "#8b6914", 3)
    btn_canvas.create_text(160, 28, text="Much click. Wow coins.", font=font_stat, fill="#3d2914")
    btn_canvas.bind("<Button-1>", lambda e: spawn_coin())

    mode_label = tk.Label(root, text="", font=font_label, bg="#fffbf0", fg="#8b7355")
    mode_label.pack(pady=(8, 0))

    def fmt(n):
        if n is None:
            return "—"
        if isinstance(n, (int, float)):
            return f"{n:,.2f}"
        return str(n)

    def fmt_doge(n):
        if n is None:
            return "—"
        x = float(n)
        return f"{x:,.0f}" if x >= 1000 else f"{x:,.2f}" if x >= 1 else f"{x:.4f}"

    def update_gui():
        if shutdown_event.is_set():
            root.quit()
            return
        s = _read_status()
        cd = _countdown_sec(s)
        pv = s.get("portfolio_value") or 0
        gu = s.get("gain_usd") or 0
        gp = s.get("gain_pct") or 0
        sig = (s.get("signal") or "hold").lower()
        move_text = "BUY" if sig == "buy" else "SELL" if sig == "sell" else "HODL"
        rsi_val = s.get("rsi")
        next_sec = s.get("next_check_seconds") or config.POLL_INTERVAL_SECONDS

        score_label.config(text=f"${fmt(pv)}")
        stat_labels["doge"].config(text=fmt_doge(s.get("doge")))
        stat_labels["usd"].config(text=f"${fmt(s.get('usd'))}")
        gain_text = f"${fmt(gu)} ({fmt(gp)}%)"
        stat_labels["gain"].config(text=gain_text, fg="#2d8a3e" if gp > 0 else "#c0392b" if gp < 0 else "#3d2914")
        stat_labels["move"].config(text=move_text, fg="#2d8a3e" if sig == "buy" else "#c0392b" if sig == "sell" else "#c9a227")

        if rsi_val is not None:
            rsi_bar["value"] = min(100, max(0, float(rsi_val)))
            rsi_value_label.config(text=f"RSI = {fmt(rsi_val)}")
        else:
            rsi_bar["value"] = 0
            rsi_value_label.config(text="RSI = —")

        if cd is not None and next_sec and next_sec > 0:
            pct = 100.0 * (next_sec - cd) / next_sec
            next_bar["value"] = min(100, max(0, pct))
            next_value_label.config(text=f"Next check in {cd}s")
        else:
            next_bar["value"] = 0
            next_value_label.config(text="—")

        learn_cd = _countdown_learn_sec(s)
        learn_interval = s.get("learn_interval_seconds") or config.LEARN_INTERVAL_SECONDS
        if learn_cd is not None and learn_interval and learn_interval > 0:
            pct_learn = 100.0 * (learn_interval - learn_cd) / learn_interval
            learn_bar["value"] = min(100, max(0, pct_learn))
            h, r = divmod(learn_cd, 3600)
            m, sec = divmod(r, 60)
            learn_value_label.config(text=f"Next backtest in {int(h)}h {int(m)}m {int(sec)}s")
        else:
            learn_bar["value"] = 0
            learn_value_label.config(text="—")

        mode_label.config(
            text="such dry run. no order. wow." if s.get("dry_run") else "very live. much trade." if s.get("allow_live") else "live off. such safe."
        )
        root.after(1000, update_gui)

    root.after(500, update_gui)

    def on_closing():
        shutdown_event.set()
        root.quit()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
    try:
        root.destroy()
    except Exception:
        pass


def run_tui(shutdown_event) -> None:
    """Run the terminal UI in the current thread. Exits when shutdown_event is set."""
    from rich.live import Live
    from rich.console import Console

    console = Console()
    with Live(console=console, refresh_per_second=2, transient=False) as live:
        while not shutdown_event.is_set():
            s = _read_status()
            cd = _countdown_sec(s)
            live.update(_make_display(s, cd))
            shutdown_event.wait(1.0)
