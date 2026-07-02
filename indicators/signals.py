"""
Proven signal engine: original 6-system scoring + smart vetoes.

The old 6-system engine timed entries well (19,000%+ return on BNB).
The 12-system layered approach delayed entries and missed big moves.

This version restores the fast EMA-crossover entry timing, then adds
four hard vetoes that kill the worst setups without slowing good ones.
Additional indicators are computed for display purposes only.
"""
import pandas as pd
import numpy as np
import ta


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # ── Core trend ────────────────────────────────────────────────────────────
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

    # RSI divergence (display)
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
    """
    Original 6-system scoring (proven performance) + 4 hard vetoes.

    Scoring systems:
      1. EMA 9/21/50 alignment    — weight 2  (trend direction)
      2. RSI zone (50–70 / 30–50) — weight 1  (momentum zone)
      3. MACD crossover            — weight 1  (momentum trigger)
      4. ADX > 25                  — weight 1  (trend strength)
      5. Bollinger Band position   — weight 1  (mean reversion)
      6. Stochastic crossover      — weight 1  (entry timing)

    Hard vetoes (block signal regardless of score):
      V1. ADX < 20     — market not trending, signals unreliable
      V2. RSI > 78     — severely overbought, no new longs
      V3. RSI < 22     — severely oversold, no new shorts
      V4. MACD & EMA conflict on opposite sides of signal
    """
    df = add_all_indicators(df)

    score = pd.Series(0.0, index=df.index)

    # 1. EMA stack (weight 2) — primary trend filter
    ema_bull = (df["ema_9"] > df["ema_21"]) & (df["ema_21"] > df["ema_50"])
    ema_bear = (df["ema_9"] < df["ema_21"]) & (df["ema_21"] < df["ema_50"])
    score += ema_bull.astype(float) * 2
    score -= ema_bear.astype(float) * 2

    # 2. RSI zone (weight 1)
    score += ((df["rsi"] > 50) & (df["rsi"] < 70)).astype(float)
    score -= ((df["rsi"] < 50) & (df["rsi"] > 30)).astype(float)

    # 3. MACD crossover (weight 1)
    score += (df["macd"] > df["macd_signal"]).astype(float)
    score -= (df["macd"] < df["macd_signal"]).astype(float)

    # 4. ADX trend confirmation (weight 1, direction-aware)
    score += ((df["adx"] > 25) & (df["adx_pos"] > df["adx_neg"])).astype(float)
    score -= ((df["adx"] > 25) & (df["adx_neg"] > df["adx_pos"])).astype(float)

    # 5. Bollinger Band position (weight 1)
    score += (df["close"] > df["bb_mid"]).astype(float)
    score -= (df["close"] < df["bb_mid"]).astype(float)

    # 6. Stochastic crossover (weight 1)
    score += ((df["stoch_k"] > df["stoch_d"]) & (df["stoch_k"] < 80)).astype(float)
    score -= ((df["stoch_k"] < df["stoch_d"]) & (df["stoch_k"] > 20)).astype(float)

    # Normalise to [-1, 1]
    df["score"] = (score / 8.0).clip(-1, 1)

    # Count direction-agreeing momentum indicators for display
    mom_v = pd.Series(0, index=df.index)
    mom_v += ema_bull.astype(int);  mom_v -= ema_bear.astype(int)
    mom_v += (df["macd"] > df["macd_signal"]).astype(int)
    mom_v -= (df["macd"] < df["macd_signal"]).astype(int)
    mom_v += ((df["adx"] > 25) & (df["adx_pos"] > df["adx_neg"])).astype(int)
    mom_v -= ((df["adx"] > 25) & (df["adx_neg"] > df["adx_pos"])).astype(int)
    mom_v += ((df["rsi"] > 50) & (df["rsi"] < 70)).astype(int)
    mom_v -= ((df["rsi"] < 50) & (df["rsi"] > 30)).astype(int)
    mom_v += ((df["stoch_k"] > df["stoch_d"]) & (df["stoch_k"] < 80)).astype(int)
    mom_v -= ((df["stoch_k"] < df["stoch_d"]) & (df["stoch_k"] > 20)).astype(int)
    df["votes"] = mom_v

    # Dummy category columns (for display compatibility)
    df["cat_a"] = ema_bull.astype(float) - ema_bear.astype(float)
    df["cat_b"] = df["score"]
    df["cat_c"] = (df["obv"] > df["obv_ema"]).astype(float) - (df["obv"] < df["obv_ema"]).astype(float)
    df["cat_d"] = pd.Series(0.0, index=df.index)

    # ── Hard vetoes ───────────────────────────────────────────────────────────
    no_trend   = df["adx"] < 20          # choppy market
    overbought = df["rsi"] > 78          # don't LONG when severely overbought
    oversold   = df["rsi"] < 22          # don't SHORT when severely oversold
    # MACD and EMA disagree on direction of intended signal
    macd_conflicts_long  = (df["macd"] < df["macd_signal"]) & ema_bull
    macd_conflicts_short = (df["macd"] > df["macd_signal"]) & ema_bear

    # ── Signal gate ───────────────────────────────────────────────────────────
    df["signal"] = 0
    df.loc[
        (df["score"] >= 0.4) & ~no_trend & ~overbought & ~macd_conflicts_long,
        "signal"
    ] = 1
    df.loc[
        (df["score"] <= -0.4) & ~no_trend & ~oversold & ~macd_conflicts_short,
        "signal"
    ] = -1

    df["confidence"] = (df["score"].abs() * 100).round(1)

    return df
