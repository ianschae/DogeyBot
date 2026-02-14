# Doge Trading Bot

Simple Dogecoin (DOGE-USD) trading bot for Coinbase Advanced Trade. Plug in your API keys and run. Uses RSI mean-reversion on a learned timeframe: buy when RSI &lt; entry (oversold), sell when RSI &gt; exit (recovery). Places **post-only limit orders** (maker only) to avoid fees. Trades only with the balance already in your account (no external capital).

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

   Everything runs from main by default: learning (backtest on startup and every 24h), the trading loop (every 60s), and the GUI. The bot fetches DOGE-USD candles (on the learned timeframe) and your balance, then either logs what it would do (dry-run) or places **post-only limit orders** (maker only, to avoid fees). Stop with Ctrl+C.

   **GUI:** A doge-game style window with a big portfolio score, stat blocks (DOGE, USD, gain, last move), RSI and next-check progress bars, and optional images. Add **dogey.png** (and optionally **dogecoin.png**) in `src/assets/` for the main graphic and the click-to-spawn coins; click **"Much click. Wow coins."** to make coins fall from the top. Set `UI_ENABLED=false` in `.env` to run without the window.

**Run tests:** `pytest tests/`

**Test API:** `python -m src.test_api` (read-only). Add `--test-buy` or `--test-sell` to place a small post-only limit order; `--test-order` places one order (buy if you have USD, else sell if you have DOGE).

## Trading strategy

The bot uses **RSI mean reversion** with standard **Wilder RSI(14)**:

- **RSI:** Wilder’s smoothing over the last 14 closes. First average gain/loss is the simple average of the first 14 changes, then each new value is smoothed with `avg = (prev_avg * 13 + current) / 14`. RSI = `100 - 100/(1 + RS)` where RS = average gain / average loss.
- **Timeframe:** The learning step tests **all** supported granularities (1m through 1d), pulls up to 350 candles per timeframe, and picks the single best **(granularity, entry, exit)** by backtest return. That granularity is saved in `learned_params.json` as `CANDLE_GRANULARITY`; the bot fetches candles on that timeframe (e.g. SIX_HOUR or ONE_HOUR) so live trading matches the backtest.
- **Signal:** Binary (in or out). **Buy** when not in position and RSI &lt; entry (oversold). **Sell** when in position and RSI &gt; exit (recovered). Otherwise **hold**.
- **Entry/exit:** Default 30/50. Learning searches a grid (entry 10–45, exit &gt; entry up to 76), uses 0.6% fee per side and simulates post-only limit fills (buy below mid, sell above mid). Best combo is saved to `learned_params.json`; the bot uses it until the next re-learn (e.g. every 24h).
- **Execution:** **Post-only limit orders** only (maker, no taker fees). Buy: limit placed 0.1% below mid; sell: limit 0.1% above mid. Good-til-canceled; if the order would cross the spread it is rejected (post-only). On buy the bot uses all available USD; on sell, all DOGE. Min order size and cooldown between orders apply.

So: Wilder RSI(14) on the **learned** timeframe, mean-reversion rules, all-in per signal, with post-only limits to avoid fees.

## Learning

The bot **learns in real time** from main: on startup it pulls max history (350 candles) for **every** timeframe (ONE_MINUTE through ONE_DAY), runs the (entry, exit) grid on each, and picks the single **(granularity, entry, exit)** with highest backtest return &gt; 0. That choice is written to `learned_params.json` (RSI_PERIOD, RSI_ENTRY, RSI_EXIT, CANDLE_GRANULARITY). If no profitable combo is found, it falls back to default RSI and SIX_HOUR. Re-learn runs every 24 hours. Backtests use **0.6% fee per side** (Coinbase maker) and simulate post-only limit fills (0.1% better price). Optional: run `python -m src.learn` with `--days 60` to pre-write `learned_params.json`; override fee with `LEARN_FEE_PCT` in `.env` (default 0.6).

## Behavior

- **Product**: DOGE-USD for candles, buys, and sells.
- **Strategy**: RSI(14) mean reversion on the **learned** candle timeframe (saved in `learned_params.json`). Buy when RSI &lt; entry, sell when RSI &gt; exit (defaults 30/50).
- **Orders**: Post-only limit orders only (maker); 0.1% inside mid (`LIMIT_OFFSET_PCT` in config). No market orders.
- **Capital**: Uses only the DOGE and USD in your Coinbase account (no external deposits). Buys use all available USD; sells use all DOGE. Having both DOGE and USD at once (e.g. from DCA outside the bot) is supported: portfolio value is USD + DOGE×price, and you're only "in position" when you have at least the min sell size in DOGE, so dust won't block buying.
- **Safety**: Default is dry-run. Set `DRY_RUN=false` and `ALLOW_LIVE=true` in `.env` to enable live trading. Min order size and cooldown between orders apply.

## Data

The bot writes `portfolio_state.json` (initial value, peak, started_at), `portfolio_log.csv` (one row per poll: timestamp_utc, usd, doge, price, portfolio_value_usd, gain_usd, gain_pct, peak_usd, drawdown_pct, days_tracked, avg_daily_gain_pct, avg_daily_gain_usd), and `status.json` (current snapshot for the GUI; in `.gitignore`). The GUI shows portfolio value, gain, peak, drawdown, days tracked, and average daily gain. The CSV grows by about one row per poll (e.g. ~1440 rows per day at 60s). For long-running 24/7 use, archive or trim the file periodically if needed.

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
