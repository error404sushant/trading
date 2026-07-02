"""
Bybit Demo Trading integration.
Connects via pybit v5 unified trading API.
Credentials loaded from .env — never hardcoded.

Supports:
  - Place perpetual LONG/SHORT with SL + TP in one call
  - Fetch open positions
  - Close position by market order
  - Account balance (USDT)
  - Symbol mapping from Yahoo Finance tickers → Bybit symbols
"""
import os
from dotenv import load_dotenv

load_dotenv()

_API_KEY    = os.getenv("BYBIT_API_KEY", "")
_API_SECRET = os.getenv("BYBIT_API_SECRET", "")
_IS_DEMO    = os.getenv("BYBIT_DEMO", "true").lower() == "true"

# Yahoo Finance → Bybit perpetual symbol
SYMBOL_MAP = {
    "BTC-USD":   "BTCUSDT",
    "ETH-USD":   "ETHUSDT",
    "SOL-USD":   "SOLUSDT",
    "BNB-USD":   "BNBUSDT",
    "XRP-USD":   "XRPUSDT",
    "ADA-USD":   "ADAUSDT",
    "DOGE-USD":  "DOGEUSDT",
    "AVAX-USD":  "AVAXUSDT",
    "MATIC-USD": "MATICUSDT",
    "DOT-USD":   "DOTUSDT",
}

_session = None


def _get_session():
    global _session
    if _session is None:
        try:
            from pybit.unified_trading import HTTP
            _session = HTTP(
                testnet=False,
                demo=_IS_DEMO,
                api_key=_API_KEY,
                api_secret=_API_SECRET,
            )
        except Exception as e:
            return None, str(e)
    return _session, None


def is_configured() -> bool:
    return bool(_API_KEY and _API_SECRET)


def get_bybit_symbol(yf_ticker: str) -> str | None:
    return SYMBOL_MAP.get(yf_ticker)


