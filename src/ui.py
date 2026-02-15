"""UI for the Doge bot: GUI (tkinter) by default; optional terminal UI (rich)."""
import json
import time
from pathlib import Path

from . import config

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

# Backtest uses 350 candles; days covered depends on granularity (so trades/month is consistent with "350 days" etc.)
_CANDLES_350_DAYS = {
    "ONE_MINUTE": 350 * 60 / 86400,
    "FIVE_MINUTE": 350 * (5 * 60) / 86400,
    "FIFTEEN_MINUTE": 350 * (15 * 60) / 86400,
    "THIRTY_MINUTE": 350 * (30 * 60) / 86400,
    "ONE_HOUR": 350 * 3600 / 86400,
    "TWO_HOUR": 350 * (2 * 3600) / 86400,
    "FOUR_HOUR": 350 * (4 * 3600) / 86400,
    "SIX_HOUR": 350 * (6 * 3600) / 86400,
    "ONE_DAY": 350.0,
}


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
        "peak_usd": 0,
        "drawdown_pct": 0,
        "change_24h_pct": None,
        "volume_24h": None,
        "days_tracked": 0,
        "avg_daily_gain_pct": 0,
        "avg_daily_gain_usd": 0,
        "price": 0,
        "rsi": None,
        "rsi_entry": 30,
        "rsi_exit": 50,
        "timestamp_utc": None,
        "next_check_seconds": config.STATUS_REFRESH_SECONDS,
        "last_learn_timestamp_utc": None,
        "learn_interval_seconds": config.LEARN_INTERVAL_SECONDS,
        "dry_run": config.DRY_RUN,
        "allow_live": config.ALLOW_LIVE,
        "backtest_return_pct": None,
        "backtest_trades": None,
        "backtest_days": None,
        "backtest_granularity": None,
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
    """Seconds until next trading check. Uses last_trading_check_utc when set (so 15s status refresh doesn't reset the 60s countdown)."""
    ts = s.get("last_trading_check_utc") or s.get("timestamp_utc")
    next_sec = s.get("next_check_seconds") or config.STATUS_REFRESH_SECONDS
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


def _load_coin_images_for_depth():
    """Load three coin sizes for depth (back=small, front=large). Returns list of (PhotoImage, size, speed)."""
    sizes = (26, 40, 56)
    speeds = (3, 5, 8)
    out = []
    for size, speed in zip(sizes, speeds):
        ph = _load_coin_image(size)
        if ph is not None:
            out.append((ph, size, speed))
    if not out:
        return []
    # If only one loaded, use it for all layers
    if len(out) == 1:
        ph, sz, sp = out[0]
        return [(ph, sz, 3), (ph, sz, 5), (ph, sz, 8)]
    while len(out) < 3:
        out.append(out[-1])
    return out[:3]


