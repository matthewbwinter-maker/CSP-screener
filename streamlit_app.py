import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import time

# ──────────────────────────────────────────────
# 1. PAGE SETUP & UI
# ──────────────────────────────────────────────
st.set_page_config(page_title="Act 60 Wheel Pro", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0a0e1a; color: #c8d4e8; }
    h1, h2, h3 { font-family: monospace; color: #00d4aa; }
    .reportview-container .main .block-container { padding-top: 2rem; }
    .stMetric { background: #131d35; border: 1px solid #1e2d4a; border-radius: 5px; padding: 10px; }
    div.stButton > button:first-child {
        background: linear-gradient(90deg, #00d4aa, #0095ff);
        color: #0a0e1a; font-weight: bold; width: 100%; border: none; height: 3em;
    }
</style>
""", unsafe_allow_html=True)

st.title("🎡 Act 60 Wheel Pro")
st.caption("Strategic Cash-Secured Put Screener | Puerto Rico Tax-Exempt Yield")

# ──────────────────────────────────────────────
# 2. SIDEBAR PARAMETERS
# ──────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    ticker_str = st.text_area("Tickers (Comma Separated)", 
                             "TSLA, NVDA, AMD, AAPL, AMZN, MSFT, GOOGL, META, COIN, MSTR, NFLX, MARA, PLTR")
    TICKERS = [t.strip().upper() for t in ticker_str.split(",") if t.strip()]
    
    st.divider()
    min_yield = st.slider("Min Annual Yield (%)", 10, 80, 20)
    otm_dist = st.slider("OTM Distance (%)", 2, 20, 7)
    earn_safe = st.slider("Earnings Hard Block (Days)", 0, 14, 7)
    
    st.info("Tip: If it won't run, reduce the number of tickers. Yahoo Finance limits rapid requests.")

# ──────────────────────────────────────────────
# 3. SCANNER ENGINE
# ──────────────────────────────────────────────
if st.button("⚡ EXECUTE STRATEGIC SCAN"):
    results = []
    progress = st.progress(0)
    status = st.empty()
    
    for i, symbol in enumerate(TICKERS):
        # Update progress
        progress.progress((i + 1) / len(TICKERS))
        status.markdown(f"**Analyzing:** `{symbol}`")
        
        try:
            ticker_obj = yf.Ticker(symbol)
            
            # Fetch History (Lite call)
            hist = ticker_obj.history(period="150d")
            if hist.empty: continue
            
            # Technical Metrics
            curr_price = hist['Close'].iloc[-1]
            sma_50 = hist['Close'].rolling(50).mean().iloc[-1]
            
            # Earnings Safety Check
            days_to_earn = 99
            try:
                cal = ticker_obj.get_calendar()
                if cal is not None and not cal.empty:
                    next_earn = pd.to_datetime(cal.iloc[0, 0]).replace(tzinfo=None)
                    days_to_earn = (next_earn - datetime.now()).days
            except: pass
            
            if 0 <= days_to_earn <= earn_safe:
                continue # Hard block earnings risk

            # Option Chain Logic
            if not ticker_obj.options: continue
            
            # Select nearest weekly (min 4 days out)
            target_expiry = ticker_obj.options[0]
            for exp in ticker_obj.options:
                d_to_exp = (datetime.strptime(exp, "%Y-%m-%d") - datetime.now()).days
                if 4 <= d_to_exp <= 12:
                    target_expiry = exp
                    break
            
            chain = ticker_obj.option_chain(target_expiry)
            puts = chain.puts
            
            # Find strike nearest to OTM target
            target_strike_val = curr_price * (1 - (otm_dist / 100))
            idx = (puts['strike'] - target_strike_val).abs().idxmin()
            opt = puts.loc[idx]
            
            # Premium & Yield
            # Use Mid-price, fallback to lastPrice if bid/ask are 0 (weekend/pre-market)
            premium = (opt['bid'] + opt['ask']) / 2 if (opt['bid'] + opt['ask']) > 0 else opt['lastPrice']
            if premium <= 0: continue
            
            weekly_y = (premium / opt['strike']) * 100
            annual_y = weekly_y * 52
            
            if annual_y < min_yield: continue
            
            # Scoring (Linear Model)
            score = 50
            score += (weekly_y * 20)  # Reward yield
            # Support Bonus: Higher score if price is near/below 50MA
            dist_sma_pct = ((curr_price / sma_50) - 1) * 100
            score -= (dist_sma_pct * 3) 
            
            results.append({
                "Ticker": symbol,
                "Score": round(score, 1),
                "Annual %": f"{round(annual_y, 1)}%",
                "Weekly %": f"{round(weekly_y, 2)}%",
                "Strike": opt['strike'],
                "Price": round(curr_price, 2),
                "Premium": round(premium, 2),
                "Dist 50MA": f"{round(dist_sma_pct, 1)}%",
                "Earn In": f"{days_to_earn}d",
                "Expiry": target_expiry
            })
            
            # Throttle to avoid rate limits
            time.sleep(0.3)
            
        except Exception as e:
            st.warning(f"Skipped {symbol}: Data unavailable.")
            continue

    # ──────────────────────────────────────────────
    # 4. DISPLAY RESULTS
    # ──────────────────────────────────────────────
    status.empty()
    progress.empty()

    if results:
        df = pd.DataFrame(results).sort_values("Score", ascending=False)
        
        st.subheader("🏆 Ranked Top Picks")
        
        # Summary Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Top Pick", df.iloc[0]['Ticker'])
        m2.metric("Qualified Trades", len(df))
        m3.metric("Avg Annual Yield", f"{round(df['Annual %'].str.rstrip('%').astype(float).mean(), 1)}%")
        
        st.dataframe(df, use_container_width=True)
        
        # Action Item
        top = df.iloc[0]
        st.success(f"**Actionable Entry:** Sell 1 Put on **{top['Ticker']}** at **${top['Strike']}** strike for **${top['Premium']}** premium. (Yield: {top['Weekly %']} / week)")
    else:
        st.error("No trades passed your filters. Try lowering the 'Min Annual Yield' or 'OTM Distance'.")

st.divider()
st.markdown("<center style='font-size:12px; color:gray;'>FOR PERSONAL USE | DATA BY YAHOO FINANCE</center>", unsafe_allow_html=True)
