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
    div.stButton > button {
        background: #00ffcc; color: #050a14; font-weight: bold; width: 100%; border: none; height: 3em;
    }
    .stTable { background-color: #0d1b2a; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ Quality & Volatility Screener")
st.caption("Focus: High Liquidity | > 10 Days to Earnings | Strategic Act 60 Yield")

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
    
    # Static Dates for April/May 2026 cycle (Today is April 17, 2026)
    DATES_2026 = {
        "TSLA": datetime(2026, 4, 22), "META": datetime(2026, 4, 22),
        "MSFT": datetime(2026, 4, 28), "GOOGL": datetime(2026, 4, 29), 
        "AMZN": datetime(2026, 4, 29), "AMD": datetime(2026, 4, 30),
        "MSTR": datetime(2026, 5, 4), "AAPL": datetime(2026, 5, 7), 
        "COIN": datetime(2026, 5, 14), "NVDA": datetime(2026, 5, 20)
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

            # 2. Safety Filter (> 10 Days)
            if days_to_earn < earn_buffer:
                continue 

            # 3. Technicals & Liquidity
            price = hist['Close'].iloc[-1]
            sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1]
            avg_vol_m = (hist['Volume'].tail(10).mean()) / 1e6
            
            # 4. Options Analysis
            if not t.options:
                continue
                
            # Filter for nearest weekly (7-15 days)
            expiry = t.options[0]
            for e in t.options:
                diff = (datetime.strptime(e, "%Y-%m-%d") - datetime.now()).days
                if 7 <= diff <= 15:
                    expiry = e
                    break
            
            chain = t.option_chain(expiry)
            puts = chain.puts
            
            # Strike Selection (OTM)
            target_strike = price * (1 - (otm_target / 100))
            idx = (puts['strike'] - target_strike).abs().idxmin()
            opt = puts.loc[idx]
            
            # Premium
            prem = (opt['bid'] + opt['ask']) / 2 if (opt['bid'] + opt['ask']) > 0 else opt['lastPrice']
            if prem < 0.10:
                continue
            
            # 5. Scoring Logic
            weekly_yield = (prem / opt['strike']) * 100
            annual_yield = weekly_yield * 52
            
            if annual_yield < min_annual:
                continue
            
            # Score: Favors high yield + Price stability (near SMA)
            dist_sma = ((price / sma_50) - 1) * 100
            score = (annual_yield * 0.7) - (abs(dist_sma) * 2)
            
            results.append({
                "Ticker": symbol,
                "Score": round(score, 1),
                "Annual %": f"{round(annual_yield, 1)}%",
                "Strike": opt['strike'],
                "Premium": f"${round(prem, 2)}",
                "Earn In": f"{days_to_earn}d",
                "Liquidity": f"{round(avg_vol_m, 1)}M",
                "Price": round(price, 2)
            })
            time.sleep(0.2)
            
        except Exception:
            continue

    status.empty()
    progress.empty()

    if results:
        df = pd.DataFrame(results).sort_values("Score", ascending=False)
        st.subheader("🏆 Ranked Alpha Opportunities")
        st.table(df)
        
        top = df.iloc[0]
        st.success(f"Best Quality Pick: {top['Ticker']} at ${top['Strike']} strike (Score: {top['Score']})")
    else:
        st.error(f"No results found. Try lowering your 'Min Annual Yield' or check 'Min Days to Earnings'.")
