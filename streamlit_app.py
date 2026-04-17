import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import time

# ──────────────────────────────────────────────
# 1. HIGH-CONTRAST UI
# ──────────────────────────────────────────────
st.set_page_config(page_title="Weekly Exit Pro", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    p, span, label, .stMarkdown { color: #FFFFFF !important; font-weight: 500; }
    h1, h2, h3 { color: #00FF00 !important; font-family: monospace; }
    .stTable { background-color: #111111; border: 2px solid #333333; }
    thead tr th { background-color: #00FF00 !important; color: #000000 !important; }
    div.stButton > button {
        background-color: #00FF00; color: #000000; 
        font-weight: 900; border: none; height: 3.5em;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ WEEKLY EXIT STRATEGY")
st.caption("Focus: Low Assignment Risk | Strong Buy Ratings | Weekly Expiry")

# ──────────────────────────────────────────────
# 2. CONFIGURATION
# ──────────────────────────────────────────────
with st.sidebar:
    st.header("⚡ FILTERS")
    ticker_str = st.text_area("Blue Chip Universe", 
                             "AAPL, MSFT, GOOGL, AMZN, NVDA, META, JPM, V, UNH, XOM, WMT, PG, AVGO, ORCL, COST, HD, ABBV")
    TICKERS = [t.strip().upper() for t in ticker_str.split(",") if t.strip()]
    
    st.divider()
    # Focus on Safety (OTM) rather than Yield
    otm_target = st.slider("OTM Safety (%)", 5, 20, 8)
    earn_buffer = st.number_input("Min Days to Earnings", value=10)

# ──────────────────────────────────────────────
# 3. ANALYSIS CORE
# ──────────────────────────────────────────────
if st.button("RUN PROBABILITY SCAN"):
    results = []
    progress = st.progress(0)
    status = st.empty()
    
    # 2026 Earnings Calendar (Today is April 17)
    D_2026 = {
        "TSLA": datetime(2026, 4, 22), "META": datetime(2026, 4, 22),
        "MSFT": datetime(2026, 4, 28), "GOOGL": datetime(2026, 4, 29), 
        "AMZN": datetime(2026, 4, 29), "AAPL": datetime(2026, 5, 7), 
        "NVDA": datetime(2026, 5, 20), "AMD": datetime(2026, 4, 30)
    }

    for i, symbol in enumerate(TICKERS):
        progress.progress((i + 1) / len(TICKERS))
        status.markdown(f"**Vetting:** `{symbol}`")
        
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="250d")
            if hist.empty: continue
            
            # 1. ANALYST RATING CHECK
            # Pulling the 'recommendationKey' (e.g., 'buy', 'strong_buy')
            info = t.info
            rating = info.get('recommendationKey', 'none').replace('_', ' ').title()
            
            # Skip if analysts don't like it (We only want 'Buy' or 'Strong Buy')
            if "Buy" not in rating:
                continue

            # 2. EARNINGS HARD-BLOCK
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

            # 3. TECHNICAL "FLOOR" CHECK
            price = hist['Close'].iloc[-1]
            sma_200 = hist['Close'].rolling(window=200).mean().iloc[-1]
            
            # Only trade if the stock is in a healthy long-term uptrend
            if price < sma_200:
                continue

            # 4. WEEKLY OPTION SELECTION
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
            
            # Strike Selection (Strategic OTM)
            strike_target = price * (1 - (otm_target / 100))
            idx = (puts['strike'] - strike_target).abs().idxmin()
            opt = puts.loc[idx]
            
            prem = (opt['bid'] + opt['ask']) / 2 if (opt['bid'] + opt['ask']) > 0 else opt['lastPrice']
            
            # 5. SCORING: Probability of Profit (POP) focused
            # Rewards higher OTM distance and "Strong Buy" ratings
            score = 50
            score += (otm_target * 3) # Reward safety
            if rating == "Strong Buy": score += 20
            
            results.append({
                "Ticker": symbol,
                "Rating": rating,
                "Score": round(score, 1),
                "Strike": opt['strike'],
                "OTM %": f"{round(((price/opt['strike'])-1)*100, 1)}%",
                "Premium": f"${round(prem, 2)}",
                "Earn In": f"{days_to_earn}d",
                "Price": round(price, 2)
            })
            time.sleep(0.2)
            
        except:
            continue

    status.empty()
    progress.empty()

    if results:
        df = pd.DataFrame(results).sort_values("Score", ascending=False)
        st.subheader("🏆 TOP PROBABILITY TRADES")
        st.table(df)
    else:
        st.error("No 'Buy' rated stocks met the safety criteria. Try lowering 'OTM Safety'.")
