import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import time
import requests

# 1. THE STEALTH FIX: Tell Yahoo we are a browser, not a bot
def get_ticker_stealth(symbol):
    session = requests.Session()
    # This 'User-Agent' makes us look like a standard Mac/Chrome user
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
    })
    return yf.Ticker(symbol, session=session)

st.set_page_config(page_title="Exit Strategy", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    thead tr th { background-color: #00FF00 !important; color: #000000 !important; font-weight: 900; }
    tbody tr td { color: #FFFFFF !important; font-weight: 800 !important; font-size: 1.1rem !important; }
    div.stButton > button {
        background-color: #00FF00 !important; color: #000000 !important;
        font-weight: 900 !important; width: 100% !important; height: 5em !important;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ STEALTH SCANNER: APR 24")

with st.sidebar:
    ticker_str = st.text_area("Universe", "NVDA, AAPL, MSFT, AMZN, META, AVGO, JPM, COST")
    TICKERS = [t.strip().upper() for t in ticker_str.split(",") if t.strip()]
    otm_target = st.slider("OTM SAFETY (%)", 3, 20, 8)
    target_date = st.text_input("Target Friday", value="2026-04-24")

if st.button("🚀 EXECUTE STEALTH SCAN"):
    results = []
    progress = st.progress(0)
    
    for i, symbol in enumerate(TICKERS):
        progress.progress((i + 1) / len(TICKERS))
        try:
            # Using the new Stealth Ticker
            t = get_ticker_stealth(symbol)
            
            # Use a slightly longer pause to avoid "Too Many Requests" errors
            time.sleep(0.5) 

            hist = t.history(period="1d")
            if hist.empty: continue
            price = hist['Close'].iloc[-1]
            
            chain = t.option_chain(target_date)
            puts = chain.puts
            
            strike_goal = price * (1 - (otm_target / 100))
            idx = (puts['strike'] - strike_goal).abs().idxmin()
            opt = puts.loc[idx]
            
            prem = (opt['bid'] + opt['ask']) / 2 if (opt['bid'] + opt['ask']) > 0 else opt['lastPrice']
            
            results.append({
                "Ticker": symbol,
                "Strike": opt['strike'],
                "OTM %": f"{round(((price/opt['strike'])-1)*100, 1)}%",
                "Premium": f"${round(prem, 2)}",
                "Price": f"${round(price, 2)}"
            })
        except Exception as e:
            continue

    progress.empty()
    if results:
        st.table(pd.DataFrame(results).sort_values("Ticker"))
    else:
        st.error("Still no results. Yahoo may be temporarily blocking Streamlit's IP. Try again in 10 minutes.")
