"""
海龟交易策略引擎
从已有 _gen_turtle.py 提取核心逻辑，支持参数动态配置
"""

import numpy as np
import pandas as pd


# ========== 参数预设方案 ==========

PRESETS = {
    '经典海龟': {
        'entry_period': 20,
        'exit_period': 10,
        'atr_period': 20,
        'risk_pct': 1.0,
        'stop_mult': 2.0,
        'max_units': 4,
        'add_interval': 0.5,
    },
    '保守型': {
        'entry_period': 30,
        'exit_period': 15,
        'atr_period': 20,
        'risk_pct': 0.5,
        'stop_mult': 3.0,
        'max_units': 2,
        'add_interval': 1.0,
    },
    '激进型': {
        'entry_period': 15,
        'exit_period': 7,
        'atr_period': 15,
        'risk_pct': 2.0,
        'stop_mult': 1.5,
        'max_units': 6,
        'add_interval': 0.5,
    },
}


# ========== 指标计算 ==========

def calc_channels(df: pd.DataFrame, entry_period: int, exit_period: int) -> pd.DataFrame:
    """计算 Donchian 通道（排除当日）"""
    df = df.copy()
    # 入场通道：过去 N 日最高价（不含当日）
    df['upper_channel'] = df['high'].rolling(window=entry_period).max().shift(1)
    # 离场通道：过去 M 日最低价（不含当日）
    df['lower_channel'] = df['low'].rolling(window=exit_period).min().shift(1)
    return df


def calc_atr(df: pd.DataFrame, atr_period: int) -> pd.DataFrame:
    """计算 ATR"""
    df = df.copy()
    high = df['high']
    low = df['low']
    pre_close = df['pre_close']

    tr1 = high - low
    tr2 = (high - pre_close).abs()
    tr3 = (low - pre_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=atr_period).mean()
    return df


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """生成买卖止损信号"""
    df = df.copy()
    df['buy_signal'] = df['close'] > df['upper_channel']
    df['sell_signal'] = df['close'] < df['lower_channel']
    return df


# ========== 回测引擎 ==========

def turtle_backtest(df: pd.DataFrame, params: dict) -> tuple:
    """
    海龟策略回测
    返回: (df_with_signals, trades_df, equity_df, metrics_dict, buy_markers, sell_markers, stop_markers)
    """
    entry_period = params['entry_period']
    exit_period = params['exit_period']
    atr_period = params['atr_period']
    risk_pct = params['risk_pct'] / 100.0
    stop_mult = params['stop_mult']
    max_units = params['max_units']
    add_interval = params['add_interval']
    initial_capital = params['initial_capital']
    commission_rate = params['commission_rate']
    stamp_duty = params['stamp_duty']
    min_commission = params['min_commission']
    lot_size = params['lot_size']
    risk_free_rate = params['risk_free_rate'] / 100.0

    # 计算指标
    df = calc_channels(df, entry_period, exit_period)
    df = calc_atr(df, atr_period)
    df = generate_signals(df)

    # 回测
    capital = initial_capital
    position = 0  # 持仓股数
    holdings = []  # 每笔买入记录: [{'price':, 'shares':, 'date':}]
    stop_price = None
    trades = []  # 交易明细
    equity_curve = []  # 每日净值
    buy_markers = []
    sell_markers = []
    stop_markers = []
    total_fees = 0

    for i in range(len(df)):
        row = df.iloc[i]
        date = row['trade_date']
        close = row['close']
        atr = row['atr']
        upper = row['upper_channel']
        lower = row['lower_channel']

        # 跳过 NaN（通道/ATR 还没算出来）
        if pd.isna(atr) or pd.isna(upper) or pd.isna(lower):
            equity = capital + position * close
            equity_curve.append({
                'trade_date': date,
                'equity': equity,
                'nav': equity / initial_capital,
                'position': position,
                'drawdown': 0,
            })
            continue

        # 检查止损
        if position > 0 and stop_price is not None and close < stop_price:
            # 止损清仓
            fee = max(position * close * commission_rate, min_commission) + position * close * stamp_duty
            capital += position * close - fee
            total_fees += fee
            stop_markers.append((date, close))
            trades.append({
                'trade_date': date,
                'type': '止损',
                'price': round(close, 2),
                'shares': position,
                'amount': round(position * close, 2),
                'fee': round(fee, 2),
                'capital_after': round(capital, 2),
            })
            position = 0
            holdings = []
            stop_price = None

        # 检查卖出信号
        elif position > 0 and close < lower:
            fee = max(position * close * commission_rate, min_commission) + position * close * stamp_duty
            capital += position * close - fee
            total_fees += fee
            sell_markers.append((date, close))
            trades.append({
                'trade_date': date,
                'type': '卖出',
                'price': round(close, 2),
                'shares': position,
                'amount': round(position * close, 2),
                'fee': round(fee, 2),
                'capital_after': round(capital, 2),
            })
            position = 0
            holdings = []
            stop_price = None

        # 检查买入信号
        elif close > upper:
            current_units = len(holdings)
            if current_units < max_units:
                # 计算单位仓位
                risk_amount = capital * risk_pct
                unit_shares = int((risk_amount / (stop_mult * atr * lot_size)))
                if unit_shares < 1:
                    unit_shares = 1
                buy_shares = unit_shares * lot_size

                if buy_shares > 0:
                    cost = buy_shares * close
                    fee = max(cost * commission_rate, min_commission)
                    if cost + fee <= capital:
                        capital -= cost + fee
                        total_fees += fee
                        position += buy_shares
                        holdings.append({'price': close, 'shares': buy_shares, 'date': date})

                        if current_units == 0:
                            # 初始建仓，设置止损价
                            stop_price = close - stop_mult * atr
                            trade_type = '买入'
                        else:
                            # 加仓，止损价上移
                            stop_price += add_interval * atr
                            trade_type = '加仓'

                        buy_markers.append((date, close))
                        trades.append({
                            'trade_date': date,
                            'type': trade_type,
                            'price': round(close, 2),
                            'shares': buy_shares,
                            'amount': round(cost, 2),
                            'fee': round(fee, 2),
                            'capital_after': round(capital, 2),
                        })

        # 记录每日净值
        equity = capital + position * close
        equity_curve.append({
            'trade_date': date,
            'equity': equity,
            'nav': equity / initial_capital,
            'position': position,
            'drawdown': 0,
        })

    # 构建 DataFrame
    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_curve)

    # 计算回撤
    equity_df['peak'] = equity_df['equity'].cummax()
    equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak']

    # 计算基准（买入持有）
    first_close = df['close'].iloc[0]
    last_close = df['close'].iloc[-1]
    benchmark_nav = df['close'] / first_close
    equity_df['benchmark_nav'] = benchmark_nav.values

    # 计算指标
    metrics = calc_metrics(df, trades_df, equity_df, initial_capital, risk_free_rate, total_fees, params)

    return df, trades_df, equity_df, metrics, buy_markers, sell_markers, stop_markers


