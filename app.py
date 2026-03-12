import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import os
import re

# 1. 網頁設定 (針對行動端優化)
st.set_page_config(page_title="InvestPie 投資派", layout="wide", initial_sidebar_state="collapsed")
DATA_FILE = "portfolio_data.csv"

# --- A. 本機資料存取 ---
def save_data(df):
    df[["ticker", "group", "shares", "cost"]].to_csv(DATA_FILE, index=False)

def load_data():
    if os.path.exists(DATA_FILE):
        try: return pd.read_csv(DATA_FILE)
        except: return pd.DataFrame(columns=["ticker", "group", "shares", "cost"])
    return pd.DataFrame(columns=["ticker", "group", "shares", "cost"])

if 'portfolio' not in st.session_state:
    st.session_state.portfolio = load_data()

# 2. 手機版視覺優化 CSS
st.markdown("""
    <style>
    .metric-box {
        background-color: #1e212b;
        padding: 15px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 10px;
        border: 1px solid #333;
    }
    .metric-label { font-size: 14px; color: #a3a7b0; }
    .metric-value { font-size: 22px; font-weight: bold; margin-top: 5px; }
    .up-color { color: #FF4B4B; }
    .down-color { color: #00FF00; }
    /* 優化 Tab 按鈕大小 */
    .stTabs [data-baseweb="tab-list"] button { font-size: 18px; padding: 10px 20px; }
    </style>
    """, unsafe_allow_html=True)

st.title("🥧 InvestPie 投資派")
st.caption("📱 行動對帳優化版 (CSV 存檔)")

# --- B. 側邊欄：新增自選股 ---
with st.sidebar:
    st.header("🔍 持股管理")
    with st.form("input_form", clear_on_submit=True):
        raw_ticker = st.text_input("股票代號", placeholder="例如: 2330")
        type_list = ["市值型", "高股息", "電子股", "金融股", "傳產股", "債券型", "美股", "其他"]
        selected_type = st.selectbox("持股類型", type_list)
        shares = st.number_input("持有股數", min_value=0.0, step=1.0, value=1000.0)
        avg_price = st.number_input("買入均價", min_value=0.0, step=0.01, value=100.0)
        submitted = st.form_submit_button("➕ 新增自選股", use_container_width=True)

    if submitted and raw_ticker:
        ticker = raw_ticker.strip().upper()
        if "." not in ticker:
            if re.match(r'^\d+[B]$', ticker): ticker = f"{ticker}.TWO" # 債券 ETF
            elif ticker.isdigit(): ticker = f"{ticker}.TW"
        
        new_row = pd.DataFrame([[ticker, selected_type, shares, avg_price * shares]], 
                                columns=["ticker", "group", "shares", "cost"])
        st.session_state.portfolio = pd.concat([st.session_state.portfolio, new_row]).drop_duplicates(subset=['ticker'], keep='last').reset_index(drop=True)
        save_data(st.session_state.portfolio)
        st.rerun()

    if not st.session_state.portfolio.empty:
        st.divider()
        if st.button("🧨 清空所有資料", use_container_width=True):
            st.session_state.portfolio = pd.DataFrame(columns=["ticker", "group", "shares", "cost"])
            save_data(st.session_state.portfolio)
            st.rerun()

# --- C. 主要顯示區：分頁設計 ---
if not st.session_state.portfolio.empty:
    tab1, tab2 = st.tabs(["📈 資產看板", "📝 明細編輯"])
    
    with st.spinner('同步報價中...'):
        df = st.session_state.portfolio.copy()
        prices = []
        for t in df["ticker"]:
            try:
                hist = yf.Ticker(t).history(period="1d")
                price = hist['Close'].iloc[-1] if not hist.empty else 0
                prices.append(price)
            except: prices.append(0)
        
        df["目前現價"] = prices
        df["買入均價"] = df["cost"] / df["shares"].replace(0, 1)
        df["目前市值"] = df["目前現價"] * df["shares"]
        df["損益"] = df["目前市值"] - df["cost"]
        df["報酬率(%)"] = (df["損益"] / df["cost"].replace(0, 1)) * 100

    with tab1:
        # 指標看板
        total_pnl = df['損益'].sum()
        pnl_class = "up-color" if total_pnl > 0 else "down-color" if total_pnl < 0 else ""
        
        col1, col2, col3 = st.columns(3)
        with col1: st.markdown(f'<div class="metric-box"><div class="metric-label">總市值</div><div class="metric-value">{df["目前市值"].sum():,.0f}</div></div>', unsafe_allow_html=True)
        with col2: st.markdown(f'<div class="metric-box"><div class="metric-label">總損益</div><div class="metric-value {pnl_class}">{total_pnl:,.0f}</div></div>', unsafe_allow_html=True)
        with col3: st.markdown(f'<div class="metric-box"><div class="metric-label">報酬率</div><div class="metric-value {pnl_class}">{(total_pnl/df["cost"].sum()*100 if df["cost"].sum() != 0 else 0):.2f}%</div></div>', unsafe_allow_html=True)
        
        # 圓餅圖
        st.plotly_chart(px.pie(df, values='目前市值', names='group', hole=0.5, height=350, title="類型占比"), use_container_width=True)
        st.plotly_chart(px.pie(df, values='目前市值', names='ticker', hole=0.5, height=350, title="持股占比"), use_container_width=True)

    with tab2:
        st.subheader("持股明細編輯")
        # 顯示核心欄位，適合手機橫滑
        edit_df = df[["ticker", "group", "shares", "買入均價", "目前現價", "損益", "報酬率(%)"]].rename(columns={
            "ticker": "代號", "group": "類型", "shares": "股數"
        })

        edited_df = st.data_editor(
            edit_df,
            column_config={
                "代號": st.column_config.TextColumn("代號", disabled=True),
                "類型": st.column_config.SelectboxColumn("類型", options=type_list),
                "股數": st.column_config.NumberColumn("股數", min_value=0),
                "買入均價": st.column_config.NumberColumn("均價", format="%.2f"),
                "目前現價": st.column_config.NumberColumn("現價", disabled=True, format="%.2f"),
                "損益": st.column_config.NumberColumn("損益", disabled=True, format="%d"),
                "報酬率(%)": st.column_config.NumberColumn("ROI", disabled=True, format="%.2f%%"),
            },
            hide_index=True,
            use_container_width=True,
            key="mobile_csv_editor"
        )

        if not edited_df.equals(edit_df):
            new_portfolio = edited_df[["代號", "類型", "股數", "買入均價"]].copy()
            new_portfolio.columns = ["ticker", "group", "shares", "avg_price"]
            new_portfolio["cost"] = new_portfolio["shares"] * new_portfolio["avg_price"]
            new_portfolio = new_portfolio[new_portfolio["shares"] > 0]
            st.session_state.portfolio = new_portfolio[["ticker", "group", "shares", "cost"]].reset_index(drop=True)
            save_data(st.session_state.portfolio)
            st.rerun()
else:
    st.info("💡 歡迎！請點擊左上角選單新增您的第一筆自選股。")
