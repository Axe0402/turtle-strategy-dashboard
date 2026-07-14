"""
可视化模块 — Plotly 交互式图表
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np


# 配色
C_PRICE = '#333333'
C_UPPER = '#E24B4A'
C_LOWER = '#1D9E75'
C_BUY = '#E24B4A'
C_SELL = '#1D9E75'
C_STOP = '#8E44AD'
C_STRATEGY = '#2E86C1'
C_BENCHMARK = '#95A5A6'
C_DRAWDOWN = '#E24B4A'


def plot_signal_chart(df, buy_markers, sell_markers, stop_markers, params, stock_info):
    """主图：股价 + 通道 + 交易信号"""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.7, 0.3],
        subplot_titles=('股价 + Donchian 通道 + 交易信号', '成交量'),
    )

    dates = pd.to_datetime(df['trade_date'])

    # 收盘价
    fig.add_trace(go.Scatter(
        x=dates, y=df['close'],
        name='收盘价', line=dict(color=C_PRICE, width=1.2),
        hovertemplate='日期: %{x|%Y-%m-%d}<br>收盘: %{y:.2f}<extra></extra>',
    ), row=1, col=1)

    # 入场通道上轨
    if 'upper_channel' in df.columns:
        fig.add_trace(go.Scatter(
            x=dates, y=df['upper_channel'],
            name=f"入场通道({params['entry_period']}日高点)",
            line=dict(color=C_UPPER, width=1, dash='dash'),
            hovertemplate='上轨: %{y:.2f}<extra></extra>',
        ), row=1, col=1)

    # 离场通道下轨
    if 'lower_channel' in df.columns:
        fig.add_trace(go.Scatter(
            x=dates, y=df['lower_channel'],
            name=f"离场通道({params['exit_period']}日低点)",
            line=dict(color=C_LOWER, width=1, dash='dash'),
            hovertemplate='下轨: %{y:.2f}<extra></extra>',
        ), row=1, col=1)

    # ATR 填充区域
    if params.get('show_atr', True) and 'atr' in df.columns:
        atr_scaled = df['atr'] / df['atr'].max() * (df['close'].max() - df['close'].min()) * 0.3
        fig.add_trace(go.Scatter(
            x=dates, y=df['close'] + atr_scaled,
            name='ATR波动', line=dict(width=0),
            showlegend=False, hoverinfo='skip',
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=dates, y=df['close'] - atr_scaled,
            name='ATR波动', fill='tonexty',
            line=dict(width=0), fillcolor='rgba(227,75,74,0.06)',
            showlegend=False, hoverinfo='skip',
        ), row=1, col=1)

    # 买入信号
    if buy_markers:
        bd, bp = zip(*buy_markers)
        bd = pd.to_datetime(bd)
        fig.add_trace(go.Scatter(
            x=bd, y=bp, name='买入信号',
            mode='markers', marker=dict(symbol='triangle-up', size=14, color=C_BUY),
            hovertemplate='买入: %{x|%Y-%m-%d} @ %{y:.2f}<extra></extra>',
        ), row=1, col=1)

    # 卖出信号
    if sell_markers:
        sd, sp = zip(*sell_markers)
        sd = pd.to_datetime(sd)
        fig.add_trace(go.Scatter(
            x=sd, y=sp, name='卖出信号',
            mode='markers', marker=dict(symbol='triangle-down', size=14, color=C_SELL),
            hovertemplate='卖出: %{x|%Y-%m-%d} @ %{y:.2f}<extra></extra>',
        ), row=1, col=1)

    # 止损信号
    if params.get('show_stop', True) and stop_markers:
        std, stp = zip(*stop_markers)
        std = pd.to_datetime(std)
        fig.add_trace(go.Scatter(
            x=std, y=stp, name='止损信号',
            mode='markers', marker=dict(symbol='x', size=12, color=C_STOP, line_width=2),
            hovertemplate='止损: %{x|%Y-%m-%d} @ %{y:.2f}<extra></extra>',
        ), row=1, col=1)

    # 成交量
    colors = [C_UPPER if c >= 0 else C_LOWER for c in df['pct_chg']]
    fig.add_trace(go.Bar(
        x=dates, y=df['vol'], name='成交量',
        marker_color=colors, opacity=0.7,
        hovertemplate='成交量: %{y:,.0f}<extra></extra>',
    ), row=2, col=1)

    # 布局
    title = f"{stock_info['name']}({stock_info['code']}) 海龟策略信号图"
    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        height=550,
        template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
        hovermode='x unified',
        xaxis_rangeslider_visible=False,
        margin=dict(l=60, r=30, t=80, b=40),
    )
    fig.update_yaxes(title_text='价格 (元)', row=1, col=1)
    fig.update_yaxes(title_text='成交量', row=2, col=1)
    fig.update_xaxes(title_text='日期', row=2, col=1)

    return fig


def plot_equity_curve(equity_df, buy_markers, sell_markers, params, stock_info):
    """资金曲线 + 回撤"""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.7, 0.3],
        subplot_titles=('策略净值 vs 基准净值', '回撤曲线'),
    )

    dates = pd.to_datetime(equity_df['trade_date'])

    # 策略净值
    fig.add_trace(go.Scatter(
        x=dates, y=equity_df['nav'],
        name='策略净值', line=dict(color=C_STRATEGY, width=1.5),
        hovertemplate='策略净值: %{y:.4f}<extra></extra>',
    ), row=1, col=1)

    # 基准净值
    fig.add_trace(go.Scatter(
        x=dates, y=equity_df['benchmark_nav'],
        name='基准净值(买入持有)', line=dict(color=C_BENCHMARK, width=1.2, dash='dash'),
        hovertemplate='基准净值: %{y:.4f}<extra></extra>',
    ), row=1, col=1)

    # 买卖信号点
    if buy_markers:
        bd, bp = zip(*buy_markers)
        bd = pd.to_datetime(bd)
        # 找到对应日期的净值
        nav_at_buy = []
        for d in bd:
            mask = equity_df['trade_date'] == d.strftime('%Y-%m-%d')
            if mask.any():
                nav_at_buy.append(equity_df.loc[mask, 'nav'].iloc[0])
            else:
                nav_at_buy.append(np.nan)
        fig.add_trace(go.Scatter(
            x=bd, y=nav_at_buy, name='买入',
            mode='markers', marker=dict(size=8, color=C_BUY),
            hovertemplate='买入点<br>净值: %{y:.4f}<extra></extra>',
        ), row=1, col=1)

    if sell_markers:
        sd, sp = zip(*sell_markers)
        sd = pd.to_datetime(sd)
        nav_at_sell = []
        for d in sd:
            mask = equity_df['trade_date'] == d.strftime('%Y-%m-%d')
            if mask.any():
                nav_at_sell.append(equity_df.loc[mask, 'nav'].iloc[0])
            else:
                nav_at_sell.append(np.nan)
        fig.add_trace(go.Scatter(
            x=sd, y=nav_at_sell, name='卖出',
            mode='markers', marker=dict(size=8, color=C_SELL),
            hovertemplate='卖出点<br>净值: %{y:.4f}<extra></extra>',
        ), row=1, col=1)

    # 回撤
    fig.add_trace(go.Scatter(
        x=dates, y=equity_df['drawdown'] * 100,
        name='回撤', fill='tozeroy', line=dict(color=C_DRAWDOWN, width=0.5),
        fillcolor='rgba(227,75,74,0.15)',
        hovertemplate='回撤: %{y:.2f}%<extra></extra>',
    ), row=2, col=1)

    title = f"{stock_info['name']}({stock_info['code']}) 资金曲线与回撤"
    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        height=450,
        template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
        hovermode='x unified',
        margin=dict(l=60, r=30, t=80, b=40),
    )
    fig.update_yaxes(title_text='净值', row=1, col=1)
    fig.update_yaxes(title_text='回撤 (%)', row=2, col=1)
    fig.update_xaxes(title_text='日期', row=2, col=1)

    return fig
