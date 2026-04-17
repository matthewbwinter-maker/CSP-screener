import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Premium Hunter", layout="wide")
st.title("💰 Weekly CSP Premium Hunter")

# Expanded list to ensure we find "Juice"
TICKERS = ['TSLA', 'NVDA', 'AMD', 'AAPL', 'AMZN', 'GOOGL', 'NFLX', 'META', 'COIN', 'MARA', 'MSTR', 'RIVN', 'BABA']

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
        status.text(f"Scanning {symbol}...")
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="1y")
            if len(hist) < 30: continue
            
            # Get Nearest Weekly Options
            exp = t.options[0]
            chain = t.option_chain(exp)
            
            # Find the ~5% OTM Put
            current_price = hist['Close'].iloc[-1]
            target_strike = current_price * 0.95
            idx = (chain.puts['strike'] - target_strike).abs().idxmin()
            put_option = chain.puts.loc[idx]
            
            # --- METRICS ---
            iv_val = put_option['impliedVolatility'] * 100
            premium = (put_option['bid'] + put_option['ask']) / 2
            weekly_yield = (premium / put_option['strike']) * 100
            rsi = get_rsi(hist['Close']).iloc[-1]
            total_oi = chain.puts['openInterest'].sum()

            # --- GRANULAR SCORING ---
            score = 0
            # Volatility (Max 40)
            if iv_val > 45: score += 40
            elif iv_val > 30: score += 30
            elif iv_val > 20: score += 15
            
            # Yield (Max 20)
            if weekly_yield > 1.5: score += 20
            elif weekly_yield > 0.8: score += 10
            
            # RSI (Max 20)
            if 30 < rsi < 50: score += 20
            elif 50 <= rsi < 60: score += 10
            
            # Liquidity (Max 20)
            if total_oi > 2000: score += 20
            elif total_oi > 500: score += 10
            
            results.append({
                "Ticker": symbol,
                "Score": score,
                "Weekly %": round(weekly_yield, 2),
                "IV %": round(iv_val, 1),
                "RSI": round(rsi, 1),
                "Strike": put_option['strike'],
                "Premium": round(premium, 2),
                "Open Int": int(total_oi)
            })
        except:
            continue
            
    status.empty()
    
    if results:
        df = pd.DataFrame(results).sort_values(by="Score", ascending=False)
        st.dataframe(df, use_container_width=True)
    else:
        st.error("No data returned. Try again.")
