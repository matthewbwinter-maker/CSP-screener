import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import time

# ──────────────────────────────────────────────
# 1. HIGH-CONTRAST "BLUE CHIP" UI
# ──────────────────────────────────────────────
st.set_page_config(page_title="Blue Chip Alpha", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    p, span, label, .stMarkdown { color: #FFFFFF !important; font-weight: 500; }
    h1, h2, h3 { color: #00FF00 !important; font-family: 'Courier New', monospace; }
    .stTable { background-color: #111111; border: 2px solid #333333; }
    thead tr th { background-color: #00FF00 !important; color: #000000 !important; }
    div.stButton > button {
        background-color: #00FF00; color: #000000; 
        font-weight: 900; border: none; height: 3.5em; font-size: 1.2em;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ BLUE CHIP WEEKLY SCANNER")
st.caption("Lower Volatility | High Liquidity | Act 60 Strategic Yield")

# ──────────────────────────────────────────────
# 2. CONFIGURATION
# ──────────────────────────────────────────────
with st.sidebar:
    st.header("⚡ FILTERS")
    # Strictly Blue Chip Universe
    ticker_str = st.text_area("Blue Chip List", 
                             "AAPL, MSFT, GOOGL, AMZN, NVDA, META, JPM, V, UNH, XOM, WMT, PG, AVGO, ORCL, COST")
    TICKERS = [t.strip().upper() for t in ticker_str.split(",") if t.strip()]
    
    st.divider()
    # Blue chips rarely offer 40%+ weekly; 15-25% is the 'Sweet Spot'
    min_annual = st.slider("Min Annual Yield (%)", 10, 50, 15)
    otm_safety = st.slider("OTM Safety (%)", 3, 15, 6)
    earn_buffer = st.number_input("Min Days to Earnings", value=10)

# ──────────────────────────────────────────────
# 3. ANALYSIS CORE
# ──────────────────────────────────────────────
if st.button("RUN BLUE CHIP SCAN"):
    results = []
    progress = st.progress(0)
    status = st.empty()
    
    # 2026 Earnings Calendar (Today is April 17)
    D_2026 = {
        "TSLA": datetime(2026, 4, 22), "META": datetime(2026, 4, 22),
        "MSFT": datetime(2026, 4, 28), "GOOGL": datetime(2026, 4, 29), 
        "AMZN": datetime(2026, 4, 29), "AAPL": datetime(2026, 5, 7), 
        "NVDA": datetime(2026, 5, 20), "JPM": datetime(2026, 4, 15), # Past
        "XOM": datetime(2026, 5, 1)
    }

    for i, symbol in enumerate(TICKERS):
        progress.progress((i + 1) / len(TICKERS))
        status.markdown(f"**Analyzing:** `{symbol}`")
        
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="150d")
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

            # 2. Volatility (Beta) Check
            # Using standard deviation of returns as a proxy for 'stickiness'
            returns = hist['Close'].pct_change().dropna()
            vol_profile = returns.std() * np.sqrt(252) # Annualized Vol
            
            # 3. Market Data
            price = hist['Close'].iloc[-1]
            sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1]
            vol_m = (hist['Volume'].tail(10).mean()) / 1e6
            
            # 4. Weekly Options Search (5-9 days)
            if not t.options: continue
            target_exp = None
            for e in t.options:
                d_to_e = (datetime.strptime(e, "%Y-%m-%d") - datetime.now()).days
                if 5 <= d_to_e <= 9:
                    target_exp = e
                    break
            
            if not target_exp: continue 
            
            chain = t.option_chain(target_exp)
            puts = chain.puts
            
            # 5. Strike Selection
            strike_target = price * (1 - (otm_safety / 100))
            idx = (puts['strike'] - strike_target).abs().idxmin()
            opt = puts.loc[idx]
            
            prem = (opt['bid'] + opt['ask']) / 2 if (opt['bid'] + opt['ask']) > 0 else opt['lastPrice']
            if prem < 0.10: continue
            
            weekly_y = (prem / opt['strike']) * 100
            annual_y = weekly_y * 52
            
            if annual_y < min_annual: continue
            
            # SCORING: Prefers Stability (Low Vol Profile) + Liquidity
            score = (annual_y * 0.5) + (vol_m * 0.05) - (vol_profile * 10)
            
            results.append({
                "Ticker": symbol,
                "Score": round(score, 1),
                "Annual %": f"{round(annual_y, 1)}%",
                "Strike": opt['strike'],
                "Premium": f"${round(prem, 2)}",
                "Earn In": f"{days_to_earn}d",
                "Liquidity": f"{round(vol_m, 1)}M",
                "Volatility": "Low" if vol_profile < 0.25 else "Moderate"
            })
            time.sleep(0.2)
            
        except:
            continue

    status.empty()
    progress.empty()

    if results:
        df = pd.DataFrame(results).sort_values("Score", ascending=False)
        st.subheader("🏆 RANKED BLUE CHIP OPPORTUNITIES")
        st.table(df)
    else:
        st.error("No Blue Chips found. Try lowering the 'OTM Safety' or 'Annual Yield'.")
