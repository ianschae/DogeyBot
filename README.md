# Doge Trading Bot

A simple Dogecoin (DOGE-USD) trading bot for **Coinbase Advanced Trade**. It uses RSI mean-reversion on a **learned timeframe**, places **post-only limit orders** (maker only, to avoid fees), and trades only with the balance already in your account—no external capital or transfers.

---

## Table of contents

- [What it does](#what-it-does)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Trading strategy](#trading-strategy)
- [Learning (backtest)](#learning-backtest)
- [Execution (orders)](#execution-orders)
- [Gain tracking](#gain-tracking)
- [Data and files](#data-and-files)
- [GUI](#gui)
- [Running as an app (macOS)](#running-as-an-app-macos)
- [Testing](#testing)
- [Security](#security)
- [Running 24/7](#running-247)
- [Disclaimer](#disclaimer)

---

## What it does

1. **Learns** — On startup and every 24 hours, the bot backtests all supported timeframes (1m through 1d) and chooses the single best **(timeframe, RSI entry, RSI exit)** by historical return (with 0.6% fee and post-only fill simulation).
2. **Trades** — Every 60 seconds it fetches DOGE-USD candles on that learned timeframe, computes RSI, and decides: **buy** (when not in position and RSI &lt; entry), **sell** (when in position and RSI &gt; exit), or **hold**.
3. **Executes** — When it buys or sells, it places **post-only limit orders** only (limit price 0.1% inside mid so you stay maker and avoid taker fees). No market orders.

By default the bot runs in **dry-run** mode: it logs what it would do but does not place real orders. Enable live trading by setting `DRY_RUN=false` and `ALLOW_LIVE=true` in `.env`.

---

## Quick start

```bash
cd /path/to/Doge
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set your Coinbase API key and secret (create a key with **view** and **trade** only at [Coinbase Developer Platform](https://docs.cdp.coinbase.com/advanced-trade/docs/getting-started)).

```bash
python -m src.main
```

This starts the learning run, then the trading loop and (if enabled) the GUI. Use Ctrl+C to stop.

---

## Configuration

All configuration is via environment variables. Use a `.env` file in the project root (see `.env.example`).

| Variable | Default | Description |
|----------|---------|-------------|
| `COINBASE_API_KEY` | *(required)* | Your Coinbase API key |
| `COINBASE_API_SECRET` | *(required)* | Your Coinbase API secret |
| `DRY_RUN` | `true` | If `true`, no real orders are placed |
| `ALLOW_LIVE` | `false` | Must be `true` with `DRY_RUN=false` to place live orders |
| `UI_ENABLED` | `true` | Show the doge-game style GUI window |
| `LEARN_DAYS` | `60` | Days of history considered for learning (used in standalone `src.learn`; main uses max candles per timeframe) |
| `LEARN_INTERVAL_SECONDS` | `86400` | Seconds between re-learn runs (24h) |
| `POLL_INTERVAL_SECONDS` | `60` | Seconds between trading loop checks |
| `STATUS_REFRESH_SECONDS` | `15` | Seconds between UI price/status refreshes |
| `ORDER_COOLDOWN_SECONDS` | `300` | Minimum seconds between placing orders |
| `LEARN_FEE_PCT` | `0.6` | Fee % per side used in backtest (Coinbase maker ~0.6%) |
| `LOG_LEVEL` | `INFO` | Logging level: DEBUG, INFO, WARNING, ERROR |

Hardcoded in code (no env): min order size 1 USD / 1 DOGE, RSI period 14, limit offset 0.1% for post-only orders, backtest grid (entry 10–45, exit &gt; entry up to 76).

---

## Trading strategy

### RSI (Wilder)

- **Indicator:** Wilder RSI(14) on the **close** of each candle. First average gain/loss is the simple average of the first 14 changes; then each new value is smoothed: `avg = (prev_avg * 13 + current) / 14`. RSI = `100 - 100/(1 + RS)` where RS = average gain / average loss.
- **Signal:** Binary. **Buy** when you are not in position and RSI &lt; **entry**. **Sell** when you are in position and RSI &gt; **exit**. Otherwise **hold**.
- **Entry/exit:** Default 30/50. The learning step chooses the best (entry, exit) from a grid and saves them (and the best **timeframe**) in `learned_params.json`; the bot loads these on startup and after each re-learn.

### Move decision

The bot’s signal each poll is **buy**, **sell**, or **hold** — one of these three:

| Condition | Move |
|-----------|------|
| Not in position **and** RSI &lt; entry | **buy** |
| In position **and** RSI &gt; exit | **sell** |
| Otherwise | **hold** |

So: you only **buy** when you hold no (or dust) DOGE and RSI is below the learned entry threshold; you only **sell** when you hold DOGE and RSI is above the learned exit threshold. Otherwise you stay put. The same logic is used for live trading and for the backtest (`signal_from_rsi()` in `src/strategies/rsi_mean_reversion.py`).

### Timeframe

- The bot does **not** use a fixed candle size. Learning tests every supported granularity (ONE_MINUTE, FIVE_MINUTE, …, ONE_DAY), pulls up to 350 candles per timeframe, and picks the **(granularity, entry, exit)** with the highest backtest return. That granularity is saved as `CANDLE_GRANULARITY`; the live bot fetches candles on that same timeframe so strategy and execution align.

### In position

- You are **in position** when your available DOGE is at least the minimum sell size (1 DOGE). Portfolio value is USD + DOGE×price. Having both DOGE and USD (e.g. from DCA outside the bot) is supported; small dust DOGE does not block new buys.

---

## Learning (backtest)

- **When:** On startup and every `LEARN_INTERVAL_SECONDS` (default 24h).
- **What:** For each timeframe, fetch up to 350 candles, then run a full (entry, exit) grid. Keep the single combo with highest **backtest return &gt; 0** and at least one trade. Write the best **granularity**, **RSI_ENTRY**, **RSI_EXIT**, and **RSI_PERIOD** to `learned_params.json`.
- **Backtest assumptions:** 0.6% fee per side (Coinbase maker), and post-only style fills (buy at close×0.999, sell at close×1.001). No slippage.
- **If no profitable combo:** The bot keeps current RSI params and uses SIX_HOUR; it does not overwrite `learned_params.json` with a losing combo.

**Standalone learning:** Run `python -m src.learn` to run the same process once and write `learned_params.json`. Option: `--days 60` (used only for logging; history is still capped by 350 candles per timeframe). Override backtest fee with `LEARN_FEE_PCT` in `.env`.

---

## Execution (orders)

- **Order type:** **Post-only limit orders only.** No market orders. Limits are placed so you are always maker (buy slightly below mid, sell slightly above mid), to avoid taker fees.
- **Prices:** Buy limit = current price × (1 − 0.001); sell limit = current price × (1 + 0.001). The 0.1% offset is configurable in code (`LIMIT_OFFSET_PCT`).
- **Behavior:** Orders are Good-til-Canceled (GTC). If the limit would immediately match (cross the spread), the exchange rejects the order (post-only). The bot does not cancel or replace open orders; it only places one order per signal and respects cooldown.
- **Size:** Buy uses all available USD (converted to DOGE at the limit price); sell uses all available DOGE. Minimum order size (1 USD / 1 DOGE) and `ORDER_COOLDOWN_SECONDS` apply.

---

## Gain tracking

Gain is **total return since tracking started**, not per-trade P&amp;L.

- **Portfolio value** (each poll): `USD balance + DOGE balance × current DOGE-USD price`. The bot gets balances from Coinbase and values your DOGE at the current market price.
- **Initial value:** The first time the bot runs (or when `portfolio_state.json` is missing/invalid), it saves that snapshot as the baseline. That value is stored as `initial_portfolio_value_usd` and never changed.
- **Gain:**  
  - **Gain (USD)** = current portfolio value − initial portfolio value.  
  - **Gain (%)** = (gain USD / initial) × 100.  
  So if you started at $100 and you’re at $105, gain is $5 and 5%.
- **Peak:** The bot also stores the highest portfolio value ever seen (`peak_portfolio_value_usd`). **Drawdown** is how far you are below that peak: `(peak − current value) / peak × 100`.
- **Days tracked:** Full calendar days since tracking started (integer). **Avg daily gain %** and **avg daily gain USD** use that full-day count in the denominator (once you have at least one full day).

State is persisted in `portfolio_state.json`; each poll is appended to `portfolio_log.csv` with all of the above so you can inspect or chart history.

---

## Data and files

| File | Purpose |
|------|---------|
| `learned_params.json` | Best RSI period, entry, exit, and **CANDLE_GRANULARITY** from the last learning run. Loaded by the bot at startup. |
| `portfolio_state.json` | Initial portfolio value, peak value, and tracking start time. Created on first run. |
| `portfolio_log.csv` | One row per poll: timestamp, usd, doge, price, portfolio_value_usd, gain_usd, gain_pct, peak_usd, drawdown_pct, days_tracked, avg_daily_gain_pct, avg_daily_gain_usd. Append-only. |
| `status.json` | Current snapshot for the GUI (balances, signal, RSI, backtest result, etc.). In `.gitignore`; not committed. |

The CSV grows by about one row per poll (~1440 rows per day at 60s). For long 24/7 runs, archive or trim it periodically if needed.

---

## GUI

With `UI_ENABLED=true` (default), a doge-themed window shows:

- Portfolio value, total gain (USD and %), peak, drawdown, days tracked, average daily gain
- DOGE and USD balances, current signal (BUY / SELL / HODL), last price
- RSI bar and “buy when RSI &lt; entry, sell when RSI &gt; exit”
- Progress bars for “next check” and “next backtest”
- Last backtest result (return %, trade count)

**Assets:** Put **dogey.png** (and optionally **dogecoin.png**) in `src/assets/` for the main graphic and click-to-spawn coins. Click **“Much click. Wow coins.”** to spawn falling coins.

Set `UI_ENABLED=false` in `.env` to run without the window (e.g. headless server).

---

## Running as an app (macOS)

Double-click **Doge.app** in the project folder to run the bot without a terminal. The app uses your project’s `.venv` and `.env`; close the Doge window to quit. You can drag `Doge.app` to the Dock or Applications for quick access. The app icon is built from `src/assets/dogecoin.png`; to rebuild it after changing that image, run `python scripts/build_app_icon.py` (from the repo root, with the venv activated).

---

## Testing

- **Unit tests:** `pytest tests/`
- **API test (read-only):** `python -m src.test_api` — checks accounts, candles, and candle range.
- **API test with one order:**  
  - `python -m src.test_api --test-buy` — place a small post-only limit buy (if you have enough USD).  
  - `python -m src.test_api --test-sell` — place a small post-only limit sell (if you have enough DOGE).  
  - `python -m src.test_api --test-order` — place one order: buy if you have USD, else sell if you have DOGE.

---

## Security

- **Secrets:** API key and secret are read only from the environment (e.g. `.env`). Do not commit `.env`; it is listed in `.gitignore`. Use `.env.example` as a template.
- **API key scope:** Create keys with **view** and **trade** only. Do **not** enable transfer or withdraw.
- **Generated files:** On Unix, the bot restricts `learned_params.json`, `portfolio_state.json`, `portfolio_log.csv`, and `status.json` to owner read/write (`0o600`) after writing. Restrict `.env` yourself if desired: `chmod 600 .env`.
- **Logs:** Logs may include balances and portfolio value; treat terminal and log output as sensitive if needed.
- **Dependencies:** Install from `requirements.txt` inside a venv and periodically check for issues (e.g. `pip install pip-audit && pip-audit`).

---

## Running 24/7

Run the bot inside a terminal multiplexer (e.g. `screen` or `tmux`) or a process manager (e.g. systemd, supervisor) so it keeps running across disconnects and reboots.

---

## Disclaimer

Trading cryptocurrency is risky. Past backtest or paper results do not guarantee future profit. Use at your own risk.
