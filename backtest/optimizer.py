"""
Optimizer — finds SL/TP that maximises win rate × profit factor × Sharpe bonus.
Enforces minimum R:R of 1.5 and minimum 10 trades.
"""
import itertools
from backtest.engine import run_backtest
import streamlit as st


@st.cache_data(show_spinner=False)
def optimize(df):
    sl_values = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
    tp_values = [2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0]

    best_score  = -1
    best_params = {"stop_loss_pct": 2.0, "take_profit_pct": 4.0}
    best_result = None

    for sl, tp in itertools.product(sl_values, tp_values):
        if tp / sl < 1.5:
            continue
        result = run_backtest(df, stop_loss_pct=sl, take_profit_pct=tp)
        if result.n_trades < 10:
            continue
        sharpe_bonus = max(0, result.sharpe) / 10
        score = (result.win_rate / 100) * result.profit_factor * (1 + sharpe_bonus)
        if score > best_score:
            best_score  = score
            best_params = {"stop_loss_pct": sl, "take_profit_pct": tp}
            best_result = result

    return {"params": best_params, "result": best_result, "score": best_score}
