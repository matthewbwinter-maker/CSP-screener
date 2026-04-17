import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import warnings

warnings.filterwarnings("ignore")

# ──────────────────────────────────────────────
# PAGE CONFIG & THEME
# ──────────────────────────────────────────────
st.set_page_config(page_title="Act 60 Wheel Engine", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; background-color: #0a0e1a; color: #c8d4e8; }
    .stApp { background-color: #0a0e1a; }
    h1, h2, h3 { font-family: 'IBM Plex Mono', monospace; color: #00d4aa; }
    .stMetric { background: #0f1629; border: 1px solid #1e2d4a; border-radius: 4px; padding: 10px; }
    .info-box { background: #001a2a; border-left: 3px solid #0095ff; padding: 15px; border-radius: 4px; font-size: 13px; margin: 10px 0; }
    .stButton > button { background: linear-gradient(90deg, #00d4aa, #0095ff); color: #0a0e1a; font-family: 'IBM Plex Mono', monospace; font-weight: 600; width: 100%; border: none; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# HEADER
# ──────────────────────────────────────────────
st.markdown("## ⚙ ACT 60 PREMIUM ENGINE")
st.markdown("<span style='color:#6b7a99; font-family:IBM Plex Mono'>Wheel Strategy Optimizer | 80% Prob. Focus | PRSCI Tax-Exempt</span>", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# SIDEBAR CONTROLS
# ──────────────────────────────────────────────
with st.sidebar:
    st.header("🏝 Parameters")
    ticker_input = st.text_area("Tickers", "TSLA, NVDA, AMD, AAPL, AMZN, MSFT, GOOGL, META, COIN, MSTR, NFLX, DIS, MARA, PLTR, HOOD", height=100)
    TICKERS = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]
    
    st.divider()
    min_annual = st.slider("Min Annual Yield (%)", 10, 100, 20)
    max_spread = st.slider("Max Spread (% of Mid)", 10, 60, 40)
    earn_block = st.slider("Earnings Hard Block (Days)", 0, 14, 7)
    
    st.header("Targeting")
    strike_dist = st.slider("OTM Distance (%)", 3, 20, 7)
    
    run_scan = st.button("⚡ RUN STRATEGIC SCAN")

# ──────────────────────────────────────────────
# CORE LOGIC FUNCTIONS
# ──────────────────────────────────────────────
def get_rsi(series):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    return
   
