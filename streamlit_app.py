import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

# ──────────────────────────────────────────────
# 1. MAXIMUM CONTRAST THEME
# ──────────────────────────────────────────────
st.set_page_config(page_title="Next-Week Weeklys", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    section[data-testid="stSidebar"] { background-color: #050505 !important; border-right: 1px solid #444444; }
    section[data-testid="stSidebar"] label p { color: #FFFFFF !important; font-weight: 900; font-size: 1.1rem; }
    div[data-testid="stThumbValue"] { color: #00FF00 !important; font-weight: 900; }
    .stTable { background-color: #000000; border: 1px solid #444444; }
    thead tr th { background-color: #00FF00 !important; color: #000000 !important; font-weight: 900; }
    tbody tr td { color: #FFFFFF !important; font-weight: 700; font-size: 1.05rem; border-bottom: 1px solid #222222 !important; }
    div.stButton > button {
        background-color: #00FF00 !important; color: #000000 !important;
        font-weight: 900 !important; width: 100% !important; height: 4.5em !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ NEXT-WEEK EXIT STRATEGY")
st.markdown("### Exclusively Scanning: Friday, April 24, 2026")

# ──────────────────────────────────────────────
# 2. SIDEBAR
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
if st.button("🚀 SCAN NEXT-WEEK CONTRACTS"):
    results = []
    progress = st.progress(0)
    status = st.empty()
    
    # Target Expiry: Next Friday (April 24, 2026)
    # Today is April 17, so we want 7 days from now.
    today = datetime.now()
    target_date_str = (today + timedelta(days=7)).strftime("%Y-%m-%d")

    for i, symbol in enumerate(TICKERS):
        progress.progress((i + 1) / len(TICKERS))
        status.markdown(f"**Vetting:** `{symbol}`")
        
        try:
            t = yf.Ticker(symbol)
            
            # Analyst Check
            info = t.info
            rating = info.get('recommendationKey', 'none').replace('_', ' ').title()
            if "Buy" not in rating: continue

            # Earnings check
            cal = t.get_calendar()
            days_to_earn = 99
            if cal is not None and not cal.empty:
                d_obj = pd.to_datetime(cal.iloc[0, 0]).replace(tzinfo=None)
                days_to_earn = (d_obj - today).days
            
            if days_to_earn < earn_buffer: continue

            # Price Data
            hist = t.history(period="100d")
            price = hist['Close'].iloc[-1]
            
            # ──────────────────────────────────────────────
            # STRICT NEXT-WEEK FILTER
            # ──────────────────────────────────────────────
            if not t.options: continue
            
            # We specifically look for the April 24 expiry
            if target_date_str not in t.options:
                # If exact date isn't there, find the closest Friday between 6-9 days out
                found_expiry = None
                for e in t.options:
                    diff = (datetime.strptime(e, "%Y-%m-%d") - today).days
                    if 6 <= diff <= 9:
                        found_expiry = e
                        break
                if not found_expiry: continue
                expiry_to_use = found_expiry
            else:
                expiry_to_use = target_date_str

            chain = t.option_chain(expiry_to_use)
            puts = chain.puts
            
            # Strike Selection
            strike_target = price * (1 - (otm_target / 100))
            idx = (puts['strike'] - strike_target).abs().idxmin()
            opt = puts.loc[idx]
            
            prem = (opt['bid'] + opt['ask']) / 2 if (opt['bid'] + opt['ask']) > 0 else opt['lastPrice']
            
            results.append({
                "Ticker": symbol,
                "Rating": rating,
                "Expiry": expiry_to_use,
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
        df = pd.DataFrame(results).sort_values("Ticker")
        st.subheader("📊 NEXT-WEEK OPPORTUNITIES")
        st.table(df)
    else:
        st.error(f"No next-week trades found for {target_date_str}. Check your filters.")
