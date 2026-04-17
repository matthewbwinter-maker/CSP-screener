import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import time

# ──────────────────────────────────────────────
# 1. ULTIMATE CONTRAST UI (Fixes Sidebar Visibility)
# ──────────────────────────────────────────────
st.set_page_config(page_title="High-Vis Alpha", layout="wide")

st.markdown("""
<style>
    /* Main App Background */
    .stApp { background-color: #000000; color: #FFFFFF; }
    
    /* SIDEBAR TEXT & WIDGET VISIBILITY */
    /* Forces all labels and slider values to Pure White */
    [data-testid="stSidebar"] .stText, 
    [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span {
        color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 1.05rem !important;
    }

    /* SLIDER CONTRAST FIX */
    /* Makes the slider track and numbers clearly visible */
    .stSlider [data-baseweb="slider"] {
        background-color: #333333; /* Darker track for contrast */
    }
    div[data-testid="stThumbValue"] {
        color: #00FF00 !important; /* Neon green value above the slider thumb */
        font-weight: 900 !important;
    }

    /* NUMBER INPUT CONTRAST */
    /* Makes the box and the numbers inside high-contrast */
    [data-testid="stSidebar"] input {
        color: #00FF00 !important;
        background-color: #111111 !important;
        border: 1px solid #FFFFFF !important;
    }

    /* HEADERS & BUTTONS */
    h1, h2, h3 { color: #00FF00 !important; font-family: monospace; }
    div.stButton > button {
        background-color: #00FF00; color: #000000; 
        font-weight: 900; border: none; height: 3.5em; width: 100%;
    }
    
    /* TABLE CONTRAST */
    .stTable { background-color: #111111; border: 2px solid #444444; }
    thead tr th { background-color: #00FF00 !important; color: #000000 !important; }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ WEEKLY EXIT STRATEGY")
st.caption("Focus: Low Assignment Risk | Analyst 'Buy' Ratings | High Visibility")

# ──────────────────────────────────────────────
# 2. CONFIGURATION (Visible Sidebar)
# ──────────────────────────────────────────────
with st.sidebar:
    st.header("⚡ FILTERS")
    
    # Text area for tickers
    ticker_str = st.text_area("Vetting Universe", 
                             "AAPL, MSFT, GOOGL, AMZN, NVDA, META, JPM, V, UNH, XOM, WMT, PG, AVGO, ORCL, COST, HD, ABBV")
    TICKERS = [t.strip().upper() for t in ticker_str.split(",") if t.strip()]
    
    st.divider()
    
    # Sliders - Now with white labels and green values
    otm_target = st.slider("OTM Safety (%)", 5, 20, 8)
    
    # Number input - Now with high-contrast borders
    earn_buffer = st.number_input("Min Days to Earnings", value=10, step=1)

# [Remaining Scanner Logic from previous version starts here...]
