# Trading Signals Platform

A professional trading signal platform built with Python and Streamlit. Supports any ticker — crypto, stocks, forex, gold, oil, and more. Signals are generated using 7 technical systems plus CVD and Open Interest filters. Includes live backtesting with date range analysis, a signal screener with browser notifications, a live TradingView chart, and **Bybit Demo auto-trading**.

**Live App:** [trade-hunt.streamlit.app](https://trade-hunt.streamlit.app)

---

## What It Does

- Automatically generates **LONG / SHORT / NO SIGNAL** for any ticker
- Computes **7 technical systems** (EMA, RSI, MACD, ADX, Bollinger Bands, Stochastic, CVD)
- Applies **4 precision filters** (EMA200 trend, RSI extreme, CVD divergence, Open Interest)
- Shows **live price** updating every 15 seconds
- **Backtest** the strategy on any date range with full metrics
- **Track tab** — watch up to 10 coins, auto-scans every 60s, fires Bybit orders automatically
- **Bybit Demo auto-trading** — places real orders on Bybit Demo account the moment a signal fires, for every tracked coin, even with the browser closed
- **Background scanner daemon** — runs 24/7 alongside the UI, monitors all watchlist coins and places Bybit orders without needing the browser open
- **Active trades** tracked in sidebar with live PnL
- Works for: Crypto · Stocks · Forex · Gold · Oil · Commodities · Indices

---

## How to Run (Local)

### First time setup

```bash
cd ~/Desktop/example/trading-platform
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Every time after laptop restart

Open Terminal and run:

```bash
cd ~/Desktop/example/trading-platform
./run.sh
```

This starts **both** the Streamlit UI and the background scanner daemon together.

Then open your browser at **http://localhost:8501**

### Run in background (terminal can be closed)

```bash
cd ~/Desktop/example/trading-platform
nohup ./run.sh > /tmp/app.log 2>&1 &
```

Stop everything: `pkill -f "streamlit run" && pkill -f "scanner_daemon"`

Check daemon log: `tail -f /tmp/scanner_daemon.log`

### Pull latest code from GitHub

```bash
cd ~/Desktop/example/trading-platform
git pull origin main
```

Then restart Streamlit.

---

## Screen Guide

### Sidebar — Symbol Picker & Active Trades

```
┌─────────────────────────────────────┐
│  ⚡ ACTIVE TRADES                    │
│  ┌──────────────────────────────┐   │
│  │ BNB-USD          +0.03%      │   │
│  │ ▼ SHORT           $0.16      │   │
│  │ In $559.84   Now $559.68     │   │
│  │ SL $573.84       TP $543.04  │   │
│  └──────────────────────────────┘   │
│  ──────────────────────────────     │
│  SYMBOL                             │
│  [ BTC-USD                     ]    │
│                                     │
│  ▼ Crypto                           │
│  [BTC-USD] [ETH-USD]                │
│  [SOL-USD] [BNB-USD]                │
│  ...                                │
│  ▼ Metals                           │
│  [GC=F Gold] [SI=F Silver] ...      │
│  ▶ Energy  ▶ US Stocks  ▶ Forex     │
│  ──────────────────────────────     │
│  Timeframe: [1d ▾]                  │
│  ☑ Auto-optimize SL/TP              │
│  SL% [——●—] 2.0    TP% [—●——] 4.0  │
└─────────────────────────────────────┘
```

**Active Trades** (top of sidebar) — shows all open trades with live PnL, entry price, current price, stop loss and take profit levels. Updates silently every 10 seconds.

**Symbol** — type any Yahoo Finance ticker or pick from the category list. Signal loads automatically when you select — no button to press.

**Timeframe** — 1m / 5m / 15m / 30m / 1h / 4h / 1d / 1w

**SL / TP sliders** — uncheck Auto-optimize to set manually. Backtest updates instantly when you move the sliders.

---

### Tab 1 — Signal & Chart

> _Screenshot: see the app at http://localhost:8501 → Signal & Chart tab_

```
┌─────────────────────────────────────────────────────┐
│  🟢  LONG                    │  ● LIVE · GC=F       │
│  Confidence 72% (High)       │  $4,132.90           │
│  Score 0.58 · SL 2% · TP 4% │  +1.24% today        │
├─────────────────────────────────────────────────────┤
│  📐 Trade Setup — LONG                              │
│  Entry $4,132  SL $4,050  TP $4,297  R:R 1:2.0     │
├─────────────────────────────────────────────────────┤
│  EMA Stack  EMA 200   RSI    MACD   ADX+DI  Stoch  │
│  Aligned✓   Above     65     Bull   +28/-19  72     │
│                                                     │
│  CVD        OI        OBV    Vol    Ichimoku CCI    │
│  ▲ Bull     ↑ 45K    Rising  1.3×   Above☁   +120  │
├─────────────────────────────────────────────────────┤
│  [TradingView Chart — full interactive]             │
│  Candlesticks + RSI + MACD + Bollinger Bands        │
└─────────────────────────────────────────────────────┘
```

**Signal box** — shows LONG (green), SHORT (red), or NO SIGNAL (yellow). Includes confidence %, score, and reason why no signal when flat.

**Trade Setup** — entry price, exact SL and TP dollar levels, and Risk:Reward ratio. Only shown when a signal is active.

**Indicator chips** — 12 indicators shown at a glance:

| Chip | What it means |
|---|---|
| EMA Stack | EMA9 > EMA21 > EMA50 = uptrend aligned |
| EMA 200 | Above = bull market, Below = bear market |
| RSI | 50-70 = bullish zone, 30-50 = bearish zone |
| MACD | Bull = MACD line above signal line |
| ADX+DI | +28/-19 = trending up with strength |
| Stoch | %K vs %D crossover under/over 80/20 |
| CVD | ▲ Bull = buyers dominating the volume |
| OI | ↑ = new money entering (crypto only) |
| OBV | Rising = volume backing the move |
| Vol Ratio | >1.2× = above average volume |
| Ichimoku | Above cloud = strong bull trend |
| CCI | >+100 = strong momentum |

**TradingView chart** — fully interactive with RSI, MACD, and Bollinger Bands overlaid. Change timeframe directly in the chart.

---

### Tab 2 — Backtest

```
┌──────────────────────────────────────────────────────────┐
│  📅 Date Range Filter                                     │
│  From [2025-07-01]    To [2026-07-02]   □ Full history   │
│  Showing: 2025-07-01 → 2026-07-02 · 367 candles         │
├────────────────────────┬─────────────────────────────────┤
│  FULL HISTORY          │  SELECTED: 2025-07-01→2026-07-02│
│  Win Rate   47.5%      │  Win Rate   49.3%               │
│  Trades     674        │  Trades     69                  │
│  Return     +934.0%    │  Return     +47.6%              │
│  Avg Win    +6.66%     │  Avg Win    +5.28%              │
│  Avg Loss   -4.88%     │  Avg Loss   -3.77%              │
│  P. Factor  1.23       │  P. Factor  1.36                │
│  Wins/Loss  320/354    │  Wins/Loss  34/35               │
│  Max DD     -84.1%     │  Max DD     -32.4%              │
├────────────────────────┴─────────────────────────────────┤
│  Equity Curve (full history faded, selected = blue)      │
│  ▲ 400k                                                  │
│       ╭─╮                                                │
│  ────╯   ╰──────────────────────────────────────────────│
│  $10k start                                              │
├──────────────────────────────────────────────────────────┤
│  My Trades (Real Signals from DB)                        │
│  Status   Type    Entry$   Exit$   PnL%                  │
│  ⏳ OPEN  🔴SHORT $559.84  $560    -0.03% (live)         │
│  🎯 TP    🟢LONG  $91,200  $93,744 +2.79%                │
├──────────────────────────────────────────────────────────┤
│  Historical Backtest Trades (all simulated trades)       │
└──────────────────────────────────────────────────────────┘
```

**Date Range Filter** — pick any From/To date to see performance in that period only. Full History checkbox shows all available data.

**Side-by-side comparison** — Full history vs your selected range shown together so you can compare recent vs long-term performance.

**Metrics explained:**

| Metric | Good | Description |
|---|---|---|
| Win Rate | > 45% | % of trades that hit Take Profit |
| Total Return | > 0% | Overall portfolio growth from $10,000 |
| Avg Win | Higher the better | Average % gain on winning trades |
| Avg Loss | Smaller the better | Average % loss on losing trades |
| Profit Factor | > 1.5 | Total wins ÷ total losses |
| Max Drawdown | Better than -30% | Worst peak-to-trough drop |

**Why 47% win rate is still profitable:** If your avg win is +6% and avg loss is -4%, you make money even winning less than half the time. Profit Factor > 1.0 means profitable overall.

---

### Tab 3 — Track (Watchlist + Auto-Trade)

```
┌──────────────────────────────────────────────────────┐
│  Tracking 4/10 coins  ·  Scans every 60s  ·  ⚡ Auto-trade ON │
├──────────────────────────────────────────────────────┤
│  XRP-USD  1d   ⏳ SHORT +1.15%   Price $1.11   Score -0.33  [🔎 View] [✕] │
│  BTC-USD  1d   ⏳ SHORT -4.56%   Price $61,863  Score +0.56  [🔎 View] [✕] │
│  ETH-USD  1d   ⚪ No Signal      Price $1,859   Score +0.56  [🔎 View] [✕] │
├──────────────────────────────────────────────────────┤
│  📋 Trades Taken                                     │
│  Result  Coin     Type    Entry              PnL %        SL $        TP $  │
│  ⏳OPEN  XRP-USD  🔴SHORT  2026-07-14 22:03  +1.15%(live) $1.13      $1.06  │
│  ⏳OPEN  BTC-USD  🔴SHORT  2026-07-09 01:50  -4.56%(live) $63,101    $59,389│
└──────────────────────────────────────────────────────┘
```

**How it works:**
1. Add up to 10 coins to the watchlist
2. The scanner checks every 60 seconds for LONG/SHORT signals
3. When a signal fires, it **automatically places a Bybit order** — no browser interaction needed
4. The background daemon (`scanner_daemon.py`) also places orders 24/7 even if the browser is closed
5. All trades logged in "Trades Taken" with live PnL

**Order parameters:** 10% of balance · 2× leverage · SL 2% · TP 4%

---

### Tab 4 — Chat

Ask questions about the current signal in plain English:

```
You: Should I enter now?
Bot: 📈 LONG signal is active. Enter at the current price shown,
     set your stop loss at the SL level, and target the TP level.
     Never risk more than 1-2% of capital per trade.

You: What is RSI?
Bot: RSI below 30 = oversold (bounce possible).
     Above 70 = overbought (drop possible). 40-60 = neutral.

You: What is stop loss?
Bot: Exit point if trade goes wrong. Never move it further
     from entry — it exists to protect your capital.
```

Ask about: **signal, long, short, stop loss, take profit, RSI, MACD, EMA, ADX, win rate, backtest**

---

### Tab 5 — Bybit Demo Trading

```
┌──────────────────────────────────────────────────────┐
│  🟡 Bybit Demo Trading                               │
│  USDT Balance  $971.80   Unrealised PnL: +0.00       │
│  ⚡ Auto-Trade: ALWAYS ON                             │
│  10% of balance × 2× leverage per signal             │
├──────────────────────────────────────────────────────┤
│  Open Positions                                      │
│  XRPUSDT  SHORT  Size 180  Entry $1.11  PnL +$2.07  │
│  BTCUSDT  SHORT  Size 0.003  Entry $61,863  PnL -$12 │
└──────────────────────────────────────────────────────┘
```

- Shows live balance and unrealised PnL
- Lists all open positions with entry price and current PnL
- Auto-Trade is always on — orders fire automatically when signals fire

---

### Tab 6 — Screener

```
┌──────────────────────────────────────────────────────┐
│  🔔 Enable Browser Notifications   [Enable Button]   │
│  ✅ Notifications are enabled                        │
├──────────────────────────────────────────────────────┤
│  ➕ Add Ticker    [BTC-USD    ] [1d ▾]  [Add]        │
│  Quick add: [BTC] [ETH] [SOL] [AAPL] [TSLA]...      │
├──────────────────────────────────────────────────────┤
│  👁 Watching 3 tickers — scans every 60s             │
│                                                      │
│  BTC-USD  $107,450   🟢 LONG    Score +0.67   [✕]   │
│  ETH-USD  $3,820     ⚪ NO SIG  Score +0.22   [✕]   │
│  AAPL     $214.50    🔴 SHORT   Score -0.51   [✕]   │
├──────────────────────────────────────────────────────┤
│  🔔 Alert History                                    │
│  Time           Ticker  Signal  Price    Score       │
│  2026-07-02 20:10  BTC  🟢LONG  $107,200  +0.67     │
│  2026-07-02 19:45  AAPL 🔴SHORT $215.10   -0.51     │
└──────────────────────────────────────────────────────┘
```

**How it works:**
1. Add any tickers to the watchlist
2. Click **Enable Browser Notifications** (one time)
3. The screener scans every 60 seconds
4. When a LONG or SHORT fires, you get a **browser popup notification** + an in-app toast
5. All alerts saved to history

---

## Supported Assets

| Category | Examples | How to type |
|---|---|---|
| Crypto | Bitcoin, Ethereum, BNB, Solana | `BTC-USD`, `ETH-USD`, `BNB-USD` |
| Gold | Gold spot | `GC=F` |
| Silver | Silver spot | `SI=F` |
| Oil | WTI Crude, Brent | `CL=F`, `BZ=F` |
| Natural Gas | — | `NG=F` |
| US Stocks | Apple, Tesla, Nvidia | `AAPL`, `TSLA`, `NVDA` |
| Indices | S&P 500, Nifty 50 | `^GSPC`, `^NSEI` |
| Forex | EUR/USD, GBP/USD | `EURUSD=X`, `GBPUSD=X` |
| Any ticker | Any Yahoo Finance symbol | Type directly in search |

---

## Signal Logic

### How a signal is generated

```
Step 1 — Score 7 systems:
  EMA 9/21/50 stack    → weight 2   (trend direction)
  RSI zone 50-70       → weight 1   (momentum zone)
  MACD crossover       → weight 1   (momentum trigger)
  ADX + DI direction   → weight 1   (trend strength)
  Bollinger Band pos.  → weight 1   (price position)
  Stochastic crossover → weight 1   (entry timing)
  CVD trend            → weight 1   (real buy/sell pressure)

  Score = total / 9   →  range -1 to +1

Step 2 — Signal gate:
  Score ≥ +0.40  →  LONG candidate
  Score ≤ -0.40  →  SHORT candidate

Step 3 — Precision filters (block bad signals):
  F1. Price below EMA200 → no LONG  (bear market)
  F2. Price above EMA200 → no SHORT (bull market)
  F3. RSI > 78  → no LONG  (severely overbought)
  F4. RSI < 22  → no SHORT (severely oversold)
  F5. CVD falling while price rising → no LONG  (divergence)
  F6. CVD rising while price falling → no SHORT (divergence)
  F7. OI falling + low confidence → signal blocked (crypto only)

Final: LONG / SHORT / NO SIGNAL
```

### What is CVD?

CVD (Cumulative Volume Delta) separates buying volume from selling volume inside each candle:

```
Buy pressure  = volume × (close − low)  / (high − low)
Sell pressure = volume × (high − close) / (high − low)
CVD           = cumulative sum of (buy − sell)
```

Rising CVD = buyers are dominant. Falling CVD = sellers are dominant.

**CVD Divergence** is one of the most powerful signals professional traders use:
- Price makes new high but CVD falls → smart money is selling into the rally → LONG blocked
- Price makes new low but CVD rises → smart money is buying the dip → SHORT blocked

### What is Open Interest (OI)?

OI = total number of open futures contracts in the market (crypto only).

| OI | Price | Meaning |
|---|---|---|
| Rising | Rising | New longs entering → strong uptrend |
| Rising | Falling | New shorts entering → strong downtrend |
| Falling | Any | Contracts closing → move losing steam → signal blocked |

---

## Auto-Optimize SL/TP

When **Auto-optimize** is checked, the system tests 56 combinations of Stop Loss and Take Profit:

```
SL options: 1% 1.5% 2% 2.5% 3% 4% 5%
TP options: 2% 3% 4% 5% 6% 8% 10% 12%
Rules: TP must be at least 1.5× the SL · Minimum 10 trades

Score = (Win Rate%) × Profit Factor × (1 + Sharpe/10)
```

The combination with the highest score becomes your recommended SL and TP.

---

## Project Structure

```
trading-platform/
├── ui/
│   └── app.py              # Main Streamlit app (Signal, Backtest, Track, Bybit, Chat tabs)
├── scanner_daemon.py        # Background daemon — scans watchlist + places Bybit orders 24/7
├── indicators/
│   └── signals.py          # Signal engine (7 systems + 4 filters)
├── backtest/
│   ├── engine.py           # Backtest simulator
│   └── optimizer.py        # SL/TP grid search
├── data/
│   ├── fetcher.py          # Yahoo Finance + Binance OI fetch
│   ├── bybit_client.py     # Bybit Demo API — place/close orders, balance, positions
│   ├── trade_store.py      # SQLite trade persistence
│   └── screener_store.py   # Watchlist store (used by both UI and daemon)
├── run.sh                   # Starts both Streamlit UI and scanner daemon together
├── .streamlit/
│   └── config.toml         # Theme + server config
├── .env                     # Bybit API credentials (not committed)
├── CALCULATIONS.md         # Full formula documentation
├── requirements.txt
└── trades.db               # Local SQLite database (auto-created)
```

---

## FAQ

**Q: Does it place real trades?**
Yes — on your **Bybit Demo account**. Credentials are loaded from a `.env` file. It uses the Bybit Demo environment so no real money is at risk. Set `BYBIT_DEMO=false` in `.env` only if you want live trading.

**Q: Why did the tracker show a signal but Bybit didn't take the trade?**
Previously the Track tab only displayed signals without placing orders. This is now fixed — both the Track tab and the background `scanner_daemon.py` place Bybit orders automatically when signals fire. Always start the app via `./run.sh` so the daemon runs alongside the UI.

**Q: Does the daemon need the browser open?**
No. `scanner_daemon.py` runs as a background process and places orders 24/7 independently of the browser or Streamlit UI.

**Q: Where is my data stored?**
Everything is local — `trades.db` is a SQLite file on your machine. Nothing is sent anywhere except Bybit API calls.

**Q: Why does OI show N/A for stocks?**
Open Interest data is only available for crypto futures via Binance API. For stocks, forex, and commodities it shows N/A — the other 6 systems still work normally.

**Q: Why is win rate ~47-50% and not higher?**
A 47% win rate with 1.5 R:R (TP = 1.5× SL) is profitable long-term. You only need 40% to break even at that ratio. Adding more indicators beyond the current 7 actually worsens performance by delaying entries.

**Q: The signal changed after I refreshed — is that normal?**
Yes. Signals are based on the latest closed candle. On the 1d timeframe, the signal can only change once per day when a new candle closes.

**Q: Do I need to redeploy on Streamlit Cloud when I push new code?**
No. Streamlit Cloud auto-deploys within 1-2 minutes of every push to `main`.
