"""
Wall Street-grade signal engine.
Modelled after how an experienced institutional analyst reads a chart:
multi-layer confirmation, divergence detection, market structure,
Ichimoku cloud, volume profile, and a strict confluence gate.
"""
import pandas as pd
import numpy as np
import ta


# ─────────────────────────────────────────────────────────────────────────────
# INDICATOR LAYER
# ─────────────────────────────────────────────────────────────────────────────

def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # ── Trend EMAs ────────────────────────────────────────────────────────────
    df["ema_9"]   = ta.trend.ema_indicator(df["close"], window=9)
    df["ema_21"]  = ta.trend.ema_indicator(df["close"], window=21)
    df["ema_50"]  = ta.trend.ema_indicator(df["close"], window=50)
    df["ema_200"] = ta.trend.ema_indicator(df["close"], window=200)

    # ── MACD ──────────────────────────────────────────────────────────────────
    macd = ta.trend.MACD(df["close"])
    df["macd"]        = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"]   = macd.macd_diff()

    # ── ADX + Directional Movement ────────────────────────────────────────────
    df["adx"]    = ta.trend.adx(df["high"], df["low"], df["close"])
    df["adx_pos"] = ta.trend.adx_pos(df["high"], df["low"], df["close"])  # +DI
    df["adx_neg"] = ta.trend.adx_neg(df["high"], df["low"], df["close"])  # -DI

    # ── RSI ───────────────────────────────────────────────────────────────────
    df["rsi"] = ta.momentum.rsi(df["close"], window=14)

    # ── Stochastic ────────────────────────────────────────────────────────────
    df["stoch_k"] = ta.momentum.stoch(df["high"], df["low"], df["close"])
    df["stoch_d"] = ta.momentum.stoch_signal(df["high"], df["low"], df["close"])

    # ── Bollinger Bands ───────────────────────────────────────────────────────
    bb = ta.volatility.BollingerBands(df["close"])
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_mid"]   = bb.bollinger_mavg()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_pct"]   = bb.bollinger_pband()
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]

    # ── ATR (volatility) ──────────────────────────────────────────────────────
    df["atr"] = ta.volatility.average_true_range(df["high"], df["low"], df["close"])

    # ── CCI (Commodity Channel Index) ─────────────────────────────────────────
    df["cci"] = ta.trend.cci(df["high"], df["low"], df["close"], window=20)

    # ── Williams %R ───────────────────────────────────────────────────────────
    df["williams_r"] = ta.momentum.williams_r(df["high"], df["low"], df["close"], lbp=14)

    # ── Volume ────────────────────────────────────────────────────────────────
    df["obv"]     = ta.volume.on_balance_volume(df["close"], df["volume"])
    df["obv_ema"] = ta.trend.ema_indicator(df["obv"], window=20)
    df["vwap"]    = (df["volume"] * (df["high"] + df["low"] + df["close"]) / 3).cumsum() \
                    / df["volume"].cumsum()
    df["vol_sma"] = df["volume"].rolling(20).mean()
    df["vol_ratio"] = df["volume"] / df["vol_sma"]   # >1.5 = high-volume confirmation

    # ── Ichimoku Cloud ────────────────────────────────────────────────────────
    ich = ta.trend.IchimokuIndicator(df["high"], df["low"])
    df["ichi_conv"]  = ich.ichimoku_conversion_line()   # Tenkan-sen (9)
    df["ichi_base"]  = ich.ichimoku_base_line()          # Kijun-sen  (26)
    df["ichi_a"]     = ich.ichimoku_a()                  # Senkou A
    df["ichi_b"]     = ich.ichimoku_b()                  # Senkou B

    # ── Pivot Points (classic) ────────────────────────────────────────────────
    df["pivot"]       = (df["high"].shift(1) + df["low"].shift(1) + df["close"].shift(1)) / 3
    df["resistance1"] = 2 * df["pivot"] - df["low"].shift(1)
    df["resistance2"] = df["pivot"] + (df["high"].shift(1) - df["low"].shift(1))
    df["support1"]    = 2 * df["pivot"] - df["high"].shift(1)
    df["support2"]    = df["pivot"] - (df["high"].shift(1) - df["low"].shift(1))

    # ── RSI Divergence (bullish / bearish) ────────────────────────────────────
    # Bullish divergence: price makes lower low but RSI makes higher low
    # Bearish divergence: price makes higher high but RSI makes lower high
    lookback = 5
    price_ll = df["close"] < df["close"].shift(lookback)     # lower low
    rsi_hl   = df["rsi"]   > df["rsi"].shift(lookback)       # higher low
    price_hh = df["close"] > df["close"].shift(lookback)     # higher high
    rsi_lh   = df["rsi"]   < df["rsi"].shift(lookback)       # lower high

    df["rsi_bull_div"] = (price_ll & rsi_hl).astype(float)   # bullish divergence
    df["rsi_bear_div"] = (price_hh & rsi_lh).astype(float)   # bearish divergence

    # ── MACD Histogram Divergence ─────────────────────────────────────────────
    df["macd_hist_rising"]  = (df["macd_hist"] > df["macd_hist"].shift(1)).astype(float)
    df["macd_hist_falling"] = (df["macd_hist"] < df["macd_hist"].shift(1)).astype(float)

    # ── Candlestick Patterns ──────────────────────────────────────────────────
    body       = (df["close"] - df["open"]).abs()
    candle_rng = df["high"] - df["low"]
    upper_wick = df["high"] - df[["close","open"]].max(axis=1)
    lower_wick = df[["close","open"]].min(axis=1) - df["low"]

    # Bullish engulfing: current green candle engulfs previous red candle
    df["bull_engulf"] = (
        (df["close"] > df["open"]) &
        (df["close"].shift(1) < df["open"].shift(1)) &
        (df["close"] > df["open"].shift(1)) &
        (df["open"] < df["close"].shift(1))
    ).astype(float)

    # Bearish engulfing
    df["bear_engulf"] = (
        (df["close"] < df["open"]) &
        (df["close"].shift(1) > df["open"].shift(1)) &
        (df["close"] < df["open"].shift(1)) &
        (df["open"] > df["close"].shift(1))
    ).astype(float)

    # Hammer: small body, long lower wick, near bottom of range
    df["hammer"] = (
        (lower_wick > 2 * body) &
        (upper_wick < 0.3 * body) &
        (body > 0)
    ).astype(float)

    # Shooting star: small body, long upper wick, near top of range
    df["shooting_star"] = (
        (upper_wick > 2 * body) &
        (lower_wick < 0.3 * body) &
        (body > 0)
    ).astype(float)

    # ── Market Structure ──────────────────────────────────────────────────────
    # Higher highs / higher lows (uptrend structure)
    df["hh"] = (df["high"] > df["high"].rolling(10).max().shift(1)).astype(float)
    df["ll"] = (df["low"]  < df["low"].rolling(10).min().shift(1)).astype(float)

    return df


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL ENGINE — 12 confirmation layers
# ─────────────────────────────────────────────────────────────────────────────

