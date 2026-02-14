# Doge Trading Bot

Simple Dogecoin (DOGE-USD) trading bot for Coinbase Advanced Trade. Plug in your API keys and run. Uses RSI mean-reversion: buy when RSI &lt; 30 (oversold), sell when RSI &gt; 50 (recovery). Trades only with the balance already in your account (no external capital).

## Setup

1. **Install dependencies**

   ```bash
   cd /path/to/Doge
   python3 -m venv .venv
   source .venv/bin/activate   # or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

2. **Configure API keys**

   - Create an API key at [Coinbase Developer Platform](https://docs.cdp.coinbase.com/advanced-trade/docs/getting-started).
   - When creating the key, use **view** and **trade** only; **do not enable transfer or withdraw**.
   - Copy `.env.example` to `.env` and set:
     - `COINBASE_API_KEY` – your API key
     - `COINBASE_API_SECRET` – your API secret
   - Optional: `DRY_RUN=false` and `ALLOW_LIVE=true` to trade for real (defaults: dry run only, no orders).

3. **Run**

   ```bash
   python -m src.main
   ```

   Everything runs from main by default: learning (backtest on startup and every 24h), the trading loop (every 60s), and the GUI. The bot fetches DOGE-USD candles and your balance, then either logs what it would do (dry-run) or places market orders. Stop with Ctrl+C.

   **GUI:** A doge-game style window with a big portfolio score, stat blocks (DOGE, USD, gain, last move), RSI and next-check progress bars, and optional images. Add **dogey.png** (and optionally **dogecoin.png**) in `src/assets/` for the main graphic and the click-to-spawn coins; click **"Much click. Wow coins."** to make coins fall from the top. Set `UI_ENABLED=false` in `.env` to run without the window.

Run tests: `pytest tests/`

Test API: `python -m src.test_api` (add `--test-order` or `--test-buy` for a small real order).

## Trading strategy

The bot uses **RSI mean reversion** with standard **Wilder RSI(14)**:

- **RSI:** Wilder’s smoothing over the last 14 closes of 6-hour candles: first average gain/loss is the simple average of the first 14 changes, then each new value is smoothed with `avg = (prev_avg * 13 + current) / 14`. RSI = `100 - 100/(1 + RS)` where RS = average gain / average loss.
- **Signal:** Binary (in or out). **Buy** when not in position and RSI &lt; entry (oversold). **Sell** when in position and RSI &gt; exit (recovered). Otherwise **hold**.
- **Entry/exit:** Default 30/50. The learning step backtests the last 60 days and, if profitable, picks the best (entry, exit) from a small grid and saves them to `learned_params.json`; the bot uses those until the next re-learn (e.g. every 24h).
- **Execution:** On buy it uses all available USD (market buy); on sell it uses all DOGE (market sell). Min order size and a cooldown between orders apply. No stop-loss beyond the RSI exit level.

So: classic Wilder RSI(14) on 6h DOGE-USD, mean-reversion rules, all-in per signal, with learned or default thresholds.

## Learning

The bot **learns in real time** from main: on startup it backtests the last 60 days and picks the best RSI entry/exit. **Only if that backtest is profitable** does it use those params; otherwise it falls back to defaults (buy when RSI &lt; 30, sell when RSI &gt; 50). While running, it re-learns every 24 hours. Optional: run `python -m src.learn` with `--days 60` to pre-write `learned_params.json`; set `LEARN_FEE_PCT=0.5` in `.env` for a 0.5% fee per side in backtests.

## Behavior

- **Product**: DOGE-USD for candles, buys, and sells.
- **Strategy**: RSI(14) mean reversion; buy when RSI &lt; 30, sell when RSI &gt; 50. Uses 6-hour candles.
- **Capital**: Uses only the DOGE and USD in your Coinbase account (no external deposits). Buys use USD; on sell it sells all DOGE. Having both DOGE and USD at once (e.g. from DCA outside the bot) is supported: portfolio value is USD + DOGE×price, and you're only "in position" when you have at least the min sell size in DOGE, so dust won't block buying.
- **Safety**: Default is dry-run. Set `DRY_RUN=false` and `ALLOW_LIVE=true` in `.env` to enable live trading. Min order size and cooldown between orders apply.

## Data

The bot writes `portfolio_state.json` (initial value, peak portfolio value, and started_at), `portfolio_log.csv` (one row per poll: timestamp_utc, usd, doge, price, portfolio_value_usd, gain_usd, gain_pct, peak_usd, drawdown_pct, days_tracked, avg_daily_gain_pct), and `status.json` (current snapshot for the GUI). The GUI shows portfolio value, gain, peak, drawdown from peak, days tracked, and average daily gain %. The CSV grows by about one row per poll (e.g. ~1440 rows per day at 60s). For long-running 24/7 use, archive or trim the file periodically if needed.

## Security

- **Secrets**: API key and secret are read only from the environment (e.g. `.env`). Never commit `.env`; it is in `.gitignore`. Use `.env.example` as a template with no real values.
- **API key scope**: Create keys with **view** and **trade** only. Do **not** enable transfer or withdraw.
- **Files**: On Unix, generated files (`status.json`, `portfolio_state.json`, `portfolio_log.csv`, `learned_params.json`) are restricted to owner read/write (mode `0o600`) after each write. Restrict `.env` yourself if desired: `chmod 600 .env`.
- **Logs**: Log output may include balances and portfolio value; protect log files and terminal output if you consider that sensitive.
- **Dependencies**: Run `pip install -r requirements.txt` from a venv and periodically check for known vulnerabilities, e.g. `pip install pip-audit && pip-audit`.

## Running 24/7

Run inside a terminal multiplexer (e.g. `screen` or `tmux`) or a process manager (e.g. systemd, supervisor) so the bot keeps running across disconnects and reboots.

## Disclaimer

Trading cryptocurrency is risky. Past backtest or paper results do not guarantee future profit. Use at your own risk.
