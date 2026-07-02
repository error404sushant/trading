import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List


@dataclass
class Trade:
    entry_date: pd.Timestamp
    entry_price: float
    direction: int          # 1 = long, -1 = short
    exit_date: pd.Timestamp = None
    exit_price: float = None
    pnl_pct: float = None
    won: bool = None


@dataclass
class BacktestResult:
    trades: List[Trade] = field(default_factory=list)
    equity: pd.Series = None

    @property
    def n_trades(self): return len(self.trades)

    @property
    def closed_trades(self):
        return [t for t in self.trades if t.exit_date is not None]

    @property
    def open_trades(self):
        return [t for t in self.trades if t.exit_date is None]

    @property
    def n_trades(self): return len(self.closed_trades)

    @property
    def win_rate(self):
        closed = self.closed_trades
        if not closed: return 0.0
        wins = sum(1 for t in closed if t.won)
        return wins / len(closed) * 100

    @property
    def total_return(self):
        if self.equity is None or self.equity.empty: return 0.0
        return (self.equity.iloc[-1] / self.equity.iloc[0] - 1) * 100

    @property
    def max_drawdown(self):
        if self.equity is None or self.equity.empty: return 0.0
        roll_max = self.equity.cummax()
        dd = (self.equity - roll_max) / roll_max
        return dd.min() * 100

    @property
    def sharpe(self):
        if self.equity is None or len(self.equity) < 2: return 0.0
        rets = self.equity.pct_change().dropna()
        if rets.std() == 0: return 0.0
        return (rets.mean() / rets.std()) * np.sqrt(252)

    @property
    def profit_factor(self):
        closed = self.closed_trades
        gross_profit = sum(t.pnl_pct for t in closed if t.pnl_pct and t.pnl_pct > 0)
        gross_loss   = abs(sum(t.pnl_pct for t in closed if t.pnl_pct and t.pnl_pct < 0))
        if gross_loss == 0: return float("inf")
        return gross_profit / gross_loss

    @property
    def avg_win(self):
        wins = [t.pnl_pct for t in self.closed_trades if t.won]
        return np.mean(wins) if wins else 0.0

    @property
    def avg_loss(self):
        losses = [t.pnl_pct for t in self.closed_trades if not t.won and t.pnl_pct is not None]
        return np.mean(losses) if losses else 0.0


def run_backtest(
    df: pd.DataFrame,
    stop_loss_pct: float = 2.0,
    take_profit_pct: float = 4.0,
    initial_capital: float = 10_000.0,
) -> BacktestResult:
    """
    Simple signal-based backtest.
    Uses df['signal'] column: 1=buy, -1=sell, 0=flat.
    Applies stop-loss and take-profit per trade.
    """
    result = BacktestResult()
    capital = initial_capital
    equity_curve = []
    in_trade = False
    current_trade: Trade = None

    for i, (ts, row) in enumerate(df.iterrows()):
        price = row["close"]
        sig   = row.get("signal", 0)

        if in_trade and current_trade is not None:
            direction = current_trade.direction
            entry     = current_trade.entry_price
            pnl_pct   = (price - entry) / entry * 100 * direction

            hit_sl = pnl_pct <= -stop_loss_pct
            hit_tp = pnl_pct >= take_profit_pct
            reversal = (sig == -direction)

            if hit_sl or hit_tp or reversal:
                current_trade.exit_date  = ts
                current_trade.exit_price = price
                current_trade.pnl_pct    = pnl_pct
                current_trade.won        = pnl_pct > 0
                capital *= (1 + pnl_pct / 100)
                result.trades.append(current_trade)
                in_trade = False
                current_trade = None

        if not in_trade and sig in (1, -1):
            current_trade = Trade(entry_date=ts, entry_price=price, direction=sig)
            in_trade = True

        equity_curve.append(capital)

    # Save any open trade at end of data
    if in_trade and current_trade is not None:
        result.trades.append(current_trade)  # exit_date/exit_price/pnl_pct remain None = open

    result.equity = pd.Series(equity_curve, index=df.index)
    return result
