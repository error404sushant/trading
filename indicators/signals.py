import pandas as pd
import numpy as np
import ta


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Trend
    df["ema_9"]  = ta.trend.ema_indicator(df["close"], window=9)
    df["ema_21"] = ta.trend.ema_indicator(df["close"], window=21)
    df["ema_50"] = ta.trend.ema_indicator(df["close"], window=50)
    df["ema_200"]= ta.trend.ema_indicator(df["close"], window=200)

    macd = ta.trend.MACD(df["close"])
    df["macd"]        = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"]   = macd.macd_diff()

    df["adx"] = ta.trend.adx(df["high"], df["low"], df["close"])

    # Momentum
    df["rsi"]  = ta.momentum.rsi(df["close"], window=14)
    df["stoch_k"] = ta.momentum.stoch(df["high"], df["low"], df["close"])
    df["stoch_d"] = ta.momentum.stoch_signal(df["high"], df["low"], df["close"])

    # Volatility
    bb = ta.volatility.BollingerBands(df["close"])
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_mid"]   = bb.bollinger_mavg()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_pct"]   = bb.bollinger_pband()
    df["atr"]      = ta.volatility.average_true_range(df["high"], df["low"], df["close"])

    # Volume
    df["obv"]  = ta.volume.on_balance_volume(df["close"], df["volume"])
    df["vwap"] = (df["volume"] * (df["high"] + df["low"] + df["close"]) / 3).cumsum() / df["volume"].cumsum()

    # Support / Resistance (rolling pivot)
    df["pivot"]      = (df["high"].shift(1) + df["low"].shift(1) + df["close"].shift(1)) / 3
    df["resistance1"]= 2 * df["pivot"] - df["low"].shift(1)
    df["support1"]   = 2 * df["pivot"] - df["high"].shift(1)

    return df


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Combine multiple indicators into a composite signal with score."""
    df = add_all_indicators(df)

    score = pd.Series(0.0, index=df.index)

    # EMA trend (+2 / -2)
    ema_bull = (df["ema_9"] > df["ema_21"]) & (df["ema_21"] > df["ema_50"])
    ema_bear = (df["ema_9"] < df["ema_21"]) & (df["ema_21"] < df["ema_50"])
    score += ema_bull.astype(float) * 2
    score -= ema_bear.astype(float) * 2

    # RSI zones (+1 / -1)
    score += ((df["rsi"] > 50) & (df["rsi"] < 70)).astype(float)
    score -= ((df["rsi"] < 50) & (df["rsi"] > 30)).astype(float)

    # MACD crossover (+1 / -1)
    score += (df["macd"] > df["macd_signal"]).astype(float)
    score -= (df["macd"] < df["macd_signal"]).astype(float)

    # ADX trend strength (+1 if trending)
    score += (df["adx"] > 25).astype(float)

    # Bollinger Band position (+1 / -1)
    score += (df["close"] > df["bb_mid"]).astype(float)
    score -= (df["close"] < df["bb_mid"]).astype(float)

    # Stochastic (+1 / -1)
    score += ((df["stoch_k"] > df["stoch_d"]) & (df["stoch_k"] < 80)).astype(float)
    score -= ((df["stoch_k"] < df["stoch_d"]) & (df["stoch_k"] > 20)).astype(float)

    # Normalize score to [-1, 1]
    df["score"] = score / 8.0

    df["signal"] = 0
    df.loc[df["score"] >= 0.4, "signal"] = 1   # BUY
    df.loc[df["score"] <= -0.4, "signal"] = -1  # SELL

    return df
