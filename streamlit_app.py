import streamlit as st
import yfinance as yf
import pandas as pd
import time

# 1. UI SETUP
st.set_page_config(page_title="Deep Search Exit", layout="wide")
st.markdown("""
<style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    [data-testid="stSidebar"] { background-color: #050505 !important; border-right: 1px solid #444444; }
    [data-testid="stSidebar"] label p { color: #FFFFFF !important; font-weight: 900; }
    thead tr th { background-color: #00FF00 !important; color: #000000 !important; font-weight: 900; }
    tbody tr td { color: #FFFFFF !important; font-weight: 700; border-bottom: 1px solid #222222 !important; }
    div.stButton > button { background-color: #00FF00 !important; color: #000000 !important; font-weight: 900 !important; height: 4em !important; }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ DEEP SEARCH: APRIL 24")

# 2. SIDEBAR
with st.sidebar:
    st.header("⚡ FILTERS")
    # Small, high-liquidity list to avoid API timeout
    ticker_str = st.text_area("Vetting Universe", "NVDA, AAPL, MSFT, AMZN, META, AVGO, JPM, UNH, COST")
    TICKERS = [t.strip().upper() for t in ticker_str.split(",") if t.strip()]
    
    st.divider()
    # AGGRESSIVE: If no hits, drop OTM to 3% to verify data is flowing
    otm_target = st.slider("OTM SAFETY (%)", 1, 20, 5)
    # FORCE 0: Set this to 0 to bypass the earnings block during this busy week
    earn_buffer = st.number_input("MIN DAYS TO EARNINGS", value=0)
    
    target_date = st.text_input("Force Expiry Date", value="2026-04-24")

# 3. SCANNER LOGIC
if st.button("🚀 FORCE DEEP SCAN"):
    results = []
    debug_log = []
    progress = st.progress(0)

    for i, symbol in enumerate(TICKERS):
        progress.progress((i + 1) / len(TICKERS))
        try:
            t = yf.Ticker(symbol)
            
            # Check if expiry exists in the API's list
            if target_date not in t.options:
                debug_log.append(f"❌ {symbol}: {target_date} not in options list. Available: {t.options[:3]}")
                continue

            # Skip Analysts for the deep scan to ensure we get results
            hist = t.history(period="1d")
            if hist.empty: continue
            price = hist['Close'].iloc[-1]
            
            # Pull the Chain
            chain = t.option_chain(target_date)
            puts = chain.puts
            
            if puts.empty:
                debug_log.append(f"⚠️ {symbol}: Put chain returned empty for {target_date}")
                continue

            # Select Strike
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
            debug_log.append(f"✅ {symbol}: Found strike {opt['strike']}")
            time.sleep(0.1)
        except Exception as e:
            debug_log.append(f"🚨 {symbol}: Error -> {str(e)}")
            continue

    progress.empty()

    if results:
        st.subheader("🟢 RESULTS")
        st.table(pd.DataFrame(results))
    
    # DEBUG DRAWER: This tells us WHY it's failing
    with st.expander("🔍 API DEBUG LOG (Click to see why it's failing)"):
        for line in debug_log:
            st.text(line)
