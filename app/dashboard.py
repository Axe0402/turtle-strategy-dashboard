"""
海龟策略演示看板 — Streamlit 主程序
"""

import sys
import os
import io
import zipfile
import pandas as pd
import numpy as np
import streamlit as st

# 将 app 目录加入 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_loader import scan_available_stocks, load_stock_data
from strategy import PRESETS, turtle_backtest
from visualization import plot_signal_chart, plot_equity_curve

# ========== 页面配置 ==========

st.set_page_config(
    page_title='海龟策略回测看板',
    page_icon='📊',
    layout='wide',
    initial_sidebar_state='expanded',
)

# 自定义 CSS
st.markdown("""
<style>
    .main-header {
        font-size: 28px;
        font-weight: bold;
        color: #333333;
        text-align: center;
        padding: 10px 0;
    }
    .metric-card {
        background-color: #F8F9FA;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        border: 1px solid #E0E0E0;
    }
    .metric-label {
        font-size: 13px;
        color: #7F8C8D;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;
        font-family: 'Consolas', monospace;
    }
    .metric-sub {
        font-size: 11px;
        color: #95A5A6;
        margin-top: 2px;
    }
    .pos { color: #E24B4A; }
    .neg { color: #1D9E75; }
    .neutral { color: #333333; }
    .sidebar .sidebar-content {
        width: 320px;
    }
    .stPlotlyChart {
        border: 1px solid #E0E0E0;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)


# ========== 数据加载 ==========

@st.cache_data
def get_stocks():
    return scan_available_stocks()


def metric_card(label, value, sub='', value_class='neutral'):
    """渲染指标卡片"""
    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value {value_class}">{value}</div>
        <div class="metric-sub">{sub}</div>
    </div>
    """


# ========== 主程序 ==========

def main():
    st.markdown('<div class="main-header">📊 海龟策略回测演示看板</div>', unsafe_allow_html=True)
    st.markdown('---')

    stocks = get_stocks()

    # ===== 侧边栏 =====
    with st.sidebar:
        st.markdown('### 🏷️ 标的选择')
        stock_names = [s['name'] for s in stocks]
        if not stock_names:
            st.error('未找到任何行情数据文件，请确认 CSV 文件已上传到仓库根目录。')
            st.stop()

        selected_name = st.selectbox('选择标的', stock_names, index=0)
        # 安全查找：避免 next() 在空列表上抛出 StopIteration
        stock_info = None
        for s in stocks:
            if s['name'] == selected_name:
                stock_info = s
                break
        if stock_info is None:
            st.error(f'未找到标的信息: {selected_name}')
            st.stop()

        st.info(
            f"**代码:** {stock_info['code']}\n\n"
            f"**板块:** {stock_info['board']}\n\n"
            f"**最小交易单位:** {stock_info['lot_size']} 股/手\n\n"
            f"**数据范围:** {stock_info['data_min']} ~ {stock_info['data_max']}\n\n"
            f"**交易日数:** {stock_info['trade_days']}"
        )

        st.markdown('---')
        st.markdown('### 📅 时段选择')

        # 加载数据获取日期范围
        df_full = load_stock_data(stock_info['file'])
        date_min = pd.to_datetime(stock_info['data_min']).date()
        date_max = pd.to_datetime(stock_info['data_max']).date()

        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input('开始日期', value=date_min, min_value=date_min, max_value=date_max)
        with col2:
            end_date = st.date_input('结束日期', value=date_max, min_value=date_min, max_value=date_max)

        # 快捷选项
        quick = st.radio('快捷选择', ['自定义', '近1年', '近2年', '全部'], horizontal=True, label_visibility='collapsed')
        if quick == '近1年':
            start_date = max(date_min, date_max.replace(year=date_max.year - 1))
        elif quick == '近2年':
            start_date = max(date_min, date_max.replace(year=date_max.year - 2))
        elif quick == '全部':
            start_date = date_min
            end_date = date_max

        # 筛选数据
        mask = (pd.to_datetime(df_full['trade_date']) >= pd.Timestamp(start_date)) & \
               (pd.to_datetime(df_full['trade_date']) <= pd.Timestamp(end_date))
        df = df_full[mask].reset_index(drop=True)
        st.caption(f'当前选定: **{len(df)}** 个交易日')

        if len(df) < 30:
            st.warning('⚠️ 选定时段少于 30 个交易日，回测结果可能不可靠。')

        st.markdown('---')
        st.markdown('### ⚙️ 海龟策略参数')

        # 参数预设
        preset = st.selectbox('参数预设', ['自定义'] + list(PRESETS.keys()))

        # 根据预设填充默认值
        defaults = PRESETS[preset].copy() if preset != '自定义' else PRESETS['经典海龟']

        col1, col2 = st.columns(2)
        with col1:
            entry_period = st.number_input('入场通道周期', min_value=5, max_value=60, value=defaults['entry_period'], step=1)
        with col2:
            exit_period = st.number_input('离场通道周期', min_value=5, max_value=60, value=defaults['exit_period'], step=1)

        atr_period = st.number_input('ATR 周期', min_value=5, max_value=60, value=defaults['atr_period'], step=1)

        st.markdown('**风控参数**')
        risk_pct = st.slider('单笔风险比例 (%)', min_value=0.5, max_value=5.0, value=defaults['risk_pct'], step=0.1)
        stop_mult = st.slider('止损倍数 (×ATR)', min_value=1.0, max_value=5.0, value=defaults['stop_mult'], step=0.1)

        st.markdown('**加仓参数**')
        max_units = st.number_input('最大加仓次数', min_value=0, max_value=10, value=defaults['max_units'], step=1)
        add_interval = st.slider('加仓间隔 (×ATR)', min_value=0.25, max_value=1.0, value=defaults['add_interval'], step=0.05)

        st.markdown('**显示选项**')
        show_stop = st.checkbox('显示止损信号标记', value=True)
        show_atr = st.checkbox('显示ATR填充区域', value=True)

        st.markdown('---')
        st.markdown('### 💰 交易参数')
        initial_capital = st.number_input('初始资金 (元)', min_value=100000, max_value=10000000, value=1000000, step=100000)
        commission_rate = st.slider('佣金费率 (%)', min_value=0.005, max_value=0.1, value=0.03, step=0.005) / 100
        stamp_duty = st.slider('印花税率 (%)', min_value=0.01, max_value=0.2, value=0.1, step=0.01) / 100
        min_commission = st.number_input('最低佣金 (元)', min_value=0, max_value=50, value=5, step=1)
        risk_free_rate = st.slider('无风险利率 (%)', min_value=0.0, max_value=5.0, value=2.0, step=0.1)

        st.markdown('---')
        col1, col2 = st.columns(2)
        with col1:
            run_btn = st.button('🚀 运行回测', type='primary', use_container_width=True)
        with col2:
            reset_btn = st.button('🔄 重置参数', use_container_width=True)

        export_btn = st.button('📥 导出报告', use_container_width=True)

    # ===== 主区域 =====

    if reset_btn:
        st.rerun()

    # 构建参数字典
    params = {
        'entry_period': int(entry_period),
        'exit_period': int(exit_period),
        'atr_period': int(atr_period),
        'risk_pct': float(risk_pct),
        'stop_mult': float(stop_mult),
        'max_units': int(max_units),
        'add_interval': float(add_interval),
        'initial_capital': float(initial_capital),
        'commission_rate': float(commission_rate),
        'stamp_duty': float(stamp_duty),
        'min_commission': float(min_commission),
        'lot_size': stock_info['lot_size'],
        'risk_free_rate': float(risk_free_rate),
        'show_stop': show_stop,
        'show_atr': show_atr,
    }

    # 运行回测
    if run_btn or 'last_result' not in st.session_state:
        with st.spinner('正在运行回测...'):
            result = turtle_backtest(df.copy(), params)
            st.session_state['last_result'] = result
            st.session_state['last_params'] = params
            st.session_state['last_stock'] = stock_info

    result = st.session_state.get('last_result')
    params_used = st.session_state.get('last_params', params)
    stock_used = st.session_state.get('last_stock', stock_info)

    if result is None:
        st.info('请在左侧调整参数后，点击 **🚀 运行回测** 开始。')
        return

    df_signals, trades_df, equity_df, metrics, buy_markers, sell_markers, stop_markers = result
    mv = metrics['values']

    # ===== 指标卡片 =====
    st.markdown('### 📈 核心指标')

    def cls(val):
        if val > 0:
            return 'pos'
        elif val < 0:
            return 'neg'
        return 'neutral'

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(metric_card(
            '累计收益率', f"{mv['total_return']:.2f}%",
            f"基准: {mv['benchmark_return']:.1f}%", cls(mv['total_return'])
        ), unsafe_allow_html=True)
    with c2:
        st.markdown(metric_card(
            '年化收益率', f"{mv['ann_return']:.2f}%",
            f"无风险利率: {risk_free_rate:.1f}%", cls(mv['ann_return'])
        ), unsafe_allow_html=True)
    with c3:
        st.markdown(metric_card(
            '最大回撤', f"{mv['max_dd']:.2f}%", '', 'neg'
        ), unsafe_allow_html=True)
    with c4:
        st.markdown(metric_card(
            '夏普比率', f"{mv['sharpe']:.3f}",
            '>1 为优' if mv['sharpe'] < 1 else '优秀', cls(mv['sharpe'])
        ), unsafe_allow_html=True)

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        st.markdown(metric_card(
            '胜率', f"{mv['win_rate']:.1f}%", '', cls(mv['win_rate'] - 50)
        ), unsafe_allow_html=True)
    with c6:
        st.markdown(metric_card(
            '盈亏比', f"{mv['pl_ratio']:.2f}", '>1 为优' if mv['pl_ratio'] < 1 else '优秀', cls(mv['pl_ratio'] - 1)
        ), unsafe_allow_html=True)
    with c7:
        st.markdown(metric_card(
            '总交易次数', f"{mv['total_trades']} 次",
            f"止损: {mv['stop_count']}次", 'neutral'
        ), unsafe_allow_html=True)
    with c8:
        st.markdown(metric_card(
            '总费用', f"{mv['total_fees']:,.0f}", '元', 'neutral'
        ), unsafe_allow_html=True)

    st.markdown('---')

    # ===== 超额收益提示 =====
    if mv['excess_return'] >= 0:
        st.success(f"超额收益: **+{mv['excess_return']:.2f}%** — 策略跑赢买入持有基准")
    else:
        st.warning(f"超额收益: **{mv['excess_return']:.2f}%** — 策略跑输买入持有基准")

    # ===== 主图 =====
    st.markdown('### 📉 主图：股价 + 通道 + 交易信号')
    fig_signal = plot_signal_chart(df_signals, buy_markers, sell_markers, stop_markers, params_used, stock_used)
    st.plotly_chart(fig_signal, use_container_width=True)

    # ===== 资金曲线 =====
    st.markdown('### 💹 资金曲线与回撤')
    fig_equity = plot_equity_curve(equity_df, buy_markers, sell_markers, params_used, stock_used)
    st.plotly_chart(fig_equity, use_container_width=True)

    # ===== 交易明细 =====
    st.markdown('### 📋 交易明细')
    if trades_df is not None and len(trades_df) > 0:
        display_trades = trades_df.copy()
        display_trades.columns = ['交易日期', '交易类型', '成交价', '成交股数', '成交金额', '费用', '交易后资金']

        # 颜色标记
        def color_type(val):
            if val == '买入':
                return 'color: #E24B4A; font-weight: bold'
            elif val == '加仓':
                return 'color: #E67E22; font-weight: bold'
            elif val == '卖出':
                return 'color: #1D9E75; font-weight: bold'
            elif val == '止损':
                return 'color: #8E44AD; font-weight: bold'
            return ''

        styled = display_trades.style.map(color_type, subset=['交易类型'])
        st.dataframe(styled, use_container_width=True, height=300)

        # 下载交易明细
        csv_trades = trades_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            '📥 下载交易明细 CSV', csv_trades,
            file_name=f"{stock_used['name']}_海龟策略_交易明细.csv",
            mime='text/csv',
        )
    else:
        st.info('回测期间无交易记录。')

    # ===== 完整指标表 =====
    st.markdown('### 📊 完整指标表')
    metrics_display = metrics['display']
    metrics_df = pd.DataFrame(list(metrics_display.items()), columns=['指标', '数值'])
    st.dataframe(metrics_df, use_container_width=True, hide_index=True)

    csv_metrics = metrics_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        '📥 下载指标 CSV', csv_metrics,
        file_name=f"{stock_used['name']}_海龟策略_指标.csv",
        mime='text/csv',
    )

    # ===== 导出报告 =====
    if export_btn:
        # 生成静态 PNG 图表
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        # 中文字体配置（兼容 Windows / Linux / macOS）
        matplotlib.rcParams['font.sans-serif'] = [
            'Microsoft YaHei',   # Windows
            'Noto Sans CJK SC',  # Linux (Streamlit Cloud)
            'WenQuanYi Micro Hei',  # Linux (备选)
            'PingFang SC',       # macOS
            'SimHei',            # Windows 备选
            'Arial Unicode MS',  # 通用
        ]
        matplotlib.rcParams['axes.unicode_minus'] = False

        buf_zip = io.BytesIO()
        with zipfile.ZipFile(buf_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 指标 CSV
            zf.writestr(f"{stock_used['name']}_海龟策略_指标.csv", csv_metrics.decode('utf-8-sig'))
            # 交易明细 CSV
            if trades_df is not None and len(trades_df) > 0:
                zf.writestr(f"{stock_used['name']}_海龟策略_交易明细.csv", csv_trades.decode('utf-8-sig'))

            # 信号图 PNG
            fig_mpl, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10), gridspec_kw={'height_ratios': [3, 1]}, sharex=True)
            dates = pd.to_datetime(df_signals['trade_date'])
            ax1.plot(dates, df_signals['close'], color='#333333', linewidth=1, label='收盘价')
            if 'upper_channel' in df_signals.columns:
                ax1.plot(dates, df_signals['upper_channel'], color='#E24B4A', linewidth=1, linestyle='--', label=f"入场({params_used['entry_period']}日)")
            if 'lower_channel' in df_signals.columns:
                ax1.plot(dates, df_signals['lower_channel'], color='#1D9E75', linewidth=1, linestyle='--', label=f"离场({params_used['exit_period']}日)")
            if buy_markers:
                bd, bp = zip(*buy_markers)
                ax1.scatter(pd.to_datetime(bd), bp, marker='^', color='#E24B4A', s=100, zorder=5, label='买入')
            if sell_markers:
                sd, sp = zip(*sell_markers)
                ax1.scatter(pd.to_datetime(sd), sp, marker='v', color='#1D9E75', s=100, zorder=5, label='卖出')
            if show_stop and stop_markers:
                std, stp = zip(*stop_markers)
                ax1.scatter(pd.to_datetime(std), stp, marker='x', color='#8E44AD', s=80, zorder=5, label='止损', linewidths=2)
            ax1.set_title(f"{stock_used['name']}({stock_used['code']}) 海龟策略信号图", fontsize=14, fontweight='bold')
            ax1.set_ylabel('价格 (元)')
            ax1.legend(loc='upper left', fontsize=8, ncol=3)
            ax1.grid(True, alpha=0.3)

            colors_vol = ['#E24B4A' if c >= 0 else '#1D9E75' for c in df_signals['pct_chg']]
            ax2.bar(dates, df_signals['vol'], color=colors_vol, width=1, alpha=0.7)
            ax2.set_ylabel('成交量')
            ax2.set_xlabel('日期')
            ax2.grid(True, alpha=0.3)
            ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            plt.xticks(rotation=30)
            plt.tight_layout()

            buf_png1 = io.BytesIO()
            fig_mpl.savefig(buf_png1, dpi=150, bbox_inches='tight', format='png')
            plt.close(fig_mpl)
            zf.writestr(f"{stock_used['name']}_海龟策略_信号图.png", buf_png1.getvalue())

            # 资金曲线 PNG
            fig_mpl2, (ax3, ax4) = plt.subplots(2, 1, figsize=(16, 8), gridspec_kw={'height_ratios': [2, 1]}, sharex=True)
            ax3.plot(dates, equity_df['nav'], color='#2E86C1', linewidth=1.5, label='策略净值')
            ax3.plot(dates, equity_df['benchmark_nav'], color='#95A5A6', linewidth=1, linestyle='--', label='基准净值')
            ax3.set_title(f"{stock_used['name']}({stock_used['code']}) 资金曲线与回撤", fontsize=14, fontweight='bold')
            ax3.set_ylabel('净值')
            ax3.legend(loc='upper left', fontsize=9)
            ax3.grid(True, alpha=0.3)

            ax4.fill_between(dates, equity_df['drawdown'] * 100, 0, color='#E24B4A', alpha=0.15, label='回撤')
            ax4.set_ylabel('回撤 (%)')
            ax4.set_xlabel('日期')
            ax4.grid(True, alpha=0.3)
            ax4.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
            ax4.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            plt.xticks(rotation=30)
            plt.tight_layout()

            buf_png2 = io.BytesIO()
            fig_mpl2.savefig(buf_png2, dpi=150, bbox_inches='tight', format='png')
            plt.close(fig_mpl2)
            zf.writestr(f"{stock_used['name']}_海龟策略_资金曲线.png", buf_png2.getvalue())

        st.download_button(
            '📥 下载完整报告 (ZIP)',
            buf_zip.getvalue(),
            file_name=f"{stock_used['name']}_海龟策略_报告.zip",
            mime='application/zip',
        )
        st.success('报告已生成，点击上方按钮下载。')


if __name__ == '__main__':
    main()
