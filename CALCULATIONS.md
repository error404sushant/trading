# Trading Platform — Complete Technical Reference

This document explains every calculation in the platform: from raw price data to the final LONG/SHORT signal, backtest metrics, optimizer, trade persistence, and the screener notification system.

---

## 1. Price Data

**Source:** Yahoo Finance via `yfinance`  
**File:** `data/fetcher.py`

Each candle (bar) has five values:

| Field | Meaning |
|---|---|
| `open` | Price at the start of the candle |
| `high` | Highest price during the candle |
| `low` | Lowest price during the candle |
| `close` | Price at the end of the candle |
| `volume` | Number of shares/units traded |

**Live price** uses `yf.Ticker.fast_info.last_price` — the real-time last traded price, not a stale candle close. Falls back to the latest 1-minute bar if fast_info fails.

**Timeframe mapping:**

| UI Timeframe | Yahoo Finance interval | Max history |
|---|---|---|
| 1m | 1m | 7 days |
| 5m / 15m / 30m | 5m / 15m / 30m | 60 days |
| 1h / 4h | 1h (4h resampled) | 730 days |
| 1d | 1d | Max available |
| 1w | 1wk | Max available |
| 1M | 1mo | Max available |

---

## 2. Wall Street Signal Engine — 12 Systems

**File:** `indicators/signals.py`  
**Function:** `generate_signals(df)`

The platform uses **12 independent analytical systems**, each weighted by importance. Every system casts a directional vote (+bull / −bear). The composite score is normalised to [−1, +1].

**Signal fires only when:** score ≥ ±0.45 **AND** at least 5 of 12 systems agree.

---

### System 1 — EMA Trend Stack (Weight: 3)

The single most important filter. All three short-to-medium EMAs must be aligned before any signal is considered.

```
EMA(today) = close(today) × k + EMA(yesterday) × (1 − k)
k = 2 / (window + 1)
```

| EMA | Window | Role |
|---|---|---|
| EMA 9 | 9 bars | Short-term momentum |
| EMA 21 | 21 bars | Medium-term trend |
| EMA 50 | 50 bars | Primary trend direction |

```
BULL: EMA9 > EMA21 > EMA50  →  +3
BEAR: EMA9 < EMA21 < EMA50  →  −3
```

---

### System 2 — EMA 200 Macro Regime Filter (Weight: 2)

Institutional funds track this line. Above it = bull market. Below = bear market. This filter prevents taking longs in a bear market or shorts in a bull market.

```
BULL: close > EMA200  →  +2
BEAR: close < EMA200  →  −2
```

---

### System 3 — MACD Momentum Crossover (Weight: 2)

Measures how fast the trend is accelerating or decelerating.

```
MACD Line   = EMA(12) − EMA(26)
Signal Line = EMA(9) of MACD Line
Histogram   = MACD Line − Signal Line
```

```
BULL: MACD Line > Signal Line  →  +2
BEAR: MACD Line < Signal Line  →  −2
```

---

### System 4 — MACD Histogram Direction (Weight: 1)

The histogram shows momentum acceleration. A rising histogram means the trend is gaining strength even before the MACD crossover completes.

```
BULL: histogram(today) > histogram(yesterday)  →  +1
BEAR: histogram(today) < histogram(yesterday)  →  −1
```

---

### System 5 — ADX + Directional Index (Weight: 2)

ADX measures trend strength; +DI and −DI give direction. This combination tells you **both** that the market is trending AND which way.

```
+DM = high − previous_high  (if positive, else 0)
−DM = previous_low − low    (if positive, else 0)
TR  = max(high−low, |high−prev_close|, |low−prev_close|)

+DI = 100 × EMA(+DM, 14) / ATR(14)
−DI = 100 × EMA(−DM, 14) / ATR(14)
ADX = EMA(|+DI − −DI| / (+DI + −DI), 14) × 100
```

```
BULL: ADX > 25 AND +DI > −DI  →  +2
BEAR: ADX > 25 AND −DI > +DI  →  −2
No trend (ADX < 25): 0 vote
```

ADX < 20 = choppy market; signals from other systems are ignored.

---

### System 6 — RSI Zone (Weight: 1.5)

Measures whether momentum is in a bullish or bearish zone (not just overbought/oversold extremes).

