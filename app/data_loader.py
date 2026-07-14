"""
数据加载与管理模块
自动扫描项目目录下的 *行情数据.csv 文件
"""

import os
import glob
import pandas as pd
import streamlit as st


# 项目根目录（app 的上级目录）
# 兼容本地开发、Streamlit Cloud、Docker 等多种部署环境
def _find_project_root():
    """多种策略定位项目根目录"""
    # 策略 1：从 data_loader.py 的 __file__ 推算
    candidate = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if os.path.isdir(os.path.join(candidate, 'app')):
        return candidate

    # 策略 2：从当前工作目录找
    cwd = os.getcwd()
    if os.path.isdir(os.path.join(cwd, 'app')):
        return cwd
    # Streamlit Cloud 可能把工作目录设在仓库根目录
    if os.path.isdir(os.path.join(cwd, '..', 'app')):
        return os.path.normpath(os.path.join(cwd, '..'))

    # 策略 3：搜索常见 Streamlit Cloud 路径
    for mount_base in ['/mount/src', '/app', '/home/appuser']:
        for d in os.listdir(mount_base) if os.path.isdir(mount_base) else []:
            p = os.path.join(mount_base, d)
            if os.path.isdir(os.path.join(p, 'app')):
                return p

    # 兜底：回退到 __file__ 推算
    return candidate

PROJECT_DIR = _find_project_root()


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
    返回 [{"name": "寒武纪", "code": "688256.SH", "file": "...", "lot_size": 200, "board": "科创板", "data_min": "...", "data_max": "..."}]
    """
    # ===== 多层搜索策略：兼容各种部署环境 =====
    search_dirs = [
        PROJECT_DIR,                                    # __file__ 推算的根目录
        os.getcwd(),                                    # 当前工作目录
        os.path.dirname(os.path.abspath(__file__)),     # app/ 目录本身
        os.path.join(os.getcwd(), '..'),                # 工作目录的上级
    ]
    # Streamlit Cloud 常见挂载路径
    cloud_mount = '/mount/src'
    if os.path.isdir(cloud_mount):
        for repo_name in os.listdir(cloud_mount):
            search_dirs.append(os.path.join(cloud_mount, repo_name))

    files = []
    searched_patterns = []
    for d in set(search_dirs):
        d = os.path.normpath(os.path.abspath(d))
        if not os.path.isdir(d):
            continue
        pattern = os.path.join(d, '*行情数据.csv')
        searched_patterns.append(pattern)
        matches = glob.glob(pattern)
        files.extend(matches)

    # 去重
    files = list(set(files))

    if not files:
        # 最后一招：递归搜索整个仓库
        import streamlit as st
        for base_dir in [PROJECT_DIR, os.getcwd(), '/mount/src']:
            if not os.path.isdir(base_dir):
                continue
            for root, dirs, fnames in os.walk(base_dir):
                # 限制搜索深度，避免太慢
                depth = root.replace(base_dir, '').count(os.sep)
                if depth > 3:
                    break
                for fn in fnames:
                    if fn.endswith('行情数据.csv'):
                        files.append(os.path.join(root, fn))

        if not files:
            # 构建详细的错误信息
            cwd = os.getcwd()
            cwd_contents = os.listdir(cwd) if os.path.isdir(cwd) else []
            proj_contents = os.listdir(PROJECT_DIR) if os.path.isdir(PROJECT_DIR) else []
            app_contents = os.listdir(os.path.join(PROJECT_DIR, 'app')) if os.path.isdir(os.path.join(PROJECT_DIR, 'app')) else []

            st.error(
                f"### 未找到任何行情数据文件\n\n"
                f"**搜索了以下路径：**\n"
                + '\n'.join([f"- `{p}`" for p in searched_patterns]) +
                f"\n\n**当前工作目录** (`{cwd}`) **下的文件：**\n"
                + ('\n'.join([f"- `{f}`" for f in cwd_contents]) if cwd_contents else '（空目录）') +
                f"\n\n**项目根目录** (`{PROJECT_DIR}`) **下的文件：**\n"
                + ('\n'.join([f"- `{f}`" for f in proj_contents]) if proj_contents else '（空目录）') +
                f"\n\n**app/ 目录下的文件：**\n"
                + ('\n'.join([f"- `{f}`" for f in app_contents]) if app_contents else '（空目录）') +
                f"\n\n**解决方法：** 请确认 3 个 CSV 数据文件（`寒武纪行情数据.csv`、`宁德时代行情数据.csv`、`招商银行行情数据.csv`）已上传到 GitHub 仓库的**根目录**（和 `README.md` 平级，而不是在 `app/` 文件夹内）。"
            )
            return []
    stocks = []
    for f in files:
        basename = os.path.basename(f)
        name = basename.replace('行情数据.csv', '')
        # 快速读取第一行获取 ts_code
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
    # 按名称排序
    stocks.sort(key=lambda x: x['name'])
    return stocks