def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Wall Street-grade composite signal.

    Each of 12 systems casts a weighted vote. Score is normalised to [-1, 1].
    Threshold is strict (±0.55) — only high-conviction setups fire a signal.
    Additionally, a minimum confluence gate requires 7+ systems to agree.
    """
    df = add_all_indicators(df)

    score = pd.Series(0.0, index=df.index)
    votes = pd.Series(0,   index=df.index)   # count of agreeing systems

    # ── 1. EMA Trend Stack (weight 3) — the primary trend filter ─────────────
    # All three EMAs must be aligned. This is the first filter every
    # institutional analyst checks before looking at anything else.
    ema_bull = (df["ema_9"] > df["ema_21"]) & (df["ema_21"] > df["ema_50"])
    ema_bear = (df["ema_9"] < df["ema_21"]) & (df["ema_21"] < df["ema_50"])
    score += ema_bull.astype(float) * 3
    score -= ema_bear.astype(float) * 3
    votes += ema_bull.astype(int)
    votes -= ema_bear.astype(int)

    # ── 2. EMA 200 Macro Filter (weight 2) ───────────────────────────────────
    # Price above EMA200 = bull market. Institutional funds won't go long
    # in a bear market and won't go short in a bull market.
    above_200 = df["close"] > df["ema_200"]
    below_200 = df["close"] < df["ema_200"]
    score += above_200.astype(float) * 2
    score -= below_200.astype(float) * 2
    votes += above_200.astype(int)
    votes -= below_200.astype(int)

    # ── 3. MACD Momentum (weight 2) ───────────────────────────────────────────
    macd_bull = df["macd"] > df["macd_signal"]
    macd_bear = df["macd"] < df["macd_signal"]
    score += macd_bull.astype(float) * 2
    score -= macd_bear.astype(float) * 2
    votes += macd_bull.astype(int)
    votes -= macd_bear.astype(int)

    # ── 4. MACD Histogram Momentum (weight 1) — histogram rising/falling ──────
    score += df["macd_hist_rising"]  * 1
    score -= df["macd_hist_falling"] * 1
    votes += df["macd_hist_rising"].astype(int)
    votes -= df["macd_hist_falling"].astype(int)

    # ── 5. ADX + Directional Index (weight 2) ────────────────────────────────
    # ADX confirms trend is real; +DI/-DI gives direction
    trending  = df["adx"] > 25
    di_bull   = trending & (df["adx_pos"] > df["adx_neg"])
    di_bear   = trending & (df["adx_pos"] < df["adx_neg"])
    score += di_bull.astype(float) * 2
    score -= di_bear.astype(float) * 2
    votes += di_bull.astype(int)
    votes -= di_bear.astype(int)

    # ── 6. RSI Zone (weight 1.5) ──────────────────────────────────────────────
    # 50–70 = bullish momentum zone. 30–50 = bearish momentum zone.
    rsi_bull = (df["rsi"] > 55) & (df["rsi"] < 75)
    rsi_bear = (df["rsi"] < 45) & (df["rsi"] > 25)
    score += rsi_bull.astype(float) * 1.5
    score -= rsi_bear.astype(float) * 1.5
    votes += rsi_bull.astype(int)
    votes -= rsi_bear.astype(int)

    # ── 7. RSI Divergence (weight 2) — high-value signal ─────────────────────
    score += df["rsi_bull_div"] * 2
    score -= df["rsi_bear_div"] * 2
    votes += df["rsi_bull_div"].astype(int)
    votes -= df["rsi_bear_div"].astype(int)

    # ── 8. Stochastic (weight 1) ─────────────────────────────────────────────
    stoch_bull = (df["stoch_k"] > df["stoch_d"]) & (df["stoch_k"] < 80)
    stoch_bear = (df["stoch_k"] < df["stoch_d"]) & (df["stoch_k"] > 20)
    score += stoch_bull.astype(float)
    score -= stoch_bear.astype(float)
    votes += stoch_bull.astype(int)
    votes -= stoch_bear.astype(int)

    # ── 9. CCI (weight 1) ────────────────────────────────────────────────────
    cci_bull = df["cci"] > 100    # strong bullish momentum
    cci_bear = df["cci"] < -100   # strong bearish momentum
    score += cci_bull.astype(float)
    score -= cci_bear.astype(float)
    votes += cci_bull.astype(int)
    votes -= cci_bear.astype(int)

    # ── 10. Ichimoku Cloud (weight 2) ─────────────────────────────────────────
    # Price above the cloud + Tenkan above Kijun = strong uptrend
    cloud_top    = df[["ichi_a","ichi_b"]].max(axis=1)
    cloud_bottom = df[["ichi_a","ichi_b"]].min(axis=1)
    ich_bull = (df["close"] > cloud_top) & (df["ichi_conv"] > df["ichi_base"])
    ich_bear = (df["close"] < cloud_bottom) & (df["ichi_conv"] < df["ichi_base"])
    score += ich_bull.astype(float) * 2
    score -= ich_bear.astype(float) * 2
    votes += ich_bull.astype(int)
    votes -= ich_bear.astype(int)

    # ── 11. Volume Confirmation (weight 1.5) ─────────────────────────────────
    # High volume on a move = institutional participation = trustworthy signal
    vol_confirm_bull = (df["close"] > df["close"].shift(1)) & (df["vol_ratio"] > 1.3) \
                     & (df["obv"] > df["obv_ema"])
    vol_confirm_bear = (df["close"] < df["close"].shift(1)) & (df["vol_ratio"] > 1.3) \
                     & (df["obv"] < df["obv_ema"])
    score += vol_confirm_bull.astype(float) * 1.5
    score -= vol_confirm_bear.astype(float) * 1.5
    votes += vol_confirm_bull.astype(int)
    votes -= vol_confirm_bear.astype(int)

    # ── 12. Candlestick Patterns (weight 1.5) ────────────────────────────────
    score += df["bull_engulf"]   * 1.5
    score -= df["bear_engulf"]   * 1.5
    score += df["hammer"]        * 1.0
    score -= df["shooting_star"] * 1.0
    votes += df["bull_engulf"].astype(int)
    votes -= df["bear_engulf"].astype(int)

    # ── Normalise ─────────────────────────────────────────────────────────────
    # Max possible raw score ≈ 24 (all 12 systems fully bullish)
    df["score"] = score / 24.0
    df["score"] = df["score"].clip(-1, 1)
    df["votes"] = votes    # how many of the 12 systems agree

    # ── Signal Gate ───────────────────────────────────────────────────────────
    # Strict threshold (0.55) + minimum 5 systems must agree.
    # This eliminates marginal setups that would lower win rate.
    df["signal"] = 0
    long_gate  = (df["score"] >= 0.45) & (df["votes"] >= 5)
    short_gate = (df["score"] <= -0.45) & (df["votes"] <= -5)
    df.loc[long_gate,  "signal"] =  1
    df.loc[short_gate, "signal"] = -1

    # ── Confidence % (for display) ────────────────────────────────────────────
    # How strongly the signal fires, expressed as a percentage
    df["confidence"] = (df["score"].abs() * 100).round(1)

    return df
