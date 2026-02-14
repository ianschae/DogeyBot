"""UI for the Doge bot: GUI (tkinter) by default; optional terminal UI (rich)."""
import json
import time

from . import config


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
        "timestamp_utc": None,
        "next_check_seconds": config.POLL_INTERVAL_SECONDS,
        "dry_run": config.DRY_RUN,
        "allow_live": config.ALLOW_LIVE,
    }
    if not config.STATUS_FILE.exists():
        return default
    try:
        with open(config.STATUS_FILE) as f:
            return json.load(f)
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

    # Header
    title = Text()
    title.append("🐕 ", style="bold")
    title.append("Doge Trading Game", style="bold yellow")
    title.append("  ·  much trade  ·  very RSI  ·  wow", style="dim")

    # Stats table
    table = Table.grid(expand=True)
    table.add_column(justify="center", style="cyan")
    table.add_column(justify="center", style="magenta")
    table.add_column(justify="center", style="green")
    table.add_column(justify="center", style="yellow")
    table.add_column(justify="center", style="blue")
    table.add_column(justify="center", style="white")

    gain_style = "green" if gp > 0 else "red" if gp < 0 else "dim"
    move_text = "BUY" if sig == "buy" else "SELL" if sig == "sell" else "HODL"
    move_style = "bold green" if sig == "buy" else "bold red" if sig == "sell" else "bold yellow"

    table.add_row(
        "[dim]SCORE[/]\n" + f"${num(pv)}",
        "[dim]GAIN[/]\n" + f"${num(gu)} ({num(gp)}%)",
        "[dim]DOGE[/]\n" + doge_num(s.get("doge")),
        "[dim]USD[/]\n" + f"${num(s.get('usd'))}",
        "[dim]RSI[/]\n" + (num(s.get("rsi")) if s.get("rsi") is not None else "—"),
        "[dim]MOVE[/]\n" + f"[{move_style}]{move_text}[/]",
    )

    cd = f"Next check in {countdown_sec}s" if countdown_sec is not None else "Waiting..."
    mode = "[dim]Dry run[/]" if s.get("dry_run") else "[green]Live[/]" if s.get("allow_live") else "[dim]Live off[/]"

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


def run_gui(shutdown_event) -> None:
    """Run the desktop GUI (tkinter). Exits when shutdown_event is set."""
    import tkinter as tk
    from tkinter import font as tkfont

    root = tk.Tk()
    root.title("Doge Trading Game")
    root.resizable(True, False)
    root.configure(bg="#fffbf0", padx=12, pady=12)

    # Title
    title_font = tkfont.Font(family="Helvetica", size=16, weight="bold")
    tk.Label(root, text="🐕 Doge Trading Game", font=title_font, bg="#fffbf0", fg="#3d2914").grid(row=0, column=0, columnspan=3, pady=(0, 4))
    tk.Label(root, text="much trade · very RSI · wow", bg="#fffbf0", fg="#666").grid(row=1, column=0, columnspan=3, pady=(0, 12))

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

    # Value labels (updated each tick)
    row = 2
    labels = {}
    for key, label_text in [
        ("score", "SCORE (Portfolio)"),
        ("gain", "GAIN"),
        ("doge", "DOGE"),
        ("usd", "USD"),
        ("rsi", "RSI"),
        ("move", "LAST MOVE"),
        ("countdown", "NEXT CHECK"),
    ]:
        tk.Label(root, text=label_text + ":", bg="#fffbf0", fg="#666", font=("Helvetica", 9)).grid(row=row, column=0, sticky="w", pady=2)
        lbl = tk.Label(root, text="—", bg="#fffbf0", fg="#3d2914", font=("Helvetica", 11, "bold"))
        lbl.grid(row=row, column=1, sticky="w", pady=2)
        labels[key] = lbl
        row += 1

    mode_label = tk.Label(root, text="", bg="#fffbf0", fg="#666", font=("Helvetica", 9))
    mode_label.grid(row=row, column=0, columnspan=2, pady=(8, 0))

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
        labels["score"].config(text=f"${fmt(pv)}")
        labels["gain"].config(text=f"${fmt(gu)} ({fmt(gp)}%)", fg="#2d8a3e" if gp > 0 else "#c0392b" if gp < 0 else "#3d2914")
        labels["doge"].config(text=fmt_doge(s.get("doge")))
        labels["usd"].config(text=f"${fmt(s.get('usd'))}")
        labels["rsi"].config(text=fmt(s.get("rsi")) if s.get("rsi") is not None else "—")
        labels["move"].config(text=move_text, fg="#2d8a3e" if sig == "buy" else "#c0392b" if sig == "sell" else "#c9a227")
        labels["countdown"].config(text=f"{cd}s" if cd is not None else "—")
        mode_label.config(text="Dry run (no orders)" if s.get("dry_run") else "Live" if s.get("allow_live") else "Live off")
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
