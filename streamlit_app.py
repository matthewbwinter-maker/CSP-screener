import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import time
import requests
import random

# 1. ENHANCED STEALTH: Randomizes the "ID Card" we show Yahoo
def get_stealth_session():
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    ]
    session = requests.Session()
    session.headers.update({'User-Agent': random.choice(user_agents)})
    return session

st.set_page_config(page_title="Exit Pro", layout="wide")

# UI Styling (High Contrast for Phone)
st.markdown("<style>.stApp { background-color: #000000; color: #FFFFFF; }</style>", unsafe_allow_html=True)
st.title("🛡️ EXIT SCANNER: APR 24")

with st.sidebar:
    ticker_str = st.text_area("Universe", "NVDA, AAPL, MSFT, AMZN, META, AVGO, JPM, COST")
    TICKERS = [t.strip().upper() for t in ticker_str.split(",") if t.strip()]
    otm_target = st.slider("OTM SAFETY (%)", 3, 20, 8)
    target_date = st.text_input("Target Friday", value="2026-04-24")

if st.button("🚀 EXECUTE CLOUD-SAFE SCAN"):
    results = []
    progress = st.progress(0)
    session = get_stealth_session()
    
    for i, symbol in enumerate(TICKERS):
        progress.progress((i + 1) / len(TICKERS))
        try:
            # We use the session to "hide" Streamlit's identity
            t = yf.Ticker(symbol, session=session)
            
            # Fetch Price
            hist = t.history(period="5d")
            if hist.empty: continue
            price = hist['Close'].iloc[-1]
            
            # Fetch Options
            chain = t.option_chain(target_date)
            puts = chain.puts
            
            if not puts.empty:
                strike_goal = price * (1 - (otm_target / 100))
                idx = (puts['strike'] - strike_goal).abs().idxmin()
                opt = puts.loc[idx]
                
                results.append({
                    "Ticker": symbol,
                    "Strike": opt['strike'],
                    "OTM %": f"{round(((price/opt['strike'])-1)*100, 1)}%",
                    "Premium": f"${round((opt['bid']+opt['ask'])/2, 2)}",
                    "Price": f"${round(price, 2)}"
                })
            # Slower pacing helps avoid the IP block
            time.sleep(1.2) 
        except Exception:
            continue

    progress.empty()
    if results:
        st.table(pd.DataFrame(results).sort_values("Ticker"))
    else:
        st.warning("⚠️ Data Blocked. Yahoo is limiting the Streamlit Server. Try one ticker at a time.")
