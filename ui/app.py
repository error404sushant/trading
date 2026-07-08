import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta

from data.fetcher import fetch_ohlcv, get_live_price, fetch_open_interest
from data.trade_store import get_open_trade, open_trade, maybe_auto_close, get_all_trades, init_db
from data.screener_store import init_screener, add_ticker, remove_ticker, get_watchlist
from data.bybit_client import (is_configured, get_balance, get_positions,
                                place_order, close_position, get_bybit_symbol,
                                get_min_qty, calc_qty, get_trade_history)
from indicators.signals import generate_signals
from backtest.engine import run_backtest
from backtest.optimizer import optimize

init_db()
init_screener()

# ── Popular tickers for autocomplete ─────────────────────────────────────────
POPULAR = {
    "Crypto":      ["BTC-USDT","ETH-USDT","SOL-USDT","BNB-USDT","XRP-USDT","ADA-USDT","DOGE-USDT","AVAX-USDT","MATIC-USDT","DOT-USDT"],
    "Metals":      ["GC=F","SI=F","PL=F","PA=F","HG=F"],
    "Energy":      ["CL=F","BZ=F","NG=F","RB=F"],
    "US Stocks":   ["AAPL","MSFT","GOOGL","AMZN","NVDA","TSLA","META","NFLX","AMD","INTC","JPM","BAC","V","MA","WMT"],
    "Indian Stocks":["RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS","TATAMOTORS.NS","SBIN.NS","BHARTIARTL.NS"],
    "Indices":     ["^GSPC","^DJI","^IXIC","^NSEI","^BSESN","^FTSE","^N225","^HSI"],
    "Forex":       ["EURUSD=X","GBPUSD=X","USDJPY=X","AUDUSD=X","USDCAD=X","USDINR=X"],
    "Commodities": ["ZW=F","ZC=F","ZS=F","KC=F","CT=F"],
}
DISPLAY_NAMES = {
    "BTC-USDT": "BTCUSDT",
    "ETH-USDT": "ETHUSDT",
    "SOL-USDT": "SOLUSDT",
    "BNB-USDT": "BNBUSDT",
    "XRP-USDT": "XRPUSDT",
    "ADA-USDT": "ADAUSDT",
    "DOGE-USDT": "DOGEUSDT",
    "AVAX-USDT": "AVAXUSDT",
    "MATIC-USDT": "MATICUSDT",
    "DOT-USDT": "DOTUSDT",
    "GC=F": "XAUUSDT (Gold)",
    "SI=F": "XAGUSDT (Silver)",
    "PL=F": "Platinum",
    "PA=F": "Palladium",
    "HG=F": "Copper",
    "CL=F": "Crude Oil",
    "BZ=F": "Brent Crude",
    "NG=F": "Natural Gas",
    "RB=F": "Gasoline",
    "EURUSD=X": "EURUSD",
    "GBPUSD=X": "GBPUSD",
    "USDJPY=X": "USDJPY",
    "AUDUSD=X": "AUDUSD",
    "USDCAD=X": "USDCAD",
    "USDINR=X": "USDINR",
    "RELIANCE.NS": "Reliance (NSE)",
    "TCS.NS": "TCS (NSE)",
    "HDFCBANK.NS": "HDFC Bank",
    "INFY.NS": "Infosys",
    "ICICIBANK.NS": "ICICI Bank",
    "TATAMOTORS.NS": "Tata Motors",
    "SBIN.NS": "State Bank of India",
    "BHARTIARTL.NS": "Bharti Airtel",
}
ALL_TICKERS = [t for group in POPULAR.values() for t in group]

TV_SYMBOL_MAP = {
    "BTC-USD":"BINANCE:BTCUSDT","ETH-USD":"BINANCE:ETHUSDT","SOL-USD":"BINANCE:SOLUSDT",
    "BNB-USD":"BINANCE:BNBUSDT","XRP-USD":"BINANCE:XRPUSDT","ADA-USD":"BINANCE:ADAUSDT",
    "DOGE-USD":"BINANCE:DOGEUSDT","AVAX-USD":"BINANCE:AVAXUSDT","MATIC-USD":"BINANCE:MATICUSDT",
    "DOT-USD":"BINANCE:DOTUSDT",
    "BTC-USDT":"BINANCE:BTCUSDT","ETH-USDT":"BINANCE:ETHUSDT","SOL-USDT":"BINANCE:SOLUSDT",
    "BNB-USDT":"BINANCE:BNBUSDT","XRP-USDT":"BINANCE:XRPUSDT","ADA-USDT":"BINANCE:ADAUSDT",
    "DOGE-USDT":"BINANCE:DOGEUSDT","AVAX-USDT":"BINANCE:AVAXUSDT","MATIC-USDT":"BINANCE:MATICUSDT",
    "DOT-USDT":"BINANCE:DOTUSDT",
    "AAPL":"NASDAQ:AAPL","MSFT":"NASDAQ:MSFT","GOOGL":"NASDAQ:GOOGL","AMZN":"NASDAQ:AMZN",
    "NVDA":"NASDAQ:NVDA","TSLA":"NASDAQ:TSLA","META":"NASDAQ:META","NFLX":"NASDAQ:NFLX",
    "AMD":"NASDAQ:AMD","INTC":"NASDAQ:INTC","JPM":"NYSE:JPM","BAC":"NYSE:BAC",
    "V":"NYSE:V","MA":"NYSE:MA","WMT":"NYSE:WMT",
    "^GSPC":"SP:SPX","^DJI":"DJ:DJI","^IXIC":"NASDAQ:IXIC",
    "^NSEI":"NSE:NIFTY50","^BSESN":"BSE:SENSEX","^FTSE":"LSE:UKX","^N225":"TVC:NI225",
    "EURUSD=X":"FX:EURUSD","GBPUSD=X":"FX:GBPUSD","USDJPY=X":"FX:USDJPY",
    "AUDUSD=X":"FX:AUDUSD","USDCAD=X":"FX:USDCAD","USDINR=X":"FX:USDINR",
    "GC=F":"TVC:GOLD","SI=F":"TVC:SILVER","PL=F":"TVC:PLATINUM","PA=F":"TVC:PALLADIUM",
    "HG=F":"TVC:COPPER","CL=F":"TVC:USOIL","BZ=F":"TVC:UKOIL","NG=F":"TVC:NATURALGAS",
    "RB=F":"NYMEX:RB1!","ZW=F":"CBOT:ZW1!","ZC=F":"CBOT:ZC1!","ZS=F":"CBOT:ZS1!",
    "KC=F":"ICEUS:KC1!","CT=F":"ICEUS:CT1!",
}

def get_tv_symbol(ticker: str) -> str:
    if ticker.endswith(".NS"):
        return "NSE:" + ticker.replace(".NS", "")
    if ticker.endswith(".BO"):
        return "BSE:" + ticker.replace(".BO", "")
    return TV_SYMBOL_MAP.get(ticker, ticker.replace("-USD","USDT").replace("=X","").replace("^","").replace("-",""))

def chat_reply(q: str, ctx: str) -> str:
    q = q.lower()
    if any(w in q for w in ["signal","buy","sell","long","short","trade","enter"]):
        if "LONG" in ctx:
            return "📈 **LONG signal is active.** Enter at the current price shown, set your stop loss at the SL level, and target the TP level. Never risk more than 1-2% of capital per trade."
        elif "SHORT" in ctx:
            return "📉 **SHORT signal is active.** Sell short at the current price, stop loss above entry, take profit at the TP level."
        else:
            return "⚠️ **No signal right now.** The market isn't giving a clean setup. Patience is key — wait for indicators to align before entering."
    elif "rsi" in q:
        return "**RSI:** Below 30 = oversold (bounce possible). Above 70 = overbought (drop possible). 40–60 = neutral, avoid trading."
    elif "macd" in q:
        return "**MACD:** MACD line above signal line = bullish momentum. Below = bearish. Histogram growing = momentum accelerating."
    elif "stop" in q or " sl" in q:
        return "**Stop Loss:** Exit point if trade goes wrong. Never move it away from entry — it exists to protect your capital."
    elif "tp" in q or "profit" in q or "target" in q:
        return "**Take Profit:** Lock in gains when price hits this level. Don't be greedy. A hit TP is a winning trade."
    elif "ema" in q or "moving" in q:
        return "**EMAs:** EMA9 > EMA21 > EMA50 = strong uptrend. Reverse order = downtrend. Signal fires when multiple EMAs align."
    elif "adx" in q:
        return "**ADX > 25** = trending market, signals are reliable. ADX < 20 = choppy, signals often fail — avoid trading."
    elif "win" in q or "accuracy" in q:
        return "A 55% win rate with 1:2 risk/reward beats a 70% win rate with 1:0.5. Risk/reward matters more than win rate alone."
    elif "backtest" in q:
        return "The backtest tab shows how this strategy performed historically on real price data. Check Profit Factor (>1.5 is good) and Sharpe Ratio (>1 is good)."
    else:
        return "Ask me: **signal, long, short, stop loss, take profit, RSI, MACD, EMA, ADX, win rate, backtest**."


st.set_page_config(page_title="Trading Signals", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

# Force sidebar open on cloud (Streamlit Cloud sometimes ignores initial_sidebar_state)
st.markdown("""
<script>
window.addEventListener('load', function() {
    setTimeout(function() {
        var btn = window.parent.document.querySelector('[data-testid="collapsedControl"]');
        if (btn) btn.click();
    }, 500);
});
</script>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* Seamless Neumorphic Header to keep sidebar toggle native and visible */
[data-testid="stHeader"] { 
    background-color: #e0e5ec !important; 
}
/* Hide the top right toolbar (Deploy, Options) */
[data-testid="stToolbar"] { display: none !important; }

/* Keep enough padding so the content doesn't overlap the header and hide the toggle button */
[data-testid="stAppViewContainer"] > section > div { padding-top: 3rem !important; padding-bottom: 0rem !important; }
[data-testid="stTabs"] { margin-top: -1rem !important; padding-top: 0rem !important; }

/* 🔵 NEUMORPHISM GLOBAL BACKGROUND 🔵 */
[data-testid="stAppViewContainer"], [data-testid="stSidebar"] { 
    background-color: #e0e5ec !important; 
}
[data-testid="stSidebar"] { 
    border-right: none !important; 
    box-shadow: 10px 0px 15px -5px rgba(163,177,198,0.3);
}

/* Base text color to ensure readability */
* { color: #4a5568; }
h1, h2, h3, h4, h5, h6, strong, b { color: #2d3748 !important; }

/* Silent auto-refresh — no fade/grey during fragment reruns */
[data-stale="true"] { opacity: 1 !important; transition: none !important; }
[data-testid="stStatusWidget"] { display: none !important; }
[data-testid="stSpinner"] { display: none !important; }
section[data-testid="stSidebar"] > div { padding-top:1rem; }

/* Neumorphic base properties */
.neu-flat {
    background-color: #e0e5ec;
    border-radius: 16px;
    box-shadow: 9px 9px 16px rgb(163,177,198,0.6), -9px -9px 16px rgba(255,255,255, 0.5);
    border: none !important;
}

/* 🟢 Signal boxes (Neumorphic) */
.sig-long  { background:#e0e5ec; box-shadow: inset 6px 6px 10px 0 rgba(163,177,198,0.6), inset -6px -6px 10px 0 rgba(255,255,255,0.5); border-radius:12px; padding:12px; text-align:center; border:none; }
.sig-long .sig-type { color: #16a34a !important; text-shadow: 1px 1px 2px rgba(22,163,74,0.2); }

.sig-short { background:#e0e5ec; box-shadow: inset 6px 6px 10px 0 rgba(163,177,198,0.6), inset -6px -6px 10px 0 rgba(255,255,255,0.5); border-radius:12px; padding:12px; text-align:center; border:none; }
.sig-short .sig-type { color: #dc2626 !important; text-shadow: 1px 1px 2px rgba(220,38,38,0.2); }

.sig-none  { background:#e0e5ec; box-shadow: inset 6px 6px 10px 0 rgba(163,177,198,0.6), inset -6px -6px 10px 0 rgba(255,255,255,0.5); border-radius:12px; padding:12px; text-align:center; border:none; }
.sig-none .sig-type { color: #d97706 !important; }

.sig-type  { font-size:1.2rem; font-weight:900; letter-spacing:1px; }
.sig-sub   { font-size:0.72rem; color:#718096; margin-top:2px; }

/* Price box */
.price-box { background:#e0e5ec; border-radius:12px; padding:12px; text-align:center; box-shadow: 7px 7px 14px rgb(163,177,198,0.6), -7px -7px 14px rgba(255,255,255, 0.5); border:none; }
.live-dot  { display:inline-block;width:8px;height:8px;background:#ef4444;border-radius:50%;animation:blink 1.2s infinite; box-shadow: 0 0 5px #ef4444; }
@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}

/* Level cards */
.lvl { background:#e0e5ec; border-radius:16px; padding:18px 14px; text-align:center; box-shadow: 9px 9px 16px rgb(163,177,198,0.6), -9px -9px 16px rgba(255,255,255, 0.5); border:none; }
.lvl-val { font-size:1.4rem; font-weight:800; color: #2d3748; }
.lvl-lbl { font-size:0.68rem; color:#718096; margin-top:3px; text-transform:uppercase; letter-spacing:.5px; }
.lvl-sub { font-size:0.78rem; margin-top:3px; }

/* No signal box */
.no-sig { background:#e0e5ec; box-shadow: inset 6px 6px 10px 0 rgba(163,177,198,0.6), inset -6px -6px 10px 0 rgba(255,255,255,0.5); border-radius:16px; padding:36px; text-align:center; border:none; }

/* Indicator chips */
.chip { background:#e0e5ec; border-radius:10px; padding:10px 12px; text-align:center; box-shadow: 5px 5px 10px rgb(163,177,198,0.6), -5px -5px 10px rgba(255,255,255, 0.5); border:none; }
.chip-val { font-size:0.9rem; font-weight:700; color: #2d3748; }
.chip-lbl { font-size:0.65rem; color:#718096; margin-top:2px; }

/* Suggestion grid */
.sugg-btn button { font-size:0.72rem !important; padding:4px 8px !important; height:auto !important; border-radius: 8px !important; }

/* Section headers */
.sec-hdr { font-size:0.75rem; font-weight:700; color:#718096; text-transform:uppercase; letter-spacing:1px; margin:8px 0 4px; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
for k,v in [("df",None),("result",None),("opt_sl",2.0),("opt_tp",4.0),
            ("ticker","BTC-USDT"),("tf","1d"),("loaded_key",""),("backtest_key",""),
            ("msgs",[{"role":"assistant","content":"Select any coin — signals load automatically."}]),
            ("bybit_auto_trade", True),("bybit_last_order", {}),
            ("track_last_signal", {}),
            ("us_search_input", "BTC-USDT"), ("ind_search_input", ""),
            ("active_tab", "Signal & Chart")]:
    if k not in st.session_state:
        st.session_state[k] = v


def set_active_ticker(t):
    st.session_state.ticker = t
    if t.endswith((".NS", ".BO")):
        st.session_state["us_search_input"] = ""
        st.session_state["ind_search_input"] = t.replace(".NS", "").replace(".BO", "")
    else:
        st.session_state["us_search_input"] = t
        st.session_state["ind_search_input"] = ""


def load_tracked_coin(sym, tf):
    set_active_ticker(sym)
    st.session_state.tf = tf
    st.session_state.active_tab = "Signal & Chart"


def on_us_search():
    val = st.session_state.us_search_input.upper().strip()
    if val:
        st.session_state.ticker = val
        st.session_state.ind_search_input = ""


def on_ind_search():
    val = st.session_state.ind_search_input.upper().strip()
    if val:
        if not val.endswith((".NS", ".BO")):
            val = val + ".NS"
        st.session_state.ticker = val
        st.session_state.us_search_input = ""

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:

    # ══ BYBIT DEMO TRADING (Top Left) ════════════════════════════════════════
    if is_configured():
        st.markdown("""<div style="font-size:0.7rem;font-weight:700;color:#6b7280;
             text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">
          🟡 Bybit Demo Trading
        </div>""", unsafe_allow_html=True)

        @st.fragment(run_every=15)
        def bybit_panel():
            bal = get_balance()
            if bal["ok"]:
                eq  = bal["equity"]
                pnl = bal["unrealised_pnl"]
                pc  = "#16a34a" if pnl >= 0 else "#dc2626"
                st.markdown(f"""
                <div style="background:#fffbf0;border:1px solid #f59e0b;border-radius:8px;
                     padding:10px 12px;margin-bottom:8px;">
                  <div style="font-size:0.68rem;color:#6b7280;">USDT Balance</div>
                  <div style="font-size:1.2rem;font-weight:800;color:#111827;">${eq:,.2f}</div>
                  <div style="font-size:0.72rem;color:{pc};font-weight:600;">
                    Unrealised PnL: {'+' if pnl>=0 else ''}{pnl:.2f}
                  </div>
                </div>""", unsafe_allow_html=True)

            positions = get_positions()
            if positions:
                st.markdown("<div style='font-size:0.68rem;font-weight:700;color:#6b7280;margin-bottom:4px;'>OPEN POSITIONS</div>", unsafe_allow_html=True)
                for p in positions:
                    pnl = p["unrealised_pnl"]
                    pc  = "#16a34a" if pnl >= 0 else "#dc2626"
                    bg  = "#f0fff4" if pnl >= 0 else "#fff5f5"
                    bc  = "#22c55e" if pnl >= 0 else "#ef4444"
                    tag = "▲ LONG" if p["side"] == "Buy" else "▼ SHORT"
                    tag_c = "#16a34a" if p["side"] == "Buy" else "#dc2626"
                    pnl_pct = (p["mark_price"] - p["entry_price"]) / p["entry_price"] * 100
                    if p["side"] == "Sell":
                        pnl_pct = -pnl_pct
                    st.markdown(f"""
                    <div style="background:{bg};border-left:4px solid {bc};
                         border-radius:8px;padding:8px 10px;margin-bottom:6px;">
                      <div style="display:flex;justify-content:space-between;">
                        <span style="font-weight:800;font-size:0.88rem;">{p['symbol']}</span>
                        <span style="font-weight:900;color:{pc};">{pnl_pct:+.2f}%</span>
                      </div>
                      <div style="display:flex;justify-content:space-between;margin-top:2px;">
                        <span style="font-size:0.7rem;font-weight:700;color:{tag_c};">{tag} · {p['size']}</span>
                        <span style="font-size:0.7rem;color:{pc};">${pnl:+.2f}</span>
                      </div>
                      <div style="display:flex;justify-content:space-between;margin-top:3px;font-size:0.68rem;color:#374151;">
                        <span>In <b>${p['entry_price']:,.2f}</b></span>
                        <span>Now <b>${p['mark_price']:,.2f}</b></span>
                      </div>
                      <div style="display:flex;justify-content:space-between;margin-top:2px;font-size:0.65rem;">
                        <span style="color:#dc2626;">SL ${p['sl']:,.2f}</span>
                        <span style="color:#16a34a;">TP ${p['tp']:,.2f}</span>
                        <span style="color:#6b7280;">{p['leverage']}×</span>
                      </div>
                    </div>""", unsafe_allow_html=True)

                    # Close button (one per position)
                    yf_sym = next((k for k,v in __import__('data.bybit_client', fromlist=['SYMBOL_MAP']).SYMBOL_MAP.items() if v == p['symbol']), None)
                    if yf_sym and st.button(f"Close {p['symbol']}", key=f"close_{p['symbol']}", use_container_width=True):
                        res = close_position(yf_sym)
                        if res["ok"]:
                            st.success("Position closed!")
                        else:
                            st.error(res["error"])
                        st.rerun()

        bybit_panel()

        st.session_state.bybit_auto_trade = True
        st.markdown("""
        <div style="background:#f0fff4;border:1px solid #22c55e;border-radius:8px;
             padding:10px 12px;font-size:0.78rem;color:#15803d;margin-bottom:12px;">
          <b>⚡ Auto-Trade: ALWAYS ON</b><br>
          10% of balance × 2× leverage per signal.
        </div>""", unsafe_allow_html=True)

        st.divider()

    # ══ Symbol search & picker ════════════════════════════════════════════════
    # ══ Global / US Search ═══════════════════════════════════════════════════
    st.markdown("""<div style="font-size:0.7rem;font-weight:700;color:#6b7280;
         text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">
      🔍 Global / US Market Search
    </div>""", unsafe_allow_html=True)
    
    us_val = st.text_input("US Search",
                           placeholder="e.g. BTC-USDT, AAPL, GC=F",
                           label_visibility="collapsed", key="us_search_input",
                           on_change=on_us_search)

    # ══ Indian Market Search ═════════════════════════════════════════════════
    st.markdown("""<div style="font-size:0.7rem;font-weight:700;color:#6b7280;
         text-transform:uppercase;letter-spacing:1px;margin-top:8px;margin-bottom:4px;">
      🇮🇳 Indian Market Search (NSE)
    </div>""", unsafe_allow_html=True)
    
    ind_val = st.text_input("Ind Search",
                            placeholder="e.g. RELIANCE, TCS, TATAMOTORS",
                            label_visibility="collapsed", key="ind_search_input",
                            on_change=on_ind_search)

    # Popular picker
    for category, tickers in POPULAR.items():
        with st.expander(category, expanded=(category in ("Crypto", "Metals"))):
            cols = st.columns(2)
            for i, t in enumerate(tickers):
                is_active = (t == st.session_state.ticker)
                lbl = DISPLAY_NAMES.get(t, t)
                cols[i%2].button(lbl, key=f"p_{t}", use_container_width=True,
                                 type="primary" if is_active else "secondary",
                                 on_click=set_active_ticker, args=(t,))

    st.divider()

    # (Duplicate Bybit panel removed from here and moved to the top of the sidebar)

    timeframe = st.selectbox("Timeframe", ["1m","5m","15m","30m","1h","4h","1d","1w"],
                             index=6, key="tf_select")
    st.session_state.tf = timeframe
    auto_opt = st.checkbox("Auto-optimize SL/TP", value=True)
    c_sl, c_tp = st.columns(2)
    sl_pct = c_sl.slider("SL %",  0.5, 10.0,
                          value=float(st.session_state.opt_sl), step=0.5,
                          disabled=auto_opt,
                          help="Stop Loss — uncheck Auto-optimize to adjust")
    tp_pct = c_tp.slider("TP %", 1.0, 20.0,
                          value=float(st.session_state.opt_tp), step=0.5,
                          disabled=auto_opt,
                          help="Take Profit — backtest updates automatically")
    if auto_opt:
        sl_pct = st.session_state.opt_sl
        tp_pct = st.session_state.opt_tp

ticker    = st.session_state.ticker
timeframe = st.session_state.tf

# ── Auto-load whenever ticker or timeframe changes (no button needed) ─────────
current_key = f"{ticker}|{timeframe}"
needs_load  = (current_key != st.session_state.loaded_key)

# ── Re-run backtest when user manually changes SL/TP (auto_opt OFF only) ──────
if (not needs_load and not auto_opt and st.session_state.df is not None):
    manual_bt_key = f"{ticker}|{timeframe}|{sl_pct}|{tp_pct}"
    if manual_bt_key != st.session_state.backtest_key:
        st.session_state.result      = run_backtest(st.session_state.df, sl_pct, tp_pct)
        st.session_state.opt_sl      = sl_pct
        st.session_state.opt_tp      = tp_pct
        st.session_state.backtest_key = manual_bt_key

if needs_load:
    st.session_state.loaded_key = current_key
    try:
        with st.spinner(f"Loading {ticker} {timeframe}…"):
            df_raw = fetch_ohlcv(ticker, interval=timeframe)
            oi     = fetch_open_interest(ticker, interval=timeframe)
            df     = generate_signals(df_raw, oi_series=oi if not oi.empty else None)
        st.session_state.df = df

        if auto_opt:
            with st.spinner("Optimizing SL/TP…"):
                opt = optimize(df)
            if opt["result"]:
                new_sl = opt["params"]["stop_loss_pct"]
                new_tp = opt["params"]["take_profit_pct"]
                st.session_state.opt_sl       = new_sl
                st.session_state.opt_tp       = new_tp
                st.session_state.result       = opt["result"]
                st.session_state.backtest_key = f"{ticker}|{timeframe}|{new_sl}|{new_tp}"
        else:
            st.session_state.opt_sl    = sl_pct
            st.session_state.opt_tp    = tp_pct
            st.session_state.result    = run_backtest(df, sl_pct, tp_pct)
            st.session_state.backtest_key = f"{ticker}|{timeframe}|{sl_pct}|{tp_pct}"
    except Exception as e:
        st.error(f"Could not load **{ticker}**: {e}")
        st.info("Try: BTC-USD, ETH-USD, AAPL, TSLA, EURUSD=X, GC=F")

col_t1, col_t2, col_t3, col_t4 = st.columns(4)
with col_t1:
    if st.button("📊 Signal & Chart", type="primary" if st.session_state.active_tab == "Signal & Chart" else "secondary", use_container_width=True):
        st.session_state.active_tab = "Signal & Chart"
        st.rerun()
with col_t2:
    if st.button("🧪 Backtest", type="primary" if st.session_state.active_tab == "Backtest" else "secondary", use_container_width=True):
        st.session_state.active_tab = "Backtest"
        st.rerun()
with col_t3:
    if st.button("🎯 Track", type="primary" if st.session_state.active_tab == "Track" else "secondary", use_container_width=True):
        st.session_state.active_tab = "Track"
        st.rerun()
with col_t4:
    if st.button("🟡 Bybit", type="primary" if st.session_state.active_tab == "Bybit" else "secondary", use_container_width=True):
        st.session_state.active_tab = "Bybit"
        st.rerun()

if st.session_state.active_tab == "Signal & Chart":
    if st.session_state.df is not None:
        df         = st.session_state.df
        last       = df.iloc[-1]
        sig        = int(last["signal"])
        used_sl    = st.session_state.opt_sl
        used_tp    = st.session_state.opt_tp
        score      = last["score"]
        votes      = int(last.get("votes", 0))
        confidence = float(last.get("confidence", abs(score) * 100))
        # Use live price for trade level calculations
        _live   = get_live_price(ticker)
        price   = _live["price"] if _live["price"] > 0 else last["close"]

        # ── Auto-record signal into DB (only once, never overwrites) ──────────
        if sig == 1 and price > 0:
            sl_p = price * (1 - used_sl / 100)
            tp_p = price * (1 + used_tp / 100)
            _, is_new = open_trade(ticker, timeframe, "LONG", price, sl_p, tp_p, used_sl, used_tp, score)
            # ── Bybit auto-trade ──────────────────────────────────────────────
            if is_new and st.session_state.get("bybit_auto_trade") and get_bybit_symbol(ticker):
                order_key = f"{ticker}|LONG|{price:.2f}"
                if st.session_state.bybit_last_order.get(ticker) != order_key:
                    qty = calc_qty(ticker, price, balance_pct=0.10, leverage=2)
                    if qty > 0:
                        res = place_order(ticker, "LONG", qty, sl_p, tp_p, leverage=2)
                        st.session_state.bybit_last_order[ticker] = order_key
                        if res["ok"]:
                            st.toast(f"✅ Bybit LONG — {ticker} qty {qty:.4f} (10% bal × 2×)", icon="🟢")
                        else:
                            st.toast(f"❌ Bybit order failed: {res['error']}", icon="🔴")
                    else:
                        st.toast(f"❌ Could not calculate qty for {ticker}", icon="🔴")
        elif sig == -1 and price > 0:
            sl_p = price * (1 + used_sl / 100)
            tp_p = price * (1 - used_tp / 100)
            _, is_new = open_trade(ticker, timeframe, "SHORT", price, sl_p, tp_p, used_sl, used_tp, score)
            # ── Bybit auto-trade ──────────────────────────────────────────────
            if is_new and st.session_state.get("bybit_auto_trade") and get_bybit_symbol(ticker):
                order_key = f"{ticker}|SHORT|{price:.2f}"
                if st.session_state.bybit_last_order.get(ticker) != order_key:
                    qty = calc_qty(ticker, price, balance_pct=0.10, leverage=2)
                    if qty > 0:
                        res = place_order(ticker, "SHORT", qty, sl_p, tp_p, leverage=2)
                        st.session_state.bybit_last_order[ticker] = order_key
                        if res["ok"]:
                            st.toast(f"✅ Bybit SHORT — {ticker} qty {qty:.4f} (10% bal × 2×)", icon="🔴")
                        else:
                            st.toast(f"❌ Bybit order failed: {res['error']}", icon="🔴")
                    else:
                        st.toast(f"❌ Could not calculate qty for {ticker}", icon="🔴")

        # Auto-close if SL/TP hit
        db_trade = get_open_trade(ticker, timeframe)
        if db_trade and price > 0:
            hit = maybe_auto_close(db_trade["id"], price)
            if hit:
                db_trade = None   # just closed

        # ── Signal + Price ────────────────────────────────────────────────────
        col_sig, col_price = st.columns([3, 1])

        with col_sig:
            conf_label = "Very High" if confidence >= 75 else "High" if confidence >= 60 else "Medium" if confidence >= 45 else "Low"
            if sig == 1:
                st.markdown(f"""<div class="sig-long">
                  <div class="sig-type" style="color:#16a34a;">🟢 &nbsp;LONG</div>
                  <div class="sig-sub">
                    Confidence <b>{confidence:.0f}%</b> ({conf_label}) &nbsp;·&nbsp;
                    {votes} / 12 systems agree &nbsp;·&nbsp;
                    Score {score:.2f} &nbsp;·&nbsp; SL {used_sl}% &nbsp;·&nbsp; TP {used_tp}%
                  </div>
                </div>""", unsafe_allow_html=True)
            elif sig == -1:
                st.markdown(f"""<div class="sig-short">
                  <div class="sig-type" style="color:#dc2626;">🔴 &nbsp;SHORT</div>
                  <div class="sig-sub">
                    Confidence <b>{confidence:.0f}%</b> ({conf_label}) &nbsp;·&nbsp;
                    {abs(votes)} / 12 systems agree &nbsp;·&nbsp;
                    Score {score:.2f} &nbsp;·&nbsp; SL {used_sl}% &nbsp;·&nbsp; TP {used_tp}%
                  </div>
                </div>""", unsafe_allow_html=True)
            else:
                reasons = []
                if last["adx"] < 20:           reasons.append(f"ADX {last['adx']:.0f} — no trend")
                if 40 < last["rsi"] < 60:      reasons.append(f"RSI {last['rsi']:.0f} — neutral zone")
                if last["macd"] > last["macd_signal"] and last["ema_9"] < last["ema_21"]:
                    reasons.append("MACD & EMA conflict")
                if abs(votes) < 5:             reasons.append(f"Only {abs(votes)}/12 systems agree — need 5+")
                if abs(score) < 0.45:          reasons.append(f"Score {score:.2f} below threshold")
                reason = " · ".join(reasons) if reasons else f"Score {score:.2f} — indicators not aligned"
                st.markdown(f"""<div class="sig-none">
                  <div class="sig-type" style="color:#d97706;">⚠️ &nbsp;NO SIGNAL</div>
                  <div class="sig-sub">Not a good time to trade &nbsp;·&nbsp; {reason}</div>
                  <div style="font-size:0.78rem;color:#9ca3af;margin-top:8px;">
                    {abs(votes)} / 12 analytical systems firing &nbsp;·&nbsp; Wait for 5+ to align.
                  </div>
                </div>""", unsafe_allow_html=True)

        with col_price:
            @st.fragment(run_every=15)
            def live_price_box(current_ticker):
                live = get_live_price(current_ticker)
                p    = live["price"]
                chg  = live["change_pct"]
                chg_color = "#16a34a" if chg >= 0 else "#dc2626"
                st.markdown(f"""<div class="price-box">
                  <div style="font-size:0.72rem;color:#6b7280;"><span class="live-dot"></span> &nbsp;LIVE &nbsp;·&nbsp; {current_ticker}</div>
                  <div style="font-size:1.4rem;font-weight:900;color:#111827;margin-top:2px;">${p:,.2f}</div>
                  <div style="color:{chg_color};font-size:0.8rem;margin-top:2px;">{'+' if chg>=0 else ''}{chg:.2f}% today</div>
                  <div style="font-size:0.6rem;color:#9ca3af;margin-top:2px;">Updates every 15s</div>
                </div>""", unsafe_allow_html=True)
            live_price_box(ticker)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Trade levels (only when signal exists) ────────────────────────────
        if sig == 1:
            sl_p = price * (1 - used_sl/100)
            tp_p = price * (1 + used_tp/100)
            rr   = used_tp / used_sl
            rc   = "#16a34a" if rr >= 1.5 else "#d97706"
            st.markdown("#### 📐 Trade Setup — LONG")
            c1,c2,c3,c4 = st.columns(4)
            with c1:
                st.markdown(f"""<div class="lvl" style="border-top:3px solid #22c55e;">
                  <div class="lvl-lbl">📍 Entry (Long)</div>
                  <div class="lvl-val" style="color:#16a34a;">${price:,.2f}</div>
                  <div class="lvl-sub" style="color:#6b7280;">Buy here</div>
                </div>""", unsafe_allow_html=True)
            with c2:
                st.markdown(f"""<div class="lvl" style="border-top:3px solid #ef4444;">
                  <div class="lvl-lbl">🛑 Stop Loss</div>
                  <div class="lvl-val" style="color:#dc2626;">${sl_p:,.2f}</div>
                  <div class="lvl-sub" style="color:#dc2626;">-{used_sl}% · Exit if broken</div>
                </div>""", unsafe_allow_html=True)
            with c3:
                st.markdown(f"""<div class="lvl" style="border-top:3px solid #22c55e;">
                  <div class="lvl-lbl">🎯 Take Profit</div>
                  <div class="lvl-val" style="color:#16a34a;">${tp_p:,.2f}</div>
                  <div class="lvl-sub" style="color:#16a34a;">+{used_tp}% · Lock gains</div>
                </div>""", unsafe_allow_html=True)
            with c4:
                st.markdown(f"""<div class="lvl" style="border-top:3px solid {rc};">
                  <div class="lvl-lbl">⚖️ Risk / Reward</div>
                  <div class="lvl-val" style="color:{rc};">1 : {rr:.1f}</div>
                  <div class="lvl-sub" style="color:{rc};">{'Excellent' if rr>=2.5 else 'Good' if rr>=2 else 'OK' if rr>=1.5 else 'Poor'}</div>
                </div>""", unsafe_allow_html=True)

        elif sig == -1:
            sl_p = price * (1 + used_sl/100)
            tp_p = price * (1 - used_tp/100)
            rr   = used_tp / used_sl
            rc   = "#16a34a" if rr >= 1.5 else "#d97706"
            st.markdown("#### 📐 Trade Setup — SHORT")
            c1,c2,c3,c4 = st.columns(4)
            with c1:
                st.markdown(f"""<div class="lvl" style="border-top:3px solid #ef4444;">
                  <div class="lvl-lbl">📍 Entry (Short)</div>
                  <div class="lvl-val" style="color:#dc2626;">${price:,.2f}</div>
                  <div class="lvl-sub" style="color:#6b7280;">Sell here</div>
                </div>""", unsafe_allow_html=True)
            with c2:
                st.markdown(f"""<div class="lvl" style="border-top:3px solid #ef4444;">
                  <div class="lvl-lbl">🛑 Stop Loss</div>
                  <div class="lvl-val" style="color:#dc2626;">${sl_p:,.2f}</div>
                  <div class="lvl-sub" style="color:#dc2626;">+{used_sl}% · Exit if broken</div>
                </div>""", unsafe_allow_html=True)
            with c3:
                st.markdown(f"""<div class="lvl" style="border-top:3px solid #22c55e;">
                  <div class="lvl-lbl">🎯 Take Profit</div>
                  <div class="lvl-val" style="color:#16a34a;">${tp_p:,.2f}</div>
                  <div class="lvl-sub" style="color:#16a34a;">-{used_tp}% · Lock gains</div>
                </div>""", unsafe_allow_html=True)
            with c4:
                st.markdown(f"""<div class="lvl" style="border-top:3px solid {rc};">
                  <div class="lvl-lbl">⚖️ Risk / Reward</div>
                  <div class="lvl-val" style="color:{rc};">1 : {rr:.1f}</div>
                  <div class="lvl-sub" style="color:{rc};">{'Excellent' if rr>=2.5 else 'Good' if rr>=2 else 'OK' if rr>=1.5 else 'Poor'}</div>
                </div>""", unsafe_allow_html=True)

        # ── Indicator chips — 12-system Wall Street dashboard ─────────────────
        st.markdown("<br>", unsafe_allow_html=True)

        # Ichimoku cloud position
        cloud_top_val    = max(float(last.get("ichi_a", 0)), float(last.get("ichi_b", 0)))
        cloud_bottom_val = min(float(last.get("ichi_a", 0)), float(last.get("ichi_b", 0)))
        above_cloud = float(last["close"]) > cloud_top_val if cloud_top_val > 0 else False
        ichi_label  = "Above ☁" if above_cloud else ("In ☁" if float(last["close"]) > cloud_bottom_val else "Below ☁")

        # Volume ratio
        vol_r = float(last.get("vol_ratio", 1.0))

        # CVD display
        cvd_val  = float(last.get("cvd", 0))
        cvd_ema  = float(last.get("cvd_ema", 0))
        cvd_bull_now = cvd_val > cvd_ema
        cvd_slope = float(last.get("cvd_slope", 0))
        cvd_label = f"{'▲' if cvd_slope > 0 else '▼'} {'Bull' if cvd_bull_now else 'Bear'}"

        # OI display
        oi_val   = last.get("oi", None)
        oi_ema_v = last.get("oi_ema", None)
        has_oi_data = oi_val is not None and not pd.isna(oi_val)
        if has_oi_data:
            oi_rising_now = float(oi_val) > float(oi_ema_v) if not pd.isna(oi_ema_v) else False
            oi_label = f"{'↑' if oi_rising_now else '↓'} {float(oi_val)/1e3:.0f}K"
        else:
            oi_rising_now = None
            oi_label = "N/A"

        chips = [
            ("EMA Stack",  "Aligned ✓" if last['ema_9'] > last['ema_21'] > last['ema_50'] else "Broken", last['ema_9'] > last['ema_21'] > last['ema_50']),
            ("EMA 200",    "Above" if last['close'] > last['ema_200'] else "Below",           last['close'] > last['ema_200']),
            ("RSI",        f"{last['rsi']:.0f}",                                              50 < last['rsi'] < 70),
            ("MACD",       "Bull" if last['macd'] > last['macd_signal'] else "Bear",          last['macd'] > last['macd_signal']),
            ("ADX+DI",     f"+{last['adx_pos']:.0f}/−{last['adx_neg']:.0f}",                 last['adx'] > 25 and last['adx_pos'] > last['adx_neg']),
            ("Stoch",      f"{last['stoch_k']:.0f}",                                          20 < last['stoch_k'] < 80),
            ("CVD",        cvd_label,                                                          cvd_bull_now),
            ("OI",         oi_label,                                                           oi_rising_now if oi_rising_now is not None else True),
            ("OBV",        "Rising" if last.get("obv", 0) > last.get("obv_ema", 0) else "Falling", last.get("obv", 0) > last.get("obv_ema", 0)),
            ("Vol Ratio",  f"{vol_r:.1f}×",                                                   vol_r > 1.2),
            ("Ichimoku",   ichi_label,                                                         above_cloud),
            ("CCI",        f"{last.get('cci', 0):.0f}",                                       -100 < last.get('cci', 0) < 100),
        ]
        rows = [chips[:6], chips[6:]]
        for row in rows:
            cols = st.columns(len(row))
            for col, (lbl, val, ok) in zip(cols, row):
                icon  = "🟢" if ok else "🔴"
                color = "#16a34a" if ok else "#dc2626"
                with col:
                    st.markdown(f"""<div class="chip">
                      <div class="chip-val" style="color:{color};">{icon} {val}</div>
                      <div class="chip-lbl">{lbl}</div>
                    </div>""", unsafe_allow_html=True)
            st.markdown("<div style='margin-top:6px;'></div>", unsafe_allow_html=True)

        st.markdown("---")

        # ── TradingView Chart ─────────────────────────────────────────────────
        st.markdown("### 📈 TradingView Chart")
        
        tv_sym = get_tv_symbol(ticker)
        
        import streamlit.components.v1 as components
        components.html(f"""
        <div id="tv_main" style="height:650px;"></div>
        <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
        <script type="text/javascript">
        new TradingView.widget({{
          "autosize": true,
          "symbol": "{tv_sym}",
          "interval": "D",
          "timezone": "Etc/UTC",
          "theme": "light",
          "style": "1",
          "locale": "en",
          "toolbar_bg": "#ffffff",
          "allow_symbol_change": true,
          "withdateranges": true,
          "hide_side_toolbar": false,
          "studies": ["RSI@tv-basicstudies","MACD@tv-basicstudies","BB@tv-basicstudies"],
          "container_id": "tv_main",
          "save_image": false,
          "show_popup_button": false,
          "popup_width": "1000",
          "popup_height": "650"
        }});
        </script>
        """, height=650)

    else:
        st.markdown("""
        <div style="text-align:center;padding:80px 20px;color:#6b7280;">
          <div style="font-size:3.5rem;">📈</div>
          <div style="font-size:1.2rem;margin-top:14px;color:#111827;font-weight:600;">Select a symbol to auto-load signals</div>
          <div style="margin-top:8px;font-size:0.88rem;">
            Use the sidebar to pick from popular symbols or type any Yahoo Finance ticker
          </div>
        </div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# BACKTEST TAB
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.active_tab == "Backtest":
    result = st.session_state.result
    if result and st.session_state.df is not None:
        df_full = st.session_state.df

        # ── Date range picker ─────────────────────────────────────────────────
        st.markdown("#### 📅 Date Range Filter")
        df_min = df_full.index.min().date()
        df_max = df_full.index.max().date()
        default_start = max(df_min, df_max - timedelta(days=365))

        col_d1, col_d2, col_d3 = st.columns([2, 2, 1])
        with col_d1:
            range_start = st.date_input("From", value=default_start,
                                        min_value=df_min, max_value=df_max,
                                        key="bt_start")
        with col_d2:
            range_end = st.date_input("To", value=df_max,
                                      min_value=df_min, max_value=df_max,
                                      key="bt_end")
        with col_d3:
            st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
            use_full = st.checkbox("Full history", value=False, key="bt_full")

        # Slice the dataframe
        if use_full or range_start >= range_end:
            df_slice   = df_full
            range_label = "Full History"
        else:
            df_slice   = df_full[str(range_start):str(range_end)]
            range_label = f"{range_start} → {range_end}"

        # Run backtest on the slice
        if len(df_slice) > 10:
            used_sl = st.session_state.opt_sl
            used_tp = st.session_state.opt_tp
            r_slice = run_backtest(df_slice, used_sl, used_tp)
        else:
            r_slice = None

        st.markdown(f"<div style='font-size:0.75rem;color:#6b7280;margin-bottom:12px;'>Showing: <b>{range_label}</b> &nbsp;·&nbsp; {len(df_slice)} candles</div>", unsafe_allow_html=True)
        st.markdown("---")

        # ── Metrics: Full Period vs Selected Range ────────────────────────────
        if not use_full and r_slice and range_start < range_end:
            col_full, col_range = st.columns(2)

            def _metric_card(r, label, color):
                wr = r.win_rate
                wins  = sum(1 for t in r.closed_trades if t.won)
                losses = r.n_trades - wins
                avg_w = r.avg_win
                avg_l = r.avg_loss
                return f"""
                <div style="background:#f8f9fc;border:1px solid #e0e4ef;border-radius:12px;padding:16px;border-top:3px solid {color};">
                  <div style="font-size:0.72rem;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;">{label}</div>
                  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;">
                    <div style="text-align:center;">
                      <div style="font-size:1.6rem;font-weight:900;color:{'#16a34a' if wr>=50 else '#dc2626'};">{wr:.1f}%</div>
                      <div style="font-size:0.65rem;color:#6b7280;margin-top:2px;">WIN RATE</div>
                    </div>
                    <div style="text-align:center;">
                      <div style="font-size:1.6rem;font-weight:900;color:#111827;">{r.n_trades}</div>
                      <div style="font-size:0.65rem;color:#6b7280;margin-top:2px;">TRADES</div>
                    </div>
                    <div style="text-align:center;">
                      <div style="font-size:1.6rem;font-weight:900;color:{'#16a34a' if r.total_return>0 else '#dc2626'};">{r.total_return:+.1f}%</div>
                      <div style="font-size:0.65rem;color:#6b7280;margin-top:2px;">RETURN</div>
                    </div>
                    <div style="text-align:center;">
                      <div style="font-size:1.1rem;font-weight:700;color:#16a34a;">{avg_w:+.2f}%</div>
                      <div style="font-size:0.65rem;color:#6b7280;margin-top:2px;">AVG WIN</div>
                    </div>
                    <div style="text-align:center;">
                      <div style="font-size:1.1rem;font-weight:700;color:#dc2626;">{avg_l:+.2f}%</div>
                      <div style="font-size:0.65rem;color:#6b7280;margin-top:2px;">AVG LOSS</div>
                    </div>
                    <div style="text-align:center;">
                      <div style="font-size:1.1rem;font-weight:700;color:{'#16a34a' if r.profit_factor>=1.5 else '#f59e0b' if r.profit_factor>=1 else '#dc2626'};">{r.profit_factor:.2f}</div>
                      <div style="font-size:0.65rem;color:#6b7280;margin-top:2px;">PROFIT FACTOR</div>
                    </div>
                    <div style="text-align:center;">
                      <div style="font-size:1.1rem;font-weight:700;color:#16a34a;">{wins}</div>
                      <div style="font-size:0.65rem;color:#6b7280;margin-top:2px;">WINS</div>
                    </div>
                    <div style="text-align:center;">
                      <div style="font-size:1.1rem;font-weight:700;color:#dc2626;">{losses}</div>
                      <div style="font-size:0.65rem;color:#6b7280;margin-top:2px;">LOSSES</div>
                    </div>
                    <div style="text-align:center;">
                      <div style="font-size:1.1rem;font-weight:700;color:#dc2626;">{r.max_drawdown:.1f}%</div>
                      <div style="font-size:0.65rem;color:#6b7280;margin-top:2px;">MAX DD</div>
                    </div>
                  </div>
                </div>"""

            with col_full:
                st.markdown(_metric_card(result, "Full History", "#6b7280"), unsafe_allow_html=True)
            with col_range:
                st.markdown(_metric_card(r_slice, f"Selected: {range_label}", "#2962FF"), unsafe_allow_html=True)

        else:
            # Full history — single row
            wr = result.win_rate
            wins  = sum(1 for t in result.closed_trades if t.won)
            losses = result.n_trades - wins
            c1,c2,c3,c4,c5,c6,c7,c8 = st.columns(8)
            for col,val,lbl,ok in [
                (c1, f"{wr:.1f}%",                    "Win Rate",     wr>=50),
                (c2, str(result.n_trades),             "Total Trades", True),
                (c3, str(wins),                        "Wins",         True),
                (c4, str(losses),                      "Losses",       False),
                (c5, f"{result.total_return:+.1f}%",   "Total Return", result.total_return>0),
                (c6, f"{result.avg_win:+.2f}%",        "Avg Win",      True),
                (c7, f"{result.avg_loss:+.2f}%",       "Avg Loss",     False),
                (c8, f"{result.profit_factor:.2f}",    "Profit Factor",result.profit_factor>1.5),
            ]:
                color = "#16a34a" if ok else "#dc2626"
                with col:
                    st.markdown(f"""<div class="lvl">
                      <div class="lvl-lbl">{lbl}</div>
                      <div class="lvl-val" style="color:{color};font-size:1.1rem;">{val}</div>
                    </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Equity curve ──────────────────────────────────────────────────────
        disp_result = r_slice if (r_slice and not use_full and range_start < range_end) else result
        fig2 = go.Figure()
        if not use_full and r_slice and range_start < range_end:
            # Show full period faded, selected range highlighted
            fig2.add_trace(go.Scatter(
                x=result.equity.index, y=result.equity.values,
                mode="lines", name="Full History",
                line=dict(color="rgba(107,114,128,0.25)", width=1.5),
            ))
            fig2.add_trace(go.Scatter(
                x=r_slice.equity.index, y=r_slice.equity.values,
                fill="tozeroy", mode="lines", name=f"Selected: {range_label}",
                line=dict(color="#2962FF", width=2.5, shape="spline", smoothing=0.5),
                fillcolor="rgba(41,98,255,0.08)",
            ))
        else:
            fig2.add_trace(go.Scatter(
                x=result.equity.index, y=result.equity.values,
                fill="tozeroy", mode="lines", name="Equity",
                line=dict(color="#2962FF", width=2.5, shape="spline", smoothing=0.5),
                fillcolor="rgba(41,98,255,0.08)",
            ))
        fig2.update_layout(
            height=280, template="plotly_white",
            paper_bgcolor="#ffffff", plot_bgcolor="#fafbff",
            title=f"Equity Curve — {ticker} {timeframe} · {range_label} (start $10,000)",
            margin=dict(l=0,r=0,t=40,b=0),
            font=dict(color="#111827"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig2, use_container_width=True)

        st.markdown("---")

        # (Bybit live positions and history removed per user request)

        # ── Section 2: Real signal trades from DB ─────────────────────────────
        st.markdown("### 🔴 My Trades (Real Signals)")
        db_trades = get_all_trades(ticker, timeframe, limit=200)
        live_p    = get_live_price(ticker)["price"] if db_trades else 0

        if db_trades:
            rows = []
            for t in db_trades:
                is_open   = t["status"] == "OPEN"
                direction = 1 if t["direction"] == "LONG" else -1
                if is_open and live_p > 0:
                    pnl        = (live_p - t["entry_price"]) / t["entry_price"] * 100 * direction
                    pnl_str    = f"{pnl:+.2f}% (live)"
                    result_str = "⏳ OPEN"
                    exit_str   = f"${live_p:,.2f} (now)"
                elif t["pnl_pct"] is not None:
                    pnl_str    = f"{t['pnl_pct']:+.2f}%"
                    result_str = {"TP_HIT":"🎯 TP HIT","SL_HIT":"🛑 SL HIT","MANUAL":"✋ MANUAL"}.get(t["status"], "✅ WIN" if t["pnl_pct"] > 0 else "❌ LOSS")
                    exit_str   = f"${t['exit_price']:,.2f}" if t["exit_price"] else "—"
                else:
                    pnl_str, result_str, exit_str = "—", "—", "—"

                rows.append({
                    "Status":     result_str,
                    "Type":       f"🟢 {t['direction']}" if t["direction"] == "LONG" else f"🔴 {t['direction']}",
                    "Entry Date": t["entry_date"][:16],
                    "Entry $":    f"${t['entry_price']:,.2f}",
                    "Exit $":     exit_str,
                    "Exit Date":  t["exit_date"][:16] if t["exit_date"] else "—",
                    "PnL %":      pnl_str,
                    "SL $":       f"${t['sl_price']:,.2f}",
                    "TP $":       f"${t['tp_price']:,.2f}",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, height=250)
        else:
            st.caption("No real trades yet — signals are recorded automatically when they fire.")

        st.markdown("---")

        # ── Section 2: Historical backtest trades ─────────────────────────────
        trades_to_show = disp_result.closed_trades
        st.markdown(f"### 📊 Historical Backtest Trades ({range_label})")
        st.caption(f"{len(trades_to_show)} trades — newest first")
        hist_rows = []
        for t in sorted(trades_to_show, key=lambda x: x.entry_date, reverse=True):
            hist_rows.append({
                "Entry Date": t.entry_date.strftime("%Y-%m-%d") if t.entry_date else "",
                "Exit Date":  t.exit_date.strftime("%Y-%m-%d")  if t.exit_date  else "—",
                "Type":       "🟢 LONG" if t.direction == 1 else "🔴 SHORT",
                "Entry $":    f"${t.entry_price:,.2f}",
                "Exit $":     f"${t.exit_price:,.2f}" if t.exit_price else "—",
                "PnL %":      f"{t.pnl_pct:+.2f}%" if t.pnl_pct is not None else "—",
                "Result":     "✅ WIN" if t.won else "❌ LOSS",
            })
        if hist_rows:
            st.dataframe(pd.DataFrame(hist_rows), use_container_width=True, height=400)
        else:
            st.caption("No closed trades in this date range.")
    else:
        st.info("Run an analysis first to see backtest results.")

# ═══════════════════════════════════════════════════════════════════════════════
# CHAT TAB
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.active_tab == "Track":
    st.markdown("## 🎯 Track & Auto-Trade")
    st.caption("Add up to 10 coins. Any signal fires a Bybit order automatically — same as the main tab.")

    # ── Add coins ─────────────────────────────────────────────────────────────
    watchlist = get_watchlist()
    can_add   = len(watchlist) < 10

    # Quick-add crypto buttons
    st.markdown("#### ➕ Add Coins to Track")
    tracked_syms = {w["ticker"] for w in watchlist}

    crypto_coins = ["BTC-USDT","ETH-USDT","SOL-USDT","BNB-USDT","XRP-USDT",
                    "ADA-USDT","DOGE-USDT","AVAX-USDT","MATIC-USDT","DOT-USDT"]
    cols_add = st.columns(5)
    for i, sym in enumerate(crypto_coins):
        already = sym in tracked_syms
        label   = f"✓ {sym}" if already else sym
        btn_type = "primary" if already else "secondary"
        if cols_add[i % 5].button(label, key=f"track_add_{sym}",
                                   use_container_width=True, type=btn_type):
            if already:
                remove_ticker(sym)
            else:
                if can_add:
                    add_ticker(sym, "1d")
            st.rerun()

    # Custom ticker input
    st.markdown("<div style='margin-top:6px;'></div>", unsafe_allow_html=True)
    ca1, ca2, ca3 = st.columns([3, 2, 1])
    with ca1:
        custom_sym = st.text_input("Custom ticker", placeholder="e.g. LINK-USD, NEAR-USD",
                                   label_visibility="collapsed", key="track_custom_sym")
    with ca2:
        custom_tf = st.selectbox("Timeframe", ["15m","30m","1h","4h","1d"],
                                 index=4, key="track_custom_tf", label_visibility="collapsed")
    with ca3:
        if st.button("Add", type="primary", use_container_width=True, key="track_custom_btn"):
            if custom_sym.strip() and can_add:
                add_ticker(custom_sym.strip().upper(), custom_tf)
                st.rerun()
            elif not can_add:
                st.warning("Max 10 coins — remove one first")

    watchlist = get_watchlist()
    st.markdown(f"""
    <div style="font-size:0.78rem;color:#6b7280;margin:8px 0 4px;">
      Tracking <b>{len(watchlist)}/10</b> coins &nbsp;·&nbsp;
      Scans every 60s &nbsp;·&nbsp;
      {'<span style="color:#16a34a;font-weight:700;">⚡ Auto-trade ON</span>' if is_configured() else '<span style="color:#f59e0b;">⚠️ Bybit not configured</span>'}
    </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Live tracking grid ────────────────────────────────────────────────────
    if not watchlist:
        st.markdown("""
        <div style="text-align:center;padding:50px;background:#f8f9fc;
             border:1px dashed #e0e4ef;border-radius:12px;color:#6b7280;">
          <div style="font-size:2.5rem;">🎯</div>
          <div style="font-size:1rem;font-weight:600;margin-top:10px;">No coins tracked yet</div>
          <div style="font-size:0.85rem;margin-top:6px;">Click coins above to add them to tracking</div>
        </div>""", unsafe_allow_html=True)
    else:
        @st.fragment(run_every=60)
        def track_scanner():
            wl = get_watchlist()
            for w in wl:
                sym = w["ticker"]
                tf  = w["timeframe"]
                key = f"{sym}|{tf}"

                sig_val = int(w.get("last_signal", 0))
                score_s = float(w.get("last_score", 0.0))
                price_s = float(w.get("last_price", 0.0))
                err = w.get("last_error")

                if price_s == 0.0 and not err:
                    err = "Scanning... (updates every 60s)"

                # ── Render card ───────────────────────────────────────────────
                if err:
                    sig_label, sig_color, t_class = "⚠️ Error", "#f59e0b", "neu-flat"
                elif sig_val == 1:
                    sig_label, sig_color, t_class = "🟢 LONG",  "#16a34a", "neu-flat"
                elif sig_val == -1:
                    sig_label, sig_color, t_class = "🔴 SHORT", "#dc2626", "neu-flat"
                else:
                    sig_label, sig_color, t_class = "⚪ No Signal", "#718096", "neu-flat"

                price_fmt = f"${price_s:,.4f}" if 0 < price_s < 1 else (f"${price_s:,.2f}" if price_s >= 1 else "—")

                # Check if open DB trade exists
                db_t = get_open_trade(sym, tf)
                trade_badge = ""
                if db_t:
                    d_dir = db_t["direction"]
                    d_col = "#16a34a" if d_dir == "LONG" else "#dc2626"
                    lp_now = get_live_price(sym)["price"]
                    if lp_now > 0:
                        mult = 1 if d_dir == "LONG" else -1
                        pnl_pct = (lp_now - db_t["entry_price"]) / db_t["entry_price"] * 100 * mult
                        pnl_col = "#16a34a" if pnl_pct >= 0 else "#dc2626"
                        trade_badge = f'<span style="font-size:0.7rem;background:transparent;box-shadow: inset 2px 2px 5px rgba(163,177,198,0.5), inset -2px -2px 5px rgba(255,255,255,0.5);color:{d_col};border-radius:6px;padding:4px 8px;font-weight:700;">⏳ {d_dir} {pnl_pct:+.2f}%</span>'

                col_card, col_view, col_rm = st.columns([9, 2, 1])
                with col_card:
                    st.markdown(f"""
                    <div class="{t_class}" style="padding:16px 20px;margin-bottom:12px;">
                      <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div>
                          <span style="font-size:1.1rem;font-weight:900;color:#2d3748;">{sym}</span>
                          <span style="font-size:0.75rem;color:#718096;margin-left:6px;">{tf}</span>
                          &nbsp;&nbsp;{trade_badge}
                        </div>
                        <div style="text-align:right;">
                          <span style="font-size:1.1rem;font-weight:900;color:{sig_color};text-shadow: 1px 1px 2px rgba(0,0,0,0.05);">{sig_label}</span>
                        </div>
                      </div>
                      <div style="display:flex;justify-content:space-between;margin-top:8px;font-size:0.85rem;color:#4a5568;">
                        <span>Price &nbsp;<b style="color:#2d3748;">{price_fmt}</b></span>
                        <span>Score &nbsp;<b style="color:{sig_color};">{score_s:+.2f}</b></span>
                        <span></span>
                      </div>
                    </div>""", unsafe_allow_html=True)
                with col_view:
                    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
                    st.button("🔎 View", key=f"tview_{sym}_{tf}", use_container_width=True, help="Load into main chart",
                              on_click=load_tracked_coin, args=(sym, tf))
                with col_rm:
                    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
                    if st.button("✕", key=f"trm_{sym}_{tf}", help=f"Remove {sym}"):
                        remove_ticker(sym)
                        st.rerun()

        track_scanner()

        st.markdown("---")

        # ── Trades taken from tracker ─────────────────────────────────────────
        st.markdown("### 📋 Trades Taken")
        tracked_syms_list = [w["ticker"] for w in watchlist]
        all_track_trades = []
        for sym in tracked_syms_list:
            trades = get_all_trades(sym, "1d", limit=20)
            all_track_trades.extend(trades)

        all_track_trades.sort(key=lambda x: x["entry_date"], reverse=True)

        if all_track_trades:
            rows = []
            for t in all_track_trades[:50]:
                is_open   = t["status"] == "OPEN"
                direction = 1 if t["direction"] == "LONG" else -1
                lp = get_live_price(t["ticker"])["price"] if is_open else 0
                if is_open and lp > 0:
                    pnl_str = f"{(lp - t['entry_price']) / t['entry_price'] * 100 * direction:+.2f}% (live)"
                    result_str = "⏳ OPEN"
                elif t["pnl_pct"] is not None:
                    pnl_str = f"{t['pnl_pct']:+.2f}%"
                    result_str = {"TP_HIT": "🎯 TP", "SL_HIT": "🛑 SL", "MANUAL": "✋"}.get(t["status"], "✅" if t["pnl_pct"] > 0 else "❌")
                else:
                    pnl_str, result_str = "—", "—"

                rows.append({
                    "Result":  result_str,
                    "Coin":    t["ticker"],
                    "Type":    f"🟢 {t['direction']}" if t["direction"] == "LONG" else f"🔴 {t['direction']}",
                    "Entry":   t["entry_date"][:16],
                    "Entry $": f"${t['entry_price']:,.4f}" if t['entry_price'] < 1 else f"${t['entry_price']:,.2f}",
                    "PnL %":   pnl_str,
                    "SL $":    f"${t['sl_price']:,.4f}" if t['sl_price'] < 1 else f"${t['sl_price']:,.2f}",
                    "TP $":    f"${t['tp_price']:,.4f}" if t['tp_price'] < 1 else f"${t['tp_price']:,.2f}",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, height=300)
        else:
            st.caption("No trades yet — they appear here as signals fire for tracked coins.")

# ═══════════════════════════════════════════════════════════════════════════════
# BYBIT TAB
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.active_tab == "Bybit":
    st.markdown("## 🟡 Bybit Demo Trading")

    if not is_configured():
        st.warning("Bybit API not configured. Add keys to .env file.")
    else:
        @st.fragment(run_every=10)
        def bybit_tab_content():
            # ── Balance ───────────────────────────────────────────────────────
            bal = get_balance()
            c1, c2, c3 = st.columns(3)
            if bal["ok"]:
                pnl_c = "#16a34a" if bal["unrealised_pnl"] >= 0 else "#dc2626"
                with c1:
                    st.markdown(f"""<div class="lvl" style="border-top:3px solid #f59e0b;">
                      <div class="lvl-lbl">💰 USDT Balance</div>
                      <div class="lvl-val" style="color:#111827;">${bal['equity']:,.2f}</div>
                    </div>""", unsafe_allow_html=True)
                with c2:
                    st.markdown(f"""<div class="lvl" style="border-top:3px solid #f59e0b;">
                      <div class="lvl-lbl">💵 Available</div>
                      <div class="lvl-val" style="color:#111827;">${bal['available']:,.2f}</div>
                    </div>""", unsafe_allow_html=True)
                with c3:
                    st.markdown(f"""<div class="lvl" style="border-top:3px solid {pnl_c};">
                      <div class="lvl-lbl">📈 Unrealised PnL</div>
                      <div class="lvl-val" style="color:{pnl_c};">{'+' if bal['unrealised_pnl']>=0 else ''}{bal['unrealised_pnl']:.2f}</div>
                    </div>""", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Live Positions ────────────────────────────────────────────────
            st.markdown("### 📌 Live Open Positions")
            positions = get_positions()
            if positions:
                for p in positions:
                    pnl     = p["unrealised_pnl"]
                    pnl_pct = (p["mark_price"] - p["entry_price"]) / p["entry_price"] * 100
                    if p["side"] == "Sell":
                        pnl_pct = -pnl_pct
                    pc  = "#16a34a" if pnl >= 0 else "#dc2626"
                    bg  = "#f0fff4" if pnl >= 0 else "#fff5f5"
                    bc  = "#22c55e" if pnl >= 0 else "#ef4444"
                    tag = "▲ LONG" if p["side"] == "Buy" else "▼ SHORT"
                    tag_c = "#16a34a" if p["side"] == "Buy" else "#dc2626"

                    col_info, col_btn = st.columns([5, 1])
                    with col_info:
                        st.markdown(f"""
                        <div style="background:{bg};border-left:5px solid {bc};border-radius:10px;
                             padding:14px 16px;margin-bottom:8px;">
                          <div style="display:flex;justify-content:space-between;align-items:baseline;">
                            <span style="font-size:1.1rem;font-weight:900;color:#111827;">{p['symbol']}</span>
                            <span style="font-size:1.3rem;font-weight:900;color:{pc};">{pnl_pct:+.2f}%</span>
                          </div>
                          <div style="display:flex;justify-content:space-between;margin-top:4px;">
                            <span style="font-weight:700;color:{tag_c};font-size:0.82rem;">{tag} · Size {p['size']}</span>
                            <span style="font-weight:700;color:{pc};font-size:0.82rem;">{'+' if pnl>=0 else ''}{pnl:.2f} USDT</span>
                          </div>
                          <div style="display:flex;justify-content:space-between;margin-top:6px;font-size:0.78rem;color:#374151;">
                            <span>Entry: <b>${p['entry_price']:,.4f}</b></span>
                            <span>Mark: <b>${p['mark_price']:,.4f}</b></span>
                            <span>Leverage: <b>{p['leverage']:.0f}×</b></span>
                          </div>
                          <div style="display:flex;gap:16px;margin-top:4px;font-size:0.72rem;">
                            <span style="color:#dc2626;">🛑 SL: ${p['sl']:,.4f}</span>
                            <span style="color:#16a34a;">🎯 TP: ${p['tp']:,.4f}</span>
                          </div>
                        </div>""", unsafe_allow_html=True)
                    with col_btn:
                        st.markdown("<div style='margin-top:18px;'></div>", unsafe_allow_html=True)
                        from data.bybit_client import SYMBOL_MAP
                        yf_sym = next((k for k,v in SYMBOL_MAP.items() if v == p["symbol"]), None)
                        if yf_sym and st.button("Close", key=f"bybit_close_{p['symbol']}", type="primary"):
                            res = close_position(yf_sym)
                            if res["ok"]:
                                st.success("✅ Position closed!")
                            else:
                                st.error(f"❌ {res['error']}")
                            st.rerun()
            else:
                st.markdown("""
                <div style="text-align:center;padding:30px;background:#f8f9fc;
                     border:1px dashed #e0e4ef;border-radius:12px;color:#6b7280;">
                  <div style="font-size:2rem;">📭</div>
                  <div style="margin-top:8px;font-weight:600;">No open positions</div>
                  <div style="font-size:0.82rem;margin-top:4px;">
                    Auto-trade is ON — a position will open automatically when the next signal fires
                  </div>
                </div>""", unsafe_allow_html=True)

            st.markdown("---")

            # ── Past Trades ───────────────────────────────────────────────────
            st.markdown("### 📒 Past Trades (Closed PnL)")
            history = get_trade_history(limit=30)
            if history:
                total_pnl = sum(h["pnl"] for h in history)
                wins      = sum(1 for h in history if h["won"])
                wr        = wins / len(history) * 100 if history else 0

                mc1, mc2, mc3 = st.columns(3)
                for col, val, lbl, ok in [
                    (mc1, f"{wr:.1f}%",          "Win Rate",  wr >= 50),
                    (mc2, str(len(history)),       "Trades",    True),
                    (mc3, f"{total_pnl:+.2f} USDT","Total PnL", total_pnl >= 0),
                ]:
                    color = "#16a34a" if ok else "#dc2626"
                    with col:
                        st.markdown(f"""<div class="lvl">
                          <div class="lvl-lbl">{lbl}</div>
                          <div class="lvl-val" style="color:{color};font-size:1.1rem;">{val}</div>
                        </div>""", unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)
                rows = []
                for h in history:
                    ts = h["created_at"]
                    try:
                        ts = pd.to_datetime(int(ts), unit="ms").strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        ts = str(ts)[:16]
                    rows.append({
                        "Time":    ts,
                        "Symbol":  h["symbol"],
                        "Side":    "🟢 LONG" if h["side"] == "Buy" else "🔴 SHORT",
                        "Qty":     h["qty"],
                        "Entry $": f"${h['entry']:,.4f}",
                        "Exit $":  f"${h['exit']:,.4f}",
                        "PnL":     f"{'+' if h['pnl']>=0 else ''}{h['pnl']:.4f} USDT",
                        "Result":  "✅ WIN" if h["won"] else "❌ LOSS",
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, height=400)
            else:
                st.markdown("""
                <div style="text-align:center;padding:30px;background:#f8f9fc;
                     border:1px dashed #e0e4ef;border-radius:12px;color:#6b7280;">
                  <div style="font-size:2rem;">📊</div>
                  <div style="margin-top:8px;font-weight:600;">No completed trades yet</div>
                  <div style="font-size:0.82rem;margin-top:4px;">
                    Past trades appear here after SL or TP is hit on Bybit
                  </div>
                </div>""", unsafe_allow_html=True)

            st.markdown("---")
            st.caption("🔄 Auto-refreshes every 10 seconds · 2× leverage · 10% balance per trade · Bybit Demo")

        bybit_tab_content()
