import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import os
import re

# 1. 網頁設定
st.set_page_config(page_title="InvestPie 投資派", layout="wide", initial_sidebar_state="auto")
DATA_FILE = "portfolio_data.csv"

# --- A. 資料存取邏輯 ---
def save_data(df):
    df[["ticker", "group", "shares", "cost"]].to_csv(DATA_FILE, index=False)

def load_data():
    if os.path.exists(DATA_FILE):
        try: return pd.read_csv(DATA_FILE)
        except: return pd.DataFrame(columns=["ticker", "group", "shares", "cost"])
    return pd.DataFrame(columns=["ticker", "group", "shares", "cost"])

if 'portfolio' not in st.session_state:
    st.session_state.portfolio = load_data()

# 2. 視覺化 CSS (強化數據顯示)
st.markdown("""
    <style>
    .metric-box {
        background-color: #1e212b; padding: 15px; border-radius: 12px;
        text-align: center; margin-bottom: 10px; border: 1px solid #333;
    }
    .metric-label { font-size: 14px; color: #a3a7b0; }
    .metric-value { font-size: 24px; font-weight: bold; margin-top: 5px; }
    .up-color { color: #FF4B4B; } .down-color { color: #00FF00; }
    /* 調整表格字體 */
    [data-testid="stTable"] { font-size: 16px; }
    </style>
    """, unsafe_allow_html=True)

# --- B. 側邊欄：控制中心 ---
with st.sidebar:
    st.title("🥧 InvestPie")
    view_mode = st.radio("🖥️ 介面顯示模式", ["手機版 (分頁式)", "電腦版 (全開式)"], index=0)
    
    st.divider()
    st.header("🔍 新增自選股")
    with st.form("input_form", clear_on_submit=True):
        raw_ticker = st.text_input("股票代號", placeholder="例如: 2330")
        type_list = ["市值型", "高股息", "電子股", "金融股", "傳產股", "債券型", "美股", "其他"]
        selected_type = st.selectbox("持股類型", type_list)
        shares = st.number_input("持有股數", min_value=0.0, step=1.0, value=1000.0)
        avg_price = st.number_input("買入均價", min_value=0.0, step=0.01, value=100.0)
        submitted = st.form_submit_button("➕ 新增", use_container_width=True)

    if submitted and raw_ticker:
        ticker = raw_ticker.strip().upper()
        if "." not in ticker:
            if re.match(r'^\d+[B]$', ticker): ticker = f"{ticker}.TWO"
            elif ticker.isdigit(): ticker = f"{ticker}.TW"
        
        new_row = pd.DataFrame([[ticker, selected_type, shares, avg_price * shares]], 
                                columns=["ticker", "group", "shares", "cost"])
        st.session_state.portfolio = pd.concat([st.session_state.portfolio, new_row]).drop_duplicates(subset=['ticker'], keep='last').reset_index(drop=True)
        save_data(st.session_state.portfolio)
        st.rerun()

    if st.button("🧨 清空所有資料", use_container_width=True):
        st.session_state.portfolio = pd.DataFrame(columns=["ticker", "group", "shares", "cost"])
        save_data(st.session_state.portfolio)
        st.rerun()

