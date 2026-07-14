"""
数据加载与管理模块
自动扫描项目目录下的 *行情数据.csv 文件
"""

import os
import pathlib
import pandas as pd
import streamlit as st


# 项目根目录 — 用 pathlib 替代 os.path，兼容性更好
_THIS_FILE = pathlib.Path(__file__).resolve()
# data_loader.py 在 app/ 里，上级目录即为项目根
PROJECT_DIR = str(_THIS_FILE.parent.parent)


def get_lot_size(ts_code: str) -> int:
    """根据股票代码判断最小交易单位"""
    code_num = ts_code.split('.')[0]
    market = ts_code.split('.')[1]
    # 科创板 688 开头 → 200 股
    if market == 'SH' and code_num.startswith('688'):
        return 200
    # 其余 → 100 股
    return 100


def get_board(ts_code: str) -> str:
    """根据股票代码判断板块"""
    code_num = ts_code.split('.')[0]
    market = ts_code.split('.')[1]
    if market == 'SH' and code_num.startswith('688'):
        return '科创板'
    if market == 'SZ' and code_num.startswith('300'):
        return '创业板'
    if market == 'SH' and code_num.startswith('60'):
        return '沪市主板'
    if market == 'SZ' and code_num.startswith('00'):
        return '深市主板'
    if market == 'SZ' and code_num.startswith('002'):
        return '中小板'
    return '其他'


@st.cache_data
def load_stock_data(filepath: str) -> pd.DataFrame:
    """加载单只股票的 CSV 数据"""
    df = pd.read_csv(filepath, encoding='utf-8-sig')
    # 统一日期格式为 YYYY-MM-DD
    # 先以字符串读取，再解析（兼容 YYYY-MM-DD 和 YYYYMMDD 两种格式）
    df['trade_date'] = df['trade_date'].astype(str)
    # 如果长度为 8 且全是数字，说明是 YYYYMMDD 格式
    sample = df['trade_date'].iloc[0] if len(df) > 0 else ''
    if len(sample) == 8 and sample.isdigit():
        df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
    else:
        df['trade_date'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y-%m-%d')
    df = df.sort_values('trade_date').reset_index(drop=True)
    return df


@st.cache_data
def scan_available_stocks() -> list:
    """
    扫描项目目录下所有 *行情数据.csv 文件
    使用 pathlib.rglob 递归搜索，原生支持 Unicode 文件名
    返回 [{"name": "寒武纪", "code": "688256.SH", ...}]
    """
    files = []

    # ===== 策略：从多个起点用 pathlib.rglob 递归搜索 =====
    search_roots = [
        pathlib.Path(PROJECT_DIR),                             # __file__ 推算的根
        pathlib.Path.cwd(),                                    # 当前工作目录
        pathlib.Path(_THIS_FILE.parent),                       # app/ 目录
        pathlib.Path.cwd().parent,                             # 工作目录上级
    ]
    # Streamlit Cloud 挂载点
    cloud_mount = pathlib.Path('/mount/src')
    if cloud_mount.is_dir():
        try:
            for child in cloud_mount.iterdir():
                if child.is_dir():
                    search_roots.append(child)
        except PermissionError:
            pass

    # 去重后搜索
    for root in set(search_roots):
        try:
            for p in root.rglob('*行情数据.csv'):
                files.append(str(p.resolve()))
        except (PermissionError, OSError):
            continue

    # 去重
    files = sorted(set(files))

    if not files:
        # ===== 诊断信息：列出各目录的实际内容 =====
        cwd = pathlib.Path.cwd()
        proj = pathlib.Path(PROJECT_DIR)

        def _list_dir(d: pathlib.Path, label: str) -> str:
            if not d.is_dir():
                return f"\n\n**{label}** (`{d}`)：目录不存在"
            try:
                items = sorted(d.iterdir())
            except PermissionError:
                return f"\n\n**{label}** (`{d}`)：无权访问"
            if not items:
                return f"\n\n**{label}** (`{d}`)：**空目录**"
            lines = [f"\n\n**{label}** (`{d}`)："]
            for item in items:
                tag = "📁" if item.is_dir() else "📄"
                lines.append(f"- {tag} `{item.name}`")
            return '\n'.join(lines)

        debug = ""
        debug += _list_dir(cwd, "当前工作目录")
        debug += _list_dir(proj, "项目根目录")
        debug += _list_dir(proj / 'app', "app/ 目录")
        debug += _list_dir(cloud_mount, "/mount/src")

        st.error(
            f"### 未找到任何行情数据文件\n\n"
            f"**搜索模式：** `*行情数据.csv`（递归匹配）\n"
            f"**搜索起点：** {len(set(search_roots))} 个目录"
            f"{debug}\n\n\n"
            f"**解决方法：** 请确认 3 个 CSV 文件已上传到 GitHub 仓库的**根目录**（和 README.md 平级，不在 app/ 里）。"
        )
        return []

    stocks = []
    for f in files:
        basename = pathlib.Path(f).name
        name = basename.replace('行情数据.csv', '')
        df = load_stock_data(f)
        if len(df) == 0:
            continue
        ts_code = df['ts_code'].iloc[0]
        stocks.append({
            'name': name,
            'code': ts_code,
            'file': f,
            'lot_size': get_lot_size(ts_code),
            'board': get_board(ts_code),
            'data_min': df['trade_date'].min(),
            'data_max': df['trade_date'].max(),
            'trade_days': len(df),
        })
    stocks.sort(key=lambda x: x['name'])
    return stocks
