"""
Proven 6-system signal engine + two precision filters.

Scoring (same as original — timing is excellent):
  1. EMA 9/21/50 alignment  (weight 2)
  2. RSI zone 50-70 / 30-50 (weight 1)
  3. MACD crossover          (weight 1)
  4. ADX + DI direction      (weight 1)
  5. Bollinger Band position (weight 1)
  6. Stochastic crossover    (weight 1)
  Threshold: score >= +0.4 or <= -0.4

Precision filters applied AFTER scoring:
  F1. EMA200 direction — LONG only above EMA200, SHORT only below.
      Stops trading against the macro trend (biggest source of losses).
  F2. RSI extreme veto — no LONG above RSI 78, no SHORT below RSI 22.
      Avoids entering when price is maximally stretched.

All Wall Street indicators computed for the dashboard display.
"""
import pandas as pd
import numpy as np
import ta


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["ema_9"]   = ta.trend.ema_indicator(df["close"], window=9)
    df["ema_21"]  = ta.trend.ema_indicator(df["close"], window=21)
    df["ema_50"]  = ta.trend.ema_indicator(df["close"], window=50)
    df["ema_200"] = ta.trend.ema_indicator(df["close"], window=200)

    macd = ta.trend.MACD(df["close"])
    df["macd"]        = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"]   = macd.macd_diff()

    df["adx"]     = ta.trend.adx(df["high"], df["low"], df["close"])
    df["adx_pos"] = ta.trend.adx_pos(df["high"], df["low"], df["close"])
    df["adx_neg"] = ta.trend.adx_neg(df["high"], df["low"], df["close"])

    df["rsi"]     = ta.momentum.rsi(df["close"], window=14)
    df["stoch_k"] = ta.momentum.stoch(df["high"], df["low"], df["close"])
    df["stoch_d"] = ta.momentum.stoch_signal(df["high"], df["low"], df["close"])

    bb = ta.volatility.BollingerBands(df["close"])
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_mid"]   = bb.bollinger_mavg()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_pct"]   = bb.bollinger_pband()
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]

    df["atr"]        = ta.volatility.average_true_range(df["high"], df["low"], df["close"])
    df["atr_pct"]    = df["atr"] / df["close"] * 100
    df["cci"]        = ta.trend.cci(df["high"], df["low"], df["close"], window=20)
    df["williams_r"] = ta.momentum.williams_r(df["high"], df["low"], df["close"], lbp=14)

    df["obv"]       = ta.volume.on_balance_volume(df["close"], df["volume"])
    df["obv_ema"]   = ta.trend.ema_indicator(df["obv"], window=20)
    df["vol_sma"]   = df["volume"].rolling(20).mean()
    df["vol_ratio"] = df["volume"] / df["vol_sma"]
    df["vwap"]      = (df["volume"] * (df["high"] + df["low"] + df["close"]) / 3).cumsum() \
                      / df["volume"].cumsum()

    ich = ta.trend.IchimokuIndicator(df["high"], df["low"])
    df["ichi_conv"] = ich.ichimoku_conversion_line()
    df["ichi_base"] = ich.ichimoku_base_line()
    df["ichi_a"]    = ich.ichimoku_a()
    df["ichi_b"]    = ich.ichimoku_b()

    df["pivot"]       = (df["high"].shift(1) + df["low"].shift(1) + df["close"].shift(1)) / 3
    df["resistance1"] = 2 * df["pivot"] - df["low"].shift(1)
    df["resistance2"] = df["pivot"] + (df["high"].shift(1) - df["low"].shift(1))
    df["support1"]    = 2 * df["pivot"] - df["high"].shift(1)
    df["support2"]    = df["pivot"] - (df["high"].shift(1) - df["low"].shift(1))

    lb = 10
    df["rsi_bull_div"] = (
        (df["close"] < df["close"].shift(lb)) & (df["rsi"] > df["rsi"].shift(lb))
    ).astype(float)
    df["rsi_bear_div"] = (
        (df["close"] > df["close"].shift(lb)) & (df["rsi"] < df["rsi"].shift(lb))
    ).astype(float)

    body       = (df["close"] - df["open"]).abs()
    upper_wick = df["high"] - df[["close","open"]].max(axis=1)
    lower_wick = df[["close","open"]].min(axis=1) - df["low"]
    df["bull_engulf"] = (
        (df["close"] > df["open"]) & (df["close"].shift(1) < df["open"].shift(1)) &
        (df["close"] > df["open"].shift(1)) & (df["open"] < df["close"].shift(1))
    ).astype(float)
    df["bear_engulf"] = (
        (df["close"] < df["open"]) & (df["close"].shift(1) > df["open"].shift(1)) &
        (df["close"] < df["open"].shift(1)) & (df["open"] > df["close"].shift(1))
    ).astype(float)
    df["hammer"]        = ((lower_wick > 2*body) & (upper_wick < 0.5*body) & (body > 0)).astype(float)
    df["shooting_star"] = ((upper_wick > 2*body) & (lower_wick < 0.5*body) & (body > 0)).astype(float)

    return df


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    df = add_all_indicators(df)

    # ── 6-system score ────────────────────────────────────────────────────────
    score = pd.Series(0.0, index=df.index)

    ema_bull = (df["ema_9"] > df["ema_21"]) & (df["ema_21"] > df["ema_50"])
    ema_bear = (df["ema_9"] < df["ema_21"]) & (df["ema_21"] < df["ema_50"])
    score += ema_bull.astype(float) * 2
    score -= ema_bear.astype(float) * 2

    score += ((df["rsi"] > 50) & (df["rsi"] < 70)).astype(float)
    score -= ((df["rsi"] < 50) & (df["rsi"] > 30)).astype(float)

    score += (df["macd"] > df["macd_signal"]).astype(float)
    score -= (df["macd"] < df["macd_signal"]).astype(float)

    adx_bull = (df["adx"] > 25) & (df["adx_pos"] > df["adx_neg"])
    adx_bear = (df["adx"] > 25) & (df["adx_neg"] > df["adx_pos"])
    score += adx_bull.astype(float)
    score -= adx_bear.astype(float)

    score += (df["close"] > df["bb_mid"]).astype(float)
    score -= (df["close"] < df["bb_mid"]).astype(float)

    score += ((df["stoch_k"] > df["stoch_d"]) & (df["stoch_k"] < 80)).astype(float)
    score -= ((df["stoch_k"] < df["stoch_d"]) & (df["stoch_k"] > 20)).astype(float)

    df["score"] = (score / 8.0).clip(-1, 1)

    # ── Raw signals ───────────────────────────────────────────────────────────
    df["signal"] = 0
    df.loc[df["score"] >= 0.4,  "signal"] =  1
    df.loc[df["score"] <= -0.4, "signal"] = -1

    # ── Precision filter 1: EMA200 macro direction ────────────────────────────
    # This is the single most impactful improvement:
    # fighting the macro trend is the #1 cause of losing trades.
    df.loc[(df["signal"] == 1)  & (df["close"] < df["ema_200"]), "signal"] = 0
    df.loc[(df["signal"] == -1) & (df["close"] > df["ema_200"]), "signal"] = 0

    # ── Precision filter 2: RSI extreme veto ─────────────────────────────────
    # Price already stretched to extremes — odds of continuation worse than reversal.
    df.loc[(df["signal"] == 1)  & (df["rsi"] > 78), "signal"] = 0
    df.loc[(df["signal"] == -1) & (df["rsi"] < 22), "signal"] = 0

    # ── Votes + display columns ───────────────────────────────────────────────
    votes = pd.Series(0, index=df.index)
    votes += ema_bull.astype(int);  votes -= ema_bear.astype(int)
    votes += (df["macd"] > df["macd_signal"]).astype(int)
    votes -= (df["macd"] < df["macd_signal"]).astype(int)
    votes += adx_bull.astype(int);  votes -= adx_bear.astype(int)
    votes += ((df["rsi"] > 50) & (df["rsi"] < 70)).astype(int)
    votes -= ((df["rsi"] < 50) & (df["rsi"] > 30)).astype(int)
    votes += ((df["stoch_k"] > df["stoch_d"]) & (df["stoch_k"] < 80)).astype(int)
    votes -= ((df["stoch_k"] < df["stoch_d"]) & (df["stoch_k"] > 20)).astype(int)
    df["votes"] = votes

    df["cat_a"] = ema_bull.astype(float) - ema_bear.astype(float)
    df["cat_b"] = (df["macd"] > df["macd_signal"]).astype(float) - \
                  (df["macd"] < df["macd_signal"]).astype(float)
    df["cat_c"] = (df["obv"] > df["obv_ema"]).astype(float) - \
                  (df["obv"] < df["obv_ema"]).astype(float)
    df["cat_d"] = pd.Series(0.0, index=df.index)

    df["confidence"] = (df["score"].abs() * 100).round(1)
    return df