```
Average Gain = mean of 14-bar gains
Average Loss = mean of 14-bar losses
RSI = 100 − (100 / (1 + Average Gain / Average Loss))
```

```
BULL: RSI 55–75  →  +1.5   (bullish momentum, not yet extreme)
BEAR: RSI 25–45  →  −1.5   (bearish momentum, not yet extreme)
Neutral (40–60): 0 vote
```

---

### System 7 — RSI Divergence (Weight: 2)

One of the highest-value signals used by professional analysts. Divergence between price and RSI often precedes major reversals.

```
lookback = 5 bars

Bullish divergence:
  price makes lower low (close < close[5])
  RSI makes higher low  (rsi  > rsi[5])
  → Sellers losing strength while price drops  →  +2

Bearish divergence:
  price makes higher high (close > close[5])
  RSI makes lower high    (rsi  < rsi[5])
  → Buyers losing strength while price rises  →  −2
```

---

### System 8 — Stochastic Oscillator (Weight: 1)

Shows where price sits within its recent range. More sensitive than RSI for short-term momentum shifts.

```
%K = (close − lowest_low_14) / (highest_high_14 − lowest_low_14) × 100
%D = 3-bar SMA of %K
```

```
BULL: %K > %D AND %K < 80  →  +1
BEAR: %K < %D AND %K > 20  →  −1
```

---

### System 9 — CCI (Commodity Channel Index) (Weight: 1)

Measures how far price has deviated from its statistical average. Used by institutional commodity and futures traders.

```
Typical Price = (high + low + close) / 3
Mean TP       = SMA(Typical Price, 20)
Mean Dev      = mean(|Typical Price − Mean TP|, 20)
CCI           = (Typical Price − Mean TP) / (0.015 × Mean Dev)
```

```
BULL: CCI > +100  →  +1   (strong bullish momentum)
BEAR: CCI < −100  →  −1   (strong bearish momentum)
```

---

### System 10 — Ichimoku Cloud (Weight: 2)

A complete trading system from Japan used by institutional traders worldwide. Combines five lines into a "cloud" that acts as dynamic support/resistance.

```
Tenkan-sen (Conversion): (highest_high_9 + lowest_low_9) / 2
Kijun-sen  (Base):       (highest_high_26 + lowest_low_26) / 2
Senkou A:                (Tenkan + Kijun) / 2  (plotted 26 bars ahead)
Senkou B:                (highest_high_52 + lowest_low_52) / 2  (26 bars ahead)

Cloud Top    = max(Senkou A, Senkou B)
Cloud Bottom = min(Senkou A, Senkou B)
```

```
BULL: close > Cloud Top  AND  Tenkan > Kijun  →  +2
BEAR: close < Cloud Bottom  AND  Tenkan < Kijun  →  −2
In cloud: 0 vote (uncertain)
```

---

### System 11 — Volume Confirmation (Weight: 1.5)

Institutional moves are always backed by volume. A price move on weak volume is suspect; on strong volume it's trustworthy.

```
Volume SMA  = SMA(volume, 20)
Volume Ratio = volume / Volume SMA        (>1.0 = above average)

OBV (On-Balance Volume):
  If close > prev_close: OBV += volume
  If close < prev_close: OBV -= volume
OBV EMA = EMA(OBV, 20)
```

```
BULL: close > prev_close  AND  vol_ratio > 1.3  AND  OBV > OBV_EMA  →  +1.5
BEAR: close < prev_close  AND  vol_ratio > 1.3  AND  OBV < OBV_EMA  →  −1.5
```

High volume on the wrong side of the trade is a red flag.

---

### System 12 — Candlestick Patterns (Weight: 1–1.5)

Price action patterns that reflect the psychology of buyers and sellers at key levels.

**Bullish Engulfing** (+1.5): A large green candle that completely wraps around the previous red candle. Shows buyers overwhelmed sellers.
```
current close > current open  (green)
previous close < previous open  (red)
current close > previous open
current open  < previous close
```

**Bearish Engulfing** (−1.5): Reverse of above. Sellers overwhelmed buyers.

**Hammer** (+1.0): Small body, long lower wick. Sellers tried to push price down but buyers stepped in hard.
```
lower_wick > 2 × body_size
upper_wick < 0.3 × body_size
```

**Shooting Star** (−1.0): Small body, long upper wick. Buyers tried to push price up but sellers slammed it back.

