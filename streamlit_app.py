import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time

# ──────────────────────────────────────────────
# 1. UI SETUP (Max Contrast White/Green/Black)
# ──────────────────────────────────────────────
st.set_page_config(page_title="Next-Week Exit Pro", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    [data-testid="stSidebar"] { background-color: #050505 !important; border-right: 1px solid #444444; }
    [data-testid="stSidebar"] label p { color: #FFFFFF !important; font-weight: 900; font-size: 1.1rem; }
    div[data-testid="stThumbValue"] { color: #00FF00 !important; font-weight: 900; }
    thead tr th { background-color: #00FF00 !important; color: #000000 !important; font-weight: 900; }
    tbody tr td { color: #FFFFFF !important; font-weight: 700; border-bottom: 1px solid #222222 !important; }
    div.stButton > button { background-color: #00FF00 !important; color: #000000 !important; font-weight: 900 !important; height: 4em !important; box-shadow: 0px 0px 15px #00FF00; }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ NEXT-WEEK EXIT STRATEGY")
st.caption("Targeting April 24, 2026 | Forced Friday Handoff Mode")

# ──────────────────────────────────────────────
# 2. SIDEBAR CONFIG
# ──────────────────────────────────────────────
with st.sidebar:
    st.header("⚡ FILTERS")
    ticker_str = st.text_area("Vetting Universe", "AAPL, MSFT, GOOGL, AMZN, NVDA, META, JPM, V, UNH, XOM, WMT, PG, AVGO, ORCL, COST, HD")
    TICKERS = [t.strip().upper() for t in ticker_str.split(",") if t.strip()]
    
    st.divider()
    otm_target = st.slider("OTM SAFETY (%)", 3, 20, 7)
    earn_buffer = st.number_input("MIN DAYS TO EARNINGS", value=7)
    
    st.divider()
    st.warning("⚠️ FRIDAY HANDOFF OVERRIDE")
    manual_date = st.text_input("Manual Expiry (YYYY-MM-DD)", value="2026-04-24")

# ──────────────────────────────────────────────
# 3. SCANNER LOGIC
# ──────────────────────────────────────────────
if st.button("🚀 EXECUTE NEXT-WEEK SEARCH"):
    results = []
    progress = st.progress(0)
    status = st.empty()
    
    today = datetime.now()

    for i, symbol in enumerate(TICKERS):
        progress.progress((i + 1) / len(TICKERS))
        status.markdown(f"**Vetting:** `{symbol}`")
        
        try:
            t = yf.Ticker(symbol)
            
            # Use manual date if provided, otherwise try auto-search
            available = t.options
            target_expiry = None
            
            if manual_date in available:
                target_expiry = manual_date
            else:
                # Fuzzy search for Friday between 6-8 days out
                for exp in available:
                    diff = (datetime.strptime(exp, "%Y-%m-%d") - today).days
                    if 6 <= diff <= 8:
                        target_expiry = exp
                        break
            
            if not target_expiry:
                continue

            # Analyst Rating Check
            info = t.info
            rating = info.get('recommendationKey', 'none').replace('_', ' ').title()
            if "Buy" not in rating: continue

            # Earnings check
            cal = t.get_calendar()
            days_to_earn = 99
            if cal is not None and not cal.empty:
                try:
                    d_val = cal.iloc[0, 0] if isinstance(cal, pd.DataFrame) else cal.get('Earnings Date')[0]
                    d_obj = pd.to_datetime(d_val).replace(tzinfo=None)
                    days_to_earn = (d_obj - today).days
                except: pass
            
            if days_to_earn < earn_buffer: continue

            # Price & Options
            hist = t.history(period="5d")
            price = hist['Close'].iloc[-1]
            
            chain = t.option_chain(target_expiry)
            puts = chain.puts
            
            # Strike Selection
            strike_goal = price * (1 - (otm_target / 100))
            idx = (puts['strike'] - strike_goal).abs().idxmin()
            opt = puts.loc[idx]
            
            prem = (opt['bid'] + opt['ask']) / 2 if (opt['bid'] + opt['ask']) > 0 else opt['lastPrice']
            
            results.append({
                "Ticker": symbol,
                "Rating": rating,
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
        st.table(pd.DataFrame(results).sort_values("Ticker"))
    else:
        st.error(f"No contracts found for {manual_date}. Check your OTM Safety or Ticker list.")