# --- C. 主要顯示邏輯 ---
if not st.session_state.portfolio.empty:
    with st.spinner('同步市場報價中...'):
        df = st.session_state.portfolio.copy()
        prices = []
        for t in df["ticker"]:
            try:
                hist = yf.Ticker(t).history(period="1d")
                prices.append(hist['Close'].iloc[-1] if not hist.empty else 0)
            except: prices.append(0)
        
        df["目前現價"] = prices
        df["買入均價"] = df["cost"] / df["shares"].replace(0, 1)
        df["目前市值"] = df["目前現價"] * df["shares"]
        df["損益"] = df["目前市值"] - df["cost"]
        df["報酬率(%)"] = (df["損益"] / df["cost"].replace(0, 1)) * 100

    total_mv = df['目前市值'].sum()
    total_pnl = df['損益'].sum()
    total_roi = (total_pnl / df['cost'].sum() * 100) if df['cost'].sum() != 0 else 0
    pnl_class = "up-color" if total_pnl > 0 else "down-color" if total_pnl < 0 else ""

    # 定義表格欄位設定 (解決 .9999 問題)
    column_cfg = {
        "代號": st.column_config.TextColumn("代號", disabled=True),
        "類型": st.column_config.SelectboxColumn("類型", options=type_list),
        "股數": st.column_config.NumberColumn("股數", format="%d"),
        "買入均價": st.column_config.NumberColumn("均價", format="%.2f"),
        "目前現價": st.column_config.NumberColumn("現價", disabled=True, format="%.2f"),
        "目前市值": st.column_config.NumberColumn("市值", disabled=True, format="NT$ %d"),
        "損益": st.column_config.NumberColumn("損益", disabled=True, format="%d"),
        "報酬率(%)": st.column_config.NumberColumn("ROI", disabled=True, format="%.2f%%"),
    }

    # --- 模式切換渲染 ---
    if view_mode == "電腦版 (全開式)":
        st.header("📈 資產全域總覽")
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(f'<div class="metric-box"><div class="metric-label">總市值</div><div class="metric-value">NT$ {total_mv:,.0f}</div></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="metric-box"><div class="metric-label">總損益</div><div class="metric-value {pnl_class}">{total_pnl:,.0f}</div></div>', unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="metric-box"><div class="metric-label">整體報酬率</div><div class="metric-value {pnl_class}">{total_roi:.2f}%</div></div>', unsafe_allow_html=True)
        
        p1, p2 = st.columns(2)
        with p1: st.plotly_chart(px.pie(df, values='目前市值', names='group', hole=0.4, title="類型占比"), use_container_width=True)
        with p2: st.plotly_chart(px.pie(df, values='目前市值', names='ticker', hole=0.4, title="持股占比"), use_container_width=True)
        
        st.subheader("💰 損益明細表")
        edit_df = df[["ticker", "group", "shares", "買入均價", "目前現價", "目前市值", "損益", "報酬率(%)"]].rename(columns={"ticker":"代號","group":"類型","shares":"股數"})
        edited_df = st.data_editor(edit_df, column_config=column_cfg, hide_index=True, use_container_width=True, key="pc_editor")

    else:
        tab1, tab2 = st.tabs(["📊 看板", "📝 編輯"])
        with tab1:
            m1, m2, m3 = st.columns(3)
            with m1: st.markdown(f'<div class="metric-box"><div class="metric-label">市值</div><div class="metric-value">{total_mv:,.0f}</div></div>', unsafe_allow_html=True)
            with m2: st.markdown(f'<div class="metric-box"><div class="metric-label">損益</div><div class="metric-value {pnl_class}">{total_pnl:,.0f}</div></div>', unsafe_allow_html=True)
            with m3: st.markdown(f'<div class="metric-box"><div class="metric-label">報酬</div><div class="metric-value {pnl_class}">{total_roi:.1f}%</div></div>', unsafe_allow_html=True)
            st.plotly_chart(px.pie(df, values='目前市值', names='group', hole=0.5, height=350), use_container_width=True)
            st.plotly_chart(px.pie(df, values='目前市值', names='ticker', hole=0.5, height=350), use_container_width=True)
        
        with tab2:
            st.subheader("編輯持股")
            edit_df = df[["ticker", "group", "shares", "買入均價", "目前現價", "損益"]].rename(columns={"ticker":"代號","group":"類型","shares":"股數"})
            edited_df = st.data_editor(edit_df, column_config=column_cfg, hide_index=True, use_container_width=True, key="mob_editor")

    # 檢查改動並同步存檔 (通用邏輯)
    if 'edited_df' in locals() and not edited_df.equals(edit_df):
        new_portfolio = edited_df[["代號", "類型", "股數", "買入均價"]].copy()
        new_portfolio.columns = ["ticker", "group", "shares", "avg_price"]
        new_portfolio["cost"] = new_portfolio["shares"] * new_portfolio["avg_price"]
        new_portfolio = new_portfolio[new_portfolio["shares"] > 0]
        st.session_state.portfolio = new_portfolio[["ticker", "group", "shares", "cost"]].reset_index(drop=True)
        save_data(st.session_state.portfolio)
        st.rerun()

else:
    st.info("💡 歡迎！請在左側選單新增自選股。")
