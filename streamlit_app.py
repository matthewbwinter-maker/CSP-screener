import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import time

# ──────────────────────────────────────────────
# 1. UI & STYLING
# ──────────────────────────────────────────────
st.set_page_config(page_title="Act 60 Alpha Engine", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #050a14; color: #e0e6ed; }
    h1, h2, h3 { font-family: monospace; color: #00ffcc; }
    .stTable { background-color: #0d1b2a; border-radius: 8px; }
    div.stButton > button {
        background: #00ffcc; color: #050a14; font-weight: bold; width: 100%; border: none;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ Quality & Volatility Screener")
st.caption("Strategic Focus: High Liquidity | > 10 Days to Earnings | Act 60 0% Capital Gains")

# ──────────────────────────────────────────────
# 2. CONFIGURATION
# ──────────────────────────────────────────────
with st.sidebar:
    st.header("Strategic Filters")
    ticker_str = st.text_area("Ticker Universe", 
                             "NVDA, AMD, COIN, MSTR, AMZN, PLTR, HOOD, MARA, AAPL, DIS, CRM, SQ, SHOP, GOOGL")
    TICKERS = [t.strip().upper() for t in ticker_str.split(",") if t.strip()]
    
    st.divider()
    min_annual = st.slider("Min Annual Yield (%)", 15, 100, 25)
    otm_target = st.slider("OTM Safety (%)", 5, 25, 10)
    earn_buffer = st.number_input("Min Days to Earnings", value=10)

# ──────────────────────────────────────────────
# 3. ANALYSIS CORE
# ──────────────────────────────────────────────
if st.button("🔍 ANALYZE LIQUID OPPORTUNITIES"):
    results = []
    progress = st.progress(0)
    status = st.empty()
    
    # 2026 Earnings Calendar (Today is April 17)
    DATES_2026 = {
        "TSLA": datetime(2026, 4, 22), 
        "META": datetime(2026, 4, 22),
        "MSFT": datetime(2026, 4, 28),
        "GOOGL": datetime(2026, 4, 29), 
        "AMZN": datetime(2026, 4, 29),
        "AMD": datetime(2026, 4, 30),
        "MSTR": datetime(2026, 5, 4),
        "AAPL": datetime(2026, 5, 7), 
        "COIN": datetime(2026, 5, 14),
        "NVDA": datetime(2026, 5, 20)
    }

    for i, symbol in enumerate(TICKERS):
        progress.progress((i + 1) / len(TICKERS))
        status.markdown(f"**Scanning:** `{symbol}`")
        
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="150d")
            if hist.empty:
                continue
            
            # 1. Earnings Logic
            if symbol in DATES_2026:
                days_to_earn = (DATES_2026[symbol] - datetime.now()).days
            else:
                days_to_earn = 99 
                cal = t.get_calendar()
                if cal is not None and not cal.empty:
                    d = pd.to_datetime(cal.iloc[0, 0]).replace(tzinfo=None)
                    days_to_earn = (d - datetime.now()).days

            # 2. Hard Block Safety Filter
            if days_to_earn < earn_buffer:
                continue 

            # 3. Liquidity & Volatility Metrics
            price = hist['Close'].iloc[-1]
            sma_50 = hist['Close'].rolling
