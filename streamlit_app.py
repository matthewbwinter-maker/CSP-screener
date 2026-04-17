import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

# ──────────────────────────────────────────────
# 1. UI SETUP
# ──────────────────────────────────────────────
st.set_page_config(page_title="Act 60 Weekly Alpha", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #050a14; color: #e0e6ed; }
    h1, h2, h3 { font-family: monospace; color: #00ffcc; }
    div.stButton > button {
        background: #00ffcc; color: #050a14; font-weight: bold; width: 100%; border: none; height: 3em;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ Weekly Quality Screener")
st.caption("Targeting 5-8 Day Expiries | > 10 Days to Earnings | High Liquidity")

# ──────────────────────────────────────────────
# 2. SIDEBAR
# ──────────────────────────────────────────────
with st.sidebar:
    st.header("Parameters")
    ticker_str = st.text_area("Ticker Universe", 
                             "NVDA, AMD, COIN, MSTR, AMZN, PLTR, HOOD, MARA, AAPL, DIS, CRM, SQ, SHOP, GOOGL")
    TICKERS = [t.strip().upper() for t in ticker_str.split(",") if t.strip()]
    
    st.divider()
    min_annual = st.slider("Min Annual Yield (%)", 15, 100, 25)
    otm_safety = st.slider("OTM Safety (%)", 5, 25, 10)
    earn_buffer = st.number_input("Min Days to Earnings", value=10)

# ──────────────────────────────────────────────
# 3. ANALYSIS
# ──────────────────────────────────────────────
if st.button("🔍 SCAN FOR WEEKLY TRADES"):
    results = []
    progress = st.progress(0)
    status = st.empty()
    
    # 2026 Earnings Map (Critical for the >10 day rule)
    D_2026 = {
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
            hist = t.history(period="100d")
            if hist.empty: continue
            
            # 1. Earnings Check
            if symbol in D_2026:
                days_to_earn = (D_2026[symbol] - datetime.now()).days
            else:
                days_to_earn = 99
                cal = t.get_calendar()
                if cal is not None and not cal.empty:
                    d_obj = pd.to_datetime(cal.iloc[0, 0]).replace(tzinfo=None)
                    days_to_earn = (d_obj - datetime.now()).days

            if days_to_earn < earn_buffer:
                continue 

            # 2. Quality & Price
            price = hist['Close'].iloc[-1]
            sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1]
            vol_m = (hist['Volume'].tail(10).mean()) / 1e6
            
            # 3. STRICT WEEKLY EXPIRY LOGIC
            if not t.options: continue
            
            # Find expiry between 5 and 10 days away
            target_exp = None
            for e in t.options:
                days_to_exp = (datetime.strptime(e, "%Y-%m-%d") - datetime.now()).days
                if 5 <= days_to_exp <= 9: # This locks it to the next Friday
                    target_exp = e
                    break
            
            if not target_exp: continue # Skip if no weekly available in that window
            
            chain = t.option_chain(target_exp)
            puts = chain.puts
            
            # Strike Selection
            strike_target = price * (1 - (otm_safety / 100))
            idx = (puts['strike'] - strike_target).abs().idxmin()
            opt = puts.loc[idx]
            
            # Premium & Math
            prem = (opt['bid'] + opt['ask']) / 2 if (opt['bid'] + opt['ask']) > 0 else opt['lastPrice']
            if prem < 0.10: continue
            
            weekly_yield = (prem / opt['strike']) * 100
            annual_yield = weekly_yield * 52
            
            if annual_yield < min_annual: continue
            
            # Score (Yield + Liquidity + SMA proximity)
            dist_sma = ((price / sma_50) - 1) * 100
            score = (annual_yield * 0.6) + (vol_m * 0.1) - (abs(dist_sma) * 1.5)
            
            results.append({
                "Ticker": symbol,
                "Score": round(score, 1),
                "Annual %": f"{round(annual_yield, 1)}%",
                "Strike": opt['strike'],
                "Premium": f"${round(prem, 2)}",
                "Expiry": target_exp,
                "Earn In": f"{days_to_earn}d",
                "Liquidity": f"{round(vol_m, 1)}M"
            })
            time.sleep(0.2)
            
        except Exception:
            continue

    status.empty()
    progress.empty()

    if results:
        df = pd.DataFrame(results).sort_values("Score", ascending=False)
        st.subheader("🏆 Ranked Weekly Alpha")
        st.table(df)
    else:
        st.error("No weekly trades found. Try lowering OTM Safety or Annual Yield.")