---

## 3. Signal Scoring & Gate

```
Raw score = sum of all 12 system votes (weighted)
Max possible raw score ≈ 24  (all systems fully bullish)

Normalised score = raw_score / 24.0   →   range [−1, +1]
Confidence %     = |score| × 100
Votes            = count of systems agreeing (positive = bullish, negative = bearish)
```

### Signal Gate (both conditions must be true):

| Direction | Score condition | Confluence condition |
|---|---|---|
| LONG | score ≥ +0.45 | votes ≥ +5 |
| SHORT | score ≤ −0.45 | votes ≤ −5 |
| NO SIGNAL | anything else | — |

This dual gate eliminates weak setups and requires a true majority of systems to agree before a trade is suggested.

### Confidence Levels:

| Confidence % | Label |
|---|---|
| 75%+ | Very High |
| 60–74% | High |
| 45–59% | Medium |
| < 45% | Low (no signal) |

---

## 4. Backtest Engine

**File:** `backtest/engine.py` → `run_backtest(df, stop_loss_pct, take_profit_pct)`

Simulates trading the strategy on all historical data, one candle at a time, with $10,000 starting capital.

```
For each candle (oldest → newest):

  IF in a trade:
    pnl_pct = (price − entry) / entry × 100 × direction
    (direction = +1 for LONG, −1 for SHORT)

    IF pnl_pct ≤ −stop_loss_pct   →  EXIT: Stop Loss Hit
    IF pnl_pct ≥ take_profit_pct  →  EXIT: Take Profit Hit
    IF signal flipped direction    →  EXIT: Signal Reversal

    On exit: capital × = (1 + pnl_pct / 100)

  IF not in trade AND signal = 1 or −1:
    Enter trade at current close price

  Append current capital to equity curve
```

---

## 5. Backtest Metrics

**File:** `backtest/engine.py` → `BacktestResult`

### Win Rate
```
Win Rate = wins / total_closed_trades × 100
```
Target: > 55%. At 1:2 R:R, you only need 34% to break even.

### Total Return
```
Total Return = (final_equity / 10000 − 1) × 100
```

### Max Drawdown
Worst peak-to-trough loss during the entire backtest period.
```
Rolling max = cumulative maximum of equity curve
Drawdown    = (equity − rolling_max) / rolling_max
Max Drawdown = min(drawdown) × 100
```
Target: better than −30%.

### Sharpe Ratio
Return per unit of risk. The standard benchmark for institutional strategies.
```
Daily returns = equity.pct_change()
Sharpe = (mean_return / std_return) × √252
```
- > 1.0 = Good  
- > 2.0 = Excellent  
- < 0 = Losing on risk-adjusted basis

### Profit Factor
```
Profit Factor = sum(winning_pnl) / |sum(losing_pnl)|
```
- > 1.0 = Overall profitable  
- > 1.5 = Good  
- > 2.0 = Excellent

### Average Win / Average Loss
```
Avg Win  = mean(pnl_pct for winning trades)
Avg Loss = mean(pnl_pct for losing trades)
```
Avg Win / |Avg Loss| should ideally exceed 1.5.

---

## 6. SL/TP Optimizer

**File:** `backtest/optimizer.py`

Grid search across 72 SL/TP combinations to find the best risk parameters for the current ticker and timeframe.

```
SL values: 0.5%, 1.0%, 1.5%, 2.0%, 2.5%, 3.0%, 4.0%, 5.0%  (8 values)
TP values: 1.5%, 2.0%, 3.0%, 4.0%, 5.0%, 6.0%, 8.0%, 10.0%, 12.0%  (9 values)

Filter: only test combinations where TP / SL ≥ 1.5  (minimum 1:1.5 R:R)
Filter: skip combinations with fewer than 5 trades

Scoring formula:
  sharpe_bonus = max(0, sharpe) / 10
  score = (win_rate / 100) × profit_factor × (1 + sharpe_bonus)

Keep the SL/TP pair with the highest score.
```

The Sharpe bonus rewards strategies that are not just profitable but **consistent** — low volatility of returns. This is how institutional desks evaluate strategies.

---

## 7. Trade Persistence (SQLite)

**File:** `data/trade_store.py`  
**Database:** `trades.db` (local SQLite file, never sent anywhere)

