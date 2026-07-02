import yfinance as yf
import pandas as pd


def get_live_price(ticker: str) -> dict:
    """Fetch current live price — fast, no historical data."""
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