def run_gui(shutdown_event) -> None:
    """Run the desktop GUI: big clicker-game style, all numbers from real status."""
    import tkinter as tk
    from tkinter import font as tkfont
    from tkinter import ttk

    root = tk.Tk()
    root.title("Doge. Such Trade. Wow.")
    root.minsize(420, 580)
    root.resizable(True, True)
    root.configure(bg="#fffbf0", padx=12, pady=10)
    bg = "#fffbf0"
    card_bg = "#f0e6d0"
    border = "#d4c4a0"  # subtle warm border for polish

    # Full-window coin layer (behind everything): coins fall from top, full width, with depth
    coin_canvas = tk.Canvas(root, bg=bg, highlightthickness=0)
    coin_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
    coin_photos_by_layer = _load_coin_images_for_depth()
    coin_refs = [p[0] for p in coin_photos_by_layer]
    coin_data = {}  # cid -> {"speed": int, "layer": int} for fall_step
    COIN_FALL_MS = 35

    # Load and show multiple Doge images (keep refs so they aren’t GC’d)
    doge_photos = _load_doge_images(max_size=80, small_size=36)
    photo_refs = [p[0] for p in doge_photos]
    try:
        font_title = tkfont.Font(family="Comic Sans MS", size=14, weight="bold")
        font_score = tkfont.Font(family="Comic Sans MS", size=22, weight="bold")
        font_stat = tkfont.Font(family="Comic Sans MS", size=11, weight="bold")
        font_label = tkfont.Font(family="Comic Sans MS", size=10)
        font_party = tkfont.Font(family="Comic Sans MS", size=12, weight="bold")
    except tk.TclError:
        font_title = tkfont.Font(family="Helvetica", size=14, weight="bold")
        font_score = tkfont.Font(family="Helvetica", size=22, weight="bold")
        font_stat = tkfont.Font(family="Helvetica", size=11, weight="bold")
        font_label = tkfont.Font(family="Helvetica", size=10)
        font_party = tkfont.Font(family="Helvetica", size=12, weight="bold")

    # Shared palette and spacing (tighter so it fits)
    fg_primary = "#3d2914"
    fg_accent = "#c9a227"
    fg_muted = "#8b7355"
    fg_success = "#2d8a3e"
    fg_danger = "#c0392b"
    pad_sm, pad_md, pad_lg = 2, 6, 8

    # Style progress bars to match the warm theme
    style = ttk.Style()
    style.configure("Warm.Horizontal.TProgressbar", troughcolor=card_bg, background=fg_accent, bordercolor=fg_muted, lightcolor=fg_accent, darkcolor="#8b6914")
    try:
        style.theme_use("clam")
        style.configure("Warm.Horizontal.TProgressbar", troughcolor=card_bg, background=fg_accent)
    except tk.TclError:
        pass

    tk.Label(root, text="Such Trade. Very Strategy. Wow.", font=font_title, bg=bg, fg=fg_accent).pack(pady=(0, pad_sm))
    tk.Label(root, text="much RSI  ·  many candle  ·  so profit", font=font_label, bg=bg, fg=fg_muted).pack(pady=(0, pad_lg))

    center_f = tk.Frame(root, bg=bg)
    center_f.pack(pady=(pad_md, pad_sm))
    if doge_photos:
        tk.Label(center_f, image=doge_photos[0][0], bg=bg).pack()
        if len(doge_photos) > 1:
            row_small = tk.Frame(center_f, bg=bg)
            row_small.pack(pady=(2, 0))
            for (ph, _) in doge_photos[1:4]:
                tk.Label(row_small, image=ph, bg=bg).pack(side=tk.LEFT, padx=2)
    else:
        tk.Label(center_f, text="\ud83d\udc15", font=("Helvetica", 36), bg=bg, fg=fg_accent).pack()

    score_label = tk.Label(root, text="$—", font=font_score, bg=bg, fg=fg_primary)
    score_label.pack(pady=(pad_lg, pad_sm))
    tk.Label(root, text="much portfolio (live)", font=font_label, bg=bg, fg=fg_muted).pack(pady=(0, pad_lg))

    stats_f = tk.Frame(root, bg=bg)
    stats_f.pack(fill=tk.X, pady=(0, pad_lg))
    for col in range(5):
        stats_f.columnconfigure(col, weight=1)
    stat_names = ("many DOGE", "such USD", "very gain", "wow move", "such price")
    stat_keys = ("doge", "usd", "gain", "move", "price")
    stat_labels = {}
    for col, (name, key) in enumerate(zip(stat_names, stat_keys)):
        f = tk.Frame(stats_f, bg=card_bg, highlightbackground=border, highlightthickness=1, padx=4, pady=3)
        f.grid(row=0, column=col, padx=2, pady=0, sticky="nsew")
        tk.Label(f, text=name, font=font_label, bg=card_bg, fg=fg_muted).pack()
        lbl = tk.Label(f, text="—", font=font_stat, bg=card_bg, fg=fg_primary)
        lbl.pack()
        stat_labels[key] = lbl
    extra_names = ("peak portfolio", "days tracked", "avg daily %", "USD daily", "24h change")
    extra_keys = ("peak", "days", "avg_daily", "usd_daily", "change_24h")
    for col, (name, key) in enumerate(zip(extra_names, extra_keys)):
        f = tk.Frame(stats_f, bg=card_bg, highlightbackground=border, highlightthickness=1, padx=4, pady=3)
        f.grid(row=1, column=col, padx=2, pady=(2, 0), sticky="nsew")
        tk.Label(f, text=name, font=font_label, bg=card_bg, fg=fg_muted).pack()
        lbl = tk.Label(f, text="—", font=font_stat, bg=card_bg, fg=fg_primary)
        lbl.pack()
        stat_labels[key] = lbl

    # Strategy & timers: one bordered section for visual grouping
    bars_f = tk.Frame(root, bg=bg)
    bars_f.pack(fill=tk.X, pady=(pad_md, 0))
    strategy_f = tk.Frame(bars_f, bg=card_bg, highlightbackground=border, highlightthickness=1, padx=6, pady=4)
    strategy_f.pack(fill=tk.X, pady=(0, pad_md))
    tk.Label(strategy_f, text="RSI", font=font_label, bg=card_bg, fg=fg_muted).pack(anchor=tk.W, pady=(0, 1))
    rsi_row = tk.Frame(strategy_f, bg=card_bg)
    rsi_row.pack(fill=tk.X, pady=(0, 1))
    rsi_bar = ttk.Progressbar(rsi_row, length=200, mode="determinate", maximum=100, style="Warm.Horizontal.TProgressbar")
    rsi_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
    rsi_value_label = tk.Label(rsi_row, text="—", font=font_label, bg=card_bg, fg=fg_primary)
    rsi_value_label.pack(side=tk.LEFT)
    strategy_explanation_label = tk.Label(strategy_f, text="—", font=font_label, bg=card_bg, fg=fg_primary, wraplength=380, justify=tk.LEFT)
    strategy_explanation_label.pack(anchor=tk.W, pady=(4, 0))

    tk.Label(bars_f, text="many seconds until next backtest", font=font_label, bg=bg, fg=fg_muted).pack(anchor=tk.W, pady=(pad_sm, 1))
    learn_bar = ttk.Progressbar(bars_f, length=220, mode="determinate", maximum=100, style="Warm.Horizontal.TProgressbar")
    learn_bar.pack(fill=tk.X, pady=(0, 1))
    learn_value_label = tk.Label(bars_f, text="—", font=font_label, bg=bg, fg=fg_primary)
    learn_value_label.pack(anchor=tk.W, pady=(0, pad_lg))

    # Coin rain + party mode: more coins when party is on, floating popups, more phrases
    import random

    click_times = []
    party_mode_until = [0.0]
    PARTY_CLICKS = 4
    PARTY_WINDOW = 1.5
    PARTY_DURATION = 22.0
    COINS_NORMAL = 2
    COINS_PARTY = 10
    PARTY_SPEED_MULT = 1.6
    DOGE_PARTY_PHRASES = (
        "WOW", "such party", "many coins", "very wow", "so rich", "much coin",
        "very party", "such wow", "many wow", "doge party", "to the moon",
        "so wow", "much party", "very rich", "such coins", "wow wow WOW",
        "diamond paws", "much profit", "very gains", "such moon", "many wow",
        "to the moon!", "HODL", "very rich", "so moon", "much party mode",
    )
    CLICK_POPUPS = ("WOW", "💎", "🐕", "much", "wow", "$$", "moon")
    POPUP_COLORS = ("#c9a227", "#e6b800", "#2d8a3e", "#c0392b", "#8e44ad", "#2980b9", "#d35400", "#16a085", "#c0392b", "#27ae60")

    def fall_step(cid):
        try:
            data = coin_data.get(cid)
            speed = data["speed"] if data else 5
            coin_canvas.move(cid, 0, speed)
            x, y = coin_canvas.coords(cid)
            h = coin_canvas.winfo_height() or 580
            if y < h + 60:
                root.after(COIN_FALL_MS, lambda c=cid: fall_step(c))
            else:
                coin_canvas.delete(cid)
                coin_data.pop(cid, None)
        except tk.TclError:
            coin_data.pop(cid, None)

    def spawn_one_coin(speed_mult=1.0):
        if not coin_photos_by_layer:
            return
        w = coin_canvas.winfo_width() or 420
        layer = random.randint(0, min(2, len(coin_photos_by_layer) - 1))
        photo, size, base_speed = coin_photos_by_layer[layer]
        speed = max(2, int(base_speed * speed_mult))
        x = random.randint(0, w) if w > 0 else random.randint(0, 420)
        cid = coin_canvas.create_image(x, -size - 10, image=photo, tags=("coin", f"layer{layer}"))
        coin_data[cid] = {"speed": speed, "layer": layer}
        coin_canvas.tag_lower("layer0")
        coin_canvas.tag_raise("layer2")
        root.after(COIN_FALL_MS, lambda c=cid: fall_step(c))

    def spawn_click_popup():
        """Short-lived popup at a random position with a random color."""
        try:
            w = coin_canvas.winfo_width() or 420
            h = coin_canvas.winfo_height() or 580
            x = random.randint(50, max(51, w - 50))
            y = random.randint(50, max(51, h - 50))
            text = random.choice(CLICK_POPUPS)
            color = random.choice(POPUP_COLORS)
            tid = coin_canvas.create_text(x, y, text=text, font=("Comic Sans MS", 24, "bold"), fill=color, tags=("popup",))
            coin_canvas.tag_raise(tid)
            def remove():
                try:
                    coin_canvas.delete(tid)
                except tk.TclError:
                    pass
            root.after(900, remove)
        except (tk.TclError, ValueError):
            pass

    def spawn_coin():
        now = time.time()
        click_times[:] = [t for t in click_times if now - t < PARTY_WINDOW]
        click_times.append(now)
        is_party = now < party_mode_until[0]
        if len(click_times) >= PARTY_CLICKS and now > party_mode_until[0]:
            party_mode_until[0] = now + PARTY_DURATION
            is_party = True
        n = COINS_PARTY if is_party else COINS_NORMAL
        mult = PARTY_SPEED_MULT if is_party else 1.0
        for _ in range(n):
            spawn_one_coin(speed_mult=mult)
        spawn_click_popup()

    # Party phrase: always in layout (fixed height) to avoid glitch when toggling
    party_label = tk.Label(root, text="", font=font_party, bg=bg, fg=fg_accent, height=1)
    party_label.pack(pady=(2, 1))
    party_phrase_until = [0.0]

    btn_canvas = tk.Canvas(root, width=200, height=36, bg=bg, highlightthickness=0, cursor="hand2")
    btn_canvas.pack(pady=(4, pad_md))

    def draw_rounded_rect(c, x1, y1, x2, y2, r, fill, outline, width=2):
        c.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, fill=fill, outline=outline, width=width)
        c.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, fill=fill, outline=outline, width=width)
        c.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, fill=fill, outline=outline, width=width)
        c.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, fill=fill, outline=outline, width=width)
        c.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline=fill)
        c.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline=fill)

    draw_rounded_rect(btn_canvas, 2, 2, 198, 34, 8, "#e6b800", border, 1)
    btn_canvas.create_text(100, 18, text="Much click. Wow coins.", font=font_stat, fill=fg_primary)
    def on_coin_click(e):
        spawn_coin()

    btn_canvas.bind("<Button-1>", on_coin_click)

    mode_label = tk.Label(root, text="", font=font_label, bg=bg, fg=fg_muted)
    mode_label.pack(pady=(pad_md, 0))
    updated_ago_label = tk.Label(root, text="", font=font_label, bg=bg, fg=fg_muted)
    updated_ago_label.pack(pady=(2, 0))

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

    # Cache last-displayed values so we only update widgets when changed (reduces flicker/redraws)
    _last = {}

    def _set_label(lbl, text, fg=None):
        key = id(lbl)
        prev = _last.get(key, (None, None))
        if (text, fg) == prev:
            return
        _last[key] = (text, fg)
        if fg is not None:
            lbl.config(text=text, fg=fg)
        else:
            lbl.config(text=text)

    def _set_bar(bar, value):
        key = id(bar)
        v = min(100, max(0, value))
        if _last.get(key) == v:
            return
        _last[key] = v
        bar["value"] = v

    def update_gui():
        if shutdown_event.is_set():
            root.quit()
            return
        s = _read_status()
        pv = s.get("portfolio_value") or 0
        gu = s.get("gain_usd") or 0
        gp = s.get("gain_pct") or 0
        sig = (s.get("signal") or "hold").lower()
        move_text = "BUY" if sig == "buy" else "SELL" if sig == "sell" else "HODL"
        rsi_val = s.get("rsi")

        _set_label(score_label, f"${fmt(pv)}")
        _set_label(stat_labels["doge"], fmt_doge(s.get("doge")))
        _set_label(stat_labels["usd"], f"${fmt(s.get('usd'))}")
        gain_text = f"${fmt(gu)} ({fmt(gp)}%)"
        _set_label(stat_labels["gain"], gain_text, fg_success if gp > 0 else fg_danger if gp < 0 else fg_primary)
        _set_label(stat_labels["move"], move_text, fg_success if sig == "buy" else fg_danger if sig == "sell" else fg_accent)
        price_val = s.get("price")
        _set_label(stat_labels["price"], f"${fmt(price_val)}" if price_val not in (None, 0) else "—")
        peak_val = s.get("peak_usd") or 0
        days_val = s.get("days_tracked") or 0
        avg_val = s.get("avg_daily_gain_pct") or 0
        usd_daily_val = s.get("avg_daily_gain_usd") or 0
        _set_label(stat_labels["peak"], f"${fmt(peak_val)}")
        _set_label(stat_labels["days"], str(int(days_val)))
        _set_label(stat_labels["avg_daily"], f"{fmt(avg_val)}%", fg_success if avg_val > 0 else fg_danger if avg_val < 0 else fg_primary)
        _set_label(stat_labels["usd_daily"], f"${fmt(usd_daily_val)}", fg_success if usd_daily_val > 0 else fg_danger if usd_daily_val < 0 else fg_primary)
        ch = s.get("change_24h_pct")
        vol = s.get("volume_24h")
        if ch is not None:
            change_text = f"{'+' if ch >= 0 else ''}{fmt(ch)}%"
            if vol is not None and vol >= 0:
                if vol >= 1_000_000:
                    change_text += f"\n{vol / 1_000_000:.1f}M vol"
                elif vol >= 1_000:
                    change_text += f"\n{vol / 1_000:.1f}K vol"
                else:
                    change_text += f"\n{fmt(vol)} vol"
            _set_label(stat_labels["change_24h"], change_text, fg_success if ch > 0 else fg_danger if ch < 0 else fg_primary)
        else:
            _set_label(stat_labels["change_24h"], "—", fg_primary)

        if rsi_val is not None:
            rsi_v = min(100, max(0, float(rsi_val)))
            _set_bar(rsi_bar, rsi_v)
            _set_label(rsi_value_label, f"RSI = {fmt(rsi_val)}")
        else:
            _set_bar(rsi_bar, 0)
            _set_label(rsi_value_label, "RSI = —")
        entry_r = s.get("rsi_entry")
        exit_r = s.get("rsi_exit")
        bt_gran = s.get("backtest_granularity") or "candles"
        entry_r = entry_r if entry_r is not None else 30
        exit_r = exit_r if exit_r is not None else 50
        # One flowing explanation: what we trade on, what’s happening now, and last backtest
        if rsi_val is None:
            current_bit = "We're still waiting for enough closed candles to compute RSI, so no decision yet."
        elif sig == "buy":
            current_bit = f"RSI is {fmt(rsi_val)}, below the buy threshold ({entry_r}), so we're buying."
        elif sig == "sell":
            current_bit = f"RSI is {fmt(rsi_val)}, above the sell threshold ({exit_r}), so we're selling DOGE."
        elif s.get("in_position"):
            current_bit = f"RSI is {fmt(rsi_val)}, still below the sell threshold ({exit_r}), so we're holding until RSI rises above {exit_r}."
        else:
            current_bit = f"RSI is {fmt(rsi_val)}, above the buy threshold ({entry_r}), so we're holding until RSI drops below {entry_r}."
        intro = f"We're trading DOGE using RSI(14) on the last 350 {bt_gran} closed candles. We buy when RSI drops below {entry_r} and sell when it rises above {exit_r}. RSI and every decision use only closed candles, so the value updates when a new candle closes."
        explanation = f"{intro}\n\nRight now: {current_bit}"
        bt_ret = s.get("backtest_return_pct")
        bt_trades = s.get("backtest_trades")
        if bt_ret is not None and bt_trades is not None:
            # Trades/month only when we know the actual backtest span (350 candles for this granularity)
            backtest_days = _CANDLES_350_DAYS.get(bt_gran) if bt_gran else None
            if backtest_days and backtest_days > 0:
                freq = f" (~{(bt_trades / backtest_days) * 30:.1f}/month)"
            else:
                freq = ""
            explanation += f"\n\nOver that same 350-candle period, this setup would have returned {bt_ret:+.2f}% in {bt_trades} trades{freq}."
        _set_label(strategy_explanation_label, explanation)

        learn_cd = _countdown_learn_sec(s)
        learn_interval = s.get("learn_interval_seconds") or config.LEARN_INTERVAL_SECONDS
        if learn_cd is not None and learn_interval and learn_interval > 0:
            pct_learn = 100.0 * (learn_interval - learn_cd) / learn_interval
            _set_bar(learn_bar, pct_learn)
            h, r = divmod(learn_cd, 3600)
            m, sec = divmod(r, 60)
            _set_label(learn_value_label, f"Next backtest in {int(h)}h {int(m)}m {int(sec)}s")
        else:
            _set_bar(learn_bar, 0)
            _set_label(learn_value_label, "—")

        mode_text = "such dry run. no order. wow." if s.get("dry_run") else "very live. much trade." if s.get("allow_live") else "live off. such safe."
        _set_label(mode_label, mode_text)
        ts = s.get("timestamp_utc")
        if ts:
            try:
                from datetime import datetime
                then = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                ago = int(time.time() - then)
                if ago < 60:
                    updated_text = f"Updated {ago}s ago"
                elif ago < 3600:
                    updated_text = f"Updated {ago // 60}m ago"
                else:
                    updated_text = f"Updated {ago // 3600}h ago"
            except Exception:
                updated_text = ""
        else:
            updated_text = ""
        _set_label(updated_ago_label, updated_text)
        now_ui = time.time()
        if now_ui < party_mode_until[0]:
            if now_ui >= party_phrase_until[0]:
                party_phrase_until[0] = now_ui + 0.35
                party_label.config(text=random.choice(DOGE_PARTY_PHRASES), fg=fg_accent)
        else:
            party_label.config(text="")
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