def get_balance() -> dict:
    """Return USDT wallet balance."""
    session, err = _get_session()
    if err:
        return {"ok": False, "error": err}
    try:
        r = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        coins = r["result"]["list"][0]["coin"]
        usdt  = next((c for c in coins if c["coin"] == "USDT"), None)
        if usdt:
            def _f(v): return float(v) if v and v != "" else 0.0
            return {
                "ok":             True,
                "equity":         _f(usdt.get("equity")),
                "available":      _f(usdt.get("availableToWithdraw")),
                "unrealised_pnl": _f(usdt.get("unrealisedPnl")),
            }
        return {"ok": False, "error": "USDT not found in wallet"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_positions() -> list:
    """Return all open perpetual positions."""
    session, err = _get_session()
    if err:
        return []
    try:
        r = session.get_positions(category="linear", settleCoin="USDT")
        positions = []
        def _f(v, default=0.0):
            try: return float(v) if v and v != "" else default
            except: return default

        for p in r["result"]["list"]:
            size = _f(p.get("size"))
            if size == 0:
                continue
            positions.append({
                "symbol":         p["symbol"],
                "side":           p["side"],
                "size":           size,
                "entry_price":    _f(p.get("avgPrice")),
                "mark_price":     _f(p.get("markPrice")),
                "unrealised_pnl": _f(p.get("unrealisedPnl")),
                "liq_price":      _f(p.get("liqPrice")),
                "leverage":       _f(p.get("leverage"), 1.0),
                "sl":             _f(p.get("stopLoss")),
                "tp":             _f(p.get("takeProfit")),
            })
        return positions
    except Exception:
        return []


def set_leverage(yf_ticker: str, leverage: int = 2) -> dict:
    """Set leverage for a symbol. Called before placing order."""
    symbol = get_bybit_symbol(yf_ticker)
    if not symbol:
        return {"ok": False, "error": "Symbol not found"}
    session, err = _get_session()
    if err:
        return {"ok": False, "error": err}
    try:
        r = session.set_leverage(
            category="linear",
            symbol=symbol,
            buyLeverage=str(leverage),
            sellLeverage=str(leverage),
        )
        # retCode 110043 = leverage not modified (already set) — that's fine
        if r["retCode"] in (0, 110043):
            return {"ok": True}
        return {"ok": False, "error": r.get("retMsg", "Unknown")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def calc_qty(yf_ticker: str, price: float, balance_pct: float = 0.10, leverage: int = 2) -> float:
    """
    Calculate order quantity using % of balance × leverage.
    balance_pct=0.10 means use 10% of available USDT.
    Returns qty rounded to exchange step size.
    """
    bal = get_balance()
    if not bal["ok"] or bal["equity"] <= 0:
        return 0.0

    usdt_to_use    = bal["equity"] * balance_pct   # 10% of balance
    position_value = usdt_to_use * leverage         # × 2x leverage
    raw_qty        = position_value / price

    # Get step size from exchange
    step = get_qty_step(yf_ticker)
    if step <= 0:
        step = 0.001

    # Round DOWN to nearest step
    qty = int(raw_qty / step) * step
    qty = round(qty, 8)
    return max(qty, step)   # at least minimum step


def get_qty_step(yf_ticker: str) -> float:
    """Get the qty step size for a symbol (e.g. 0.001 for BTC)."""
    symbol = get_bybit_symbol(yf_ticker)
    if not symbol:
        return 0.001
    session, err = _get_session()
    if err:
        return 0.001
    try:
        r = session.get_instruments_info(category="linear", symbol=symbol)
        info = r["result"]["list"][0]["lotSizeFilter"]
        return float(info.get("qtyStep", 0.001))
    except Exception:
        return 0.001


def place_order(
    yf_ticker: str,
    direction: str,    # "LONG" or "SHORT"
    qty: float,
    sl_price: float,
    tp_price: float,
    leverage: int = 2,
) -> dict:
    """
    Set leverage then place a market perpetual order with SL and TP.
    Returns {"ok": True, "order_id": "...", "qty": qty} or {"ok": False, "error": "..."}
    """
    symbol = get_bybit_symbol(yf_ticker)
    if not symbol:
        return {"ok": False, "error": f"{yf_ticker} not supported on Bybit perpetual"}

    session, err = _get_session()
    if err:
        return {"ok": False, "error": err}

    # Set leverage first
    set_leverage(yf_ticker, leverage)

    side = "Buy" if direction == "LONG" else "Sell"

    # Format prices to reasonable precision
    sl_str = f"{sl_price:.4f}" if sl_price < 10 else f"{sl_price:.2f}"
    tp_str = f"{tp_price:.4f}" if tp_price < 10 else f"{tp_price:.2f}"
    qty_str = f"{qty:.6f}".rstrip("0").rstrip(".")

    try:
        r = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            orderType="Market",
            qty=qty_str,
            stopLoss=sl_str,
            takeProfit=tp_str,
            slTriggerBy="MarkPrice",
            tpTriggerBy="MarkPrice",
            timeInForce="IOC",
            reduceOnly=False,
        )
        if r["retCode"] == 0:
            return {"ok": True, "order_id": r["result"]["orderId"], "symbol": symbol, "qty": qty}
        return {"ok": False, "error": f"[{r['retCode']}] {r.get('retMsg', 'Unknown error')}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def close_position(yf_ticker: str) -> dict:
    """Close the open position for a symbol using a market reduce-only order."""
    symbol = get_bybit_symbol(yf_ticker)
    if not symbol:
        return {"ok": False, "error": f"{yf_ticker} not on Bybit"}

    session, err = _get_session()
    if err:
        return {"ok": False, "error": err}

    # Get current position size and side
    positions = get_positions()
    pos = next((p for p in positions if p["symbol"] == symbol), None)
    if not pos:
        return {"ok": False, "error": "No open position found"}

    # Closing side is opposite of position side
    close_side = "Sell" if pos["side"] == "Buy" else "Buy"

    try:
        r = session.place_order(
            category="linear",
            symbol=symbol,
            side=close_side,
            orderType="Market",
            qty=str(pos["size"]),
            timeInForce="IOC",
            reduceOnly=True,
        )
        if r["retCode"] == 0:
            return {"ok": True, "order_id": r["result"]["orderId"]}
        return {"ok": False, "error": r.get("retMsg", "Unknown error")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_min_qty(yf_ticker: str) -> float:
    """Get minimum order quantity for a symbol."""
    symbol = get_bybit_symbol(yf_ticker)
    if not symbol:
        return 0.0
    session, err = _get_session()
    if err:
        return 0.0
    try:
        r = session.get_instruments_info(category="linear", symbol=symbol)
        info = r["result"]["list"][0]["lotSizeFilter"]
        return float(info.get("minOrderQty", 0.001))
    except Exception:
        return 0.001


def get_trade_history(limit: int = 20) -> list:
    """Fetch closed PnL history from Bybit (past completed trades)."""
    session, err = _get_session()
    if err:
        return []
    try:
        r = session.get_closed_pnl(category="linear", limit=limit)
        trades = []
        def _f(v, d=0.0):
            try: return float(v) if v and v != "" else d
            except: return d
        for t in r["result"]["list"]:
            pnl = _f(t.get("closedPnl"))
            trades.append({
                "symbol":     t.get("symbol", ""),
                "side":       t.get("side", ""),
                "qty":        _f(t.get("qty")),
                "entry":      _f(t.get("avgEntryPrice")),
                "exit":       _f(t.get("avgExitPrice")),
                "pnl":        pnl,
                "pnl_pct":    _f(t.get("closedPnl")),
                "created_at": t.get("createdTime", ""),
                "won":        pnl > 0,
            })
        return trades
    except Exception:
        return []
