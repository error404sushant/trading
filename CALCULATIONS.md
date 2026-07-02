# Trading Platform — How Everything Is Calculated

This document explains every calculation in the platform in plain language, from raw price data to the final LONG/SHORT signal and backtest metrics.

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

**Live price** is fetched separately using `yf.Ticker.fast_info.last_price` — this is the real-time last traded price, not the stale candle close.

---

## 2. Technical Indicators

**File:** `indicators/signals.py` → `add_all_indicators()`

### 2.1 Exponential Moving Averages (EMA)

An EMA gives more weight to recent candles than old ones. It "follows" the price but smooths out noise.

```
EMA(today) = close(today) × k + EMA(yesterday) × (1 − k)
where k = 2 / (window + 1)
```

Four EMAs are calculated:

| EMA | Window | Purpose |
|---|---|---|
| EMA 9 | 9 bars | Short-term trend (very reactive) |
| EMA 21 | 21 bars | Medium-term trend |
| EMA 50 | 50 bars | Long-term trend (main trend filter) |
| EMA 200 | 200 bars | Macro trend (bull/bear market) |

**Reading:**  
- EMA9 > EMA21 > EMA50 = Strong uptrend (price accelerating up)  
- EMA9 < EMA21 < EMA50 = Strong downtrend  
- Price above EMA200 = Bull market; below = Bear market

---

### 2.2 MACD (Moving Average Convergence Divergence)

Measures momentum — how fast the trend is accelerating or decelerating.

```
MACD Line    = EMA(12) − EMA(26)
Signal Line  = EMA(9) of MACD Line
Histogram    = MACD Line − Signal Line
```

**Reading:**  
- MACD Line crosses **above** Signal Line = Bullish momentum starting  
- MACD Line crosses **below** Signal Line = Bearish momentum starting  
- Histogram growing positive = momentum accelerating upward  
- Histogram shrinking = momentum fading (early warning of reversal)

---

### 2.3 ADX (Average Directional Index)

Measures **trend strength** — not direction, just how strong the move is.

```
+DM = high − previous_high  (if positive, else 0)
−DM = previous_low − low    (if positive, else 0)
TR  = max(high−low, |high−prev_close|, |low−prev_close|)

+DI = 100 × EMA(+DM, 14) / EMA(TR, 14)
−DI = 100 × EMA(−DM, 14) / EMA(TR, 14)
DX  = 100 × |+DI − −DI| / (+DI + −DI)
ADX = EMA(DX, 14)
```

**Reading:**  
- ADX > 25 = Trending market — signals are reliable  
- ADX > 40 = Very strong trend  
- ADX < 20 = Choppy/ranging market — avoid trading, signals often fail  
- ADX tells you nothing about direction; combine with EMA for direction

---

### 2.4 RSI (Relative Strength Index)

Measures whether price is overbought (too high, due for pullback) or oversold (too low, due for bounce). Window: 14 bars.

```
Average Gain = mean of gains over last 14 bars
Average Loss = mean of losses over last 14 bars
RS           = Average Gain / Average Loss
RSI          = 100 − (100 / (1 + RS))
```

**Reading:**  
- RSI < 30 = Oversold — potential bounce (bullish opportunity)  
- RSI > 70 = Overbought — potential drop (bearish opportunity)  
- RSI 40–60 = Neutral zone — no strong signal  
- RSI > 50 in an uptrend = momentum confirmation  

---

### 2.5 Stochastic Oscillator

Compares current close to the range over the last 14 bars — shows where price sits within its recent range.

```
%K = (close − lowest_low_14) / (highest_high_14 − lowest_low_14) × 100
%D = 3-bar SMA of %K  (signal line)
```

**Reading:**  
- %K > %D and %K < 80 = Bullish momentum (not yet overbought)  
- %K < %D and %K > 20 = Bearish momentum (not yet oversold)  
- %K crossing above %D from below 20 = Strong buy signal  
- %K crossing below %D from above 80 = Strong sell signal

---

### 2.6 Bollinger Bands (BB)

Measures volatility and whether price is stretched. Uses a 20-bar moving average with 2 standard deviations.

```
Middle Band = SMA(close, 20)
Upper Band  = SMA + 2 × StdDev(close, 20)
Lower Band  = SMA − 2 × StdDev(close, 20)

BB %        = (close − Lower Band) / (Upper Band − Lower Band)
```

**Reading:**  
- BB% > 0.8 = Price near upper band = overbought  
- BB% < 0.2 = Price near lower band = oversold  
- BB% 0.4–0.6 = Middle zone = neutral  
- Bands squeezing together = low volatility, big move coming soon  
- Price breaking above upper band with volume = strong breakout

