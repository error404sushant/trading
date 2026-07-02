"""
Signal engine: 6-system scoring + CVD + OI precision filters.

Scoring:
  1. EMA 9/21/50 alignment  (weight 2)
  2. RSI zone 50-70 / 30-50 (weight 1)
  3. MACD crossover          (weight 1)
  4. ADX + DI direction      (weight 1)
  5. Bollinger Band position (weight 1)
  6. Stochastic crossover    (weight 1)
  7. CVD trend               (weight 1)  ← NEW
  Threshold: score >= +0.4 or <= -0.4

Precision filters (applied AFTER scoring):
  F1. EMA200 direction  — LONG only above EMA200, SHORT only below
  F2. RSI extreme veto  — no LONG above RSI 78, no SHORT below RSI 22
  F3. CVD divergence    — block signal when CVD contradicts price direction
  F4. OI confirmation   — for crypto: block weak signals when OI is falling
                          (falling OI = contracts closing = move losing steam)

CVD (Cumulative Volume Delta):
  Approximated from OHLCV using candle body position within the range.
  buy_pressure  = volume × (close − low)  / (high − low)
  sell_pressure = volume × (high − close) / (high − low)
  CVD = cumsum(buy_pressure − sell_pressure)
  Rising CVD = buyers dominating. Falling CVD = sellers dominating.

Open Interest (OI):
  Fetched from Binance Futures API for crypto (BTC, ETH, SOL, BNB, etc.)
  Rising OI + rising price  = new longs entering  → confirms LONG
  Rising OI + falling price = new shorts entering → confirms SHORT
  Falling OI = existing positions closing → weak/exhausted move → veto signal
"""
import pandas as pd
import numpy as np
import ta


def _compute_cvd(df: pd.DataFrame) -> pd.DataFrame:
    """
    CVD approximation from OHLCV.
    Uses the fraction of the candle range that close occupies above/below midpoint.
    """
    hl = (df["high"] - df["low"]).replace(0, np.nan)
    buy_vol  = df["volume"] * (df["close"] - df["low"])  / hl
    sell_vol = df["volume"] * (df["high"]  - df["close"]) / hl
    delta = (buy_vol - sell_vol).fillna(0)

    df["cvd"]       = delta.cumsum()
    df["cvd_ema"]   = ta.trend.ema_indicator(df["cvd"], window=20)
    df["cvd_slope"] = df["cvd"].diff(3)   # 3-bar momentum of CVD
    df["cvd_delta"] = delta                # single-bar delta
    return df


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

    # ── CVD ──────────────────────────────────────────────────────────────────
    df = _compute_cvd(df)

    return df


def generate_signals(df: pd.DataFrame, oi_series: pd.Series = None) -> pd.DataFrame:
    """
    oi_series: optional Open Interest series indexed by datetime (from Binance API).
               If provided, used as precision filter F4 for crypto.
    """
    df = add_all_indicators(df)

    # ── Merge OI if provided ──────────────────────────────────────────────────
    has_oi = False
    if oi_series is not None and not oi_series.empty:
        oi_aligned = oi_series.reindex(df.index, method="nearest", tolerance=pd.Timedelta("2d"))
        if oi_aligned.notna().sum() > 10:
            df["oi"]       = oi_aligned
            df["oi_ema"]   = ta.trend.ema_indicator(df["oi"].fillna(method="ffill"), window=10)
            df["oi_rising"] = (df["oi"] > df["oi_ema"]).astype(float)
            has_oi = True

    if not has_oi:
        df["oi"]        = np.nan
        df["oi_ema"]    = np.nan
        df["oi_rising"] = np.nan

    # ── 7-system score ────────────────────────────────────────────────────────
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

    # System 7: CVD trend (weight 1)
    cvd_bull = df["cvd"] > df["cvd_ema"]
    cvd_bear = df["cvd"] < df["cvd_ema"]
    score += cvd_bull.astype(float)
    score -= cvd_bear.astype(float)

    # Max raw score is now 9 (EMA×2 + 5×1 + CVD×1)
    df["score"] = (score / 9.0).clip(-1, 1)

    # ── Raw signal gate ───────────────────────────────────────────────────────
    df["signal"] = 0
    df.loc[df["score"] >= 0.4,  "signal"] =  1
    df.loc[df["score"] <= -0.4, "signal"] = -1

    # ── Filter 1: EMA200 macro direction ─────────────────────────────────────
    df.loc[(df["signal"] == 1)  & (df["close"] < df["ema_200"]), "signal"] = 0
    df.loc[(df["signal"] == -1) & (df["close"] > df["ema_200"]), "signal"] = 0

    # ── Filter 2: RSI extreme veto ────────────────────────────────────────────
    df.loc[(df["signal"] == 1)  & (df["rsi"] > 78), "signal"] = 0
    df.loc[(df["signal"] == -1) & (df["rsi"] < 22), "signal"] = 0

    # ── Filter 3: CVD divergence veto ────────────────────────────────────────
    # Price going up but CVD falling = smart money distributing → block LONG
    # Price going down but CVD rising = smart money accumulating → block SHORT
    price_up   = df["close"] > df["close"].shift(3)
    price_down = df["close"] < df["close"].shift(3)
    cvd_div_bear = price_up   & cvd_bear   # price rising, CVD falling → bearish divergence
    cvd_div_bull = price_down & cvd_bull   # price falling, CVD rising → bullish divergence
    df.loc[(df["signal"] == 1)  & cvd_div_bear, "signal"] = 0
    df.loc[(df["signal"] == -1) & cvd_div_bull, "signal"] = 0

    # ── Filter 4: OI confirmation (crypto only) ───────────────────────────────
    # Only block when OI is clearly falling (contracts being closed = weak move)
    if has_oi:
        oi_falling = df["oi_rising"] == 0
        # Falling OI = market losing conviction → skip low-confidence signals
        low_conf = df["score"].abs() < 0.6
        df.loc[(df["signal"] != 0) & oi_falling & low_conf, "signal"] = 0

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
    votes += cvd_bull.astype(int);  votes -= cvd_bear.astype(int)
    df["votes"] = votes

    df["cat_a"] = ema_bull.astype(float) - ema_bear.astype(float)
    df["cat_b"] = (df["macd"] > df["macd_signal"]).astype(float) - \
                  (df["macd"] < df["macd_signal"]).astype(float)
    df["cat_c"] = (df["obv"] > df["obv_ema"]).astype(float) - \
                  (df["obv"] < df["obv_ema"]).astype(float)
    df["cat_d"] = cvd_bull.astype(float) - cvd_bear.astype(float)

    df["confidence"] = (df["score"].abs() * 100).round(1)
    return df
