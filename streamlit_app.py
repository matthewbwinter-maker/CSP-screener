import streamlit as st
import yfinance as yf
import pandas as pd
import time

# UI STYLING
st.set_page_config(page_title="One-Tap Exit", layout="centered")
st.markdown("<style>.stApp { background-color: #000000; color: #FFFFFF; }</style>", unsafe_allow_html=True)

st.title("🎯 ONE-TAP SCANNER")
st.caption("Targeting April 24, 2026 | Lower Frequency Mode")

# INPUTS
symbol = st.text_input("Enter Ticker (e.g. NVDA, AAPL)", "NVDA").upper()
otm_target = st.slider("OTM Safety (%)", 3, 15, 8)
target_date = "2026-04-24"

if st.button(f"🔍 SCAN {symbol}"):
    try:
        t = yf.Ticker(symbol)
        
        # 1. Price Check
        price = t.history(period="1d")['Close'].iloc[-1]
        
        # 2. Options Fetch (The most sensitive part)
        chain = t.option_chain(target_date)
        puts = chain.puts
        
        # 3. Logic
        strike_goal = price * (1 - (otm_target / 100))
        idx = (puts['strike'] - strike_goal).abs().idxmin()
        opt = puts.loc[idx]
        
        # Display Result in Big Bold Cards for Phone
        st.metric(label="Current Price", value=f"${round(price, 2)}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.success(f"STRIKE: {opt['strike']}")
        with col2:
            st.info(f"PREMIUM: ${round((opt['bid']+opt['ask'])/2, 2)}")
            
        st.warning(f"Strategy: Sell to Open the {opt['strike']} Put")
        
    except Exception as e:
        st.error("Yahoo is currently blocking this request. Wait 60 seconds and try a different ticker.")