---

### 2.7 ATR (Average True Range)

Measures volatility — how much price moves on an average bar. Used to set realistic stop losses.

```
True Range = max(high−low, |high−prev_close|, |low−prev_close|)
ATR        = EMA(True Range, 14)
```

**Why it matters:** A stock with ATR of $5 should have a stop loss at least $5 away. If your stop is too tight, normal price noise will knock you out before the trade plays out.

---

### 2.8 OBV (On-Balance Volume)

Tracks whether volume is flowing into or out of an asset. Confirms price moves with volume.

```
If close > prev_close: OBV = prev_OBV + volume
If close < prev_close: OBV = prev_OBV − volume
If close = prev_close: OBV = prev_OBV
```

**Reading:**  
- OBV rising while price rises = healthy uptrend (buyers backing the move)  
- OBV falling while price rises = dangerous (price going up on weak volume — likely to reverse)  
- OBV divergence = one of the most reliable early reversal signals

---

### 2.9 VWAP (Volume-Weighted Average Price)

The average price weighted by how much was traded at each level. Institutional traders (banks, funds) use this as their benchmark.

```
VWAP = Σ(volume × typical_price) / Σ(volume)
where typical_price = (high + low + close) / 3
```

**Reading:**  
- Price above VWAP = buyers are in control (bullish)  
- Price below VWAP = sellers are in control (bearish)  
- Large institutions try to trade close to VWAP — price tends to return to it

---

### 2.10 Pivot Points (Support & Resistance)

Calculated from the previous candle's high, low, and close. Acts as automatic support/resistance.

```
Pivot     = (prev_high + prev_low + prev_close) / 3
R1        = 2 × Pivot − prev_low    (first resistance)
S1        = 2 × Pivot − prev_high   (first support)
```

**Reading:**  
- Price above Pivot = bullish bias for the session  
- Price below Pivot = bearish bias  
- R1 and S1 are the first levels where price typically pauses or reverses

---

## 3. Signal Scoring System

**File:** `indicators/signals.py` → `generate_signals()`

Six indicators vote on direction. Each vote adds or subtracts from a raw score, then it's normalized to **−1 to +1**.

| Indicator | LONG votes | SHORT votes | Max contribution |
|---|---|---|---|
| EMA alignment | EMA9 > EMA21 > EMA50 → +2 | EMA9 < EMA21 < EMA50 → −2 | ±2 |
| RSI zone | RSI 50–70 → +1 | RSI 30–50 → −1 | ±1 |
| MACD crossover | MACD > Signal → +1 | MACD < Signal → −1 | ±1 |
| ADX strength | ADX > 25 → +1 | (no penalty) | +1 |
| Bollinger position | Close > BB Mid → +1 | Close < BB Mid → −1 | ±1 |
| Stochastic | %K > %D and < 80 → +1 | %K < %D and > 20 → −1 | ±1 |

```
Raw score range: −7 to +8
Normalized score = raw_score / 8.0   →   range: −0.875 to +1.0

Signal = LONG  if score ≥ +0.40
Signal = SHORT if score ≤ −0.40
Signal = NONE  if −0.40 < score < +0.40
```

**Why a threshold of 0.4?** It requires at least 3–4 indicators to agree before signalling. Single-indicator setups are filtered out.

---

## 4. Backtest Engine

**File:** `backtest/engine.py` → `run_backtest()`

Simulates trading the strategy on all historical data, one candle at a time.

### How it works step by step:

```
Start with $10,000 capital.
For each candle (oldest → newest):

  IF currently in a trade:
    pnl_pct = (current_price − entry_price) / entry_price × 100 × direction
    
    IF pnl_pct ≤ −stop_loss_pct  →  EXIT (stop loss hit)
    IF pnl_pct ≥ take_profit_pct →  EXIT (take profit hit)
    IF signal reversed direction  →  EXIT (signal reversal)

  IF not in a trade AND signal = 1 or −1:
    Enter trade at current close price
    Record entry_date, entry_price, direction

  Update equity curve: append current capital value
```

**Direction:** `+1` for LONG, `−1` for SHORT  
**PnL calculation:**
```
LONG:  pnl_pct = (exit − entry) / entry × 100
SHORT: pnl_pct = (entry − exit) / entry × 100
Capital update: new_capital = old_capital × (1 + pnl_pct / 100)
```

---

## 5. Backtest Metrics

**File:** `backtest/engine.py` → `BacktestResult`

### Win Rate
```
Win Rate = (Number of winning trades / Total closed trades) × 100
```
A 55% win rate means 55 out of 100 trades were profitable.

### Total Return
```
Total Return = (final_equity / initial_equity − 1) × 100
```

