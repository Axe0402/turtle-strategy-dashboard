# 海龟策略回测演示看板

> 海龟交易策略 A 股回测演示看板 — 基于 Streamlit + Plotly 实现交互式参数配置、实时回测、交易信号可视化与指标分析

基于 Streamlit + Plotly 的交互式海龟交易策略回测系统，支持标的切换、时段选择、参数调节和一键导出报告。

**GitHub 仓库推荐设置：**

| 项目 | 推荐内容 |
|------|----------|
| 仓库名称 | `turtle-strategy-dashboard` |
| 仓库描述 | `基于 Streamlit 的海龟交易策略 A 股回测看板 \| 交互式参数配置 · 实时回测 · 信号可视化` |
| Topics 标签 | `streamlit` `plotly` `turtle-trading` `backtest` `quantitative-finance` `a-share` `python` `data-visualization` `trading-strategy` |
| 可见性 | Public（Streamlit Community Cloud 要求公开仓库） |

## 功能

- **标的选择**：寒武纪(科创板)、宁德时代(创业板)、招商银行(沪市主板)
- **时段选择**：自定义日期范围 + 快捷按钮（近1年/近2年/全部）
- **策略参数**：通道周期、ATR周期、风险比例、止损倍数、加仓次数和间隔
- **参数预设**：经典海龟 / 保守型 / 激进型，一键切换
- **可视化**：Plotly 交互式主图（股价+通道+信号+成交量）、资金曲线与回撤图
- **指标卡片**：累计收益、年化收益、最大回撤、夏普比率、胜率、盈亏比等 8 项核心指标
- **交易明细**：逐笔记录，按类型着色，支持 CSV 导出
- **报告导出**：ZIP 打包下载（PNG 信号图 + PNG 资金曲线 + 指标 CSV + 交易明细 CSV）

## 策略说明

海龟交易策略核心规则：
- **入场**：价格突破 20 日 Donchian 通道上轨（过去 20 日最高价）
- **离场**：价格跌破 10 日 Donchian 通道下轨（过去 10 日最低价）
- **止损**：价格低于 2×ATR 止损线
- **加仓**：价格每上涨 0.5×ATR 加仓 1 个单位，最多 4 个单位
- **仓位**：单笔风险 = 总资金 × 1% ÷ (止损倍数 × ATR)

## 在线演示

部署到 Streamlit Community Cloud 后，可获得永久公开访问链接：

```
https://turtle-strategy-dashboard.streamlit.app
```

详细部署步骤见 [`部署指引_StreamlitCloud.md`](部署指引_StreamlitCloud.md)。

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app/dashboard.py
```

浏览器自动打开 `http://localhost:8501`。

## 数据

三只 A 股 2023-07-10 至 2026-07-10 的前复权日线数据（728 个交易日），来源于 Tushare。

| 标的 | 代码 | 板块 | 最小交易单位 |
|------|------|------|-------------|
| 寒武纪 | 688256.SH | 科创板 | 200 股/手 |
| 宁德时代 | 300750.SZ | 创业板 | 100 股/手 |
| 招商银行 | 600036.SH | 沪市主板 | 100 股/手 |

## 项目结构

```
├── app/
│   ├── dashboard.py       # Streamlit 主程序入口
│   ├── strategy.py        # 海龟策略引擎 + 参数预设
│   ├── data_loader.py     # 数据加载与板块识别
│   └── visualization.py   # Plotly 图表生成
├── 寒武纪行情数据.csv
├── 宁德时代行情数据.csv
├── 招商银行行情数据.csv
├── requirements.txt
├── .streamlit/config.toml
└── README.md
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 框架 | Streamlit |
| 图表 | Plotly（交互式）+ Matplotlib（静态导出） |
| 数据 | Pandas |
| 计算 | NumPy |
