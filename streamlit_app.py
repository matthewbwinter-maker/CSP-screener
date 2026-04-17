import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time

# ──────────────────────────────────────────────
# 1. UI SETUP (High Contrast White on Black)
# ──────────────────────────────────────────────
st.set_page_config(page_title="Next-Week Exit Pro", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    [data-testid="stSidebar"] { background-color: #050505 !important; border-right: 1px solid #444444; }
    [data-testid="stSidebar"] label p { color: #FFFFFF !important; font-weight: 900; }
    div[data-testid="stThumbValue"] { color: #00FF00 !important; font-weight: 900; }
    thead tr th { background-color: #00FF00 !important; color: #000000 !important; font-weight: 900; }
    tbody tr td { color: #FFFFFF !important; font-weight: 700; border-bottom: 1px solid #222222 !important; }
    div.stButton > button { background-color: #00FF00 !important; color: #000000 !important; font-weight: 900 !important; height: 4em !important; }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ NEXT-WEEK SCANNER")
st.caption("Targeting the April 24, 2026 Cycle")

# ──────────────────────────────────────────────
# 2. SIDEBAR
# ──────────────────────────────────────────────
with st.sidebar:
    st.header("⚡ FILTERS")
    ticker_str = st.text_area("Vetting Universe", "NVDA, AAPL, MSFT, AMZN, GOOGL, META, AVGO, JPM, COST")
    TICKERS = [t.strip().upper() for t in ticker_str.split(",") if t.strip()]
    st.divider()
    otm_target = st.slider("OTM SAFETY (%)", 3, 20, 8)
    earn_buffer = st.number_input("MIN DAYS TO EARNINGS", value=7)

# ──────────────────────────────────────────────
# 3. SCANNER LOGIC
# ──────────────────────────────────────────────
if st.button("🚀 EXECUTE NEXT-WEEK SEARCH"):
    results = []
    progress = st.progress(0)
    
    today = datetime.now()
    # We want a Friday that is 6-8 days away (April 24)
    min_days, max_days = 6, 8

    for i, symbol in enumerate(TICKERS):
        progress.progress((i + 1) / len(TICKERS))
        try:
            t = yf.Ticker(symbol)
            
            # 1. EXPIRY SEARCH (Failsafe Logic)
            available_expiries = t.options
            if not available_expiries: continue
            
            target_expiry = None
            for exp in available_expiries:
                exp_date = datetime.strptime(exp, "%Y-%m-%d")
                days_away = (exp_date - today).days
                if min_days <= days_away <= max_days:
                    target_expiry = exp
                    break
            
            if not target_expiry: continue # Skip if next Friday isn't listed yet

            # 2. ANALYST CHECK
            info = t.info
            rating = info.get('recommendationKey', 'none').replace('_', ' ').title()
            if "Buy" not in rating: continue

            # 3. EARNINGS CHECK
            cal = t.get_calendar()
            days_to_earn = 99
            if cal is not None and not cal.empty:
                # Handle different formats of yfinance calendar
                try:
                    d_val = cal.iloc[0, 0] if isinstance(cal, pd.DataFrame) else cal.get('Earnings Date')[0]
                    d_obj = pd.to_datetime(d_val).replace(tzinfo=None)
                    days_to_earn = (d_obj - today).days
                except: pass
            
            if days_to_earn < earn_buffer: continue

            # 4. PRICE & OPTION DATA
            hist = t.history(period="5d")
            price = hist['Close'].iloc[-1]
            
            chain = t.option_chain(target_expiry)
            puts = chain.puts
            
            # Find closest strike to our OTM target
            strike_goal = price * (1 - (otm_target / 100))
            idx = (puts['strike'] - strike_goal).abs().idxmin()
            opt = puts.loc[idx]
            
            prem = (opt['bid'] + opt['ask']) / 2 if (opt['bid'] + opt['ask']) > 0 else opt['lastPrice']
            
            results.append({
                "Ticker": symbol,
                "Rating": rating,
                "Expiry": target_expiry,
                "Strike": opt['strike'],
                "OTM %": f"{round(((price/opt['strike'])-1)*100, 1)}%",
                "Premium": f"${round(prem, 2)}",
                "Price": f"${round(price, 2)}"
            })
            time.sleep(0.1)
        except Exception as e:
            continue

    progress.empty()
    if results:
        st.table(pd.DataFrame(results))
    else:
        st.warning("No April 24th contracts found. Providers may still be updating. Try again in a few minutes or lower the OTM Safety.")