### Schema:
```sql
CREATE TABLE trades (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker       TEXT,
    timeframe    TEXT,
    direction    TEXT,       -- LONG / SHORT
    entry_date   TEXT,
    entry_price  REAL,       -- set once, never changes
    sl_price     REAL,
    tp_price     REAL,
    sl_pct       REAL,
    tp_pct       REAL,
    signal_score REAL,
    exit_date    TEXT,
    exit_price   REAL,
    pnl_pct      REAL,
    status       TEXT,       -- OPEN / TP_HIT / SL_HIT / MANUAL
    quantity     REAL        -- always 1.0
)
```

### Entry price protection:
`open_trade()` checks for an existing OPEN trade for the same ticker+timeframe before inserting. If one exists, it returns the existing ID without any change. This is why the entry price never resets on page refresh.

### Auto-close logic (runs every 10–15 seconds):
```
LONG pnl  = (live_price − entry_price) / entry_price × 100
SHORT pnl = (entry_price − live_price) / entry_price × 100

If pnl ≤ −sl_pct  →  SL_HIT
If pnl ≥  tp_pct  →  TP_HIT
```

---

## 8. Screener & Browser Notifications

**File:** `data/screener_store.py`

### Schema:
```sql
CREATE TABLE screener_watchlist (
    ticker    TEXT UNIQUE,
    timeframe TEXT,
    added_at  TEXT
)

CREATE TABLE screener_alerts (
    ticker    TEXT,
    timeframe TEXT,
    signal    TEXT,   -- LONG / SHORT
    score     REAL,
    price     REAL,
    fired_at  TEXT
)
```

### Scan logic (runs every 60 seconds):
```
For each ticker in watchlist:
  1. Fetch latest OHLCV
  2. Run full signal computation (all 12 systems)
  3. Get current signal (1, -1, or 0)
  4. Compare to last known signal in session state
  5. If signal changed from 0 → 1 or 0 → −1:
       - Log alert to screener_alerts table
       - Fire browser push notification (Notification API)
       - Show in-app st.toast()
       - Update last known signal
```

**Why "changed from 0"?** To avoid sending a notification every 60 seconds for a signal that's already been active. Only fires once per new signal.

---

## 9. Asset Coverage

| Category | Tickers | Exchange |
|---|---|---|
| Crypto | BTC, ETH, SOL, BNB, XRP, ADA, DOGE, AVAX, MATIC, DOT | Binance (via Yahoo) |
| Metals | Gold (GC=F), Silver (SI=F), Platinum (PL=F), Palladium (PA=F), Copper (HG=F) | COMEX |
| Energy | WTI Oil (CL=F), Brent Oil (BZ=F), Natural Gas (NG=F), Gasoline (RB=F) | NYMEX |
| US Stocks | AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA, META, NFLX, AMD, INTC, JPM, BAC, V, MA, WMT | NASDAQ / NYSE |
| Indices | S&P 500, Dow, Nasdaq, Nifty, Sensex, FTSE, Nikkei, Hang Seng | Various |
| Forex | EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, USD/INR | Forex |
| Commodities | Wheat, Corn, Soy, Coffee, Cotton | CBOT / ICEUS |
| Any ticker | Type any Yahoo Finance symbol in the search box | Yahoo Finance |

---

## 10. Signal Quality Summary

| Score | Votes | Signal | Quality |
|---|---|---|---|
| ≥ 0.75 | 8–12 systems | Strong LONG | Institutional-grade setup |
| 0.45–0.74 | 5–7 systems | LONG | High conviction |
| −0.44 to +0.44 | < 5 systems | NO SIGNAL | Too risky — wait |
| −0.45 to −0.74 | 5–7 systems | SHORT | High conviction |
| ≤ −0.75 | 8–12 systems | Strong SHORT | Institutional-grade setup |

---

## 11. Risk / Reward

```
R:R = take_profit_pct / stop_loss_pct
```

| R:R | Rating | Break-even win rate needed |
|---|---|---|
| ≥ 2.5 | Excellent | 29% |
| 2.0–2.4 | Good | 33% |
| 1.5–1.9 | OK | 40% |
| < 1.5 | Poor | > 40% |

**The key insight:** A 45% win rate at 1:2.5 R:R is more profitable than a 70% win rate at 1:0.5 R:R. This is why the optimizer enforces a minimum 1:1.5 R:R on all combinations it tests.
