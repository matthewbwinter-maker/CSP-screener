import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

# ──────────────────────────────────────────────
# 1. SETUP & UI
# ──────────────────────────────────────────────
st.set_page_config(page_title="Act 60 Wheel Pro", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0a0e1a; color: #c8d4e8; }
    h1, h2, h3 { font-family: monospace; color: #00d4aa; }
    .stMetric { background: #131d35; border: 1px solid #1e2d4a; border-radius: 5px; padding: 10px; }
    div.stButton > button:first-child {
        background: linear-gradient(90deg, #00d4aa, #0095ff);
        color: #0a0e1a; font-weight: bold; width: 100%; border: none; height: 3em;
    }
</style>
""", unsafe_allow_html=True)

st.title("🎡 Act 60 Wheel Pro")

# ──────────────────────────────────────────────
# 2. SIDEBAR PARAMETERS
# ──────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    ticker_str = st.text_area("Tickers", "TSLA, NVDA, AMD, AAPL, AMZN, MSFT, GOOGL, META, COIN, MSTR, NFLX, MARA, PLTR")
    TICKERS_LIST = [t.strip().upper() for t in ticker_str.split(",") if t.strip()]
    
    st.divider()
    min_yield = st.slider("Min Annual Yield (%)", 10, 80, 20)
    otm_dist = st.slider("OTM Distance (%)", 2, 20, 7)
    earn_safe = st.slider("Earnings Hard Block (Days)", 0, 14, 7)

# ──────────────────────────────────────────────
# 3. SCANNER ENGINE
# ──────────────────────────────────────────────
if st.button("⚡ EXECUTE STRATEGIC SCAN"):
    results = []
    progress = st.progress(0)
    status = st.empty()
    
    # Static Dates for April 2026 Earnings Season (Reliability Fix)
    EARNINGS_MAP = {
        "TSLA": datetime(2026, 4, 22),
        "GOOGL": datetime(2026, 4, 29),
        "GOOG": datetime(2026, 4, 29),
        "META": datetime(2026, 4, 22)
    }

    for i, symbol in enumerate(TICKERS_LIST):
        progress.progress((i + 1) / len(TICKERS_LIST))
        status.markdown(f"**Analyzing:** `{symbol}`")
        
        try:
            ticker_obj = yf.Ticker(symbol)
            hist = ticker_obj.history(period="150d")
            if hist.empty: continue
            
            curr_price = hist['Close'].iloc[-1]
            sma_50 = hist['Close'].rolling(50).mean().iloc[-1]
            
            # --- EARNINGS CHECK ---
            if symbol in EARNINGS_MAP:
                days_to_earn = (EARNINGS_MAP[symbol] - datetime.now()).days
            else:
                days_to_earn = 99
                try:
                    cal = ticker_obj.get_calendar()
                    if cal is not None and not cal.empty:
                        earn_date = pd.to_datetime(cal.iloc[0, 0]).replace(tzinfo=None)
                        days_to_earn = (earn_date - datetime.now()).days
                except: pass
            
            if 0 <= days_to_earn <= earn_safe:
                st.info(f"⏭️ Skipping {symbol}: Earnings in {days_to_earn} days.")
                continue 

            # --- OPTION SELECTION ---
            if not ticker_obj.options: continue
            
            target_expiry = ticker_obj.options[0]
            for exp in ticker_obj.options:
                d_to_exp = (datetime.strptime(exp, "%Y-%m-%d") - datetime.now()).days
                if 4 <= d_to_exp <= 12:
                    target_expiry = exp
                    break
            
            chain = ticker_obj.option_chain(target_expiry)
            puts = chain.puts
            
            target_strike_val = curr_price * (1 - (otm_dist / 100))
            idx = (puts['strike'] - target_strike_val).abs().idxmin()
            opt = puts.loc[idx]
            
            # Premium Math
            premium = (opt['bid'] + opt['ask']) / 2 if (opt['bid'] + opt['ask']) > 0 else opt['lastPrice']
            if premium < 0.10: continue 
            
            weekly_y = (premium / opt['strike']) * 100
            annual_y = weekly_y * 52
            
            if annual_y < min_yield: continue
            
            # Scoring
            dist_sma_pct = ((curr_price / sma_50) - 1) * 100
            score = 50 + (weekly_y * 20) - (dist_sma_pct * 3)
            
            results.append({
                "Ticker": symbol, "Score": round(score, 1),
                "Annual %": f"{round(annual_y, 1)}%", "Weekly %": f"{round(weekly_y, 2)}%",
                "Strike": opt['strike'], "Price": round(curr_price, 2),
                "Premium": round(premium, 2), "Earn In": f"{days_to_earn}d"
            })
            time.sleep(0.3)
            
        except: continue

    status.empty()
    progress.empty()

    if results:
        df = pd.DataFrame(results).sort_values("Score", ascending=False)
        st.subheader("🏆 Ranked Top Picks")
        st.dataframe(df, use_container_width=True)
    else:
        st.error("No trades passed filters. Try lowering 'Min Annual Yield'.")
