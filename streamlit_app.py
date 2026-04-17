import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import time

# ──────────────────────────────────────────────
# 1. MAXIMUM CONTRAST THEME
# ──────────────────────────────────────────────
st.set_page_config(page_title="Weekly Exit Strategy", layout="wide")

st.markdown("""
<style>
    /* Main App Background */
    .stApp { background-color: #000000; color: #FFFFFF; }
    
    /* SIDEBAR: Pure White Bold Labels */
    section[data-testid="stSidebar"] {
        background-color: #050505 !important;
        border-right: 1px solid #444444;
    }
    section[data-testid="stSidebar"] label p {
        color: #FFFFFF !important;
        font-weight: 900 !important;
        font-size: 1.1rem !important;
        text-transform: uppercase;
    }
    
    /* SLIDERS: Neon Green Thumb & Value */
    div[data-testid="stThumbValue"] { color: #00FF00 !important; font-weight: 900; font-size: 1.2rem; }
    div[data-baseweb="slider"] { background-color: #333333; }

    /* TABLE: Pure White Cells on Dark Background */
    .stTable { background-color: #000000; border: 1px solid #444444; }
    
    /* Header Row: Neon Green with Black Text */
    thead tr th { 
        background-color: #00FF00 !important; 
        color: #000000 !important; 
        font-weight: 900 !important;
    }
    
    /* Data Cells: FORCED PURE WHITE */
    tbody tr td { 
        color: #FFFFFF !important; 
        font-weight: 700 !important; 
        font-size: 1.05rem !important;
        border-bottom: 1px solid #222222 !important;
    }

    /* SEARCH BUTTON: Giant Neon Green Trigger */
    div.stButton > button {
        background-color: #00FF00 !important;
        color: #000000 !important;
        font-weight: 900 !important;
        width: 100% !important;
        border: none !important;
        height: 4.5em !important;
        margin-top: 2em !important;
        box-shadow: 0px 0px 15px #00FF00;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ WEEKLY EXIT STRATEGY")
st.markdown("### Analyst 'Buy' Filtered | High-Contrast Mode")

# ──────────────────────────────────────────────
# 2. SIDEBAR CONFIGURATION
# ──────────────────────────────────────────────
with st.sidebar:
    st.header("⚡ FILTERS")
    
    ticker_str = st.text_area("Vetting Universe", 
                             "AAPL, MSFT, GOOGL, AMZN, NVDA, META, JPM, V, UNH, XOM, WMT, PG, AVGO, ORCL, COST, HD, ABBV")
    TICKERS = [t.strip().upper() for t in ticker_str.split(",") if t.strip()]
    
    st.divider()
    otm_target = st.slider("OTM SAFETY (%)", 3, 20, 8)
    earn_buffer = st.number_input("MIN DAYS TO EARNINGS", value=10)

# ──────────────────────────────────────────────
# 3. SCANNER LOGIC
# ──────────────────────────────────────────────
if st.button("🚀 EXECUTE WEEKLY SEARCH"):
    results = []
    progress = st.progress(0)
    status = st.empty()
    
    # Static Dates for April/May 2026 Earnings
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
            # Filter for Analyst 'Buy' or 'Strong Buy'
            info = t.info
            rating = info.get('recommendationKey', 'none').replace('_', ' ').title()
            
            if "Buy" not in rating:
                continue

            # Earnings check
            if symbol in D_2026:
                days_to_earn = (D_2026[symbol] - datetime.now()).days
            else:
                days_to_earn = 99
            
            if days_to_earn < earn_buffer:
                continue

            # Price Data
            hist = t.history(period="200d")
            price = hist['Close'].iloc[-1]
            
            # Weekly Expiry (5-9 days out)
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
            
            # Strike Selection
            strike_target = price * (1 - (otm_target / 100))
            idx = (puts['strike'] - strike_target).abs().idxmin()
            opt = puts.loc[idx]
            
            prem = (opt['bid'] + opt['ask']) / 2 if (opt['bid'] + opt['ask']) > 0 else opt['lastPrice']
            
            # Final Score
            score = 50 + (otm_target * 2.5)
            if rating == "Strong Buy": score += 15
            
            results.append({
                "Ticker": symbol,
                "Rating": rating,
                "Score": round(score, 1),
                "Strike": opt['strike'],
                "OTM %": f"{round(((price/opt['strike'])-1)*100, 1)}%",
                "Premium": f"${round(prem, 2)}",
                "Price": f"${round(price, 2)}"
            })
            time.sleep(0.1)
        except:
            continue

    status.empty()
    progress.empty()

    if results:
        df = pd.DataFrame(results).sort_values("Score", ascending=False)
        st.subheader("📊 QUANTIFIED OPPORTUNITIES")
        # st.table is best for forced contrast over st.dataframe
        st.table(df)
    else:
        st.error("No trades matched your Analyst Buy / Safety criteria.")
