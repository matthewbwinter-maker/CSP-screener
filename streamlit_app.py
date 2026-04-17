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
    h1, h2, h3 { font-family: 'Courier New', monospace; color: #00ffcc; }
    .stMetric { background: #0d1b2a; border: 1px solid #1b263b; border-radius: 8px; padding: 10px; }
    div.stButton > button {
        background: #00ffcc; color: #050a14; font-weight: bold; border-radius: 4px; width: 100%;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ Quality & Volatility Screener")
st.caption("Focus: High Liquidity | > 10 Days to Earnings | Strategic Premium")

# ──────────────────────────────────────────────
# 2. CONFIGURATION
# ──────────────────────────────────────────────
with st.sidebar:
    st.header("Strategic Filters")
    # Focused on your priorities: Quality + Volatility + Liquidity
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
    
    # Static Dates for April/May 2026 to bypass '99-day' API glitches
    # TSLA (4/22) and META (4/22) will be filtered out by your 10-day rule
    DATES_2026 = {
        "TSLA": datetime(2026, 4, 22), "MSFT": datetime(2026, 4, 28),
        "GOOGL": datetime(2026, 4, 29), "AMZN": datetime(2026, 4, 29),
        "NVDA": datetime(2026, 5, 20), "AMD": datetime(2026, 4, 30),
        "AAPL": datetime(2026, 5, 7), "COIN": datetime(2026, 5, 14),
        "META": datetime(2026, 4, 22), "MSTR": datetime(2026, 5, 4)
    }

    for i, symbol in enumerate(TICKERS):
        progress.progress((i + 1) / len(TICKERS))
        status.markdown(f"**Scanning:** `{symbol}`")
        
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="150d")
            if hist.empty: continue
            
            # 1. Earnings Logic
            if symbol in DATES_2026:
