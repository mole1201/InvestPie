import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import os
import re

# 1. 網頁基本設定
st.set_page_config(page_title="InvestPie 投資派", layout="wide")
DATA_FILE = "portfolio_data.csv"

# --- A. 資料存取邏輯 ---
def save_data(df):
    """將資料存入本機 CSV"""
    df[["ticker", "group", "shares", "cost"]].to_csv(DATA_FILE, index=False)

def load_data():
    """從本機讀取資料"""
    if os.path.exists(DATA_FILE):
        try:
            return pd.read_csv(DATA_FILE)
        except:
            return pd.DataFrame(columns=["ticker", "group", "shares", "cost"])
    return pd.DataFrame(columns=["ticker", "group", "shares", "cost"])

# 初始化持股資料
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = load_data()

# 自訂台股紅漲綠跌 CSS
st.markdown("""<style>
    .metric-box { background-color: #1e212b; padding: 20px; border-radius: 10px; text-align: center; }
    .up-color { color: #FF4B4B; }   /* 紅色代表上漲/獲利 */
    .down-color { color: #00FF00; } /* 綠色代表下跌/虧損 */
</style>""", unsafe_allow_html=True)

st.title("🥧 InvestPie 投資派：精準管理系統")

# --- B. 側邊欄：管理工具 ---
with st.sidebar:
    st.header("🔍 持股管理")
    
    # 區塊 1：新增自選股
    with st.expander("➕ 新增自選股", expanded=True):
        with st.form("input_form", clear_on_submit=True):
            raw_ticker = st.text_input("股票代號", placeholder="例如: 2330 或 00937B")
            type_list = ["市值型", "高股息", "電子股", "金融股", "傳產股", "債券型", "美股", "其他"]
            selected_type = st.selectbox("持股類型", type_list)
            shares = st.number_input("持有股數", min_value=0.0, step=1.0, value=1000.0)
            avg_price = st.number_input("買入均價", min_value=0.0, step=0.01, value=100.0)
            submitted = st.form_submit_button("新增至清單")

    # 處理新增邏輯
    if submitted and raw_ticker:
        ticker = raw_ticker.strip().upper()
        if "." not in ticker:
            if re.match(r'^\d+[B]$', ticker): ticker = f"{ticker}.TWO" # 債券 ETF 
            elif ticker.isdigit(): ticker = f"{ticker}.TW" # 一般台股
        
        new_row = pd.DataFrame([[ticker, selected_type, shares, avg_price * shares]], 
                                columns=["ticker", "group", "shares", "cost"])
        st.session_state.portfolio = pd.concat([st.session_state.portfolio, new_row]).drop_duplicates(subset=['ticker'], keep='last').reset_index(drop=True)
        save_data(st.session_state.portfolio)
        st.rerun()

    # 區塊 2：單一刪除功能 (應用戶要求增加)
    if not st.session_state.portfolio.empty:
        st.divider()
        st.subheader("🎯 移除特定標的")
        ticker_options = st.session_state.portfolio["ticker"].tolist()
        target_to_delete = st.selectbox("請選擇要剔除的股票", ticker_options)
        if st.button(f"🗑️ 刪除 {target_to_delete}", use_container_width=True):
            st.session_state.portfolio = st.session_state.portfolio[st.session_state.portfolio["ticker"] != target_to_delete].reset_index(drop=True)
            save_data(st.session_state.portfolio)
            st.success(f"已成功移除 {target_to_delete}")
            st.rerun()

        # 區塊 3：一鍵清空 (放在最下面作為備用)
        st.divider()
        if st.button("🧨 清空所有資料", use_container_width=True):
            st.session_state.portfolio = pd.DataFrame(columns=["ticker", "group", "shares", "cost"])
            save_data(st.session_state.portfolio)
            st.rerun()

# --- C. 主要顯示區 ---
if not st.session_state.portfolio.empty:
    df = st.session_state.portfolio.copy()
    
    with st.spinner('同步市場報價中...'):
        prices = []
        for t in df["ticker"]:
            try:
                stock = yf.Ticker(t)
                hist = stock.history(period="1d")
                price = hist['Close'].iloc[-1] if not hist.empty else stock.fast_info.get('last_price', 0)
                prices.append(price if price > 0 else 0)
            except:
                prices.append(0)
        
        df["目前現價"] = prices
        df["買入均價"] = df["cost"] / df["shares"].replace(0, 1)
        df["目前市值"] = df["目前現價"] * df["shares"]
        df["損益"] = df["目前市值"] - df["cost"]
        df["報酬率(%)"] = (df["損益"] / df["cost"].replace(0, 1)) * 100

    # 1. 總覽看板
    total_pnl = df['損益'].sum()
    pnl_class = "up-color" if total_pnl > 0 else "down-color" if total_pnl < 0 else ""
    c1, c2, c3 = st.columns(3)
    c1.markdown(f'<div class="metric-box">總市值<br><span style="font-size:24px">NT$ {df["目前市值"].sum():,.0f}</span></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-box">總損益<br><span style="font-size:24px" class="{pnl_class}">{total_pnl:,.0f}</span></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="metric-box">整體報酬率<br><span style="font-size:24px" class="{pnl_class}">{(total_pnl/df["cost"].sum()*100):.2f}%</span></div>', unsafe_allow_html=True)

    st.divider()

    # 2. 雙圓餅圖
    col_p1, col_p2 = st.columns(2)
    use_val = '目前市值' if df['目前市值'].sum() > 0 else 'cost'
    with col_p1:
        st.subheader("🍕 資產類型分布")
        st.plotly_chart(px.pie(df, values=use_val, names='group', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel), use_container_width=True)
    with col_p2:
        st.subheader("📈 個股持股占比")
        st.plotly_chart(px.pie(df, values=use_val, names='ticker', hole=0.4), use_container_width=True)

    # 3. 損益明細表
    st.subheader("📝 損益明細與持股編輯")
    edit_df = df[["ticker", "group", "shares", "買入均價", "目前現價", "目前市值", "損益", "報酬率(%)"]].rename(columns={
        "ticker": "代號", "group": "類型", "shares": "股數"
    })

    edited_df = st.data_editor(
        edit_df,
        column_config={
            "代號": st.column_config.TextColumn("代號", disabled=True),
            "類型": st.column_config.SelectboxColumn("類型", options=type_list, required=True),
            "股數": st.column_config.NumberColumn("股數", min_value=0, format="%d"),
            "買入均價": st.column_config.NumberColumn("買入均價", min_value=0.0, format="%.2f"),
            "目前現價": st.column_config.NumberColumn("目前現價", disabled=True, format="%.2f"),
            "目前市值": st.column_config.NumberColumn("目前市值", disabled=True, format="%d"),
            "損益": st.column_config.NumberColumn("損益", disabled=True, format="%d"),
            "報酬率(%)": st.column_config.NumberColumn("報酬率(%)", disabled=True, format="%.2f%%"),
        },
        hide_index=True,
        use_container_width=True,
        key="portfolio_editor_v5"
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
    st.info("💡 歡迎！請從左側新增自選股。現在您可以使用「單一刪除」功能精準管理您的持股了！")