### Max Drawdown
The worst peak-to-trough loss in equity during the backtest.
```
For each point: drawdown = (equity − running_maximum) / running_maximum
Max Drawdown = minimum drawdown value × 100
```
A −25% max drawdown means the strategy once lost 25% from its peak before recovering.

### Sharpe Ratio
Risk-adjusted return. Measures how much return you get per unit of risk.
```
Daily Returns = equity.pct_change()
Sharpe = (mean_return / std_return) × √252
```
- Sharpe > 1 = Good  
- Sharpe > 2 = Excellent  
- Sharpe < 0 = Losing money on a risk-adjusted basis

### Profit Factor
```
Profit Factor = Total Gross Profit / Total Gross Loss
```
- PF > 1 = Strategy makes money overall  
- PF > 1.5 = Good  
- PF > 2 = Excellent  
- PF = 1.5 means for every $1 lost, the strategy makes $1.50

### Average Win / Average Loss
```
Avg Win  = mean(pnl_pct) across all winning trades
Avg Loss = mean(pnl_pct) across all losing trades
```
A good strategy has Avg Win / |Avg Loss| > 1.5 (reward exceeds risk per trade).

---

## 6. SL/TP Optimizer

**File:** `backtest/optimizer.py`

Grid search across all combinations of stop loss and take profit percentages:

```
SL values tested: 1.0%, 1.5%, 2.0%, 2.5%, 3.0%
TP values tested: 2.0%, 3.0%, 4.0%, 5.0%, 6.0%, 8.0%
Total combinations: 5 × 6 = 30 (minus any where TP ≤ SL)

For each combination:
  Run full backtest
  Score = (win_rate / 100) × profit_factor
  Keep the combination with the highest score
```

**Why this scoring formula?** Win rate alone is misleading (a 90% win rate with −50% losses is terrible). Profit factor alone is misleading too. Multiplying them penalises both extremes and rewards balanced strategies.

---

## 7. Trade Persistence

**File:** `data/trade_store.py`  
**Database:** `trades.db` (SQLite, local file)

### How a trade is recorded:

1. Signal fires (score ≥ 0.4 for LONG, ≤ −0.4 for SHORT)
2. `open_trade()` is called — **only writes if no OPEN trade exists for that ticker+timeframe**
3. Entry price is set once and never changed
4. SL and TP prices are calculated:
   ```
   LONG:  SL = entry × (1 − sl_pct/100),  TP = entry × (1 + tp_pct/100)
   SHORT: SL = entry × (1 + sl_pct/100),  TP = entry × (1 − tp_pct/100)
   ```

### Auto-close logic (`maybe_auto_close()`):

Every 10–15 seconds, the live price is checked against the stored SL/TP:
```
LONG pnl  = (live_price − entry_price) / entry_price × 100
SHORT pnl = (entry_price − live_price) / entry_price × 100

If pnl ≤ −sl_pct  →  close trade as SL_HIT
If pnl ≥  tp_pct  →  close trade as TP_HIT
```

---

## 8. Screener

**File:** `data/screener_store.py`

Watchlist stored in SQLite (`screener_watchlist` table). Every 60 seconds, the scanner:

1. Fetches OHLCV for each watched ticker
2. Runs `generate_signals()` to get the current signal
3. Compares to the last known signal (stored in `st.session_state.screener_last`)
4. If signal **changed** from 0 → 1 (or 0 → −1): fires a browser notification + in-app toast + logs to `screener_alerts` table
5. Same signal as before: no alert (prevents spam)

---

## 9. Signal Quality Summary

| Score Range | Signal | Meaning |
|---|---|---|
| 0.75 to 1.0 | Strong LONG | 6–8 indicators aligned bullish |
| 0.40 to 0.74 | LONG | Majority bullish |
| −0.39 to +0.39 | NO SIGNAL | Mixed — too risky to trade |
| −0.40 to −0.74 | SHORT | Majority bearish |
| −0.75 to −1.0 | Strong SHORT | 6–8 indicators aligned bearish |

---

## 10. Risk/Reward Ratio

```
R:R = take_profit_pct / stop_loss_pct
```

| R:R | Rating | Meaning |
|---|---|---|
| ≥ 2.5 | Excellent | You make 2.5× what you risk per trade |
| 2.0–2.4 | Good | |
| 1.5–1.9 | OK | Minimum acceptable |
| < 1.5 | Poor | Not worth taking — need win rate > 70% to be profitable |

**Why R:R matters more than win rate:**  
At 1:2 R:R, you only need a **34% win rate** to break even.  
At 1:0.5 R:R, you need a **67% win rate** just to break even.  
This is why professional traders focus on R:R first, win rate second.
