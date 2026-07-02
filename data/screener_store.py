"""
Screener watchlist + alert history — persisted in the same trades.db.
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "trades.db")


def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_screener():
    with _conn() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS screener_watchlist (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker    TEXT NOT NULL UNIQUE,
            timeframe TEXT NOT NULL DEFAULT '1d',
            added_at  TEXT NOT NULL
        )""")
        con.execute("""
        CREATE TABLE IF NOT EXISTS screener_alerts (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker    TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            signal    TEXT NOT NULL,
            score     REAL,
            price     REAL,
            fired_at  TEXT NOT NULL
        )""")


def add_ticker(ticker: str, timeframe: str = "1d"):
    init_screener()
    with _conn() as con:
        try:
            con.execute(
                "INSERT INTO screener_watchlist (ticker, timeframe, added_at) VALUES (?,?,?)",
                (ticker.upper(), timeframe, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
            )
        except sqlite3.IntegrityError:
            # Already in watchlist — update timeframe
            con.execute(
                "UPDATE screener_watchlist SET timeframe=? WHERE ticker=?",
                (timeframe, ticker.upper())
            )


def remove_ticker(ticker: str):
    init_screener()
    with _conn() as con:
        con.execute("DELETE FROM screener_watchlist WHERE ticker=?", (ticker.upper(),))


def get_watchlist():
    init_screener()
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM screener_watchlist ORDER BY added_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def log_alert(ticker: str, timeframe: str, signal: str, score: float, price: float):
    init_screener()
    with _conn() as con:
        con.execute(
            "INSERT INTO screener_alerts (ticker, timeframe, signal, score, price, fired_at) "
            "VALUES (?,?,?,?,?,?)",
            (ticker, timeframe, signal, score, price,
             datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
        )


def get_recent_alerts(limit: int = 50):
    init_screener()
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM screener_alerts ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
