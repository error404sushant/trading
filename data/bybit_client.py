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


def place_order(
    yf_ticker: str,
    direction: str,      # "LONG" or "SHORT"
    qty: float,          # quantity in base currency (e.g. 0.01 BTC)
    sl_price: float,
    tp_price: float,
) -> dict:
    """
    Place a market perpetual order with SL and TP.
    Returns {"ok": True, "order_id": "..."} or {"ok": False, "error": "..."}
    """
    symbol = get_bybit_symbol(yf_ticker)
    if not symbol:
        return {"ok": False, "error": f"{yf_ticker} not supported on Bybit perpetual"}

    session, err = _get_session()
    if err:
        return {"ok": False, "error": err}

    side = "Buy" if direction == "LONG" else "Sell"

    try:
        r = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            orderType="Market",
            qty=str(round(qty, 6)),
            stopLoss=str(round(sl_price, 2)),
            takeProfit=str(round(tp_price, 2)),
            slTriggerBy="MarkPrice",
            tpTriggerBy="MarkPrice",
            timeInForce="IOC",
            reduceOnly=False,
        )
        if r["retCode"] == 0:
            return {"ok": True, "order_id": r["result"]["orderId"], "symbol": symbol}
        return {"ok": False, "error": r.get("retMsg", "Unknown error")}
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
