import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

# ──────────────────────────────────────────────
# 1. UI & STYLING
# ──────────────────────────────────────────────
st.set_page_config(page_title="Act 60 Alpha Engine", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #050a14; color: #e0e6ed; }
    h1, h2, h3 { font-family: 'Courier New', monospace; color: #00ffcc; }
    .stMetric { background: #0d1b2a; border: 1px solid #1b263b; border-radius: 8px; }
    div.stButton > button {
        background: #00ffcc; color: #050a14; font-weight: bold; border-radius: 4px;
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
    # Tickers known for high options liquidity
    ticker_str = st.text_area("Ticker Universe", 
                             "NVDA, AMD, COIN, MSTR, AMZN, PLTR, HOOD, MARA, AAPL, DIS, CRM, SQ, SHOP")
    TICKERS = [t.strip().upper() for t in ticker_str.split(",") if t.strip()]
    
    st.divider()
    min_annual = st.slider("Min Annual Yield (%)", 15, 100, 25)
    otm_target = st.slider("OTM Safety (%)", 5, 25, 10)
    # Your requested 10-day buffer
    earn_buffer = st.number_input("Min Days to Earnings", value=10)

# ──────────────────────────────────────────────
# 3. ANALYSIS CORE
# ──────────────────────────────────────────────
if st.button("🔍 ANALYZE LIQUID OPPORTUNITIES"):
    results = []
    progress = st.progress(0)
    
    # Precise dates for April/May 2026 cycle
    DATES_2026 = {
        "TSLA": datetime(2026, 4, 22), "MSFT": datetime(2026, 4, 28),
        "GOOGL": datetime(2026, 4, 29), "AMZN": datetime(2026, 4, 29),
        "NVDA": datetime(2026, 5, 20), "AMD": datetime(2026, 4, 30),
        "AAPL": datetime(2026, 5, 7), "COIN": datetime(2026, 5, 14)
    }

    for i, symbol in enumerate(TICKERS):
        progress.progress((i + 1) / len(TICKERS))
        
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="200d")
            if hist.empty: continue
            
            # 1. Earnings Logic
            if symbol in DATES_2026:
                days_to_earn = (DATES_2026[symbol] - datetime.now()).days
            else:
                days_to_earn = 99 # Default safe
                cal = t.get_calendar()
                if cal is not None and not cal.empty:
                    d = pd.to_datetime(cal.iloc[0, 0]).replace(tzinfo=None)
                    days_to_earn = (d - datetime.now()).days

            if days_to_earn < earn_buffer:
                continue # STRICT SKIP for your 10-day rule

            # 2. Quality & Liquidity Metrics
            price = hist['Close'].iloc[-1]
            sma_50 = hist['Close'].rolling(50).mean().iloc[-1]
            avg_vol = hist['Volume'].tail(10).mean() # Liquidity proxy
            
            # 3. Options Math
            if not t.options: continue
            # Find expiry between 7 and 14 days out
            expiry = t.options[0]
            for e in t.options:
                diff = (datetime.strptime(e, "%Y-%m-%d") - datetime.now()).days
                if 7 <= diff <= 15:
                    expiry = e
                    break
            
            chain = t.option_chain(expiry)
            puts = chain.puts
            
            # Select Strike (Quality OTM)
            target_strike = price * (1 - (otm_target / 100))
            idx = (puts['strike'] - target_strike).abs().idxmin()
            opt = puts.loc[idx]
            
            premium = (opt['bid'] + opt['ask']) / 2 if (opt['bid'] + opt['ask']) > 0 else opt['lastPrice']
            if premium < 0.15: continue
            
            # 4. SCORING MODEL (Prioritizing Volatility + Quality)
            weekly_yield = (premium / opt['strike']) * 100
            annual_yield = weekly_yield * 52
            
            if annual_yield < min_annual: continue
            
            # Quality Score: Higher if stock is consolidating near/above 50MA
            # Volatility Score: Reflected in high premium/annual yield
            score = (annual_yield * 0.6) + (100 - abs((price/sma_50 - 1) * 100))
            
            results.append({
                "Ticker": symbol,
                "Score": round(score, 1),
                "Annual %": f"{round(annual_yield, 1)}%",
                "Premium": f"${round(premium, 2)}",
                "Strike": opt['strike'],
                "Price": round(price, 2),
                "Earn In": f"{days_to_earn}d",
                "Liquidity (M)": f"{round(avg_vol / 1e6, 1)}M"
            })
            time.sleep(0.2)
            
        except: continue

    if results:
        df = pd.DataFrame(results).sort_values("Score", ascending=False)
        st.subheader("🔥 Top Strategic Picks (> 10 Days Safety)")
        st.table(df)
        st.success(f"Best Quality Pick: {df.iloc[0]['Ticker']} with {df.
