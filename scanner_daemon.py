import sys
import os
import time
import pandas as pd
import numpy as np

# Ensure root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.fetcher import fetch_ohlcv, get_live_price, fetch_open_interest
from data.trade_store import open_trade, get_open_trade, init_db
from data.screener_store import init_screener, get_watchlist, update_watchlist_status
from data.bybit_client import is_configured, place_order, get_bybit_symbol, calc_qty
from indicators.signals import generate_signals

init_db()
init_screener()

print("Background Watchlist Scanner Daemon started...")

# Keep track of last processed signal in memory to prevent double trigger on reboot
last_signal_keys = {}

while True:
    try:
        watchlist = get_watchlist()
        if not watchlist:
            time.sleep(60)
            continue
            
        for w in watchlist:
            sym = w["ticker"]
            tf  = w["timeframe"]
            key = f"{sym}|{tf}"
            
            # Map ticker to YF format (e.g. BTC-USDT -> BTC-USD)
            yf_sym = sym
            if yf_sym.endswith("-USDT"):
                yf_sym = yf_sym.replace("-USDT", "-USD")
                
            try:
                oi = fetch_open_interest(yf_sym, interval=tf)
                df = generate_signals(fetch_ohlcv(yf_sym, interval=tf), oi_series=oi if not oi.empty else None)
                if df.empty:
                    update_watchlist_status(sym, 0.0, 0, 0.0, error="Empty OHLCV data")
                    continue
                last_row = df.iloc[-1]
                sig = int(last_row["signal"])
                score = float(last_row["score"])
                
                # Check live price
                live = get_live_price(yf_sym)
                price = live["price"] if live["price"] > 0 else float(last_row["close"])
                
                # Update cache in DB
                update_watchlist_status(sym, price, sig, score, error=None)
                
                # Standard parameters for background trading
                used_sl = 2.0
                used_tp = 4.0
                
                if sig != 0 and price > 0 and is_configured() and get_bybit_symbol(yf_sym):
                    direction = "LONG" if sig == 1 else "SHORT"
                    
                    # Prevent double order placement in same session
                    order_key = f"{sym}|{direction}|{price:.2f}"
                    if last_signal_keys.get(key) == order_key:
                         continue
                         
                    # Also check DB to make sure we don't have an open trade
                    db_trade = get_open_trade(yf_sym, tf)
                    if db_trade:
                        continue
                        
                    # Calculate levels
                    if direction == "LONG":
                        sl_p = price * (1 - used_sl / 100)
                        tp_p = price * (1 + used_tp / 100)
                    else:
                        sl_p = price * (1 + used_sl / 100)
                        tp_p = price * (1 - used_tp / 100)
                        
                    # Log trade in DB to keep state consistency
                    trade_id, is_new = open_trade(yf_sym, tf, direction, price, sl_p, tp_p, used_sl, used_tp, score)
                    
                    if is_new:
                        qty = calc_qty(yf_sym, price, balance_pct=0.10, leverage=2)
                        if qty > 0:
                            res = place_order(yf_sym, direction, qty, sl_p, tp_p, leverage=2)
                            last_signal_keys[key] = order_key
                            if res["ok"]:
                                print(f"✅ Placed Bybit {direction} order for {sym} (Qty: {qty})")
                            else:
                                print(f"❌ Failed to place Bybit order for {sym}: {res['error']}")
                        else:
                            print(f"❌ Calculated quantity was zero for {sym}")
            except Exception as e:
                print(f"Error scanning {sym}: {e}")
                update_watchlist_status(sym, 0.0, 0, 0.0, error=str(e))
                
    except Exception as e:
        print(f"Daemon loop error: {e}")
        
    time.sleep(60)
