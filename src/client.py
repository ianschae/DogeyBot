"""Thin wrapper around Coinbase REST client for DOGE-USD."""
import logging
import os
import time
from decimal import Decimal

from coinbase.rest import RESTClient

from . import config

logger = logging.getLogger(__name__)

# SIX_HOUR in seconds for closed-candle cutoff
GRANULARITY_SECONDS = {"SIX_HOUR": 6 * 3600, "ONE_DAY": 24 * 3600}


def _retry(fn, max_attempts: int = 3, delay_sec: float = 2):
    """Call fn(); on exception retry after delay_sec, then re-raise. No retry for orders."""
    last = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as e:
            last = e
            if attempt + 1 < max_attempts:
                time.sleep(delay_sec)
    raise last


def _client() -> RESTClient:
    if not config.COINBASE_API_KEY or not config.COINBASE_API_SECRET:
        raise ValueError("COINBASE_API_KEY and COINBASE_API_SECRET must be set")
    return RESTClient(
        api_key=config.COINBASE_API_KEY,
        api_secret=config.COINBASE_API_SECRET,
    )


def get_doge_and_usd_balances() -> tuple[Decimal, Decimal]:
    """Return (doge_available, usd_available) as Decimals. DOGE is base, USD is quote."""
    client = _client()

    def _fetch():
        return client.get_accounts()

    try:
        resp = _retry(_fetch)
    except Exception as e:
        logger.exception("Couldn't fetch accounts: %s", e)
        return Decimal("0"), Decimal("0")
    doge = Decimal("0")
    usd = Decimal("0")
    for acc in getattr(resp, "accounts", []) or []:
        currency = getattr(acc, "currency", None) if not isinstance(acc, dict) else acc.get("currency")
        if not currency:
            continue
        bal = getattr(acc, "available_balance", None) if not isinstance(acc, dict) else acc.get("available_balance")
        if bal is None:
            continue
        val = getattr(bal, "value", None) if not isinstance(bal, dict) else bal.get("value")
        if val is None:
            continue
        try:
            q = Decimal(str(val))
        except Exception:
            continue
        if currency == "DOGE":
            doge = q
        elif currency == "USD":
            usd = q
    return doge, usd


def get_current_price() -> float | None:
    """Fetch current DOGE-USD price from the product endpoint. Returns None on failure."""
    client = _client()

    def _fetch():
        return client.get_product(product_id=config.PRODUCT_ID)

    try:
        resp = _retry(_fetch)
    except Exception as e:
        logger.debug("Couldn't fetch current price: %s", e)
        return None
    price = getattr(resp, "price", None) if not isinstance(resp, dict) else resp.get("price")
    if price is None:
        return None
    try:
        return float(str(price))
    except (TypeError, ValueError):
        return None


def get_closed_candles(count: int = None) -> list[dict]:
    """Fetch DOGE-USD candles and return only closed ones, sorted ascending by time.
    Returns list of dicts with keys: start, open, high, low, close, volume.
    """
    count = count or config.CANDLES_COUNT
    client = _client()
    end_ts = int(time.time())
    granularity_sec = GRANULARITY_SECONDS.get(config.CANDLE_GRANULARITY, 6 * 3600)
    # Request enough range to get at least `count` candles; end before now so last candle is closed
    start_ts = end_ts - (count + 2) * granularity_sec
    start_str = str(start_ts)
    end_str = str(end_ts)

    def _fetch():
        return client.get_candles(
            product_id=config.PRODUCT_ID,
            start=start_str,
            end=end_str,
            granularity=config.CANDLE_GRANULARITY,
        )

    try:
        resp = _retry(_fetch)
    except Exception as e:
        logger.exception("Couldn't fetch candles: %s", e)
        return []
    out = _parse_candle_response(resp)
    # Only closed: candle's end = start + granularity_sec; must be < now
    cutoff = end_ts - granularity_sec
    out = [c for c in out if (c["start"] + granularity_sec) <= cutoff]
    out.sort(key=lambda c: c["start"])
    return out[-count:] if len(out) > count else out


def _parse_candle_response(resp) -> list[dict]:
    """Parse API candle response to list of dicts with start, open, high, low, close, volume."""
    raw = getattr(resp, "candles", None) or getattr(resp, "candle_list", None)
    if not raw and hasattr(resp, "to_dict"):
        d = resp.to_dict()
        raw = d.get("candles", d.get("candle_list", []))
    if not raw:
        return []
    out = []
    for c in raw:
        if hasattr(c, "start"):
            start = int(c.start) if c.start else 0
            open_ = str(getattr(c, "open", 0))
            high = str(getattr(c, "high", 0))
            low = str(getattr(c, "low", 0))
            close = str(getattr(c, "close", 0))
            volume = str(getattr(c, "volume", 0))
        else:
            start = int(c.get("start", 0))
            open_ = str(c.get("open", 0))
            high = str(c.get("high", 0))
            low = str(c.get("low", 0))
            close = str(c.get("close", 0))
            volume = str(c.get("volume", 0))
        out.append({"start": start, "open": open_, "high": high, "low": low, "close": close, "volume": volume})
    return out


def get_candles_range(start_ts: int, end_ts: int, granularity: str = "SIX_HOUR") -> list[dict]:
    """Fetch DOGE-USD candles for a time range. Returns list of dicts (start, open, high, low, close, volume) sorted ascending."""
    client = _client()

    def _fetch():
        return client.get_candles(
            product_id=config.PRODUCT_ID,
            start=str(start_ts),
            end=str(end_ts),
            granularity=granularity,
        )

    try:
        resp = _retry(_fetch)
    except Exception as e:
        logger.exception("Couldn't fetch price history: %s", e)
        return []
    out = _parse_candle_response(resp)
    out.sort(key=lambda c: c["start"])
    return out


def _order_id() -> str:
    """Unique order id to avoid exchange rejections from collision."""
    return f"doge-bot-{int(time.time() * 1000)}-{os.urandom(4).hex()}"


def market_buy_usd(quote_size_usd: str | Decimal) -> None:
    """Place market buy for DOGE using quote_size in USD (DOGE-USD pair)."""
    client = _client()
    client_order_id = _order_id()
    client.market_order_buy(
        client_order_id=client_order_id,
        product_id=config.PRODUCT_ID,
        quote_size=str(quote_size_usd),
    )
    logger.info("Placed buy order for %s USD.", quote_size_usd)


def market_sell_doge(base_size_doge: str | Decimal) -> None:
    """Place market sell for DOGE (base_size in DOGE)."""
    client = _client()
    client_order_id = _order_id()
    client.market_order_sell(
        client_order_id=client_order_id,
        product_id=config.PRODUCT_ID,
        base_size=str(base_size_doge),
    )
    logger.info("Placed sell order for %s DOGE.", base_size_doge)
