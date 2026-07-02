"""
Local SQLite trade store.
Persists real signal-based trades across refreshes.
Once entered, entry price never changes.
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "trades.db")


def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with _conn() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT    NOT NULL,
            timeframe   TEXT    NOT NULL,
            direction   TEXT    NOT NULL,   -- LONG / SHORT
            entry_date  TEXT    NOT NULL,
            entry_price REAL    NOT NULL,
            sl_price    REAL    NOT NULL,
            tp_price    REAL    NOT NULL,
            sl_pct      REAL    NOT NULL,
            tp_pct      REAL    NOT NULL,
            signal_score REAL,
            exit_date   TEXT,
            exit_price  REAL,
            pnl_pct     REAL,
            status      TEXT    DEFAULT 'OPEN',  -- OPEN / TP_HIT / SL_HIT / MANUAL
            quantity    REAL    DEFAULT 1.0       -- always 1 unit
        )""")


def get_open_trade(ticker: str, timeframe: str):
    """Return the current open trade for ticker+timeframe, or None."""
    init_db()
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM trades WHERE ticker=? AND timeframe=? AND status='OPEN' ORDER BY id DESC LIMIT 1",
            (ticker, timeframe)
        ).fetchone()
    return dict(row) if row else None


def open_trade(ticker: str, timeframe: str, direction: str,
               entry_price: float, sl_price: float, tp_price: float,
               sl_pct: float, tp_pct: float, signal_score: float = 0.0):
    """
    Record a new trade. Only allowed if no OPEN trade exists for this ticker+timeframe.
    Returns (trade_id, is_new): is_new=True if just created, False if already existed.
    """
    init_db()
    existing = get_open_trade(ticker, timeframe)
    if existing:
        return existing["id"], False   # already open — don't overwrite

    entry_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO trades
               (ticker, timeframe, direction, entry_date, entry_price,
                sl_price, tp_price, sl_pct, tp_pct, signal_score)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (ticker, timeframe, direction, entry_date, entry_price,
             sl_price, tp_price, sl_pct, tp_pct, signal_score)
        )
        return cur.lastrowid, True


def close_trade(trade_id: int, exit_price: float, status: str):
    """Close a trade with exit price and status (TP_HIT / SL_HIT / MANUAL)."""
    with _conn() as con:
        row = con.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
        if not row:
            return
        t = dict(row)
        direction = 1 if t["direction"] == "LONG" else -1
        pnl_pct = (exit_price - t["entry_price"]) / t["entry_price"] * 100 * direction
        exit_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        con.execute(
            "UPDATE trades SET exit_date=?, exit_price=?, pnl_pct=?, status=? WHERE id=?",
            (exit_date, exit_price, pnl_pct, status, trade_id)
        )


def maybe_auto_close(trade_id: int, live_price: float):
    """Check if live price hit SL or TP and auto-close if so."""
    with _conn() as con:
        row = con.execute("SELECT * FROM trades WHERE id=? AND status='OPEN'", (trade_id,)).fetchone()
        if not row:
            return None
        t = dict(row)
    direction = 1 if t["direction"] == "LONG" else -1
    pnl_pct = (live_price - t["entry_price"]) / t["entry_price"] * 100 * direction

    if pnl_pct <= -t["sl_pct"]:
        close_trade(trade_id, live_price, "SL_HIT")
        return "SL_HIT"
    if pnl_pct >= t["tp_pct"]:
        close_trade(trade_id, live_price, "TP_HIT")
        return "TP_HIT"
    return None


def get_all_trades(ticker: str, timeframe: str, limit: int = 100):
    """Return all trades newest first."""
    init_db()
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM trades WHERE ticker=? AND timeframe=? ORDER BY id DESC LIMIT ?",
            (ticker, timeframe, limit)
        ).fetchall()
    return [dict(r) for r in rows]
