import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Put Screener", layout="wide")
st.title("🎯 Blue Chip Put Screener")

# Simplified Ticker List to ensure success
TICKERS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'JPM', 'PG', 'KO', 'TSLA']

def get_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9) # Avoid division by zero
    return 100 - (100 / (1 + rs))

if st.button("Run Global Scan"):
    results = []
    status = st.empty()
    
    for symbol in TICKERS:
        status.text(f"Scanning {symbol}...")
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="1y")
            if len(hist) < 20: continue
            
            # Fundamentals
            info = t.info
            score = 0
            
            # Quality Checks
            if info.get('debtToEquity', 200) < 150: score += 25
            if info.get('payoutRatio', 1) < 0.7: score += 25
            
            # Technicals
            rsi_vals = get_rsi(hist['Close'])
            last_rsi = rsi_vals.iloc[-1]
            if 30 < last_rsi < 60: score += 25
            
            # Options
            exp = t.options[0]
            chain = t.option_chain(exp)
            if not chain.puts.empty: score += 25
            
            results.append({
                "Ticker": symbol, 
                "Score": score, 
                "Price": round(hist['Close'].iloc[-1], 2),
                "RSI": round(last_rsi, 1)
            })
        except Exception as e:
            continue
            
    status.empty()
    
    if results:
        df = pd.DataFrame(results)
        df = df.sort_values(by="Score", ascending=False)
        st.table(df)
    else:
        st.error("No data found. The markets might be closed or the API is rate-limiting. Try again in a moment.")
