import streamlit as st
import yfinance as yf
import pandas as pd
import time
from datetime import datetime

# 1. STYLE: High-Contrast Ranking View
st.set_page_config(page_title="Ranked Exit Pro", layout="wide")
st.markdown("""
<style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    [data-testid="stMetricValue"] { color: #00FF00 !important; font-size: 1.8rem !important; }
    thead tr th { background-color: #00FF00 !important; color: #000000 !important; font-weight: 900; }
    tbody tr td { color: #FFFFFF !important; font-weight: 800 !important; font-size: 1.1rem !important; }
    div.stButton > button {
        background-color: #00FF00 !important; color: #000000 !important;
        font-weight: 900 !important; width: 100% !important; height: 5em !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🏆 RANKED MOVES: APR 24")

# 2. INPUTS
with st.sidebar:
    st.header("⚡ CRITERIA")
    # High-liquidity universe
    ticker_str = st.text_area("Vetting Universe", "NVDA, AAPL, MSFT, AMZN, META, AVGO, JPM, UNH, COST")
    TICKERS = [t.strip().upper() for t in ticker_str.split(",") if t.strip()]
    otm_target = st.slider("OTM Safety Target (%)", 5, 15, 8)
    target_date = "2026-04-24"

# 3. RANKING ENGINE
if st.button("🚀 RANK ALL MOVES"):
    results = []
    progress = st.progress(0)
    status = st.empty()

    for i, symbol in enumerate(TICKERS):
        progress.progress((i + 1) / len(TICKERS))
        status.text(f"Analyzing {symbol}...")
        try:
            t = yf.Ticker(symbol)
            # Fetch Price & History
            hist = t.history(period="5d")
            price = hist['Close'].iloc[-1]
            
            # Fetch Options (Slower pacing to avoid blocks)
            time.sleep(1.5) 
            chain = t.option_chain(target_date)
            puts = chain.puts
            
            # Find closest strike to OTM goal
            strike_goal = price * (1 - (otm_target / 100))
            idx = (puts['strike'] - strike_goal).abs().idxmin()
            opt = puts.loc[idx]
            
            prem = (opt['bid'] + opt['ask']) / 2 if (opt['bid'] + opt['ask']) > 0 else opt['lastPrice']
            
            # SCORING LOGIC: Yield / Distance to Strike
            # We want high premium but high safety
            yield_score = (prem / opt['strike']) * 100
            
            results.append({
                "Rank": 0, # Placeholder
                "Ticker": symbol,
                "Strike": opt['strike'],
                "Premium": round(prem, 2),
                "OTM %": f"{round(((price/opt['strike'])-1)*100, 1)}%",
                "Score": round(yield_score, 3), # Higher is better
                "Price": round(price, 2)
            })
        except:
            continue

    status.empty()
    progress.empty()

    if results:
        # Sort by Score (Best Move First)
        df = pd.DataFrame(results).sort_values("Score", ascending=False)
        df['Rank'] = range(1, len(df) + 1)
        
        # Display Top Pick
        top_pick = df.iloc[0]
        st.success(f"🥇 BEST MOVE: {top_pick['Ticker']} {top_pick['Strike']} PUT at ${top_pick['Premium']}")
        
        # Full Ranked Table
        st.table(df[['Rank', 'Ticker', 'Strike', 'Premium', 'OTM %', 'Price']])
    else:
        st.error("Yahoo blocked the scan. Turn off Wi-Fi on your phone and try again on Cellular Data.")
