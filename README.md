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

   The bot runs in a loop (every 60 seconds), fetches DOGE-USD candles and your balance, and either logs what it would do (dry-run) or places market orders. Stop with Ctrl+C.

Run tests: `pytest tests/`

## Learning

The bot **learns in real time**: on startup it backtests the last 60 days and picks the best RSI entry/exit. **Only if that backtest is profitable** does it use those params; otherwise it falls back to the default settings (buy when RSI &lt; 30, sell when RSI &gt; 50). While running, it re-learns every 24 hours and only switches to new params when the new backtest is profitable.

You can also run learning standalone:

```bash
python -m src.learn
```

Optional: `--days 60` (default 60). Writes the best to `learned_params.json`; the next bot run will use it until the first in-run re-learn. Backtest assumes no fees by default; set `LEARN_FEE_PCT=0.5` (or similar) in `.env` for a 0.5% fee per side to make learned params more conservative.

## Behavior

- **Product**: DOGE-USD only.
- **Strategy**: RSI(14) mean reversion; buy when RSI &lt; 30, sell when RSI &gt; 50. Uses 6-hour candles.
- **Capital**: Uses only the DOGE and USD in your Coinbase account (no external deposits). On buy it uses all available USD; on sell it sells all DOGE. Having both DOGE and USD at once (e.g. from DCA outside the bot) is supported: portfolio value is USD + DOGE×price, and you're only "in position" when you have at least the min sell size in DOGE, so dust won't block buying.
- **Safety**: Default is dry-run. Set `DRY_RUN=false` and `ALLOW_LIVE=true` in `.env` to enable live trading. Min order size and cooldown between orders apply.

## Data

The bot writes `portfolio_state.json` (initial value when tracking started) and `portfolio_log.csv` (one row per tick: timestamp, usd, doge, price, portfolio_value_usd, gain_usd, gain_pct). The CSV grows by about one row per poll (e.g. ~1440 rows per day at 60s). For long-running 24/7 use, archive or trim the file periodically if needed.

## Running 24/7

Run inside a terminal multiplexer (e.g. `screen` or `tmux`) or a process manager (e.g. systemd, supervisor) so the bot keeps running across disconnects and reboots.

## Disclaimer

Trading cryptocurrency is risky. Past backtest or paper results do not guarantee future profit. Use at your own risk.
