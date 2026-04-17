import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Premium Hunter", layout="wide")
st.title("💰 Weekly CSP Premium Hunter")

# Tickers known for high options liquidity and "juice"
TICKERS = ['TSLA', 'NVDA', 'AMD', 'AAPL', 'AMZN', 'GOOGL', 'NFLX', 'META', 'COIN', 'MARA']

def get_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

if st.button("🔥 Scan for Juice"):
    results = []
    status = st.empty()
    
    for symbol in TICKERS:
        status.text(f"Calculating yield for {symbol}...")
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="1y")
            if len(hist) < 30: continue
            
            # Get Nearest Weekly Options
            exp = t.options[0]
            chain = t.option_chain(exp)
            
            # We look at the Put closest to 5% Out-of-the-Money (OTM)
            current_price = hist['Close'].iloc[-1]
            target_strike = current_price * 0.95
            
            # Find the actual strike in the chain closest to our target
            idx = (chain.puts['strike'] - target_strike).abs().idxmin()
            put_option = chain.puts.loc[idx]
            
            # --- CALCULATIONS ---
            iv_val = put_option['impliedVolatility'] * 100
            premium = (put_option['bid'] + put_option['ask']) / 2
            # Weekly Yield = Premium / Strike Price
            weekly_yield = (premium / put_option['strike']) * 100
            
            rsi = get_rsi(hist['Close']).iloc[-1]
            total_oi = chain.puts['openInterest'].sum()

            # --- THE SCOREBOARD ---
            score = 0
            if iv_val > 30: score += 40      # Volatility is King
            if weekly_yield > 1.0: score += 20 # >1% per week is the goal
            if total_oi > 1000: score += 20   # Liquidity
            if 30 < rsi < 50: score += 20     # Technical Entry
            
            results.append({
                "Ticker": symbol,
                "Score": score,
                "Weekly Yield %": round(weekly_yield, 2),
                "IV %": round(iv_val, 1),
                "RSI": round(rsi, 1),
                "Strike": put_option['strike'],
                "Premium $": round(premium, 2),
                "Open Int": int(total_oi)
            })
        except:
            continue
            
    status.empty()
    
    if results:
        df = pd.DataFrame(results).sort_values(by="Score", ascending=False)
        st.dataframe(df, use_container_width=True)
        st.write("*(Weekly Yield assumes selling a 5% Out-of-the-Money Put)*")
    else:
        st.error("Markets might be closed or API is throttled. Try again in 1 minute.")
