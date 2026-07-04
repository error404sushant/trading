import yfinance as yf
import pandas as pd
import requests


def get_live_price(ticker: str) -> dict:
    """Fetch current live price — fast, no historical data."""
    if ticker.endswith("-USDT"):
        ticker = ticker.replace("-USDT", "-USD")

    # If it is a crypto symbol, fetch from Binance Spot API for accurate and fast price info
    if ticker in _BINANCE_MAP:
        try:
            binance_symbol = _BINANCE_MAP[ticker]
            url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={binance_symbol}"
            r = requests.get(url, timeout=3)
            data = r.json()
            if "lastPrice" in data:
                price = float(data["lastPrice"])
                chg_pct = float(data["priceChangePercent"])
                prev = float(data.get("prevClosePrice", price / (1 + chg_pct / 100)))
                return {"price": price, "change_pct": chg_pct, "prev_close": prev}
        except Exception:
            pass  # Fallback to Yahoo Finance below

    try:
        tk = yf.Ticker(ticker)
        info = tk.fast_info
        price = info.last_price
        prev  = info.previous_close
        if price and prev:
            chg_pct = (price - prev) / prev * 100
        else:
            chg_pct = 0.0
        return {"price": price or 0.0, "change_pct": chg_pct, "prev_close": prev or 0.0}
    except Exception:
        # fallback: pull 1-min bar
        try:
            df = yf.download(ticker, period="1d", interval="1m", progress=False, auto_adjust=True)
            if not df.empty:
                price = float(df["Close"].iloc[-1])
                prev  = float(df["Close"].iloc[0])
                return {"price": price, "change_pct": (price-prev)/prev*100, "prev_close": prev}
        except Exception:
            pass
        return {"price": 0.0, "change_pct": 0.0, "prev_close": 0.0}


def fetch_ohlcv(ticker: str, interval: str = "1d", period: str = "2y") -> pd.DataFrame:
    """Fetch OHLCV data for any ticker via Yahoo Finance."""
    if ticker.endswith("-USDT"):
        ticker = ticker.replace("-USDT", "-USD")
    interval_map = {
        "1m": ("7d", "1m"),
        "5m": ("60d", "5m"),
        "15m": ("60d", "15m"),
        "30m": ("60d", "30m"),
        "1h": ("730d", "1h"),
        "4h": ("730d", "1h"),  # resample from 1h
        "1d": ("max", "1d"),
        "1w": ("max", "1wk"),
        "1M": ("max", "1mo"),
    }

    yf_period, yf_interval = interval_map.get(interval, ("max", "1d"))
    tk = yf.Ticker(ticker)
    df = tk.history(period=yf_period, interval=yf_interval, auto_adjust=True)

    if df.empty:
        raise ValueError(f"No data returned for {ticker}")

    df.index = pd.to_datetime(df.index, utc=True).tz_convert(None)
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = ["open", "high", "low", "close", "volume"]
    df.dropna(inplace=True)

    if interval == "4h":
        df = df.resample("4h").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        ).dropna()

    return df


# ── Binance symbol mapping ────────────────────────────────────────────────────
_BINANCE_MAP = {
    "BTC-USD": "BTCUSDT", "ETH-USD": "ETHUSDT", "SOL-USD": "SOLUSDT",
    "BNB-USD": "BNBUSDT", "XRP-USD": "XRPUSDT", "ADA-USD": "ADAUSDT",
    "DOGE-USD": "DOGEUSDT", "AVAX-USD": "AVAXUSDT", "MATIC-USD": "MATICUSDT",
    "DOT-USD": "DOTUSDT",
}

_INTERVAL_MAP_BINANCE = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "4h": "4h", "1d": "1d", "1w": "1w",
}


def fetch_open_interest(ticker: str, interval: str = "1d", limit: int = 500) -> pd.Series:
    """
    Fetch historical Open Interest from Binance Futures API.
    Returns a Series indexed by datetime. Returns empty Series for non-crypto.
    OI = total number of outstanding futures contracts (measures market conviction).
    """
    if ticker.endswith("-USDT"):
        ticker = ticker.replace("-USDT", "-USD")
    sym = _BINANCE_MAP.get(ticker)
    if not sym:
        return pd.Series(dtype=float)

    period_map = {
        "1m": "5m", "5m": "5m", "15m": "15m", "30m": "30m",
        "1h": "1h", "4h": "4h", "1d": "1d", "1w": "1d",
    }
    binance_period = period_map.get(interval, "1d")

    try:
        url = "https://fapi.binance.com/futures/data/openInterestHist"
        r = requests.get(url, params={
            "symbol": sym, "period": binance_period, "limit": limit
        }, timeout=8)
        data = r.json()
        if not isinstance(data, list) or not data:
            return pd.Series(dtype=float)

        oi = pd.Series(
            {pd.to_datetime(d["timestamp"], unit="ms"): float(d["sumOpenInterest"])
             for d in data}
        )
        oi.index = pd.to_datetime(oi.index).tz_localize(None)
        return oi.sort_index()
    except Exception:
        return pd.Series(dtype=float)