def calc_metrics(df, trades_df, equity_df, initial_capital, rf, total_fees, params):
    """计算回测指标"""
    final_equity = equity_df['equity'].iloc[-1]
    total_return = (final_equity / initial_capital - 1) * 100

    # 年化收益率
    n_days = len(equity_df)
    if n_days > 1:
        ann_return = ((final_equity / initial_capital) ** (252 / n_days) - 1) * 100
    else:
        ann_return = 0

    # 基准收益率
    benchmark_return = (equity_df['benchmark_nav'].iloc[-1] - 1) * 100

    # 超额收益
    excess_return = total_return - benchmark_return

    # 最大回撤
    max_dd = equity_df['drawdown'].min() * 100

    # 夏普比率
    daily_returns = equity_df['nav'].pct_change().dropna()
    if len(daily_returns) > 1 and daily_returns.std() > 0:
        sharpe = (daily_returns.mean() * 252 - rf) / (daily_returns.std() * np.sqrt(252))
    else:
        sharpe = 0

    # 胜率、盈亏比
    if trades_df is not None and len(trades_df) > 0:
        # 配对计算：买入/加仓 → 卖出/止损 为一次完整交易
        buy_trades = trades_df[trades_df['type'].isin(['买入', '加仓'])].copy()
        sell_trades = trades_df[trades_df['type'].isin(['卖出', '止损'])].copy()

        complete_trades = []
        buy_queue = []
        for _, t in trades_df.iterrows():
            if t['type'] in ['买入', '加仓']:
                buy_queue.append(t)
            else:
                if buy_queue:
                    buy_t = buy_queue.pop(0)
                    pnl = (t['price'] - buy_t['price']) * t['shares']
                    complete_trades.append({
                        'buy_date': buy_t['trade_date'],
                        'sell_date': t['trade_date'],
                        'buy_price': buy_t['price'],
                        'sell_price': t['price'],
                        'shares': t['shares'],
                        'pnl': pnl,
                        'type': t['type'],
                    })

        if complete_trades:
            wins = [t for t in complete_trades if t['pnl'] > 0]
            losses = [t for t in complete_trades if t['pnl'] <= 0]
            win_rate = len(wins) / len(complete_trades) * 100
            avg_win = np.mean([t['pnl'] for t in wins]) if wins else 0
            avg_loss = abs(np.mean([t['pnl'] for t in losses])) if losses else 0
            pl_ratio = avg_win / avg_loss if avg_loss > 0 else float('inf')
            max_profit = max([t['pnl'] for t in complete_trades]) if complete_trades else 0
            max_loss = min([t['pnl'] for t in complete_trades]) if complete_trades else 0
        else:
            win_rate = 0
            pl_ratio = 0
            max_profit = 0
            max_loss = 0

        stop_count = len(trades_df[trades_df['type'] == '止损'])
    else:
        win_rate = 0
        pl_ratio = 0
        max_profit = 0
        max_loss = 0
        stop_count = 0

    total_trades = len(sell_trades) if trades_df is not None and len(trades_df) > 0 else 0

    metrics = {
        '累计收益率': f'{total_return:.2f}%',
        '年化收益率': f'{ann_return:.2f}%',
        '基准收益率（买入持有）': f'{benchmark_return:.2f}%',
        '超额收益': f'{excess_return:.2f}%',
        '最大回撤 (MDD)': f'{max_dd:.2f}%',
        '夏普比率 (Sharpe Ratio)': f'{sharpe:.3f}',
        '胜率': f'{win_rate:.1f}%',
        '盈亏比': f'{pl_ratio:.2f}',
        '总交易次数': f'{total_trades} 次',
        '止损触发次数': f'{stop_count} 次',
        '最大单笔盈利': f'{max_profit:,.2f} 元',
        '最大单笔亏损': f'{max_loss:,.2f} 元',
        '总费用': f'{total_fees:,.2f} 元',
        '初始资金': f'{initial_capital:,.0f} 元',
        '最终资金': f'{final_equity:,.2f} 元',
    }

    # 同时返回数值版本（用于卡片展示）
    metrics_values = {
        'total_return': total_return,
        'ann_return': ann_return,
        'benchmark_return': benchmark_return,
        'excess_return': excess_return,
        'max_dd': max_dd,
        'sharpe': sharpe,
        'win_rate': win_rate,
        'pl_ratio': pl_ratio,
        'total_trades': total_trades,
        'stop_count': stop_count,
        'total_fees': total_fees,
        'final_equity': final_equity,
    }

    return {'display': metrics, 'values': metrics_values}
