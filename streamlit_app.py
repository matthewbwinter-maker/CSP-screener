import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time

# ──────────────────────────────────────────────
# 1. MOBILE-OPTIMIZED HIGH CONTRAST UI
# ──────────────────────────────────────────────
st.set_page_config(page_title="Exit Strategy", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    [data-testid="stSidebar"] { background-color: #080808 !important; border-right: 1px solid #333333; }
    [data-testid="stSidebar"] label p { color: #FFFFFF !important; font-weight: 900; font-size: 1.1rem; }
    div[data-testid="stThumbValue"] { color: #00FF00 !important; font-weight: 900; }
    
    /* TABLE: Pure White Bold Cells for Phone Visibility */
    thead tr th { background-color: #00FF00 !important; color: #000000 !important; font-weight: 900; }
    tbody tr td { color: #FFFFFF !important; font-weight: 800 !important; font-size: 1.1rem !important; }
    
    /* BIG GREEN BUTTON FOR MOBILE THUMBS */
    div.stButton > button {
        background-color: #00FF00 !important; color: #000000 !important;
        font-weight: 900 !important; width: 100% !important; height: 5em !important;
        border-radius: 10px; border: none;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ WEEKLY EXIT STRATEGY")

# ──────────────────────────────────────────────
# 2. SIDEBAR
# ──────────────────────────────────────────────
with st.sidebar:
    st.header("⚡ FILTERS")
    ticker_str = st.text_area("Universe", "NVDA, AAPL, MSFT, AMZN, META, AVGO, JPM, UNH, COST")
    TICKERS = [t.strip().upper() for t in ticker_str.split(",") if t.strip()]
    
    st.divider()
    otm_target = st.slider("OTM SAFETY (%)", 3, 20, 8)
    earn_buffer = st.number_input("MIN DAYS TO EARNINGS", value=7)
    
    st.divider()
    target_date = st.text_input("Target Friday", value="2026-04-24")

# ──────────────────────────────────────────────
# 3. SCANNER
# ──────────────────────────────────────────────
if st.button("🚀 RUN NEXT-WEEK SCAN"):
    results = []
    progress = st.progress(0)
    today = datetime.now()

    for i, symbol in enumerate(TICKERS):
        progress.progress((i + 1) / len(TICKERS))
        try:
            t = yf.Ticker(symbol)
            
            # Check Analyst Rating
            info = t.info
            rating = info.get('recommendationKey', 'none').replace('_', ' ').title()
            if "Buy" not in rating: continue

            # Check Earnings (Skip if too close)
            cal = t.get_calendar()
            if cal is not None and not cal.empty:
                try:
                    earn_date = pd.to_datetime(cal.iloc[0, 0]).replace(tzinfo=None)
                    if (earn_date - today).days < earn_buffer: continue
                except: pass

            # Fetch Price and Chain
            hist = t.history(period="1d")
            price = hist['Close'].iloc[-1]
            
            chain = t.option_chain(target_date)
            puts = chain.puts
            
            # Find Strike
            strike_goal = price * (1 - (otm_target / 100))
            idx = (puts['strike'] - strike_goal).abs().idxmin()
            opt = puts.loc[idx]
            
            prem = (opt['bid'] + opt['ask']) / 2 if (opt['bid'] + opt['ask']) > 0 else opt['lastPrice']
            
            results.append({
                "Ticker": symbol,
                "Rating": rating,
                "Strike": opt['strike'],
                "OTM %": f"{round(((price/opt['strike'])-1)*100, 1)}%",
                "Premium": f"${round(prem, 2)}",
                "Price": f"${round(price, 2)}"
            })
            time.sleep(0.1)
        except: continue

    progress.empty()
    if results:
        st.table(pd.DataFrame(results).sort_values("Ticker"))
    else:
        st.error("No hits. Ensure the 'Target Friday' matches TOS exactly.")
